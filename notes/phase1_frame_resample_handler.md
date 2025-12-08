# Phase 1: Core FrameResampleHandler Implementation

## Objective

Build the foundational `FrameResampleHandler` class that can calculate and apply processing resolutions independently from display resolution, with preset quality configurations.

## Scope

**In Scope:**
- ✅ Create `FrameResampleHandler` class structure
- ✅ Implement resolution preset system (Ultra/High/Medium/Low/Custom)
- ✅ Implement `calculate_processing_size()` logic
- ✅ Implement `resample_frame()` method
- ✅ Unit tests for resolution calculations
- ✅ Basic integration with `FrameProcessor`

**Out of Scope (Future Phases):**
- ❌ GUI configuration dialog
- ❌ Coordinate mapping system
- ❌ ROI coordinate transformation
- ❌ User preferences persistence
- ❌ Performance monitoring

## Implementation Steps

### Step 1: Create File Structure

Create new file: `froth_monitor/handlers/frame_resample_handler.py`

```python
"""Frame Resample Handler Module.

Manages frame resampling for the processing pipeline, decoupling processing
resolution from display resolution to optimize performance.
"""

import cv2
from enum import Enum
from PySide6.QtCore import QObject, Signal
from froth_monitor.handlers.logger_config import get_logger

logger = get_logger(__name__)
```

### Step 2: Define Resolution Presets

```python
class ResolutionPreset(Enum):
    """Predefined quality presets for processing resolution.
    
    Each preset defines a scale factor and maximum resolution limits
    to balance quality and performance.
    """
    ULTRA = "ultra"      # 100% of source, no limits
    HIGH = "high"        # 75% of source, max 1920x1080
    MEDIUM = "medium"    # 50% of source, max 1280x720
    LOW = "low"          # 25% of source, max 640x480
    CUSTOM = "custom"    # User-defined parameters


# Preset configuration mappings
PRESET_CONFIG = {
    ResolutionPreset.ULTRA: {
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
```

### Step 3: Implement FrameResampleHandler Class

```python
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
    preset_changed = Signal(str)        # Preset name
    
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
    
    def set_preset(self, preset: ResolutionPreset) -> None:
        """Change the active resolution preset.
        
        Args:
            preset: New resolution preset to apply
        """
        if preset != self.current_preset:
            self.current_preset = preset
            logger.info(f"Resolution preset changed to: {preset.value}")
            self.preset_changed.emit(preset.value)
            
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
        
        logger.debug(f"Custom parameters set: scale={self.custom_scale}, "
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
        proc_w = max(320, proc_w)
        proc_h = max(240, proc_h)
        
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
            logger.debug("Processing resolution matches source, skipping resize")
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
            
            logger.info(f"Processing resolution updated: {src_w}x{src_h} → "
                       f"{new_proc_w}x{new_proc_h} "
                       f"({(new_proc_w/src_w)*100:.1f}% scale)")
            
            self.resolution_changed.emit(self.processing_resolution)
    
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
```

### Step 4: Unit Tests

Create file: `froth_monitor/tests/test_frame_resample_handler.py`

```python
"""Unit tests for FrameResampleHandler."""

import pytest
import numpy as np
from froth_monitor.handlers.frame_resample_handler import (
    FrameResampleHandler,
    ResolutionPreset,
    PRESET_CONFIG
)


class TestFrameResampleHandler:
    """Test suite for FrameResampleHandler."""
    
    def test_initialization(self):
        """Test handler initializes with default medium preset."""
        handler = FrameResampleHandler()
        assert handler.current_preset == ResolutionPreset.MEDIUM
        assert handler.processing_resolution == (0, 0)
    
    def test_calculate_processing_size_medium_preset(self):
        """Test medium preset calculates 50% scale with 1280x720 max."""
        handler = FrameResampleHandler()
        
        # Test with 1920x1080 source (should scale to 960x540)
        proc_w, proc_h = handler.calculate_processing_size(1920, 1080)
        assert proc_w == 960
        assert proc_h == 540
        
        # Test with 4K source (should cap at 1280x720)
        proc_w, proc_h = handler.calculate_processing_size(3840, 2160)
        assert proc_w == 1280
        assert proc_h == 720
    
    def test_calculate_processing_size_ultra_preset(self):
        """Test ultra preset returns full resolution."""
        handler = FrameResampleHandler()
        handler.set_preset(ResolutionPreset.ULTRA)
        
        proc_w, proc_h = handler.calculate_processing_size(1920, 1080)
        assert proc_w == 1920
        assert proc_h == 1080
    
    def test_calculate_processing_size_low_preset(self):
        """Test low preset calculates 25% scale with 640x480 max."""
        handler = FrameResampleHandler()
        handler.set_preset(ResolutionPreset.LOW)
        
        proc_w, proc_h = handler.calculate_processing_size(1920, 1080)
        assert proc_w == 480
        assert proc_h == 270
    
    def test_even_dimensions(self):
        """Test that output dimensions are always even."""
        handler = FrameResampleHandler()
        
        # Test with odd source dimensions
        proc_w, proc_h = handler.calculate_processing_size(1921, 1081)
        assert proc_w % 2 == 0
        assert proc_h % 2 == 0
    
    def test_minimum_dimensions(self):
        """Test that minimum dimensions are enforced."""
        handler = FrameResampleHandler()
        handler.set_preset(ResolutionPreset.LOW)
        
        # Very small source should still meet minimum
        proc_w, proc_h = handler.calculate_processing_size(400, 300)
        assert proc_w >= 320
        assert proc_h >= 240
    
    def test_custom_preset(self):
        """Test custom preset with user-defined parameters."""
        handler = FrameResampleHandler()
        handler.set_custom_parameters(scale=0.6, max_width=1600, max_height=900)
        handler.set_preset(ResolutionPreset.CUSTOM)
        
        proc_w, proc_h = handler.calculate_processing_size(1920, 1080)
        expected_w = int(1920 * 0.6)
        expected_h = int(1080 * 0.6)
        assert proc_w == expected_w - (expected_w % 2)
        assert proc_h == expected_h - (expected_h % 2)
    
    def test_resample_frame(self):
        """Test frame resampling functionality."""
        handler = FrameResampleHandler()
        
        # Create test frame (1920x1080)
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        
        resampled, proc_res = handler.resample_frame(frame)
        
        # Should be resampled to 960x540 (medium preset)
        assert resampled.shape[1] == 960
        assert resampled.shape[0] == 540
        assert proc_res == (960, 540)
    
    def test_preset_change_signal(self, qtbot):
        """Test that preset change emits signal."""
        handler = FrameResampleHandler()
        
        with qtbot.waitSignal(handler.preset_changed) as blocker:
            handler.set_preset(ResolutionPreset.HIGH)
        
        assert blocker.args[0] == "high"
    
    def test_resolution_changed_signal(self, qtbot):
        """Test that resolution change emits signal."""
        handler = FrameResampleHandler()
        
        with qtbot.waitSignal(handler.resolution_changed) as blocker:
            frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
            handler.resample_frame(frame)
        
        assert blocker.args[0] == (960, 540)
    
    def test_aspect_ratio_preservation(self):
        """Test that aspect ratio is preserved when applying max limits."""
        handler = FrameResampleHandler()
        
        # 16:9 source
        proc_w, proc_h = handler.calculate_processing_size(1920, 1080)
        aspect_ratio = proc_w / proc_h
        assert abs(aspect_ratio - (16/9)) < 0.01
        
        # 4:3 source
        proc_w, proc_h = handler.calculate_processing_size(1600, 1200)
        aspect_ratio = proc_w / proc_h
        assert abs(aspect_ratio - (4/3)) < 0.01
```

### Step 5: Basic FrameProcessor Integration

Modify `froth_monitor/handlers/frame_processor.py`:

```python
# In __init__
def __init__(self, event_handler, gui, frame_model, video_thread, overlay_widget,
             video_recorder, roi_handler, velocity_plotter, frame_resample_handler):
    # ... existing code ...
    self.frame_resample_handler = frame_resample_handler

# In process_new_frame
def process_new_frame(self, frame):
    if not self.playing:
        return
    
    self.current_frame = frame
    
    # Display path (unchanged)
    qt_image = self._convert_frame_to_qimage(frame)
    scaled_image = self._scale_image_to_canvas(qt_image)
    
    # Processing path (NEW - uses FrameResampleHandler)
    processing_frame, proc_res = self.frame_resample_handler.resample_frame(frame)
    
    # Process at optimal resolution
    self.video_thread.if_release = False
    self._process_frame_with_model(processing_frame)
    self.video_thread.if_release = True
    
    # ... rest of method unchanged ...
```

### Step 6: MainHandler Integration

Modify `froth_monitor/handlers/main_handler.py`:

```python
# In initialize_level_two_handlers()
def initialize_level_two_handlers(self) -> None:
    # ... existing code ...
    
    # Frame resampling configuration
    self.frame_resample_handler = FrameResampleHandler()
    logger.info("FrameResampleHandler initialized")

# In initialize_level_three_handlers()
def initialize_level_three_handlers(self) -> None:
    # ... existing code ...
    
    self.frame_processor = FrameProcessor(
        self,
        self.gui,
        self.frame_model,
        self.video_thread,
        self.overlay_widget,
        self.video_recorder,
        self.roi_handler,
        self.data_handler,
        self.frame_resample_handler  # Add new parameter
    )
```

## Testing Strategy

### Unit Tests
- ✅ Test all resolution presets
- ✅ Test custom parameters
- ✅ Test dimension constraints (even, minimum)
- ✅ Test aspect ratio preservation
- ✅ Test signal emissions

### Integration Tests
- ✅ Test with actual video frames
- ✅ Test preset changes during playback
- ✅ Test with various camera resolutions (640x480, 1920x1080, 4K)

### Manual Tests
- ✅ Load 1080p video → verify processing at 960x540
- ✅ Load 4K video → verify capped at 1280x720
- ✅ Load 480p video → verify minimum dimensions
- ✅ Check logs for resolution info

## Acceptance Criteria

✅ **AC1**: `FrameResampleHandler` class created with all methods implemented
✅ **AC2**: All 4 presets (Ultra/High/Medium/Low) calculate correct resolutions
✅ **AC3**: Custom preset allows user-defined scale and max dimensions
✅ **AC4**: Output dimensions are always even (divisible by 2)
✅ **AC5**: Minimum dimensions (320x240) are enforced
✅ **AC6**: Aspect ratio is preserved when applying max limits
✅ **AC7**: Signals emit correctly when preset or resolution changes
✅ **AC8**: Unit tests pass with >90% coverage
✅ **AC9**: `FrameProcessor` successfully uses resampled frames
✅ **AC10**: Processing resolution is independent of display resolution

## Success Metrics

- Unit test coverage: >90%
- All acceptance criteria met
- No performance regression (< 5ms per frame overhead)
- Logs show correct resolution calculations

## Next Steps (Phase 2)

After Phase 1 completion:
1. Implement `CoordinateMapper` for ROI coordinate transformation
2. Update `ROI` class to store dual coordinates
3. Integrate coordinate mapping with `ROIHandler`
