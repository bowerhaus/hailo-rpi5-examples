# Watcher Applications Testing Framework

This directory contains a testing framework for validating the behavior of watcher applications such as helen-o-matic and pigeonator.

## Overview

The testing framework allows you to:

1. Run applications with sample MP4 files as input
2. Validate the metadata JSON files produced by the applications
3. Check for specific class percentages and expected behaviors
4. Aggregate test results and produce a summary
5. Filter test cases based on specific criteria
6. Handle cases where no metadata is expected to be generated
7. Use the `expect_metadata` flag to specify whether metadata is expected for a test case
8. Use default HEF and label files based on the app type
9. Interactively select tests to run from a filtered list

## Directory Structure

```
testing/
├── schemas/                # JSON schemas for validation
│   └── metadata_schema.json
├── testdata/              # Test video files
│   ├── helen_out.mp4
│   ├── helen_back.mp4
│   ├── helen_with_dog.mp4
│   └── pigeon.mp4
├── test_output/           # Test output files (created when tests run)
├── test_runner.py         # The main test runner
├── test_config.py         # Test case definitions
└── README.md              # This file
```

## Getting Started

1. Place your test video files in the `test_data` directory.
2. Update `test_config.py` to add your test cases.
3. Run the tests.

## Running Tests

To run all tests defined in `test_config.py`:

```
cd /home/bower/hailo-rpi5-examples/community_projects/watcher
python -m testing.test_runner
```

To use a different test configuration file:

```
python -m testing.test_runner --config /path/to/custom_config.py
```

To filter test cases based on criteria:

```
python -m testing.test_runner --filter "app_type=helen-o-matic"
```

To run a single test by name:

```
python -m testing.test_runner --test-name "helen_out_test"
```

To list available tests without running them:

```
python -m testing.test_runner --list
```

To interactively select which test to run:

```
python -m testing.test_runner --interactive
# or the shorter version
python -m testing.test_runner -i
```

You can also combine the interactive mode with filters:

```
python -m testing.test_runner --app-type helen-o-matic --interactive
```

## Defining Test Cases

Test cases are defined in `test_config.py`. Each test case specifies:

- `name`: A unique name for the test
- `input_file`: Path to the input MP4 file
- `app_type`: Either 'helen-o-matic' or 'pigeonator'
- `hef_path`: (Optional) Path to the HEF file, uses default if not provided
- `labels_json`: (Optional) Path to the labels JSON file, uses default if not provided
- `expected_metadata`: Key-value pairs that should match in the output JSON
- `expected_classes`: Minimum percentage values for specific classes
- `timeout`: Maximum time in seconds to wait for the test to complete (default: 60)
- `custom_validation`: An optional function for additional validation
- `expect_metadata`: A flag indicating whether metadata is expected to be generated (default: True)

Example test case:

```python
TestCase(
    name="helen_out_test",
    input_file="testdata/helen_out.mp4",
    app_type="helen-o-matic",
    expected_metadata={
        "class": "person",
        "label": "HELEN_OUT"
    },
    expected_classes={
        "helen_out": {"ge": 50.0},  # Expect at least 50% helen_out
        "person": {"ge": 80.0}      # Expect at least 80% person
    },
    expect_metadata=True
)
```

## Default HEF and Label Files

The framework uses default HEF and label files for each app type, which are defined in `test_config.py`:

```python
APP_DEFAULTS = {
    "helen-o-matic": {
        "hef_path": HELEN_HEF,
        "labels_json": HELEN_LABELS
    },
    "pigeonator": {
        "hef_path": PIGEON_HEF,
        "labels_json": PIGEON_LABELS
    }
}
```

When creating test cases, you can omit the `hef_path` and `labels_json` parameters, and the default values will be used based on the `app_type`.

## Custom Validation

You can define custom validation functions to perform additional checks on the metadata:

```python
def validate_helen_direction(metadata):
    errors = []
    if metadata.get("label") == "HELEN_OUT":
        direction = metadata.get("direction", 0)
        if not (25 <= direction < 100):
            errors.append(f"Direction for HELEN_OUT should be between 25-100, got {direction}")
    return errors
```

Then assign this function to the `custom_validation` parameter of your test case.

## Adding New Test Cases

To add a new test case:

1. Add your test video to the `test_data` directory
2. Define a new `TestCase` in `test_config.py`
3. Add any custom validation functions needed

## Interpreting Results

After running tests, you'll see a summary of results in the console:

```
==============================================================
TEST SUMMARY: 3/4 tests passed
==============================================================
1. helen_out_test: PASS
2. helen_back_test: PASS
3. helen_with_dog_test: PASS
4. pigeon_test: FAIL
   - Expected class percentage 'pigeon_percent' not found in metadata
==============================================================
```

For failed tests, you can examine the detailed errors and inspect the output files in the `test_output` directory.
