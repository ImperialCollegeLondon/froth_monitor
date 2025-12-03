import cv2
import time
from typing import cast
from PySide6.QtWidgets import (
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
from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QImage, QPixmap

# Import MainGUIWindow at the beginning
from froth_monitor.handlers.gui_window import MainGUIWindow

# Import FrameModel from fm_model module
from froth_monitor.processing.fm_model import FrameModel, ROI

# Import the custom overlay widget
from froth_monitor.handlers.overlay_widget import OverlayWidget

# Import the camera and network threads
from froth_monitor.video_threads.camera_thread import CameraThread
from froth_monitor.video_threads.network_thread import NetworkThread

# Import the video recorder module
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
        self, parent_widget, video_thread: NetworkThread | CameraThread, frame_model: FrameModel
    ):
        self.video_thread = video_thread
        self.overlay_widget = cast(OverlayWidget, None)

        self.frame_model = frame_model
        self.frame_model.initialize_algo_config()

        self.lk_params = self.frame_model.lk_params
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
        self.of_params = self.frame_model.of_params
        self.of_valid_values = {
            "pyr_scale": [0.3, 0.5, 0.7, 0.9],  # Must be between 0 and 1 (exclusive)
            "levels": [1, 2, 3, 4, 5],  # Positive integers
            "winsize": [5, 7, 9, 11, 13, 15, 17, 19, 21],  # Positive odd integers
            "iterations": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],  # Positive integers
            "poly_n": [5, 7],  # Only 5 or 7
        }
        self.dis_params = self.frame_model.dis_params
        self.dis_valid_values = {
            "preset": ["Ultra Fast", "Fast", "Medium"]
        }

        self.parent_widget = parent_widget

        self.previous_process_time = 0.0
        self.accumulated_process_time: list[float] = []
        self.frame_count = 0
        self.process_time_avg_30 = 0.0

        self.initUI()
        self.initialize_tool_window()
        self.video_thread.frame_available.connect(self.process_new_frame)

    def initUI(self):
        self.dialog = QDialog(self.parent_widget)
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
        """Initialize algorithm selector combobox with available algorithms.
        
        Sets the current selection to match the active algorithm in frame_model.
        """
        # List of available algorithms (must match order with frame_model.algorithm_list)
        algorithms = ["Farneback", "Lucas-Kanade", "DIS"]
        self.algorithm_selector.addItems(algorithms)
        
        # Set current selection to match the active algorithm in frame_model
        try:
            current_algorithm = self.frame_model.current_algorithm
            current_index = algorithms.index(current_algorithm)
            self.algorithm_selector.setCurrentIndex(current_index)
        except (ValueError, AttributeError):
            # If algorithm not found or frame_model doesn't have current_algorithm,
            # default to first item (already set by addItems)
            pass
        
        self.algorithm_selector.setStyleSheet(
            "background-color: #4285f4; color: white; font-size: 12px; padding: 8px; \
            border-radius: 4px;"
        )
        
        # Update parameter table to show params for the current algorithm
        self._update_parameter_table()
        
        # Connect signal to update params when algorithm changes
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
            combo_criteria.setCurrentIndex(0)  # Default to EPS|COUNT
            self.param_table.setCellWidget(2, 0, combo_criteria)

        if selected_algorithm == "DIS":
            self.param_table.setRowCount(1)
            self.param_table.setColumnCount(1)
            self.param_table.setHorizontalHeaderLabels(["Value"])
            self.param_table.setVerticalHeaderLabels(["preset"])
            
            combo_preset = QComboBox()
            for preset in self.dis_valid_values["preset"]:
                combo_preset.addItem(preset)
            combo_preset.setCurrentText(self.dis_params["preset"])
            self.param_table.setCellWidget(0, 0, combo_preset)

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
            
        if selected_algorithm == "DIS":
            self.dis_params["preset"] = cast(
                QComboBox, self.param_table.cellWidget(0, 0)
            ).currentText()
            
            self.frame_model.confirm_algorithm_n_params(
                selected_algorithm, self.dis_params
            )
            
        # Update all existing ROIs with the new algorithm and parameters
        for roi in self.frame_model.roi_list:
            roi.get_algorithm_n_params(selected_algorithm, self.frame_model.of_params if selected_algorithm == "Farneback" else (self.frame_model.lk_params if selected_algorithm == "Lucas-Kanade" else self.frame_model.dis_params))

        # Log the changes
        logger.info(f"Algorithm Configurator: Algorithm changed to: {selected_algorithm}")
        if selected_algorithm == "Farneback":
            logger.info(f"Algorithm Configurator: Farneback parameters: {self.frame_model.of_params}")
        elif selected_algorithm == "Lucas-Kanade":
            logger.info(f"Algorithm Configurator: Lucas-Kanade parameters: {self.frame_model.lk_params}")
        elif selected_algorithm == "DIS":
            logger.info(f"Algorithm Configurator: DIS parameters: {self.frame_model.dis_params}")

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

        elif selected_algorithm == "DIS":
            params = self.dis_params

        else:
            params = self.lk_params

        param_str = "\n".join(f"{k}: {v}" for k, v in params.items())

        QMessageBox.information(
            self.dialog,
            "Algorithm Configuration",
            f"Algorithm: {selected_algorithm}\n Parameters:\n{param_str}",
        )

        self.dialog.close()
