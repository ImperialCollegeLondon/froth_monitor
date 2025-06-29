"""Network Thread Module for Froth Tracker Application.

This module defines the `NetworkThread` class, which runs in a separate thread to receive
video frames and sensor data from a remote source over the network and emits signals
when new data is available. This enables integration with remote data sources.
"""

import cv2
import threading
import time
import numpy as np
from PySide6.QtCore import QObject, Signal
from froth_monitor.network.windows_receiver import (
    VideoReceiver,
)  # Adjust import path as needed


class NetworkThread(QObject):
    """
    A thread-based network receiver class that emits signals when new frames and sensor data are available.

    This class runs a network receiver loop in a separate thread and emits signals
    with the received frame and sensor data whenever new data is available. This enables an
    event-driven approach to remote data processing similar to the CameraThread.

    Attributes:
        frame_available (Signal): Signal emitted when a new frame is available.
        sensor_data_available (Signal): Signal emitted when new sensor data is available.
        running (bool): Flag indicating if the receiver thread is running.
        thread: Thread object for the receiver loop.
    """

    # Signals to emit when new data is available
    frame_available = Signal(np.ndarray)
    sensor_data_available = Signal(dict)  # For LIDAR and other sensor data
    data_available = Signal(
        dict, np.ndarray
    )  # Combined signal for both frame and sensor data

    def __init__(self):
        """
        Initialize the NetworkThread with default values.
        """
        super().__init__()
        self.video_receiver = None
        self.running = False
        self.paused = False
        self.thread_ = None
        self.network_address = None
        self.network_port = None
        self.buffer_size = 0
        self.max_buffer = 5  # Allow 5 frames in buffer
        self.buffer_lock = threading.Lock()
        self.if_release = True

    def start_network_capture(self, address="0.0.0.0", port=5001, verbose_level=1):
        """
        Start receiving frames and sensor data from the specified network source.

        Args:
            address (str): Network address to listen on (default: "0.0.0.0")
            port (int): Network port to listen on (default: 5001)
            verbose_level (int): Verbosity level for the receiver (default: 1)

        Returns:
            bool: True if network capture started successfully, False otherwise.
        """
        # Store network configuration
        self.network_address = address
        self.network_port = port

        # If already running, stop first
        if self.running:
            self.stop_capture()

        try:
            # Initialize network receiver
            self.video_receiver = VideoReceiver(
                address, port, verbose_level=verbose_level
            )

            # Start receiver thread
            self.running = True
            self.thread_ = threading.Thread(target=self._receiver_loop)
            self.thread_.daemon = True  # Thread will exit when main program exits
            self.thread_.start()

            return True

        except Exception as e:
            print(f"Failed to start network capture: {e}")
            return False

    def stop_capture(self):
        """
        Stop receiving data and release resources.
        """
        self.running = False
        self.paused = False

        # Wait for thread to finish if it exists
        if self.thread_ and self.thread_.is_alive():
            self.thread_.join(timeout=1.0)  # Wait up to 1 second

        # Release network receiver resources
        if self.video_receiver:
            self.video_receiver.close()
            self.video_receiver = None

    def _receiver_loop(self):
        """
        Main receiver loop that runs in a separate thread.
        Continuously receives frames and sensor data and emits signals when new data is available.
        Supports pausing without closing the network connection.
        """
        while self.running and self.video_receiver:
            try:
                # If paused, just sleep a bit and continue the loop without receiving
                if self.paused:
                    time.sleep(0.1)  # Sleep to avoid busy waiting
                    continue

                # Receive data from network
                result = self.video_receiver.recv()
                if result is None:
                    server_data, frame = None, None
                else:
                    server_data, frame = result

                if frame is None:
                    print("Frame is None")
                    # No data received or connection closed
                    time.sleep(0.01)  # Small delay to prevent busy waiting
                    continue

                # Convert frame from RGB to BGR (OpenCV standard)
                if frame is not None:
                    frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

                # # Skip frame if buffer is full (similar to CameraThread)
                # with self.buffer_lock:
                #     if self.buffer_size >= self.max_buffer:
                #         continue
                #     self.buffer_size += 1

                # Emit signals with the received data
                if self.if_release:

                    if frame is not None:
                        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                        self.frame_available.emit(frame)

                    if server_data:
                        self.sensor_data_available.emit(server_data)
                    # Combined signal for convenience
                    self.data_available.emit(server_data, frame)

                # Small delay to prevent maxing out CPU
                time.sleep(0.001)

            except Exception as e:
                print(f"Error in network receiver loop: {e}")
                time.sleep(0.1)  # Wait before retrying
                continue

        # Clean up when loop exits
        if self.video_receiver:
            self.video_receiver.close()

    def is_running(self):
        """
        Check if the receiver thread is running.

        Returns:
            bool: True if running, False otherwise.
        """
        return self.running

    def pause(self):
        """
        Pause data reception without stopping the thread or closing the connection.
        """
        self.paused = True

    def resume(self):
        """
        Resume data reception after pausing.
        """
        self.paused = False

    def is_paused(self):
        """
        Check if the receiver is currently paused.

        Returns:
            bool: True if paused, False otherwise.
        """
        return self.paused

    def get_network_info(self):
        """
        Get the network configuration being used.

        Returns:
            tuple: (address, port) of the network connection, or (None, None) if not connected.
        """
        if self.running:
            return (self.network_address, self.network_port)
        return (None, None)

    def release_buffer(self):
        """Decrement buffer counter when frame processing completes"""
        with self.buffer_lock:
            if self.buffer_size > 0:
                self.buffer_size -= 1

    def reset(self) -> None:
        """
        Reset the network thread to its initial state.
        """
        self.stop_capture()
