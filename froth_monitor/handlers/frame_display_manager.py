"""Frame display management for GUI operations.

This module handles all frame display operations on the GUI canvas,
including overlay synchronization and status bar updates.
"""

from PySide6.QtCore import QRect, QObject, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QLabel, QStatusBar
from froth_monitor.handlers.overlay_widget import OverlayWidget
from froth_monitor.handlers.logger_config import get_logger

logger = get_logger(__name__)


class FrameDisplayManager(QObject):
    """Manages frame display on GUI canvas and overlay synchronization.
    
    Responsibilities:
        - Display frames on video canvas label
        - Update overlay widget position to match video
        - Update status bar with frame information
    
    This class encapsulates all GUI display operations, keeping them
    separate from frame processing logic.
    """
    
    # Signal emitted once when first frame is displayed with valid dimensions
    first_frame_ready = Signal(tuple)  # Emits (width, height) of video
    
    def __init__(
        self,
        canvas_label: QLabel,
        status_bar: QStatusBar,
        overlay_widget: OverlayWidget
    ):
        """Initialize display manager with GUI components.
        
        Args:
            canvas_label: QLabel widget for video display
            status_bar: Application status bar for messages
            overlay_widget: Transparent overlay for ROIs and annotations
        """
        super().__init__() # Call QObject constructor
        self.canvas_label = canvas_label
        self.status_bar = status_bar
        self.overlay_widget = overlay_widget
        
        # Cache canvas dimensions
        self.canvas_width = canvas_label.width()
        self.canvas_height = canvas_label.height()
        
        # Track current video position within canvas
        self.video_rect = QRect()
        
        # Flag to track first frame display
        self._first_frame_displayed = False
        
        logger.info("FrameDisplayManager: Initialized with canvas dimensions: {}x{}".format(self.canvas_width, self.canvas_height))
    
    def display_frame(self, qt_image: QImage) -> QPixmap:
        """Display QImage on canvas and update overlay position.
        
        Args:
            qt_image: Scaled QImage ready for display
            
        Returns:
            QPixmap that was displayed on canvas
        """
        # Update canvas dimensions in case window was resized
        self.canvas_width = self.canvas_label.width()
        self.canvas_height = self.canvas_label.height()
        
        # Convert to pixmap and display
        pixmap = QPixmap.fromImage(qt_image)
        self.canvas_label.setPixmap(pixmap)
        
        # Update overlay to match video position
        self._update_overlay_position(pixmap)
        
        return pixmap
    
    def update_status(self, frame_number: int, timestamp: str) -> None:
        """Update status bar with frame information.
        
        Args:
            frame_number: Current frame number
            timestamp: Formatted timestamp string
        """
        self.status_bar.showMessage(
            f"Frame: {frame_number} | Time: {timestamp}"
        )
    
    def _update_overlay_position(self, pixmap: QPixmap) -> None:
        """Update overlay widget geometry to match video position.
        
        The overlay must be positioned correctly when the video is
        smaller than the canvas (centered with letterboxing).
        
        Args:
            pixmap: Currently displayed pixmap
        """
        if pixmap.width() < self.canvas_width or pixmap.height() < self.canvas_height:
            # Video is centered in canvas - calculate offsets
            x_offset = (self.canvas_width - pixmap.width()) // 2
            y_offset = (self.canvas_height - pixmap.height()) // 2
            
            self.video_rect = QRect(
                x_offset,
                y_offset,
                pixmap.width(),
                pixmap.height()
            )
        else:
            # Video fills the entire canvas
            self.video_rect = QRect(
                0,
                0,
                self.canvas_width,
                self.canvas_height
            )
        
        # Update overlay widget to match video position
        if self.overlay_widget:
            self.overlay_widget.setGeometry(self.video_rect)
            # Update video dimensions for ruler scaling
            self.overlay_widget.set_video_dimensions(
                self.video_rect.width(), 
                self.video_rect.height()
            )
        
        # Emit first_frame_ready signal once when valid dimensions are available
        if not self._first_frame_displayed and self.video_rect.width() > 0 and self.video_rect.height() > 0:
            self._first_frame_displayed = True
            video_dims = (self.video_rect.width(), self.video_rect.height())
            self.first_frame_ready.emit(video_dims)
            logger.info(f"FrameDisplayManager: First frame ready with dimensions: {video_dims}")
    
    def get_canvas_size(self) -> tuple[int, int]:
        """Get canvas dimensions.
        
        Returns:
            Tuple of (width, height) in pixels
        """
        return self.canvas_width, self.canvas_height
    
    def get_video_dimensions(self) -> tuple[int, int]:
        """Get current displayed video dimensions.
        
        Returns:
            Tuple of (width, height) of displayed video
        """
        return self.video_rect.width(), self.video_rect.height()
    
    def get_video_rect(self) -> QRect:
        """Get video rectangle within canvas.
        
        Returns:
            QRect representing video position and size
        """
        return self.video_rect
    
    def cleanup(self) -> None:
        """Clean up resources and clear display.
        
        This method should be called when ending a session or resetting
        the application to free memory and clear the display.
        """
        logger.info("FrameDisplayManager: Starting cleanup...")
        
        # Clear canvas label pixmap
        if self.canvas_label:
            self.canvas_label.clear()  # This automatically clears the pixmap
        
        # Clear status bar
        if self.status_bar:
            self.status_bar.clearMessage()
        
        # Reset video rect
        self.video_rect = QRect()
        
        # Reset overlay widget geometry if exists
        if self.overlay_widget:
            self.overlay_widget.setGeometry(QRect())
        
        logger.info("FrameDisplayManager: Cleanup complete - display cleared")
