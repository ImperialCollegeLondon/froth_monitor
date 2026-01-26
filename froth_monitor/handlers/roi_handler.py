"""
ROI Handler Module

This module manages Region of Interest (ROI) creation and coordinate transformation
for the froth monitoring system. It provides a completely decoupled handler that
communicates exclusively via Qt signals.

Architecture:
    - Pure business logic component (no GUI or handler dependencies)
    - Receives data through constructor and update methods
    - Communicates results via Qt signals
    - Dynamically tracks resolution changes
"""

from PySide6.QtCore import QObject, Signal
from froth_monitor.handlers.logger_config import get_logger

# Initialize logger for this module
logger = get_logger(__name__)


class ROIHandler(QObject):
    """Manages Region of Interest (ROI) creation and coordinate transformation.
    
    This handler provides a completely decoupled ROI management system that:
    - Transforms ROI coordinates between display and processing resolutions
    - Validates video state before ROI operations
    - Communicates via signals only
    - Maintains minimal internal state
    
    Architecture:
        - Pure business logic component (no GUI/handler dependencies)
        - Receives data through constructor and update methods
        - Communicates results via Qt signals
        - Dynamically tracks resolution changes
    
    Signals:
        Outbound (ROIHandler → External):
            roi_draw_start: Request overlay widget to enter ROI drawing mode
            roi_added: Emit ROI coordinates (display_coords, processing_coords)
            roi_deleted: Notify that last ROI was deleted
            status_message: Emit status bar messages
            warning_box: Emit warning dialog messages
            request_overlay_update: Request overlay widget to redraw
    
    Example Usage:
        # In MainHandler initialization
        roi_handler = ROIHandler(
            display_res=(800, 450),
            processing_res=(640, 360),
            video_running=True
        )
        
        # Connect signals
        roi_handler.roi_added.connect(self._handle_roi_data)
        display_manager.first_frame_ready.connect(roi_handler.update_display_res)
    """
    
    # ============ Signals: Outbound Communication ============
    
    # Drawing mode control
    roi_draw_start = Signal()  # Request overlay to enter ROI drawing mode
    
    # ROI data flow
    roi_added = Signal(tuple, tuple)  # (display_coords, proc_coords) -> FrameModel
    roi_deleted = Signal()  # Last ROI deleted → FrameModel

    # User feedback
    status_message = Signal(str)  # Status bar messages → MainHandler
    warning_box = Signal(str)  # Warning dialogs → MainHandler
    
    # UI updates
    request_overlay_update = Signal()  # Request overlay redraw → OverlayWidget

    def __init__(self, display_res, processing_res, video_running=False):
        """Initialize ROI handler with resolution data only.
        
        Args:
            display_res (tuple): Display resolution (width, height)
            processing_res (tuple): Processing resolution (width, height)
            video_running (bool): Initial video state
        
        Note:
            All parameters are expected to be updated dynamically via the
            update_* methods as resolutions/settings change during runtime.
        """
        super().__init__()
        
        self.display_res = display_res
        self.processing_res = processing_res
        self.video_running = video_running
        
        logger.info(
            f"ROIHandler: Initialized with "
            f"display_res: {self.display_res}, "
            f"processing_res: {self.processing_res}, "
            f"video_running: {self.video_running}"
        )

    # ============ Dynamic Updates: External State Synchronization ============
    
    def update_display_res(self, display_res):
        """Update display resolution from FrameDisplayManager.
        
        Called via signal when window is resized or video dimensions change.
        
        Args:
            display_res (tuple): New display resolution (width, height)
        """
        self.display_res = display_res
        logger.info(f"ROIHandler: Display resolution updated: {self.display_res}")
    
    def update_processing_res(self, processing_res):
        """Update processing resolution from FrameResampleHandler.
        
        Called via signal when resolution preset changes.
        
        Args:
            processing_res (tuple): New processing resolution (width, height)
        """
        self.processing_res = processing_res
        logger.info(f"ROIHandler: Processing resolution updated: {self.processing_res}")
    
    def update_video_status(self, is_running):
        """Update video running status from VideoThread.
        
        Called via signal when video starts or stops.
        
        Args:
            is_running (bool): True if video is currently running
        """
        self.video_running = is_running
        logger.info(f"ROIHandler: Video running: {self.video_running}")
    
    # ============ ROI Operations ============
    
    def add_roi(self):
        """Request ROI drawing mode.
        
        Validates that video is running before allowing ROI creation.
        Emits signals to control overlay widget and inform user.
        
        Workflow:
            1. Check video_running state
            2. Emit warning if video not running
            3. Emit roi_draw_start to overlay widget
            4. Emit status message for user feedback
        """
        if not self.video_running:
            self.warning_box.emit("No video source loaded! Please load a video first.")
            return
        
        # Request overlay widget to enter ROI drawing mode
        self.roi_draw_start.emit()
        
        # Inform the user via status bar
        self.status_message.emit("Click and drag to draw a Region of Interest rectangle")
    
    def handle_roi_created(self, rect):
        """Handle ROI creation with coordinate transformation.
        
        Transforms ROI rectangle from display space -> processing space using
        CoordinateMapper, then emits the transformed coordinates for consumption
        by FrameModel.
        
        Args:
            rect (QRect): ROI rectangle from overlay (in display coordinates)
        
        Workflow:
            1. Extract display coordinates from QRect
            2. Transform: display pixels -> processing pixels
            3. Emit roi_added signal with both coordinate sets
            4. Update status bar with creation info
        
        Example:
            Display: (100, 100, 200, 150) at 800x450
            Processing: (80, 80, 160, 120) at 640x360 (80% scale)
        """
        from froth_monitor.utils.coordinate_mapper import CoordinateMapper
        
        # Extract display coordinates
        display_coords = (rect.x(), rect.y(), rect.width(), rect.height())
        
        # Transform display coordinates -> processing coordinates
        if self.display_res != (0, 0) and self.processing_res != (0, 0) and self.display_res[0] > 0:
            # Create coordinate mapper
            mapper = CoordinateMapper(self.display_res, self.processing_res)
            
            # Transform coordinates
            proc_coords = mapper.display_to_processing(*display_coords)
            
            logger.info(
                f"ROIHandler: ROI created:\n"
                f"  Display: {display_coords} at {self.display_res}\n"
                f"  Processing: {proc_coords} at {self.processing_res}\n"
                f"  Scale: {self.processing_res[0]/self.display_res[0]:.1%} x "
                f"{self.processing_res[1]/self.display_res[1]:.1%}"
            )
        else:
            # Fallback: use display coordinates directly
            proc_coords = display_coords
            logger.warning(
                f"ROIHandler: Resolutions not initialized "
                f"(display={self.display_res}, processing={self.processing_res}), "
                f"using display coords directly"
            )
        
        # Emit ROI data for FrameModel to consume
        self.roi_added.emit(display_coords, proc_coords)
        
        # Status update
        self.status_message.emit(
            f"ROI created at ({display_coords[0]}, {display_coords[1]}) "
            f"-> Processing: ({proc_coords[0]}, {proc_coords[1]})"
        )
    
    def delete_last_roi(self):
        """Request deletion of the last created ROI.
        
        Emits signals to notify FrameModel of deletion and request
        overlay widget to redraw.
        
        Workflow:
            1. Emit roi_deleted signal -> FrameModel removes ROI
            2. Emit request_overlay_update -> Overlay redraws
            3. Emit status message -> User feedback
        """
        self.roi_deleted.emit()
        self.request_overlay_update.emit()
        self.status_message.emit("Last ROI deleted")
