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
from gstreamer_watcher_app import GStreamerWatcherApp
from geometry import Point2D

import threading
from web_server import app as web_app
from time import sleep
from watcher_base import WatcherBase, watcher_base_callback

# Load configuration from config.json
with open('config.json', 'r') as config_file:
    config = json.load(config_file)
    logger.info(f"Loaded config: {config}")

DOG_ALERT = "dogalert.mp3"
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
        
        # Setup speech files
        tts = gtts.gTTS(f"Its a {self.class_to_track.upper()}")
        tts.save(DOG_ALERT)
        tts = gtts.gTTS(f"Helen is going out")
        tts.save(HELEN_OUT_ALERT)
        tts = gtts.gTTS(f"Helen is back")
        tts.save(HELEN_BACK_ALERT)

        logger.info(f"Looking for {self.class_to_track.upper()}")

    def start_active_tracking(self, class_detections):
        """Override to add helen-specific behavior"""
        super().start_active_tracking(class_detections)
        # Play alert sound
        playsound(DOG_ALERT, 0)

    def stop_active_tracking(self):
        """Override to add helen-specific behavior with direction detection"""
        self.is_active_tracking = False
        self.end_centroid = self.object_centroid

        avg_detection_count = self.get_average_detection_instance_count()
        avg_detection_count_rounded = round(avg_detection_count)
        
        # Calculate direction
        avg_velocity_direction = int(self.avg_velocity.direction()) if self.avg_velocity else 0
        named_direction = self.get_named_direction(avg_velocity_direction)
        estimated_label = self.estimate_label(avg_velocity_direction, self.max_instances, avg_detection_count)

        logger.info(f"{self.class_to_track.upper()} GONE at: {self.end_centroid} time: {datetime.datetime.now()}, avg count: {avg_detection_count:.2f}, max count: {self.max_instances}, direction: {avg_velocity_direction}, named direction: {named_direction}, label: {estimated_label}")

        # Create root filename with direction info
        root_filename = f"{self.active_timestamp}_{self.class_to_track}_x{avg_detection_count_rounded}_{avg_velocity_direction}"

        # Ensure output directories exist
        date_subdir = datetime.datetime.now().strftime("%Y%m%d")
        output_dir = f"{self.output_directory}/{date_subdir}"
        os.makedirs(output_dir, exist_ok=True)

        # Stop any video recording and rename the file to include the average count
        final_video_filename = f"{output_dir}/{root_filename}.m4v"  # Use .m4v extension
        self.stop_video_recording(final_video_filename)

        # Convert video to H264 in background thread - will rename to .mp4
        threading.Thread(
            target=self.convert_video_to_h264,
            args=(final_video_filename,),
            daemon=True
        ).start()

        # Save the frame with the most instances if SAVE_DETECTION_IMAGES is True
        if self.save_frame is not None and self.save_detection_images:
            self.image_filename = f"{output_dir}/{root_filename}.jpg"
            cv2.imwrite(self.image_filename, self.save_frame)
            logger.info(f"Image saved as {self.image_filename}")

        # Compute event duration in seconds
        try:
            event_start = datetime.datetime.strptime(self.active_timestamp + "000", "%Y%m%d_%H%M%S_%f")
        except Exception:
            event_start = datetime.datetime.now()
        event_seconds = (datetime.datetime.now() - event_start).total_seconds()

        # Create metadata dictionary with Helen-specific fields
        metadata = {
            "filename": root_filename,
            "class": self.class_to_track,
            "initial_confidence": round(self.initial_max_confidence, 2),
            "timestamp": self.active_timestamp,
            "max_instances": self.max_instances,
            "average_instances": avg_detection_count,
            "event_seconds": round(event_seconds, 1),
            "video_truncated": self.video_truncated,
            "direction": avg_velocity_direction,
            "named_direction": named_direction,
            "label": estimated_label,
            "reviewed": False
        }

        # Save metadata as JSON file
        metadata_filename = f"{output_dir}/{root_filename}.json"
        with open(metadata_filename, 'w') as metadata_file:
            json.dump(metadata, metadata_file)
        logger.info(f"Metadata saved: {metadata}")

        # Play the appropriate alert based on the estimated label
        if estimated_label == "HELEN_OUT":
            playsound(HELEN_OUT_ALERT, 0)
        elif estimated_label == "HELEN_BACK":
            playsound(HELEN_BACK_ALERT, 0)

        # Reset tracking state
        self.max_instances = 0
        self.save_frame = None
        self.object_centroid = None
        self.avg_velocity = Point2D(0.0, 0.0)
        self.previous_centroid = None
        self.detection_counts.clear()
        self.max_mean_detection_count = 0

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
    playsound(HELLO, 0)
    
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
    
    # Create the watcher app instance and run it
    user_data = HelenOMatic(config)
    app = GStreamerWatcherApp(watcher_base_callback, user_data)
    user_data.app = app  # Store app reference in user_data
    app.run()