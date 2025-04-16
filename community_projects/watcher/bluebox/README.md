# Bluebox

A smart surveillance system built on the Raspberry Pi platform with Hailo AI acceleration, designed to detect and track objects (particularly dogs) in your environment.

## Features

- Real-time object detection using Hailo AI acceleration
- Web-based interface for reviewing detection events
- Secure user authentication with admin and regular user roles
- Video and image capture of detection events
- Support for tagging and reviewing events
- Event filtering for dogs and other objects
- Temperature monitoring of the system
- Mobile-friendly responsive design

## Requirements

- Raspberry Pi (recommended: RPi 5)
- Hailo AI accelerator
- Camera module compatible with Raspberry Pi
- Python 3.7 or higher
- Internet connection for initial setup

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/hailo-rpi5-examples.git
   cd hailo-rpi5-examples
   ```

2. Set up the environment:
   ```bash
   source setup_env.sh
   ```

3. Install required Python packages:
   ```bash
   pip install -r requirements.txt
   ```

4. Create SSL certificates (optional but recommended):
   ```bash
   mkdir -p community_projects/watcher/bluebox/certificate
   cd community_projects/watcher/bluebox/certificate
   openssl req -x509 -newkey rsa:4096 -nodes -out bluebox.pem -keyout bluebox-privkey.pem -days 365
   ```

5. Configure the application by creating or editing the `config.json` file:
   ```json
   {
    "CLASS_TO_TRACK": "dog",
    "CLASS_DETECTED_COUNT": 4,
    "CLASS_GONE_SECONDS": 5,
    "CLASS_MATCH_CONFIDENCE": 0.8,
    "SAVE_DETECTION_IMAGES": true,
    "SAVE_DETECTION_VIDEO": true,
    "SHOW_DETECTION_BOXES": false,
    "FRAME_RATE": 30,
    "DAYTIME_ONLY": true,
    "USE_SSL": true
   }
   ```

## Usage

### Starting the Application

1. Run the start script:
   ```bash
   cd community_projects/watcher/bluebox
   bash start_bluebox.sh
   ```

2. Access the web interface at `https://your_raspberry_pi_ip:5003/`

3. Log in with the default credentials:
   - Username: `bower`
   - Password: `XXXXXX`
   
   (You should change this password immediately after first login)

### Web Interface

The web interface provides the following functionality:

- **Event Timeline**: View all detection events ordered by date and time
- **Event Details**: See detailed metadata for each detection event
- **Video Playback**: Watch recorded videos of detected events
- **Event Tagging**: Mark events as "Dog" or "Not Dog" for future reference
- **Star Important Events**: Tag important events with a star
- **Delete Events**: Remove unwanted detection events
- **Download Videos**: Save videos to your local device

### User Management

If you have admin privileges, you can:

1. Create new users by clicking the "Register" button on the login page
2. Set user permissions (admin or regular user)

Regular users can view events but cannot modify, tag, or delete them.

## System Architecture

Bluebox consists of several components:

- **Detection Engine**: Built on GStreamer with Hailo AI acceleration
- **Web Server**: Flask-based server providing the web UI and API
- **Event Storage**: File-based storage for videos, images, and metadata
- **User Authentication**: JWT-based authentication system

## Troubleshooting

- **Web Interface Not Loading**: Check if the web server is running with `ps aux | grep web_server.py`
- **No Events Being Detected**: Verify camera connection and check `~/bluebox.log` for errors
- **High CPU Temperature**: Ensure proper ventilation and consider adding a cooling solution
- **Authentication Issues**: Reset users by editing or removing `users.json`

## License

This project is licensed under the MIT License


