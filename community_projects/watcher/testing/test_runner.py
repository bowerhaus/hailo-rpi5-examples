import os
import sys
import json
import glob
import time
import shutil
import subprocess
import argparse
import datetime
import jsonschema
import threading
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable

# Add parent directory to path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from logger_config import logger
from comparison_utils import ValueValidator

# Constants
DEFAULT_TIMEOUT = 60  # Default timeout in seconds for test execution
TEST_OUTPUT_DIR = "test_output"  # Directory for test outputs


@dataclass
class TestCase:
    """
    Represents a single test case for watcher applications.
    """
    name: str
    input_file: str
    app_type: str  # 'helen-o-matic' or 'pigeonator'
    hef_path: Optional[str] = None
    labels_json: Optional[str] = None
    config_file: Optional[str] = None
    expected_metadata: Dict[str, Any] = field(default_factory=dict)
    expected_classes: Dict[str, Any] = field(default_factory=dict)
    timeout: int = DEFAULT_TIMEOUT
    custom_validation: Optional[Callable] = None
    expect_metadata: bool = True  # Flag to indicate if metadata should be generated
    
    def __post_init__(self):
        # Import the defaults here to avoid circular imports
        # Get the APP_DEFAULTS from test_config
        try:
            from test_config import APP_DEFAULTS
            
            # Use defaults if not provided
            if self.app_type in APP_DEFAULTS:
                app_defaults = APP_DEFAULTS[self.app_type]
                
                # Only apply defaults if the values weren't explicitly provided
                if self.hef_path is None and "hef_path" in app_defaults:
                    self.hef_path = app_defaults["hef_path"]
                    
                if self.labels_json is None and "labels_json" in app_defaults:
                    self.labels_json = app_defaults["labels_json"]
                    
                if self.config_file is None and "config_file" in app_defaults:
                    self.config_file = app_defaults["config_file"]
        except (ImportError, AttributeError):
            # If APP_DEFAULTS is not defined, continue with provided values
            pass
            
        # Ensure input file exists
        if not os.path.exists(self.input_file):
            raise ValueError(f"Input file {self.input_file} does not exist")
        if self.hef_path and not os.path.exists(self.hef_path):
            raise ValueError(f"HEF file {self.hef_path} does not exist")
        if self.labels_json and not os.path.exists(self.labels_json):
            raise ValueError(f"Labels JSON file {self.labels_json} does not exist")
        if self.config_file and not os.path.exists(self.config_file):
            raise ValueError(f"Config file {self.config_file} does not exist")


class TestRunner:
    """
    Test runner for watcher applications that handles executing apps with test data
    and validating the output metadata.
    """
    
    def __init__(self, test_cases: List[TestCase], output_dir: str = TEST_OUTPUT_DIR):
        self.test_cases = test_cases
        self.output_dir = output_dir
        self.results = []
        
        # Create output directory if it doesn't exist
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Load metadata schema for validation
        schema_path = os.path.join(os.path.dirname(__file__), "schemas", "metadata_schema.json")
        if os.path.exists(schema_path):
            with open(schema_path, 'r') as f:
                self.metadata_schema = json.load(f)
        else:
            logger.warning(f"Schema file {schema_path} not found, schema validation will be skipped")
            self.metadata_schema = None
    
    def filter_tests(self, app_type=None, test_name=None):
        """
        Filter test cases by app type or test name.
        
        Args:
            app_type (str, optional): The app type to filter by ('helen-o-matic' or 'pigeonator').
            test_name (str, optional): The specific test name to run.
            
        Returns:
            List[TestCase]: The filtered list of test cases.
        """
        filtered_tests = self.test_cases.copy()
        
        if app_type:
            filtered_tests = [test for test in filtered_tests if test.app_type == app_type]
            logger.info(f"Filtered tests by app type '{app_type}', {len(filtered_tests)} tests remaining")
            
        if test_name:
            filtered_tests = [test for test in filtered_tests if test.name == test_name]
            logger.info(f"Filtered tests by name '{test_name}', {len(filtered_tests)} tests remaining")
            
        if not filtered_tests:
            logger.warning("No tests match the specified filters!")
            
        return filtered_tests
    
    def display_tests_and_get_selection(self):
        """
        Display available tests and prompt the user to select one.
        
        Returns:
            TestCase: The selected test case or None if selection is invalid
        """
        if not self.test_cases:
            logger.error("No tests available to select")
            return None
            
        print("\n=== Available Tests ===")
        for i, test in enumerate(self.test_cases):
            print(f"{i+1}. {test.name} (type: {test.app_type})")
        print("======================\n")
        
        try:
            selection = input("Enter test number to run (or 'q' to quit): ")
            if selection.lower() == 'q':
                return None
                
            index = int(selection) - 1
            if 0 <= index < len(self.test_cases):
                return [self.test_cases[index]]
            else:
                logger.error(f"Invalid selection: {selection}. Please enter a number between 1 and {len(self.test_cases)}")
                return None
        except ValueError:
            logger.error("Please enter a valid number")
            return None
    
    def run_tests(self):
        """Run all test cases and collect results."""
        logger.info(f"Starting test run with {len(self.test_cases)} test cases")
        
        for i, test_case in enumerate(self.test_cases):
            logger.info(f"Running test case {i+1}/{len(self.test_cases)}: {test_case.name}")
            
            # Kill any existing Hailo processes before starting the next test
            self._kill_hailo_processes()
            
            # Wait a moment to ensure processes are fully terminated
            time.sleep(2)
            
            test_result = self.run_test(test_case)
            self.results.append(test_result)
        
        # Print summary
        self.print_summary()
        
        # Return overall success
        return all(result["success"] for result in self.results)
    
    def _kill_hailo_processes(self):
        """Kill any running Hailo processes to ensure clean test environment."""
        try:
            logger.info("Killing any existing Hailo processes...")
            subprocess.run(["pkill", "-f", "Hailo"], check=False)
            # Also kill any python processes that might be related to our tests
            subprocess.run(["pkill", "-f", "helen_o_matic.py"], check=False)
            subprocess.run(["pkill", "-f", "pigeonator.py"], check=False)
        except Exception as e:
            logger.warning(f"Error when trying to kill existing processes: {e}")
    
    def run_test(self, test_case: TestCase) -> Dict[str, Any]:
        """Run a single test case and return the result."""
        result = {
            "name": test_case.name,
            "success": False,
            "errors": [],
            "metadata": None,
            "output_files": []
        }
        
        # Save current working directory to restore it later
        original_cwd = os.getcwd()
        
        try:
            # Create a temporary output directory for this test
            # Use an absolute path based on the test runner location
            test_output_dir = os.path.abspath(os.path.join(self.output_dir, test_case.name))
            if os.path.exists(test_output_dir):
                shutil.rmtree(test_output_dir)
            os.makedirs(test_output_dir)
            
            # Get the app directory and script
            app_dir = self._get_app_directory(test_case.app_type)
            app_script = self._get_app_script(test_case.app_type)
            
            today = datetime.datetime.now().strftime("%Y%m%d")
            output_dir = os.path.join(test_output_dir, "output", today)
            os.makedirs(output_dir, exist_ok=True)
            
            # Prepare the command - use relative paths since we'll change directory
            cmd = [
                "python",
                os.path.basename(app_script),
                "--input", os.path.abspath(test_case.input_file),  # Ensure this is absolute
                "--hef-path", os.path.abspath(test_case.hef_path),
                "--labels-json", os.path.abspath(test_case.labels_json),
                "--use-frame"
            ]
            
            # Run the app as a subprocess
            logger.info(f"Executing command in {app_dir}: {' '.join(cmd)}")
            env = os.environ.copy()
            
            # Set the output directory via environment variable - use absolute path
            env["WATCHER_OUTPUT_DIRECTORY"] = os.path.abspath(os.path.join(test_output_dir, "output"))
            logger.info(f"Setting output directory to: {env['WATCHER_OUTPUT_DIRECTORY']}")
            
            # Set config file path if test case has a specific config file
            if hasattr(test_case, 'config_file') and test_case.config_file:
                env["WATCHER_CONFIG_FILE"] = os.path.abspath(test_case.config_file)
                logger.info(f"Setting config file to: {env['WATCHER_CONFIG_FILE']}")
            
            # Change to the application directory before running
            os.chdir(app_dir)
            
            process = subprocess.Popen(
                cmd, 
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,  # Use text mode for output
                bufsize=1  # Line buffered
            )
            
            # Use separate threads to read output so we don't block
            stdout_data = []
            stderr_data = []
            
            def read_output(pipe, data_list):
                for line in iter(pipe.readline, ''):
                    data_list.append(line)
                    logger.debug(line.strip())
                pipe.close()
            
            # Start output reader threads
            stdout_thread = threading.Thread(target=read_output, args=(process.stdout, stdout_data))
            stderr_thread = threading.Thread(target=read_output, args=(process.stderr, stderr_data))
            stdout_thread.daemon = True
            stderr_thread.daemon = True
            stdout_thread.start()
            stderr_thread.start()
            
            # Wait for the process to complete or timeout
            start_time = time.time()
            while process.poll() is None:
                if time.time() - start_time > test_case.timeout:
                    process.terminate()
                    try:
                        process.wait(timeout=5)  # Give it 5 seconds to terminate gracefully
                    except subprocess.TimeoutExpired:
                        process.kill()  # Force kill if it doesn't terminate
                    os.chdir(original_cwd)  # Restore original directory
                    raise TimeoutError(f"Test {test_case.name} timed out after {test_case.timeout} seconds")
                time.sleep(1)  # Check status every second
            
            # Get process output
            returncode = process.returncode
            
            # Restore original working directory
            os.chdir(original_cwd)
            
            if returncode != 0:
                stdout_thread.join(timeout=5)
                stderr_thread.join(timeout=5)
                stdout_str = '\n'.join(stdout_data)
                stderr_str = '\n'.join(stderr_data)
                raise RuntimeError(f"Process exited with code {returncode}: {stderr_str}\nStdout: {stdout_str}")
            
            # Find the metadata files produced
            metadata_files = glob.glob(os.path.join(output_dir, "*.json"))
            
            # If metadata is not expected for this test, it's a success if no files were created
            if not test_case.expect_metadata:
                if not metadata_files:
                    logger.info(f"No metadata files found as expected for test {test_case.name}")
                    result["success"] = True
                else:
                    result["errors"].append(f"Metadata files were found when none were expected: {', '.join(metadata_files)}")
                return result
            
            # If we get here, we're expecting metadata files
            if not metadata_files:
                raise FileNotFoundError(f"No metadata files found in {output_dir} but metadata was expected")
            
            # Get the latest metadata file
            latest_metadata_file = max(metadata_files, key=os.path.getctime)
            result["metadata_file"] = latest_metadata_file
            
            # Load the metadata
            with open(latest_metadata_file, 'r') as f:
                metadata = json.load(f)
                result["metadata"] = metadata
            
            # Get all output files
            result["output_files"] = [
                f for f in glob.glob(os.path.join(output_dir, "*"))
                if os.path.isfile(f)
            ]
            
            # Validate the metadata
            self._validate_metadata(result, test_case)
            
            # Mark the test as successful if no errors were found
            if not result["errors"]:
                result["success"] = True
                
        except Exception as e:
            result["errors"].append(str(e))
            logger.error(f"Error running test {test_case.name}: {e}")
            
        finally:
            # Always restore the original working directory, even if an exception occurs
            os.chdir(original_cwd)
            
            # Make sure we kill the process if it's still running
            if 'process' in locals() and process.poll() is None:
                try:
                    process.terminate()
                    process.wait(timeout=5)
                except (subprocess.TimeoutExpired, OSError):
                    try:
                        process.kill()
                    except OSError:
                        pass
        
        return result

    def _get_app_directory(self, app_type):
        """Get the directory containing the application."""
        if app_type == "helen-o-matic":
            return os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "helen-o-matic"
            )
        elif app_type == "pigeonator":
            return os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "pigeonator"
            )
        else:
            raise ValueError(f"Unknown app type: {app_type}")
    
    def _validate_metadata(self, result: Dict[str, Any], test_case: TestCase):
        """Validate metadata against expected values and schema."""
        metadata = result["metadata"]
        
        # Validate against schema if available
        if self.metadata_schema:
            try:
                jsonschema.validate(instance=metadata, schema=self.metadata_schema)
            except jsonschema.exceptions.ValidationError as e:
                result["errors"].append(f"Schema validation error: {e}")
        
        # Check expected metadata values using validators
        for key, expected_value in test_case.expected_metadata.items():
            validator = ValueValidator.create(expected_value)
            
            if key not in metadata:
                result["errors"].append(f"Expected key '{key}' not found in metadata")
            else:
                is_valid, error_msg = validator.validate(metadata[key])
                if not is_valid:
                    result["errors"].append(f"Value mismatch for key '{key}': {error_msg}")
        
        # Check expected class percentages using validators
        for class_name, expected_value in test_case.expected_classes.items():
            key = f"{class_name}_percent"
            validator = ValueValidator.create(expected_value)
            
            if key not in metadata:
                result["errors"].append(f"Expected class percentage '{key}' not found in metadata")
            else:
                is_valid, error_msg = validator.validate(metadata[key])
                if not is_valid:
                    result["errors"].append(f"Class percentage invalid for '{key}': {error_msg}")
        
        # Run custom validation if provided
        if test_case.custom_validation:
            try:
                custom_errors = test_case.custom_validation(metadata)
                if custom_errors:
                    result["errors"].extend(custom_errors)
            except Exception as e:
                result["errors"].append(f"Custom validation error: {e}")
    
    def _get_app_script(self, app_type):
        """Get the path to the application script."""
        if app_type == "helen-o-matic":
            return os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "helen-o-matic",
                "helen_o_matic.py"
            )
        elif app_type == "pigeonator":
            return os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "pigeonator",
                "pigeonator.py"
            )
        else:
            raise ValueError(f"Unknown app type: {app_type}")
    
    def print_summary(self):
        """Print a summary of the test results."""
        total = len(self.results)
        passed = sum(1 for result in self.results if result["success"])
        
        logger.info("=" * 60)
        logger.info(f"TEST SUMMARY: {passed}/{total} tests passed")
        logger.info("=" * 60)
        
        for i, result in enumerate(self.results):
            status = "PASS" if result["success"] else "FAIL"
            logger.info(f"{i+1}. {result['name']}: {status}")
            
            if not result["success"]:
                for error in result["errors"]:
                    logger.info(f"   - {error}")
        
        logger.info("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run tests for watcher applications")
    parser.add_argument("--config", default="test_config.py", help="Test configuration file")
    parser.add_argument("--app-type", choices=["helen-o-matic", "pigeonator"], 
                        help="Filter tests by application type")
    parser.add_argument("--test-name", help="Run a specific test by name")
    parser.add_argument("--list", action="store_true", help="List available tests without running them")
    parser.add_argument("--interactive", "-i", action="store_true", 
                        help="Interactive mode: list tests and select one to run")
    args = parser.parse_args()
    
    # Import test cases from config file
    if not os.path.exists(args.config):
        logger.error(f"Config file {args.config} not found")
        sys.exit(1)
    
    sys.path.append(os.path.dirname(os.path.abspath(args.config)))
    config_module = __import__(os.path.basename(args.config).replace(".py", ""))
    
    # Create test runner
    runner = TestRunner(config_module.TEST_CASES)
    
    # If --list is specified, just list the available tests and exit
    if args.list:
        logger.info("Available tests:")
        for i, test in enumerate(runner.test_cases):
            logger.info(f"{i+1}. {test.name} (type: {test.app_type})")
        sys.exit(0)
    
    # Filter tests based on command line arguments
    filtered_tests = runner.filter_tests(args.app_type, args.test_name)
    if not filtered_tests:
        logger.error("No tests to run after applying filters")
        sys.exit(1)
    
    # Replace the test cases with the filtered list
    runner.test_cases = filtered_tests
    
    # Interactive mode: Let user select from available tests
    if args.interactive:
        # Display filtered tests and get user selection
        selected_test = runner.display_tests_and_get_selection()
        if not selected_test:
            logger.info("No test selected, exiting")
            sys.exit(0)
        runner.test_cases = selected_test
    
    # Run tests
    success = runner.run_tests()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)
