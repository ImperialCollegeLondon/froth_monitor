import queue
import time
from PySide6.QtCore import QObject, Signal

# Import MainGUIWindow at the beginning

# Import FrameModel from fm_model module
from froth_monitor.processing import FrameModel
from froth_monitor.utils.performance_monitor import PerformanceMonitor

# Import the camera and network threads
from froth_monitor.video_threads.camera_thread import CameraThread
from froth_monitor.video_threads.network_thread import NetworkThread


# Import the video recorder module
from froth_monitor.handlers.video_recorder import VideoRecorder
# from froth_monitor.event_handler import EventHandler
from froth_monitor.handlers.logger_config import get_logger


from froth_monitor.handlers.roi_handler import ROIHandler
from froth_monitor.handlers.recorder_thread import VideoRecordingWorker 
# from froth_monitor.handlers.data_handler import DataHandler
from froth_monitor.utils.frame_converter import FrameConverter
from froth_monitor.handlers.frame_display_manager import FrameDisplayManager

# Initialize logger for this module
logger = get_logger(__name__)

class FrameProcessor(QObject):

    update_velocity_plot = Signal(list)
    processing_fps_updated = Signal(float)

    def __init__(
        self,
        frame_model: FrameModel,
        video_thread: CameraThread | NetworkThread,
        video_recorder: VideoRecorder,
        roi_handler: ROIHandler,
        frame_resample_handler,
        display_manager: FrameDisplayManager,
    ):
        super().__init__()
        self.playing = True # Set to True by default, frame processor can only be initialised when the video is playing
        self.frame_model = frame_model
        self.video_thread = video_thread
        self.video_recorder = video_recorder
        self.roi_handler = roi_handler
        self.frame_resample_handler = frame_resample_handler
        self.display_manager = display_manager
        
        # Initialize and start the video recording worker thread
        self.video_queue: queue.Queue = queue.Queue(maxsize=30)
        self.video_recording_worker = VideoRecordingWorker(
            self.video_recorder, self.video_queue
        )
        self.video_recording_worker.start()
        self.perf_monitor = PerformanceMonitor()

        # Processing performance tracking
        self.last_proc_time = 0.0
        self.proc_fps_ema = 0.0
        self.alpha = 0.1  # Smoothing factor for EMA


    def set_playback_state(self, playing: bool):
        self.playing = playing

    # -----------------------------------Frame Processing-----------------------------------------------
    def process_new_frame(self, frame):
        """
        Process and display a new frame received from the camera thread.

        This method is called whenever a new frame is available from the camera thread.
        It processes the frame, updates the UI, and handles ROI display.

        Args:
            frame: The new frame from the camera thread
        """
        if not self.playing:  # Access playing state from VideoHandler
            return

        start_time = time.perf_counter()

        # Store the current frame for potential further processing
        self.current_frame = frame

        # Convert frame to QImage and scale it for display
        qt_image = FrameConverter.bgr_to_qimage(frame)
        canvas_width, canvas_height = self.display_manager.get_canvas_size()
        scaled_image = FrameConverter.scale_to_fit(
            qt_image, canvas_width, canvas_height
        )

        # Use FrameResampleHandler for processing (independent of display resolution)
        processing_frame, proc_res = self.frame_resample_handler.resample_frame(frame)
        
        # Process the frame with the frame model
        # Only allow to let frame pass in when the previous frame has been processed
        # This is to prevent the overstacking of frames
        self.video_thread.if_release = False
        self._process_frame_with_model(processing_frame)
        self.video_thread.if_release = True

        # Display frame and update status
        self.display_manager.display_frame(scaled_image)
        with self.frame_model._processing_lock:
            self.display_manager.update_status(
                self.current_frame_number,
                self.frame_model.last_processed_time or "N/A"
            )

        self.perf_monitor.start_timer("frame_recording")
        # Record frame if recording is active (non-blocking)
        if self.video_recorder.is_active():
            self.video_recording_worker.add_frame(frame)
        self.perf_monitor.stop_timer("frame_recording")

        # Calculate processing FPS
        duration = time.perf_counter() - start_time
        if duration > 0:
            current_fps = 1.0 / duration
            if self.proc_fps_ema == 0:
                self.proc_fps_ema = current_fps
            else:
                self.proc_fps_ema = (self.alpha * current_fps) + ((1 - self.alpha) * self.proc_fps_ema)
            
            self.processing_fps_updated.emit(self.proc_fps_ema)


    # Note: Utility methods extracted to dedicated classes:
    # - Frame conversion -> FrameConverter utility class
    # - GUI display -> FrameDisplayManager
    # - Frame resampling -> FrameResampleHandler

    def _process_frame_with_model(self, resized_frame):
        """
        Process the frame with the frame model and display ROIs.

        Args:
            resized_frame: The resized frame to process
        """
        # Process the frame
        self.perf_monitor.start_timer("fm_model_processing")
        with self.frame_model._processing_lock:
            self.current_frame_number, roi_list, update_velo_plot, update_average_velo = (
                self.frame_model.process_frame(resized_frame)
            )
        self.perf_monitor.stop_timer("fm_model_processing")

        # Display ROIs on overlay widget
        self.perf_monitor.start_timer("roi_display_on_canvas")
        self.display_manager.overlay_widget.display_roi(roi_list)
        self.perf_monitor.stop_timer("roi_display_on_canvas")

        # Update the velocity plot with the latest data
        if update_velo_plot:
            self.perf_monitor.start_timer("receive_plot_signal")
            self.update_velocity_plot.emit(roi_list)
            
        self.perf_monitor.log_frame(self.current_frame_number)
    
    def cleanup(self):
        """Clean up resources, particularly the video recording worker thread.
        
        This method should be called when the FrameProcessor is being destroyed
        or when resetting the application to ensure proper cleanup of threads
        and memory.
        """
        logger.info("FrameProcessor: Starting cleanup...")
        
        # Stop video recording worker thread
        if hasattr(self, 'video_recording_worker'):
            self.video_recording_worker.stop()
            self.video_recording_worker.wait()  # Wait for thread to finish
            logger.info("FrameProcessor: Video recording worker thread stopped")
        
        # Clear video queue
        if hasattr(self, 'video_queue'):
            while not self.video_queue.empty():
                try:
                    self.video_queue.get_nowait()
                except queue.Empty:
                    break
            logger.debug("FrameProcessor: Video queue cleared")
        
        # Clear current frame reference
        self.current_frame = None
        
        logger.info("FrameProcessor: Cleanup complete")
