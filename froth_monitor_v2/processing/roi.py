"""ROI (Region of Interest) Module for Optical Flow Analysis.

This module defines the ROI class for managing optical flow velocity
calculations with coordinate transformations and historical tracking.
"""

import math
import numpy as np
import time
import logging
from typing import Any
from datetime import datetime
from froth_monitor.processing.image_analysis import VideoAnalysis

logger = logging.getLogger(__name__)



class ROIConstants:
    """Configuration constants for ROI processing."""
    AVERAGE_VELOCITY_WINDOW_SIZE = 30  # Samples for rolling average
    TIMESTAMP_PRECISION = 8  # HH:MM:SS format length
    MAX_VALID_DELTA = 1e6  # Maximum valid delta/velocity
    DEFAULT_PX2MM = 1.0
    DEFAULT_DEGREE = -90.0


class ROI:
    """Region of Interest for Optical Flow Analysis.
    
    Manages optical flow velocity calculations with coordinate transformations,
    velocity accumulation, and historical data tracking.
    """
    
    def __init__(self, px2mm: float, degree: float) -> None:
        """Initialize ROI with calibration parameters."""
        self._init_coordinates()
        self._init_optical_flow()
        self._init_calibration(px2mm, degree)
        self._init_history_tracking()
        self._init_timestamps()
        
        logger.debug(f"ROI initialized: px2mm={px2mm}, degree={degree}")
    
    # ============ Initialization Helpers ============
    
    def _init_coordinates(self) -> None:
        """Initialize coordinate system."""
        self.display_coordinate: tuple[int, int, int, int] | None = None
        self.processing_coordinate: tuple[int, int, int, int] | None = None
        self.coordinate: tuple[int, int, int, int] | None = None
    
    def _init_optical_flow(self) -> None:
        """Initialize optical flow components."""
        self.analysis = VideoAnalysis(0, 0)
        self.delta_pixels: tuple[float, float] | None = (0.0, 0.0)
        self.cross_position: Any | None = None
        self.matcher: Any | None = None
    
    def _init_calibration(self, px2mm: float, degree: float) -> None:
        """Initialize calibration parameters."""
        if px2mm <= 0:
            raise ValueError(f"px2mm must be positive, got {px2mm}")
        
        self.id = 0
        self.px2mm = px2mm
        self.mm2px = 1 / px2mm
        self.degree = degree
        self.arrow_dir = 0.0
    
    def _init_history_tracking(self) -> None:
        """Initialize history tracking lists."""
        self.delta_history: list = []
        self.sum_history: list = []
        self.velo_history: list[float] = []
        self.velo_history_with_time: list = []
        self.current_velocity = 0.0
        self.average_velocity_past_30s: float | None = None
    
    def _init_timestamps(self) -> None:
        """Initialize timestamp tracking."""
        self.timestamp = time.strftime("%H:%M:%S", time.localtime())
        self.timestamp_buffer = self.timestamp
    
    # ============ Properties for Backward Compatibility ============
    
    @property
    def velo_only_history(self) -> list[float]:
        """Alias for velo_history."""
        return self.velo_history
    
    @property
    def velo_only_history_for_display(self) -> list[float]:
        """DEPRECATED: Use velo_history directly."""
        return self.velo_history
    
    @property
    def sum_history_for_display(self) -> list:
        """DEPRECATED: Use sum_history directly."""
        return self.sum_history
    
    # ============ Validation Helpers ============
    
    def _is_valid_delta(self, value: float) -> bool:
        """Check if delta value is valid and finite."""
        return np.isfinite(value) and abs(value) < ROIConstants.MAX_VALID_DELTA
    
    def _sanitize_delta(self, value: float) -> float:
        """Sanitize delta, returning 0.0 if invalid."""
        return value if self._is_valid_delta(value) else 0.0
    
    # ============ Coordinate Management ============
    
    def set_display_coordinate(self, display_coord: tuple[int, int, int, int]) -> None:
        self.display_coordinate = display_coord
    
    def set_processing_coordinate(self, proc_coord: tuple[int, int, int, int]) -> None:
        """Set coordinates for processing space and update active coordinate.
        
        Args:
            proc_coord: (x, y, width, height) in processing resolution
        """
        self.processing_coordinate = proc_coord
        self.coordinate = proc_coord  # Processing uses this coordinate
    
    def update_id(self, id: int):
        self.id = id

    def process_frame(self, frame: np.ndarray) -> tuple[bool, bool]:
        """
        Process a cropped frame using the VideoAnalysis.analyze function and store the results.

        Parameters
        ----------
        frame : np.ndarray
            The cropped video frame to process.
        """

        self.delta_pixels = self.analysis.analyze(frame)

        if self.delta_pixels == (None, None):
            return False, False

        self.calibrated_delta = self.project_delta_on_direction(self.delta_pixels)

        # Update timestamp
        self.timestamp = datetime.now().strftime("%H:%M:%S.%f")

        # self.timestamp = time.strftime("%H:%M:%S.%f", time.localtime())
        if_new_velo = self.accumulate_velocity_per_second(self.calibrated_delta)
        if_new_average = self.update_rolling_average()
        self.delta_history.append(
            [self.timestamp, self.delta_pixels, self.calibrated_delta]
        )

        return if_new_velo, if_new_average

    def project_delta_on_direction(self, delta_pixels: tuple[float, float]) -> float:
        """Project pixel delta onto the specified direction angle.
        
        Calculates the component of motion in the direction specified by self.degree
        using vector projection (dot product). Converts result from pixels to millimeters.
        
        Args:
            delta_pixels: (delta_x, delta_y) movement in pixels
        
        Returns:
            Projected delta in mm/frame in the specified direction
        """

        # Convert degree to radians
        rad = math.radians(self.degree)

        # Create a unit vector in the direction of self.degree
        # Note: In the coordinate system, 0 degrees points right, and angles increase counterclockwise
        # But y-axis is inverted (positive y is downward), so we need to negate the y component
        direction_x = math.cos(rad)
        direction_y = -math.sin(rad)  # Negative because positive y is downward

        # Extract delta_x and delta_y from delta_pixels
        delta_x, delta_y = delta_pixels

        # Validate input values
        if not (np.isfinite(delta_x) and np.isfinite(delta_y)):
            return 0.0

        # Calculate the dot product (projection)
        projection = delta_x * direction_x + delta_y * direction_y

        # Validate projection result
        if not np.isfinite(projection):
            return 0.0

        # Convert from pixels to millimeters
        projection_mm = projection * self.mm2px


        return projection_mm

    def accumulate_velocity_per_second(self, delta: float) -> bool:
        """Accumulate velocity measurements into per-second values.
        
        Delta values are accumulated within the same second (based on timestamp),
        then stored when the second changes.
        
        Args:
            delta: Calibrated delta in mm/frame
        
        Returns:
            True if new per-second velocity was stored, False if still accumulating
        """
        # Sanitize input
        delta = self._sanitize_delta(delta)
        
        # Extract current second (HH:MM:SS)
        current_second = self.timestamp[:ROIConstants.TIMESTAMP_PRECISION]
        
        # Still in same second - accumulate
        if current_second == self.timestamp_buffer:
            self.current_velocity += delta
            self.current_velocity = self._sanitize_delta(self.current_velocity)
            return False

        # New second - store accumulated velocity and reset
        self.timestamp_buffer = current_second
        
        # Store velocity for this past second
        velocity = self._sanitize_delta(self.current_velocity)
        self.velo_history.append(velocity)
        self.velo_history_with_time.append([velocity, self.timestamp, time.time()])
        
        # Reset accumulator with current delta
        self.current_velocity = delta
        
        return True

    def update_rolling_average(self) -> bool:
        """Calculate rolling average velocity over window.
        
        Computes average every N samples (defined by AVERAGE_VELOCITY_WINDOW_SIZE).
        Filters out invalid values before averaging.
        
        Returns:
            True if new average was calculated, False otherwise
        """
        window_size = ROIConstants.AVERAGE_VELOCITY_WINDOW_SIZE
        
        # Update every N samples
        if len(self.velo_history) % window_size != 0:
            return False
        
        # Get recent values
        recent_values = self.velo_history[-window_size:]
        # Filter valid values only
        valid_values = [v for v in recent_values if self._is_valid_delta(v)]
        
        # Calculate average
        if valid_values:
            average = sum(valid_values) / len(valid_values)
            self.average_velocity_past_30s = self._sanitize_delta(average)
        else:
            self.average_velocity_past_30s = 0.0
        
        return True

    def configure_optical_flow(self, algorithm: str, params: dict) -> None:
        """Configure optical flow algorithm and parameters.
        
        Args:
            algorithm: Algorithm name ("Farneback", "Lucas-kanade", or "DIS")
            params: Algorithm-specific parameters dictionary
        """
        
        self.analysis.current_algorithm = algorithm

        if algorithm == "Farneback":
            self.analysis.of_params = params
        elif algorithm == "Lucas-kanade":
            self.analysis.lk_params = params
        elif algorithm == "DIS":
            self.analysis.set_dis_preset(params.get("preset", "Medium"))
        
        logger.debug(f"ROI {self.id}: Configured optical flow - {algorithm}")
    
    # Backward compatibility alias
    def get_algorithm_n_params(self, algorithm: str, params: dict) -> None:
        """DEPRECATED: Use configure_optical_flow() instead."""
        self.configure_optical_flow(algorithm, params)

    def update_sum_history(self, data: list) -> None:
        """Append data to summary history."""
        self.sum_history.append(data)

    def clear_display_history(self) -> None:
        """Clear display history - no-op since properties are views."""
        pass  # Properties are views of main lists
