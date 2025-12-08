# Clean Ruler Calibration with CoordinateMapper

## Goal

Implement a clean, centralized approach for ruler calibration using CoordinateMapper in the CalibrationHandler, keeping coordinate transformation logic in one place.

---

## Current Problems

1. **OverlayWidget does too much** - Has CoordinateMapper logic, resolution tracking, and scaling calculations
2. **FrameProcessor polluted** - Has overlay widget resolution management code
3. **Scattered logic** - Coordinate transformation happens in paintEvent and mouseReleaseEvent
4. **Tight coupling** - OverlayWidget knows about resolutions it shouldn't care about

---

## Proposed Clean Solution

### Principle: **Separation of Concerns**

- **OverlayWidget**: Only draws and emits raw overlay measurements (no transformations)
- **CalibrationHandler**: Owns all calibration logic including coordinate transformations
- **CoordinateMapper**: Used exclusively in CalibrationHandler

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    User draws ruler                         │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ↓
┌─────────────────────────────────────────────────────────────┐
│  OverlayWidget                                               │
│  • Draws ruler line                                          │
│  • Calculates distance in OVERLAY space                      │
│  • Displays "XXX px (overlay)" during drawing                │
│  • Emits ruler_measured.emit(overlay_distance)               │
└────────────────────┬────────────────────────────────────────┘
                     │ emit(overlay_distance)
                     ↓
┌─────────────────────────────────────────────────────────────┐
│  CalibrationHandler.handle_ruler_measurement()               │
│  • Receives overlay_distance (e.g., 450px)                   │
│  • Gets resolutions from FrameResampleHandler:               │
│    - source_res = (1280, 720)                                │
│    - Get overlay_res from FrameDisplayManager                │
│  • Creates CoordinateMapper(overlay_res, source_res)         │
│  • Transforms: source_px = mapper.scale_distance(overlay_px) │
│  • Displays dialog: "Measured 640px in source video"         │
│  • Calculates px2mm from SOURCE pixels                       │
└─────────────────────────────────────────────────────────────┘
```

---

## Implementation Details

### 1. OverlayWidget Simplification

**Remove**:
- ❌ `display_resolution` field
- ❌ `processing_resolution` field  
- ❌ `set_resolutions()` method
- ❌ All CoordinateMapper imports and usage
- ❌ Source distance calculations

**Keep**:
- ✅ `video_width` / `video_height` (for local drawing only)
- ✅ `ruler_distance` (overlay space measurement)
- ✅ Simple display: `f"{self.ruler_distance:.1f} px (overlay)"`
- ✅ Emit raw overlay distance: `ruler_measured.emit(self.ruler_distance)`

**New paintEvent for ruler**:
```python
if self.ruler_distance > 0:
    # Simple display - no transformation
    text = f"{self.ruler_distance:.1f} px"
    painter.drawText(text_x, text_y, text)
```

---

### 2. CalibrationHandler Enhancement

**Add new field**:
```python
def __init__(self, gui, frame_model, overlay_widget, frame_resample_handler):
    # ...existing fields...
    self.frame_resample_handler = frame_resample_handler  # NEW
```

**Update `handle_ruler_measurement()`**:
```python
def handle_ruler_measurement(self, overlay_px: float):
    """Handle ruler measurement with coordinate transformation.
    
    Args:
        overlay_px: Measured distance in overlay space (pixels)
    """
    from froth_monitor.utils.coordinate_mapper import CoordinateMapper
    
    # Get resolutions
    source_res = self.frame_resample_handler.source_resolution
    
    # Get overlay dimensions from FrameDisplayManager
    # Option A: Via MainHandler reference
    overlay_res = self.main_handler.frame_processor.display_manager.get_video_dimensions()
    
    # Option B: Store overlay_res in CalibrationHandler (updated each frame)
    # overlay_res = self.overlay_resolution
    
    # Transform overlay pixels → source pixels
    if source_res != (0, 0) and overlay_res != (0, 0):
        mapper = CoordinateMapper(overlay_res, source_res)
        
        # For distance, use average scale factor
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
        source_px = overlay_px
        logger.warning("Resolutions not initialized, using overlay pixels directly")
    
    # Calculate px2mm from SOURCE pixels
    distance_mm = self.gui.px2mm_spinbox.value()
    px_ratio = float(source_px / distance_mm)
    
    self.frame_model.get_px_to_mm(px_ratio)
    self.gui.px2mm_result_textbox.setText(f"{self.frame_model.px2mm:.1f}")
    
    # Display the result
    QMessageBox.information(
        self.gui,
        "Ruler Calibration",
        f"Measured {source_px:.1f}px in source video\n"
        f"Px to mm ratio: {self.frame_model.px2mm:.1f} per mm"
    )
    
    self.gui.statusBar().showMessage(
        f"Calibrated: {source_px:.1f}px = {distance_mm}mm "
        f"(px2mm: {self.frame_model.px2mm:.1f})"
    )
```

---

### 3. MainHandler Integration

**Update CalibrationHandler initialization**:
```python
# In MainHandler.initialize_level_three_handlers()
self.calibration_handler = CalibrationHandler(
    self.gui, 
    self.frame_model, 
    self.overlay_widget,
    self.frame_resample_handler  # Pass resample handler
)
```

---

### 4. Getting Overlay Dimensions

**Option A: Direct access via MainHandler** (Cleaner)
```python
# In CalibrationHandler.handle_ruler_measurement()
overlay_res = (
    self.main_handler.frame_processor.display_manager.video_rect.width(),
    self.main_handler.frame_processor.display_manager.video_rect.height()
)
```

**Option B: Store in CalibrationHandler** (More decoupled)
```python
# Add to CalibrationHandler
def set_overlay_resolution(self, width: int, height: int):
    """Called by FrameDisplayManager when overlay size changes."""
    self.overlay_resolution = (width, height)

# In FrameDisplayManager._update_overlay_position()
if self.calibration_handler:
    self.calibration_handler.set_overlay_resolution(
        self.video_rect.width(), 
        self.video_rect.height()
    )
```

**Recommendation**: Use Option A for now (simpler, no new dependencies)

---

## Implementation Steps

### Phase 1: Simplify OverlayWidget
- [ ] Remove `display_resolution` and `processing_resolution` fields
- [ ] Remove `set_resolutions()` method
- [ ] Remove CoordinateMapper imports and usage from paintEvent
- [ ] Remove CoordinateMapper usage from mouseReleaseEvent
- [ ] Update ruler display to show simple overlay pixels
- [ ] Emit raw overlay distance only

### Phase 2: Enhance CalibrationHandler
- [ ] Add `frame_resample_handler` parameter to `__init__`
- [ ] Add `main_handler` reference (for overlay dimensions)
- [ ] Update `handle_ruler_measurement()` to use CoordinateMapper
- [ ] Add proper logging and user feedback
- [ ] Calculate px2mm from source pixels

### Phase 3: Update MainHandler
- [ ] Pass `frame_resample_handler` to CalibrationHandler
- [ ] Pass `self` (MainHandler) reference to CalibrationHandler

### Phase 4: Testing
- [ ] Test ruler drawing shows overlay pixels during draw
- [ ] Test measurement dialog shows source pixels
- [ ] Verify px2mm calculated from source resolution
- [ ] Test with different window sizes (overlay changes, source doesn't)
- [ ] Test with different resolution presets

---

## Data Flow Example

### Scenario: 1280x720 video, displayed at 800x450, ruler drawn

```
1. User draws 400px ruler on overlay
   → OverlayWidget: ruler_distance = 400.0
   → Display during draw: "400.0 px"
   → Emit: ruler_measured.emit(400.0)

2. CalibrationHandler.handle_ruler_measurement(400.0)
   → source_res = (1280, 720)
   → overlay_res = (800, 450)
   → mapper = CoordinateMapper((800, 450), (1280, 720))
   → scale = 1.6
   → source_px = 400 * 1.6 = 640
   
3. User enters: "This is 20mm"
   → px2mm = 640 / 20 = 32.0 pixels per mm
   
4. Dialog shows:
   "Measured 640.0px in source video
    Px to mm ratio: 32.0 per mm"
```

**Window resized to 1000x562**:
```
1. User draws same physical length ruler (500px in new overlay size)
   → Emit: ruler_measured.emit(500.0)

2. CalibrationHandler
   → source_res = (1280, 720) (unchanged!)
   → overlay_res = (1000, 562) (new!)
   → mapper = CoordinateMapper((1000, 562), (1280, 720))
   → scale = 1.28
   → source_px = 500 * 1.28 = 640 ✅ Same result!
```

---

## Benefits

✅ **Single Responsibility**: OverlayWidget only handles drawing, CalibrationHandler handles calibration
✅ **Clean Separation**: Coordinate transformation isolated in CalibrationHandler
✅ **No Pollution**: FrameProcessor doesn't know about overlay resolutions
✅ **Testable**: CalibrationHandler logic can be unit tested
✅ **Maintainable**: All calibration logic in one place
✅ **Flexible**: Easy to add more calibration features

---

## Files to Modify

| File | Changes | Complexity |
|------|---------|------------|
| `overlay_widget.py` | Remove resolution tracking, simplify ruler display | Medium |
| `calibration_handler.py` | Add CoordinateMapper logic, update handle_ruler_measurement | High |
| `main_handler.py` | Pass additional parameters to CalibrationHandler | Low |
| `frame_processor.py` | No changes needed! ✅ | None |

**Total**: 3 files, ~50 LOC changes

---

## Success Criteria

- [ ] OverlayWidget has no CoordinateMapper or resolution tracking
- [ ] Ruler shows overlay pixels during drawing
- [ ] Measurement dialog shows source pixels
- [ ] px2mm calculated from source resolution
- [ ] Works correctly across window resizes
- [ ] All calibration logic in CalibrationHandler
- [ ] No changes to FrameProcessor
