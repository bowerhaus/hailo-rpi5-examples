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
from gstreamer_bluebox_app import GStreamerBlueboxApp

import threading
from web_server import app as web_app
from time import sleep
from watcher_base import WatcherBase, watcher_base_callback
from geometry import Point2D
import cv2
import urllib.request
import urllib.parse

# Load configuration from config.json or from environment variable if specified
config_file = os.environ.get('WATCHER_CONFIG_FILE', 'config.json')
logger.info(f"Loading configuration from: {config_file}")
with open(config_file, 'r') as config_file:
    config = json.load(config_file)
    logger.info(f"Loaded config: {config}")

HELLO = "hello.mp3"

# Inheritance from WatcherBase
class BlueboxWatcher(WatcherBase):
    def __init__(self, config):
        super().__init__(config)
        
        # Set logger to use the bluebox logger
        self.logger = logger
        
        logger.info(f"Looking for {self.class_to_track.upper()}")
        
        # Initialize truck tracking parameters
        self.truck_class_to_track = 'truck'
        self.truck_min_area_percentage = config.get('TRUCK_MIN_AREA_PERCENTAGE', 15)  # % of the image
        self.truck_detection_counter = 0
        self.truck_previous_centroid = None
        self.truck_current_centroid = None
        self.truck_initial_centroid = None
        
        # Use only percentage-based threshold for movement detection
        self.truck_movement_threshold_percent = config.get('TRUCK_MOVEMENT_THRESHOLD_PERCENT', 20)  # % of truck width
        
        self.truck_detection_threshold = config.get('TRUCK_DETECTION_FRAMES', 3)
        self.truck_is_moving = False
        self.truck_alert_cooldown = 10 * self.frame_rate  # 10 seconds cooldown between alerts
        self.truck_alert_counter = 0
        self.truck_image_cooldown = 2 * self.frame_rate  # 2 seconds cooldown between images
        self.truck_image_counter = 0
        
        # Truck video recording parameters
        self.truck_video_writer = None
        self.truck_video_filename = None
        self.truck_video_recording = False
        self.truck_video_frame_count = 0
        self.truck_video_start_time = None
        self.truck_max_video_seconds = config.get('TRUCK_VIDEO_MAX_SECONDS', 10)  # Default 10 seconds
        self.truck_recording_timestamp = None
        self.truck_event_data = {}  # Store event data for metadata
        self.truck_video_frames_written = 0
        self.truck_video_truncated = False
        self.truck_video_completed = False
        
        # Pushsafer notification parameters
        self.pushsafer_enabled = config.get('PUSHSAFER_ENABLED', False)
        self.pushsafer_key = config.get('PUSHSAFER_PRIVATE_KEY', '')
        self.pushsafer_device = config.get('PUSHSAFER_DEVICE', '')
        self.pushsafer_cooldown_seconds = config.get('PUSHSAFER_COOLDOWN_SECONDS', 300)  # Default 5 minutes
        self.last_pushsafer_time = datetime.datetime.min

    def send_pushsafer_notification(self, title, message, icon="176", sound="61"):
        """Send notification using Pushsafer."""
        if not self.pushsafer_enabled or not self.pushsafer_key:
            return False
            
        # Check cooldown period
        now = datetime.datetime.now()
        if (now - self.last_pushsafer_time).total_seconds() < self.pushsafer_cooldown_seconds:
            logger.info(f"Pushsafer notification skipped due to cooldown period ({self.pushsafer_cooldown_seconds} seconds)")
            return False
            
        try:
            # Prepare post data
            post_data = {
                'k': self.pushsafer_key,
                't': title,
                'm': message,
                'i': icon,  # Icon (check Pushsafer docs)
                's': sound,  # Sound (check Pushsafer docs),
                'v': '3',  # Vibration
            }
            
            # Add device if specified
            if self.pushsafer_device:
                post_data['d'] = self.pushsafer_device
            
            # Encode data
            post_data = urllib.parse.urlencode(post_data).encode('utf-8')
            
            # Send request to Pushsafer API
            request = urllib.request.Request('https://www.pushsafer.com/api', data=post_data)
            response = urllib.request.urlopen(request)
            
            # Read and parse response
            response_data = response.read().decode('utf-8')
            response_json = json.loads(response_data)
            
            # Check if notification was sent successfully
            if response_json.get('status') == 1:
                self.last_pushsafer_time = now
                logger.info(f"Pushsafer notification sent successfully: {response_json}")
                return True
            else:
                logger.error(f"Pushsafer notification failed: {response_json}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to send Pushsafer notification: {str(e)}")
            return False

    def create_truck_metadata(self, filename, **kwargs):
        """Create metadata JSON file for truck detection events."""
        # Extract timestamp from filename
        filename_base = os.path.basename(filename)
        timestamp = filename_base.split('_moving_truck')[0]
        
        # Create base metadata dictionary
        metadata = {
            "filename": filename_base,
            "hef_model": self.hef_model,
            "class": self.truck_class_to_track,
            "timestamp": timestamp,
            "reviewed": False
        }
        
        # Add any other fields from kwargs
        metadata.update(kwargs)
        
        # Create metadata filename from image/video filename
        metadata_filename = os.path.splitext(filename)[0] + '.json'
        
        # Save metadata as JSON file
        with open(metadata_filename, 'w') as metadata_file:
            json.dump(metadata, metadata_file)
        self.logger.info(f"Truck metadata saved: {metadata_filename}")
        
        return metadata

    def start_truck_video_recording(self, timestamp):
        """Start recording video of a moving truck."""
        if self.truck_video_recording:
            return  # Already recording
            
        # Ensure output directory exists
        date_subdir = datetime.datetime.now().strftime("%Y%m%d")
        output_dir = f"{self.output_directory}/{date_subdir}"
        os.makedirs(output_dir, exist_ok=True)
        
        # Set the video filename with the given timestamp
        self.truck_video_filename = f"{output_dir}/{timestamp}_moving_truck.m4v"
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        self.truck_video_writer = cv2.VideoWriter(
            self.truck_video_filename, 
            fourcc, 
            self.frame_rate, 
            (self.width, self.height)
        )
        self.truck_video_recording = True
        self.truck_video_frame_count = 0
        self.truck_video_frames_written = 0
        self.truck_video_start_time = datetime.datetime.now()
        self.truck_recording_timestamp = timestamp
        self.truck_video_truncated = False
        self.truck_video_completed = False
        
        self.logger.info(f"Started recording truck video: {self.truck_video_filename}")
        
    def write_truck_video_frame(self, frame):
        """Write a frame to the truck video."""
        if self.truck_video_writer is not None and frame is not None:
            # Check if we've reached max duration
            if self.truck_video_start_time is not None:
                elapsed = (datetime.datetime.now() - self.truck_video_start_time).total_seconds()
                if elapsed >= self.truck_max_video_seconds:
                    if not self.truck_video_truncated:
                        self.logger.info(f"Truck video truncated after {self.truck_max_video_seconds} seconds.")
                        self.truck_video_truncated = True
                    
                    if not self.truck_video_completed:
                        self.truck_video_completed = True
                        # Schedule video completion after a short delay
                        threading.Timer(0.1, self.stop_truck_video_recording).start()
                    return False  # Don't write more frames if we've exceeded the max duration
            
            # Write the frame
            self.truck_video_writer.write(frame)
            self.truck_video_frame_count += 1
            self.truck_video_frames_written += 1
            return True
        return False
            
    def stop_truck_video_recording(self):
        """Stop recording truck video and convert to H264."""
        if not self.truck_video_recording or self.truck_video_writer is None:
            return
            
        # Release the video writer
        self.truck_video_writer.release()
        self.truck_video_writer = None
        self.truck_video_recording = False
        
        final_video_path = self.truck_video_filename
        self.logger.info(f"Finished recording truck video after {self.truck_video_frames_written} frames")
        
        # Calculate actual video duration
        if self.truck_video_start_time is not None:
            actual_duration = min(
                (datetime.datetime.now() - self.truck_video_start_time).total_seconds(),
                self.truck_max_video_seconds
            )
        else:
            actual_duration = 0
        
        # Convert video to H264 in background thread
        threading.Thread(
            target=self.convert_video_to_h264,
            args=(final_video_path,),
            daemon=True
        ).start()
        
        # Update metadata with video details
        if self.truck_recording_timestamp:
            # Add video information to the event data
            self.truck_event_data.update({
                "video_filename": os.path.basename(final_video_path).replace(".m4v", ".mp4"),
                "video_frame_count": self.truck_video_frames_written,
                "video_duration": round(actual_duration, 2),
                "video_truncated": self.truck_video_truncated
            })
            
            # Create metadata with all event data
            self.create_truck_metadata(
                final_video_path,
                **self.truck_event_data
            )
        
        # Reset recording state
        self.truck_recording_timestamp = None
        self.truck_video_completed = False
        
    def monitor_secondary_tracking(self, detections):
        """Look for secondary tracked objects - specifically large trucks."""
        # First, handle video recording if already in progress
        if self.truck_video_recording and self.current_frame is not None:
            # Create a copy of the current frame
            frame_to_save = self.current_frame.copy()
            
            # Draw boxes on any truck detections if enabled
            if self.show_detection_boxes:
                truck_detections = [
                    detection for detection in detections 
                    if detection.get_label() == self.truck_class_to_track
                    and detection.get_confidence() > self.class_match_confidence
                ]
                
                for detection in truck_detections:
                    bbox = detection.get_bbox()
                    cv2.rectangle(
                        frame_to_save,
                        (int(bbox.xmin() * self.width), int(bbox.ymin() * self.height)),
                        (int(bbox.xmax() * self.width), int(bbox.ymax() * self.height)),
                        (0, 0, 255),  # Red color in BGR
                        2  # Thicker line for the truck
                    )
            
            # Write the frame to the video even if there are no truck detections
            self.write_truck_video_frame(frame_to_save)
            
        # Now check for truck detections to start tracking/recording
        truck_detections = [
            detection for detection in detections 
            if detection.get_label() == self.truck_class_to_track
            and detection.get_confidence() > self.class_match_confidence
        ]
        
        if not truck_detections:
            # Reset detection counter if no trucks found
            self.truck_detection_counter = 0
            self.truck_previous_centroid = self.truck_current_centroid
            self.truck_current_centroid = None
            self.truck_is_moving = False
            self.truck_initial_centroid = None  # Reset initial centroid when no trucks are detected
            return
        
        # Find the largest truck detection
        largest_truck = None
        largest_area_percentage = 0
        
        for detection in truck_detections:
            bbox = detection.get_bbox()
            # Calculate area as a percentage of the image
            area_percentage = (bbox.xmax() - bbox.xmin()) * (bbox.ymax() - bbox.ymin()) * 100
            
            if area_percentage > largest_area_percentage:
                largest_area_percentage = area_percentage
                largest_truck = detection
        
        # If we have a large enough truck
        if largest_truck and largest_area_percentage >= self.truck_min_area_percentage:
            self.truck_detection_counter += 1
            
            # Calculate truck centroid and dimensions
            bbox = largest_truck.get_bbox()
            centroid_x = (bbox.xmin() + bbox.xmax()) / 2
            centroid_y = (bbox.ymin() + bbox.ymax()) / 2
            self.truck_current_centroid = Point2D(centroid_x, centroid_y)
            
            # Calculate truck width (normalized coordinates)
            truck_width = bbox.xmax() - bbox.xmin()
            
            # Save initial centroid if this is the first detection
            if self.truck_initial_centroid is None:
                self.truck_initial_centroid = self.truck_current_centroid
                self.logger.debug(f"Initial truck centroid set to {self.truck_initial_centroid}")
            
            # Check for movement from initial position if we have an initial position
            if self.truck_initial_centroid and self.truck_detection_counter >= self.truck_detection_threshold:
                # Calculate movement from initial position instead of previous frame
                movement = self.truck_current_centroid.subtract(self.truck_initial_centroid)
                
                # Use only horizontal movement (x-axis)
                movement_magnitude = abs(movement.x)
                
                # Calculate the movement threshold based on truck width
                dynamic_threshold = truck_width * (self.truck_movement_threshold_percent / 100.0)
                    
                # If movement exceeds threshold, consider truck as moving
                if movement_magnitude > dynamic_threshold:
                    self.truck_is_moving = True
                    
                    # Only alert if cooldown has elapsed
                    if self.truck_alert_counter == 0:
                        confidence = largest_truck.get_confidence()
                        
                        # Calculate movement as percentage of truck width for logging
                        movement_percent = (movement_magnitude / truck_width * 100) if truck_width > 0 else 0
                        
                        self.logger.warning(
                            f"ALERT: Large moving TRUCK detected! "
                            f"Area: {largest_area_percentage:.1f}%, "
                            f"Horizontal Movement: {movement_magnitude:.4f} ({movement_percent:.1f}% of truck width), "
                            f"Confidence: {confidence:.2f}"
                        )
                        self.truck_alert_counter = self.truck_alert_cooldown
                        
                        # Create timestamp for both image and video filenames
                        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
                        
                        # Format timestamp for display in notifications
                        readable_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        
                        # Send Pushsafer notification
                        if self.pushsafer_enabled:
                            push_title = "Truck Movement Detected"
                            push_message = (
                                f"Large moving truck detected at {readable_time}.\n"
                                f"Area: {largest_area_percentage:.1f}%, Movement: {movement_percent:.1f}% of truck width"
                            )
                            threading.Thread(
                                target=self.send_pushsafer_notification,
                                args=(push_title, push_message),
                                daemon=True
                            ).start()
                        
                        # Store all event data that will be needed for metadata
                        self.truck_event_data = {
                            "confidence": round(confidence, 2),
                            "area_percentage": round(largest_area_percentage, 1),
                            "movement_magnitude": round(movement_magnitude, 4),
                            "movement_percent": round(movement_percent, 1),
                            "truck_width": round(truck_width, 4),
                            "detection_time": datetime.datetime.now().isoformat(),
                            "pushsafer_sent": self.pushsafer_enabled
                        }
                        
                        # Start video recording if not already recording
                        if not self.truck_video_recording:
                            self.start_truck_video_recording(timestamp)
                        
                        # Save image if current frame is available and image cooldown has elapsed
                        if self.current_frame is not None and self.truck_image_counter == 0:
                            # Create a copy of the current frame for drawing
                            frame_to_save = self.current_frame.copy()
                            
                            # Draw boxes if enabled
                            if self.show_detection_boxes:
                                # Draw box around the truck
                                bbox = largest_truck.get_bbox()
                                cv2.rectangle(
                                    frame_to_save,
                                    (int(bbox.xmin() * self.width), int(bbox.ymin() * self.height)),
                                    (int(bbox.xmax() * self.width), int(bbox.ymax() * self.height)),
                                    (0, 0, 255),  # Red color in BGR
                                    2  # Thicker line for the truck
                                )
                            
                            # Ensure output directory exists
                            date_subdir = datetime.datetime.now().strftime("%Y%m%d")
                            output_dir = f"{self.output_directory}/{date_subdir}"
                            os.makedirs(output_dir, exist_ok=True)
                            
                            # Create image filename
                            truck_image_filename = f"{output_dir}/{timestamp}_moving_truck.jpg"
                            
                            # Save the image
                            cv2.imwrite(truck_image_filename, frame_to_save)
                            self.logger.info(f"Moving truck image saved as {truck_image_filename}")
                            
                            # Add image filename to event data
                            self.truck_event_data["image_filename"] = os.path.basename(truck_image_filename)
                            
                            # Set image cooldown counter
                            self.truck_image_counter = self.truck_image_cooldown
            
            # Update previous centroid
            self.truck_previous_centroid = self.truck_current_centroid
        else:
            # Reset detection counter if truck is too small
            self.truck_detection_counter = 0
            self.truck_is_moving = False
            self.truck_initial_centroid = None  # Reset initial centroid if truck is too small
        
        # Decrement counters if active
        if self.truck_alert_counter > 0:
            self.truck_alert_counter -= 1
        if self.truck_image_counter > 0:
            self.truck_image_counter -= 1

    def on_eos(self):
        """Handle end of stream."""
        # Stop truck video recording if active when stream ends
        if self.truck_video_recording:
            self.stop_truck_video_recording()
        
        # Call parent's on_eos method
        super().on_eos()

if __name__ == "__main__":
    # Create an instance of the user app callback class
    tts = gtts.gTTS(f"Hello Bluebox")
    tts.save(HELLO) 
    user_data = BlueboxWatcher(config)
    user_data.playsound_async(HELLO)
    
    # Start web server first.
    web_server_kwargs = {'host': '0.0.0.0', 'port': 5004}
    
    # Check if SSL should be used
    if config.get('USE_SSL', False):
        web_server_kwargs['ssl_context'] = ('certificate/bluebox.pem', 'certificate/bluebox-privkey.pem')
        logger.info("Starting web server with SSL enabled")
    else:
        logger.info("Starting web server without SSL")
    
    web_server_thread = threading.Thread(target=web_app.run, kwargs=web_server_kwargs)
    web_server_thread.daemon = True
    web_server_thread.start()
    
    sleep(1)  # Give web server time to initialize.
    
    # Create the watcher app instance and run it
    app = GStreamerBlueboxApp(watcher_base_callback, user_data)
    user_data.app = app
    app.run()