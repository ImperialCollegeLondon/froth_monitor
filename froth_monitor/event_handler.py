"""Froth Tracker Application Event Handler.

This module connects the GUI components with the functional logic of the application.
It handles events triggered by user interactions with the GUI and manages the underlying
data processing and analysis.
"""

import cv2
import sys
import os
import time
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
from PySide6.QtCore import QTimer, Qt, QRect
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtGui import QIcon

# Import MainGUIWindow at the beginning
from froth_monitor.gui_window import MainGUIWindow

# Import FrameModel from fm_model module
from froth_monitor.fm_model import FrameModel

# Import the custom overlay widget
from froth_monitor.overlay_widget import OverlayWidget

# Import the camera thread
from froth_monitor.camera_thread import CameraThread

from froth_monitor.export import Export

# Import the video recorder module
from froth_monitor.video_recorder import VideoRecorder


class AlgorithmConfigurationHandler:
    """
    A class to handle the configuration of the velocity calculation algorithm.

    This class provides a dialog window for configuring thevelocity calculation
    algorithm. It allows the user to select an algorithm (Farneback or Lucas-Kanade) and
    adjust the parameters for the selected algorithm. The class also provides a
    method to retrieve the selected algorithm and its parameters.
    """

    def __init__(self, gui: MainGUIWindow, 
                        camera_thread: CameraThread,
                        frame_model: FrameModel):
        self.camera_thread = camera_thread
        self.overlay_widget = cast(OverlayWidget, None)

        self.frame_model = frame_model
        self.frame_model.initialize_algo_config()

        self.lk_params = dict(
            winSize=(15, 15),
            maxLevel=2,
            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03),
        )
        self.lk_valid_values = {
            "winSize": [
                (5, 5),
                (7, 7),
                (9, 9),
                (11, 11),
                (13, 13),
                (15, 15),
                (17, 17),
                (19, 19),
                (21, 21),
            ],  # Must be between 0 and 1 (exclusive)
            "maxLevel": [0, 1, 2, 3, 4, 5],  # Positive integers
            "criteria": [
                (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, "EPS|COUNT"),
                (cv2.TERM_CRITERIA_EPS, "EPS"),
                (cv2.TERM_CRITERIA_COUNT, "COUNT"),
            ],
        }
        self.of_params = dict(
            pyr_scale=0.5,
            levels=int(3),
            winsize=int(15),
            iterations=int(3),
            poly_n=int(7),
            poly_sigma=1.5,
        )
        self.of_valid_values = {
            "pyr_scale": [0.3, 0.5, 0.7, 0.9],  # Must be between 0 and 1 (exclusive)
            "levels": [1, 2, 3, 4, 5],  # Positive integers
            "winsize": [5, 7, 9, 11, 13, 15, 17, 19, 21],  # Positive odd integers
            "iterations": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],  # Positive integers
            "poly_n": [5, 7],  # Only 5 or 7
        }

        self.gui = gui

        self.previous_process_time = 0.0
        self.accumulated_process_time: list[float] = []
        self.frame_count = 0
        self.process_time_avg_30 = 0.0

        self.initUI()
        self.initialize_tool_window()
        self.camera_thread.frame_available.connect(self.process_new_frame)

    def initUI(self):
        self.dialog = QDialog(self.gui)
        self.dialog.closeEvent = lambda arg__1: self.closeEvent(arg__1)
        self.dialog.setWindowTitle("Algorithm Configuration")
        main_layout = QHBoxLayout(self.dialog)

        # Left side: Algorithm selection and parameter table
        left_layout = QVBoxLayout()
        self.algorithm_selector = QComboBox()
        left_layout.addWidget(self.algorithm_selector)
        self.param_table = QTableWidget()  # Placeholder for parameter table
        self.param_table.setStyleSheet(
            """
            background-color: white;
            color: blue; font-size: 12px; font-weight: bold; border: 1px solid #ccc;
            """
        )
        left_layout.addWidget(self.param_table)
        left_layout.addStretch()

        self.confirm_algo_button = QPushButton("Apply change")
        self.confirm_algo_button.setStyleSheet(
            """
            QPushButton {
                background-color: #4285f4;
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding: 8px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #3367d6;
            }
            """
        )
        self.confirm_algo_button.clicked.connect(self._confirm_algo)
        
        self.exit_button = QPushButton("Confirm and Exit")
        self.exit_button.setStyleSheet(
            """
            QPushButton {
                background-color: #4285f4;
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding: 8px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #3367d6;
            }
            """
        )
        self.exit_button.clicked.connect(self.dialog.close)
        left_layout.addWidget(self.confirm_algo_button)
        left_layout.addWidget(self.exit_button)
        self._add_algorithm_combo()  # Add this line

        # Right side: Video canvas and info bar
        right_layout = QVBoxLayout()
        self.video_canvas = QLabel("[Video Canvas]")  # Placeholder for video display
        self.canvas_width = 320  # Example width
        self.canvas_height = 240  # Example height
        self.video_canvas.setFixedSize(self.canvas_width, self.canvas_height)
        self.video_canvas.setStyleSheet(
            "border: 1px solid #ccc; background-color: #f0f0f0;"
        )  # Example style
        right_layout.addWidget(self.video_canvas)
        
        # Info bar
        self.info_bar = QLabel("Frame time: -- ms | Avg (15): -- ms")
        right_layout.addWidget(self.info_bar)

        main_layout.addLayout(left_layout)
        main_layout.addLayout(right_layout)
        self.dialog.setLayout(main_layout)

    def _add_algorithm_combo(self):
        self.algorithm_selector.addItems(["Farneback", "Lucas-Kanade"])
        self.algorithm_selector.setStyleSheet(
            "background-color: #4285f4; color: white; font-size: 12px; padding: 8px; \
            border-radius: 4px;"
        )
        self._update_parameter_table()
        self.algorithm_selector.currentIndexChanged.connect(
            self._update_parameter_table
        )

    def _update_parameter_table(self):
        selected_algorithm = self.algorithm_selector.currentText()

        if selected_algorithm == "Farneback":
            self.param_table.setRowCount(5)
            self.param_table.setColumnCount(1)
            self.param_table.setHorizontalHeaderLabels(["Value"])
            self.param_table.setVerticalHeaderLabels(
                ["pyr_scale", "levels", "winsize", "iterations", "poly_n"]
            )
            param_keys = list(self.of_params.keys())

            for row in range(5):
                key = param_keys[row]
                value = self.of_params[key]
                if key in self.of_valid_values:
                    combo = QComboBox()
                    for v in self.of_valid_values[key]:
                        combo.addItem(str(v))
                    combo.setCurrentText(str(value))
                    self.param_table.setCellWidget(row, 0, combo)
                else:
                    # For poly_sigma, which is not in the table but is in of_params, use QDoubleSpinBox
                    spinbox = QDoubleSpinBox()
                    spinbox.setDecimals(2)
                    spinbox.setRange(0.1, 10.0)
                    spinbox.setValue(value)
                    self.param_table.setCellWidget(row, 0, spinbox)

        if selected_algorithm == "Lucas-Kanade":
            self.param_table.setRowCount(3)
            self.param_table.setColumnCount(1)
            self.param_table.setHorizontalHeaderLabels(["Value"])
            self.param_table.setVerticalHeaderLabels(
                ["winSize", "maxLevel", "criteria"]
            )

            # winSize
            combo_win = QComboBox()
            for ws in self.lk_valid_values["winSize"]:
                combo_win.addItem(str(ws))
            combo_win.setCurrentText(str(self.lk_params["winSize"]))
            self.param_table.setCellWidget(0, 0, combo_win)

            # maxLevel
            combo_level = QComboBox()
            for lvl in self.lk_valid_values["maxLevel"]:
                combo_level.addItem(str(lvl))
            combo_level.setCurrentText(str(self.lk_params["maxLevel"]))
            self.param_table.setCellWidget(1, 0, combo_level)

            # criteria
            combo_criteria = QComboBox()
            for val, label in self.lk_valid_values["criteria"]:
                combo_criteria.addItem(label, val)
            combo_criteria.setCurrentIndex(0)  # Default to EPS|COUNT
            self.param_table.setCellWidget(2, 0, combo_criteria)

    def _confirm_algo(self):
        """
        Confirm the selected algorithm and update the GUI accordingly.
        """
        selected_algorithm = self.algorithm_selector.currentText()
        if selected_algorithm == "Farneback":
            self.of_params["pyr_scale"] = float(
                cast(QComboBox, self.param_table.cellWidget(0, 0)).currentText()
            )
            self.of_params["levels"] = int(cast(QComboBox, self.param_table.cellWidget(1, 0)).currentText())
            self.of_params["winsize"] = int(cast(QComboBox, self.param_table.cellWidget(2, 0)).currentText())
            self.of_params["iterations"] = int(cast(QComboBox, self.param_table.cellWidget(3, 0)).currentText())
            self.of_params["poly_n"] = int(cast(QComboBox, self.param_table.cellWidget(4, 0)).currentText())

            self.frame_model.confirm_algorithm_n_params(selected_algorithm, 
            self.of_params)
        if selected_algorithm == "Lucas-Kanade":
            winsize_str = cast(QComboBox, self.param_table.cellWidget(0, 0)).currentText()
            winsize_tuple = eval(winsize_str)  # Safely convert string "(15, 15)" to tuple
            self.lk_params["winSize"] = winsize_tuple
            self.lk_params["maxLevel"] = int(cast(QComboBox, self.param_table.cellWidget(1, 0)).currentText())
            criteria_val = cast(QComboBox, self.param_table.cellWidget(2, 0)).currentData()
            self.lk_params["criteria"] = (criteria_val, 10, 0.03)

            self.frame_model.confirm_algorithm_n_params(selected_algorithm, self.lk_params)
        
    def initialize_tool_window(self):

        # Initialize the video rectangle to the full canvas size
        # This will be updated when the first frame arrives
        self.video_rect = QRect(0, 0, self.canvas_width, self.canvas_height)

        # Create and set up the overlay widget
        self.overlay_widget = OverlayWidget(self.video_canvas)
        self.overlay_widget.setGeometry(self.video_rect)
        self.overlay_widget.if_algo_config = True
        self.overlay_widget.video_height = self.canvas_height
        self.overlay_widget.video_width = self.canvas_width

        # Show the overlay
        self.overlay_widget.show()
        self.overlay_active = True

        # Bring the overlay to the front
        self.overlay_widget.raise_()

    def process_new_frame(self, frame):
        """
        Process and display a new frame received from the camera thread.

        This method is called whenever a new frame is available from the camera thread.
        It processes the frame, updates the UI, and handles ROI display.

        Args:
            frame: The new frame from the camera thread
        """

        time_start = time.time()

        # Store the current frame for potential further processing
        self.current_frame = frame

        # Convert frame to QImage and scale it
        cropped_frame = self._crop_image(frame)
        qt_image = self._convert_frame_to_qimage(cropped_frame)
        scaled_image = self._scale_image_to_canvas(qt_image)

        # Create a resized frame for processing
        resized_frame = self._create_resized_frame(
            frame, scaled_image.width(), scaled_image.height()
        )

        # Only allow to let frame pass in when the previous frame has been processed
        # This is to prevent the overstacking of frames
        self.camera_thread.if_release = False
        self._process_frame_with_model(resized_frame)
        self.camera_thread.if_release = True

        # Display the frame on the canvas
        pixmap = self._display_frame_on_canvas(scaled_image)

        self.previous_process_time = time.time() - time_start
        self._update_info_bar()
    
    def _update_info_bar(self):
        """
        Update the information bar with the current frame time and average time.
        """
        self.frame_count += 1
        self.accumulated_process_time.append(self.previous_process_time)

        # Calculate the average time over the last 30 frames
        if len(self.accumulated_process_time) == 30:
            self.process_time_avg_30 = sum(self.accumulated_process_time) / 30
            self.accumulated_process_time = self.accumulated_process_time[1:]
            
        self.info_bar.setText(
            f"Frame time: {self.previous_process_time * 1000:.2f} ms |\
                 Avg (30): {self.process_time_avg_30 * 1000:.2f} ms"
        )
        self.info_bar.setStyleSheet(
            "color: black; font-size: 12px; padding: 8px; \
            border-radius: 4px;"
        )

    def _crop_image(self, frame):
        """
        Crop the frame based on the canvas size.

        Args:
            frame: The frame to be cropped

        Returns:
            The cropped frame
        """
        # Calculate the cropping coordinates
        x = (frame.shape[1] - self.canvas_width) // 2
        y = (frame.shape[0] - self.canvas_height) // 2

        # Crop the frame
        cropped_frame = frame[y : y + self.canvas_height, x : x + self.canvas_width]

        return cropped_frame
        
    def _convert_frame_to_qimage(self, frame):
        """
        Convert an OpenCV frame (BGR) to a Qt QImage (RGB).

        Args:
            frame: OpenCV frame in BGR format

        Returns:
            QImage: The converted Qt image
        """
        # Convert the frame from BGR to RGB format (OpenCV uses BGR, Qt uses RGB)
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Create a QImage from the frame data
        h, w, ch = rgb_frame.shape
        bytes_per_line = ch * w
        return QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)

    def _scale_image_to_canvas(self, qt_image):
        """
        Scale the QImage to fit the canvas while maintaining aspect ratio.

        Args:
            qt_image: The QImage to scale

        Returns:
            QImage: The scaled image
        """
        return qt_image.scaled(
            self.canvas_width, self.canvas_height, Qt.AspectRatioMode.KeepAspectRatio
        )

    def _create_resized_frame(self, frame, width, height):
        """
        Create a resized NumPy array with the specified dimensions.

        Args:
            frame: The original frame
            width: Target width
            height: Target height

        Returns:
            ndarray: Resized frame
        """
        return cv2.resize(frame, (width, height))

    def _process_frame_with_model(self, resized_frame):
        self.delta_pixels = self.frame_model.process_frame_for_algo_config(resized_frame)
        print(self.delta_pixels)
        self.overlay_widget.display_roi_for_algo_config(self.delta_pixels)

    def _display_frame_on_canvas(self, scaled_image):
        """
        Convert the QImage to a QPixmap and display it on the video canvas.

        Args:
            scaled_image: The scaled QImage to display

        Returns:
            QPixmap: The pixmap that was set on the canvas
        """
        pixmap = QPixmap.fromImage(scaled_image)
        self.video_canvas.setPixmap(pixmap)
        return pixmap

    def closeEvent(self, event):
        """
        Handle the window close event.

        This method is called when the window is closed. It releases the
        video capture and stops the timer.

        Args:
            event: The close event.
        """
        selected_algorithm = self.algorithm_selector.currentText()

        if selected_algorithm == "Farneback":
            params = self.of_params

        else:
            params = self.lk_params

        param_str = "\n".join(f"{k}: {v}" for k, v in params.items())

        QMessageBox.information(
            self.dialog,
            "Algorithm Configuration",
            f"Algorithm: {selected_algorithm}\n Parameters:\n{param_str}"
        )

        self.dialog.close()


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
        """
        Initialize the EventHandler with a reference to the GUI.

        Args:
            gui: The MainGUIWindow instance to connect with.
        """
        self.gui = gui
        self.canvas_width = self.gui.video_canvas_label.width()
        self.canvas_height = self.gui.video_canvas_label.height()

        # Initialize camera thread for event-driven frame capture
        self.camera_thread = CameraThread()
        self.camera_thread.frame_available.connect(self.process_new_frame)

        # Initialize video capture for compatibility with existing code
        self.video_capture = None  # Keep for compatibility with existing code
        self.timer = QTimer()  # Keep for compatibility with existing code

        # Parameters of the event handling logic
        self.playing = False
        self.confirm_algo = False
        self.confirm_calibration = False
        self.current_frame = None
        self.frame_width = 0
        self.frame_height = 0

        # Initialize the frame model for processing video frames
        self.frame_model = FrameModel()
        self.current_frame_number = 0
        self.export = Export(self.gui)

        # Initialize video recorder
        self.video_recorder = VideoRecorder()
        self.recording_active = False

        # Overlay related attributes
        self.overlay_widget: OverlayWidget = cast(OverlayWidget, None)
        self.overlay_active = False
        self.video_rect = QRect()

        self.if_save = False
        # Connect GUI signals to handler methods
        self.connect_signals()

    def connect_signals(self):
        """Connect GUI signals to their respective handler methods."""
        # Connect menu actions directly
        self.gui.import_button.clicked.connect(self.handle_video_import)
        self.gui.export_button.clicked.connect(self.export_settings)

        # # Connect buttons directly using the gui reference
        self.gui.play_pause_button.clicked.connect(self.pause_play)
        self.gui.add_roi_button.clicked.connect(self.add_roi)
        self.gui.algorithm_configuration.clicked.connect(
            self.open_algorithm_configuration
        )
        self.gui.confirm_arrow_button.clicked.connect(self.confirm_arrow_n_ruler)
        self.gui.save_button.clicked.connect(self.save_data)
        self.gui.record_button.clicked.connect(self.toggle_recording)
        self.gui.simple_reset_button.clicked.connect(self.reset_mission)
        self.gui.add_arrow_button.clicked.connect(self.start_arrow_drawing)
        self.gui.calibration_button.clicked.connect(self.start_ruler_calibration)
        self.gui.delete_roi_button.clicked.connect(self.delete_last_roi)

    def handle_video_import(self):
        if self.gui.webcam_radio.isChecked():
            self.load_camera_dialog()
        else:
            self.import_local_video()

    def initialize_for_local_video(self, video_capture: cv2.VideoCapture) -> None:
        """
        Read the FPS of the video from the video capture object."
        """
        self.fps_rate = video_capture.get(cv2.CAP_PROP_FPS)
        self.time_interval = int(1000 / self.fps_rate)

        self.initialze_tool_window()
        self.timer.start(self.time_interval)

    def import_local_video(self):
        """
        Open a file dialog to select a local video file and initialize video capture.
        """
        file_path, _ = QFileDialog.getOpenFileName(
            self.gui, "Open Video File", "", "Video Files (*.mp4 *.avi *.mkv)"
        )

        if file_path:
            # Store the video source for pause/resume functionality
            self.last_video_source = file_path

            # Start the camera thread with the selected video file
            if self.camera_thread.start_capture(file_path):
                # Get video properties
                self.frame_width, self.frame_height = (
                    self.camera_thread.get_frame_dimensions()
                )

                # Start playing the video
                self.playing = True
                self.initialze_tool_window()
            else:
                QMessageBox.critical(
                    self.gui, "Error", "Could not open the video file!"
                )
                return

    def load_camera_dialog(self):
        """
        Open a dialog to select and load an available camera.
        """
        available_cameras = []
        for index in range(10):  # Check up to 10 camera indices
            cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
            if cap.isOpened():
                available_cameras.append(f"Camera {index}")
                cap.release()

        if not available_cameras:
            QMessageBox.critical(self.gui, "Error", "No cameras detected!")
            return

        dialog = QDialog(self.gui)
        dialog.setWindowTitle("Select Camera")
        dialog.setMinimumWidth(300)

        layout = QVBoxLayout(dialog)

        # Camera selection dropdown
        camera_combo = QComboBox(dialog)
        camera_combo.addItems(available_cameras)
        camera_combo.setStyleSheet(
            "background-color: #4285f4; color: white; font-size: 14px; padding: 8px; \
            border-radius: 4px;"
        )
        layout.addWidget(camera_combo)

        # Confirm button
        confirm_button = QPushButton("Load Camera", dialog)
        confirm_button.clicked.connect(
            lambda: self.load_selected_camera(camera_combo, dialog)
        )
        layout.addWidget(confirm_button)

        # Show the dialog
        dialog.exec()

    def load_selected_camera(self, camera_combo, dialog):
        """
        Load the selected camera from the camera selection dialog.

        Args:
            camera_combo: QComboBox containing the camera selection.
            dialog: QDialog containing the camera selection dialog.
        """
        selected_camera = camera_combo.currentText()
        camera_index = int(selected_camera.split(" ")[1])

        # Store the camera index for pause/resume functionality
        self.last_video_source = camera_index

        # Start the camera thread with the selected camera
        if self.camera_thread.start_capture(camera_index):
            # Get video properties
            self.frame_width, self.frame_height = (
                self.camera_thread.get_frame_dimensions()
            )

            # Start playing the video
            self.playing = True
            self.initialze_tool_window()
            # Close the dialog
            dialog.accept()
        else:
            QMessageBox.critical(
                self.gui, "Error", "Could not open the selected camera!"
            )
            return

    def open_algorithm_configuration(self):
        """
        Open a dialog to configure the velocity calculation algorithm.
        """
        if not self.camera_thread.is_running():
            QMessageBox.warning(self.gui, "Warning", "No video source loaded!")
            return

        dialog = AlgorithmConfigurationHandler(self.gui, 
                                                self.camera_thread, 
                                                self.frame_model)
        dialog.dialog.exec()
        pass

    def pause_play(self):
        """
        Toggle between playing and pausing the video.
        """

        def resource_path(relative_path):
            if hasattr(sys, "_MEIPASS"):
                return os.path.join(sys._MEIPASS, relative_path)  # type: ignore
            return relative_path

        if not self.camera_thread.is_running() and not self.playing:
            QMessageBox.warning(self.gui, "Warning", "No video source loaded!")
            return

        if self.playing:
            # Pause the video using the camera thread's pause method
            # This keeps the video source open but stops emitting frames
            self.camera_thread.pause()
            self.playing = False
            self.gui.statusBar().showMessage("Video paused")
            # Change icon to play icon when paused
            self.gui.play_pause_button.setIcon(
                QIcon(resource_path("froth_monitor/resources/play_icon.ico"))
            )
        else:
            # If the thread is running but paused, just resume it
            if self.camera_thread.is_running() and self.camera_thread.is_paused():
                self.camera_thread.resume()
                self.playing = True
                self.gui.statusBar().showMessage("Video resumed")
                # Change icon to pause icon when playing
                self.gui.play_pause_button.setIcon(
                    QIcon(resource_path("froth_monitor/resources/pause_icon.ico"))
                )

            # If the thread is not running, we need to restart it
            elif hasattr(self, "last_video_source"):
                self.camera_thread.start_capture(self.last_video_source)
                self.playing = True
                self.gui.statusBar().showMessage("Video started")
            else:
                QMessageBox.warning(self.gui, "Warning", "Cannot resume video!")
                return

    def initialze_tool_window(self):
        if not self.playing:
            return

        # Get the dimensions of the video canvas
        canvas_width = self.gui.video_canvas_label.width()
        canvas_height = self.gui.video_canvas_label.height()

        # Initialize the video rectangle to the full canvas size
        # This will be updated when the first frame arrives
        self.video_rect = QRect(0, 0, canvas_width, canvas_height)

        # Create and set up the overlay widget
        self.overlay_widget = OverlayWidget(self.gui.video_container)

        # Connect the ROI created signal to our handler
        self.overlay_widget.roi_created.connect(self.handle_roi_created)
        # Connect the ruler measurement signal to our handler
        self.overlay_widget.ruler_measured.connect(self.handle_ruler_measurement)
        self.overlay_widget.arrow_drawn.connect(self.handle_arrow_drawing)

        self.overlay_widget.setGeometry(self.video_rect)
        print("Geometry of the overlay widget:", self.overlay_widget.geometry())
        print("Geometry of the video container:", self.gui.video_container.geometry())
        print(
            "Geometry of the video canvas label:",
            self.gui.video_canvas_label.geometry(),
        )

        # Show the overlay
        self.overlay_widget.show()
        self.overlay_active = True

        # Bring the overlay to the front
        self.overlay_widget.raise_()

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
        self.confirm_calibration = False
        self.confirm_algo = False
        self.current_frame_number = 0
        self.camera_thread.reset()
        self.gui.video_canvas_label.clear()
        self.gui.plot_widget.clear()
        self.frame_model.reset()
        self.overlay_widget.reset()

    # -----------------------------------Frame Processing-----------------------------------------------
    def process_new_frame(self, frame):
        """
        Process and display a new frame received from the camera thread.

        This method is called whenever a new frame is available from the camera thread.
        It processes the frame, updates the UI, and handles ROI display.

        Args:
            frame: The new frame from the camera thread
        """
        if not self.playing:
            return

        # Store the current frame for potential further processing
        self.current_frame = frame

        # Convert frame to QImage and scale it
        qt_image = self._convert_frame_to_qimage(frame)
        scaled_image = self._scale_image_to_canvas(qt_image)

        # Create a resized frame for processing
        resized_frame = self._create_resized_frame(
            frame, scaled_image.width(), scaled_image.height()
        )

        # Process the frame with the frame model

        # Only allow to let frame pass in when the previous frame has been processed
        # This is to prevent the overstacking of frames
        self.camera_thread.if_release = False
        self._process_frame_with_model(resized_frame)
        self.camera_thread.if_release = True

        # Display the frame on the canvas
        pixmap = self._display_frame_on_canvas(scaled_image)

        # Update the overlay position
        self._update_overlay_position(pixmap)

        # Record frame if recording is active
        if self.recording_active and self.video_recorder.is_active():
            self.video_recorder.record_frame(frame)

        # Update status bar
        self._update_status_bar()

    def _convert_frame_to_qimage(self, frame):
        """
        Convert an OpenCV frame (BGR) to a Qt QImage (RGB).

        Args:
            frame: OpenCV frame in BGR format

        Returns:
            QImage: The converted Qt image
        """
        # Convert the frame from BGR to RGB format (OpenCV uses BGR, Qt uses RGB)
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Create a QImage from the frame data
        h, w, ch = rgb_frame.shape
        bytes_per_line = ch * w
        return QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)

    def _scale_image_to_canvas(self, qt_image):
        """
        Scale the QImage to fit the canvas while maintaining aspect ratio.

        Args:
            qt_image: The QImage to scale

        Returns:
            QImage: The scaled image
        """
        return qt_image.scaled(
            self.canvas_width, self.canvas_height, Qt.AspectRatioMode.KeepAspectRatio
        )

    def _create_resized_frame(self, frame, width, height):
        """
        Create a resized NumPy array with the specified dimensions.

        Args:
            frame: The original frame
            width: Target width
            height: Target height

        Returns:
            ndarray: Resized frame
        """
        return cv2.resize(frame, (width, height))

    def _process_frame_with_model(self, resized_frame):
        """
        Process the frame with the frame model and display ROIs.

        Args:
            resized_frame: The resized frame to process
        """
        self.current_frame_number, roi_list, update_velo_plot, update_average_velo = (
            self.frame_model.process_frame(resized_frame)
        )
        self.display_roi(roi_list)

        # Update the velocity plot with the latest data
        if update_velo_plot:
            self.update_velocity_plot()

        # Update the average velocity label
        if update_average_velo:
            self.update_ave_velo_table()

    def _display_frame_on_canvas(self, scaled_image):
        """
        Convert the QImage to a QPixmap and display it on the video canvas.

        Args:
            scaled_image: The scaled QImage to display

        Returns:
            QPixmap: The pixmap that was set on the canvas
        """
        pixmap = QPixmap.fromImage(scaled_image)
        self.gui.video_canvas_label.setPixmap(pixmap)
        return pixmap

    def _update_overlay_position(self, pixmap):
        """
        Update the position and size of the overlay widget based on the video dimensions.

        Args:
            pixmap: The pixmap displayed on the canvas
        """
        if pixmap.width() < self.canvas_width or pixmap.height() < self.canvas_height:
            # Calculate the position of the video within the canvas (centered)
            x_offset = (self.canvas_width - pixmap.width()) // 2
            y_offset = (self.canvas_height - pixmap.height()) // 2
            self.video_rect = QRect(x_offset, y_offset, pixmap.width(), pixmap.height())

            # Update overlay widget geometry if it exists
            if self.overlay_widget and self.overlay_active:
                self.overlay_widget.setGeometry(self.video_rect)
        else:
            # Video fills the canvas
            self.video_rect = QRect(0, 0, self.canvas_width, self.canvas_height)

    def _update_status_bar(self):
        """
        Update status bar with frame information.
        """
        if hasattr(self.gui, "statusBar"):
            self.gui.statusBar().showMessage(
                f"Frame: {self.current_frame_number} | Time: {self.frame_model.last_processed_time}"
            )

    # ------------------------------------Ruler Drawing------------------------------------------------
    def start_ruler_calibration(self):
        """Start the ruler calibration mode for measuring distances in pixels."""
        # Check if video is loaded
        if self.check_if_import() is False:
            return

        if self.confirm_calibration:
            QMessageBox.warning(
                self.gui,
                "Warning",
                "You have already confirmed the arrow and ruler. Please reset the application if you want to change them.",
            )
            return
        # Start ruler calibration mode
        self.overlay_widget.ruler_calibration()

        # Inform the user
        self.gui.statusBar().showMessage(
            "Click and drag to draw a line of 2cm for pixel measurement"
        )

    def handle_ruler_measurement(self, px):
        """Handle the ruler measurement result.

        Args:
            distance: The measured distance in pixels
        """
        distance = self.gui.px2mm_spinbox.value()
        print("Spin box value:", distance)
        print("Drawed px:", px)
        px_ratio = float(px / distance)

        self.frame_model.get_px_to_mm(px_ratio)
        self.gui.px2mm_result_textbox.setText(f"{self.frame_model.px2mm:.1f}")
        # Display the measurement result to the user
        QMessageBox.information(
            self.gui,
            "Ruler Calibration",
            f"Px to mm ratio: {self.frame_model.px2mm:.1f} per mm",
        )

        # Update the status bar
        self.gui.statusBar().showMessage(
            f"Px to mm ratio: {self.frame_model.px2mm:.1f} per mm"
        )

        # You could store this calibration value for future use if needed
        # self.calibration_value = distance

    # ------------------------------------ROi Drawing--------------------------------------------------
    def add_roi(self):
        """Add a new Region of Interest to the video."""
        # Check if video is loaded
        if not self.camera_thread.is_running():
            QMessageBox.warning(
                self.gui,
                "Warning",
                "No video source loaded! Please load a video first.",
            )
            return

        # Check if calibration is confirmed
        if not self.confirm_calibration:
            QMessageBox.warning(
                self.gui,
                "Warning",
                "Please confirm the arrow and ruler before adding ROIs.",
            )
            return

        # Create overlay widget if it doesn't exist
        if not self.overlay_widget:
            self.overlay_widget = OverlayWidget(self.gui.video_container)
            # Connect the ROI created signal to our handler
            self.overlay_widget.roi_created.connect(self.handle_roi_created)

        # Connect the ruler measurement signal to our handler
        self.overlay_widget.ruler_measured.connect(self.handle_ruler_measurement)

        # Start ROI drawing mode
        self.overlay_widget.start_roi_drawing()

        # Inform the user
        self.gui.statusBar().showMessage(
            "Click and drag to draw a Region of Interest rectangle"
        )

    def handle_roi_created(self, rect):
        """Handle the creation of a new ROI rectangle.

        Args:
            rect: QRect representing the ROI rectangle drawn by the user
        """
        # Convert the rectangle coordinates to be relative to the video dimensions
        # This is important for when the video is scaled to fit the canvas
        video_x = rect.x()
        video_y = rect.y()
        video_width = rect.width()
        video_height = rect.height()

        # Store the ROI coordinates
        roi_coords = video_x, video_y, video_width, video_height

        # For now, just print the coordinates for debugging
        print(f"ROI created at: {roi_coords}")

        # You would typically create an ROI object here and add it to your application's data model
        self.frame_model.add_roi(roi_coords)

        # Inform the user
        self.gui.statusBar().showMessage(
            f"ROI created at ({video_x}, {video_y}) with size {video_width}x{video_height}"
        )

        # You might want to hide the overlay after ROI creation
        # self.overlay_widget.hide()
        # self.overlay_active = False

    def display_roi(self, roi_list):
        """Display the Region of Interests on the video.

        Args:
            roi_list: List of ROI objects to be displayed
        """
        # Check if video is loaded
        if not self.camera_thread.is_running():
            QMessageBox.warning(
                self.gui,
                "Warning",
                "No video source loaded! Please load a video first.",
            )
            return
        self.overlay_widget.display_roi(roi_list)

    def delete_last_roi(self):
        self.frame_model.delete_last_roi()
        self.overlay_widget.update()
        self.gui.statusBar().showMessage("Last ROI deleted")

    # ------------------------------------Arrow Drawing------------------------------------------------
    def confirm_arrow_n_ruler(self):
        """Confirm the current arrow direction."""
        # Placeholder for arrow confirmation
        if self.check_if_import() is False:
            return

        if self.frame_model.px2mm is None:
            QMessageBox.warning(
                self.gui, "Warning", "Please calibrate the ruler first."
            )
            return

        try:
            arrow_direction = float(self.gui.direction_textbox.text())
            px_distance = float(self.gui.px2mm_result_textbox.text())
            self.frame_model.get_px_to_mm(px_distance)
            self.frame_model.get_overflow_direction(arrow_direction)

        except ValueError:
            print(ValueError)
            QMessageBox.warning(
                self.gui,
                "Warning",
                "Please enter valid arrow direction and px2mm values.",
            )
            return

        self.confirm_calibration = True
        QMessageBox.information(
            self.gui,
            "Info",
            "Overflow direction (arrow) and calibration (ruler) confirmed.",
        )

    def start_arrow_drawing(self):
        """Start the arrow drawing mode."""

        if self.check_if_import() is False:
            return

        # Create overlay widget if it doesn't exist
        if not self.overlay_widget:
            self.overlay_widget = OverlayWidget(self.gui.video_container)
            # Connect the signals to our handlers
            self.overlay_widget.roi_created.connect(self.handle_roi_created)
            self.overlay_widget.ruler_measured.connect(self.handle_ruler_measurement)
            self.overlay_widget.setGeometry(self.video_rect)
            self.overlay_widget.show()
            self.overlay_active = True

        if self.confirm_calibration:
            QMessageBox.warning(
                self.gui,
                "Warning",
                "You have already confirmed the arrow and ruler. Please reset the application if you want to change them.",
            )
            return

        # Start ruler calibration mode
        self.overlay_widget.start_arrow_drawing()

        # Inform the user
        self.gui.statusBar().showMessage(
            "Click and drag to draw a line of 2cm for pixel measurement"
        )

    def handle_arrow_drawing(self, start_pos, end_pos, degree):
        # Placeholder for arrow drawing result handling
        """Handle the ruler measurement result.

        Args:
            distance: The measured distance in pixels
        """

        self.frame_model.get_overflow_direction(degree)
        self.gui.direction_textbox.setText(f"{degree:.2f}")

        # Display the measurement result to the user
        QMessageBox.information(
            self.gui,
            "Arrow drawed",
            f"angle: {degree:.1f} degrees (from the horizontal axis anticlockwisely)",
        )

        # Update the status bar
        self.gui.statusBar().showMessage(f"arrow angle: {degree:.1f} degrees")

    def toggle_recording(self):
        """Start or stop video recording."""
        # Check if video is loaded
        if not self.camera_thread.is_running():
            QMessageBox.warning(
                self.gui,
                "Warning",
                "No video source loaded! Please load a video first.",
            )
            return

        if not self.export.finish_save_setting:
            QMessageBox.warning(
                self.gui,
                "Export Error",
                "Please configure export settings before recording.",
            )
            return

        if not self.recording_active:
            # Start recording
            # Get video directory and filename from export settings
            video_directory = self.export.video_directory
            video_filename = self.export.video_filename

            # If no directory is set, use a default directory
            if not video_directory:
                video_directory = os.path.join(
                    os.path.expanduser("~"), "Videos", "FrothMonitor"
                )
                self.export.video_directory = video_directory

            # Get frame dimensions and FPS
            fps = 120.0
            frame_width, frame_height = self.camera_thread.get_frame_dimensions()
            if self.camera_thread.is_video_file:
                fps = self.camera_thread.get_fps()

            # Start recording
            success = self.video_recorder.start_recording(
                video_directory,
                video_filename,
                frame_width,
                frame_height,
                fps,
                self.camera_thread.is_video_file,
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

        self.export.export_setting_window()

    def check_if_import(self) -> bool:
        """Check if a video file is being imported."""

        if not self.camera_thread.is_running():
            QMessageBox.warning(
                self.gui,
                "Warning",
                "No video source loaded! Please load a video first.",
            )
            return False
        else:
            return True

    def save_data(self):
        """Save the current analysis data."""
        self.if_save = self.export.excel_results(
            self.frame_model.roi_list, self.frame_model.degree, self.frame_model.px2mm
        )

    # ------------------------------------Plotting Functions------------------------------------------
    def update_velocity_plot(self):
        """Update the velocity plot with data from all ROIs.

        This method extracts velocity history data from each ROI in the frame_model's roi_list
        and plots it on the plot_widget. Each ROI's velocity history is plotted as a separate
        line with a different color and labeled in the legend.

        The plot displays a fixed window of 30 elements (3 seconds) with new data appearing
        from the right edge and older data scrolling to the left. When the history exceeds
        30 elements, the oldest elements are removed to maintain the fixed window size.
        """
        # Clear the plot widget
        self.gui.plot_widget.clear()

        # Check if there are any ROIs to plot
        if not self.frame_model.roi_list:
            return

        # Define a list of colors for different ROIs
        colors = [
            "r",
            "g",
            "b",
            "c",
            "m",
            "y",
            "w",
        ]  # Red, green, blue, cyan, magenta, yellow, white

        # Fixed window size (3 seconds)
        WINDOW_SIZE = 30

        # Find the maximum velocity across all ROIs for y-axis scaling
        max_velocity = 0
        if self.frame_model.roi_list and any(
            roi.velo_only_history for roi in self.frame_model.roi_list
        ):
            max_velocity = max(
                max(roi.velo_only_history) if roi.velo_only_history else 0
                for roi in self.frame_model.roi_list
            )

        # Plot velocity history for each ROI
        for i, roi in enumerate(self.frame_model.roi_list):
            # Skip if no velocity history
            if not roi.velo_only_history:
                continue

            # Get color for this ROI (cycle through colors if more ROIs than colors)
            color = colors[i % len(colors)]

            # Get the velocity history data
            history = roi.velo_only_history

            # Limit history to the most recent WINDOW_SIZE elements
            if len(history) > WINDOW_SIZE:
                history = history[-WINDOW_SIZE:]

            # Create a fixed-size array for display (30 elements)
            display_data = [None] * WINDOW_SIZE

            # Position the data at the right side of the display
            # For example, if we have 5 elements, they go in positions 25-29 (0-indexed)
            start_pos = WINDOW_SIZE - len(history)
            for j, value in enumerate(history):
                display_data[start_pos + j] = value

            # Create x-axis data (fixed range from 0 to WINDOW_SIZE-1)
            x_data = list(range(WINDOW_SIZE))

            # Create y-axis data with None values filtered out for plotting
            # (pyqtgraph will skip None values when plotting)
            plot_x = []
            plot_y = []
            for x, y in zip(x_data, display_data):
                if y is not None:
                    plot_x.append(x)
                    plot_y.append(y)

            # Add the plot with a label for the legend
            if plot_x and plot_y:  # Only plot if we have data
                self.gui.plot_widget.plot(
                    plot_x, plot_y, pen=color, name=f"ROI {i + 1}"
                )

        # Set fixed x-axis range (0 to WINDOW_SIZE-1)
        self.gui.plot_widget.setXRange(0, WINDOW_SIZE - 1)

        # Set appropriate y-axis range if there's data
        if max_velocity > 0:
            # Add some padding to the top of the y-axis
            self.gui.plot_widget.setYRange(0, max_velocity * 1.1)

        # Update the plot
        self.gui.plot_widget.update()

    def update_ave_velo_table(self):
        """Update the average velocity table with data from all ROIs."""
        # Clear the table
        self.gui.table_widget.clear()
        self.gui.table_widget.setRowCount(len(self.frame_model.roi_list))

        list_data = []
        # Add data to the table
        for i, roi in enumerate(self.frame_model.roi_list):
            # Skip if no velocity history
            if roi.average_velocity_past_30s is None:
                list_data.append("N/A")
                continue

            print(list_data)
            # Add average velocity to the table
            list_data.append(roi.average_velocity_past_30s)

        self.gui.table_widget.setData(list_data)
        self.gui.table_widget.setHorizontalHeaderLabels(["mean_velocity  "])
        self.gui.table_widget.setFormat("%.2f")
        self.gui.table_widget.setColumnWidth(0, 120)
        # self.table_widget.setColumnWidth(1, 100)
        self.gui.table_widget.setFixedHeight(200)


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
