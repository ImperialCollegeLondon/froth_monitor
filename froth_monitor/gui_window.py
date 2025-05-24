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
    QMenuBar,
    QMenu,
    QWidget,
    QVBoxLayout,
    QGridLayout,
    QLineEdit,
)
from PySide6.QtCore import Qt
import pyqtgraph as pg
import sys
import numpy as np


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
        self.setWindowTitle("Froth Tracker")
        self.setGeometry(100, 100, 1200, 800)

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

        This function sets up the main window's layout, adds a menu bar,
        a grid layout for buttons and the video canvas, and adds placeholders
        for the video canvas, arrow canvas, ROI movements canvas, and the
        overflow direction label and text box.
        """

        # Main widget and layout
        main_widget = QWidget(self)
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout()
        main_widget.setLayout(main_layout)

        # Menu bar
        self.createMenuBar()

        # Grid layout for buttons and canvas
        grid_layout = QGridLayout()
        main_layout.addLayout(grid_layout)

        # Video canvas placeholder
        self.add_canvas_placeholder(grid_layout)

        # ROI Movements Canvas
        self.add_ROI_movement_placeholder(grid_layout)

        self.add_buttons(grid_layout)

        # Px2mm value label
        self.px2mm_textbox = QLineEdit(self)
        self.px2mm_textbox.setText(f"{self.px2mm:.2f}")  # Default to 1.0
        self.px2mm_textbox.setAlignment(Qt.AlignmentFlag.AlignRight)
        grid_layout.addWidget(self.px2mm_textbox, 0, 1, 1, 1)

        # Overflow direction value label
        self.direction_textbox = QLineEdit(self)
        self.direction_textbox.setText(
            f"{np.degrees(self.arrow_angle):.2f}"
        )  # Default to 90 degrees
        self.direction_textbox.setAlignment(Qt.AlignmentFlag.AlignRight)
        grid_layout.addWidget(self.direction_textbox, 1, 1, 1, 1)

    def createMenuBar(self) -> None:
        """
        Create the menu bar for the main window.

        This function creates a menu bar with two menus: "Import" and "Export".
        The "Import" menu contains two actions: "Import Local Video" and "Load Camera".
        The "Export" menu contains one action: "Export Settings".
        """

        menu_bar = QMenuBar(self)
        self.setMenuBar(menu_bar)

        # File menu
        file_menu = QMenu("Import", self)
        menu_bar.addMenu(file_menu)
        self.local_import = file_menu.addAction("Import Local Video")
        self.live_import = file_menu.addAction("Load Camera")

        # Export menu
        export_menu = QMenu("Export", self)
        menu_bar.addMenu(export_menu)
        self.export_button = export_menu.addAction("Export Settings")

    def add_buttons(self, layout: QGridLayout) -> None:
        """
        Adds buttons to the layout for adding a ROI, pausing/resuming the video,
        confirming the arrow direction, saving the current state, resetting the application,
        and starting video recording.
        """

        self.calibration_button = QPushButton("Calibration (Ruler drawing)", self)
        layout.addWidget(
            self.calibration_button, 0, 0, 1, 1
        )  # Add calibration button at the top left corner

        self.add_arrow_button = QPushButton("Add overflow arrow")
        layout.addWidget(self.add_arrow_button, 1, 0, 1, 1)

        self.confirm_arrow_button = QPushButton("Confirm Arrow and Ruler", self)
        layout.addWidget(self.confirm_arrow_button, 2, 0, 1, 2)

        self.add_roi_button = QPushButton("Add One ROI", self)
        layout.addWidget(self.add_roi_button, 4, 0, 1, 2)

        self.delete_roi_button = QPushButton("Delete Last ROI", self)
        layout.addWidget(self.delete_roi_button, 5, 0, 1, 2)

        self.pause_play_button = QPushButton("Pause/Play", self)
        layout.addWidget(self.pause_play_button, 7, 0, 1, 2)

        self.save_end_button = QPushButton("Save", self)
        layout.addWidget(self.save_end_button, 8, 0, 1, 2)

        self.reset_button = QPushButton("Start a new mission", self)
        layout.addWidget(self.reset_button, 9, 0, 1, 2)

        self.start_record_button = QPushButton("Start Recording", self)
        layout.addWidget(self.start_record_button, 11, 0, 1, 2)

    def add_canvas_placeholder(self, layout: QGridLayout) -> None:
        """
        Adds a placeholder QLabel to the layout where the video canvas will be drawn.
        The size of the label is fixed to 700x400.
        """
        # Create a container for the video canvas and overlay
        self.video_container = QWidget(self)
        self.video_container.setFixedSize(1000, 500)
        layout.addWidget(self.video_container, 0, 4, 16, 4)

        # Create the video canvas label
        self.video_canvas_label = QLabel("VIDEO CANVAS", self.video_container)
        self.video_canvas_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_canvas_label.setStyleSheet("background-color: black;")
        self.video_canvas_label.setGeometry(0, 0, 1000, 500)

    def add_ROI_movement_placeholder(self, layout: QGridLayout) -> None:
        """
        Adds a placeholder for the ROI movement curves to the layout.

        Creates a PlotWidget instance and adds it to the layout. The widget is
        set to have a fixed size of 700x200 and the Y-axis scale is hidden.
        The X-axis scale is also hidden, and a legend is added to the plot.
        """

        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground("black")
        self.plot_widget.setFixedSize(1000, 300)
        # self.plot_widget.hideAxis('left')  # Hide Y-axis scale
        # self.plot_widget.hideAxis('bottom')  # Hide X-axis scale
        self.plot_widget.addLegend()
        # Show axes that were hidden in the GUI setup
        self.plot_widget.showAxis("left")
        self.plot_widget.showAxis("bottom")

        # Set axis labels with proper units
        self.plot_widget.setLabel("left", "Velocity", units="mm/s")
        self.plot_widget.setLabel("bottom", "Time", units="frames")

        layout.addWidget(self.plot_widget, 16, 4, 10, 4)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainGUIWindow()
    window.show()
    sys.exit(app.exec())
