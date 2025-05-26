"""Camera Thread Module for Froth Tracker Application.

This module defines the `CameraThread` class, which runs in a separate thread to capture
frames from a camera or video source and emits signals when new frames are available.
This enables an event-driven approach to frame processing instead of timer-based polling.
"""

import cv2
import threading
import time
import numpy as np
from PySide6.QtCore import QObject, Signal


class CameraThread(QObject):
    """
    A thread-based camera capture class that emits signals when new frames are available.

    This class runs a camera capture loop in a separate thread and emits a signal
    with the captured frame whenever a new frame is available. This enables an
    event-driven approach to frame processing instead of timer-based polling.

    Attributes:
        frame_available (Signal): Signal emitted when a new frame is available.
        video_capture: OpenCV VideoCapture object for video input.
        running (bool): Flag indicating if the capture thread is running.
        thread: Thread object for the capture loop.
    """

    # Signal to emit when a new frame is available
    frame_available = Signal(np.ndarray)

    def __init__(self):
        """
        Initialize the CameraThread with default values.
        """
        super().__init__()
        self.video_capture = None
        self.running = False
        self.paused = False
        self.thread_ = None
        self.is_video_file = False
        self.frame_delay = 0  # Time in seconds between frames
        self.video_source = (
            None  # Store the video source for pause/resume functionality
        )
        self.buffer_size = 0
        self.max_buffer = 5  # Allow 5 frames in buffer
        self.buffer_lock = threading.Lock()

        self.if_release = True

    def start_capture(self, video_source):
        """
        Start capturing frames from the specified video source.

        Args:
            video_source: Either a camera index (int) or a video file path (str).

        Returns:
            bool: True if capture started successfully, False otherwise.
        """
        # Store the video source for pause/resume functionality
        self.video_source = video_source

        # If already running, stop first
        if self.running:
            self.stop_capture()

        # Initialize video capture
        if isinstance(video_source, int):
            # For camera, use DirectShow backend on Windows
            self.video_capture = cv2.VideoCapture(video_source, cv2.CAP_DSHOW)
            self.is_video_file = False
        else:
            # For video files
            self.video_capture = cv2.VideoCapture(video_source)
            self.is_video_file = True

            # Calculate frame delay for video files based on FPS
            fps = self.get_fps()
            if fps > 0:
                self.frame_delay = 1.0 / fps
            else:
                # Default to 30 FPS if unable to determine
                self.frame_delay = 1.0 / 30.0

        # Check if video capture opened successfully
        if not self.video_capture.isOpened():
            return False

        # Start capture thread
        self.running = True
        self.thread_ = threading.Thread(target=self._capture_loop)
        self.thread_.daemon = True  # Thread will exit when main program exits
        self.thread_.start()

        return True

    def stop_capture(self):
        """
        Stop capturing frames and release resources.
        """
        self.running = False
        self.paused = False

        # Wait for thread to finish if it exists
        if self.thread_ and self.thread_.is_alive():
            self.thread_.join(timeout=1.0)  # Wait up to 1 second

        # Release video capture resources
        if self.video_capture:
            self.video_capture.release()
            self.video_capture = None

    def _capture_loop(self):
        """
        Main capture loop that runs in a separate thread.
        Continuously captures frames and emits signals when new frames are available.
        For video files, paces the frame emission according to the video's native frame rate.
        Supports pausing without releasing the video source.
        """
        last_frame_time = time.time()

        while self.running and self.video_capture and self.video_capture.isOpened():
            # If paused, just sleep a bit and continue the loop without capturing
            if self.paused:
                time.sleep(0.1)  # Sleep to avoid busy waiting
                continue

            # Capture frame
            ret, frame = self.video_capture.read()

            if not ret:
                # End of video or error reading frame
                self.running = False
                break

            # Skip frame if buffer is full
            # with self.buffer_lock:
            #     if self.buffer_size >= self.max_buffer:
            #         continue
            #     self.buffer_size += 1

            current_time = time.time()

            # For video files, control the frame rate
            if self.is_video_file:

                # Calculate time elapsed since last frame
                elapsed = current_time - last_frame_time
                # If we need to wait to maintain the correct frame rate
                if elapsed < self.frame_delay:
                    time.sleep(self.frame_delay - elapsed)
            else:
                # For live camera, just a small sleep to prevent maxing out CPU
                time.sleep(0.001)

            # Emit signal with the captured frame
            if self.if_release:
                self.frame_available.emit(frame)

            # Update last frame time
            last_frame_time = time.time()

    def is_running(self):
        """
        Check if the capture thread is running.

        Returns:
            bool: True if running, False otherwise.
        """
        return self.running

    def pause(self):
        """
        Pause frame capture without stopping the thread or releasing resources.
        """
        self.paused = True

    def resume(self):
        """
        Resume frame capture after pausing.
        """
        self.paused = False

    def is_paused(self):
        """
        Check if the capture is currently paused.

        Returns:
            bool: True if paused, False otherwise.
        """
        return self.paused

    def get_frame_dimensions(self):
        """
        Get the dimensions of the video frames being captured.

        Returns:
            tuple: (width, height) of the frames, or (0, 0) if not available.
        """
        if self.video_capture and self.video_capture.isOpened():
            width = int(self.video_capture.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(self.video_capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
            return (width, height)
        return (0, 0)

    def get_fps(self):
        """
        Get the frames per second rate of the video source.

        Returns:
            float: FPS rate, or 0.0 if not available.
        """
        if self.video_capture and self.video_capture.isOpened():
            return self.video_capture.get(cv2.CAP_PROP_FPS)
        return 0.0

    def release_buffer(self):
        """Decrement buffer counter when frame processing completes"""
        with self.buffer_lock:
            if self.buffer_size > 0:
                self.buffer_size -= 1

    def reset(self) -> None:
        """
        Reset the camera thread to its initial state.
        """
        self.stop_capture()