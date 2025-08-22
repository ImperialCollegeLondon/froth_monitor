"""Network Thread Module for Froth Tracker Application.

This module defines the `NetworkThread` class, which runs in a separate thread to receive
video frames and sensor data from a remote source over the network using DataReceiver
(high-level abstraction) instead of low-level VideoReceiver.
"""

import threading
import time
import numpy as np
from PySide6.QtCore import QObject, Signal
from froth_monitor.handlers.data_receiver import DataReceiver
from froth_monitor.api_jetson.commands import CommandPriority

from froth_monitor.handlers.logger_config import get_logger

# Initialize logger for this module
logger = get_logger(__name__)


class NetworkThread(QObject):
    """
    A thread-based network receiver class that uses DataReceiver for high-level communication.

    This class runs a network receiver loop in a separate thread using DataReceiver
    (similar to testbench) and emits signals with the received frame and sensor data
    whenever new data is available.

    Attributes:
        frame_available (Signal): Signal emitted when a new frame is available.
        sensor_data_available (Signal): Signal emitted when new sensor data is available.
        lidar_data_available (Signal): Signal emitted when new LiDAR data is available.
        data_available (Signal): Combined signal for both frame and sensor data.
        connection_status_changed (Signal): Signal for connection status changes.
        command_sent (Signal): Signal when command is sent successfully.
        running (bool): Flag indicating if the receiver thread is running.
        thread: Thread object for the receiver loop.
    """

    # Signals to emit when new data is available
    frame_available = Signal(np.ndarray)
    sensor_data_available = Signal(dict)  # For LIDAR and other sensor data
    lidar_data_available = Signal(dict)  # Dedicated LiDAR signal
    data_available = Signal(
        dict, np.ndarray
    )  # Combined signal for both frame and sensor data

    # Signals for communication status
    connection_status_changed = Signal(bool, str)  # connected, status_message
    command_sent = Signal(dict)  # Signal when command is sent successfully
    command_send_failed = Signal(str)  # Signal when command sending fails

    def __init__(self):
        """
        Initialize the NetworkThread with default values.
        """
        super().__init__()
        self.data_receiver = None
        self.running = False
        self.paused = False
        self.thread_ = None
        self.network_address = None
        self.network_port = None
        self.request_timeout = None
        self.buffer_size = 0
        self.max_buffer = 5  # Allow 5 frames in buffer
        self.buffer_lock = threading.Lock()
        self.if_release = True

        # Connection status
        self.is_connected = False

    def start_network_capture(
        self, address="0.0.0.0", port=5001, request_timeout=3600, verbose_level=1
    ):
        """
        Start receiving frames and sensor data from the specified network source using DataReceiver.

        Args:
            address (str): Network address to listen on (default: "0.0.0.0")
            port (int): Network port to listen on (default: 5001)
            request_timeout (int): Request timeout in seconds (default: 3600)
            verbose_level (int): Verbosity level for the receiver (default: 1)

        Returns:
            bool: True if network capture started successfully, False otherwise.
        """
        # Store network configuration
        self.network_address = address
        self.network_port = port
        self.request_timeout = request_timeout

        # If already running, stop first
        if self.running:
            self.stop_capture()

        try:
            # Initialize DataReceiver (high-level abstraction)
            self.data_receiver = DataReceiver(
                addr=address,
                port=port,
                request_timeout=request_timeout,
                verbose_level=verbose_level,
            )

            # Check if connection was successful
            if self.data_receiver.jetson_ip and self.data_receiver.agreed_port:
                self.is_connected = True
                connection_msg = f"Connected to Jetson at {self.data_receiver.jetson_ip}:{self.data_receiver.agreed_port}"
                self.connection_status_changed.emit(True, connection_msg)

                # Start receiver thread
                self.running = True
                self.thread_ = threading.Thread(target=self._receiver_loop)
                self.thread_.daemon = True  # Thread will exit when main program exits
                self.thread_.start()
                logger.info("Network capture started successfully")

                return True
            else:
                self.is_connected = False
                self.connection_status_changed.emit(
                    False, "Failed to connect to Jetson"
                )
                logger.info("Failed to connect to Jetson")
                return False

        except Exception as e:
            print(f"Failed to start network capture: {e}")
            self.is_connected = False
            self.connection_status_changed.emit(False, f"Error: {str(e)}")
            return False

    def get_connection_status(self):
        """
        Get the current connection status.

        Returns:
            bool: True if connected, False otherwise
        """
        return self.is_connected

    def get_jetson_info(self):
        """
        Get information about the connected Jetson.

        Returns:
            tuple: (jetson_ip, agreed_port) or (None, None) if not connected
        """
        if self.data_receiver:
            return (self.data_receiver.jetson_ip, self.data_receiver.agreed_port)
        return (None, None)

    def stop_capture(self):
        """
        Stop receiving data and release resources.
        """
        self.running = False
        self.paused = False
        self.is_connected = False
        self.connection_status_changed.emit(False, "Disconnected")

        # Wait for thread to finish if it exists
        if self.thread_ and self.thread_.is_alive():
            self.thread_.join(timeout=1.0)  # Wait up to 1 second

        # Release DataReceiver resources
        if self.data_receiver:
            self.data_receiver.close()
            self.data_receiver = None

    def _receiver_loop(self):
        """
        Main receiver loop that runs in a separate thread.
        Uses DataReceiver.get_data() generator similar to testbench.
        """
        consecutive_none_frames = 0
        max_consecutive_none_frames = 59999990  # Allow up to 50 consecutive None frames before warning
        initial_connection_grace_period = 100  # Extra tolerance during initial connection
        total_frames_received = 0
        
        try:
            # Use DataReceiver's generator approach like testbench
            if self.data_receiver is None:
                raise RuntimeError("Data receiver not initialized")
                
            logger.info("Starting network receiver loop")
            
            for data in self.data_receiver.get_data():
                if not self.running:
                    break

                # If paused, just continue the loop without emitting signals
                if self.paused:
                    time.sleep(0.1)
                    continue

                # Handle None or invalid data gracefully
                if data is None:
                    consecutive_none_frames += 1
                    if consecutive_none_frames > max_consecutive_none_frames:
                        # During initial connection, be more tolerant
                        threshold = initial_connection_grace_period if total_frames_received < 10 else max_consecutive_none_frames
                        if consecutive_none_frames > threshold:
                            logger.warning(f"Received {consecutive_none_frames} consecutive None data packets")
                            # Don't break the loop, just continue - Jetson might recover
                    continue

                # Extract data components with additional validation
                frame = data.get("frame") if isinstance(data, dict) else None
                
                # Handle None frame (common during Jetson startup)
                if frame is None:
                    consecutive_none_frames += 1
                    # During initial connection, this is expected behavior
                    if total_frames_received < 10:
                        logger.debug(f"Received None frame during initial connection (frame #{total_frames_received})")
                    elif consecutive_none_frames > max_consecutive_none_frames:
                        logger.warning(f"Received {consecutive_none_frames} consecutive None frames")
                    continue
                
                # Reset consecutive None counter on successful frame
                if consecutive_none_frames > 0:
                    logger.info(f"Connection recovered after {consecutive_none_frames} None frames")
                    consecutive_none_frames = 0
                
                total_frames_received += 1
                
                # Extract server data safely
                server_data = {
                    "camera_timestamp": data.get("camera_timestamp"),
                    "lidar_reading": data.get("lidar_reading"),
                    "lidar_timestamp": data.get("lidar_timestamp"),
                }

                # Emit signals with the received data
                if self.if_release:
                    # Only emit frame signal if we have a valid frame
                    if frame is not None:
                        self.frame_available.emit(frame)
                        
                        # Log successful frame reception (only for first few frames)
                        if total_frames_received <= 5:
                            logger.info(f"Successfully received frame #{total_frames_received}")

                    if server_data and any(server_data.values()):
                        self.sensor_data_available.emit(server_data)

                        # Emit dedicated LiDAR signal if LiDAR data is present
                        if (
                            server_data.get("lidar_reading") is not None
                            or server_data.get("lidar_timestamp") is not None
                        ):
                            lidar_data = {
                                "lidar_reading": server_data.get("lidar_reading"),
                                "lidar_timestamp": server_data.get("lidar_timestamp"),
                            }
                            self.lidar_data_available.emit(lidar_data)

                    # Combined signal for convenience (only emit if we have valid frame)
                    if frame is not None:
                        self.data_available.emit(server_data, frame)

        except Exception as e:
            logger.error(f"Error in network receiver loop: {e}")
            print(f"Error in network receiver loop: {e}")
            self.command_send_failed.emit(str(e))
        finally:
            # Clean up when loop exits
            logger.info(f"Network receiver loop ended. Total frames received: {total_frames_received}")
            if self.data_receiver:
                self.data_receiver.close()
                self.is_connected = False
                self.connection_status_changed.emit(False, "Connection closed")

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

    def get_frame_dimensions(self):
        return (1280, 720)

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

    # =================================================================
    # COMMAND SENDING METHODS (using DataReceiver)
    # =================================================================

    def send_legacy_data(self, data):
        """
        Send legacy data to Jetson (backward compatibility).

        Args:
            data (dict): JSON-serializable dictionary to send

        Returns:
            bool: True if data was sent successfully, False otherwise
        """
        if not self.data_receiver:
            self.command_send_failed.emit("Not connected to Jetson")
            return False

        try:
            self.data_receiver.send_jeston_data(data)
            self.command_sent.emit(data)
            return True
        except Exception as e:
            self.command_send_failed.emit(str(e))
            return False

    def send_command(self, command):
        """
        Send a structured command to Jetson.

        Args:
            command: Command object to send

        Returns:
            bool: True if command was sent successfully, False otherwise
        """
        if not self.data_receiver:
            self.command_send_failed.emit("Not connected to Jetson")
            return False

        try:
            self.data_receiver.send_command(command)
            self.command_sent.emit(command.to_dict())
            return True
        except Exception as e:
            self.command_send_failed.emit(str(e))
            return False

    def send_commands(self, commands):
        """
        Send multiple structured commands to Jetson.

        Args:
            commands: List of Command objects to send

        Returns:
            bool: True if all commands were sent successfully, False otherwise
        """
        if not self.data_receiver:
            self.command_send_failed.emit("Not connected to Jetson")
            return False

        try:
            self.data_receiver.send_commands(commands)
            for command in commands:
                self.command_sent.emit(command.to_dict())
            return True
        except Exception as e:
            self.command_send_failed.emit(str(e))
            return False

    def get_command_list(self):
        """
        Get the command list instance for creating structured commands.

        Returns:
            CommandList: The command list instance, or None if not connected
        """
        if self.data_receiver:
            return self.data_receiver.get_command_list()
        return None

    # =================================================================
    # CONVENIENCE COMMAND METHODS
    # =================================================================

    def send_roi_command(self, x, y, width, height, priority=CommandPriority.NORMAL):
        """
        Send ROI (Region of Interest) command to Jetson.

        Args:
            x (int): X coordinate of ROI
            y (int): Y coordinate of ROI
            width (int): Width of ROI
            height (int): Height of ROI
            priority: Command priority
        """
        cmd_list = self.get_command_list()
        if cmd_list:
            command = cmd_list.create_roi_command(
                x, y, width, height, priority=priority
            )
            return self.send_command(command)
        return False

    def send_camera_adjustment_command(
        self, brightness=None, contrast=None, priority=CommandPriority.NORMAL
    ):
        """
        Send camera adjustment command to Jetson.

        Args:
            brightness (float): Brightness value (0.0-1.0)
            contrast (float): Contrast value (0.0-2.0)
            priority: Command priority
        """
        cmd_list = self.get_command_list()
        if cmd_list:
            command = cmd_list.create_camera_adjustment_command(
                brightness=brightness, contrast=contrast, priority=priority
            )
            return self.send_command(command)
        return False

    def send_lidar_calibration_command(
        self, offset, sampling_rate=None, priority=CommandPriority.NORMAL
    ):
        """
        Send LiDAR calibration command to Jetson.

        Args:
            offset (float): LiDAR offset value
            sampling_rate (int): Sampling rate
            priority: Command priority
        """
        cmd_list = self.get_command_list()
        if cmd_list:
            command = cmd_list.create_lidar_calibration_command(
                offset, sampling_rate, priority=priority
            )
            return self.send_command(command)
        return False

    def send_algorithm_config_command(
        self, algorithm_name, config_params, priority=CommandPriority.NORMAL
    ):
        """
        Send algorithm configuration command to Jetson.

        Args:
            algorithm_name (str): Name of the algorithm
            config_params (dict): Configuration parameters
            priority: Command priority
        """
        cmd_list = self.get_command_list()
        if cmd_list:
            command = cmd_list.create_algorithm_config_command(
                algorithm_name, config_params, priority=priority
            )
            return self.send_command(command)
        return False

    def send_system_status_command(self, priority=CommandPriority.NORMAL):
        """
        Send system status request command to Jetson.

        Args:
            priority: Command priority
        """
        cmd_list = self.get_command_list()
        if cmd_list:
            command = cmd_list.create_system_status_command(priority=priority)
            return self.send_command(command)
        return False

    def send_heartbeat_command(
        self, client_id="network_thread", priority=CommandPriority.LOW
    ):
        """
        Send heartbeat command to Jetson.

        Args:
            client_id (str): Client identifier
            priority: Command priority
        """
        cmd_list = self.get_command_list()
        if cmd_list:
            command = cmd_list.create_heartbeat_command(client_id, priority=priority)
            return self.send_command(command)
        return False
