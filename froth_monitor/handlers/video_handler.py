"""Video Handler Module for Froth Monitor Application.

This module provides the VideoHandler class which manages video playback and capture
functionality. It supports both live camera feeds and pre-recorded video files,
operating in a fully decoupled manner from the GUI through Qt signals.

The VideoHandler communicates with the GUI layer exclusively through signals,
making it highly testable and reusable in different UI contexts.

Example:
    Basic usage of VideoHandler:
    
    >>> video_handler = VideoHandler(frame_model, camera_thread, network_thread, video_thread)
    >>> video_handler.camera_selection_requested.connect(show_camera_dialog)
    >>> video_handler.handle_video_import("webcam")
"""

from typing import Optional, Union
from PySide6.QtCore import QObject, Signal

# Import FrameModel from fm_model module
from froth_monitor.processing import FrameModel
from froth_monitor.video_threads.camera_thread import CameraThread
from froth_monitor.video_threads.network_thread import NetworkThread
from froth_monitor.handlers.logger_config import get_logger

# Initialize logger for this module
logger = get_logger(__name__)


class VideoHandler(QObject):
    """Manages video playback and capture for the Froth Monitor application.
    
    This class handles all video-related operations including loading cameras,
    loading video files, controlling playback (play/pause), and managing video
    thread lifecycles. It communicates with the GUI exclusively through Qt signals,
    ensuring complete separation of concerns.
    
    Signals:
        thread_activate: Emitted when normal mode is triggered
        video_paused: Emitted when video playback is paused
        video_resumed: Emitted when video playback is resumed
        video_started: Emitted when video playback starts
        video_cannot_resume: Emitted when video cannot be resumed
        status_message (str): Emitted to update status bar with a message
        info_occurred (str): Emitted when an info/warning/error occurs
        camera_selection_requested: Emitted to request camera selection from user
        file_selection_requested: Emitted to request file selection from user
    
    Attributes:
        frame_model: The FrameModel instance for processing frames
        camera_thread: Thread for camera capture
        network_thread: Thread for network video streaming
        video_thread: Currently active video thread (camera or network)
        playing: Whether video is currently playing
        if_jetson: Whether in Jetson mode
        frame_width: Width of video frames
        frame_height: Height of video frames
        last_video_source: Last loaded video source (for resume functionality)
        jetson_source_address: IP address for Jetson streaming
        jetson_source_port: Port for Jetson streaming
    """

    # Mode control signals
    thread_activate: Signal = Signal()

    # Playback state signals
    playback_state_changed: Signal = Signal(bool)
    video_started: Signal = Signal()
    video_cannot_resume: Signal = Signal()

    # Communication signals
    status_message: Signal = Signal(str)
    info_occurred: Signal = Signal(str, str)  # (title, message)

    # Request signals - asking for user input
    camera_selection_requested: Signal = Signal()
    file_selection_requested: Signal = Signal()

    def __init__(
        self,
        frame_model: FrameModel,
        camera_thread: CameraThread,
        network_thread: NetworkThread,
        video_thread: Union[NetworkThread, CameraThread]
    ) -> None:
        """Initialize the VideoHandler.
        
        Args:
            frame_model: The FrameModel instance for processing frames
            camera_thread: Thread for camera capture
            network_thread: Thread for network video streaming
            video_thread: Initially active video thread
        """
        super().__init__()
        self.frame_model: FrameModel = frame_model
        self.camera_thread: CameraThread = camera_thread
        self.network_thread: NetworkThread = network_thread
        self.video_thread: Union[NetworkThread, CameraThread] = video_thread
        
        # Playback state variables
        self.playing: bool = False
        self.if_jetson: bool = False
        self.frame_width: int = 0
        self.frame_height: int = 0
        self.last_video_source: Optional[Union[str, int]] = None

        # Jetson streaming configuration
        self.jetson_source_address: str = "0.0.0.0"
        self.jetson_source_port: int = 5001

    def handle_video_import(self, import_mode: str) -> None:
        """Handle video import request by emitting appropriate signal.
        
        This method does not directly open dialogs. Instead, it emits signals
        that the GUI layer should connect to for displaying dialogs.
        
        Args:
            import_mode: Either 'webcam' or 'file'
        """
        if import_mode == "webcam":
            self.camera_selection_requested.emit()
        elif import_mode == "file":
            self.file_selection_requested.emit()

    def load_video_file(self, file_path: str) -> None:
        """Load and start playback of a video file.
        
        Args:
            file_path: Absolute path to the video file to load
        """
        if not file_path:  # User cancelled
            return
            
        self.last_video_source = file_path
        
        if self.camera_thread.is_running():
            self.camera_thread.reset()
        
        if self.camera_thread.start_capture(file_path):
            self.frame_width, self.frame_height = (
                self.camera_thread.get_frame_dimensions()
            )
            self.playing = True
            self.playback_state_changed.emit(True)
            self.if_jetson = False
            self.thread_activate.emit()
        else:
            self.info_occurred.emit("Error", "Could not open the video file!")
   
    def load_camera(self, camera_index: int) -> None:
        """Load and start capture from a camera device.
        
        Args:
            camera_index: The camera device index (0, 1, 2, etc.)
        """
        if self.camera_thread.is_running():
            self.camera_thread.reset()
        
        if self.camera_thread.start_capture(camera_index):
            self.frame_width, self.frame_height = (
                self.camera_thread.get_frame_dimensions()
            )
            self.playing = True
            self.playback_state_changed.emit(True)
            self.thread_activate.emit()
        else:
            self.info_occurred.emit("Error", "Could not open the selected camera!")
    
    def update_video_thread(self, video_thread: Union[NetworkThread, CameraThread]) -> None:
        """Update the active video thread.
        
        Args:
            video_thread: The new video thread to use
        """
        self.video_thread = video_thread

    def _pause_play(self) -> None:
        """Toggle between playing and pausing the video.
        
        This method handles three scenarios:
        1. Pausing: If playing, pause the video thread
        2. Resume from pause: If paused, resume the video thread
        3. Restart: If stopped, restart from last video source
        """
        if not self.video_thread.is_running() and not self.playing:
            self.info_occurred.emit("Warning", "No video source loaded!")
            return

        if self.playing:
            # Pause the video using the thread's pause method
            # This keeps the video source open but stops emitting frames
            self.video_thread.pause()
            self.playing = False
            self.playback_state_changed.emit(False)

        else:
            # If the thread is running but paused, just resume it
            if self.video_thread.is_running() and self.video_thread.is_paused():
                self.video_thread.resume()
                self.playing = True
                self.playback_state_changed.emit(True)

            # If the thread is not running, we need to restart it
            elif hasattr(self, "last_video_source") and self.last_video_source is not None:
                if self.if_jetson and isinstance(self.video_thread, NetworkThread):
                    self.video_thread.start_network_capture(
                        self.jetson_source_address, self.jetson_source_port
                    )
                elif not self.if_jetson and isinstance(self.video_thread, CameraThread):
                    self.video_thread.start_capture(self.last_video_source)
                self.playing = True
                self.video_started.emit()
            else:
                self.video_cannot_resume.emit()
                return

    def reset(self) -> None:
        """Reset the VideoHandler to its initial state.
        
        This method cleans up all resources, stops any running threads,
        and resets all state variables to their initial values.
        Useful when starting a new mission or cleaning up.
        
        Note:
            Jetson configuration (address and port) is preserved as it represents
            user configuration rather than runtime state.
        """
        logger.info("Video handler: Resetting VideoHandler...")
        
        # Reset all video threads (reset() handles stopping internally)
        if hasattr(self, 'camera_thread') and self.camera_thread:
            self.camera_thread.reset()
            logger.debug("Video handler: Camera thread reset")
        
        if hasattr(self, 'network_thread') and self.network_thread:
            self.network_thread.reset()
            logger.debug("Video handler: Network thread reset")
        
        if hasattr(self, 'video_thread') and self.video_thread:
            self.video_thread.reset()
            logger.debug("Video thread reset")
        
        # Reset all state variables to initial values
        self.playing = False
        self.if_jetson = False
        self.frame_width = 0
        self.frame_height = 0
        self.last_video_source = None
        
        # Keep jetson settings (they are configuration, not state)
        # self.jetson_source_address = "0.0.0.0"
        # self.jetson_source_port = 5001
        
        logger.info("Video handler: VideoHandler reset complete")
