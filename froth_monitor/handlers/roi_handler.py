from PySide6.QtWidgets import (
    QMessageBox,
)

# Import MainGUIWindow at the beginning
from froth_monitor.handlers.gui_window import MainGUIWindow

# Import FrameModel from fm_model module
from froth_monitor.processing.fm_model import FrameModel, ROI

# Import the custom overlay widget
from froth_monitor.handlers.overlay_widget import OverlayWidget

# Import the camera and network threads
from froth_monitor.video_threads.camera_thread import CameraThread
from froth_monitor.video_threads.network_thread import NetworkThread

# from froth_monitor.event_handler import EventHandler
from froth_monitor.handlers.logger_config import get_logger

# Initialize logger for this module
logger = get_logger(__name__)


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

