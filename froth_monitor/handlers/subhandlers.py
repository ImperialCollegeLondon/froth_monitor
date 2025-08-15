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
from PySide6.QtCore import Qt, QRect, QObject, Signal, QTimer
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtGui import QIcon

# Import MainGUIWindow at the beginning
from froth_monitor.handlers.gui_window import MainGUIWindow

# Import FrameModel from fm_model module
from froth_monitor.processing.fm_model import FrameModel, ROI

# Import the custom overlay widget
from froth_monitor.handlers.overlay_widget import OverlayWidget

# Import the camera and network threads
from froth_monitor.video_threads.camera_thread import CameraThread
from froth_monitor.video_threads.network_thread import NetworkThread
from froth_monitor.lidar_thread.lidar_data_processor import LidarDataProcessor
from froth_monitor.lidar_thread.lidar_control_dialog import LidarControlDialog
from froth_monitor.air_recovery import AirRecoveryDataProcessor

from froth_monitor.handlers.export import Export

# Import the video recorder module
from froth_monitor.handlers.video_recorder import VideoRecorder
# from froth_monitor.event_handler import EventHandler
from froth_monitor.handlers.logger_config import get_logger

# Initialize logger for this module
logger = get_logger(__name__)

class AlgorithmConfigurationHandler:
    """
    A class to handle the configuration of the velocity calculation algorithm.

    This class provides a dialog window for configuring thevelocity calculation
    algorithm. It allows the user to select an algorithm (Farneback or Lucas-Kanade) and
    adjust the parameters for the selected algorithm. The class also provides a
    method to retrieve the selected algorithm and its parameters.
    """

    def __init__(
        self, gui: MainGUIWindow, video_thread: NetworkThread | CameraThread, frame_model: FrameModel
    ):
        self.video_thread = video_thread
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
        self.video_thread.frame_available.connect(self.process_new_frame)

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
            self.of_params["levels"] = int(
                cast(QComboBox, self.param_table.cellWidget(1, 0)).currentText()
            )
            self.of_params["winsize"] = int(
                cast(QComboBox, self.param_table.cellWidget(2, 0)).currentText()
            )
            self.of_params["iterations"] = int(
                cast(QComboBox, self.param_table.cellWidget(3, 0)).currentText()
            )
            self.of_params["poly_n"] = int(
                cast(QComboBox, self.param_table.cellWidget(4, 0)).currentText()
            )

            self.frame_model.confirm_algorithm_n_params(
                selected_algorithm, self.of_params
            )
        if selected_algorithm == "Lucas-Kanade":
            winsize_str = cast(
                QComboBox, self.param_table.cellWidget(0, 0)
            ).currentText()
            winsize_tuple = eval(
                winsize_str
            )  # Safely convert string "(15, 15)" to tuple
            self.lk_params["winSize"] = winsize_tuple
            self.lk_params["maxLevel"] = int(
                cast(QComboBox, self.param_table.cellWidget(1, 0)).currentText()
            )
            criteria_val = cast(
                QComboBox, self.param_table.cellWidget(2, 0)
            ).currentData()
            self.lk_params["criteria"] = (criteria_val, 10, 0.03)

            self.frame_model.confirm_algorithm_n_params(
                selected_algorithm, self.lk_params
            )

        QMessageBox.information(
            self.dialog,
            "Algorithm Changed",
            "The new configuration has been applied.",
        )

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
        self.video_thread.if_release = False
        self._process_frame_with_model(resized_frame)
        self.video_thread.if_release = True

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
        self.delta_pixels = self.frame_model.process_frame_for_algo_config(
            resized_frame
        )
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
            f"Algorithm: {selected_algorithm}\n Parameters:\n{param_str}",
        )

        self.dialog.close()

class VideoHandler:
    def __init__(
        self,
        event_handler,
        gui: MainGUIWindow,
        frame_model: FrameModel,
        video_thread: NetworkThread
    ):
        self.gui = gui
        self.event_handler = event_handler
        self.frame_model = frame_model
        self.video_thread = video_thread

        # Add missing state variables
        self.playing = False
        self.frame_width = 0
        self.frame_height = 0
        self.last_video_source = None

        self.jetson_source_address = "0.0.0.0"
        self.jetson_source_port = 5001

    def handle_video_import(self):
        self.import_jetson_video()

    def import_jetson_video(self):
        self.event_handler.if_jetson = True
        
        # Connect the signal BEFORE starting network capture
        self.video_thread.connection_status_changed.connect(
            lambda connected, message: self.event_handler.handle_network_connection_status(connected, message)
        )

        # Start network capture
        if self.video_thread.start_network_capture(self.jetson_source_address,
                self.jetson_source_port):
            self.playing = True
            self.event_handler.trigger_jetson_mode()

        else:
            QMessageBox.critical(
                self.gui, "Error", "Failed to start network capture."
            )

    def pause_play(self):
        """
        Toggle between playing and pausing the video.
        """

        def resource_path(relative_path):
            if hasattr(sys, "_MEIPASS"):
                return os.path.join(sys._MEIPASS, relative_path)  # type: ignore
            return relative_path
        print(self.video_thread.is_running(), self.playing)

        if not self.video_thread.is_running() and not self.playing:
            QMessageBox.warning(self.gui, "Warning", "No video source loaded!")
            return

        if self.playing:
            # Pause the video using the camera thread's pause method
            # This keeps the video source open but stops emitting frames
            self.video_thread.pause()
            self.playing = False
            self.gui.statusBar().showMessage("Video paused")
            # Change icon to play icon when paused
            self.gui.play_pause_button.setIcon(
                QIcon(resource_path("froth_monitor/gui_resources/play_icon.ico"))
            )
        else:
            # If the thread is running but paused, just resume it
            if self.video_thread.is_running() and self.video_thread.is_paused():
                self.video_thread.resume()
                self.playing = True
                self.gui.statusBar().showMessage("Video resumed")
                # Change icon to pause icon when playing
                self.gui.play_pause_button.setIcon(
                    QIcon(resource_path("froth_monitor/gui_resources/pause_icon.ico"))
                )

            # If the thread is not running, we need to restart it
            elif hasattr(self, "last_video_source"):
                if self.event_handler.if_jetson:
                    self.video_thread.start_network_capture( # type: ignore
                        self.jetson_source_address, self.jetson_source_port
                    )
                else:
                    self.video_thread.start_capture(self.last_video_source) # type: ignore
                # self.camera_thread.start_capture(self.last_video_source)
                self.playing = True
                self.gui.statusBar().showMessage("Video started")
            else:
                QMessageBox.warning(self.gui, "Warning", "Cannot resume video!")
                return

class CalibrationHandler(QObject):
    """Handles ruler calibration and arrow direction setup."""

    calibration_confirmed = Signal()
    def __init__(self, gui, frame_model, overlay_widget):
        super().__init__()
        self.gui = gui
        self.frame_model = frame_model
        self.overlay_widget = overlay_widget
        self.confirm_calibration = False

    # ------------------------------------Ruler Drawing------------------------------------------------
    def start_ruler_calibration(self):
        """Start the ruler calibration mode for measuring distances in pixels."""

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

    # ------------------------------------Arrow Drawing------------------------------------------------
    def confirm_arrow_n_ruler(self):
        """Confirm the current arrow direction."""

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
        self.calibration_confirmed.emit()
        QMessageBox.information(
            self.gui,
            "Info",
            "Overflow direction (arrow) and calibration (ruler) confirmed.",
        )

    def start_arrow_drawing(self):
        """Start the arrow drawing mode."""

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

class OverlayHandler:
    def __init__(self, gui, event_handler) -> None:
        self.gui = gui
        self.overlay_widget = OverlayWidget(self.gui)
        self.event_handler = event_handler

    def initialize_tool_window(self):
        # Get the dimensions of the video canvas
        canvas_width = self.gui.video_canvas_label.width()
        canvas_height = self.gui.video_canvas_label.height()

        # Initialize the video rectangle to the full canvas size
        # This will be updated when the first frame arrives
        self.video_rect = QRect(0, 0, canvas_width, canvas_height)

        # Create and set up the overlay widget
        self.overlay_widget = OverlayWidget(self.gui.video_canvas_label)

        self.overlay_widget.setGeometry(self.video_rect)
        # print("Geometry of the overlay widget:", self.overlay_widget.geometry())
        # print("Geometry of the video container:", self.gui.video_container.geometry())
        # print("Geometry of the video canvas label:",self.gui.video_canvas_label.geometry())

        # Show the overlay
        self.overlay_widget.show()
        self.overlay_active = True
        # Bring the overlay to the front
        self.overlay_widget.raise_()

class ROIHandler:
    def __init__(
        self,
        event_handler,
        gui: MainGUIWindow,
        frame_model: FrameModel,
        video_thread: CameraThread | NetworkThread,
        overlay_widget: OverlayWidget,
    ):
        self.gui = gui
        self.event_handler = event_handler
        self.video_thread = video_thread
        self.frame_model = frame_model
        self.overlay_widget = overlay_widget

    # ------------------------------------ROi Drawing--------------------------------------------------
    def add_roi(self):
        """Add a new Region of Interest to the video."""
        # Check if video is loaded
        if not self.video_thread.is_running():
            QMessageBox.warning(
                self.gui,
                "Warning",
                "No video source loaded! Please load a video first.",
            )
            return

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

        # You would typically create an ROI object here and add it to your application's data model
        self.frame_model.add_roi(roi_coords)

        # Inform the user
        self.gui.statusBar().showMessage(
            f"ROI created at ({video_x}, {video_y}) with size {video_width}x{video_height}"
        )

    def display_roi(self, roi_list):
        """Display the Region of Interests on the video.

        Args:
            roi_list: List of ROI objects to be displayed
        """
        # Check if video is loaded
        if not self.video_thread.is_running():
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

class DataHandler:
    def __init__(self, gui: MainGUIWindow, frame_model: FrameModel,
    lidar_data_processor: LidarDataProcessor, air_recovery_data_processor: AirRecoveryDataProcessor):
        self.gui = gui
        self.frame_model = frame_model
        self.plot_widget = self.gui.plot_widget
        self.lidar_data_processor = lidar_data_processor
        self.air_recovery_data_processor = air_recovery_data_processor

        self.if_lidar = False
        self.if_air_rec = False

        self.table_list_data = []
        self.frame_lidar_hist = []

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
        import numpy as np

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

        # Helper function to sanitize velocity data
        def sanitize_velocity_data(data):
            """Remove invalid values (inf, nan, extremely large values) from velocity data."""
            sanitized = []
            for value in data:
                if value is not None and np.isfinite(value) and abs(value) < 1e6:
                    sanitized.append(value)
                else:
                    sanitized.append(0.0)  # Replace invalid values with 0
            return sanitized

        # Find the maximum velocity across all ROIs for y-axis scaling
        max_velocity = 0
        if self.frame_model.roi_list and any(
            roi.velo_only_history for roi in self.frame_model.roi_list
        ):
            all_velocities = []
            for roi in self.frame_model.roi_list:
                if roi.velo_only_history:
                    sanitized_history = sanitize_velocity_data(roi.velo_only_history)
                    all_velocities.extend(sanitized_history)

            if all_velocities:
                max_velocity = max(all_velocities)

        # Plot velocity history for each ROI
        for i, roi in enumerate(self.frame_model.roi_list):
            # Skip if no velocity history
            if not roi.velo_only_history:
                continue

            # Get color for this ROI (cycle through colors if more ROIs than colors)
            color = colors[i % len(colors)]

            # Get the velocity history data and sanitize it
            history = sanitize_velocity_data(roi.velo_only_history)

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
                if y is not None and np.isfinite(y):
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
        if max_velocity > 0 and np.isfinite(max_velocity):
            # Add some padding to the top of the y-axis
            self.gui.plot_widget.setYRange(0, max_velocity * 1.1)

        # Update the plot
        self.gui.plot_widget.update()

    def update_velo_table(self):
        """Update the average velocity table with data from all ROIs."""
        # Clear the table

        logger.info(f'update_velo_table...')

        # Add data to the table
        for i, roi in enumerate(self.frame_model.roi_list):
            if self.if_lidar and len(self.lidar_data_processor.reading_history_av1s) > 1:
                # Start asynchronous matching - results will be handled by signal callbacks
                self.start_matching_velo_n_lidar(i, roi, len(roi.delta_history)-2)

    def update_arec_tablengraph(self):
        import numpy as np

        table_list_data = []

        for i, roi in enumerate(self.frame_model.roi_list):
            timestamp = roi.sum_history[len(roi.sum_history)-1][0][:8]
            list_data_a = roi.sum_history[len(roi.sum_history)-1][1:4]
            logger.info(f'selected summary history of the roi: {list_data_a}')
            # timestamp, velocity, froth_height, air_recovery, air flow rate, crcted air flrt
            table_list_data.append([timestamp] + list_data_a)

        self.gui.velo_widget.setData(table_list_data)
        self.gui.velo_widget.setHorizontalHeaderLabels(["timestamp", "v(mm/s)", "f_height(mm)", "air_rec(%)"])
        self.gui.velo_widget.setFormat("%.2f")
        self.gui.velo_widget.setMinimumHeight(110)
        self.gui.velo_widget.setColumnWidth(0, 65)
        self.gui.velo_widget.setColumnWidth(1, 65)
        self.gui.velo_widget.setColumnWidth(2, 65)
        self.gui.velo_widget.setColumnWidth(3, 65)

        self.gui.velo_widget.setStyleSheet(
            """
            background-color: #f0f0f0;
            font-size: 10px;
            border: 1px solid #ccc;
            border-radius: 4px;
            """
        )

        # Update air recovery plot with data from all ROIs
        self._update_air_recovery_plot()

    def _update_air_recovery_plot(self):
        """Update the air recovery plot with data from all ROIs.

        This method extracts air recovery history data from each ROI in the frame_model's roi_list
        and plots it on the ar_plot_widget. Each ROI's air recovery history is plotted as a separate
        line with a different color and labeled in the legend.

        The plot displays a fixed window of 30 elements (3 seconds) with new data appearing
        from the right edge and older data scrolling to the left. When the history exceeds
        30 elements, the oldest elements are removed to maintain the fixed window size.
        """
        import numpy as np

        # Clear the air recovery plot widget
        self.gui.ar_plot_widget.clear()

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

        # Helper function to sanitize air recovery data
        def sanitize_air_recovery_data(data):
            """Remove invalid values (inf, nan, extremely large values) from air recovery data."""
            sanitized = []
            for value in data:
                if value is not None and np.isfinite(value) and abs(value) < 1e6:
                    sanitized.append(value)
                else:
                    sanitized.append(0.0)  # Replace invalid values with 0
            return sanitized

        # Extract air recovery history from sum_history (4th element, index 3)
        def extract_air_recovery_history(roi):
            """Extract air recovery values from roi.sum_history."""
            air_recovery_history = []
            for entry in roi.sum_history:
                if len(entry) > 3:  # Ensure air_recovery exists (4th element)
                    air_recovery_history.append(entry[3])  # air_recovery is at index 3
                else:
                    air_recovery_history.append(0.0)  # Default value if not available
            return air_recovery_history

        # Find the maximum air recovery across all ROIs for y-axis scaling
        max_air_recovery = 0
        if self.frame_model.roi_list and any(
            roi.sum_history for roi in self.frame_model.roi_list
        ):
            all_air_recoveries = []
            for roi in self.frame_model.roi_list:
                if roi.sum_history:
                    air_recovery_history = extract_air_recovery_history(roi)
                    sanitized_history = sanitize_air_recovery_data(air_recovery_history)
                    all_air_recoveries.extend(sanitized_history)

            if all_air_recoveries:
                max_air_recovery = max(all_air_recoveries)

        # Plot air recovery history for each ROI
        for i, roi in enumerate(self.frame_model.roi_list):
            # Skip if no sum_history
            if not roi.sum_history:
                continue

            # Get color for this ROI (cycle through colors if more ROIs than colors)
            color = colors[i % len(colors)]

            # Get the air recovery history data and sanitize it
            air_recovery_history = extract_air_recovery_history(roi)
            history = sanitize_air_recovery_data(air_recovery_history)

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
                if y is not None and np.isfinite(y):
                    plot_x.append(x)
                    plot_y.append(y)

            # Add the plot with a label for the legend
            if plot_x and plot_y:  # Only plot if we have data
                self.gui.ar_plot_widget.plot(
                    plot_x, plot_y, pen=color, name=f"ROI {i + 1}"
                )

        # Set fixed x-axis range (0 to WINDOW_SIZE-1)
        self.gui.ar_plot_widget.setXRange(0, WINDOW_SIZE - 1)

        # Set appropriate y-axis range if there's data
        if max_air_recovery > 0 and np.isfinite(max_air_recovery):
            # Add some padding to the top of the y-axis
            self.gui.ar_plot_widget.setYRange(0, max_air_recovery * 1.1)

        # Update the plot
        self.gui.ar_plot_widget.update()

    def update_fh_plot(self, lidar_reading_history_av1s_only_v):
        """Update the velocity plot with data from all ROIs.

        This method extracts velocity history data from each ROI in the frame_model's roi_list
        and plots it on the plot_widget. Each ROI's velocity history is plotted as a separate
        line with a different color and labeled in the legend.

        The plot displays a fixed window of 30 elements (3 seconds) with new data appearing
        from the right edge and older data scrolling to the left. When the history exceeds
        30 elements, the oldest elements are removed to maintain the fixed window size.
        """
        import numpy as np

        # Clear the plot widget
        self.gui.froth_height_plot_widget.clear()

        # Check if there are any ROIs to plot
        if not lidar_reading_history_av1s_only_v:
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

        # Helper function to sanitize froth height data
        def sanitize_data(data):
            """Remove invalid values (inf, nan, extremely large values) from data."""
            sanitized = []
            for value in data:
                if value is not None and np.isfinite(value) and abs(value) < 1e6:
                    sanitized.append(value)
                else:
                    sanitized.append(0.0)  # Replace invalid values with 0
            return sanitized

        # Sanitize the lidar reading history
        sanitized_history = sanitize_data(lidar_reading_history_av1s_only_v)

        # Find the maximum froth height for y-axis scaling
        max_fh = 0
        if sanitized_history:
            max_fh = max(sanitized_history)

        # Get the velocity history data
        history = sanitized_history

        # Limit history to the most recent WINDOW_SIZE elements
        if len(history) > WINDOW_SIZE:
            history = history[-WINDOW_SIZE:]

        # Create a fixed-size array for display (30 elements)
        display_data = [None] * WINDOW_SIZE

        # Position the data so newest values appear on the right side
        # Fill from the right side of the array (highest indices)
        start_pos = WINDOW_SIZE - len(history)
        for j, value in enumerate(history):
            display_data[start_pos + j] = value

        # Create x-axis data - higher x-values are on the right
        x_data = list(range(WINDOW_SIZE))

        # Create y-axis data with None values filtered out for plotting
        # (pyqtgraph will skip None values when plotting)
        plot_x = []
        plot_y = []
        for x, y in zip(x_data, display_data):
            if y is not None and np.isfinite(y):
                plot_x.append(x)
                plot_y.append(y)

        # Add the plot with a label for the legend
        if plot_x and plot_y:  # Only plot if we have data
            self.gui.froth_height_plot_widget.plot(
                plot_x, plot_y, pen=colors[2], name=f"froth height"
            )

        # Set fixed x-axis range (0 to WINDOW_SIZE-1)
        self.gui.froth_height_plot_widget.setXRange(0, WINDOW_SIZE - 1)

        # Set appropriate y-axis range if there's data
        if max_fh > 0 and np.isfinite(max_fh):
            # Add some padding to the top of the y-axis
            self.gui.froth_height_plot_widget.setYRange(0, max_fh * 1.1)

        # Update the plot
        self.gui.froth_height_plot_widget.update()

    def start_matching_velo_n_lidar(self, roi_number, roi, index):
        """Start asynchronous matching of velocity and lidar data.

        Args:
            velo_data: Velocity data with timestamp
        """
        if not hasattr(self, 'matcher'):
            roi.matcher = VelocityLidarMatcher(self.lidar_data_processor)
            roi.matcher.match_found.connect(self._on_match_found)
            roi.matcher.match_failed.connect(self._on_match_failed)

        logger.info(f"===Start matching frame and lidar for ROI {roi_number + 1}===")
        logger.info(f"Frame index {index}")
        roi.matcher.start_matching(roi, index)

    def _on_match_found(self, roi, velo_data, lidar_data, index):
        """Handle successful match between velocity and lidar data."""

        velo_n_fh = [velo_data, lidar_data]
        logger.info("Velocity and Froth Height Match Found:")
        logger.info(velo_n_fh)

        froth_height = lidar_data[0][1]
        velocity = velo_data[0]
        timestamp = velo_data[1]
        roi.delta_history[index][4] = froth_height
        air_rec = self.air_rec_calculation(roi, velocity, froth_height, timestamp)
        logger.info(f"Air Recovery{air_rec}")

        self.update_arec_tablengraph()

    def _on_match_failed(self, roi, velo_data, index):
        """Handle failed match between velocity and lidar data."""
        logger.info(f"No matching lidar data found for velocity timestamp: {velo_data[1][:8]}")

    def stop_matcher(self, roi):
        """Stop the velocity-lidar matcher if it exists."""
        if hasattr(roi, 'matcher'):
            roi.matcher.stop_matching()

    def air_rec_calculation(self, roi, velocity, froth_height, timestamp) -> float:
        """
        Calculate air recovery using the air recovery data processor.

        Args:
            velocity (float): Overflow velocity in mm/s
            froth_height (float): Froth height in mm

        Returns:
            float: Air recovery percentage
        """
        try:
            # Get current timestamp

            # Process data through air recovery processor
            if hasattr(self, 'air_recovery_data_processor'):
                if self.air_recovery_data_processor is not None:
                    timestamp, velocity, froth_height, air_rec, current_air_flow, current_air_flow_in_mm = \
                        self.air_recovery_data_processor.process_air_recovery_data(velocity, froth_height, timestamp) # type: ignore

                    self.roi_sum_history_append(roi, timestamp, velocity, froth_height, air_rec, current_air_flow, current_air_flow_in_mm)
                air_rec = self.air_recovery_data_processor.get_current_air_recovery()
            else:
                logger.warning("Air recovery data processor not available")
                air_rec = 0.0

            return air_rec

        except Exception as e:
            logger.error(f"Error in air recovery calculation: {e}")
            return 0.0

    def roi_sum_history_append(self, roi, timestamp, velocity, froth_height, air_rec, current_air_flow, current_air_flow_in_mm):
        roi.sum_history.append([timestamp, velocity, froth_height, air_rec, current_air_flow, current_air_flow_in_mm])

class VelocityLidarMatcher(QObject):
    """Asynchronous matcher for velocity and lidar data based on timestamps."""

    # Signals
    match_found = Signal(ROI, list, list, int)  # velo_data, lidar_data, frame index
    match_failed = Signal(ROI, list, int)  # velo_data

    def __init__(self, lidar_data_processor):
        super().__init__()
        self.lidar_data_processor = lidar_data_processor
        self.roi: ROI = cast(ROI, None)
        self.index = 0
        self.matching_timer = QTimer()
        self.matching_timer.timeout.connect(self._check_for_match)
        self.current_velo_data = None
        self.target_timestamp = None
        self.current_roi_number = 0
        self.start_time = cast(float, None)
        self.max_wait_time = 1.0  # 1 second maximum wait
        self.initial_lidar_count = 0

    def start_matching(self, roi: ROI, index):

        """Start matching process for given velocity data."""
        self.roi = roi
        self.index = index

        velo_data = roi.velo_history_with_time[-1]
        self.current_velo_data = velo_data
        self.target_timestamp = velo_data[1][:8] # Extract HH:MM:SS
        self.target_time_marker = velo_data[2]
        self.start_time = cast(float, None)

        # Get current lidar data
        lidar_history = self.lidar_data_processor.reading_history_av1s

        if not lidar_history:
            self.match_failed.emit(self.current_roi_number, velo_data)
            return

        self.initial_lidar_count = len(lidar_history)

        # Check for immediate match
        if self._check_immediate_match(lidar_history):
            return

        # Start timer for periodic checking
        self.start_time = time.time()
        self.matching_timer.start(100) # Check every 100ms

    def _check_immediate_match(self, lidar_history):
        """Check for immediate match in current lidar data."""
        latest_lidar_data = lidar_history[-1]
        latest_lidar_timestamp = latest_lidar_data[0][2][:8]  # Extract HH:MM:SS

        # Scenario 1: Exact match
        if self.target_timestamp == latest_lidar_timestamp:
            self.match_found.emit(self.roi, self.current_velo_data, latest_lidar_data, self.index)
            return True

        # Scenario 2: Lidar timestamp is later - search backwards
        elif latest_lidar_timestamp > self.target_timestamp:
            for lidar_data in reversed(lidar_history):
                lidar_ts = lidar_data[2][:8]
                if lidar_ts == self.target_timestamp:
                    self.match_found.emit(self.roi, self.current_velo_data, latest_lidar_data, self.index)
                    return True
                elif lidar_ts < self.target_timestamp:
                    break

            # No match found in history
            self.match_failed.emit(self.roi, self.current_velo_data, self.index)
            return True

        # Scenario 3: Lidar timestamp is earlier - need to wait
        return False

    def _check_for_match(self):
        """Periodic check for new lidar data during waiting period."""
        import time

        # Check timeout
        if time.time() - self.start_time > self.max_wait_time:
            self.matching_timer.stop()
            self.match_failed.emit(self.roi, self.current_velo_data, self.index)
            return

        # Check for new lidar data
        current_lidar_history = self.lidar_data_processor.reading_history_av1s
        if len(current_lidar_history) > self.initial_lidar_count:
            # New data arrived
            new_latest_data = current_lidar_history[-1]
            new_latest_timestamp = new_latest_data[0][2][:8]

            if new_latest_timestamp == self.target_timestamp:
                self.matching_timer.stop()
                self.match_found.emit(self.roi, self.current_velo_data, new_latest_data, self.index)
            elif new_latest_timestamp > self.target_timestamp:
                # Timestamp jumped past target
                self.matching_timer.stop()
                self.match_failed.emit(self.roi, self.current_velo_data, self.index)

            # Update count for next iteration
            self.initial_lidar_count = len(current_lidar_history)

    def stop_matching(self):
        """Stop the matching timer if it's running."""
        if self.matching_timer.isActive():
            self.matching_timer.stop()

class FrameProcessor:
    def __init__(
        self,
        event_handler,
        gui: MainGUIWindow,
        frame_model: FrameModel,
        video_thread: CameraThread | NetworkThread,
        overlay_widget: OverlayWidget,
        video_recorder: VideoRecorder,
        roi_handler: ROIHandler,
        velocity_plotter: DataHandler,
    ):
        self.gui = gui
        self.event_handler = event_handler
        self.frame_model = frame_model
        self.video_thread = video_thread
        self.overlay_widget = overlay_widget
        self.video_recorder = video_recorder
        self.roi_handler = roi_handler
        self.velocity_plotter = velocity_plotter

        self.canvas_width = self.gui.video_canvas_label.width()
        self.canvas_height = self.gui.video_canvas_label.height()

    # -----------------------------------Frame Processing-----------------------------------------------
    def process_new_frame(self, timestamp:str, frame):
        """
        Process and display a new frame received from the camera thread.

        This method is called whenever a new frame is available from the camera thread.
        It processes the frame, updates the UI, and handles ROI display.

        Args:
            frame: The new frame from the camera thread
        """
        if (
            not self.event_handler.video_handler.playing
        ):  # Access playing state from VideoHandler
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
        self.video_thread.if_release = False
        self._process_frame_with_model(timestamp, resized_frame)
        self.video_thread.if_release = True

        # Display the frame on the canvas
        pixmap = self._display_frame_on_canvas(scaled_image)

        # Update the overlay position
        self._update_overlay_position(pixmap)

        # Record frame if recording is active
        if self.event_handler.recording_active and self.video_recorder.is_active():
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

    def _process_frame_with_model(self, timestamp:str, resized_frame):
        """
        Process the frame with the frame model and display ROIs.

        Args:
            resized_frame: The resized frame to process
        """
        self.current_frame_number, roi_list, update_velo_plot, update_average_velo = (
            self.frame_model.process_frame(timestamp, resized_frame)
        )
        self.roi_handler.display_roi(roi_list)
        logger.info(f"if update velo plot: {update_velo_plot}")

        # Update the velocity plot with the latest data
        if update_velo_plot:
            self.velocity_plotter.update_velocity_plot()
            self.velocity_plotter.update_velo_table()

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
            if self.overlay_widget:
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

class AirRecoveryHandler:
    """Handler for air recovery functionality."""

    def __init__(self, air_recovery_data_processor, gui: MainGUIWindow, event_handler):
        self.air_recovery_data_processor = air_recovery_data_processor

        self.gui = gui
        self.gui.apply_flow_btn.clicked.connect(self.apply_main_flow_changes)

        self.event_handler = event_handler

    def main_gui_show_air_flow_rate(self):

        if self.air_recovery_data_processor.use_jg_calculation:
            logger.info("JG method is used.")
            self.gui.show_air_flow_control_panel(event = "jg_method")
            self.gui.main_jg_spin.setValue(self.air_recovery_data_processor.jg_value)
        else:
            logger.info("Direct air flow method is used")
            logger.info(f'Air flow unit is {self.air_recovery_data_processor.air_flow_unit}')
            self.gui.show_air_flow_control_panel(event = "normal_method")
            self.gui.main_flow_rate_spin.setValue(self.air_recovery_data_processor.air_flow_rate)
            self.gui.main_flow_unit_label.setText(self.air_recovery_data_processor.air_flow_unit)

    def apply_main_flow_changes(self):

        if self.air_recovery_data_processor.use_jg_calculation:
            self.air_recovery_data_processor.jg_value = self.gui.main_jg_spin.value()
        else:
            self.air_recovery_data_processor.air_flow_rate = self.gui.main_flow_rate_spin.value()

    def open_air_recovery_control(self):
        """Open the air recovery control dialog."""
        try:
            from froth_monitor.air_recovery import AirRecoveryControlDialog
            dialog = AirRecoveryControlDialog(self.air_recovery_data_processor, self.gui)
            dialog.configuration_lock.connect(self.main_gui_show_air_flow_rate)
            dialog.show()

        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(
                self.gui,
                "Error",
                f"Failed to open air recovery control dialog: {str(e)}"
            )
            logger.error(f"Error opening air recovery control dialog: {e}")

class LidarHandler:
    def __init__(self,
                lidar_data_processor: LidarDataProcessor,
                gui: MainGUIWindow,
                velocity_plotter: DataHandler,
                event_handler):
        self.gui = gui
        self.event_handler = event_handler
        self.lidar_data_processor = lidar_data_processor
        self.velocity_plotter = velocity_plotter

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
        self.velocity_plotter.if_lidar = True
        self.event_handler.if_lidar = True

    def update_fh_plot(self, lidar_reading_history_av1s_only_v):
        self.velocity_plotter.update_fh_plot(lidar_reading_history_av1s_only_v)

    def get_lidar_statistics(self):
        """Get LiDAR statistics from the data processor."""
        return self.lidar_data_processor.get_statistics()