from hailo_apps_infra.detection_pipeline import GStreamerDetectionApp
from hailo_apps_infra.gstreamer_helper_pipelines import (
    INFERENCE_PIPELINE,
    INFERENCE_PIPELINE_WRAPPER,
    TRACKER_PIPELINE,
    USER_CALLBACK_PIPELINE,
    QUEUE,
    get_camera_resulotion,
    get_source_type
)
from hailo_apps_infra.hailo_rpi_common import (
    get_default_parser,
    detect_hailo_arch,
)
from screeninfo import get_monitors
import datetime
import time
from astral import LocationInfo
from astral.sun import sun
import threading
from gi.repository import Gst
import os
from logger_config import logger  # Import the logger


def SOURCE_PIPELINE(video_source, video_width=640, video_height=640, video_format='RGB', name='source', no_webcam_compression=False):
    """
    Creates a GStreamer pipeline string for the video source.

    Args:
        video_source (str): The path or device name of the video source.
        video_width (int, optional): The width of the video. Defaults to 640.
        video_height (int, optional): The height of the video. Defaults to 640.
        video_format (str, optional): The video format. Defaults to 'RGB'.
        name (str, optional): The prefix name for the pipeline elements. Defaults to 'source'.

    Returns:
        str: A string representing the GStreamer pipeline for the video source.
    """
    source_type = get_source_type(video_source)

    if source_type == 'usb':
        if no_webcam_compression:
            # When using uncomressed format, only low resolution is supported
            source_element = (
                f'v4l2src device={video_source} name={name} ! '
                f'video/x-raw, format=RGB, width=640, height=480 ! '
                'videoflip name=videoflip video-direction=horiz ! '
            )
        else:
            # Use compressed format for webcam
            width, height = get_camera_resulotion(video_width, video_height)
            source_element = (
                f'v4l2src device={video_source} name={name} ! image/jpeg, framerate=30/1, width={width}, height={height} ! '
                f'{QUEUE(name=f"{name}_queue_decode")} ! '
                f'decodebin name={name}_decodebin ! '
                f'videoflip name=videoflip video-direction=horiz ! '
            )
    elif source_type == 'rpi':
        source_element = (
            f'appsrc name=app_source is-live=true leaky-type=downstream max-buffers=3 ! '
            #'videoflip name=videoflip video-direction=horiz ! '
            f'video/x-raw, format={video_format}, width={video_width}, height={video_height} ! '
        )
    elif source_type == 'libcamera':
        source_element = (
            f'libcamerasrc name={name} ! '
            f'video/x-raw, format={video_format}, width=1536, height=864 ! '
        )
    elif source_type == 'ximage':
        source_element = (
            f'ximagesrc xid={video_source} ! '
            f'{QUEUE(name=f"{name}queue_scale_")} ! '
            f'videoscale ! '
        )
    else:
        source_element = (
            f'filesrc location="{video_source}" name={name} ! '
            f'{QUEUE(name=f"{name}_queue_decode")} ! '
            f'decodebin name={name}_decodebin ! '
        )
    source_pipeline = (
        f'{source_element} '
        f'{QUEUE(name=f"{name}_scale_q")} ! '
        f'videoscale name={name}_videoscale n-threads=2 ! '
        f'{QUEUE(name=f"{name}_convert_q")} ! '
        f'videoconvert n-threads=3 name={name}_convert qos=false ! '
        f'video/x-raw, pixel-aspect-ratio=1/1, format={video_format}, width={video_width}, height={video_height} '
    )

    return source_pipeline

def get_screen_resolution():
    """Get current screen resolution."""
    monitor = get_monitors()[0]
    width = monitor.width
    height = monitor.height
    return width, height

def DISPLAY_PIPELINE(video_sink='xvimagesink', sync='true', show_fps='false', name='hailo_display'):
    """
    Creates a GStreamer pipeline string for displaying the video.
    It includes the hailooverlay plugin to draw bounding boxes and labels on the video.

    Args:
        video_sink (str, optional): The video sink element to use. Defaults to 'xvimagesink'.
        sync (str, optional): The sync property for the video sink. Defaults to 'true'.
        show_fps (str, optional): Whether to show the FPS on the video sink. Should be 'true' or 'false'. Defaults to 'false'.
        name (str, optional): The prefix name for the pipeline elements. Defaults to 'hailo_display'.

    Returns:
        str: A string representing the GStreamer pipeline for displaying the video.
    """
    screen_width, screen_height = min(get_screen_resolution(), (1024, 1024))

    # Construct the display pipeline string
    display_pipeline = (
        f'{QUEUE(name=f"{name}_hailooverlay_q")} ! '
        f'hailooverlay name={name}_hailooverlay ! '
        f'{QUEUE(name=f"{name}_videoscale_q")} ! '
        f'videoscale ! '
        f'video/x-raw, width={screen_width}, height={screen_height}, pixel-aspect-ratio=1/1 ! '
        f'{QUEUE(name=f"{name}_videoconvert_q")} ! '
        f'videoconvert name={name}_videoconvert n-threads=2 qos=false ! '
        f'{QUEUE(name=f"{name}_q")} ! '
        f'fpsdisplaysink name={name} video-sink={video_sink} sync={sync} text-overlay={show_fps} signal-fps-measurements=true '
    )

    return display_pipeline

def get_active_period(date):
    """
    Calculate active period based on sunrise and sunset times.
    
    Args:
        date: The date to calculate the active period for.
        
    Returns:
        tuple: (active_start, active_end) times for the given date.
    """
    # Adjust location as needed; default uses London coordinates.
    loc = LocationInfo("London", "England", "Europe/London", 51.5, -0.116)
    s = sun(loc.observer, date=date)
    active_start = s['sunrise'] - datetime.timedelta(minutes=30)
    active_end = s['sunset'] + datetime.timedelta(minutes=30)
    return active_start.replace(tzinfo=None), active_end.replace(tzinfo=None)

class GStreamerWatcherApp(GStreamerDetectionApp):
    """Base class for watcher applications using the Hailo detection pipeline."""
    
    def __init__(self, app_callback, user_data):
        """
        Initialize the watcher application.
        
        Args:
            app_callback: Callback function to process frames.
            user_data: User data to pass to the callback.
        """
        parser = get_default_parser()
        parser.add_argument(
            "--labels-json",
            default=None,
            help="Path to custom labels JSON file",
        )
        args = parser.parse_args()
        
        # Call the parent class constructor
        super().__init__(args, user_data)
        
        # Set Hailo parameters
        self.batch_size = 2
        self.nms_score_threshold = 0.3
        self.nms_iou_threshold = 0.45

        # Determine the architecture if not specified
        if args.arch is None:
            detected_arch = detect_hailo_arch()
            if detected_arch is None:
                raise ValueError("Could not auto-detect Hailo architecture. Please specify --arch manually.")
            self.arch = detected_arch
            logger.info(f"Auto-detected Hailo architecture: {self.arch}")
        else:
            self.arch = args.arch

        # Set the HEF file path based on the architecture
        if args.hef_path is not None:
            self.hef_path = args.hef_path
        elif self.arch == "hailo8":
            self.hef_path = os.path.join(self.current_path, '../resources/yolov8m.hef')
        else:  # hailo8l
            self.hef_path = os.path.join(self.current_path, '../resources/yolov8s_h8l.hef')

        # Set the post-processing shared object file
        self.post_process_so = os.path.join(self.current_path, '../resources/libyolo_hailortpp_postprocess.so')
        self.post_function_name = "filter_letterbox"
        
        # User-defined label JSON file
        self.labels_json = args.labels_json

        self.app_callback = app_callback

        self.thresholds_str = (
            f"nms-score-threshold={self.nms_score_threshold} "
            f"nms-iou-threshold={self.nms_iou_threshold} "
            f"output-format-type=HAILO_FORMAT_TYPE_FLOAT32"
        )

        logger.info(f"Program arguments: {args}")
        self.create_pipeline()

    def get_pipeline_string(self):
        """
        Create the GStreamer pipeline string.
        
        Returns:
            str: The GStreamer pipeline string.
        """
        source_pipeline = SOURCE_PIPELINE(self.video_source, self.video_width, self.video_height)
        detection_pipeline = INFERENCE_PIPELINE(
            hef_path=self.hef_path,
            post_process_so=self.post_process_so,
            post_function_name=self.post_function_name,
            batch_size=self.batch_size,
            config_json=self.labels_json,
            additional_params=self.thresholds_str)
        detection_pipeline_wrapper = INFERENCE_PIPELINE_WRAPPER(detection_pipeline)
        tracker_pipeline = TRACKER_PIPELINE(class_id=-1)
        user_callback_pipeline = USER_CALLBACK_PIPELINE()
        display_pipeline = DISPLAY_PIPELINE(video_sink="xvimagesink", sync=self.sync, show_fps=self.show_fps)

        pipeline_string = (
            f'{source_pipeline} ! '
            f'{detection_pipeline_wrapper} ! '
            # f'{tracker_pipeline} ! '
            f'{user_callback_pipeline} ! '
            f'{display_pipeline}'
        )
        logger.info(f"Pipeline: {pipeline_string}")
        return pipeline_string

    def monitor_active_period(self):
        """Thread method to monitor active period and pause/play the pipeline accordingly."""
        check_interval = 60  # seconds
        while True:
            # Only perform active period check if DAYTIME_ONLY is True
            if not getattr(self.user_data, "daytime_only", False):
                time.sleep(check_interval)
                continue

            now = datetime.datetime.now()
            active_start, active_end = get_active_period(now.date())
            if now < active_start or now > active_end:
                # Outside active period; pause the pipeline if not already paused.
                current_state = self.pipeline.get_state(0).state
                if current_state != Gst.State.PAUSED:
                    logger.info("Outside active period. Pausing pipeline.")
                    self.pipeline.set_state(Gst.State.PAUSED)
            else:
                # Within active period; play the pipeline if not already playing.
                current_state = self.pipeline.get_state(0).state
                if current_state != Gst.State.PLAYING:
                    logger.info("Within active period. Setting pipeline to PLAYING.")
                    self.pipeline.set_state(Gst.State.PLAYING)
            time.sleep(check_interval)

    def on_eos(self):
        """Handle end-of-stream event."""
        self.user_data.on_eos()
        self.pipeline.set_state(Gst.State.PAUSED)

    def run(self):
        """Run the watcher application."""
        # Proceed with the pipeline execution.
        self.user_data.pipeline = self.pipeline
        
        # Start the active period monitor thread.
        monitor_thread = threading.Thread(target=self.monitor_active_period, daemon=True)
        monitor_thread.start()

        # Set pipeline to an initial state.
        self.pipeline.set_state(Gst.State.PAUSED)
        super(GStreamerWatcherApp, self).run()
