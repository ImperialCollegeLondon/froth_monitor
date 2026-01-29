"""The entry point for the Bubble Analyser program."""

from froth_monitor.handlers.main_handler import EventHandler
from froth_monitor.handlers.gui_window import MainGUIWindow
from froth_monitor.handlers.logger_config import get_logger

# from .gui import MainGUI
import sys
from PySide6.QtWidgets import QApplication, QStyleFactory
from PySide6.QtGui import QFont

# Initialize logger for this module
logger = get_logger(__name__)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    font = QFont("SF Pro", 11)  # You can adjust size as needed
    app.setFont(font)
    app.setStyle(QStyleFactory.create("Macintosh"))
    app.setStyleSheet("""
        QLabel, QLineEdit, QRadioButton, QPushButton, QGroupBox, \
            QMenuBar, QMenu, QMessageBox, QDialog, QComboBox, QCheckBox, QRadioButton,
            QStatusBar, QToolBar, QTabWidget, QTabBar, QToolButton, QProgressBar, QSlider
            {
            color: black;
        }

        QMessageBox QLabel {
            color: black;
        }
    """)
    window = MainGUIWindow()
    logger.info("Starting event handler")
    handler = EventHandler(window)
    window.show()
    logger.info("Application started successfully")
    sys.exit(app.exec())

### Air_rec Formula - unit of %
### Stick with cm for the first version
### (overflow's velocity (mm/s | distance/time)) * (froth height(mm | distance)) * (perimeter of cell (input from user) (mm | distance)) /
### over
### (air flow into 1. (we can ask user to choose the unit, volume/time - m^3/hr (industrial scale), liters/min (lab scale), cm3/s)
###                2. Ask for Jg (cm/s), calculate airflow based on (Jg*Area of cell)

### average value of velo/height within a second/several seconds
### Can display the value in real-time on graph
### Average value display on the table

### Graph - limit of y-label
### Air-rec panel
### User-defined air-flow

### Port of LIDAR choosing - more intuitive
