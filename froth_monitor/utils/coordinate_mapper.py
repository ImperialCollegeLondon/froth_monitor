"""Coordinate mapping utilities for resolution transformation.

This module provides coordinate transformation between display resolution
(where users interact) and processing resolution (where optical flow runs).
"""

import logging
from typing import Tuple

logger = logging.getLogger(__name__)


class CoordinateMapper:
    """Transform coordinates between display and processing resolutions.
    
    Handles coordinate transformations when display resolution differs
    from processing resolution due to FrameResampleHandler resampling.
    
    This ensures ROI coordinates drawn by users on the display are correctly
    mapped to the processing frame coordinates for accurate optical flow analysis.
    
    Example:
        Display resolution: 640x480
        Processing resolution: 320x240 (50% scale)
        
        User draws ROI at (100, 50, 200, 150) on display
        → Transformed to (50, 25, 100, 75) for processing
    """
    
    def __init__(self, display_resolution: Tuple[int, int], 
                 processing_resolution: Tuple[int, int]):
        """Initialize mapper with resolution pair.
        
        Args:
            display_resolution: (width, height) of displayed video
            processing_resolution: (width, height) of processing pipeline
            
        Raises:
            ValueError: If resolutions contain zero or negative values
        """
        if display_resolution[0] <= 0 or display_resolution[1] <= 0:
            raise ValueError(f"Invalid display resolution: {display_resolution}")
        
        if processing_resolution[0] <= 0 or processing_resolution[1] <= 0:
            raise ValueError(f"Invalid processing resolution: {processing_resolution}")
        
        self.display_width, self.display_height = display_resolution
        self.proc_width, self.proc_height = processing_resolution
        
        # Calculate scale factors
        self.scale_x = self.proc_width / self.display_width
        self.scale_y = self.proc_height / self.display_height
        
        logger.debug(
            f"CoordinateMapper initialized: "
            f"Display {display_resolution} → Processing {processing_resolution} "
            f"(scale: {self.scale_x:.2%} x {self.scale_y:.2%})"
        )
    
    def display_to_processing(self, x: int, y: int, 
                             width: int, height: int) -> Tuple[int, int, int, int]:
        """Transform coordinates from display to processing space.
        
        Args:
            x: X coordinate (left) in display space
            y: Y coordinate (top) in display space
            width: Width in display space
            height: Height in display space
            
        Returns:
            Tuple of (x, y, width, height) in processing space
            
        Example:
            >>> mapper = CoordinateMapper((640, 480), (320, 240))
            >>> mapper.display_to_processing(100, 50, 200, 150)
            (50, 25, 100, 75)
        """
        proc_x = int(x * self.scale_x)
        proc_y = int(y * self.scale_y)
        proc_width = max(1, int(width * self.scale_x))  # Minimum 1 pixel
        proc_height = max(1, int(height * self.scale_y))  # Minimum 1 pixel
        
        logger.debug(
            f"Display→Processing: ({x}, {y}, {width}, {height}) → "
            f"({proc_x}, {proc_y}, {proc_width}, {proc_height})"
        )
        
        return proc_x, proc_y, proc_width, proc_height
    
    def processing_to_display(self, x: int, y: int, 
                             width: int, height: int) -> Tuple[int, int, int, int]:
        """Transform coordinates from processing to display space.
        
        Args:
            x: X coordinate (left) in processing space
            y: Y coordinate (top) in processing space
            width: Width in processing space
            height: Height in processing space
            
        Returns:
            Tuple of (x, y, width, height) in display space
            
        Example:
            >>> mapper = CoordinateMapper((640, 480), (320, 240))
            >>> mapper.processing_to_display(50, 25, 100, 75)
            (100, 50, 200, 150)
        """
        disp_x = int(x / self.scale_x)
        disp_y = int(y / self.scale_y)
        disp_width = max(1, int(width / self.scale_x))  # Minimum 1 pixel
        disp_height = max(1, int(height / self.scale_y))  # Minimum 1 pixel
        
        logger.debug(
            f"Processing→Display: ({x}, {y}, {width}, {height}) → "
            f"({disp_x}, {disp_y}, {disp_width}, {disp_height})"
        )
        
        return disp_x, disp_y, disp_width, disp_height
    
    def scale_delta(self, delta_x: float, delta_y: float, 
                   to_display: bool = False) -> Tuple[float, float]:
        """Scale optical flow delta pixels between coordinate spaces.
        
        Used to transform motion vectors between processing and display spaces.
        Processing calculates delta in processing resolution, but display needs
        it in display resolution for visualization.
        
        Args:
            delta_x: X component of motion vector
            delta_y: Y component of motion vector
            to_display: If True, scale from processing to display
                       If False, scale from display to processing
            
        Returns:
            Tuple of (scaled_delta_x, scaled_delta_y)
            
        Example:
            # Motion calculated in processing space (320x240)
            delta_x, delta_y = 10.0, 5.0
            
            # Scale to display space (640x480) for visualization
            >>> mapper = CoordinateMapper((640, 480), (320, 240))
            >>> mapper.scale_delta(10.0, 5.0, to_display=True)
            (20.0, 10.0)
        """
        if to_display:
            # Processing → Display: divide by scale factor
            scaled_x = delta_x / self.scale_x
            scaled_y = delta_y / self.scale_y
        else:
            # Display → Processing: multiply by scale factor
            scaled_x = delta_x * self.scale_x
            scaled_y = delta_y * self.scale_y
        
        return scaled_x, scaled_y
    
    def get_scale_factors(self) -> Tuple[float, float]:
        """Get the scale factors for this mapping.
        
        Returns:
            Tuple of (scale_x, scale_y)
        """
        return self.scale_x, self.scale_y
    
    def is_identity(self) -> bool:
        """Check if this is an identity mapping (no scaling).
        
        Returns:
            True if display and processing resolutions are the same
        """
        return (self.display_width == self.proc_width and 
                self.display_height == self.proc_height)
