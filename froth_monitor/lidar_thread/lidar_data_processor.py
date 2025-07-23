"""LiDAR Data Processor Module for Froth Monitor Application.

This module defines the `LidarDataProcessor` class, which processes LiDAR sensor data
received from the LidarThread and integrates it with the froth monitoring system.
It handles data buffering, averaging, and GUI updates.
"""

from typing import cast, List
import time
from datetime import datetime
from PySide6.QtWidgets import QMessageBox
from froth_monitor.logger_config import get_logger

# Initialize logger for this module
logger = get_logger(__name__)

class LidarDataProcessor:
    """
    Processes LiDAR sensor data and integrates it with the froth monitoring system.
    
    This class handles LiDAR data received from the LidarThread, processes it for
    analysis, and updates the GUI with current readings and historical data.
    """

    def __init__(self, event_handler, lidar_thread):
        """
        Initialize the LiDAR data processor.
        
        Args:
            event_handler: The main event handler instance
            lidar_thread: The LidarThread instance providing data
        """
        self.event_handler = event_handler
        self.lidar_thread = lidar_thread
        self.gui = self.event_handler.gui

        # Current readings
        self.current_lidar_reading = 0.0
        self.current_timestamp: str = cast(str, None)

        # Historical data storage
        self.lidar_reading_history = []
        self.lidar_reading_history_av1s = []  # 1-second averages
        self.lidar_reading_history_av1s_only_v = []  # Velocity-only averages

        # Data buffering
        self.lidar_reading_buffer = []
        self.timestamp_buffer = cast(str, None)

        # Reference measurements
        self.lidar_reading_last_mark = 0.0
        self.lidar_reading_current_mark = 0.0

        # Processing parameters
        self.buffer_size = 10  # Number of readings to average
        self.update_interval = 1.0  # Seconds between GUI updates
        self.last_update_time = datetime.now()

    def process_lidar_data(self, lidar_data: dict):
        """
        Process new LiDAR data received from the LidarThread.

        This method is called whenever new LiDAR data is available from the thread.
        It processes the data, updates buffers, and refreshes the GUI.

        Args:
            lidar_data (dict): Dictionary containing LiDAR measurement data
        """
        # Check if video is playing (only process data when active)
        # if not self.event_handler.video_handler.playing:
        #     return

        try:
            # Extract data from the LiDAR measurement
            distance_mm = lidar_data.get('distance_mm', 0.0)
            timestamp = lidar_data.get('timestamp', datetime.now())
            formatted_timestamp = lidar_data.get('formatted_timestamp', '')

            # Update current readings
            self.current_lidar_reading = distance_mm
            self.current_timestamp = formatted_timestamp

            # Add to historical data
            self.lidar_reading_history.append(distance_mm)

            # Update GUI periodically
            current_time = datetime.now()
            
            if_update = self._if_update()
            
            if if_update:
                self._update_gui()
                self._calculate_averages()
                self.last_update_time = current_time

        except Exception as e:
            print(f"Error processing LiDAR data: {e}")

    def _if_update(self) -> bool:

        try:
            timestamp_buffer = self.current_timestamp[:8]

            if self.timestamp_buffer is None:
                self.timestamp_buffer = timestamp_buffer
                self.lidar_reading_buffer.append(self.current_lidar_reading)
                return False

            if timestamp_buffer == self.timestamp_buffer:
                self.lidar_reading_buffer.append(self.current_lidar_reading)
                return False

            else:
                self.timestamp_buffer = timestamp_buffer
                average_fh = sum(self.lidar_reading_buffer) / len(self.lidar_reading_buffer)
                self.lidar_reading_history_av1s.append([[0, average_fh, \
                    self.current_timestamp, time.time()]])
                self.lidar_reading_history_av1s_only_v.append(average_fh)

                self.lidar_reading_buffer = []

                return True

        except Exception as e:
            logger.error(f"Error calculating LiDAR averages: {e}")
            return False

    def _update_gui(self):
        """
        Update the GUI with current LiDAR readings.
        """
        try:
            # Update status bar with current reading
            if hasattr(self.gui, 'statusBar'):
                status_text = f"LiDAR: {self.current_lidar_reading:.1f} mm | Time: {self.current_timestamp}"
                self.gui.statusBar().showMessage(status_text)

            # Update any LiDAR-specific GUI elements if they exist
            # This can be extended based on GUI requirements
            self.event_handler.lidar_handler.update_fh_plot(self.lidar_reading_history_av1s_only_v)
            
        except Exception as e:
            print(f"Error updating GUI with LiDAR data: {e}")

    def _calculate_averages(self):
        """
        Calculate running averages of LiDAR readings.
        """
        try:
            if len(self.lidar_reading_buffer) > 0:
                # Calculate current average
                current_average = sum(self.lidar_reading_buffer) / len(self.lidar_reading_buffer)
                
                # Add to 1-second average history
                self.lidar_reading_history_av1s.append(current_average)
                
                # Calculate velocity-related metrics if needed
                if len(self.lidar_reading_history_av1s) > 1:
                    velocity = (self.lidar_reading_history_av1s[-1] - 
                               self.lidar_reading_history_av1s[-2]) / self.update_interval
                    self.lidar_reading_history_av1s_only_v.append(velocity)

        except Exception as e:
            print(f"Error calculating LiDAR averages: {e}")

    def get_current_reading(self) -> float:
        """
        Get the current LiDAR distance reading.
        
        Returns:
            float: Current distance in millimeters
        """
        return self.current_lidar_reading

    def get_average_reading(self) -> float:
        """
        Get the current averaged LiDAR reading.
        
        Returns:
            float: Averaged distance in millimeters
        """
        if len(self.lidar_reading_buffer) > 0:
            return sum(self.lidar_reading_buffer) / len(self.lidar_reading_buffer)
        return 0.0

    def get_reading_history(self) -> List[float]:
        """
        Get the complete history of LiDAR readings.
        
        Returns:
            List[float]: List of all distance measurements
        """
        return self.lidar_reading_history.copy()

    def get_velocity_history(self) -> List[float]:
        """
        Get the history of calculated velocities.
        
        Returns:
            List[float]: List of velocity measurements
        """
        return self.lidar_reading_history_av1s_only_v.copy()

    def set_reference_mark(self):
        """
        Set the current reading as a reference mark for comparison.
        """
        self.lidar_reading_last_mark = self.lidar_reading_current_mark
        self.lidar_reading_current_mark = self.current_lidar_reading
        print(f"LiDAR reference mark set: {self.lidar_reading_current_mark:.1f} mm")

    def get_distance_from_mark(self) -> float:
        """
        Get the distance change from the last reference mark.
        
        Returns:
            float: Distance change in millimeters
        """
        return self.current_lidar_reading - self.lidar_reading_current_mark

    def clear_data(self):
        """
        Clear all stored LiDAR data and reset buffers.
        """
        self.lidar_reading_history.clear()
        self.lidar_reading_history_av1s.clear()
        self.lidar_reading_history_av1s_only_v.clear()
        self.lidar_reading_buffer.clear()
        
        self.current_lidar_reading = 0.0
        self.current_timestamp = ""
        self.lidar_reading_last_mark = 0.0
        self.lidar_reading_current_mark = 0.0
        
        print("LiDAR data processor cleared")

    def export_processed_data(self, filename: str) -> bool:
        """
        Export processed LiDAR data to a file.
        
        Args:
            filename (str): Path to the output file
            
        Returns:
            bool: True if export was successful, False otherwise
        """
        try:
            import csv
            
            with open(filename, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                
                # Write headers
                writer.writerow([
                    'reading_index', 
                    'distance_mm', 
                    'average_distance_mm', 
                    'velocity_mm_per_s'
                ])
                
                # Write data
                max_len = max(
                    len(self.lidar_reading_history),
                    len(self.lidar_reading_history_av1s),
                    len(self.lidar_reading_history_av1s_only_v)
                )
                
                for i in range(max_len):
                    distance = self.lidar_reading_history[i] if i < len(self.lidar_reading_history) else ''
                    avg_distance = self.lidar_reading_history_av1s[i] if i < len(self.lidar_reading_history_av1s) else ''
                    velocity = self.lidar_reading_history_av1s_only_v[i] if i < len(self.lidar_reading_history_av1s_only_v) else ''
                    
                    writer.writerow([i, distance, avg_distance, velocity])
            
            print(f"Processed LiDAR data exported to {filename}")
            return True
            
        except Exception as e:
            print(f"Failed to export processed LiDAR data: {e}")
            return False

    def get_statistics(self) -> dict:
        """
        Get statistical information about the LiDAR data.
        
        Returns:
            dict: Dictionary containing statistical data
        """
        if not self.lidar_reading_history:
            return cast(dict, None)
        
        import statistics
        
        try:
            stats = {
                'count': len(self.lidar_reading_history),
                'current': self.current_lidar_reading,
                'average': statistics.mean(self.lidar_reading_history),
                'median': statistics.median(self.lidar_reading_history),
                'min': min(self.lidar_reading_history),
                'max': max(self.lidar_reading_history),
                'range': max(self.lidar_reading_history) - min(self.lidar_reading_history)
            }
            
            if len(self.lidar_reading_history) > 1:
                stats['std_dev'] = statistics.stdev(self.lidar_reading_history)
            else:
                stats['std_dev'] = 0.0
                
            return stats
            
        except Exception as e:
            print(f"Error calculating LiDAR statistics: {e}")
            return cast(dict, None)