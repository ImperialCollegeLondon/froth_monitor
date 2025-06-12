"""The entry point for the Bubble Analyser program."""

from froth_monitor.event_handler import EventHandler
from froth_monitor.gui_window import MainGUIWindow

# from .gui import MainGUI
import sys
from PySide6.QtWidgets import QApplication, QStyleFactory
from PySide6.QtGui import QFont


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
    print("starting event handler")
    handler = EventHandler(window)
    window.show()
    sys.exit(app.exec())
