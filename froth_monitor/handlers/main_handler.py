"""Froth Tracker Application Event Handler.

This module connects the GUI components with the functional logic of the application.
It handles events triggered by user interactions with the GUI and manages the underlying
data processing and analysis.
"""

import cv2
import sys
import os
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
from PySide6.QtGui import QIcon

# Import MainGUIWindow at the beginning
from froth_monitor.handlers.gui_window import MainGUIWindow

# Import FrameModel from fm_model module
from froth_monitor.processing import FrameModel

# Import the camera and network threads
from froth_monitor.video_threads.camera_thread import CameraThread
from froth_monitor.video_threads.network_thread import NetworkThread
from froth_monitor.lidar_thread.lidar_thread import LidarThread
from froth_monitor.lidar_thread.lidar_data_processor import LidarDataProcessor
from froth_monitor.air_recovery.air_recovery_data_processor import AirRecoveryDataProcessor
from froth_monitor.handlers import AlgorithmConfigurationHandler
from froth_monitor.handlers.realtime_export import RealtimeExporter

# Import the video recorder module
from froth_monitor.handlers.video_recorder import VideoRecorder
from froth_monitor.handlers import (
    VideoHandler,
    CalibrationHandler,
    OverlayHandler,
    ROIHandler,
    FrameProcessor,
    LidarHandler,
    # DataHandler, # Deprecated
    DataCoordinator,
    AirRecoveryHandler
)
from froth_monitor.handlers.visualization_handler import VisualizationHandler
from froth_monitor.handlers.logger_config import get_logger

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
        self.initialize_level_one_handlers()
        self.initialize_level_two_handlers()

        # Parameters of the event handling logic
        self.current_frame = None
        self.if_save = False
        self.if_record = False

        # Connect GUI signals to handler methods
        self.connect_gui_signals()
        self.initialize_gui_guidance()
        self.update_guidance()

    # ============= GUI guidance =============
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

    # ============= Different mode trigger ==============
    def start_playing(self):
        # self.network_thread.reset() # Removed to prevent terminating the thread just started by video_handler
        self.video_thread = self.network_thread
        self.video_handler.update_video_thread(self.video_thread)
        self.initialize_level_three_handlers()
        
        # if not self.lidar_data_processor.if_lidar:
        #     self.gui._trigger_normal_mode() // v2_residue
        
        self.update_guidance()

    # ============= Handler Initialization Pipeline ==============
    def initialize_level_one_handlers(self) -> None:
        """Initialize foundational components with no inter-handler dependencies.
        
        This level establishes core infrastructure components that other handlers
        will depend on. These components are stateless or have minimal dependencies,
        making them safe to initialize first.
        
        Components initialized:
            - FrameModel: Video frame processing and analysis engine
            - Video threads: Camera, network, and unified video thread management
            - LiDAR thread:  For depth sensing management
            - VideoRecorder: Frame capture and storage system
        
        Note:
            This method must be called before initialize_level_two_handlers().
        """
        # Core processing model - no dependencies
        self.frame_model = FrameModel()
        self.current_frame_number = 0

        # Hardware interface threads - minimal dependencies
        self.lidar_thread = LidarThread()
        self.camera_thread = CameraThread()
        self.network_thread = NetworkThread()
        
        # Active video source (defaults to camera thread)
        self.video_thread: NetworkThread | CameraThread = \
            cast(NetworkThread | CameraThread, CameraThread())

        # Recording infrastructure
        self.video_recorder = VideoRecorder()
        self.recording_active = False

    def initialize_level_two_handlers(self) -> None:
        """Initialize data processors and handlers that depend on Level 1 components.
        
        This level creates handlers that require the foundational components from
        Level 1. These handlers coordinate between data sources, processing logic,
        and GUI presentation. Signal connections are established to enable
        event-driven communication.
        
        Components initialized:
            - Data processors: LiDAR, air recovery, and integrated data handling
            - Control handlers: Video, overlay, LiDAR, and air recovery management
            - Export infrastructure: Real-time data export to external formats
        
        Dependencies:
            - Requires: frame_model, video threads, lidar_thread
            - Required by: Level 3 handlers (FrameProcessor, ROIHandler, etc.)
        
        Note:
            This method must be called after initialize_level_one_handlers() and
            before initialize_level_three_handlers().
        """
        # LiDAR data processing pipeline
        self.lidar_data_processor = LidarDataProcessor()
        # self.lidar_thread.data_available.connect(
        #     self.lidar_data_processor.process_lidar_data
        # ) // v2_residue

        # Air recovery calculation and control
        self.air_recovery_data_processor = AirRecoveryDataProcessor(self)
        self.air_recovery_handler = AirRecoveryHandler(
            self.air_recovery_data_processor, self.gui, self
        )

        # Integrated data handling and visualization
        self.data_coordinator = DataCoordinator(
            self.frame_model,
            self.lidar_data_processor,
            self.air_recovery_data_processor
        )
        self.visualization_handler = VisualizationHandler(self.gui)

        self.lidar_data_processor.display_data_available.connect(self.visualization_handler.update_fh_plot)
        self.data_coordinator.air_recovery_updated.connect(self.visualization_handler.update_arec_display)
        
        # LiDAR control interface
        # self.lidar_handler = LidarHandler(
        #     self.lidar_thread, self.lidar_data_processor, self.gui, self
        # ) //v2_residue

        self.lidar_handler = LidarHandler(
            self.lidar_data_processor, self.gui, self
        ) ## v3_only

        # Overlay management (prepares for Level 3 initialization)
        self.overlay_handler = OverlayHandler(self.gui, self)
        
        # Video playback and capture control
        self.video_handler = VideoHandler(
            self.frame_model,
            self.camera_thread,
            self.network_thread,
            self.video_thread
        )
        
        # Video handler signal routing
        self.video_handler.camera_selection_requested.connect(self._show_camera_dialog)
        self.video_handler.file_selection_requested.connect(self._show_file_dialog)
        self.video_handler.video_started.connect(self._video_started)
        self.video_handler.video_cannot_resume.connect(self._video_cannot_resume)
        self.video_handler.playback_state_changed.connect(self._playback_state_changed)
        self.video_handler.thread_activate.connect(self.start_playing)
        self.video_handler.thread_activate.connect(self.lidar_handler.initialize_lidar_mode)

        # Frame resampling configuration (decouples processing from display resolution)
        from froth_monitor.handlers.frame_resample_handler import FrameResampleHandler, ResolutionPreset
        self.frame_resample_handler = FrameResampleHandler()
        logger.info(f"MainHandler: FrameResampleHandler initialized with {self.frame_resample_handler.current_preset.value} preset")
        
        # Connect resolution dropdown if available
        if hasattr(self.gui, 'resolution_combo'):
            self.gui.resolution_combo.currentTextChanged.connect(self._on_resolution_changed)
            self.frame_resample_handler.available_resolutions.connect(self._update_resolution_dropdown)

        # Real-time data export infrastructure
        self.exporter = RealtimeExporter(self.gui)
        self.exporter.setting_finished.connect(self._finish_export_setting)

    def initialize_level_three_handlers(self) -> None:
        """Initialize UI-dependent handlers that require active video playback.
        
        This level creates handlers that depend on the overlay widget and active
        video stream. These components facilitate user interaction with live video,
        including ROI definition, calibration, and frame processing. This method
        is called dynamically when video playback starts.
        
        Components initialized:
            - CalibrationHandler: Spatial calibration and measurement tools
            - ROIHandler: Region of interest creation and management
            - FrameProcessor: Real-time frame processing and display pipeline
        
        Dependencies:
            - Requires: overlay_widget (created by overlay_handler)
            - Requires: Active video stream (video_handler.playing == True)
            - Requires: All Level 1 and Level 2 handlers
        
        Signal Routing:
            Establishes connections between overlay interactions, calibration
            actions, and ROI management for coordinated user workflow.
        
        Note:
            This method is called from start_playing() when video begins.
            It will abort if video is not actively playing.
        
        Raises:
            Logs info message and returns early if video is not playing.
        """
        # Guard: Ensure video is actively playing before creating UI handlers
        if not self.video_handler.playing:
            logger.info("Video is not playing, cannot initialize tool window.")
            return

        # Create overlay widget for video interaction layer
        self.overlay_handler.initialize_tool_window()
        self.overlay_widget = self.overlay_handler.overlay_widget  # Get overlay widget reference
        
        # Real-time frame processing pipeline
        # Create display manager for GUI operations
        from froth_monitor.handlers.frame_display_manager import FrameDisplayManager
        self.display_manager = FrameDisplayManager(
            self.gui.video_canvas_label,
            self.gui.statusBar(),
            self.overlay_widget
        )

        # Spatial calibration and measurement system
        self.calibration_handler = CalibrationHandler(
            self.gui.px2mm_result_textbox.text(),
            self.gui.px2mm_spinbox.value(), 
            self.gui.direction_textbox.text(), 
            self.frame_resample_handler.source_resolution,  # For source resolution
            self.display_manager.get_video_dimensions(),
            self.frame_resample_handler.custom_scale
        )
        self.display_manager.first_frame_ready.connect(self.calibration_handler.update_overlay_res)
        self.frame_resample_handler.resolution_changed.connect(self.calibration_handler.update_source_res)
        self.frame_resample_handler.scale_changed.connect(self.calibration_handler.update_scale_factor)
        self.calibration_handler.ruler_draw_start.connect(self.overlay_widget.ruler_calibration)
        self.calibration_handler.arrow_draw_start.connect(self.overlay_widget.start_arrow_drawing)
        self.calibration_handler.release_px2mm.connect(self.frame_model.get_px_to_mm)
        self.calibration_handler.release_arrow_direction.connect(self.frame_model.get_overflow_direction)
        self.gui.px2mm_result_textbox.textChanged.connect(self.calibration_handler.update_display_px2mm)
        self.gui.px2mm_spinbox.valueChanged.connect(self.calibration_handler.update_distance_mm)
        self.gui.direction_textbox.textChanged.connect(self.calibration_handler.update_arrow_direction)
        self.calibration_handler.status_message.connect(self._status_message)
        self.calibration_handler.message_box.connect(self._message_box)
        self.calibration_handler.warning_box.connect(self._warning_box)
        self.calibration_handler.calibration_confirmed.connect(self.update_guidance)
        self.calibration_handler.set_textbox_px2mm.connect(self.gui.px2mm_result_textbox.setText)
        self.calibration_handler.set_textbox_arrow_direction.connect(self.gui.direction_textbox.setText)
        self.overlay_widget.ruler_measured.connect(self.calibration_handler.handle_ruler_measurement)
        self.overlay_widget.arrow_drawn.connect(self.calibration_handler.handle_arrow_drawing)


        # Region of interest management
        self.roi_handler = ROIHandler(
            display_res=self.display_manager.get_video_dimensions(),
            processing_res=self.frame_resample_handler.processing_resolution,
            video_running=self.video_thread.is_running()
        )
        
        # Dynamic resolution/state updates
        self.display_manager.first_frame_ready.connect(self.roi_handler.update_display_res)
        self.frame_resample_handler.resolution_changed.connect(self.roi_handler.update_processing_res)
        # Note: Video thread state is tracked via is_running() checks rather than signals
        # as CameraThread/NetworkThread don't expose started/stopped signals
        
        # ROI drawing workflow
        self.roi_handler.roi_draw_start.connect(self.overlay_widget.start_roi_drawing)
        self.overlay_widget.roi_created.connect(self.roi_handler.handle_roi_created)
        
        # ROI data flow
        self.roi_handler.roi_added.connect(self._handle_roi_data)
        self.roi_handler.roi_deleted.connect(self.frame_model.delete_last_roi)
        
        # UI updates
        self.roi_handler.request_overlay_update.connect(self.overlay_widget.update)
        
        # User feedback
        self.roi_handler.status_message.connect(self._status_message)
        self.roi_handler.warning_box.connect(self._warning_box)
        
        self.frame_processor = FrameProcessor(
            self.frame_model,
            self.video_thread,
            self.video_recorder,
            self.roi_handler,
            self.frame_resample_handler,
            self.display_manager,
        )
        self.frame_processor.update_velocity_plot.connect(self.visualization_handler.update_velocity_plot)
        self.frame_processor.update_velocity_plot.connect(self.data_coordinator.process_new_velocity_data)
        # Frame processor state synchronization
        self.video_handler.playback_state_changed.connect(
            self.frame_processor.set_playback_state
        )
        # self.video_thread.frame_available.connect(
        #     self.frame_processor.process_new_frame
        # ) // v2_residue

        self.video_thread.frame_available.connect(
            lambda frame: self.frame_processor.process_new_frame(frame)
        )
        self.video_thread.lidar_data_available.connect( # type: ignore
            lambda data: self.lidar_data_processor.process_lidar_data(data)
        ) 

        self.gui.confirm_arrow_button.clicked.connect(self.calibration_handler.confirm_arrow_n_ruler)
        self.gui.add_arrow_button.clicked.connect(self.calibration_handler.start_arrow_drawing)
        self.gui.calibration_button.clicked.connect(self.calibration_handler.start_ruler_calibration)
        self.gui.delete_roi_button.clicked.connect(self.roi_handler.delete_last_roi)
        self.gui.add_roi_button.clicked.connect(self.roi_handler.add_roi)

    def _finish_export_setting(self):

        self.calibration_handler.release_export_data.connect(lambda degree, px2mm: self.exporter.write_calibration_data(degree, px2mm))
        self.calibration_handler.update_export_status(True)

        self.frame_model.initialize_roi_sheets.connect(lambda roi_list: self.exporter.initialize_roi_sheets(roi_list))
        self.frame_model.create_roi_sheets.connect(lambda num_roi: self.exporter.create_roi_sheets(num_roi))
        self.frame_model.delete_roi_sheets.connect(lambda num_roi: self.exporter.delete_roi_sheets(num_roi))
        self.frame_model.release_roi_movement_data.connect(lambda roi_id, delta_list: self.exporter.write_roi_movement_data(roi_id, delta_list))
        self.frame_model.update_export_status(True)

        self.data_coordinator.release_roi_summary_data.connect(lambda roi_id, summary_list: self.exporter.write_roi_summary_data(roi_id, summary_list))
        self.data_coordinator.update_export_status(True)

        self.lidar_data_processor.load_exporter(self.exporter)
        self.update_guidance()
    
    def _handle_roi_data(self, display_coords, proc_coords):
        """Handle ROI creation by adding to FrameModel.
        
        Called when ROIHandler emits roi_added signal after coordinate transformation.
        
        Args:
            display_coords (tuple): Display coordinates (x, y, width, height)
            proc_coords (tuple): Processing coordinates (x, y, width, height)
        """
        # Add ROI to FrameModel
        roi = self.frame_model.add_roi()
        roi.set_display_coordinate(display_coords)
        roi.set_processing_coordinate(proc_coords)
        
        logger.info(
            f"MainHandler: ROI added to FrameModel - "
            f"Display: {display_coords}, Processing: {proc_coords}"
        )

    # ============= Step 2: Connect GUI signals to the buttons =============
    def connect_gui_signals(self):
        """Connect GUI signals to their respective handler methods."""

        # Connect menu actions 
        self.gui.import_button.clicked.connect(self._on_import_button_clicked)
        self.gui.export_button.clicked.connect(self.export_settings)

        # Connect left panel buttons
        self.gui.algorithm_configuration.clicked.connect(self.open_algorithm_configuration)
        self.gui.record_button.clicked.connect(self.toggle_recording)
        self.gui.simple_reset_button.clicked.connect(self.reset_mission)

        # Connect central panel buttons
        self.gui.play_pause_button.clicked.connect(self.video_handler._pause_play)
        self.gui.refresh_graph_button.clicked.connect(self.visualization_handler.clear_display)

        # Connect right panel buttons
        self.gui.lidar_configuration.clicked.connect(self.lidar_handler.open_lidar_control)
        self.gui.air_rec_configuration.clicked.connect(self.air_recovery_handler.open_air_recovery_control)

    def disconnect_signals(self):
        # Connect menu actions directly
        self.gui.import_button.clicked.disconnect(self.video_handler.handle_video_import)
        self.gui.export_button.clicked.disconnect(self.export_settings)

        # # Connect buttons directly using the gui reference
        self.gui.play_pause_button.clicked.disconnect(self.video_handler._pause_play)

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

        self.gui.refresh_graph_button.clicked.disconnect(self.visualization_handler.clear_display)

    def reset_signals(self):
        self.gui.export_button.clicked.connect(self.export_settings)

        # # Connect buttons directly using the gui reference
        self.gui.play_pause_button.clicked.connect(self.video_handler._pause_play)
        self.gui.algorithm_configuration.clicked.connect(
            self.open_algorithm_configuration
        )

        # self.gui.save_button.clicked.connect(self.save_data)
        self.gui.record_button.clicked.connect(self.toggle_recording)
        self.gui.simple_reset_button.clicked.connect(self.reset_mission)
        self.gui.refresh_graph_button.clicked.connect(self.visualization_handler.clear_display)

    # ============= Video Handlers signal and related GUI interaction =============
    def _resource_path(self,relative_path):
        if hasattr(sys, "_MEIPASS"):
            return os.path.join(sys._MEIPASS, relative_path)  # type: ignore
        return relative_path

    def _on_import_button_clicked(self):
        """Handle import button click by reading GUI state and calling handler."""
        # v2_reside
        # if self.gui.webcam_radio.isChecked():
        #     self.video_handler.handle_video_import("webcam")
        # elif self.gui.prerecorded_radio.isChecked():
        #     self.video_handler.handle_video_import("file")
        self.video_handler.load_jetson()

    def _on_resolution_changed(self, text):
        """Handle resolution preset change from GUI."""
        from froth_monitor.handlers.frame_resample_handler import ResolutionPreset
        try:
            # simple mapping based on text.upper() matching enum names
            # Enum is ULTRA, HIGH, MEDIUM, LOW
            # Format might get "MEDIUM (1280x720)" -> split to get "MEDIUM"
            preset_name = text.split(" (")[0].upper()
            
            if hasattr(ResolutionPreset, preset_name):
                preset = ResolutionPreset[preset_name]
                self.frame_resample_handler.set_preset(preset)
                self._status_message(f"Resolution changed to {text}")
        except Exception as e:
            logger.error(f"Error changing resolution: {e}")

    def _update_resolution_dropdown(self, resolutions_map: dict):
        """Update resolution dropdown with dynamic labels."""
        try:
            from froth_monitor.handlers.frame_resample_handler import ResolutionPreset
            
            # Store current selection to try and restore it
            current_text = self.gui.resolution_combo.currentText()
            # If current text has parentheses, extract the preset name
            current_preset_name = current_text.split(" (")[0].upper()
            
            self.gui.resolution_combo.blockSignals(True)
            self.gui.resolution_combo.clear()
            
            # Order: ORIGINAL, High, Medium, Low
            ordered_presets = [
                ResolutionPreset.ORIGINAL,
                ResolutionPreset.HIGH,
                ResolutionPreset.MEDIUM,
                ResolutionPreset.LOW
            ]
            
            for preset in ordered_presets:
                if preset in resolutions_map:
                    self.gui.resolution_combo.addItem(resolutions_map[preset])
            
            # Restore selection
            for i in range(self.gui.resolution_combo.count()):
                item_text = self.gui.resolution_combo.itemText(i)
                if item_text.split(" (")[0].upper() == current_preset_name:
                    self.gui.resolution_combo.setCurrentIndex(i)
                    break
                    
            self.gui.resolution_combo.blockSignals(False)
            logger.debug("Resolution dropdown updated with dynamic labels")
            
        except Exception as e:
            logger.error(f"Error updating resolution dropdown: {e}")

    def _show_camera_dialog(self):
        """Show camera selection dialog and pass result to video handler."""
        # Detect available cameras
        available_cameras = []
        for index in range(10):
            cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
            if cap.isOpened():
                available_cameras.append(f"Camera {index}")
                cap.release()
        
        if not available_cameras:
            QMessageBox.critical(self.gui, "Error", "No cameras detected!")
            return
        
        # Show dialog
        dialog = QDialog(self.gui)
        dialog.setWindowTitle("Select Camera")
        layout = QVBoxLayout(dialog)
        
        camera_combo = QComboBox(dialog)
        camera_combo.addItems(available_cameras)
        layout.addWidget(camera_combo)
        
        confirm_button = QPushButton("Load Camera", dialog)
        confirm_button.clicked.connect(dialog.accept)
        layout.addWidget(confirm_button)
        
        # If user confirms, pass the selected camera to VideoHandler
        if dialog.exec():
            selected_camera = camera_combo.currentText()
            camera_index = int(selected_camera.split(" ")[1])
            self.video_handler.load_camera(camera_index)

    def _show_file_dialog(self):
        """Show file selection dialog and pass result to video handler."""
        file_path, _ = QFileDialog.getOpenFileName(
            self.gui, 
            "Open Video File", 
            "", 
            "Video Files (*.mp4 *.avi *.mkv)"
        )
        
        if file_path:
            self.video_handler.load_video_file(file_path)

    def _playback_state_changed(self, state):
        if state:
            self._status_message("Video playing")
            self.gui.play_pause_button.setIcon(
                QIcon(self._resource_path("froth_monitor/resources/pause_icon.ico"))
            )
        else:
            self._status_message("Video paused")
            self.gui.play_pause_button.setIcon(
                QIcon(self._resource_path("froth_monitor/resources/play_icon.ico"))
            )

    def _video_cannot_resume(self):
        QMessageBox.warning(self.gui, "Warning", "Cannot resume video!")

    def _video_started(self):
        self._status_message("Video started")

    def _message_box(self, message):
        QMessageBox.information(self.gui, "Information", message)
    
    def _status_message(self, message):
        self.gui.statusBar().showMessage(message)

    def _warning_box(self, message):
        QMessageBox.warning(self.gui, "Warning", message)
    
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
            self.video_handler._pause_play()  # Use VideoHandler's pause_play metho

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
        if hasattr(self, 'camera_thread') and self.camera_thread:
            self.camera_thread.reset()
        if hasattr(self, 'network_thread') and self.network_thread:
            self.network_thread.reset()
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
                self.gui.record_button.setText("  Start Video Recording")
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
        self.video_handler.reset()
        self.frame_processor.cleanup()

    def reset_mission(self):
        """Reset the application for a new mission."""

        # Check if data has been saved
        reply = QMessageBox.question(
            self.gui,
            "Confirmation",
            "Are you sure you want to end the session and save data?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,  # Set default button to No
        )

        # Only proceed if user explicitly clicked Yes
        # The X button will return QMessageBox.StandardButton.No by default
        if reply != QMessageBox.StandardButton.Yes:
            return  # Exit the function without resetting
    
        self.calibration_handler.confirm_calibration = False
        self.current_frame_number = 0
        self.exporter.stop_session()
        
        self.gui.video_canvas_label.clear()
        self.gui.plot_widget.clear()

        logger.info("===Starting a new mission===")
        logger.info("Disconnecting Signals...")
        self.disconnect_signals()
        logger.info("Initializing handlers...")
        self.reset_handlers()
        logger.info("Connecting Signals...")
        self.reset_signals()
        logger.info("Updating Guidance...")
        self.update_guidance()

        # If we get here, either data was saved or user confirmed reset
        QMessageBox.information(self.gui, "Info", "Application reset for new mission.")

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

            # Get frame dimensions and FPS from the active video thread
            frame_width, frame_height = self.video_thread.get_frame_dimensions()
            fps = self.video_thread.get_fps() if hasattr(self.video_thread, "get_fps") else 30.0
            
            # Default to 30.0 if thread returns 0 or invalid FPS
            if fps <= 0:
                fps = 30.0

            # Start recording
            success = self.video_recorder.start_recording(
                video_directory,
                video_filename,
                frame_width,
                frame_height,
                fps,
                getattr(self.video_thread, "is_video_file", False),
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
                self.gui.record_button.setText("  Start Video Recording")
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
