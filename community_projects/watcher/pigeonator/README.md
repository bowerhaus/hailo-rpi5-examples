# Pigeonator

## Overview

Pigeonator is an AI-powered pigeon deterrent system built on the Raspberry Pi 5 with Hailo AI accelerator. The system uses computer vision to detect pigeons and automatically trigger a deterrent mechanism using the LinkTap smart watering system.

## Features

- Real-time pigeon detection using a YOLO8 model and Hailo's AI acceleration
- Adjustable detection confidence thresholds
- Automatic deterrent triggering with configurable delay
- Water spray deterrent via LinkTap smart watering system
- Web interface for reviewing detection events
- Video recording and event logging
- Mobile-friendly responsive design

## Hardware Requirements

- Raspberry Pi 5
- Hailo AI Accelerator
- Camera module compatible with Raspberry Pi
- LinkTap smart watering system
- Internet connection for LinkTap API access

## Software Components

1. **Detection System**: Uses Hailo's AI acceleration to detect pigeons in camera feed
2. **Deterrent Manager**: Controls the LinkTap water sprinkler system
3. **Web Interface**: Allows reviewing and managing detection events
4. **Video Recording**: Captures video clips of pigeon events

## Configuration

Configuration is stored in `config.json` with the following parameters:

- `CLASS_TO_TRACK`: Object class to detect (default: "bird")
- `CLASS_DETECTED_COUNT`: Number of consecutive detections required (default: 4)
- `CLASS_GONE_SECONDS`: Time with no detection before ending tracking (default: 3)
- `CLASS_MATCH_CONFIDENCE`: Confidence threshold for detection (default: 0.4)
- `LINKTAP_USERNAME`: LinkTap account username
- `LINKTAP_APIKEY`: LinkTap API key
- `LINKTAP_GATEWAYID`: LinkTap gateway ID
- `LINKTAP_TAPLINKERID`: LinkTap device ID
- `WATERING_DURATION_SEC`: Duration to activate water (default: 3)
- `DETER_DELAY_SECONDS`: Delay before triggering deterrent (default: 8)
- `DETER_RATE_LIMIT_SECONDS`: Minimum time between deterrent activations (default: 60)
- `WATERING_ON`: Enable/disable water trigger (default: true)

## Usage

1. Configure the `config.json` file with your LinkTap credentials
2. Run the application:
   ```
   python pigeonator.py
   ```
3. Access the web interface at `http://[raspberry-pi-ip]:5001`

## Web Interface

The web interface allows you to:
- View detection events with timestamps
- Play video recordings
- Mark events as reviewed
- Tag events as confirmed pigeons or false positives
- Delete unwanted recordings
- Download video clips

## Project Structure

- `pigeonator.py`: Main application
- `linktap.py`: LinkTap API integration
- `deterrent_manager.py`: Manages the deterrent triggering
- `gstreamer_pigeonator_app.py`: GStreamer pipeline for video processing
- `web_server.py`: Web server for the user interface
- `static/`: Web interface files

## Example Configuration

```json
{
  "CLASS_TO_TRACK": "bird",
  "CLASS_DETECTED_COUNT": 4,
  "CLASS_GONE_SECONDS": 3,
  "CLASS_MATCH_CONFIDENCE": 0.4,
  "LINKTAP_USERNAME": "your_username",
  "LINKTAP_APIKEY": "your_api_key",
  "LINKTAP_GATEWAYID": "your_gateway_id",
  "LINKTAP_TAPLINKERID": "your_tapliker_id",
  "WATERING_DURATION_SEC": 3,
  "DETER_DELAY_SECONDS": 8,
  "DETER_RATE_LIMIT_SECONDS": 60,
  "WATERING_ON": true
}
```

## License
This project is licensed under the MIT License
