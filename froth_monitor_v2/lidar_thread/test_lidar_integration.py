"""Test script for LiDAR integration in Froth Monitor.

This script demonstrates how to use the integrated LiDAR functionality
with the froth monitor application.
"""

import sys
import os
from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QLabel, QTextEdit
from PySide6.QtCore import QTimer

# Add the parent directory to the path to import froth_monitor modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from froth_monitor.lidar_thread.lidar_thread import LidarThread
from froth_monitor.lidar_thread.lidar_data_processor import LidarDataProcessor
from froth_monitor.lidar_thread.lidar_control_dialog import LidarControlDialog


class MockEventHandler:
    """Mock event handler for testing LiDAR functionality."""
    
    def __init__(self, gui):
        self.gui = gui
        self.lidar_thread = LidarThread()
        self.lidar_data_processor = LidarDataProcessor(self, self.lidar_thread)
        
        # Connect signals
        self.lidar_thread.data_available.connect(
            self.lidar_data_processor.process_lidar_data
        )
        
        # Mock video handler
        self.video_handler = MockVideoHandler()
    
    def start_lidar_capture(self, port="COM3", baudrate=115200):
        return self.lidar_thread.start_lidar_capture(port, baudrate)
    
    def stop_lidar_capture(self):
        self.lidar_thread.stop_lidar_capture()
    
    def pause_lidar_capture(self):
        self.lidar_thread.pause_lidar_capture()
    
    def resume_lidar_capture(self):
        self.lidar_thread.resume_lidar_capture()
    
    def set_lidar_offset(self, offset_mm):
        self.lidar_thread.set_distance_offset(offset_mm)
    
    def export_lidar_data(self, filename=None):
        return self.lidar_thread.export_data(filename or "test_lidar_data.csv")
    
    def get_lidar_statistics(self):
        return self.lidar_data_processor.get_statistics()
    
    def clear_lidar_data(self):
        self.lidar_thread.clear_data()
        self.lidar_data_processor.clear_data()


class MockVideoHandler:
    """Mock video handler for testing."""
    
    def __init__(self):
        self.playing = True  # Simulate video playing


class LidarTestWindow(QMainWindow):
    """Test window for LiDAR functionality."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LiDAR Integration Test")
        self.setGeometry(100, 100, 600, 500)
        
        # Create mock event handler
        self.event_handler = MockEventHandler(self)
        
        self.setup_ui()
        
        # Timer for updating display
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_display)
        self.update_timer.start(1000)  # Update every second
    
    def setup_ui(self):
        """Set up the user interface."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        
        # Title
        title_label = QLabel("LiDAR Integration Test")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; margin: 10px;")
        layout.addWidget(title_label)
        
        # Control buttons
        self.start_btn = QPushButton("Start LiDAR (COM3)")
        self.start_btn.clicked.connect(self.start_lidar)
        layout.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton("Stop LiDAR")
        self.stop_btn.clicked.connect(self.stop_lidar)
        layout.addWidget(self.stop_btn)
        
        self.control_btn = QPushButton("Open LiDAR Control Dialog")
        self.control_btn.clicked.connect(self.open_control_dialog)
        layout.addWidget(self.control_btn)
        
        self.export_btn = QPushButton("Export Data")
        self.export_btn.clicked.connect(self.export_data)
        layout.addWidget(self.export_btn)
        
        self.clear_btn = QPushButton("Clear Data")
        self.clear_btn.clicked.connect(self.clear_data)
        layout.addWidget(self.clear_btn)
        
        # Status display
        self.status_label = QLabel("Status: Ready")
        self.status_label.setStyleSheet("font-weight: bold; margin: 10px;")
        layout.addWidget(self.status_label)
        
        # Data display
        self.data_display = QTextEdit()
        self.data_display.setMaximumHeight(200)
        self.data_display.setReadOnly(True)
        layout.addWidget(self.data_display)
        
        # Instructions
        instructions = QLabel(
            "Instructions:\n"
            "1. Make sure you have a LiDAR device connected or use the dummy LiDAR simulator\n"
            "2. Click 'Start LiDAR' to begin data collection\n"
            "3. Use 'Open LiDAR Control Dialog' for advanced controls\n"
            "4. Export data when finished"
        )
        instructions.setStyleSheet("margin: 10px; padding: 10px; background-color: #f0f0f0;")
        layout.addWidget(instructions)
    
    def start_lidar(self):
        """Start LiDAR data collection."""
        success = self.event_handler.start_lidar_capture("COM3", 115200)
        if success:
            self.status_label.setText("Status: LiDAR Running")
            self.status_label.setStyleSheet("color: green; font-weight: bold; margin: 10px;")
        else:
            self.status_label.setText("Status: Failed to start LiDAR")
            self.status_label.setStyleSheet("color: red; font-weight: bold; margin: 10px;")
    
    def stop_lidar(self):
        """Stop LiDAR data collection."""
        self.event_handler.stop_lidar_capture()
        self.status_label.setText("Status: LiDAR Stopped")
        self.status_label.setStyleSheet("color: orange; font-weight: bold; margin: 10px;")
    
    def open_control_dialog(self):
        """Open the LiDAR control dialog."""
        try:
            dialog = LidarControlDialog(self.event_handler, self)
            dialog.show()
        except Exception as e:
            self.status_label.setText(f"Error: {str(e)}")
            self.status_label.setStyleSheet("color: red; font-weight: bold; margin: 10px;")
    
    def export_data(self):
        """Export LiDAR data."""
        success = self.event_handler.export_lidar_data("test_export.csv")
        if success:
            self.status_label.setText("Status: Data exported to test_export.csv")
        else:
            self.status_label.setText("Status: Export failed")
    
    def clear_data(self):
        """Clear LiDAR data."""
        self.event_handler.clear_lidar_data()
        self.status_label.setText("Status: Data cleared")
    
    def update_display(self):
        """Update the data display."""
        try:
            # Get current statistics
            stats = self.event_handler.get_lidar_statistics()
            current_reading = self.event_handler.lidar_data_processor.get_current_reading()
            
            if stats:
                display_text = f"""Current Reading: {current_reading:.1f} mm

Statistics:
Count: {stats.get('count', 0)}
Average: {stats.get('average', 0):.1f} mm
Min: {stats.get('min', 0):.1f} mm
Max: {stats.get('max', 0):.1f} mm
Range: {stats.get('range', 0):.1f} mm
Std Dev: {stats.get('std_dev', 0):.1f} mm"""
            else:
                display_text = f"Current Reading: {current_reading:.1f} mm\n\nNo statistical data available yet."
            
            self.data_display.setText(display_text)
            
        except Exception as e:
            self.data_display.setText(f"Error updating display: {str(e)}")
    
    def closeEvent(self, event):
        """Handle window close event."""
        # Stop LiDAR if running
        if self.event_handler.lidar_thread.running:
            self.event_handler.stop_lidar_capture()
        
        self.update_timer.stop()
        event.accept()


def main():
    """Main function to run the test application."""
    app = QApplication(sys.argv)
    
    # Set application style
    app.setStyle("Fusion")
    
    window = LidarTestWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()