#!/usr/bin/env python3

import os
import sys
import argparse
from test_runner import TestRunner
import importlib.util

def load_test_case_from_config(config_file, test_name):
    """Load a specific test case from a configuration file."""
    # Load the module from file path
    spec = importlib.util.spec_from_file_location("config_module", config_file)
    config_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config_module)
    
    # Find the test case with the matching name
    for test_case in config_module.TEST_CASES:
        if test_case.name == test_name:
            return test_case
    
    raise ValueError(f"Test case '{test_name}' not found in configuration file")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run a single test for watcher applications")
    parser.add_argument("--config", default="test_config.py", help="Test configuration file")
    parser.add_argument("--test", required=True, help="Name of the test case to run")
    parser.add_argument("--no-metadata", action="store_true", help="Skip metadata validation for this test")
    args = parser.parse_args()
    
    # Import test case from config file
    if not os.path.exists(args.config):
        print(f"Config file {args.config} not found")
        sys.exit(1)
    
    try:
        test_case = load_test_case_from_config(args.config, args.test)
        print(f"Running test: {test_case.name}")
        
        # Override expect_metadata if --no-metadata flag is used
        if args.no_metadata:
            test_case.expect_metadata = False
            print("Metadata validation will be skipped for this test")
        
        # Kill any existing Hailo processes
        os.system("pkill -f Hailo")
        os.system("pkill -f helen_o_matic.py")
        os.system("pkill -f pigeonator.py")
        os.system("pkill -f peetronic.py")
        os.system("pkill -f bluebox.py")
        
        # Run the test
        runner = TestRunner([test_case])
        success = runner.run_tests()
        
        # Exit with appropriate code
        sys.exit(0 if success else 1)
    
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
