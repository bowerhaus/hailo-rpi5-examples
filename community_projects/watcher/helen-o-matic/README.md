# Helen-O-Matic

## Overview
Helen-O-Matic is an AI-powered dog monitoring system built on the Hailo edge AI platform and Raspberry Pi 5. 
The system specifically tracks dogs as they enter and exit a monitored area.

## Purpose
Helen-O-Matic was designed to:
- Monitor and track dogs as they move in and out of the area
- Intelligently determine the direction of movement (IN vs OUT)
- Classify and tag importent events (e.g., "HELEN OUT", "HELEN BACK")
- Provide a web interface for reviewing recorded events
- Create a visual log of pet activity over time
- Generate analytics about pet movement patterns

## Key Features
- **AI-Powered Detection**: Uses YOLOv8 object detection to identify and track pets
- **Direction Analysis**: Calculates and categorizes movement direction
- **Video Recording**: Automatically records and saves videos of detection events
- **Web Interface**: Intuitive UI for reviewing, tagging, and organizing events
- **Event Classification**: Automatic labeling of events (HELEN OUT, HELEN BACK, etc.)
- **Mobile Support**: Responsive design works on smartphones and tablets
- **Clock View**: Visual representation of pet activity patterns throughout the day
- **Multi-User System**: Supports multiple user accounts with authentication

## Technical Details
- **Hardware**: Raspberry Pi 5 with Hailo-8 or Hailo-8L AI accelerator
- **Camera Support**: Compatible with USB webcams and Raspberry Pi Camera Module
- **Backend**: Python Flask server with JWT authentication
- **Frontend**: HTML5/CSS3/JavaScript with responsive design
- **AI Framework**: Hailo AI framework with GStreamer pipeline
- **Storage**: Organized file-based storage of videos, images and metadata

## Installation
1. Ensure you have a Raspberry Pi 5 with Hailo AI accelerator installed
2. Clone the repository
3. Install dependencies: `pip install -r requirements.txt`
4. Configure `config.json` with your desired settings
5. Generate SSL certificates or use the provided self-signed ones
6. Run the application: `python helen_o_matic.py --hef-path models/helen-o-matic.v7.yolov8p.hef --labels-json models/helen-o-matic.v5-labels.json --input rpi`

## Usage
1. Access the web interface at `https://[RPI_IP_ADDRESS]:5000`
2. Log in with the default credentials (or create a new account)
3. Review detected events in the main interface
4. Use the classification buttons to tag events
5. View activity patterns in the clock view
6. Download or delete recordings as needed

## Configuration
The system can be configured through the `config.json` file:
- `CLASS_TO_TRACK`: Primary object class to track (default: "dog")
- `CLASS_MATCH_CONFIDENCE`: Detection confidence threshold (default: 0.4)
- `HELEN_THRESHOLD_PERCENT`: Threshold for Helen classification (default: 10)
- `DOG_MIN_SECONDS`: Minimum dog visibility time to save an event (default: 1)
- `VIDEO_MAX_SECONDS`: Maximum video recording length (default: 30)
- `DAYTIME_ONLY`: Whether to only monitor during daylight hours (default: false)

## License
This project is licensed under the MIT License
