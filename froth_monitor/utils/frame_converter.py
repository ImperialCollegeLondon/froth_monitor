"""Frame conversion utilities for FrameProcessor.

This module provides pure utility functions for converting frames between
OpenCV (BGR) and Qt (RGB) formats, as well as resizing operations.
"""

import cv2
import logging
import numpy as np
from numpy.typing import NDArray
from PySide6.QtGui import QImage
from PySide6.QtCore import Qt

# Use standard logging to avoid circular import with handlers package
logger = logging.getLogger(__name__)


class FrameConverter:
    """Pure utility class for frame format conversions.
    
    Handles conversions between OpenCV (BGR) and Qt (RGB) formats,
    as well as resizing operations for processing and display.
    
    All methods are static as this is a stateless utility class.
    """
    
    @staticmethod
    def bgr_to_qimage(frame: NDArray[np.uint8]) -> QImage:
        """Convert BGR frame to QImage (RGB).
        
        Args:
            frame: OpenCV frame in BGR format (Height x Width x 3)
            
        Returns:
            QImage in RGB format
            
        Raises:
            ValueError: If frame is None or has invalid shape
            cv2.error: If color conversion fails
        """
        # Validate input
        if frame is None:
            raise ValueError("FrameConverter: Frame cannot be None")
        
        if len(frame.shape) != 3:
            raise ValueError(
                f"FrameConverter: Expected 3D frame, got shape {frame.shape}"
            )
        
        if frame.shape[2] != 3:
            raise ValueError(
                f"FrameConverter: Expected 3 channels (BGR), got {frame.shape[2]}"
            )
        
        # Convert BGR to RGB
        try:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        except cv2.error as e:
            logger.error(f"FrameConverter: Color conversion failed: {e}")
            raise
        
        # Create QImage
        h, w, ch = rgb_frame.shape
        bytes_per_line = ch * w
        
        return QImage(
            rgb_frame.data,
            w,
            h,
            bytes_per_line,
            QImage.Format.Format_RGB888
        )
    
    @staticmethod
    def scale_to_fit(
        qt_image: QImage,
        target_width: int,
        target_height: int,
        keep_aspect_ratio: bool = True
    ) -> QImage:
        """Scale QImage to fit target dimensions.
        
        Args:
            qt_image: Source QImage to scale
            target_width: Target width in pixels
            target_height: Target height in pixels
            keep_aspect_ratio: Whether to maintain aspect ratio (default: True)
            
        Returns:
            Scaled QImage
            
        Raises:
            ValueError: If target dimensions are invalid
        """
        if target_width <= 0 or target_height <= 0:
            raise ValueError(
                f"FrameConverter: Invalid target dimensions: "
                f"{target_width}x{target_height}"
            )
        
        aspect_mode = (
            Qt.AspectRatioMode.KeepAspectRatio 
            if keep_aspect_ratio 
            else Qt.AspectRatioMode.IgnoreAspectRatio
        )
        
        return qt_image.scaled(
            target_width,
            target_height,
            aspect_mode,
            Qt.TransformationMode.SmoothTransformation
        )
    
    @staticmethod
    def resize_frame(
        frame: NDArray[np.uint8],
        width: int,
        height: int,
        interpolation: int = cv2.INTER_LINEAR
    ):
        """Resize OpenCV frame to specified dimensions.
        
        Args:
            frame: Source frame to resize
            width: Target width in pixels
            height: Target height in pixels
            interpolation: OpenCV interpolation method (default: INTER_LINEAR)
            
        Returns:
            Resized frame
            
        Raises:
            ValueError: If dimensions are invalid or frame is None
        """
        if frame is None:
            raise ValueError("FrameConverter: Frame cannot be None")
        
        if width <= 0 or height <= 0:
            raise ValueError(
                f"FrameConverter: Invalid dimensions: {width}x{height}"
            )
        
        return cv2.resize(frame, (width, height), interpolation=interpolation)
