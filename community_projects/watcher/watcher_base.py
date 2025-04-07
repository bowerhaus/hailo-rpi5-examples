import os
import sys
import json
import cv2
import numpy as np
import datetime
import subprocess
import threading
import hailo
from hailo_apps_infra.hailo_rpi_common import (
    get_caps_from_pad,
    get_numpy_from_buffer,
    app_callback_class,
)
from gi.repository import Gst
from geometry import Point2D
from logger_config import logger  # Import the shared logger
import gtts
from playsound import playsound

CLASS_ALERT = "classalert.mp3"

class WatcherBase(app_callback_class):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.logger = logger  # Use the shared logger from logger_config
        
        # Extract common config parameters
        self.class_to_track = config.get('CLASS_TO_TRACK', 'person')
        self.class_detected_count = config.get('CLASS_DETECTED_COUNT', 4)
        self.class_gone_seconds = config.get('CLASS_GONE_SECONDS', 3)
        self.class_match_confidence = config.get('CLASS_MATCH_CONFIDENCE', 0.4)
        self.save_detection_images = config.get('SAVE_DETECTION_IMAGES', True)
        self.show_detection_boxes = config.get('SHOW_DETECTION_BOXES', True)
        self.save_detection_video = config.get('SAVE_DETECTION_VIDEO', True)
        self.frame_rate = config.get('FRAME_RATE', 30)
        
        # Check environment variable for output directory first, then config
        self.output_directory = os.environ.get(
            'WATCHER_OUTPUT_DIRECTORY',  # First check environment variable
            config.get('OUTPUT_DIRECTORY', 'output')  # Fall back to config or default
        )
        
        # Ensure the output directory is an absolute path
        if not os.path.isabs(self.output_directory):
            # If it's a relative path, make it absolute based on current working directory
            self.output_directory = os.path.abspath(self.output_directory)
            
        self.logger.info(f"Using output directory: {self.output_directory}")
        
        self.max_video_seconds = config.get('VIDEO_MAX_SECONDS', 30)
        self.daytime_only = config.get('DAYTIME_ONLY', False)
        
        # Add field for HEF model name
        self.hef_model = "unknown"

        self.create_speech_files()
        
        # Initialize state variables for debouncing
        self.detection_counter = 0  # Count consecutive frames with detections
        self.no_detection_counter = 0  # Count consecutive frames without detections
        self.max_instances = 0  # Maximum number of instances detected in a frame
        self.object_centroid = None  # Current object centroid
        self.start_centroid = None  # Start centroid when object is first detected
        self.end_centroid = None  # End centroid when object is gone
        
        # State tracking, is the debounced object active or not?
        self.is_active_tracking = False

        # Variables for computing average detection instance count
        self.total_detection_instances = 0
        self.active_detection_count = 0
        self.detection_counts = []
        self.max_mean_detection_count = 0

        # Variables for computing moving average of velocity
        self.avg_velocity = Point2D(0.0, 0.0)
        self.previous_centroid = None

        # Initialize video writer
        self.video_writer = None
        self.video_filename = None
        self.format = None
        self.width = None
        self.height = None
        self.video_frame_count = 0
        self.video_start_time = None
        self.video_truncated = False  # Flag to log truncation once
        self.tracking_start_time = None  # Track when active tracking starts
        
        # Application reference
        self.app = None
        
        # For saving frames
        self.save_frame = None
        self.current_frame = None
        self.detection_frame = None
        self.active_timestamp = None
        self.initial_max_confidence = 0.0

        # Add a field to store all detections for subclasses to use
        self.all_detections = []

    def create_speech_files(self):
        tts = gtts.gTTS(f"Its a {self.class_to_track.upper()}")
        tts.save(CLASS_ALERT)

    def on_eos(self):
        """Handle end of stream."""
        if self.is_active_tracking:
            self.stop_active_tracking()

    def start_video_recording(self, width, height, video_filename, format, fps):
        """Start recording video."""
        self.video_filename = video_filename.replace('.mp4', '.m4v')  # Use .m4v extension initially
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')  # Ensure the codec is set for MP4 format
        self.video_writer = cv2.VideoWriter(self.video_filename, fourcc, fps, (width, height))
        self.video_frame_count = 0  # Reset frame count at start
        self.video_start_time = datetime.datetime.now()  # Record start time

    def write_video_frame(self, frame):
        """Write a frame to the video."""
        if self.video_writer is not None and self.current_frame is not None:
            self.video_writer.write(frame)

    def draw_detection_boxes(self, detections, width, height):
        """Draw bounding boxes around detections."""
        if self.current_frame is not None and self.show_detection_boxes:
            for detection in detections:
                bbox = detection.get_bbox()
                cv2.rectangle(self.current_frame, 
                              (int(bbox.xmin() * width), int(bbox.ymin() * height)), 
                              (int(bbox.xmax() * width), int(bbox.ymax() * height)), 
                              (0, 0, 255), 1)

    def stop_video_recording(self, final_filename):
        """Stop recording video and save it."""
        if self.video_writer is not None:
            self.video_writer.release()
            self.video_writer = None
            os.rename(self.video_filename, final_filename)
            self.logger.info(f"Video saved as {final_filename}")

    def convert_video_to_h264(self, video_path):
        """Convert video to H264 format using ffmpeg."""
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
            self.logger.info(f"Successfully converted {video_path} to H264 and saved as {final_path}")
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to convert video {video_path} to H264: {e}")
            # Clean up temp file if it exists
            if os.path.exists(temp_path):
                os.remove(temp_path)
     
    def get_average_detection_instance_count(self):
        """Calculate the average detection instance count."""
        if not self.detection_counts:
            return 0
        detection_counts_np = np.array(self.detection_counts)
        window_size = self.frame_rate
        if len(detection_counts_np) >= window_size:
            moving_averages = np.convolve(detection_counts_np, np.ones(window_size)/window_size, mode='valid')
            return moving_averages.max()
        else:
            return np.mean(detection_counts_np)

    def playsound_async(self, sound_file):
        """Play sound asynchronously in a separate thread."""
        threading.Thread(target=playsound, args=(sound_file,), daemon=True).start()

    def start_active_tracking(self, class_detections):
        """Start tracking detected objects."""
        self.is_active_tracking = True
        self.max_instances = len(class_detections)
        self.start_centroid = self.object_centroid
        
        self.save_frame = self.current_frame
        self.active_timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]

        # Draw detection boxes on the frame if SHOW_DETECTION_BOXES is True
        if self.current_frame is not None and self.show_detection_boxes:
            self.draw_detection_boxes(class_detections, self.width, self.height)

        # Ensure output directory exists
        date_subdir = datetime.datetime.now().strftime("%Y%m%d")
        output_dir = f"{self.output_directory}/{date_subdir}"
        os.makedirs(output_dir, exist_ok=True)

        # Start recording video if SAVE_DETECTION_VIDEO and self.video_writer is None and frame is not None:
        if self.save_detection_video and self.video_writer is None and self.current_frame is not None:
            video_filename = f"{output_dir}/{self.active_timestamp}_{self.class_to_track}.mp4"
            self.start_video_recording(self.width, self.height, video_filename, self.format, self.frame_rate)

        self.logger.info(f"{self.class_to_track.upper()} DETECTED {self.start_centroid} at: {datetime.datetime.now()}")

        # Record maximum detection confidence when tracking starts
        self.initial_max_confidence = max(det.get_confidence() for det in class_detections) if class_detections else 0.0
        self.tracking_start_time = datetime.datetime.now()  # Record tracking start time

        self.playsound_async(CLASS_ALERT)

    def active_tracking(self, class_detections):
        """Update tracking information for active objects."""
        # Update total detection instances and active detection count for later averaging
        detection_instance_count = len(class_detections)
        if detection_instance_count > 0:
            # Draw detection boxes on the frame if SHOW_DETECTION_BOXES is True
            if self.show_detection_boxes:
                self.draw_detection_boxes(class_detections, self.width, self.height)
            self.total_detection_instances += detection_instance_count
            self.active_detection_count += 1
            self.detection_counts.append(detection_instance_count)
            if detection_instance_count > self.max_instances:
                self.max_instances = detection_instance_count
                self.save_frame = self.current_frame

        # If a frame is available, write the frame to the video
        if self.current_frame is not None and self.video_writer is not None and self.video_start_time:
            elapsed = (datetime.datetime.now() - self.video_start_time).total_seconds()
            if elapsed < self.max_video_seconds:
                self.write_video_frame(self.current_frame)
            else:
                if not self.video_truncated:
                    self.logger.info(f"Video truncated after {self.max_video_seconds} seconds.")
                    self.video_truncated = True

        # Update moving average of velocity
        if self.object_centroid is not None and self.previous_centroid is not None:
            delta = self.object_centroid.subtract(self.previous_centroid)
            self.avg_velocity = Point2D(
                (self.avg_velocity.x * (self.active_detection_count - 1) + delta.x) / self.active_detection_count,
                (self.avg_velocity.y * (self.active_detection_count - 1) + delta.y) / self.active_detection_count
            )
        self.previous_centroid = self.object_centroid

    def create_metadata(self, root_filename, event_seconds):
        """Create metadata dictionary."""
        metadata = {
            "filename": root_filename,
            "hef_model": self.hef_model,  # Include the HEF model name
            "class": self.class_to_track,
            "initial_confidence": round(self.initial_max_confidence, 2),
            "timestamp": self.active_timestamp,
            "max_instances": self.max_instances,
            "average_instances": self.get_average_detection_instance_count(),
            "event_seconds": round(event_seconds, 1),  # Round to 1 decimal place
            "video_truncated": self.video_truncated,  
            "reviewed": False  # Add reviewed field, initially false
        }
        return metadata
    
    def root_filename(self):
        """Create final root filename."""
        avg_detection_count_rounded = round(self.get_average_detection_instance_count())
        return f"{self.active_timestamp}_{self.class_to_track}_x{avg_detection_count_rounded}"

    def stop_active_tracking(self, abort=False):
        """Stop tracking objects and save relevant data.
        
        Args:
            abort (bool): If True, don't save metadata and delete any created files.
        """
        self.is_active_tracking = False
        self.end_centroid = self.object_centroid
        
        avg_detection_count = self.get_average_detection_instance_count()
        self.logger.info(f"{self.class_to_track.upper()} GONE time: {datetime.datetime.now()}, avg count: {avg_detection_count:.2f}, max count: {self.max_instances}")

        # Create root filename
        root_filename = self.root_filename()

        # Ensure output directories exist
        date_subdir = datetime.datetime.now().strftime("%Y%m%d")
        output_dir = f"{self.output_directory}/{date_subdir}"
        os.makedirs(output_dir, exist_ok=True)

        # Stop any video recording
        final_video_filename = f"{output_dir}/{root_filename}.m4v"  # Use .m4v extension
        self.stop_video_recording(final_video_filename)

        # If aborting, delete the video file and skip the rest of the process
        if abort:
            self.logger.info(f"Aborting tracking, deleting any created files.")
            # Delete video file if it exists
            if os.path.exists(final_video_filename):
                os.remove(final_video_filename)
                self.logger.info(f"Deleted video file: {final_video_filename}")
                
            # Check for and delete the MP4 version if it exists
            mp4_filename = final_video_filename.replace('.m4v', '.mp4')
            if os.path.exists(mp4_filename):
                os.remove(mp4_filename)
                self.logger.info(f"Deleted converted video file: {mp4_filename}")
                
            # Delete image file if it exists
            if hasattr(self, 'image_filename') and self.image_filename and os.path.exists(self.image_filename):
                os.remove(self.image_filename)
                self.logger.info(f"Deleted image file: {self.image_filename}")
        else:
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
                self.logger.info(f"Image saved as {self.image_filename}")

            # Compute event duration in seconds from active_timestamp
            try:
                event_start = datetime.datetime.strptime(self.active_timestamp + "000", "%Y%m%d_%H%M%S_%f")
            except Exception:
                event_start = datetime.datetime.now()
            event_seconds = (datetime.datetime.now() - event_start).total_seconds()

            # Create metadata dictionary
            metadata = self.create_metadata(root_filename, event_seconds)

            # Save metadata as JSON file
            metadata_filename = f"{output_dir}/{root_filename}.json"
            with open(metadata_filename, 'w') as metadata_file:
                json.dump(metadata, metadata_file)
            self.logger.info(f"Metadata saved: {metadata}")

        # Reset tracking state
        self.max_instances = 0
        self.save_frame = None
        self.object_centroid = None
        self.avg_velocity = Point2D(0.0, 0.0)
        self.previous_centroid = None
        self.detection_counts.clear()
        self.max_mean_detection_count = 0

    def get_avg_centroid(self, class_detections):
        """Calculate the average centroid of a list of class detections."""
        centroids = []
        for detection in class_detections:
            bbox = detection.get_bbox()
            centroid_x = (bbox.xmin() + bbox.xmax()) / 2
            centroid_y = (bbox.ymin() + bbox.ymax()) / 2
            centroids.append(Point2D(centroid_x, centroid_y))
            
        if centroids:
            avg_centroid_x = sum(point.x for point in centroids) / len(centroids)
            avg_centroid_y = sum(point.y for point in centroids) / len(centroids)
            return Point2D(avg_centroid_x, avg_centroid_y)
        return None


def watcher_base_callback(pad, info, user_data):
    """
    Generic callback function for processing video frames and detecting objects.
    Args:
        pad (Gst.Pad): The pad from which the buffer is received.
        info (Gst.PadProbeInfo): The probe info containing the buffer.
        user_data (WatcherBase): Custom user data object for tracking state and configurations.
    Returns:
        Gst.PadProbeReturn: Indicates the result of the pad probe.
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
    
    # Get the detections from the buffer
    roi = hailo.get_roi_from_buffer(buffer)
    detections = roi.get_objects_typed(hailo.HAILO_DETECTION)
    
    # Store all detections for subclasses to use
    user_data.all_detections = detections

    # Filter detections that match class_to_track and have confidence greater than class_match_confidence
    class_detections = [
        detection for detection in detections 
        if (detection.get_label() == user_data.class_to_track) 
        and detection.get_confidence() > user_data.class_match_confidence
    ]

    # Count the number of detections that match class_to_track
    detection_instance_count = len(class_detections)
    object_detected = False
    if detection_instance_count > 0:
        object_detected = True
        user_data.detection_frame = user_data.current_frame
        user_data.object_centroid = user_data.get_avg_centroid(class_detections)

    # Debouncing logic to start/stop active tracking
    if object_detected:
        user_data.detection_counter += 1
        user_data.no_detection_counter = 0
        
        # Only activate after class_detected_count consecutive frames with detections
        if user_data.detection_counter >= user_data.class_detected_count and not user_data.is_active_tracking:
            user_data.start_active_tracking(class_detections)
    else:
        user_data.no_detection_counter += 1
        user_data.detection_counter = 0
        
        # Only deactivate after class_gone_seconds without detections
        if user_data.no_detection_counter >= (user_data.class_gone_seconds * user_data.frame_rate) and user_data.is_active_tracking:
            user_data.stop_active_tracking()

    # Active tracking
    if user_data.is_active_tracking:
        user_data.active_tracking(class_detections)

    return Gst.PadProbeReturn.OK
