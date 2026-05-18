"""LiDAR Control Dialog for Froth Monitor Application.

This module provides a GUI dialog for controlling LiDAR functionality,
including starting/stopping capture, configuring settings, and viewing data.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QSpinBox, QDoubleSpinBox,
    QComboBox, QTextEdit, QGroupBox, QFileDialog,
    QMessageBox
)
from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont
from froth_monitor.handlers.logger_config import get_logger

# Initialize logger for this module
logger = get_logger(__name__)

class LidarControlDialog(QDialog):
    """
    Dialog for controlling LiDAR functionality in the froth monitor application.
    
    Provides controls for:
    - Starting/stopping LiDAR capture
    - Configuring serial port settings
    - Setting distance offset
    - Viewing real-time data
    - Exporting data
    """

    def __init__(self, event_handler, parent=None):
        """
        Initialize the LiDAR control dialog.
        
        Args:
            event_handler: The main event handler instance
            parent: Parent widget
        """
        super().__init__(parent)
        self.event_handler = event_handler
        self.lidar_thread = event_handler.lidar_thread
        self.lidar_processor = event_handler.lidar_data_processor
        
        self.setWindowTitle("LiDAR Control")
        self.setModal(False)
        self.resize(500, 600)
        
        # Update timer for real-time display
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_display)
        self.update_timer.start(1000)  # Update every second
        
        self.setup_ui()
        self.refresh_ports()  # Load full device names on startup
        self.update_controls_state()

    def setup_ui(self):
        """
        Set up the user interface.
        """
        self._create_stylesheets()
        
    def _create_stylesheets(self):
        """
        Initialize stylesheets for UI elements to match main GUI.
        """
        # Primary button style (matches main GUI ENABLED_BUTTON_STYLE)
        self.PRIMARY_BUTTON_STYLE = """
            QPushButton {
                background-color: #4285f4;
                color: white;
                font-size: 12px;
                padding: 5px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #3367d6;
            }
        """
        
        # Secondary button style (matches main GUI DISABLED_BUTTON_STYLE)
        self.SECONDARY_BUTTON_STYLE = """
            QPushButton {
                background-color: #808080;
                color: #404040;
                font-size: 12px;
                padding: 5px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #909090;
            }
        """
        
        # Input field style
        self.INPUT_FIELD_STYLE = """
            background-color: white;
            color: black;
            font-size: 12px;
            padding: 5px;
            border-radius: 4px;
            border: 1px solid #ccc;
        """
        
        # Label style for dark backgrounds
        self.DARK_LABEL_STYLE = """
            background-color: #3c4043;
            color: white;
            font-size: 12px;
            font-weight: bold;
            padding: 8px;
            border-radius: 4px;
        """
        
        self.COMBO_BOX_STYLE = \
            """
            QComboBox {
                background-color: #f0f0f0;
                font-size: 12px;
                color: black;
                padding: 5px;
                border-radius: 4px;
                border: 1px solid #ccc;
            }
            QComboBox::drop-down {
                border: none;
                color: black;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #666;
                margin-right: 5px;
            }
            QComboBox QAbstractItemView {
                background-color: white;
                color: black;
                selection-background-color: #4285f4;
                selection-color: white;
                border: 1px solid #ccc;
            }
        """

        layout = QVBoxLayout(self)
        
        # Connection settings group
        connection_group = QGroupBox("Connection Settings")
        connection_layout = QGridLayout(connection_group)
        
        # Port selection
        connection_layout.addWidget(QLabel("Serial Port:"), 0, 0)
        self.port_combo = QComboBox()
        self.port_combo.setEditable(True)
        self.port_combo.setStyleSheet(self.COMBO_BOX_STYLE)
            
        # Add default ports with device names as user data
        default_ports = ["COM3", "COM4", "COM5", "COM6", "COM7", "COM8"]
        for port in default_ports:
            self.port_combo.addItem(port, port)
        connection_layout.addWidget(self.port_combo, 0, 1)
        
        # Refresh ports button
        self.refresh_ports_btn = QPushButton("Refresh")
        self.refresh_ports_btn.setStyleSheet(self.PRIMARY_BUTTON_STYLE)
        self.refresh_ports_btn.clicked.connect(self.refresh_ports)
        connection_layout.addWidget(self.refresh_ports_btn, 0, 2)
        
        # Baudrate
        connection_layout.addWidget(QLabel("Baud Rate:"), 1, 0)
        self.baudrate_spin = QSpinBox()
        self.baudrate_spin.setRange(9600, 921600)
        self.baudrate_spin.setValue(38400)
        self.baudrate_spin.setSingleStep(9600)
        self.baudrate_spin.setStyleSheet(self.INPUT_FIELD_STYLE)
        connection_layout.addWidget(self.baudrate_spin, 1, 1)
        
        # Distance offset
        connection_layout.addWidget(QLabel("Distance Offset (mm):"), 2, 0)
        self.offset_spin = QDoubleSpinBox()
        self.offset_spin.setRange(-1000.0, 1000.0)
        self.offset_spin.setValue(0.0)
        self.offset_spin.setSingleStep(1.0)
        self.offset_spin.setStyleSheet(self.INPUT_FIELD_STYLE)
        self.offset_spin.valueChanged.connect(self.update_offset)
        connection_layout.addWidget(self.offset_spin, 2, 1)
        
        layout.addWidget(connection_group)
        
        # Control buttons
        control_layout = QHBoxLayout()
        
        self.start_btn = QPushButton("Start LiDAR")
        self.start_btn.setStyleSheet(self.PRIMARY_BUTTON_STYLE)
        self.start_btn.clicked.connect(self.start_lidar)
        control_layout.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton("Stop LiDAR")
        self.stop_btn.setStyleSheet(self.SECONDARY_BUTTON_STYLE)
        self.stop_btn.clicked.connect(self.stop_lidar)
        control_layout.addWidget(self.stop_btn)
        
        self.pause_btn = QPushButton("Pause")
        self.pause_btn.setStyleSheet(self.SECONDARY_BUTTON_STYLE)
        self.pause_btn.clicked.connect(self.pause_lidar)
        control_layout.addWidget(self.pause_btn)
        
        self.resume_btn = QPushButton("Resume")
        self.resume_btn.setStyleSheet(self.PRIMARY_BUTTON_STYLE)
        self.resume_btn.clicked.connect(self.resume_lidar)
        control_layout.addWidget(self.resume_btn)
        
        layout.addLayout(control_layout)
        
        # Status display group
        status_group = QGroupBox("Status")
        status_layout = QGridLayout(status_group)
        
        # Connection status
        status_layout.addWidget(QLabel("Status:"), 0, 0)
        self.status_label = QLabel("Disconnected")
        self.status_label.setStyleSheet("color: red; font-weight: bold;")
        status_layout.addWidget(self.status_label, 0, 1)
        
        # Current reading
        status_layout.addWidget(QLabel("Current Distance:"), 1, 0)
        self.distance_label = QLabel("-- mm")
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        self.distance_label.setFont(font)
        status_layout.addWidget(self.distance_label, 1, 1)
        
        # Data count
        status_layout.addWidget(QLabel("Readings Count:"), 2, 0)
        self.count_label = QLabel("0")
        status_layout.addWidget(self.count_label, 2, 1)
        
        layout.addWidget(status_group)
        
        # Statistics group
        stats_group = QGroupBox("Statistics")
        stats_layout = QGridLayout(stats_group)
        
        self.stats_text = QTextEdit()
        self.stats_text.setMaximumHeight(150)
        self.stats_text.setReadOnly(True)
        self.stats_text.setStyleSheet(self.INPUT_FIELD_STYLE)
        stats_layout.addWidget(self.stats_text, 0, 0, 1, 2)
        
        layout.addWidget(stats_group)
        
        # Data management buttons
        data_layout = QHBoxLayout()
        
        self.export_btn = QPushButton("Export Data")
        self.export_btn.setStyleSheet(self.PRIMARY_BUTTON_STYLE)
        self.export_btn.clicked.connect(self.export_data)
        data_layout.addWidget(self.export_btn)
        
        self.clear_btn = QPushButton("Clear Data")
        self.clear_btn.setStyleSheet(self.PRIMARY_BUTTON_STYLE)
        self.clear_btn.clicked.connect(self.clear_data)
        data_layout.addWidget(self.clear_btn)
        
        layout.addLayout(data_layout)
        
        # Close button
        close_layout = QHBoxLayout()
        close_layout.addStretch()
        
        self.close_btn = QPushButton("Close")
        self.close_btn.setStyleSheet(self.PRIMARY_BUTTON_STYLE)
        self.close_btn.clicked.connect(self.close)
        close_layout.addWidget(self.close_btn)
        
        layout.addLayout(close_layout)

    def refresh_ports(self):
        """
        Refresh the list of available serial ports.
        """
        try:
            import serial.tools.list_ports
            
            current_text = self.port_combo.currentText()
            self.port_combo.clear()
            
            # Get available ports with full descriptions
            ports = serial.tools.list_ports.comports()
            
            if ports:
                for port in ports:
                    # Use full description if available, otherwise fall back to device name
                    if port.description and port.description != 'n/a':
                        display_name = f"{port.description} ({port.device})"
                    else:
                        display_name = port.device
                    
                    # Store the actual device name as user data for connection
                    self.port_combo.addItem(display_name, port.device)
                
                # Try to restore previous selection by checking both display text and device name
                index = self.port_combo.findText(current_text)
                if index < 0:
                    # If display text doesn't match, try to find by device name
                    for i in range(self.port_combo.count()):
                        if self.port_combo.itemData(i) == current_text:
                            index = i
                            break
                
                if index >= 0:
                    self.port_combo.setCurrentIndex(index)
                
                
            else:
                self.port_combo.addItem("No ports found")
                
        except ImportError:
            QMessageBox.warning(
                self,
                "Warning",
                "pyserial not installed. Cannot detect ports automatically."
            )

    def start_lidar(self):
        """
        Start LiDAR data capture.
        """
        # Get the actual device name from user data, fall back to display text if not available
        port_data = self.port_combo.currentData()
        if port_data:
            port = port_data
        else:
            port = self.port_combo.currentText()
        
        baudrate = self.baudrate_spin.value()
        
        if not port or port == "No ports found":
            QMessageBox.warning(self, "Warning", "Please select a valid serial port.")
            return
        
        success = self.event_handler.start_lidar_capture(port, baudrate)

        if success:
            self.update_controls_state()

    def stop_lidar(self):
        """
        Stop LiDAR data capture.
        """
        self.event_handler.stop_lidar_capture()
        self.update_controls_state()

    def pause_lidar(self):
        """
        Pause LiDAR data capture.
        """
        self.event_handler.pause_lidar_capture()
        self.update_controls_state()

    def resume_lidar(self):
        """
        Resume LiDAR data capture.
        """
        self.event_handler.resume_lidar_capture()
        self.update_controls_state()

    def update_offset(self):
        """
        Update the distance offset.
        """
        offset = self.offset_spin.value()
        self.event_handler.set_lidar_offset(offset)

    def export_data(self):
        """
        Export LiDAR data to a file.
        """
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export LiDAR Data",
            "lidar_data.csv",
            "CSV Files (*.csv);;All Files (*)"
        )
        
        if filename:
            self.event_handler.export_lidar_data(filename)

    def clear_data(self):
        """
        Clear all LiDAR data.
        """
        reply = QMessageBox.question(
            self,
            "Confirm Clear",
            "Are you sure you want to clear all LiDAR data?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.event_handler.clear_lidar_data()

    def update_controls_state(self):
        """
        Update the state of control buttons based on LiDAR status.
        """
        is_running = self.lidar_thread.is_running()
        is_connected = self.lidar_thread.running
        
        # Update button states and styles
        start_enabled = not is_connected
        self.start_btn.setEnabled(start_enabled)
        self.start_btn.setStyleSheet(self.PRIMARY_BUTTON_STYLE if start_enabled else self.SECONDARY_BUTTON_STYLE)
        
        stop_enabled = is_connected
        self.stop_btn.setEnabled(stop_enabled)
        self.stop_btn.setStyleSheet(self.PRIMARY_BUTTON_STYLE if stop_enabled else self.SECONDARY_BUTTON_STYLE)
        
        pause_enabled = is_running
        self.pause_btn.setEnabled(pause_enabled)
        self.pause_btn.setStyleSheet(self.PRIMARY_BUTTON_STYLE if pause_enabled else self.SECONDARY_BUTTON_STYLE)
        
        resume_enabled = is_connected and not is_running
        self.resume_btn.setEnabled(resume_enabled)
        self.resume_btn.setStyleSheet(self.PRIMARY_BUTTON_STYLE if resume_enabled else self.SECONDARY_BUTTON_STYLE)
        
        # Update status label
        if is_running:
            self.status_label.setText("Running")
            self.status_label.setStyleSheet("color: green; font-weight: bold;")
        elif is_connected:
            self.status_label.setText("Paused")
            self.status_label.setStyleSheet("color: orange; font-weight: bold;")
        else:
            self.status_label.setText("Disconnected")
            self.status_label.setStyleSheet("color: red; font-weight: bold;")

    def update_display(self):
        """
        Update the real-time display with current LiDAR data.
        """
        try:
            # Update controls state
            self.update_controls_state()
            
            # Update current reading
            current_reading = self.lidar_processor.get_current_reading()
            self.distance_label.setText(f"{current_reading:.1f} mm")
            
            # Update data count
            history = self.lidar_processor.get_reading_history()
            self.count_label.setText(str(len(history)))
            
            # Update statistics
            stats = self.event_handler.get_lidar_statistics()
            if stats:
                stats_text = f"""Average: {stats.get('average', 0):.1f} mm
Median: {stats.get('median', 0):.1f} mm
Min: {stats.get('min', 0):.1f} mm
Max: {stats.get('max', 0):.1f} mm
Range: {stats.get('range', 0):.1f} mm
Std Dev: {stats.get('std_dev', 0):.1f} mm"""
                self.stats_text.setText(stats_text)
            else:
                self.stats_text.setText("No data available")
                
        except Exception as e:
            print(f"Error updating LiDAR display: {e}")

    def closeEvent(self, arg__1):
        """
        Handle dialog close event.
        """
        self.update_timer.stop()
        arg__1.accept()
