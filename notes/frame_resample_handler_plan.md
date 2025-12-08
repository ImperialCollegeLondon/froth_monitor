# Frame Resample Handler Implementation Plan

## Overview

Create a dedicated `FrameResampleHandler` to decouple processing resolution from display resolution, giving users control over quality vs performance tradeoffs.

## User Requirements

### Primary Goals
1. **User Control**: Allow users to select processing resolution via GUI
2. **Independence**: Processing resolution must be independent of display size
3. **Flexibility**: Support various quality presets and custom resolutions
4. **Transparency**: Show current processing resolution to user
5. **Coordinate Mapping**: Automatically handle ROI coordinate transformations

## Proposed Architecture

### New Handler: FrameResampleHandler

```python
# Location: froth_monitor/handlers/frame_resample_handler.py

class FrameResampleHandler(QObject):
    """Manages frame resampling for processing pipeline.
    
    Responsibilities:
        - Configure processing resolution independent of display
        - Transform frames to optimal processing resolution
        - Map coordinates between display and processing spaces
        - Provide user-friendly presets (High/Medium/Low/Custom)
        - Monitor and adjust based on performance
    
    Signals:
        resolution_changed: Emitted when processing resolution changes
        preset_changed: Emitted when user changes quality preset
    """
```

### User Interface Components

**New GUI Dialog**: `Processing Resolution Configuration`

```
┌─────────────────────────────────────────────────────┐
│  Processing Resolution Configuration               │
├─────────────────────────────────────────────────────┤
│                                                     │
│  Quality Preset:                                    │
│    ○ Ultra (100% - Full camera/video resolution)         │
│    ○ High (75% - 1920x1080 max)                    │
│    ● Medium (50% - 1280x720 max)  [Default]        │
│    ○ Low (25% - 640x480)                           │
│    ○ Custom                                         │
│                                                     │
│  [Custom Settings - enabled if Custom selected]    │
│    Scale: [====|====] 50%                          │
│    Max Width:  [1280    ] px                       │
│    Max Height: [720     ] px                       │
│                                                     │
│  Current Status:                                    │
│    Camera:     1920 x 1080                         │
│    Display:    800 x 600                           │
│    Processing: 960 x 540 (50%)                     │
│                                                     │
│  [Apply]  [Cancel]  [Reset to Default]             │
└─────────────────────────────────────────────────────┘
```

## Component Design

### 1. Resolution Presets

```python
class ResolutionPreset(Enum):
    """Predefined quality presets for processing resolution."""
    ULTRA = "ultra"      # 100% of camera, no max limit
    HIGH = "high"        # 75% of camera, max 1920x1080
    MEDIUM = "medium"    # 50% of camera, max 1280x720
    LOW = "low"          # 25% of camera, max 640x480
    CUSTOM = "custom"    # User-defined

PRESET_CONFIG = {
    ResolutionPreset.ULTRA: {"scale": 1.0, "max_width": None, "max_height": None},
    ResolutionPreset.HIGH: {"scale": 0.75, "max_width": 1920, "max_height": 1080},
    ResolutionPreset.MEDIUM: {"scale": 0.5, "max_width": 1280, "max_height": 720},
    ResolutionPreset.LOW: {"scale": 0.25, "max_width": 640, "max_height": 480},
}
```

### 2. Coordinate Mapping System

```python
class CoordinateMapper:
    """Maps coordinates between display and processing spaces."""
    
    def __init__(self, display_size, processing_size):
        self.display_width, self.display_height = display_size
        self.proc_width, self.proc_height = processing_size
        self.scale_x = self.proc_width / self.display_width
        self.scale_y = self.proc_height / self.display_height
    
    def display_to_processing(self, coord):
        """Convert ROI from display space to processing space."""
        x, y, w, h = coord
        return [
            int(x * self.scale_x),
            int(y * self.scale_y),
            int(w * self.scale_x),
            int(h * self.scale_y)
        ]
    
    def processing_to_display(self, coord):
        """Convert results from processing space to display space."""
        x, y, w, h = coord
        return [
            int(x / self.scale_x),
            int(y / self.scale_y),
            int(w / self.scale_x),
            int(h / self.scale_y)
        ]
    
    def scale_delta(self, delta_pixels):
        """Scale optical flow delta from processing to display space."""
        dx, dy = delta_pixels
        return (dx / self.scale_x, dy / self.scale_y)
```

### 3. FrameResampleHandler Core

```python
class FrameResampleHandler(QObject):
    # Signals
    resolution_changed = Signal(tuple)  # (proc_width, proc_height)
    preset_changed = Signal(str)        # Preset name
    
    def __init__(self, gui):
        self.gui = gui
        self.current_preset = ResolutionPreset.MEDIUM
        self.custom_scale = 0.5
        self.custom_max_width = 1280
        self.custom_max_height = 720
        
        # Current resolutions
        self.camera_resolution = (0, 0)
        self.display_resolution = (0, 0)
        self.processing_resolution = (0, 0)
        
        # Coordinate mapper
        self.coord_mapper = None
    
    def set_camera_resolution(self, width, height):
        """Called when video source changes."""
        self.camera_resolution = (width, height)
        self._recalculate_processing_resolution()
    
    def set_display_resolution(self, width, height):
        """Called when canvas size changes."""
        self.display_resolution = (width, height)
        self._update_coordinate_mapper()
    
    def calculate_processing_size(self, frame_width, frame_height):
        """Calculate the target processing resolution."""
        config = PRESET_CONFIG.get(self.current_preset)
        
        if self.current_preset == ResolutionPreset.CUSTOM:
            scale = self.custom_scale
            max_w = self.custom_max_width
            max_h = self.custom_max_height
        else:
            scale = config["scale"]
            max_w = config["max_width"]
            max_h = config["max_height"]
        
        # Apply scale
        proc_w = int(frame_width * scale)
        proc_h = int(frame_height * scale)
        
        # Apply maximum limits
        if max_w and proc_w > max_w:
            ratio = max_w / proc_w
            proc_w = max_w
            proc_h = int(proc_h * ratio)
        
        if max_h and proc_h > max_h:
            ratio = max_h / proc_h
            proc_h = max_h
            proc_w = int(proc_w * ratio)
        
        # Ensure even dimensions (for video codecs)
        proc_w = proc_w - (proc_w % 2)
        proc_h = proc_h - (proc_h % 2)
        
        return proc_w, proc_h
    
    def resample_frame(self, frame):
        """Resample frame to processing resolution."""
        if self.processing_resolution == (0, 0):
            # First frame - calculate resolution
            h, w = frame.shape[:2]
            proc_w, proc_h = self.calculate_processing_size(w, h)
            self.processing_resolution = (proc_w, proc_h)
            self._update_coordinate_mapper()
        
        proc_w, proc_h = self.processing_resolution
        return cv2.resize(frame, (proc_w, proc_h))
    
    def _update_coordinate_mapper(self):
        """Update coordinate mapper when resolutions change."""
        if self.display_resolution != (0, 0) and self.processing_resolution != (0, 0):
            self.coord_mapper = CoordinateMapper(
                self.display_resolution,
                self.processing_resolution
            )
    
    def open_configuration_dialog(self):
        """Show processing resolution configuration dialog."""
        # Create and show QDialog with preset options
        pass
```

## Integration Points

### 1. MainHandler Initialization

```python
# In MainHandler.initialize_level_two_handlers()
self.frame_resample_handler = FrameResampleHandler(self.gui)
self.frame_resample_handler.resolution_changed.connect(
    self._on_processing_resolution_changed
)
```

### 2. FrameProcessor Integration

```python
# In FrameProcessor.__init__()
def __init__(self, ..., frame_resample_handler):
    self.frame_resample_handler = frame_resample_handler

# In process_new_frame()
def process_new_frame(self, frame):
    # ... existing display code ...
    
    # Use FrameResampleHandler for processing
    processing_frame = self.frame_resample_handler.resample_frame(frame)
    self._process_frame_with_model(processing_frame)
```

### 3. ROI Coordinate Mapping

```python
# In ROIHandler.handle_roi_created()
def handle_roi_created(self, gui_rect):
    # Convert from display coordinates to processing coordinates
    proc_coord = self.frame_resample_handler.coord_mapper.display_to_processing(
        [gui_rect.x(), gui_rect.y(), gui_rect.width(), gui_rect.height()]
    )
    
    # Create ROI with both coordinate sets
    roi = ROI(gui_coordinate=gui_rect, processing_coordinate=proc_coord)
```

### 4. GUI Button Integration

```python
# Add to left panel in GUI
self.gui.processing_res_config_button = QPushButton("Processing Resolution")
self.gui.processing_res_config_button.clicked.connect(
    self.frame_resample_handler.open_configuration_dialog
)
```

## Implementation Phases

### Phase 1: Core Handler (Priority)
- [ ] Create `FrameResampleHandler` class
- [ ] Implement preset configurations
- [ ] Implement `calculate_processing_size()` method
- [ ] Implement `resample_frame()` method
- [ ] Add unit tests for resolution calculation

### Phase 2: Coordinate Mapping
- [ ] Create `CoordinateMapper` class
- [ ] Implement display ↔ processing coordinate conversion
- [ ] Update `ROI` class to store both coordinate sets
- [ ] Update `FrameModel` to use processing coordinates
- [ ] Test coordinate accuracy at various scales

### Phase 3: GUI Integration
- [ ] Design configuration dialog UI
- [ ] Implement dialog with preset radio buttons
- [ ] Add custom resolution sliders
- [ ] Show current resolution status
- [ ] Add "Apply" / "Cancel" logic

### Phase 4: Integration & Testing
- [ ] Integrate with `FrameProcessor`
- [ ] Update `ROIHandler` for coordinate mapping
- [ ] Test with different camera resolutions
- [ ] Test with different display sizes
- [ ] Performance benchmarking

### Phase 5: Persistence & Polish
- [ ] Save/load user preference
- [ ] Add tooltips and help text
- [ ] Display processing resolution in status bar
- [ ] Add performance indicators
- [ ] Documentation

## Future Considerations (Noted for Later)

- Adaptive resolution based on FPS
- Per-ROI resolution (high res for critical ROIs)
- GPU acceleration options
- Resolution interpolation methods (bilinear/bicubic/lanczos)
- Real-time resolution switching
- Multi-threaded resampling

## Files to Create

1. `froth_monitor/handlers/frame_resample_handler.py` - Main handler
2. `froth_monitor/utils/coordinate_mapper.py` - Coordinate transformation
3. `froth_monitor/handlers/processing_resolution_dialog.py` - GUI dialog

## Files to Modify

1. `frame_processor.py` - Use resample handler
2. `main_handler.py` - Initialize resample handler
3. `roi_handler.py` - Handle coordinate mapping
4. `fm_model.py` - Use processing coordinates
5. `roi.py` - Store dual coordinates

## Success Criteria

✅ User can select processing resolution independently of display
✅ ROI coordinates automatically mapped between spaces
✅ Performance impact < 5ms per frame
✅ No visual artifacts or coordinate misalignment
✅ User preferences persist across sessions
✅ Clear visual feedback of current resolution
