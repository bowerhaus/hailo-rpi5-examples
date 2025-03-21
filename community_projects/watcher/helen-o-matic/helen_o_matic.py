import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib
import gtts
from playsound import playsound
import datetime
import json
from logger_config import logger
from gstreamer_helenomatic_app import GStreamerHelenOMaticApp  # Updated import
from geometry import Point2D

import threading
from web_server import app as web_app
from time import sleep
from watcher_base import WatcherBase, watcher_base_callback

# Load configuration from config.json
with open('config.json', 'r') as config_file:
    config = json.load(config_file)
    logger.info(f"Loaded config: {config}")

HELEN_OUT_ALERT = "helenout.mp3"
HELEN_BACK_ALERT = "helenback.mp3"
HELLO = "hello.mp3"

# Inheritance from WatcherBase
class HelenOMatic(WatcherBase):
    def __init__(self, config):
        super().__init__(config)
        
        # Set logger to use the helen-o-matic logger
        self.logger = logger
        
        # Helen-specific configuration
        self.helen_dogs_threshold = config.get('HELEN_DOGS_THRESHOLD', 2)

    def create_speech_files(self):
        super().create_speech_files()

        tts = gtts.gTTS(f"Helen is going out")
        tts.save(HELEN_OUT_ALERT)
        tts = gtts.gTTS(f"Helen is back")
        tts.save(HELEN_BACK_ALERT)

    def create_metadata(self, root_filename, event_seconds):
        metadata = super().create_metadata(root_filename, event_seconds)

        avg_velocity_direction = int(self.avg_velocity.direction()) if self.avg_velocity else 0
        named_direction = self.get_named_direction(avg_velocity_direction)
        avg_detection_count = self.get_average_detection_instance_count()
        estimated_label = self.estimate_label(avg_velocity_direction, self.max_instances, avg_detection_count)

        if estimated_label == "HELEN_OUT":
            self.playsound_async(HELEN_OUT_ALERT)
        elif estimated_label == "HELEN_BACK":
            self.playsound_async(HELEN_BACK_ALERT)

        new_metadata = {
            "direction": avg_velocity_direction,
            "named_direction": named_direction,
            "label": estimated_label
        }
        metadata.update(new_metadata)
        return metadata
    
    def root_filename(self):
        avg_detection_count = self.get_average_detection_instance_count()
        avg_detection_count_rounded = round(avg_detection_count)
        avg_velocity_direction = int(self.avg_velocity.direction()) if self.avg_velocity else 0
        return f"{self.active_timestamp}_{self.class_to_track}_x{avg_detection_count_rounded}_{avg_velocity_direction}"

    def get_named_direction(self, direction):
        """
        Get the named direction from a given angle.
        Args:
            direction (int): The angle in degrees.
        Returns:
            str: The named direction.
        """
        if direction >= 25 and direction < 100:
            return "OUT"
        if direction >= 205 and direction < 280:
            return "BACK"
        return "OTHER"
    
    def estimate_label(self, direction, max_instances, avg_detection_count):
        """
        Estimate the label based on the given direction, max instances, and average detection count.
        Args:
            direction (int): The angle in degrees.
            max_instances (int): The maximum number of instances detected in a frame.
            avg_detection_count (float): The average number of instances detected in a frame.
        Returns:
            str: The estimated label.
        """
        number_of_dogs = round(avg_detection_count)
        if number_of_dogs >= self.helen_dogs_threshold:
            named_direction = self.get_named_direction(direction)
            if named_direction == "OUT":
                return "HELEN_OUT"
            if named_direction == "BACK":
                return "HELEN_BACK"
        return None


if __name__ == "__main__":
    # Create an instance of the user app callback class
    tts = gtts.gTTS(f"Hello Helen Oh Matic")
    tts.save(HELLO)
    user_data = HelenOMatic(config)
    user_data.playsound_async(HELLO)
    
    # Start the web server in a separate thread   
    web_server_thread = threading.Thread(
        target=web_app.run, 
        kwargs={
            'host': '0.0.0.0', 
            'port': 5000,
            'ssl_context': ('certificate/helen-o-matic.pem', 'certificate/helen-o-matic-privkey.pem')
        }
    )
    web_server_thread.daemon = True
    web_server_thread.start()
    
    sleep(1)  # Give web server time to initialize.
    
    # Create the helenomatic app instance and run it - updated class name
    app = GStreamerHelenOMaticApp(watcher_base_callback, user_data)
    user_data.app = app  # Store app reference in user_data
    app.run()