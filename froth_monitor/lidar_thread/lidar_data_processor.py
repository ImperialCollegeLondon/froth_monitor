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

    def __init__(self, gui, event_handler):
        """
        Initialize the LiDAR data processor.
        
        Args:
            event_handler: Reference to the main event handler
        """
        self.gui = gui
        self.event_handler = event_handler
        
        # Data storage
        self.current_reading = None
        self.current_timestamp = None
        self.reading_history = []  # List of (timestamp, distance) tuples
        self.reading_buffer = []   # Buffer for 1-second averaging
        self.reading_history_av1s = []
        self.reading_history_av1s_only_v = []  # 1-second averaged readings
        
        # Statistics
        self.total_readings = 0
        self.min_distance = float('inf')
        self.max_distance = float('-inf')
        self.avg_distance = 0.0
        
        # GUI update timer
        # self.gui_update_timer = QTimer()
        # self.gui_update_timer.timeout.connect(self.update_gui)
        # self.gui_update_timer.start(100)  # Update GUI every 100ms
        
        # Network mode flag - True when receiving LiDAR data via network thread
        self.network_mode = False
        
        logger.info("LiDAR data processor initialized")

    def set_network_mode(self, enabled: bool):
        """
        Set whether LiDAR data is received via network thread or serial connection.
        
        Args:
            enabled (bool): True for network mode, False for serial mode
        """
        self.network_mode = enabled
        if enabled:
            logger.info("LiDAR data processor switched to network mode")
        else:
            logger.info("LiDAR data processor switched to serial mode")

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
            distance_mm = lidar_data.get('lidar_reading', 0.0)
            timestamp = lidar_data.get('lidar_timestamp', datetime.now())

            # Update current readings
            self.current_lidar_reading = distance_mm
            self.current_timestamp = timestamp

            # Add to historical data
            self.reading_history.append(distance_mm)

            # Update GUI periodically
            current_time = datetime.now()
            
            if_update = self._if_update()
            
            if if_update:
                self._update_gui()
                # # self._calculate_averages()
                self.last_update_time = current_time

        except Exception as e:
            print(f"Error processing LiDAR data: {e}")

    def _if_update(self) -> bool:

        try:
            timestamp_buffer = str(self.current_timestamp)[:8] if self.current_timestamp is not None else None

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
                self.reading_history_av1s.append([[0, average_fh, \
                    self.current_timestamp, time.time()]])
                self.reading_history_av1s_only_v.append(average_fh)

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
            self.event_handler.lidar_handler.update_fh_plot(self.reading_history_av1s_only_v)
            
        except Exception as e:
            print(f"Error updating GUI with LiDAR data: {e}")

    # # def _calculate_averages(self):
    #     """
    # #     Calculate running averages of LiDAR readings.
    #     """
    # #     try:
    # #         if len(self.lidar_reading_buffer) > 0:
                  # # Calculate current average
    # #             current_average = sum(self.lidar_reading_buffer) / len(self.lidar_reading_buffer)
                
    # #             # Add to 1-second average history
    # #             self.reading_history_av1s.append(current_average)
                
    # #             # Calculate velocity-related metrics if needed
    # #             if len(self.reading_history_av1s) > 1:
    # #                 velocity = (self.reading_history_av1s[-1] - 
    # #                            self.reading_history_av1s[-2]) / self.update_interval
    # #                 self.reading_history_av1s_only_v.append(velocity)

        # # except Exception as e:
        # #     print(f"Error calculating LiDAR averages: {e}")

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
        return self.reading_history.copy()

    def get_velocity_history(self) -> List[float]:
        """
        Get the history of calculated velocities.
        
        Returns:
            List[float]: List of velocity measurements
        """
        return self.reading_history_av1s_only_v.copy()

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
        self.reading_history.clear()
        self.reading_history_av1s.clear()
        self.reading_history_av1s_only_v.clear()
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
                    len(self.reading_history),
                    len(self.reading_history_av1s),
                    len(self.reading_history_av1s_only_v)
                )
                
                for i in range(max_len):
                    distance = self.reading_history[i] if i < len(self.reading_history) else ''
                    avg_distance = self.reading_history_av1s[i] if i < len(self.reading_history_av1s) else ''
                    velocity = self.reading_history_av1s_only_v[i] if i < len(self.reading_history_av1s_only_v) else ''
                    
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
        if not self.reading_history:
            return cast(dict, None)
        
        import statistics
        
        try:
            stats = {
                'count': len(self.reading_history),
                'current': self.current_lidar_reading,
                'average': statistics.mean(self.reading_history),
                'median': statistics.median(self.reading_history),
                'min': min(self.reading_history),
                'max': max(self.reading_history),
                'range': max(self.reading_history) - min(self.reading_history)
            }
            
            if len(self.reading_history) > 1:
                stats['std_dev'] = statistics.stdev(self.reading_history)
            else:
                stats['std_dev'] = 0.0
                
            return stats
            
        except Exception as e:
            print(f"Error calculating LiDAR statistics: {e}")
            return cast(dict, None)