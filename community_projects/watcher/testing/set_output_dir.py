#!/usr/bin/env python3
"""
Helper script to run watcher applications with a specific output directory
without modifying the command line arguments.
"""

import os
import sys
import subprocess
import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run a watcher application with a specific output directory")
    parser.add_argument("--output-dir", required=True, help="Output directory for metadata and recordings")
    parser.add_argument("--app", choices=["helen-o-matic", "pigeonator"], required=True, help="Application to run")
    parser.add_argument("--input", default="rpi", help="Input source (default: rpi)")
    parser.add_argument("--hef-path", help="Path to HEF file (optional, uses default if not provided)")
    parser.add_argument("--labels-json", help="Path to labels JSON file (optional, uses default if not provided)")
    args = parser.parse_args()
    
    # Convert output directory to absolute path
    output_dir = os.path.abspath(args.output_dir)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
    
    # Ensure input is an absolute path if it's a file
    input_path = args.input
    if input_path != "rpi" and not input_path.startswith("/dev/") and os.path.exists(input_path):
        input_path = os.path.abspath(input_path)
        
    # Set up environment with output directory
    env = os.environ.copy()
    env["WATCHER_OUTPUT_DIRECTORY"] = output_dir
    print(f"Setting WATCHER_OUTPUT_DIRECTORY to: {output_dir}")
    
    # Import the defaults
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    try:
        from test_config import APP_DEFAULTS
    except ImportError:
        print("Warning: Could not import APP_DEFAULTS from test_config, using hardcoded defaults")
        APP_DEFAULTS = {
            "helen-o-matic": {
                "hef_path": "models/helen-o-matic.v7.yolov8.hef",
                "labels_json": "models/helen-o-matic.v5-labels.json"
            },
            "pigeonator": {
                "hef_path": "models/pigeonator-mk3-b.v4.yolov8.hef",
                "labels_json": "models/pigeonator-mk3-b.v3-labels.json"
            }
        }
    
    # Determine which app to run
    app_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), args.app)
    
    # Use provided HEF and labels, fall back to defaults
    hef_path = args.hef_path
    labels_json = args.labels_json
    
    if not hef_path and args.app in APP_DEFAULTS:
        hef_path = APP_DEFAULTS[args.app]["hef_path"]
        # Convert to relative path if it's in the app directory
        if os.path.dirname(os.path.abspath(hef_path)).startswith(app_dir):
            hef_path = os.path.relpath(hef_path, app_dir)
    
    if not labels_json and args.app in APP_DEFAULTS:
        labels_json = APP_DEFAULTS[args.app]["labels_json"]
        # Convert to relative path if it's in the app directory
        if os.path.dirname(os.path.abspath(labels_json)).startswith(app_dir):
            labels_json = os.path.relpath(labels_json, app_dir)
    
    # Build the command
    if args.app == "helen-o-matic":
        cmd = [
            "python", "helen_o_matic.py",
            "--use-frame",
            "--hef-path", hef_path,
            "--labels-json", labels_json,
            "--input", input_path
        ]
    else:  # pigeonator
        cmd = [
            "python", "pigeonator.py",
            "--use-frame",
            "--hef-path", hef_path,
            "--labels-json", labels_json,
            "--input", input_path
        ]
    
    # Run the command with the modified environment
    try:
        print(f"Running {args.app} with output directory: {output_dir}")
        print(f"Using HEF: {hef_path}")
        print(f"Using labels: {labels_json}")
        os.chdir(app_dir)
        subprocess.run(cmd, env=env, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("Process interrupted")
        sys.exit(130)
