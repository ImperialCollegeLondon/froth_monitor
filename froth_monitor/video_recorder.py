"""Video Recorder Module for Froth Monitor Application.

This module defines the `VideoRecorder` class, which provides functionality for
recording video frames from the camera thread to a video file. It handles
initialization of the video writer, frame processing, and file management.
"""

import cv2
import os
import time
from datetime import datetime
from typing import Optional, Tuple
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QMessageBox


class VideoRecorder(QObject):
    """
    Video recorder class for capturing and saving video frames.

    This class handles the recording of video frames from the camera thread
    to a video file. It manages the video writer initialization, frame processing,
    and file management.

    Attributes:
        recording_started (Signal): Signal emitted when recording starts.
        recording_stopped (Signal): Signal emitted when recording stops.
        is_recording (bool): Flag indicating if recording is currently active.
        video_writer: OpenCV VideoWriter object for video output.
        output_path (str): Path where the video file will be saved.
        frame_count (int): Counter for the number of frames recorded.
        start_time (float): Timestamp when recording started.
        frame_width (int): Width of the video frame.
        frame_height (int): Height of the video frame.
        fps (float): Frames per second for the output video.
    """

    # Signals for recording state changes
    recording_started = Signal(str)  # Emits the output path when recording starts
    recording_stopped = Signal(str, int)  # Emits the output path and frame count when recording stops

    def __init__(self):
        """
        Initialize the VideoRecorder with default values.
        """
        super().__init__()
        self.is_recording = False
        self.video_writer = None
        self.output_path = ""
        self.frame_count = 0
        self.start_time = 0.0
        self.frame_width = 0
        self.frame_height = 0
        self.fps = 30.0  # Default FPS

    def start_recording(self, directory: str, filename: str, frame_width: int, frame_height: int, fps: float = 30.0) -> bool:
        """
        Start recording video frames to a file.

        Args:
            directory (str): Directory where the video file will be saved.
            filename (str): Base filename for the video file (without extension).
            frame_width (int): Width of the video frame.
            frame_height (int): Height of the video frame.
            fps (float, optional): Frames per second for the output video. Defaults to 30.0.

        Returns:
            bool: True if recording started successfully, False otherwise.
        """
        if self.is_recording:
            return False

        # Store frame dimensions and fps
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.fps = fps

        # Create output directory if it doesn't exist
        if not os.path.exists(directory):
            try:
                os.makedirs(directory)
            except OSError as e:
                print(f"Error creating directory: {e}")
                return False

        # Generate output path with timestamp to avoid overwriting
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.output_path = os.path.join(directory, f"{filename}_{timestamp}.mp4")

        # Initialize video writer
        # Use H.264 codec (XVID is more widely supported than mp4v)
        fourcc = cv2.VideoWriter.fourcc(*'XVID')
        self.video_writer = cv2.VideoWriter(self.output_path, fourcc, fps, (frame_width, frame_height))

        if not self.video_writer.isOpened():
            print("Failed to open video writer")
            return False

        # Reset counters
        self.frame_count = 0
        self.start_time = time.time()
        self.is_recording = True

        # Emit signal that recording has started
        self.recording_started.emit(self.output_path)
        return True

    def record_frame(self, frame) -> bool:
        """
        Record a single frame to the video file.

        Args:
            frame: The frame to record (OpenCV image format).

        Returns:
            bool: True if the frame was recorded successfully, False otherwise.
        """
        if not self.is_recording or self.video_writer is None:
            return False

        # Ensure frame dimensions match what the writer expects
        if frame.shape[1] != self.frame_width or frame.shape[0] != self.frame_height:
            frame = cv2.resize(frame, (self.frame_width, self.frame_height))

        # Write the frame
        self.video_writer.write(frame)
        self.frame_count += 1
        return True

    def stop_recording(self) -> Tuple[bool, str, int]:
        """
        Stop recording and release resources.

        Returns:
            Tuple[bool, str, int]: A tuple containing:
                - Success flag (True if stopped successfully)
                - Output path of the recorded video
                - Number of frames recorded
        """
        if not self.is_recording or self.video_writer is None:
            return False, "", 0

        # Calculate recording duration
        duration = time.time() - self.start_time
        actual_fps = self.frame_count / duration if duration > 0 else 0

        # Release video writer
        self.video_writer.release()
        self.video_writer = None
        self.is_recording = False

        # Print recording statistics
        print(f"Recording stopped: {self.output_path}")
        print(f"Frames recorded: {self.frame_count}")
        print(f"Duration: {duration:.2f} seconds")
        print(f"Actual FPS: {actual_fps:.2f}")

        # Emit signal that recording has stopped
        self.recording_stopped.emit(self.output_path, self.frame_count)
        return True, self.output_path, self.frame_count

    def is_active(self) -> bool:
        """
        Check if recording is currently active.

        Returns:
            bool: True if recording is active, False otherwise.
        """
        return self.is_recording

    def get_recording_info(self) -> Tuple[str, int, float]:
        """
        Get information about the current recording.

        Returns:
            Tuple[str, int, float]: A tuple containing:
                - Output path of the video
                - Number of frames recorded
                - Duration of recording in seconds
        """
        duration = time.time() - self.start_time if self.is_recording else 0.0
        return self.output_path, self.frame_count, duration