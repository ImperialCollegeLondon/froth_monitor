"""
Calibration Handler Module

This module handles spatial calibration for the froth monitor system, including:
- Ruler calibration: Converting pixel measurements to millimeters
- Arrow direction: Setting the overflow direction for froth movement
- Resolution scaling: Accounting for different display and processing resolutions

The handler is completely decoupled from GUI and other handlers, communicating
exclusively through Qt signals for maximum testability and reusability.
"""

from typing import cast
from PySide6.QtWidgets import (
    QMessageBox,
)
from PySide6.QtCore import QObject, Signal

# Import MainGUIWindow at the beginning
from froth_monitor.handlers.realtime_export import RealtimeExporter
from froth_monitor.handlers.logger_config import get_logger

# Initialize logger for this module
logger = get_logger(__name__)


class CalibrationHandler(QObject):
    """Manages spatial calibration for froth monitoring with resolution-aware calculations.
    
    This handler provides a completely decoupled calibration system that:
    - Converts pixel measurements to real-world millimeters (px2mm ratio)
    - Accounts for resolution differences between display and processing
    - Manages overflow direction via arrow drawing
    - Maintains calibration state and history
    
    Architecture:
        - Pure business logic component (no GUI or handler dependencies)
        - Receives data through constructor and update methods
        - Communicates results via Qt signals
        - Dynamically tracks resolution changes
    
    Data Flow:
        1. User draws ruler on overlay (overlay pixels)
        2. Coordinates transformed: overlay → source resolution
        3. px2mm calculated for both display and processing resolutions
        4. Results emitted via signals for consumption by FrameModel/GUI
    
    Signals:
        Outbound (CalibrationHandler → External):
            ruler_draw_start: Request overlay widget to start ruler drawing mode
            arrow_draw_start: Request overlay widget to start arrow drawing mode
            release_px2mm: Emit calculated px2mm for processing resolution
            release_arrow_direction: Emit confirmed arrow direction (degrees)
            release_export_data: Emit calibration data for export (degree, px2mm)
            calibration_confirmed: Emit when user confirms calibration
            status_message: Emit status bar messages
            message_box: Emit information dialog messages
            warning_box: Emit warning dialog messages
            set_textbox_px2mm: Update GUI textbox with px2mm value
            set_textbox_arrow_direction: Update GUI textbox with arrow direction
        
        Inbound (External → CalibrationHandler via update methods):
            update_display_px2mm: Manual px2mm entry from GUI
            update_distance_mm: Reference distance entry from GUI
            update_arrow_direction: Manual arrow direction entry from GUI
            update_scale_factor: Processing scale factor from FrameResampleHandler
            update_source_res: Source video resolution from FrameResampleHandler
            update_overlay_res: Displayed video resolution from FrameDisplayManager
    
    Coordinate System:
        - Overlay space: User's cursor position on displayed video widget
        - Source space: Full-resolution source video (e.g., 1280x720)
        - Processing space: Downsampled for optical flow (e.g., 640x360 at 50% scale)
        
        Example:
            User draws 400px ruler on 800x450 overlay
            → Maps to 640px in 1280x720 source video
            → Display px2mm = 640/20mm = 32.0 px/mm
            → Processing px2mm = 32 * 0.5 = 16.0 px/mm (for 50% scale)
    
    State Management:
        - confirm_calibration: Whether calibration has been confirmed
        - export_enable: Whether export functionality is enabled
        - display_px2mm: px2mm ratio for display/source resolution
        - processed_px2mm: px2mm ratio for processing resolution (used by algorithms)
    
    Example Usage:
        # In MainHandler initialization
        calibration_handler = CalibrationHandler(
            distance_mm=20.0,
            arrow_direction="45.0",
            source_res=(1280, 720),
            overlay_res=(800, 450),
            scale_factor=0.5
        )
        
        # Connect signals
        calibration_handler.release_px2mm.connect(frame_model.get_px_to_mm)
        frame_resample_handler.scale_changed.connect(
            calibration_handler.update_scale_factor
        )
    """
    
    # ============ Signals: Outbound Communication ============
    
    # Drawing mode control
    ruler_draw_start = Signal()  # Request to start ruler drawing on overlay
    arrow_draw_start = Signal()  # Request to start arrow drawing on overlay

    # Calibration results
    calibration_confirmed = Signal()  # User has confirmed calibration settings
    release_px2mm = Signal(float)  # Emit calculated px2mm for processing (pixels per mm)
    release_arrow_direction = Signal(float)  # Emit arrow direction in degrees
    release_export_data = Signal(float, float)  # Emit (degree, px2mm) for data export

    # User feedback
    status_message = Signal(str)  # Status bar message text
    message_box = Signal(str)  # Information dialog message text
    warning_box = Signal(str)  # Warning dialog message text

    # GUI control
    set_textbox_px2mm = Signal(str)  # Set px2mm textbox value (display resolution)
    set_textbox_arrow_direction = Signal(str)  # Set arrow direction textbox value

    def __init__(self, display_px2mm, distance_mm, arrow_direction, source_res, overlay_res, scale_factor):
        """Initialize calibration handler with current resolution and scale settings.
        
        Args:
            distance_mm (float): Reference distance in millimeters for calibration
            arrow_direction (str): Arrow direction as string (will be converted to float)
            source_res (tuple[int, int]): Source video resolution (width, height)
            overlay_res (tuple[int, int]): Displayed overlay resolution (width, height)
            scale_factor (float): Processing scale factor (e.g., 0.5 for 50% downsampling)
        
        Note:
            All parameters except internal state are expected to be updated dynamically
            via the update_* methods as resolutions/settings change during runtime.
        """
        super().__init__()

        # Calibration state - convert string input to float
        try:
            self.display_px2mm = float(display_px2mm) if display_px2mm else 0.0
        except (ValueError, TypeError):
            self.display_px2mm = 0.0
            logger.warning(f"Invalid display_px2mm value: {display_px2mm}, defaulting to 0.0")
            
        self.processed_px2mm = 0.0  # px2mm ratio for processing resolution (used by algorithms)
        self.scale_factor = scale_factor  # Current processing scale factor

        # Resolution tracking (updated dynamically)
        self.source_res = source_res  # Source video resolution (e.g., 1280x720)
        self.overlay_res = overlay_res  # Displayed overlay resolution (e.g., 800x450)
        
        # User input values (updated from GUI)
        self.distance_mm = distance_mm  # Reference distance for calibration
        self.arrow_direction = arrow_direction  # Overflow direction

        # Workflow state
        self.confirm_calibration = False  # Whether calibration has been confirmed
        self.export_enable = False  # Whether data export is enabled
        logger.info(f"CalibrationHandler: Initialized with display px2mm: {self.display_px2mm}, distance mm: {self.distance_mm}, arrow direction: {self.arrow_direction}, source res: {self.source_res}, overlay res: {self.overlay_res}, scale factor: {self.scale_factor}")
 
    # ============ Dynamic Updates: External State Synchronization ============

    def update_display_px2mm(self, px2mm):
        """Update manually entered px2mm value for display resolution.
        
        Called when user manually types px2mm value in GUI textbox.
        
        Args:
            px2mm (str or float): Pixels per millimeter ratio for display resolution
        """
        try:
            self.display_px2mm = float(px2mm) if px2mm else 0.0
        except (ValueError, TypeError):
            self.display_px2mm = 0.0
            logger.warning(f"Invalid px2mm value: {px2mm}, defaulting to 0.0")
        logger.info(f"CalibrationHandler: Display px2mm updated: {self.display_px2mm}")

    def update_distance_mm(self, mm):
        """Update reference distance in millimeters.
        
        Called when user changes the reference distance in GUI spinbox.
        
        Args:
            mm (float): Reference distance in millimeters
        """
        self.distance_mm = mm
        logger.info(f"CalibrationHandler: Distance mm updated: {self.distance_mm}")

    def update_arrow_direction(self, direction):
        """Update arrow direction value.
        
        Called when user manually changes arrow direction in GUI textbox.
        
        Args:
            direction (str): Arrow direction as string (degrees)
        """
        self.arrow_direction = direction
        logger.info(f"CalibrationHandler: Arrow direction updated: {self.arrow_direction}")

    def update_scale_factor(self, scale_factor):
        """Update processing scale factor from FrameResampleHandler.
        
        Called via signal when FrameResampleHandler changes preset/scale.
        This ensures px2mm calculations remain accurate when processing
        resolution changes.
        
        Args:
            scale_factor (float): New scale factor (e.g., 0.5 for 50% downsampling)
        """
        self.scale_factor = scale_factor
        logger.info(f"CalibrationHandler: Scale factor updated: {self.scale_factor}")
    
    def update_source_res(self, source_res):
        """Update source video resolution.
        
        Called via signal when source video resolution changes (e.g., new video loaded).
        
        Args:
            source_res (tuple[int, int]): Source resolution (width, height)
        """
        self.source_res = source_res
        logger.info(f"CalibrationHandler: Source resolution updated: {self.source_res}")
    
    def update_overlay_res(self, overlay_res):
        """Update overlay display resolution.
        
        Called when window is resized or video display size changes.
        
        Args:
            overlay_res (tuple[int, int]): Overlay resolution (width, height)
        """
        self.overlay_res = overlay_res
        logger.info(f"CalibrationHandler: Overlay resolution updated: {self.overlay_res}")

    # ============ Ruler Calibration Workflow ============

    def start_ruler_calibration(self):
        """Initiate ruler calibration mode for pixel-to-millimeter measurement.
        
        Emits ruler_draw_start signal to request OverlayWidget to enter
        ruler drawing mode. User will then click and drag to measure a
        known distance.
        
        Workflow:
            1. Emit ruler_draw_start → OverlayWidget.ruler_calibration()
            2. User draws line on overlay
            3. OverlayWidget.ruler_measured → handle_ruler_measurement()
        """
        if self.confirm_calibration:
            self.warning_box.emit(
                "You have already confirmed the arrow and ruler. Please reset the application if you want to change them.",
            )
            return
        
        # Request overlay widget to start ruler drawing mode
        self.ruler_draw_start.emit()

        # Inform the user via status bar
        self.status_message.emit(
            "Click and drag to draw a line for pixel measurement"
        )

    def _calculate_px2mm_with_scaling(self, source_px: float) -> tuple[float, float]:
        """Calculate px2mm ratio with resolution scaling applied.
        
        Core calibration calculation that accounts for the difference between
        display (source) resolution and processing resolution.
        
        Args:
            source_px (float): Measured distance in source video pixels
            
        Returns:
            tuple[float, float]: (display_px2mm, processing_px2mm)
                - display_px2mm: Pixels per mm for display/source resolution
                - processing_px2mm: Pixels per mm for processing resolution
        
        Example:
            source_px = 640 (pixels in 1280x720 source video)
            distance_mm = 20 (mm)
            scale_factor = 0.5 (processing at 640x360)
            
            display_px2mm = 640 / 20 = 32.0 px/mm
            processing_px2mm = 32.0 * 0.5 = 16.0 px/mm
        """
        scale_factor = self.scale_factor
        
        # Calculate px2mm for display resolution (source video)
        px_ratio_display_res = float(source_px / self.distance_mm)
        
        # Scale to processing resolution
        # When processing at 50% scale, pixels are half the size, so px/mm ratio is also halved
        px_ratio_processing_res = float(px_ratio_display_res * scale_factor)
        
        logger.info(
            f"CalibrationHandler: px2mm calculation:"
            f"  Source pixels: {source_px:.1f}px"
            f"  Distance: {self.distance_mm}mm"
            f"  Display px2mm: {px_ratio_display_res:.1f}"
            f"  Processing px2mm: {px_ratio_processing_res:.1f} (scale: {scale_factor:.2f})"
        )
        
        return px_ratio_display_res, px_ratio_processing_res

    def handle_ruler_measurement(self, overlay_px: float):
        """Process ruler measurement with coordinate transformation.
        
        Transforms ruler measurement from overlay space → source space → calculates
        px2mm for both display and processing resolutions.
        
        Args:
            overlay_px (float): Measured distance in overlay space (pixels)
        
        Workflow:
            1. Validate resolutions are initialized
            2. Transform: overlay pixels → source pixels (using CoordinateMapper)
            3. Calculate: source pixels → px2mm (display and processing)
            4. Emit results via signals
            5. Update GUI textbox and show user feedback
        
        Example:
            Overlay: 400px at 800x450
            Source: 1280x720
            Transform: 400 * (1280/800) = 640px in source
            Calculate: 640px / 20mm = 32.0 px/mm (display)
                      32.0 * 0.5 = 16.0 px/mm (processing at 50% scale)
        """
        from froth_monitor.utils.coordinate_mapper import CoordinateMapper
        
        # Validation: Ensure resolutions are initialized
        if self.source_res == (0, 0) or self.overlay_res == (0, 0):
            logger.warning("CalibrationHandler: Source or overlay resolution not initialized")
            return

        # Use stored resolution values
        source_res = self.source_res
        overlay_res = self.overlay_res
        
        # Transform overlay pixels → source pixels
        if source_res != (0, 0) and overlay_res != (0, 0) and overlay_res[0] > 0:
            # Create mapper for coordinate transformation
            mapper = CoordinateMapper(overlay_res, source_res)
            
            # For distance, use average scale factor (handles non-uniform scaling)
            scale_x, scale_y = mapper.get_scale_factors()
            scale = (scale_x + scale_y) / 2
            source_px = overlay_px * scale
            
            logger.info(
                f"Ruler calibration:\n"
                f"  Overlay:  {overlay_px:.1f}px at {overlay_res}\n"
                f"  Source:   {source_px:.1f}px at {source_res}\n"
                f"  Scale:    {scale:.2f}x"
            )
        else:
            # Fallback: use overlay pixels directly if transformation fails
            source_px = overlay_px
            logger.warning(
                f"Resolutions not initialized (source={source_res}, overlay={overlay_res})"
                f"using overlay pixels directly"
            )
        
        # Calculate px2mm with scaling (core calibration calculation)
        self.display_px2mm, self.processed_px2mm = self._calculate_px2mm_with_scaling(source_px)
        
        # Emit processing px2mm for FrameModel (used by optical flow algorithms)
        self.release_px2mm.emit(self.processed_px2mm)
        
        # Update GUI textbox with display px2mm (user-facing value)
        self.set_textbox_px2mm.emit(f"{self.display_px2mm:.1f}")
        
        # Display detailed result to user
        self.message_box.emit(
            f"Ruler Calibration\n"
            f"Measured {source_px:.1f}px in source video\n"
            f"Px to mm ratio for display resolution: {self.display_px2mm:.1f} per mm\n"
            f"Px to mm ratio for processed resolution: {self.processed_px2mm:.1f} per mm",
        )
        
        # Update status bar with summary
        self.status_message.emit(
            f"Calibrated: {source_px:.1f}px = {self.distance_mm}mm\n"
            f"Px2mm: {self.processed_px2mm:.1f}"
        )

    # ============ Arrow Direction Workflow ============

    def confirm_arrow_n_ruler(self):
        """Confirm calibration settings and recalculate px2mm with current scale.
        
        Called when user clicks confirm button. This method:
        1. Validates that px2mm has been set (either via ruler or manual entry)
        2. Recalculates processing px2mm using current scale factor
        3. Emits confirmed values to FrameModel
        4. Sets confirm_calibration = True (locks calibration)
        5. Triggers data export if enabled
        
        This ensures that even if user manually entered px2mm, the
        processing resolution value is correctly calculated with scaling.
        
        Raises:
            ValueError: If arrow direction or px2mm values are invalid
        """
        try:
            arrow_direction = float(self.arrow_direction)
            
            # Get the manually entered px2mm value (display resolution)
            px2mm_display = float(self.display_px2mm) if self.display_px2mm else None
            
            if px2mm_display is None or px2mm_display == 0:
                self.warning_box.emit("Please calibrate the ruler first or enter a valid px2mm value.")
                return
            
            # Recalculate to get processing resolution px2mm
            # px2mm_display is in "pixels per mm" for display resolution
            # Convert back to source pixels: source_px = px2mm_display * distance_mm
            source_px = px2mm_display * self.distance_mm
            
            # Apply scaling to get processing resolution px2mm
            self.display_px2mm, self.processed_px2mm = self._calculate_px2mm_with_scaling(source_px)
            
            # Emit values to FrameModel for use in optical flow calculations
            self.release_px2mm.emit(self.processed_px2mm)
            self.release_arrow_direction.emit(arrow_direction)
            self.set_textbox_px2mm.emit(str(self.display_px2mm))
            self.set_textbox_arrow_direction.emit(str(arrow_direction))
            
            logger.info(
                f"CalibrationHandler: Calibration confirmed:\n"
                f"  Arrow direction: {arrow_direction:.2f}°\n"
                f"  Display px2mm: {self.display_px2mm:.1f}\n"
                f"  Processing px2mm: {self.processed_px2mm:.1f}"
            )
            
        except ValueError as e:
            logger.error(f"ValueError in confirm_arrow_n_ruler: {e}")
            self.warning_box.emit("Please enter valid arrow direction and px2mm values.")
            return
    
        # Lock calibration (prevents further changes)
        self.confirm_calibration = True
        
        # Emit confirmation signal
        self.calibration_confirmed.emit()
        
        # Notify user
        self.message_box.emit("Overflow direction (arrow) and calibration (ruler) confirmed.")
    
    def start_arrow_drawing(self):
        """Initiate arrow drawing mode for overflow direction measurement.
        
        Emits arrow_draw_start signal to request OverlayWidget to enter
        arrow drawing mode. User will then click and drag to indicate
        the direction of froth overflow.
        
        Workflow:
            1. Emit arrow_draw_start → OverlayWidget.start_arrow_drawing()
            2. User draws arrow on overlay
            3. OverlayWidget.arrow_drawn → handle_arrow_drawing()
        """
        if self.confirm_calibration:
            logger.warning("You have already confirmed the arrow and ruler. Please reset the application if you want to change them.")
            return

        # Request overlay widget to start arrow drawing mode
        self.arrow_draw_start.emit()

        # Inform the user via status bar
        self.status_message.emit(
            "Click and drag to draw a line of 2cm for pixel measurement"
        )

    def handle_arrow_drawing(self, start_pos, end_pos, degree):
        """Process arrow drawing result.
        
        Args:
            start_pos: Arrow start position (unused, kept for compatibility)
            end_pos: Arrow end position (unused, kept for compatibility)
            degree (float): Calculated angle in degrees from horizontal
        
        Note:
            Angle convention: 0° = horizontal right, positive = counterclockwise
        """
        # Emit arrow direction to FrameModel
        self.release_arrow_direction.emit(degree)
        
        # Update GUI textbox
        self.set_textbox_arrow_direction.emit(f"{degree:.2f}")

        # Display result to user
        self.message_box.emit(
            f"Arrow drawed\n"
            f"angle: {degree:.1f} degrees (from the horizontal axis anticlockwisely)"
        )

        # Update status bar
        self.status_message.emit(f"arrow angle: {degree:.1f} degrees")

    # ============ Data Export Workflow ============

    def update_export_status(self, state: bool):
        """Enable or disable data export functionality.
        
        Called when export configuration is completed in MainHandler.
        If calibration is already confirmed when export is enabled,
        immediately exports current calibration data.
        
        Args:
            state (bool): True to enable export, False to disable
        """
        self.export_enable = state

        # If both calibration and export are ready, export immediately
        if self.confirm_calibration == True and self.export_enable == True:
            self.release_export_data.emit(self.arrow_direction, self.processed_px2mm)
