import queue
from PySide6.QtCore import QThread

# Import the video recorder module
from froth_monitor.handlers.video_recorder import VideoRecorder
# from froth_monitor.event_handler import EventHandler
from froth_monitor.handlers.logger_config import get_logger

# Initialize logger for this module
logger = get_logger(__name__)

class VideoRecordingWorker(QThread):
    """
    Worker thread for handling video recording asynchronously.
    
    This class runs in a separate thread to prevent video recording operations
    from blocking the main UI thread and frame processing pipeline.
    """
    
    def __init__(self, video_recorder: VideoRecorder, frame_queue: queue.Queue):
        super().__init__()
        self.video_recorder = video_recorder
        self.frame_queue = frame_queue
        self.running = True
        
    def add_frame(self, frame):
        """
        Add a frame to the recording queue.
        
        Args:
            frame: The frame to be recorded
        """
        try:
            # Use put_nowait to avoid blocking if queue is full
            self.frame_queue.put_nowait(frame.copy())  # Copy frame to avoid reference issues
        except queue.Full:
            # If queue is full, skip this frame to prevent blocking
            logger.warning("Video recording queue is full, skipping frame")
    
    def run(self):
        """
        Main thread loop for processing video recording frames.
        """
        while self.running:
            try:
                # Wait for a frame with timeout to allow checking running flag
                frame = self.frame_queue.get(timeout=0.1)
                
                # Record the frame if recording is active
                if self.video_recorder.is_active():
                    self.video_recorder.record_frame(frame)
                    
                self.frame_queue.task_done()
                
            except queue.Empty:
                # No frame available, continue loop
                continue
            except Exception as e:
                logger.error(f"Error in video recording worker: {e}")
    
    def stop(self):
        """
        Stop the worker thread gracefully.
        """
        self.running = False
        # Clear the queue
        while not self.frame_queue.empty():
            try:
                self.frame_queue.get_nowait()
                self.frame_queue.task_done()
            except queue.Empty:
                break
        self.wait()  # Wait for thread to finish
