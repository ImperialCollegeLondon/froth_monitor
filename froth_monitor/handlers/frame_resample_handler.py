"""Frame Resample Handler Module.

Manages frame resampling for the processing pipeline, decoupling processing
resolution from display resolution to optimize performance.
"""

import cv2
from enum import Enum
from typing import Any, Dict
from PySide6.QtCore import QObject, Signal
from froth_monitor.handlers.logger_config import get_logger

logger = get_logger(__name__)


class ResolutionPreset(Enum):
    """Predefined quality presets for processing resolution.
    
    Each preset defines a scale factor and maximum resolution limits
    to balance quality and performance.
    """
    ORIGINAL = "original"      # 100% of source, no limits
    HIGH = "high"        # 75% of source, max 1920x1080
    MEDIUM = "medium"    # 50% of source, max 1280x720
    LOW = "low"          # 25% of source, max 640x480
    CUSTOM = "custom"    # User-defined parameters


# Preset configuration mappings
PRESET_CONFIG: Dict[ResolutionPreset, Dict[str, Any]] = {
    ResolutionPreset.ORIGINAL: {
        "scale": 1.0,
        "max_width": None,
        "max_height": None,
        "description": "Full resolution - Best quality"
    },
    ResolutionPreset.HIGH: {
        "scale": 0.75,
        "max_width": 1920,
        "max_height": 1080,
        "description": "High quality - 75% scale"
    },
    ResolutionPreset.MEDIUM: {
        "scale": 0.5,
        "max_width": 1280,
        "max_height": 720,
        "description": "Balanced - 50% scale (Default)"
    },
    ResolutionPreset.LOW: {
        "scale": 0.25,
        "max_width": 640,
        "max_height": 480,
        "description": "Performance - 25% scale"
    },
}


class FrameResampleHandler(QObject):
    """Manages frame resampling for processing pipeline.
    
    Decouples processing resolution from display resolution, allowing
    users to optimize the balance between quality and performance.
    
    Attributes:
        current_preset: Active resolution preset
        custom_scale: Scale factor for custom preset (0.0-1.0)
        custom_max_width: Maximum width for custom preset
        custom_max_height: Maximum height for custom preset
        source_resolution: Original video/camera resolution
        processing_resolution: Calculated processing resolution
    
    Signals:
        resolution_changed(tuple): Emitted when processing resolution changes
        preset_changed(str): Emitted when preset changes
    """
    
    # Signals
    resolution_changed = Signal(tuple)  # (width, height)
    scale_changed = Signal(float)       # Scale factor
    preset_changed = Signal(str)        # Preset name
    available_resolutions = Signal(object) # Dictionary of preset: formatting string
    
    def __init__(self):
        """Initialize handler with default Medium preset."""
        super().__init__()
        
        # Preset configuration
        self.current_preset = ResolutionPreset.MEDIUM
        self.custom_scale = 0.5
        self.custom_max_width = 1280
        self.custom_max_height = 720
        
        # Resolution tracking
        self.source_resolution = (0, 0)      # Video/camera original size
        self.processing_resolution = (0, 0)  # Calculated processing size
        
        logger.info(f"FrameResampleHandler initialized with preset: {self.current_preset.value}")
    
    def _calculate_all_resolutions(self) -> dict:
        """Calculate resolution for all presets based on current source."""
        if self.source_resolution == (0, 0):
            return {}
            
        src_w, src_h = self.source_resolution
        resolutions = {}
        
        for preset in ResolutionPreset:
            if preset == ResolutionPreset.CUSTOM:
                continue
                
            config = PRESET_CONFIG[preset]
            scale = config["scale"]
            max_w = config["max_width"]
            max_h = config["max_height"]
            
            # Reimplement calculation logic for this specific preset
            # (We cannot call calculate_processing_size directly as it relies on self.current_preset)
            
            proc_w = int(src_w * scale)
            proc_h = int(src_h * scale)
            
            if max_w and proc_w > max_w:
                ratio = max_w / proc_w
                proc_w = max_w
                proc_h = int(proc_h * ratio)
            
            if max_h and proc_h > max_h:
                ratio = max_h / proc_h
                proc_h = max_h
                proc_w = int(proc_w * ratio)
                
            proc_w = proc_w - (proc_w % 2)
            proc_h = proc_h - (proc_h % 2)
            
            # Format: "Original (1920x1080)"
            label = f"{preset.value.title()} ({proc_w}x{proc_h})"
            resolutions[preset] = label
            
        return resolutions
    
    def set_preset(self, preset: ResolutionPreset) -> None:
        """Change the active resolution preset.
        
        Args:
            preset: New resolution preset to apply
        """
        if preset != self.current_preset:
            self.current_preset = preset
            logger.info(f"FrameResampleHandler: Resolution preset changed to: {preset.value}")
            self.preset_changed.emit(preset.value)
            self.custom_scale = PRESET_CONFIG[preset]["scale"]

            # Recalculate if source resolution is known
            if self.source_resolution != (0, 0):
                self._recalculate_processing_resolution()
    
    def set_custom_parameters(self, scale: float, max_width: int, max_height: int) -> None:
        """Configure custom resolution parameters.
        
        Args:
            scale: Scale factor (0.0-1.0)
            max_width: Maximum processing width in pixels
            max_height: Maximum processing height in pixels
        """
        self.custom_scale = max(0.1, min(1.0, scale))  # Clamp to [0.1, 1.0]
        self.custom_max_width = max(320, max_width)     # Minimum 320px
        self.custom_max_height = max(240, max_height)   # Minimum 240px
        
        logger.info(f"FrameResampleHandler: Custom parameters set: scale={self.custom_scale}, "
                    f"max={self.custom_max_width}x{self.custom_max_height}")
        
        if self.current_preset == ResolutionPreset.CUSTOM:
            self._recalculate_processing_resolution()
    
    def calculate_processing_size(self, source_width: int, source_height: int) -> tuple[int, int]:
        """Calculate optimal processing resolution based on current preset.
        
        Args:
            source_width: Original frame width
            source_height: Original frame height
        
        Returns:
            Tuple of (processing_width, processing_height)
        """
        # Get preset configuration
        if self.current_preset == ResolutionPreset.CUSTOM:
            scale = self.custom_scale
            max_w = self.custom_max_width
            max_h = self.custom_max_height
        else:
            config = PRESET_CONFIG[self.current_preset]
            scale = config["scale"]
            max_w = config["max_width"]
            max_h = config["max_height"]
        
        # Apply scale factor
        proc_w = int(source_width * scale)
        proc_h = int(source_height * scale)
        
        # Apply maximum dimension limits (if set)
        if max_w and proc_w > max_w:
            # Scale down to fit width, maintaining aspect ratio
            ratio = max_w / proc_w
            proc_w = max_w
            proc_h = int(proc_h * ratio)
        
        if max_h and proc_h > max_h:
            # Scale down to fit height, maintaining aspect ratio
            ratio = max_h / proc_h
            proc_h = max_h
            proc_w = int(proc_w * ratio)
        
        # Ensure even dimensions (required by many video codecs)
        proc_w = proc_w - (proc_w % 2)
        proc_h = proc_h - (proc_h % 2)
        
        # Enforce minimum dimensions
        # proc_w = max(320, proc_w)
        # proc_h = max(240, proc_h)
        
        return proc_w, proc_h
    
    def resample_frame(self, frame) -> tuple:
        """Resample frame to processing resolution.
        
        On first call, calculates and caches processing resolution.
        Subsequent calls use cached resolution for consistency.
        
        Args:
            frame: Input frame (numpy array)
        
        Returns:
            Tuple of (resampled_frame, processing_resolution)
        """
        frame_h, frame_w = frame.shape[:2]
        
        # First frame or source resolution changed
        if self.processing_resolution == (0, 0) or self.source_resolution != (frame_w, frame_h):
            self.source_resolution = (frame_w, frame_h)
            self._recalculate_processing_resolution()
        
        proc_w, proc_h = self.processing_resolution
        
        # Skip resampling if resolution matches
        if (proc_w, proc_h) == (frame_w, frame_h):
            logger.debug("FrameResampleHandler: Processing resolution matches source, skipping resize")
            return frame, self.processing_resolution
        
        # Resample frame
        resampled = cv2.resize(frame, (proc_w, proc_h), interpolation=cv2.INTER_LINEAR)
        
        return resampled, self.processing_resolution
    
    def _recalculate_processing_resolution(self) -> None:
        """Recalculate processing resolution and emit change signal."""
        if self.source_resolution == (0, 0):
            return
        
        src_w, src_h = self.source_resolution
        new_proc_w, new_proc_h = self.calculate_processing_size(src_w, src_h)
        
        if self.processing_resolution != (new_proc_w, new_proc_h):
            self.processing_resolution = (new_proc_w, new_proc_h)
            
            logger.info(f"FrameResampleHandler: Processing resolution updated: {src_w}x{src_h} -> "
                       f"{new_proc_w}x{new_proc_h} "
                       f"({(new_proc_w/src_w)*100:.1f}% scale)")
            
            self.resolution_changed.emit(self.processing_resolution)
            self.scale_changed.emit(self.custom_scale)
            
            # Update available resolutions list GUI
            resolutions_map = self._calculate_all_resolutions()
            self.available_resolutions.emit(resolutions_map)
    
    def get_resolution_info(self) -> dict:
        """Get current resolution information.
        
        Returns:
            Dictionary with source, processing, and preset info
        """
        return {
            "preset": self.current_preset.value,
            "source_resolution": self.source_resolution,
            "processing_resolution": self.processing_resolution,
            "scale_percent": (self.processing_resolution[0] / self.source_resolution[0] * 100) 
                           if self.source_resolution[0] > 0 else 0
        }
    
    def cleanup(self) -> None:
        """Clean up resources and reset state.
        
        This method should be called when ending a session or resetting
        the application to free memory and reset resolution state.
        """
        logger.info("FrameResampleHandler: Starting cleanup...")
        
        # Reset resolution state
        self.source_resolution = (0, 0)
        self.processing_resolution = (0, 0)
        
        # Reset to default preset
        self.current_preset = ResolutionPreset.MEDIUM
        self.custom_scale = 0.5
        self.custom_max_width = 1280
        self.custom_max_height = 720
        
        logger.info("FrameResampleHandler: Cleanup complete - state reset to defaults")
