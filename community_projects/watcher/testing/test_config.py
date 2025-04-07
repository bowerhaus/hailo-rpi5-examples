import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from test_runner import TestCase

# Base directory for test data
TEST_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_data")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HELEN_HEF = os.path.join(BASE_DIR, "helen-o-matic", "models", "helen-o-matic.v7.yolov8p.hef")
HELEN_LABELS = os.path.join(BASE_DIR, "helen-o-matic", "models", "helen-o-matic.v5-labels.json")
PIGEON_HEF = os.path.join(BASE_DIR, "pigeonator", "models", "pigeonator-mk3-b.v4.yolov8p.hef")
PIGEON_LABELS = os.path.join(BASE_DIR, "pigeonator", "models", "pigeonator-mk3-b.v3-labels.json")

# App test config files - moved to test_data directory
HELEN_CONFIG = os.path.join(TEST_DATA_DIR, "helen_config.json")
PIGEON_CONFIG = os.path.join(TEST_DATA_DIR, "pigeon_config.json")

# Define default configurations for each app type
APP_DEFAULTS = {
    "helen-o-matic": {
        "hef_path": HELEN_HEF,
        "labels_json": HELEN_LABELS,
        "config_file": HELEN_CONFIG
    },
    "pigeonator": {
        "hef_path": PIGEON_HEF,
        "labels_json": PIGEON_LABELS,
        "config_file": PIGEON_CONFIG
    }
}

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
            "helen_out": {"ge": 42.0},  
            "dog": {"ge": 50.0}
        },
        custom_validation=validate_helen_direction
    ),
    
    # Low threshold test using custom config
    TestCase(
        name="helen_out_low_percent_test",
        input_file=os.path.abspath(os.path.join(TEST_DATA_DIR, "helen_out_low_percent.mp4")),
        app_type="helen-o-matic",
        expected_metadata={
            "class": "dog",
            "label": "HELEN_OUT",
            "direction": {"range": [25, 100]},
            "named_direction": "OUT"
        },
        expected_classes={
            "helen_out": {"ge": 28.0},  
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
            "dog": {"ge": 45}
        }
    ),
    TestCase(
        name="false_dog_test",
        input_file=os.path.abspath(os.path.join(TEST_DATA_DIR, "false_dog.mp4")),
        app_type="helen-o-matic",
        expect_metadata=False,  # This test will not produce metadata because no class matches
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
        custom_validation=validate_pigeon_deterrent
    )
]
