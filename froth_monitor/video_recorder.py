"""Video Recorder Module for Froth Monitor Application.

This module defines the `VideoRecorder` class, which provides functionality for
recording video frames from the camera thread to a video file. It handles
initialization of the video writer, frame processing, and file management.
"""

import cv2
import os
import time
import numpy as np
from datetime import datetime
from typing import Optional, Tuple, cast
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
        self.frame_interval = 0.0  # Time interval between frames
        self.is_video_file = False  # Flag to indicate if recording from a video file or camera
        self.previous_frame = cast(np.ndarray, None)  # Store the previous frame for comparison

    def start_recording(self, directory: str, filename: str, 
    frame_width: int, frame_height: int, fps: float = 30.0,
    is_video_file: bool = False) -> bool:
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
        self.frame_interval = 1.0 / fps
        self.is_video_file = is_video_file

        # Create output directory if it doesn't exist
        if not os.path.exists(directory):
            try:
                os.makedirs(directory)
            except OSError as e:
                print(f"Error creating directory: {e}")
                return False

        # Generate output path with timestamp to avoid overwriting
        # timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.output_path = os.path.join(directory, f"{filename}.mp4")

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
        
        # Insert previous frames to keep the same pace of the live video feed
        # As the fps of a realtime camera might not be constant
        if self.frame_count > 0:
            # Check if it's time to record the next frame
            if not self.is_video_file:
                current_time = time.time()
                print("Live recording")
                if current_time - self.previous_frame_time > self.frame_interval:
                    num_interval = int((current_time - self.previous_frame_time) / self.frame_interval)
                    for _ in range(num_interval):
                        self.video_writer.write(self.previous_frame)
                        self.frame_count += 1

        # Ensure frame dimensions match what the writer expects
        if frame.shape[1] != self.frame_width or frame.shape[0] != self.frame_height:
            frame = cv2.resize(frame, (self.frame_width, self.frame_height))

        if not self.is_video_file:
            self.previous_frame = frame
            self.previous_frame_time = time.time()

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

        # Release video writer
        self.video_writer.release()
        self.video_writer = None
        self.is_recording = False

        # Print recording statistics
        print(f"Recording stopped: {self.output_path}")
        print(f"Frames recorded: {self.frame_count}")

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
    
    def reset(self) -> None:
        """
        Reset the video recorder to its initial state.
        """
        if self.is_recording:
            self.stop_recording()