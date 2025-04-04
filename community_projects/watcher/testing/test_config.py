import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from test_runner import TestCase

# Base directory for test data - renamed from testdata to test_data
TEST_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_data")

# Custom validation functions
def validate_helen_direction(metadata):
    """Validate that a helen_out detection has a direction between 25-100 degrees."""
    errors = []
    if metadata.get("label") == "HELEN_OUT":
        direction = metadata.get("direction", 0)
        if not (25 <= direction < 100):
            errors.append(f"Direction for HELEN_OUT should be between 25-100, got {direction}")
    elif metadata.get("label") == "HELEN_BACK":
        direction = metadata.get("direction", 0)
        if not (205 <= direction < 280):
            errors.append(f"Direction for HELEN_BACK should be between 205-280, got {direction}")
    return errors

def validate_pigeon_deterrent(metadata):
    """Validate that a pigeon detection has appropriate event duration."""
    errors = []
    if metadata.get("class") == "pigeon":
        event_seconds = metadata.get("event_seconds", 0)
        if event_seconds < 5:
            errors.append(f"Pigeon event too short: {event_seconds} seconds")
    return errors

# Define test cases
TEST_CASES = [
    # Helen-O-Matic test cases
    TestCase(
        name="helen_out_test",
        input_file=os.path.abspath(os.path.join(TEST_DATA_DIR, "helen_out.mp4")),
        app_type="helen-o-matic",
        expected_metadata={
            "class": "dog",
            "label": "HELEN_OUT",
            "direction": {"range": [25, 100]},
            "named_direction": "OUT"
        },
        expected_classes={
            "helen_out": {"ge": 50.0}, 
            "person": {"lt": 50.0}, 
            "dog": {"ge": 50.0}
        },
        custom_validation=validate_helen_direction
    ),
    TestCase(
        name="helen_back_test",
        input_file=os.path.abspath(os.path.join(TEST_DATA_DIR, "helen_back.mp4")),
        app_type="helen-o-matic",
        expected_metadata={
            "class": "dog",
            "label": "HELEN_BACK",
            "direction": {"range": [205, 280]},
            "named_direction": "BACK"
        },
        expected_classes={
            "helen_back": {"ge": 50.0},  
            "person": {"lt": 50.0}, 
            "dog": {"ge": 50.0}
        },
        custom_validation=validate_helen_direction
    ),
    TestCase(
        name="person_with_dog_out_test",
        input_file=os.path.abspath(os.path.join(TEST_DATA_DIR, "out.mp4")),
        app_type="helen-o-matic",
        expected_metadata={
            "class": "dog",
            "label": None
        },
        expected_classes={
            "person": {"ge": 50.0},
            "dog": {"ge": 47}
        }
    ),
    
    # Pigeonator test cases
    TestCase(
        name="pigeon_test",
        input_file=os.path.abspath(os.path.join(TEST_DATA_DIR, "two_pigeons.mp4")),
        app_type="pigeonator",
        expected_metadata={
            "class": "pigeon",
            "max_instances": {"range": [1, 3]},
            "event_seconds": {"gt": 5}
        },
        expected_classes={
            "pigeon": {"ge": 70.0}
        },
        custom_validation=validate_pigeon_deterrent
    )
]
