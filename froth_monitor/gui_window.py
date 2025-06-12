"""Froth Tracker Application GUI Window.

This module contains the GUI layout and components for the Froth Tracker application
without any connected functionality. It serves as a template for the application's
user interface structure.
"""

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QPushButton,
    QLabel,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QRadioButton,
    QFrame,
    QGroupBox,
    QSpinBox,
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon
import pyqtgraph as pg
import sys
import numpy as np
import os


class MainGUIWindow(QMainWindow):
    """
    The main graphical user interface (GUI) window class for the Froth Tracker application.

    This class provides the primary interface layout for the application, including:
    - Menu bar with import and export options
    - Video canvas for displaying frames
    - Arrow direction canvas and controls
    - ROI movement visualization area
    - Control buttons for various operations
    """

    def __init__(self) -> None:
        """
        Constructor for the MainGUIWindow class.

        Initializes the main window and sets up the UI elements.
        """
        super(MainGUIWindow, self).__init__()
        self.setWindowTitle("Froth Monitor")
        self.setGeometry(100, 100, 1000, 600)
        self.setStyleSheet("background-color: #f0f0f0;")

        # Initialize default arrow angle (90 degrees)
        self.arrow_angle = -np.pi / 2
        # Initialize default px2mm value (1.0)
        self.px2mm = 1.0

        # Initialize overlay related attributes
        self.overlay_widget = None
        self.video_rect = None

        # Define UI elements
        self.initUI()

    def initUI(self) -> None:
        """
        Initialize the UI elements of the main window.

        This function sets up the main window's layout by calling specialized methods
        for creating different parts of the UI, including the header bar, left panel controls,
        and right panel with video canvas and graph display.
        """
        # Main widget and layout
        main_widget = QWidget(self)
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_widget.setLayout(main_layout)

        # Create header bar
        header_bar = self._create_header_bar()
        main_layout.addWidget(header_bar)

        # Main content area
        content_widget = QWidget()
        content_widget.setStyleSheet(
            "background-color: #f0f0f0; font-weight: bold; font-size: 16px; \
            color: black"
        )
        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.addWidget(content_widget)

        # Create left panel with controls
        left_panel = self._create_left_panel()

        # Create right panel with video canvas and graph
        right_panel = self._create_right_panel()

        # Add panels to content layout
        content_layout.addWidget(left_panel)
        content_layout.addWidget(right_panel)

    def _create_header_bar(self) -> QFrame:
        """
        Create the header bar with title.

        Returns:
            QFrame: The header bar widget.
        """
        header_bar = QFrame()
        header_bar.setStyleSheet("background-color: #3c4043; color: white;")
        header_bar.setFixedHeight(50)
        header_layout = QHBoxLayout(header_bar)
        header_layout.setContentsMargins(20, 0, 20, 0)

        # Add title to header
        title_label = QLabel("Froth Monitor")
        title_label.setStyleSheet("color: white; font-size: 24px; font-weight: bold;")
        header_layout.addWidget(title_label)

        # Add spacer to push window controls to the right
        header_layout.addStretch()

        return header_bar

    def _create_left_panel(self) -> QFrame:
        """
        Create the left panel with all control elements.

        Returns:
            QFrame: The left panel widget with all controls.
        """
        left_panel = QFrame()
        left_panel.setFixedWidth(250)
        left_panel.setStyleSheet("background-color: #f0f0f0;")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(15)
        left_layout.setContentsMargins(10, 10, 10, 10)

        # Add video source controls
        source_group = self._create_video_source_controls()
        left_layout.addWidget(source_group)

        # Add calibration controls
        calibration_group = self._create_calibration_controls()
        left_layout.addWidget(calibration_group)

        # Add ROI controls
        roi_group = self._create_roi_controls()
        left_layout.addWidget(roi_group)

        # Add export settings
        export_group = self._create_export_settings()
        left_layout.addWidget(export_group)
        # Add reset buttons
        self._add_reset_buttons(left_layout)

        # Add spacer at the bottom
        left_layout.addStretch()

        return left_panel

    def _create_video_source_controls(self) -> QGroupBox:
        """
        Create the video source selection controls.

        Returns:
            QGroupBox: The video source group box with radio buttons.
        """
        source_group = QGroupBox("Video Source")
        source_group.setStyleSheet("font-weight: bold; font-size: 16px; color: black")
        source_layout = QVBoxLayout(source_group)
        source_layout.setSpacing(10)

        # Radio buttons for video source
        self.webcam_radio = QRadioButton("Webcam")
        self.webcam_radio.setStyleSheet(
            "font-weight: normal; font-size: 14px; color: black"
        )
        self.prerecorded_radio = QRadioButton("Pre-recorded")
        self.prerecorded_radio.setStyleSheet(
            "font-weight: normal; font-size: 14px; color: black"
        )
        self.webcam_radio.setChecked(True)
        self.import_button = QPushButton("Import")
        self.import_button.setStyleSheet(
            """
            QPushButton {
                background-color: #4285f4;
                color: white;
                font-size: 14px;
                padding: 8px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #3367d6;
            }
            """
        )

        self.algorithm_configuration = QPushButton("Algorithm Configuration")
        self.algorithm_configuration.setStyleSheet(
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

        source_layout.addWidget(self.webcam_radio)
        source_layout.addWidget(self.prerecorded_radio)
        source_layout.addWidget(self.import_button)
        source_layout.addWidget(self.algorithm_configuration)

        return source_group

    def _create_calibration_controls(self) -> QGroupBox:
        """
        Create the calibration controls.

        Returns:
            QGroupBox: The calibration group box with button and text input.
        """
        calibration_group = QGroupBox("Calibration/ROI")
        calibration_group.setStyleSheet(
            "font-weight: bold; font-size: 16px; \
            color: black"
        )
        calibration_layout = QVBoxLayout(calibration_group)
        calibration_layout.setSpacing(10)

        roi_layout = QVBoxLayout()
        roi_layout_1 = QHBoxLayout()

        # ---------Ruler draw sector 1
        self.calibration_button = QPushButton("Draw a line with \n length of")
        self.calibration_button.setStyleSheet(
            """
            QPushButton {
                background-color: #4285f4;
                color: white;
                font-size: 12px;
                padding: 8px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #3367d6;
            }
            """
        )
        self.calibration_button.setFixedWidth(120)  # Fixed width for the button

        self.px2mm_spinbox = QSpinBox()
        self.px2mm_spinbox.setRange(1, 1000)  # Adjust the range as needed
        self.px2mm_spinbox.setValue(20)  # Default value
        self.px2mm_spinbox.setStyleSheet(
            "background-color: white; font-size: 12px; padding: 5px; border-radius: 4px;"
        )

        px2mm_label = QLabel("mm")
        px2mm_label.setStyleSheet("color: black; font-size: 8px;")

        roi_layout_1.addWidget(self.calibration_button)
        roi_layout_1.addWidget(self.px2mm_spinbox)
        roi_layout_1.addWidget(px2mm_label)

        # ---------Ruler draw sector 2
        roi_layout_2 = QHBoxLayout()
        px2mm_label_2 = QLabel("Result ratio \n(edible):")
        px2mm_label_2.setStyleSheet(
            "\
                background-color: #3c4043;\
                color: white;\
                font-size: 12px;\
                padding: 8px;\
                border-radius: 4px;\
                "
        )
        px2mm_label_2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        px2mm_label_2.setFixedWidth(120)

        self.px2mm_result_textbox = QLineEdit()
        self.px2mm_result_textbox.setText("1.0")  # Default value
        self.px2mm_result_textbox.setStyleSheet(
            "background-color: white; font-size: 10px; padding: 8px; border-radius: 4px;"
        )
        self.px2mm_result_textbox.setAlignment(Qt.AlignmentFlag.AlignCenter)

        px2mm_label_3 = QLabel("mm/px")
        px2mm_label_3.setStyleSheet("color: black; font-size: 8px;")

        roi_layout_2.addWidget(px2mm_label_2)
        roi_layout_2.addWidget(self.px2mm_result_textbox)
        roi_layout_2.addWidget(px2mm_label_3)

        roi_layout.addLayout(roi_layout_1)
        roi_layout.addLayout(roi_layout_2)

        # Separator line
        separator_1 = QFrame()
        separator_1.setFrameShape(QFrame.Shape.HLine)
        separator_1.setFrameShadow(QFrame.Shadow.Sunken)
        separator_1.setStyleSheet("background-color: #3c4043;")

        # Arrow Sector
        arrow_layout = QHBoxLayout()
        self.add_arrow_button = QPushButton("Draw Arrow")
        self.add_arrow_button.setStyleSheet(
            """
            QPushButton {
                background-color: #4285f4;
                color: white;
                font-size: 12px;
                padding: 8px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #3367d6;
            }
            """
        )
        self.add_arrow_button.setFixedWidth(120)

        self.direction_textbox = QLineEdit()
        self.direction_textbox.setText("-90.0")  # Default value
        self.direction_textbox.setStyleSheet(
            "background-color: white; font-size: 10px; padding: 8px; border-radius: 4px;"
        )
        self.direction_textbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        degree_label = QLabel("degree")
        degree_label.setStyleSheet("color: black; font-size: 8px;")

        # Separator line
        separator_2 = QFrame()
        separator_2.setFrameShape(QFrame.Shape.HLine)
        separator_2.setFrameShadow(QFrame.Shadow.Sunken)
        separator_2.setStyleSheet("background-color: #3c4043;")

        self.confirm_arrow_button = QPushButton("Confirm calibration")
        self.confirm_arrow_button.setStyleSheet(
            """
            QPushButton {
                background-color: #4285f4;
                color: white;
                font-size: 14px;
                padding: 12px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #3367d6;
            }
            """
        )
        arrow_layout.addWidget(self.add_arrow_button)
        arrow_layout.addWidget(self.direction_textbox)
        arrow_layout.addWidget(degree_label)

        calibration_layout.addLayout(roi_layout)
        calibration_layout.addWidget(separator_1)
        calibration_layout.addLayout(arrow_layout)
        # calibration_layout.addWidget(separator_2)
        calibration_layout.addWidget(self.confirm_arrow_button)

        return calibration_group

    def _create_roi_controls(self) -> QGroupBox:
        """
        Create the ROI (Region of Interest) controls.

        Returns:
            QGroupBox: The ROI group box with add and delete buttons.
        """
        roi_group = QGroupBox()
        roi_group.setStyleSheet("font-weight: bold; font-size: 16px; color: black")
        roi_layout = QHBoxLayout(roi_group)

        # Add spacer to push buttons to the right
        # roi_layout.addStretch()
        self.roi_text = QLabel("ROI")
        self.roi_text.setStyleSheet(
            "background-color: #3c4043; color: white; font-size: 14px; \
            font-weight: bold; padding: 8px; border-radius: 4px;"
        )

        # Add + and - buttons for ROI
        self.add_roi_button = QPushButton("+")
        self.add_roi_button.setStyleSheet(
            """
            QPushButton {
                background-color: #4285f4; color: white; font-size: 18px; \
            font-weight: bold; padding: 5px; border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #3367d6;
            }
            """
        )
        self.add_roi_button.setFixedSize(40, 40)

        self.delete_roi_button = QPushButton("-")
        self.delete_roi_button.setStyleSheet(
            """
            QPushButton {
                background-color: #4285f4; color: white; font-size: 18px; \
            font-weight: bold; padding: 5px; border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #3367d6;
            }
            """
        )
        self.delete_roi_button.setFixedSize(40, 40)

        roi_layout.addWidget(self.roi_text)
        roi_layout.addWidget(self.add_roi_button)
        roi_layout.addWidget(self.delete_roi_button)

        return roi_group

        # Helper to get resource path

    def resource_path(self, relative_path):
        if hasattr(sys, "_MEIPASS"):
            return os.path.join(sys._MEIPASS, relative_path)  # type: ignore
        return relative_path

    def _add_reset_buttons(self, layout: QVBoxLayout) -> None:
        """
        Add reset buttons to the given layout.

        Args:
            layout: The layout to add the reset buttons to.
        """

        # Reset button with camera icon
        self.record_button = QPushButton("  Start Recording")
        self.record_button.setIcon(
            QIcon(self.resource_path("froth_monitor/resources/camera_icon.ico"))
        )
        self.record_button.setIconSize(QSize(24, 24))
        self.record_button.setStyleSheet(
            "QPushButton {\
                background-color: red; color: white; font-size: 15px; \
                padding: 5px; border-radius: 4px;\
            }\
            QPushButton:hover {\
                background-color: #3367d6;\
            }"
        )
        self.record_button.setFixedHeight(50)
        layout.addWidget(self.record_button)

        # Simple Reset button (as shown in the image)
        self.simple_reset_button = QPushButton("Reset")
        self.simple_reset_button.setStyleSheet(
            "QPushButton {\
                background-color: #4285f4; color: white; font-size: 14px; \
                padding: 5px; border-radius: 4px;\
            }\
            QPushButton:hover {\
                background-color: #3367d6;\
            }"
        )
        layout.addWidget(self.simple_reset_button)

    def _create_right_panel(self) -> QFrame:
        """
        Create the right panel with video canvas and graph display.

        Returns:
            QFrame: The right panel widget with video and graph components.
        """
        right_panel = QFrame()
        right_panel.setStyleSheet("background-color: #f0f0f0;")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setSpacing(10)

        # Add video canvas
        self._create_video_canvas(right_layout)

        # Add graph display
        self._create_graph_display(right_layout)

        return right_panel

    def _create_video_canvas(self, layout: QVBoxLayout) -> None:
        """
        Create the video canvas and add it to the given layout.

        Args:
            layout: The layout to add the video canvas to.
        """
        self.video_container = QWidget()
        self.video_container.setFixedSize(700, 400)
        self.video_container.setStyleSheet(
            "background-color: #333333; border-radius: 4px;"
        )
        video_container_layout = QVBoxLayout(self.video_container)

        # Create the video canvas label
        self.video_canvas_label = QLabel("")
        self.video_canvas_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_canvas_label.setStyleSheet("background-color: #333333;")
        self.video_canvas_label.setGeometry(0, 0, 700, 400)
        video_container_layout.addWidget(self.video_canvas_label)

        layout.addWidget(self.video_container)

        # Add media controls below the video canvas
        self._create_media_controls(layout)

    def _create_export_settings(self) -> QGroupBox:
        """
        Create the calibration controls.

        Returns:
            QGroupBox: The calibration group box with button and text input.
        """
        export_group = QGroupBox("Export Settings")
        export_group.setStyleSheet("font-weight: bold; font-size: 16px; color: black")
        export_layout = QVBoxLayout(export_group)
        export_layout.setSpacing(10)

        # roi_layout = QHBoxLayout()
        self.export_button = QPushButton("Export/Recording Settings")
        self.export_button.setStyleSheet(
            """
            QPushButton {
                background-color: #4285f4;
                color: white;
                font-size: 12px;
                padding: 8px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #3367d6;
            }
            """
        )
        # self.calibration_button.setFixedWidth(100)

        self.save_button = QPushButton("Save")
        self.save_button.setStyleSheet(
            """
            QPushButton {
                background-color: #4285f4;
                color: white;
                font-size: 12px;
                padding: 8px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #3367d6;
            }
            """
        )
        export_layout.addWidget(self.export_button)
        export_layout.addWidget(self.save_button)

        return export_group

    def _create_graph_display(self, layout: QVBoxLayout) -> None:
        """
        Create the graph display for velocity vs time and add it to the given layout.

        Args:
            layout: The layout to add the graph display to.
        """
        # Velocity vs Time label
        velocity_label = QLabel("Velocity vs Time")
        velocity_label.setStyleSheet(
            "font-weight: bold; font-size: 16px; \
            color: black"
        )
        layout.addWidget(velocity_label)

        horizontal_layout = QHBoxLayout()

        example_1d_data = ["N/A"]
        # ROI Movements Table
        self.table_widget = pg.TableWidget()
        self.table_widget.setData(example_1d_data)
        # self.table_widget.setColumnCount(2)
        self.table_widget.setHorizontalHeaderLabels(["mean_velocity  "])
        self.table_widget.setFormat("%.2f")
        self.table_widget.setColumnWidth(0, 120)
        # self.table_widget.setColumnWidth(1, 100)
        self.table_widget.setFixedHeight(200)

        # ROI Movements Canvas (graph)
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground("white")
        self.plot_widget.setFixedHeight(200)
        self.plot_widget.showAxis("left")
        self.plot_widget.showAxis("bottom")
        self.plot_widget.setLabel("left", "Velocity", units="mm/s")
        self.plot_widget.setLabel("bottom", "Time", units="secs")
        self.plot_widget.addLegend()
        horizontal_layout.addWidget(self.table_widget)
        horizontal_layout.addWidget(self.plot_widget)
        layout.addLayout(horizontal_layout)

        # layout.addWidget(self.plot_widget)

        # Add "Average 30 s" label
        avg_label = QLabel("Average over past 30s")
        avg_label.setStyleSheet("font-size: 10px; color: #333333; text-align: left;")
        avg_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(avg_label)

    def _create_media_controls(self, layout: QVBoxLayout) -> None:
        """
        Create media control buttons (play/pause) below the video canvas.

        Args:
            layout: The layout to add the media controls to.
        """
        # Create a container for media controls
        media_controls_container = QWidget()
        media_controls_layout = QHBoxLayout(media_controls_container)
        media_controls_layout.setContentsMargins(0, 5, 0, 5)

        # Create play/pause button
        self.play_pause_button = QPushButton()
        self.play_pause_button.setIcon(
            QIcon(self.resource_path("froth_monitor/resources/pause_icon.ico"))
        )

        self.play_pause_button.setIconSize(QSize(24, 24))
        self.play_pause_button.setStyleSheet(
            """
            QPushButton {
                background-color: #4285f4; color: white; font-size: 14px; padding: 8px; \
            border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #3367d6;
            }
            """
        )
        self.play_pause_button.setFixedSize(40, 40)
        self.play_pause_button.setToolTip("Play/Pause Video")

        # Add the button to the layout
        media_controls_layout.addWidget(self.play_pause_button)
        # Add a stretch to push the button to the right
        media_controls_layout.addStretch()

        # Add the media controls container to the main layout
        layout.addWidget(media_controls_container)

    # The createMenuBar, add_buttons, add_canvas_placeholder, and add_ROI_movement_placeholder methods
    # have been integrated into the new initUI method to create a more modern interface


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet("""
        QLabel, QLineEdit, QRadioButton, QPushButton, QGroupBox, QMenuBar, QMenu, QMessageBox {
            color: black;
        }
        QPushButton {
            background-color: #4285f4;
            color: white;
            font-size: 14px;
            padding: 8px;
            border-radius: 4px;
        }
        QPushButton:hover {
            background-color: #3367d6;
        }
        QMessageBox QLabel {
            color: black;
        }
    """)
    window = MainGUIWindow()
    window.show()
    sys.exit(app.exec())
