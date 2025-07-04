"""LiDAR Thread Module for Froth Monitor Application.

This module defines the `LidarThread` class, which runs in a separate thread to read
LiDAR sensor data from a serial port and emits signals when new data is available.
This enables integration of LiDAR distance measurements into the froth monitoring system.
"""

import serial
import threading
import time
from datetime import datetime
from typing import Optional
import numpy as np
from PySide6.QtCore import QObject, Signal


class LidarThread(QObject):
    """
    A thread-based LiDAR reader class that emits signals when new distance measurements are available.

    This class runs a serial communication loop in a separate thread and emits signals
    with the received distance data whenever new measurements are available. This enables an
    event-driven approach to LiDAR data processing similar to the CameraThread and NetworkThread.

    Attributes:
        data_available (Signal): Signal emitted when new LiDAR data is available.
        running (bool): Flag indicating if the LiDAR thread is running.
        paused (bool): Flag indicating if the LiDAR thread is paused.
        thread: Thread object for the LiDAR reading loop.
    """

    # Signal to emit when new LiDAR data is available
    data_available = Signal(dict)  # Emits dict with timestamp and distance

    def __init__(self):
        """
        Initialize the LidarThread with default values.
        """
        super().__init__()
        self.serial_connection: Optional[serial.Serial] = None
        self.running = False
        self.paused = False
        self.thread_: Optional[threading.Thread] = None
        
        # LiDAR configuration
        self.port = "COM3"  # Default port
        self.baudrate = 115200
        self.timeout = 1.0
        
        # Data storage
        self.full_timestamps = []
        self.full_distances = []
        
        # Offset for distance measurements (in mm)
        self.distance_offset = 0.0

    def start_lidar_capture(self, port: str = "COM3", baudrate: int = 115200, timeout: float = 1.0) -> bool:
        """
        Start reading LiDAR data from the specified serial port.

        Args:
            port (str): Serial port to connect to (default: "COM3")
            baudrate (int): Baud rate for serial communication (default: 115200)
            timeout (float): Timeout for serial operations (default: 1.0)

        Returns:
            bool: True if LiDAR capture started successfully, False otherwise.
        """
        # Store LiDAR configuration
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout

        # If already running, stop first
        if self.running:
            self.stop_lidar_capture()

        try:
            # Initialize serial connection
            self.serial_connection = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout
            )
            
            # Clear any existing data in the buffer
            # self.serial_connection.flushInput()
            self.serial_connection.reset_input_buffer()
            
            # Start the reading thread
            self.running = True
            self.paused = False
            self.thread_ = threading.Thread(target=self._lidar_loop, daemon=True)
            self.thread_.start()
            
            print(f"LiDAR capture started on {self.port}")
            return True
            
        except Exception as e:
            print(f"Failed to start LiDAR capture: {e}")
            self.serial_connection = None
            return False

    def _lidar_loop(self):
        """
        Main LiDAR reading loop that runs in a separate thread.
        Continuously reads distance measurements and emits signals when new data is available.
        Supports pausing without closing the serial connection.
        """
        while self.running and self.serial_connection:
            try:
                # If paused, just sleep a bit and continue the loop without reading
                if self.paused:
                    time.sleep(0.1)  # Sleep to avoid busy waiting
                    continue

                # Read data from serial port
                if self.serial_connection.in_waiting > 0:
                    # line = self.serial_connection.readline().decode('utf-8').strip()
                    line = self.serial_connection.readline().decode("ascii", errors="ignore").strip()
                    
                    if line:
                        # Parse LiDAR data (expecting format like "D=1.234m")
                        distance_mm = self._parse_lidar_data(line)
                        
                        if distance_mm is not None:
                            # Apply offset
                            distance_mm += self.distance_offset
                            
                            # Create timestamp
                            timestamp = datetime.now()
                            
                            # Store data
                            self.full_timestamps.append(timestamp)
                            self.full_distances.append(distance_mm)
                            
                            # Prepare data dictionary
                            lidar_data = {
                                'timestamp': timestamp,
                                'distance_mm': distance_mm,
                                'distance_mm_inverted': -distance_mm,  # For compatibility
                                'formatted_timestamp': timestamp.strftime("%Y/%m/%d %H:%M:%S.%f")[:-3]
                            }
                            
                            # Emit signal with new data
                            self.data_available.emit(lidar_data)
                else:
                    # No data available, sleep briefly
                    time.sleep(0.01)
                    
            except Exception as e:
                print(f"Error in LiDAR reading loop: {e}")
                time.sleep(0.1)  # Sleep on error to avoid busy loop

    def _parse_lidar_data(self, line: str) -> Optional[float]:
        """
        Parse LiDAR data from a line of text.
        
        Expected format: "D=X.XXXm" where X.XXX is the distance in meters.
        
        Args:
            line (str): Raw line from LiDAR sensor
            
        Returns:
            Optional[float]: Distance in millimeters, or None if parsing failed
        """
        try:
            # Look for pattern "D=X.XXXm"
            if line.startswith('D=') and line.endswith('m'):
                # Extract the numeric part
                distance_str = line[2:-1]  # Remove "D=" and "m"
                distance_m = float(distance_str)
                # Convert to millimeters
                distance_mm = distance_m * 1000.0
                return distance_mm

        except (ValueError, IndexError):
            pass
        
        return None

    def pause_lidar_capture(self):
        """
        Pause LiDAR data reading without closing the serial connection.
        """
        if self.running:
            self.paused = True
            print("LiDAR capture paused")

    def resume_lidar_capture(self):
        """
        Resume LiDAR data reading.
        """
        if self.running:
            self.paused = False
            print("LiDAR capture resumed")

    def stop_lidar_capture(self):
        """
        Stop LiDAR data reading and close the serial connection.
        """
        if self.running:
            self.running = False
            self.paused = False
            
            # Wait for thread to finish
            if self.thread_ and self.thread_.is_alive():
                self.thread_.join(timeout=2.0)
            
            # Close serial connection
            if self.serial_connection:
                try:
                    self.serial_connection.close()
                except Exception as e:
                    print(f"Error closing serial connection: {e}")
                finally:
                    self.serial_connection = None
            
            print("LiDAR capture stopped")

    def is_running(self) -> bool:
        """
        Check if the LiDAR thread is currently running.
        
        Returns:
            bool: True if running, False otherwise.
        """
        return self.running and not self.paused

    def set_distance_offset(self, offset_mm: float):
        """
        Set the distance offset for LiDAR measurements.
        
        Args:
            offset_mm (float): Offset in millimeters to add to all measurements
        """
        self.distance_offset = offset_mm
        print(f"LiDAR distance offset set to {offset_mm} mm")

    def get_latest_data(self) -> Optional[dict]:
        """
        Get the latest LiDAR measurement.
        
        Returns:
            Optional[dict]: Latest measurement data or None if no data available
        """
        if self.full_timestamps and self.full_distances:
            latest_timestamp = self.full_timestamps[-1]
            latest_distance = self.full_distances[-1]
            
            return {
                'timestamp': latest_timestamp,
                'distance_mm': latest_distance,
                'distance_mm_inverted': -latest_distance,
                'formatted_timestamp': latest_timestamp.strftime("%Y/%m/%d %H:%M:%S.%f")[:-3]
            }
        
        return None

    def export_data(self, filename: str) -> bool:
        """
        Export collected LiDAR data to a CSV file.
        
        Args:
            filename (str): Path to the output CSV file
            
        Returns:
            bool: True if export was successful, False otherwise
        """
        try:
            import csv
            
            with open(filename, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                
                # Write header
                writer.writerow(['timestamp', 'distance_mm_inverted'])
                
                # Write data
                for timestamp, distance in zip(self.full_timestamps, self.full_distances):
                    formatted_timestamp = timestamp.strftime("%Y/%m/%d %H:%M:%S.%f")[:-3]
                    writer.writerow([formatted_timestamp, -distance])  # Inverted for compatibility
            
            print(f"LiDAR data exported to {filename}")
            return True
            
        except Exception as e:
            print(f"Failed to export LiDAR data: {e}")
            return False

    def clear_data(self):
        """
        Clear all stored LiDAR data.
        """
        self.full_timestamps.clear()
        self.full_distances.clear()
        print("LiDAR data cleared")