"""Froth Tracker Application Event Handler.

This module connects the GUI components with the functional logic of the application.
It handles events triggered by user interactions with the GUI and manages the underlying
data processing and analysis.
"""


import sys
import os
from datetime import datetime
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
from PySide6.QtCore import QRect

# Import MainGUIWindow at the beginning
from froth_monitor.handlers.gui_window import MainGUIWindow

# Import FrameModel from fm_model module
from froth_monitor.processing.fm_model import FrameModel

# Import the custom overlay widget
from froth_monitor.handlers.overlay_widget import OverlayWidget

# Import the camera and network threads
from froth_monitor.video_threads.network_thread import NetworkThread
from froth_monitor.lidar_thread.lidar_data_processor import LidarDataProcessor

# Import the video recorder module
from froth_monitor.handlers.video_recorder import VideoRecorder
from froth_monitor.handlers.subhandlers import (
    AlgorithmConfigurationHandler,
    LidarHandler,
    VideoHandler,
    CalibrationHandler,
    OverlayHandler,
    ROIHandler,
    FrameProcessor,
    DataHandler,
    AirRecoveryHandler
)
from froth_monitor.handlers.logger_config import get_logger
from froth_monitor.handlers.realtime_export import RealtimeExporter

# Initialize logger for this module
logger = get_logger(__name__)

class EventHandler:
    """
    Event handler class that connects GUI components with application logic.

    This class handles events triggered by user interactions with the GUI,
    such as button clicks, menu selections, and mouse events. It manages
    the underlying video processing, ROI analysis, and data export.

    Attributes:
        gui: The MainGUIWindow instance to connect with.
        video_capture: OpenCV VideoCapture object for video input.
        timer: QTimer for controlling frame updates.
        playing: Boolean flag indicating if video is currently playing.
        current_frame: The current video frame being displayed.
        frame_width: Width of the video frame.
        frame_height: Height of the video frame.
    """

    def __init__(self, gui: MainGUIWindow):
        self.gui = gui
        self.handlers_initial_before_overlay_creation()

        # Parameters of the event handling logic
        self.current_frame = None
        self.if_save = False
        self.if_record = False

        # If using jetson import or not
        self.if_jetson = False

        # Connect GUI signals to handler methods
        self.connect_signals()
        self.initialize_gui_guidance()
        self.update_guidance()
        self.gui._trigger_jetson_mode()

    def initialize_gui_guidance(self):
        self.step_import = False
        self.step_algo_config = False
        self.step_calibration = False
        self.step_ROI_drawing = False
        self.step_export = False
    
    def update_guidance(self):
        
        # if no video is imported
        if self.video_thread.is_running() == False:
            self.gui._update_guidance("step_1")

        else:
            # if video is imported but calibration not finished
            if self.calibration_handler.confirm_calibration == False:
                self.gui._update_guidance("step_2")

            else:
                # if calibration is finished but ROI not drawn
                if self.step_ROI_drawing == False:
                    self.gui._update_guidance("step_3")
                    
        # if export setting finished
        if self.exporter.finish_save_setting == True:
            self.gui._update_guidance("finish_export_setting")

            if self.exporter.record_video == True:
                self.gui._update_guidance("enable_recording")

    def trigger_jetson_mode(self):
        self.if_jetson = True
        self.initialze_tool_window_n_handlers()
        self.update_guidance()

    # ============= Step 1: Initialize handlers ==============
    def handlers_initial_before_overlay_creation(self):
        self.canvas_width = self.gui.video_canvas_label.width()
        self.canvas_height = self.gui.video_canvas_label.height()

        # Initialize the frame model for processing video frames
        self.frame_model = FrameModel()
        self.current_frame_number = 0
        
        # Initialize LiDAR data processor and connect signals
        self.lidar_data_processor = LidarDataProcessor(
            self.gui, self
        )
        
        # Initialize Air Recovery data processor
        from froth_monitor.air_recovery import AirRecoveryDataProcessor
        self.air_recovery_data_processor = AirRecoveryDataProcessor(self)

        self.data_handler = DataHandler(self.gui, self.frame_model, self.lidar_data_processor, self.air_recovery_data_processor)

        self.exporter = RealtimeExporter(self.gui)
        self.exporter.setting_finished.connect(self.finish_export_setting)

        # Overlay related attributes
        self.overlay_active = False
        self.video_rect = QRect()

        # Initialize camera thread for event-driven frame capture
        self.video_thread = NetworkThread()

        self.lidar_handler = LidarHandler(self.lidar_data_processor,
                                        self.gui, self.data_handler, self)
                                        
        self.gui.lidar_configuration.clicked.connect(self.lidar_handler.open_lidar_control)
        
        # Initialize Air Recovery handler
        self.air_recovery_handler = AirRecoveryHandler(self.air_recovery_data_processor, self.gui, self)
        self.gui.air_rec_configuration.clicked.connect(self.air_recovery_handler.open_air_recovery_control)

        # Initialize video recorder
        self.video_recorder = VideoRecorder()
        self.recording_active = False

        # Initialize handlers
        self.overlay_handler = OverlayHandler(self.gui, self)
        self.video_handler = VideoHandler(
            self, self.gui, 
            self.frame_model, 
            video_thread=self.video_thread
        )

    # ============= Step 2: Connect GUI signals to the buttons =============
    def connect_signals(self):
        """Connect GUI signals to their respective handler methods."""

        # Connect menu actions directly
        self.gui.import_button.clicked.connect(self.video_handler.handle_video_import)
        self.gui.export_button.clicked.connect(self.export_settings)

        # # Connect buttons directly using the gui reference
        self.gui.play_pause_button.clicked.connect(self.video_handler.pause_play)

        self.gui.algorithm_configuration.clicked.connect(
            self.open_algorithm_configuration
        )

        # self.gui.save_button.clicked.connect(self.save_data)
        self.gui.record_button.clicked.connect(self.toggle_recording)
        self.gui.simple_reset_button.clicked.connect(self.reset_mission)

    def initialze_tool_window_n_handlers(self):
        if not self.video_handler.playing:  # Access playing state from VideoHandler
            return

        self.overlay_handler.initialize_tool_window()
        self.overlay_widget = self.overlay_handler.overlay_widget

        self.handlers_initial_after_overlay_creation()
        self.update_guidance()

    def disconnect_signals(self):
        # Connect menu actions directly
        self.gui.import_button.clicked.disconnect(self.video_handler.handle_video_import)
        self.gui.export_button.clicked.disconnect(self.export_settings)

        # # Connect buttons directly using the gui reference
        self.gui.play_pause_button.clicked.disconnect(self.video_handler.pause_play)

        self.gui.algorithm_configuration.clicked.disconnect(
            self.open_algorithm_configuration
        )

        # self.gui.save_button.clicked.disconnect(self.save_data)
        self.gui.record_button.clicked.disconnect(self.toggle_recording)
        self.gui.simple_reset_button.clicked.disconnect(self.reset_mission)

        self.gui.confirm_arrow_button.clicked.disconnect(
            self.calibration_handler.confirm_arrow_n_ruler
        )
        self.gui.add_arrow_button.clicked.disconnect(
            self.calibration_handler.start_arrow_drawing
        )
        self.gui.calibration_button.clicked.disconnect(
            self.calibration_handler.start_ruler_calibration
        )
        self.overlay_widget.ruler_measured.disconnect(
            self.calibration_handler.handle_ruler_measurement
        )
        self.overlay_widget.arrow_drawn.disconnect(
            self.calibration_handler.handle_arrow_drawing
        )

        self.gui.add_roi_button.clicked.disconnect(self.roi_handler.add_roi)
        self.overlay_widget.roi_created.disconnect(
            self.roi_handler.handle_roi_created
        )  # Connect to the signal emitted by OverlayWidget
        self.gui.delete_roi_button.clicked.disconnect(self.roi_handler.delete_last_roi)

    def handlers_initial_after_overlay_creation(self):
        """
        Initialize the event handlers after the overlay widget is created.
        """

        self.calibration_handler = CalibrationHandler(
            self.gui, self.frame_model, self.overlay_widget
        )
        self.calibration_handler.calibration_confirmed.connect(
            self.update_guidance
        )
        self.roi_handler = ROIHandler(
            self, self.gui, self.frame_model, self.video_thread, self.overlay_widget
        )
        self.frame_processor = FrameProcessor(
            self,
            self.gui,
            self.frame_model,
            self.video_thread,
            self.overlay_widget,
            self.video_recorder,
            self.roi_handler,
            self.data_handler,
        )

        # Connect camera thread signals to frame processor
        if self.if_jetson:
            
            # Connect network thread connection status to automatic LiDAR control
            self.video_thread.connection_status_changed.connect(
                lambda connected, message: self.handle_network_connection_status(connected, message)
            )
    

            self.video_thread.data_available.connect(
                self.handle_jetson_data
            )
            

        self.gui.confirm_arrow_button.clicked.connect(
            self.calibration_handler.confirm_arrow_n_ruler
        )
        self.gui.add_arrow_button.clicked.connect(
            self.calibration_handler.start_arrow_drawing
        )
        self.gui.calibration_button.clicked.connect(
            self.calibration_handler.start_ruler_calibration
        )
        self.overlay_widget.ruler_measured.connect(
            self.calibration_handler.handle_ruler_measurement
        )
        self.overlay_widget.arrow_drawn.connect(
            self.calibration_handler.handle_arrow_drawing
        )

        self.gui.add_roi_button.clicked.connect(self.roi_handler.add_roi)
        self.overlay_widget.roi_created.connect(
            self.roi_handler.handle_roi_created
        )  # Connect to the signal emitted by OverlayWidget
        self.gui.delete_roi_button.clicked.connect(self.roi_handler.delete_last_roi)

    def finish_export_setting(self):
        self.frame_model.load_exporter(self.exporter)
        self.data_handler.load_exporter(self.exporter)
        self.calibration_handler.load_exporter(self.exporter)
        self.lidar_data_processor.load_exporter(self.exporter)

        self.update_guidance()

    def handle_jetson_data(self, server_data, frame):
        timestamp = server_data.get("lidar_timestamp", datetime.now())
        lidar_reading = server_data.get("lidar_reading")

        if frame is not None and frame.size > 0:
            self.frame_processor.process_new_frame(frame)
        if server_data:
            self.lidar_data_processor.process_lidar_data(timestamp, lidar_reading)

    def open_algorithm_configuration(self):
        """
        Open a dialog to configure the velocity calculation algorithm.
        """
        if_paused = self.video_handler.playing

        if not self.video_thread.is_running():
            QMessageBox.warning(self.gui, "Warning", "No video source loaded!")
            return

        if not if_paused:  # Access playing state from VideoHandler
            QMessageBox.information(
                self.gui,
                "Information",
                "Video was PAUSED by user,\
                \nit is going to be CONTINUED now for algoritm configuration.",
            )
            self.video_handler.pause_play()  # Use VideoHandler's pause_play metho

        dialog = AlgorithmConfigurationHandler(
            self.gui, self.video_thread, self.frame_model
        )
        dialog.dialog.exec()
        pass
    
    def reset_handlers(self):
        # Overlay related attributes
        self.video_rect = QRect()
        
        self.frame_model.reset()
        self.overlay_widget.reset()

        # Initialize camera thread for event-driven frame capture
        if hasattr(self, 'video_thread') and self.video_thread:
            self.video_thread.reset()

        # self.lidar_thread = cast(LidarThread, None)
        # self.lidar_thread = LidarThread()

        # Reset video recorders
        if self.recording_active:
            # Stop recording
            success, output_path, frame_count = self.video_recorder.stop_recording()

            if success:
                self.recording_active = False
                self.gui.record_button.setText("  Start Recording")
                self.gui.record_button.setStyleSheet(
                    "QPushButton {\
                        background-color: red; color: white; font-size: 15px; \
                        padding: 5px; border-radius: 4px;\
                    }\
                    QPushButton:hover {\
                        background-color: #3367d6;\
                    }"
                )

                # Show success message with recording statistics
                QMessageBox.information(
                    self.gui,
                    "Recording Completed",
                    f"Video saved to: {output_path}\nFrames recorded: {frame_count}",
                )

                self.gui.statusBar().showMessage(f"Recording stopped: {output_path}")

        # Reset video handler
        # self.video_handler = cast(VideoHandler, None)
        self.video_handler = VideoHandler(
            self, self.gui, 
            self.frame_model, 
            self.video_thread
        )

    def reset_mission(self):
        """Reset the application for a new mission."""
        # Check if data has been saved
        if not self.if_save:
            # Show confirmation dialog
            reply = QMessageBox.question(
                self.gui,
                "Confirmation",
                "Are you sure you want to reset the application for a new mission? \
                    \nAll unsaved data will be lost.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,  # Set default button to No
            )

            # Only proceed if user explicitly clicked Yes
            # The X button will return QMessageBox.StandardButton.No by default
            if reply != QMessageBox.StandardButton.Yes:
                return  # Exit the function without resetting

        # If we get here, either data was saved or user confirmed reset
        QMessageBox.information(self.gui, "Info", "Application reset for new mission.")
    
        self.if_save = False
        self.calibration_handler.confirm_calibration = False
        self.current_frame_number = 0
        
        self.gui.video_canvas_label.clear()
        self.gui.plot_widget.clear()

        logger.info("===Starting a new mission===")
        logger.info("Disconnecting Signals...")
        self.disconnect_signals()
        logger.info("Initializing handlers...")
        self.reset_handlers()
        logger.info("Connecting Signals...")
        self.connect_signals()
        logger.info("Updating Guidance...")
        self.update_guidance()

    def handle_network_connection_status(self, connected: bool, message: str):
        """
        Handle network thread connection status changes.
        Automatically start/stop LiDAR based on network connection status.
        
        Args:
            connected (bool): True if network is connected, False if disconnected
            message (str): Connection status message
        """
        if connected:
            # Network connected - automatically start LiDAR in network mode
            logger.info(f"Network connected: {message}")
            self.gui.statusBar().showMessage(f"Network connected: {message}")
            
            # Switch LiDAR to network mode (no separate serial connection needed)
            self.lidar_data_processor.set_network_mode(True)
            
            # Initialize LiDAR mode in the GUI
            self.lidar_handler.initialize_lidar_mode()
            
            logger.info("LiDAR automatically connected via network thread")
            
        else:
            # Network disconnected - stop LiDAR
            logger.info(f"Network disconnected: {message}")
            self.gui.statusBar().showMessage(f"Network disconnected: {message}")
            
            # Switch LiDAR back to serial mode
            self.lidar_data_processor.set_network_mode(False)
            
            logger.info("LiDAR disconnected due to network disconnection")

    def toggle_recording(self):
        """Start or stop video recording."""
        # Check if video is loaded
        if not self.video_thread.is_running():
            QMessageBox.warning(
                self.gui,
                "Warning",
                "No video source loaded! Please load a video first.",
            )
            return

        if not self.exporter.finish_save_setting:
            QMessageBox.warning(
                self.gui,
                "Export Error",
                "Please configure export settings before recording.",
            )
            return

        if not self.recording_active:
            # Start recording
            # Get video directory and filename from export settings
            video_directory = self.exporter.video_directory
            video_filename = self.exporter.video_filename

            # If no directory is set, use a default directory
            if not video_directory:
                video_directory = os.path.join(
                    os.path.expanduser("~"), "Videos", "FrothMonitor"
                )
                self.exporter.video_directory = video_directory

            # Get frame dimensions and FPS
            fps = 120.0
            frame_width, frame_height = self.video_thread.get_frame_dimensions()

            # Start recording
            success = self.video_recorder.start_recording(
                video_directory,
                video_filename,
                frame_width,
                frame_height,
                fps,
                is_video_file = False,
            )

            if success:
                self.recording_active = True
                self.gui.record_button.setText("  Stop Recording")
                self.gui.record_button.setStyleSheet(
                    "QPushButton {\
                        background-color: red; color: white; font-size: 15px; \
                        padding: 5px; border-radius: 4px;\
                    }\
                    QPushButton:hover {\
                        background-color: #3367d6;\
                    }"
                )
                self.gui.statusBar().showMessage(
                    f"Recording started: {self.video_recorder.output_path}"
                )
            else:
                QMessageBox.critical(
                    self.gui,
                    "Error",
                    "Could not start recording! Check if the directory is accessible.",
                )
        else:
            # Stop recording
            success, output_path, frame_count = self.video_recorder.stop_recording()

            if success:
                self.recording_active = False
                self.gui.record_button.setText("  Start Recording")
                self.gui.record_button.setStyleSheet(
                    "QPushButton {\
                        background-color: red; color: white; font-size: 15px; \
                        padding: 5px; border-radius: 4px;\
                    }\
                    QPushButton:hover {\
                        background-color: #3367d6;\
                    }"
                )

                # Show success message with recording statistics
                QMessageBox.information(
                    self.gui,
                    "Recording Completed",
                    f"Video saved to: {output_path}\nFrames recorded: {frame_count}",
                )

                self.gui.statusBar().showMessage(f"Recording stopped: {output_path}")
            else:
                QMessageBox.warning(self.gui, "Warning", "No active recording to stop.")

    def export_settings(self):
        """Open export settings dialog."""
        # Placeholder for export settings
        # QMessageBox.information(self.gui, "Info", "Export settings will be implemented.")

        self.exporter.export_setting_window()

    def check_if_import(self) -> bool:
        """Check if a video file is being imported."""

        if not self.video_thread.is_running():
            QMessageBox.warning(
                self.gui,
                "Warning",
                "No video source loaded! Please load a video first.",
            )
            return False
        else:
            return True


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("macintosh")
    app.setStyleSheet("""
        QLabel, QLineEdit, QRadioButton, QPushButton, QGroupBox, QMenuBar, QMenu, QMessageBox {
            color: black;
        }
        QMessageBox QLabel {
            color: black;
        }
    """)
    window = MainGUIWindow()
    handler = EventHandler(window)
    window.show()
    sys.exit(app.exec())
