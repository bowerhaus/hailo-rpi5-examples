import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib
import os
import numpy as np
import cv2
import hailo
import subprocess  # Add this import
from hailo_apps_infra.hailo_rpi_common import (
    get_caps_from_pad,
    get_numpy_from_buffer,
    app_callback_class,
)
from hailo_apps_infra.detection_pipeline import GStreamerDetectionApp

import gtts
from playsound import playsound
import datetime
import math
import json
from logger_config import logger
from gstreamer_peetronic_app import GStreamerPeetronicApp

import threading
from web_server import app as web_app
from time import sleep

# Load configuration from config.json
with open('config.json', 'r') as config_file:
    config = json.load(config_file)
    logger.info(f"Loaded config: {config}")

# Load CLASS_* options from config
CLASS_DETECTED_COUNT = config.get('CLASS_DETECTED_COUNT', 4)
CLASS_GONE_SECONDS = config.get('CLASS_GONE_SECONDS', 3)
CLASS_MATCH_CONFIDENCE = config.get('CLASS_MATCH_CONFIDENCE', 0.4)
CLASS_TO_TRACK = config.get('CLASS_TO_TRACK', 'dog')
SAVE_DETECTION_IMAGES = config.get('SAVE_DETECTION_IMAGES', True)
SHOW_DETECTION_BOXES = config.get('SHOW_DETECTION_BOXES', True)
SAVE_DETECTION_VIDEO = config.get('SAVE_DETECTION_VIDEO', True)
FRAME_RATE = config.get('FRAME_RATE', 30)
OUTPUT_DIRECTORY = config.get('OUTPUT_DIRECTORY', 'output')

CLASS_ALERT = "classalert.mp3"
HELLO = "hello.mp3"

class Point2D:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __repr__(self):
        return f"Point2D({self.x}, {self.y})"

    def round(self, n=2):
        return Point2D(round(self.x, n), round(self.y, n))

    def subtract(self, p):
        return Point2D(self.x - p.x, self.y - p.y)

    def magnitude(self):
        return (self.x**2 + self.y**2)**0.5

    def direction(self):
        angle = math.degrees(math.atan2(self.y, self.x))
        return angle if angle >= 0 else angle + 360

# Inheritance from the app_callback_class
class user_app_callback_class(app_callback_class):
    def __init__(self):
        super().__init__()
        
        # Initialize state variables for debouncing
        self.detection_counter = 0  # Count consecutive frames with detections
        self.no_detection_counter = 0  # Count consecutive frames without detections
        self.max_instances = 0  # Maximum number of instances detected in a frame
        
        # State tracking, is the debounced object active or not?
        self.is_active_tracking = False

        # Variables for computing average detection instance count
        self.total_detection_instances = 0
        self.active_detection_count = 0
        self.detection_counts = []
        self.max_mean_detection_count = 0

        # Variables for computing moving average of velocity
        self.avg_velocity = Point2D(0.0, 0.0)

        # Setup speech files
        # make request to google to get synthesis
       
        tts = gtts.gTTS(f"Its a {CLASS_TO_TRACK.upper()}")
        tts.save(CLASS_ALERT)

        logger.info(f"Looking for {CLASS_TO_TRACK.upper()}")

        # Initialize video writer
        self.video_writer = None
        self.video_filename = None

        self.format = None
        self.width = None
        self.height = None

    def on_eos(self):
        if self.is_active_tracking:
            self.stop_active_tracking()

    def start_video_recording(self, width, height, video_filename, format, fps):
        self.video_filename = video_filename.replace('.mp4', '.m4v')  # Use .m4v extension initially
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')  # Ensure the codec is set for MP4 format
        self.video_writer = cv2.VideoWriter(self.video_filename, fourcc, fps, (width, height))

    def write_video_frame(self, frame):
        if self.video_writer is not None and self.current_frame is not None:
            self.video_writer.write(frame)

    def draw_detection_boxes(self, detections, width, height):
        if self.current_frame is not None and SHOW_DETECTION_BOXES:
            for detection in detections:
                bbox = detection.get_bbox()
                cv2.rectangle(self.current_frame, 
                              (int(bbox.xmin() * width), int(bbox.ymin() * height)), 
                              (int(bbox.xmax() * width), int(bbox.ymax() * height)), 
                              (0, 0, 255), 1)

    def stop_video_recording(self, final_filename):
        if self.video_writer is not None:
            self.video_writer.release()
            self.video_writer = None
            os.rename(self.video_filename, final_filename)
            logger.info(f"Video saved as {final_filename}")
     
    def get_average_detection_instance_count(self):
        if not self.detection_counts:
            return 0
        detection_counts_np = np.array(self.detection_counts)
        window_size = FRAME_RATE
        if len(detection_counts_np) >= window_size:
            moving_averages = np.convolve(detection_counts_np, np.ones(window_size)/window_size, mode='valid')
            return moving_averages.max()
        else:
            return np.mean(detection_counts_np)

    def start_active_tracking(self, class_detections):
        self.is_active_tracking = True
        self.max_instances = len(class_detections)
        
        self.save_frame = self.current_frame
        self.active_timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]

        # Draw detection boxes on the frame if SHOW_DETECTION_BOXES is True
        if self.current_frame is not None and SHOW_DETECTION_BOXES:
            self.draw_detection_boxes(class_detections, self.width, self.height)

        # Ensure output directory exists
        date_subdir = datetime.datetime.now().strftime("%Y%m%d")
        output_dir = f"{OUTPUT_DIRECTORY}/{date_subdir}"
        os.makedirs(output_dir, exist_ok=True)

        # Start recording video if SAVE_DETECTION_VIDEO and self.video_writer is None and frame is not None:
        if SAVE_DETECTION_VIDEO and self.video_writer is None and self.current_frame is not None:
            video_filename = f"{output_dir}/{self.active_timestamp}_{CLASS_TO_TRACK}.mp4"
            self.start_video_recording(self.width, self.height, video_filename, self.format, FRAME_RATE)

        phrase = f"{CLASS_TO_TRACK.upper()} DETECTED"
        logger.info(f"{phrase} at: {datetime.datetime.now()}")
        playsound(CLASS_ALERT, 0)

    def active_tracking(self, class_detections):
        # Update total detection instances and active detection count for later averaging
        detection_instance_count = len(class_detections)
        if detection_instance_count > 0:
            # Draw detection boxes on the frame if SHOW_DETECTION_BOXES is True
            if SHOW_DETECTION_BOXES:
                self.draw_detection_boxes(class_detections, self.width, self.height)
            self.total_detection_instances += detection_instance_count
            self.active_detection_count += 1
            self.detection_counts.append(detection_instance_count)
            if detection_instance_count > self.max_instances:
                self.max_instances = detection_instance_count
                self.save_frame = self.current_frame

        # If a frame is available, write the frame to the video
        if self.current_frame is not None:
            self.write_video_frame(self.current_frame)

    def convert_video_to_h264(self, video_path):
        """Convert video to H264 format using ffmpeg"""
        try:
            temp_path = video_path + ".temp.mp4"
            final_path = video_path.replace('.m4v', '.mp4')  # Final path with .mp4 extension
            
            subprocess.run([
                'ffmpeg',
                '-y',  # Overwrite output file if it exists
                '-i', video_path,  # Input is .m4v
                '-codec:v', 'libx264',  # Use H264 codec
                '-preset', 'fast',  # Use fast preset for speed
                '-movflags', 'faststart',  # Optimize for web playback
                temp_path
            ], check=True, capture_output=True)
            
            # Replace original .m4v file with converted .mp4 file
            os.replace(temp_path, final_path)
            # Remove the original .m4v file
            os.remove(video_path)
            logger.info(f"Successfully converted {video_path} to H264 and saved as {final_path}")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to convert video {video_path} to H264: {e}")
            # Clean up temp file if it exists
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def stop_active_tracking(self):
        self.is_active_tracking = False

        avg_detection_count = self.get_average_detection_instance_count()
        avg_detection_count_rounded = round(avg_detection_count)

        logger.info(f"{CLASS_TO_TRACK.upper()} GONE time: {datetime.datetime.now()}, avg count: {avg_detection_count:.2f}, max count: {self.max_instances}")

        # Create root filename
        root_filename = f"{self.active_timestamp}_{CLASS_TO_TRACK}_x{avg_detection_count_rounded}"

        # Ensure output directories exist
        date_subdir = datetime.datetime.now().strftime("%Y%m%d")
        output_dir = f"{OUTPUT_DIRECTORY}/{date_subdir}"
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
        if self.save_frame is not None and SAVE_DETECTION_IMAGES:
            self.image_filename = f"{output_dir}/{root_filename}.jpg"
            cv2.imwrite(self.image_filename, self.save_frame)
            logger.info(f"Image saved as {self.image_filename}")

        # Create metadata dictionary
        metadata = {
            "filename": root_filename,
            "class": CLASS_TO_TRACK,
            "timestamp": self.active_timestamp,
            "max_instances": self.max_instances,
            "average_instances": avg_detection_count,
            "reviewed": False  # Add reviewed field, initially false
        }

        # Save metadata as JSON file
        metadata_filename = f"{output_dir}/{root_filename}.json"
        with open(metadata_filename, 'w') as metadata_file:
            json.dump(metadata, metadata_file)
        logger.info(f"Metadata saved: {metadata}")

        self.max_instances = 0
        self.avg_velocity = Point2D(0.0, 0.0)
        self.detection_counts.clear()
        self.max_mean_detection_count = 0
  
def app_callback(pad, info, user_data):
    """
    Callback function for processing video frames and detecting objects.
    Args:
        pad (Gst.Pad): The pad from which the buffer is received.
        info (Gst.PadProbeInfo): The probe info containing the buffer.
        user_data (UserData): Custom user data object for tracking state and configurations.
    Returns:
        Gst.PadProbeReturn: Indicates the result of the pad probe.
    The function performs the following tasks:
    - Retrieves the GstBuffer from the probe info.
    - Increments the frame count using user_data.
    - Extracts video frame information if user_data.use_frame is True.
    - Retrieves detections from the buffer and filters them based on class and confidence.
    - Counts the number of filtered detections.
    - Implements debouncing logic to determine if an object is detected or not.
    - Activates or deactivates detection state based on consecutive frames with or without detections.
    - Logs detection events and saves frame images when an object is detected.
    """
    # Get the GstBuffer from the probe info
    buffer = info.get_buffer()
    # Check if the buffer is valid
    if buffer is None:
        return Gst.PadProbeReturn.OK
    
    # Using the user_data to count the number of frames
    user_data.increment()
    
    # Get the caps from the pad
    user_data.format, user_data.width, user_data.height = get_caps_from_pad(pad)
    
    # If the user_data.use_frame is set to True, we can get the video frame from the buffer
    if user_data.use_frame and user_data.format is not None and user_data.width is not None and user_data.height is not None:
        user_data.current_frame = get_numpy_from_buffer(buffer, user_data.format, user_data.width, user_data.height)
        user_data.current_frame = cv2.cvtColor(user_data.current_frame, cv2.COLOR_RGB2BGR)

    # Use this to create a new user frame window
    # user_data.set_frame(user_data.current_frame)
    
    # Get the detections from the buffer
    roi = hailo.get_roi_from_buffer(buffer)
    detections = roi.get_objects_typed(hailo.HAILO_DETECTION)

    # Filter detections that match CLASS_TO_TRACK and have confidence greater than CLASS_MATCH_CONFIDENCE
    class_detections = [
        detection for detection in detections if (detection.get_label() == CLASS_TO_TRACK) and detection.get_confidence() > CLASS_MATCH_CONFIDENCE
    ]

    # Count the number of detections that match CLASS_TO_TRACK and have confidence greater than CLASS_MATCH_CONFIDENCE
    detection_instance_count = len(class_detections)
    object_detected = False
    if detection_instance_count > 0:
        object_detected = True
        user_data.detection_frame = user_data.current_frame

    # Debouncing logic to start/stop active tracking
    if object_detected:
        user_data.detection_counter += 1
        user_data.no_detection_counter = 0
        
        # Only activate after CLASS_DETECTED_COUNT consecutive frames with detections
        if user_data.detection_counter >= CLASS_DETECTED_COUNT and not user_data.is_active_tracking:
            user_data.start_active_tracking(class_detections)
    else:
        user_data.no_detection_counter += 1
        user_data.detection_counter = 0
        
        # Only deactivate after CLASS_GONE_SECONDS without detections
        if user_data.no_detection_counter >= (CLASS_GONE_SECONDS * FRAME_RATE) and user_data.is_active_tracking:
            user_data.stop_active_tracking()

    # Active tracking
    if user_data.is_active_tracking:
        user_data.active_tracking(class_detections)

    return Gst.PadProbeReturn.OK

if __name__ == "__main__":
    # Create an instance of the user app callback class
    tts = gtts.gTTS(f"Hello Peetronic")
    tts.save(HELLO) 
    playsound(HELLO, 0)
    
    # Start web server first.
    web_server_thread = threading.Thread(target=web_app.run, kwargs={'host': '0.0.0.0', 'port': 5000})
    web_server_thread.daemon = True
    web_server_thread.start()
    
    sleep(1)  # Give web server time to initialize.
    
    # Create the watcher app instance and run it. Active time checking now occurs inside run().
    user_data = user_app_callback_class()
    user_data.daytime_only = config.get("DAYTIME_ONLY", False)
    app = GStreamerPeetronicApp(app_callback, user_data)
    app.run()