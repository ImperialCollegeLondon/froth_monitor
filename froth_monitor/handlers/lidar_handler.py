import cv2
import sys
import os
import time
import queue
import threading
from typing import cast
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QDialog,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QDoubleSpinBox,
    QMessageBox,
    QTableWidget,
    QPushButton,
    QVBoxLayout,
)
from PySide6.QtCore import Qt, QRect, QObject, Signal, QTimer, QThread
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtGui import QIcon

# Import MainGUIWindow at the beginning
from froth_monitor.handlers.gui_window import MainGUIWindow

# Import FrameModel from fm_model module
from froth_monitor.processing.fm_model import FrameModel, ROI
from froth_monitor.processing.delta_filter import DeltaFilter
from froth_monitor.utils.performance_monitor import PerformanceMonitor

# Import the custom overlay widget
from froth_monitor.handlers.overlay_widget import OverlayWidget

# Import the camera and network threads
from froth_monitor.video_threads.camera_thread import CameraThread
from froth_monitor.video_threads.network_thread import NetworkThread
from froth_monitor.lidar_thread.lidar_thread import LidarThread
from froth_monitor.lidar_thread.lidar_data_processor import LidarDataProcessor
from froth_monitor.lidar_thread.lidar_control_dialog import LidarControlDialog
from froth_monitor.air_recovery.air_recovery_data_processor import AirRecoveryDataProcessor
from froth_monitor.handlers.realtime_export import RealtimeExporter

# Import the video recorder module
from froth_monitor.handlers.video_recorder import VideoRecorder
# from froth_monitor.event_handler import EventHandler
from froth_monitor.handlers.logger_config import get_logger

# Initialize logger for this module
logger = get_logger(__name__)


class LidarHandler:
    def __init__(self,
                lidar_thread: LidarThread,
                lidar_data_processor: LidarDataProcessor,
                gui: MainGUIWindow,
                event_handler):

        self.lidar_thread = lidar_thread
        self.gui = gui
        self.event_handler = event_handler
        self.lidar_data_processor = lidar_data_processor

    def start_lidar_capture(self, port: str = "COM3", baudrate: int = 115200):
        """Start LiDAR data capture."""
        try:
            success = self.lidar_thread.start_lidar_capture(port, baudrate)
            logger.info(f"""
            Try to start LiDAR capture on port {port} at {baudrate} baud.
            """)
            if success:
                logger.info(f"""
                Starting LiDAR capture on port {port} at {baudrate} baud.
                """)
                self.initialize_lidar_mode()
                return True
            else:
                QMessageBox.warning(
                    self.gui,
                    "LiDAR Error",
                    f"Failed to start LiDAR capture on {port}. Please check the connection."
                )
                return False
        except Exception as e:
            QMessageBox.critical(
                self.gui,
                "LiDAR Error",
                f"Error starting LiDAR: {str(e)}"
            )
            return False
    
    def stop_lidar_capture(self):
        """Stop LiDAR data capture."""
        try:
            self.lidar_thread.stop_lidar_capture()
            QMessageBox.information(
                self.gui,
                "LiDAR Stopped",
                "LiDAR capture stopped successfully"
            )
        except Exception as e:
            QMessageBox.warning(
                self.gui,
                "LiDAR Warning",
                f"Error stopping LiDAR: {str(e)}"
            )
    
    def pause_lidar_capture(self):
        """Pause LiDAR data capture."""
        self.lidar_thread.pause_lidar_capture()
    
    def resume_lidar_capture(self):
        """Resume LiDAR data capture."""
        self.lidar_thread.resume_lidar_capture()
    
    def set_lidar_offset(self, offset_mm: float):
        """Set LiDAR distance offset."""
        self.lidar_thread.set_distance_offset(offset_mm)
    
    def export_lidar_data(self, filename: str = cast(str, None)):
        """Export LiDAR data to CSV file."""
        if filename is cast(str, None):
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"lidar_data_{timestamp}.csv"
        
        try:
            success = self.lidar_thread.export_data(filename)
            if success:
                QMessageBox.information(
                    self.gui,
                    "Export Successful",
                    f"LiDAR data exported to {filename}"
                )
            else:
                QMessageBox.warning(
                    self.gui,
                    "Export Failed",
                    "Failed to export LiDAR data"
                )
            return success
        except Exception as e:
            QMessageBox.critical(
                self.gui,
                "Export Error",
                f"Error exporting LiDAR data: {str(e)}"
            )
            return False
    
    def get_lidar_statistics(self) -> dict:
        """Get LiDAR data statistics."""
        return self.lidar_data_processor.get_statistics()
    
    def clear_lidar_data(self):
        """Clear all LiDAR data."""
        self.lidar_thread.clear_data()
        self.lidar_data_processor.clear_data()
        QMessageBox.information(
            self.gui,
            "Data Cleared",
            "LiDAR data cleared successfully"
        )
    
    def open_lidar_control(self):
        """Open the LiDAR control dialog."""
        try:
            dialog = LidarControlDialog(self, self.gui)
            dialog.show()
        except Exception as e:
            QMessageBox.critical(
                self.gui,
                "Error",
                f"Failed to open LiDAR control dialog: {str(e)}"
            )

    def initialize_lidar_mode(self):
        self.gui._trigger_lidar_mode()
        self.lidar_data_processor.if_lidar = True
