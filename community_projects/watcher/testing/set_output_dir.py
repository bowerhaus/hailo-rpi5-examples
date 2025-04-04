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
    
    # Determine which app to run
    if args.app == "helen-o-matic":
        app_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "helen-o-matic")
        cmd = [
            "python", "helen_o_matic.py",
            "--use-frame",
            "--hef-path", "models/helen-o-matic.v6.yolov8p.hef",
            "--labels-json", "models/helen-o-matic.v5-labels.json",
            "--input", input_path
        ]
    else:  # pigeonator
        app_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pigeonator")
        cmd = [
            "python", "pigeonator.py",
            "--use-frame",
            "--hef-path", "models/pigeonator-mk3-b.v4.yolov8.hef",
            "--labels-json", "models/pigeonator-mk3-b.v3-labels.json",
            "--input", input_path
        ]
    
    # Run the command with the modified environment
    try:
        print(f"Running {args.app} with output directory: {output_dir}")
        os.chdir(app_dir)
        subprocess.run(cmd, env=env, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("Process interrupted")
        sys.exit(130)
