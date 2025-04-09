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
import hailo

import threading
from web_server import app as web_app
from time import sleep
from watcher_base import WatcherBase, watcher_base_callback

# Load configuration from config.json or from environment variable if specified
config_file = os.environ.get('WATCHER_CONFIG_FILE', 'config.json')
logger.info(f"Loading configuration from: {config_file}")
with open(config_file, 'r') as config_file:
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
        
        # Counters for additional classes
        self.helen_out_count = 0
        self.helen_back_count = 0
        self.person_count = 0
        self.dog_count = 0  # Add counter for dog class
        self.total_active_frames = 0

    def create_speech_files(self):
        super().create_speech_files()

        tts = gtts.gTTS(f"Helen is going out")
        tts.save(HELEN_OUT_ALERT)
        tts = gtts.gTTS(f"Helen is back")
        tts.save(HELEN_BACK_ALERT)

    def active_tracking(self, class_detections):
        """Override active_tracking to count additional classes"""
        # Call the parent method first
        super().active_tracking(class_detections)
        
        # Increment total frames counter
        self.total_active_frames += 1
        
        # Using all_detections from base class (which is populated in the callback)
        if hasattr(self, 'all_detections') and self.all_detections:
            # Create a set to track which classes we've already counted in this frame
            counted_classes = set()
            
            for detection in self.all_detections:
                label = detection.get_label()
                confidence = detection.get_confidence()
                
                # Only count each class once per frame using the set
                if confidence > self.class_match_confidence and label not in counted_classes:
                    if label == "helen_out":
                        self.helen_out_count += 1
                        counted_classes.add(label)
                    elif label == "helen_back":
                        self.helen_back_count += 1
                        counted_classes.add(label)
                    elif label == "person":
                        self.person_count += 1
                        counted_classes.add(label)
                    elif label == "dog":
                        self.dog_count += 1
                        counted_classes.add(label)

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

        # Calculate percentages for additional classes
        total_frames = max(self.total_active_frames, 1)  # Avoid division by zero
        helen_out_percent = round((self.helen_out_count / total_frames) * 100, 1)
        helen_back_percent = round((self.helen_back_count / total_frames) * 100, 1)
        person_percent = round((self.person_count / total_frames) * 100, 1)
        dog_percent = round((self.dog_count / total_frames) * 100, 1)  # Calculate dog percentage

        # Calculate visible dog seconds
        dog_seconds = 0
        if self.tracking_start_time:
            total_event_seconds = (datetime.datetime.now() - self.tracking_start_time).total_seconds()
            dog_seconds = (total_event_seconds - self.class_gone_seconds) * (dog_percent / 100.0)
            dog_seconds = round(max(0, dog_seconds), 1)  # Ensure non-negative and round to 1 decimal

        new_metadata = {
            "direction": avg_velocity_direction,
            "named_direction": named_direction,
            "label": estimated_label,
            "helen_out_percent": helen_out_percent,
            "helen_back_percent": helen_back_percent,
            "person_percent": person_percent,
            "dog_percent": dog_percent,  # Add dog percentage to metadata
            "dog_seconds": dog_seconds    # Add visible dog seconds to metadata
        }
        metadata.update(new_metadata)
        return metadata
    
    def stop_active_tracking(self, abort=False):
        """Override to add reporting for additional classes"""
        # Calculate percentages before calling super's stop_active_tracking
        total_frames = max(self.total_active_frames, 1)  # Avoid division by zero
        helen_out_percent = round((self.helen_out_count / total_frames) * 100, 1)
        helen_back_percent = round((self.helen_back_count / total_frames) * 100, 1) if hasattr(self, 'helen_back_percent') else 0
        person_percent = round((self.person_count / total_frames) * 100, 1)
        dog_percent = round((self.dog_count / total_frames) * 100, 1)  # Calculate dog percentage
        
        # Log the percentages
        logger.info(f"{self.class_to_track.upper()} GONE with additional class percentages: Helen Out: {helen_out_percent}%, Helen Back: {helen_back_percent}%, Person: {person_percent}%, Dog: {dog_percent}%")
        
        # Calculate actual visible dog time
        if self.tracking_start_time:
            event_seconds = (datetime.datetime.now() - self.tracking_start_time).total_seconds()
            
            # Updated formula: (event_seconds - CLASS_GONE_SECONDS) * dog_percent / 100
            # This accounts for the fact that we wait CLASS_GONE_SECONDS before declaring the dog is gone
            visible_dog_seconds = (event_seconds - self.class_gone_seconds) * (dog_percent / 100.0)
            
            # Get minimum required dog seconds from config (default 1 second)
            dog_min_seconds = self.config.get('DOG_MIN_SECONDS', 1)
            
            # Log the calculated values
            logger.info(f"Total event: {event_seconds:.1f}s, Dog visible: {visible_dog_seconds:.1f}s, Minimum required: {dog_min_seconds}s")
            
            # If visible dog time is less than minimum, abort
            if visible_dog_seconds < dog_min_seconds:
                logger.info(f"Dog visibility time {visible_dog_seconds:.1f}s below threshold {dog_min_seconds}s - aborting event")
                abort = True
        
        # Call the parent class method with the abort parameter
        super().stop_active_tracking(abort)
        
        # Reset our counters after parent has finished
        self.helen_out_count = 0
        self.helen_back_count = 0
        self.person_count = 0
        self.dog_count = 0  # Reset dog counter
        self.total_active_frames = 0
    
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
        Estimate the label based on the given direction and class percentages.
        Args:
            direction (int): The angle in degrees.
            max_instances (int): The maximum number of instances detected in a frame.
            avg_detection_count (float): The average number of instances detected in a frame.
        Returns:
            str: The estimated label.
        """
        # Get the named direction
        named_direction = self.get_named_direction(direction)
        
        # Calculate percentages for each class
        total_frames = max(self.total_active_frames, 1)  # Avoid division by zero
        helen_out_percent = (self.helen_out_count / total_frames) * 100
        helen_back_percent = (self.helen_back_count / total_frames) * 100
        person_percent = (self.person_count / total_frames) * 100
        
        # Simple ranking of percentages
        all_percentages = {
            "helen_out": helen_out_percent,
            "helen_back": helen_back_percent,
            "person": person_percent
        }
        
        # Get threshold from config
        threshold = config.get('HELEN_THRESHOLD_PERCENT', 10)
        
        # If the direction is BACK and helen_back has the highest percentage
        if named_direction == "BACK" and helen_back_percent > threshold:
            return "HELEN_BACK"
        
        # If the direction is OUT and helen_out has the highest percentage
        if named_direction == "OUT" and helen_out_percent > threshold:
            return "HELEN_OUT"
            
        return None


if __name__ == "__main__":
    # Create an instance of the user app callback class
    tts = gtts.gTTS(f"Hello Helen Oh Matic")
    tts.save(HELLO)
    user_data = HelenOMatic(config)
    user_data.playsound_async(HELLO)
    
    # Start the web server in a separate thread
    web_server_kwargs = {'host': '0.0.0.0', 'port': 5000}
    
    # Check if SSL should be used
    if config.get('USE_SSL', True):
        web_server_kwargs['ssl_context'] = ('certificate/helen-o-matic.pem', 'certificate/helen-o-matic-privkey.pem')
        logger.info("Starting web server with SSL enabled")
    else:
        logger.info("Starting web server without SSL")
    
    web_server_thread = threading.Thread(
        target=web_app.run, 
        kwargs=web_server_kwargs
    )
    web_server_thread.daemon = True
    web_server_thread.start()
    
    sleep(1)  # Give web server time to initialize.
    
    # Create the helenomatic app instance and run it - updated class name
    app = GStreamerHelenOMaticApp(watcher_base_callback, user_data)
    user_data.app = app  # Store app reference in user_data
    app.run()