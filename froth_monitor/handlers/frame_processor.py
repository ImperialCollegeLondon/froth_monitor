import queue
import time
import numpy as np
from PySide6.QtCore import QObject, Signal, QThread, Slot

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

class ROIProcessingWorker(QThread):
    """
    Worker thread for handling ROI processing asynchronously.
    """
    finished = Signal(int, list, bool, bool)  # frame_count, roi_list, update_plot, update_average

    def __init__(self, frame_model: FrameModel):
        super().__init__()
        self.frame_model = frame_model
        self.frame_queue: queue.Queue = queue.Queue(maxsize=1)
        self.running = True
        self.perf_monitor = PerformanceMonitor()

    def add_frame(self, frame: np.ndarray):
        """Add a frame to the processing queue."""
        try:
            self.frame_queue.put_nowait(frame)
        except queue.Full:
            # Skip if still processing previous frame
            pass

    def run(self):
        """Main loop for ROI processing."""
        while self.running:
            try:
                frame = self.frame_queue.get(timeout=0.1)
                
                self.perf_monitor.start_timer("fm_model_processing")
                with self.frame_model._processing_lock:
                    frame_count, roi_list, update_plot, update_average = (
                        self.frame_model.process_frame(frame)
                    )
                self.perf_monitor.stop_timer("fm_model_processing")
                
                self.finished.emit(frame_count, roi_list, update_plot, update_average)
                self.frame_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"ROIProcessingWorker error: {e}")

    def stop(self):
        """Stop the worker thread."""
        self.running = False
        # self.wait() # wait() should be called by the caller if they want to ensure it stopped


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

        # Initialize and start the ROI processing worker thread
        self.roi_worker = ROIProcessingWorker(self.frame_model)
        self.roi_worker.finished.connect(self._on_processing_finished)
        self.roi_worker.start()

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
        It handles display immediately and offloads processing to a worker thread.

        Args:
            frame: The new frame from the camera thread
        """
        if not self.playing:  # Access playing state from VideoHandler
            return

        self.start_proc_time = time.perf_counter()

        # Store the current frame for potential further processing
        self.current_frame = frame

        # Convert frame to QImage and scale it for display (Fast)
        qt_image = FrameConverter.bgr_to_qimage(frame)
        canvas_width, canvas_height = self.display_manager.get_canvas_size()
        scaled_image = FrameConverter.scale_to_fit(
            qt_image, canvas_width, canvas_height
        )

        # Display frame immediately (Fast)
        self.display_manager.display_frame(scaled_image)

        # Use FrameResampleHandler for processing (independent of display resolution)
        processing_frame, _ = self.frame_resample_handler.resample_frame(frame)
        
        # Offload processing to background worker
        # Block next frame from emission until this one finishes analysis
        self.video_thread.if_release = False
        self.roi_worker.add_frame(processing_frame)

        # Record frame if recording is active (non-blocking)
        if self.video_recorder.is_active():
            self.video_recording_worker.add_frame(frame)

    @Slot(int, list, bool, bool)
    def _on_processing_finished(self, frame_count, roi_list, update_plot, update_average):
        """
        Handle results from the ROI processing worker.
        Runs on the GUI thread.
        """
        # Update display status with results
        with self.frame_model._processing_lock:
            self.display_manager.update_status(
                frame_count,
                self.frame_model.last_processed_time or "N/A"
            )

        # Display ROIs on overlay widget
        self.display_manager.overlay_widget.display_roi(roi_list)

        # Update the velocity plot if needed
        if update_plot:
            self.update_velocity_plot.emit(roi_list)

        # Calculate and emit processing FPS
        duration = time.perf_counter() - self.start_proc_time
        if duration > 0:
            current_fps = 1.0 / duration
            if self.proc_fps_ema == 0:
                self.proc_fps_ema = current_fps
            else:
                self.proc_fps_ema = (self.alpha * current_fps) + ((1 - self.alpha) * self.proc_fps_ema)
            
            self.processing_fps_updated.emit(self.proc_fps_ema)

        self.perf_monitor.log_frame(frame_count)
        
        # Unlock VideoThread to allow next frame capture/emission
        self.video_thread.if_release = True


    # Note: Utility methods extracted to dedicated classes:
    # - Frame conversion -> FrameConverter utility class
    # - GUI display -> FrameDisplayManager
    # - Frame resampling -> FrameResampleHandler

    def cleanup(self):
        """Clean up resources, particularly the worker threads.
        
        This method should be called when the FrameProcessor is being destroyed
        or when resetting the application to ensure proper cleanup of threads
        and memory.
        """
        logger.info("FrameProcessor: Starting cleanup...")
        
        # Stop ROI processing worker thread
        if hasattr(self, 'roi_worker'):
            self.roi_worker.stop()
            logger.info("FrameProcessor: ROI processing worker thread stopped")

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
