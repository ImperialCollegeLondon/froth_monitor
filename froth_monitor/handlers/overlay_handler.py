from PySide6.QtCore import QRect

# Import the custom overlay widget
from froth_monitor.handlers.overlay_widget import OverlayWidget
from froth_monitor.handlers.logger_config import get_logger

# Initialize logger for this module
logger = get_logger(__name__)


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
