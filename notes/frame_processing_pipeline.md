# Froth Monitor Frame Processing Pipeline

## Complete Frame Flow 🎬

```
┌─────────────────────────────────────────────────────────────────────┐
│                    FRAME CAPTURE & EMISSION                         │
└─────────────────────────────────────────────────────────────────────┘
Video Source (Camera/File/Network)
         ↓
CameraThread._capture_loop()                    [Background Thread]
    ├─ while running and video_capture.isOpened():
    ├─ if paused: sleep(0.1) and skip
    ├─ ret, frame = video_capture.read()
    ├─ Rate control (video files: respect FPS, camera: 0.001s sleep)
    └─ if self.if_release:                      [Flow Control Gate]
           self.frame_available.emit(frame)     [Signal Emission]

┌─────────────────────────────────────────────────────────────────────┐
│                   FRAME PROCESSING PIPELINE                         │
└─────────────────────────────────────────────────────────────────────┘
Signal: frame_available(frame)                  [Qt Event Loop]
         ↓ [Connected in MainHandler.initialize_level_three_handlers()]
FrameProcessor.process_new_frame(frame)         [GUI Thread]
    │
    ├─ Check: if not self.playing: return       [Playback State Gate]
    │
    ├─ [1] Format Conversion
    │     qt_image = _convert_frame_to_qimage(frame)
    │         └─ cv2.cvtColor(frame, BGR2RGB)
    │         └─ Create QImage from RGB data
    │
    ├─ [2] GUI Scaling
    │     scaled_image = _scale_image_to_canvas(qt_image)
    │         └─ qt_image.scaled(canvas_width, canvas_height, KeepAspectRatio)
    │
    ├─ [3] Processing Resize
    │     resized_frame = _create_resized_frame(frame, width, height)
    │         └─ cv2.resize(frame, (width, height))
    │
    ├─ [4] Flow Control (CRITICAL)
    │     self.video_thread.if_release = False   [Block next frame]
    │
    ├─ [5] Model Processing (Thread-Safe)
    │     _process_frame_with_model(resized_frame)
    │         │
    │         ├─ FrameModel.process_frame(resized_frame)
    │         │     │
    │         │     └─ with self._processing_lock:     [THREAD SAFETY]
    │         │           ├─ Iterate roi_list
    │         │           ├─ Crop frame per ROI
    │         │           ├─ roi.process_frame(cropped)
    │         │           │     └─ Optical flow calculation
    │         │           │     └─ Velocity computation
    │         │           │     └─ Update roi.delta_pixels
    │         │           └─ Return (frame_count, roi_list, update_flags)
    │         │
    │         ├─ ROIHandler.display_roi(roi_list)
    │         │     └─ OverlayWidget.display_roi(roi_list)
    │         │           └─ self.roi_list = roi_list
    │         │           └─ self.update()           [Trigger repaint]
    │         │
    │         └─ if update_velo_plot:
    │               ├─ DataHandler.update_velocity_plot()
    │               │     └─ with frame_model._processing_lock: [THREAD SAFETY]
    │               │           └─ Read roi.velo_only_history_for_display
    │               │           └─ Update PyQtGraph plots
    │               └─ DataHandler.update_arec_data()
    │
    ├─ [6] Unlock Flow Control
    │     self.video_thread.if_release = True    [Allow next frame]
    │
    ├─ [7] GUI Display
    │     pixmap = _display_frame_on_canvas(scaled_image)
    │         └─ gui.video_canvas_label.setPixmap(pixmap)
    │
    ├─ [8] Overlay Sync
    │     _update_overlay_position(pixmap)
    │         └─ overlay_widget.setGeometry(video_rect)
    │
    ├─ [9] Optional Recording
    │     if recording_active and video_recorder.is_active():
    │         video_recording_worker.add_frame(frame)
    │
    └─ [10] Status Update
          _update_status_bar()
              └─ gui.statusBar().showMessage(f"Frame: {number}")

┌─────────────────────────────────────────────────────────────────────┐
│                    OVERLAY WIDGET INTERACTION                       │
└─────────────────────────────────────────────────────────────────────┘

OverlayWidget sits ON TOP of video_canvas_label (transparent layer)

[User Interaction Events]
│
├─ ROI Creation Mode
│     User: Clicks "Add ROI" button
│         ↓
│     GUI: add_roi_button.clicked → ROIHandler.add_roi()
│         ↓
│     Overlay: overlay_widget.start_roi_drawing()
│         ├─ self.drawing_roi = True
│         └─ Mouse events enabled:
│               mousePressEvent() → capture start_point
│               mouseMoveEvent() → update end_point (live preview)
│               mouseReleaseEvent() → finalize ROI
│                   ↓
│                   roi_created.emit(QRect)
│                       ↓
│                   ROIHandler.handle_roi_created(rect)
│                       └─ Create ROI object
│                       └─ Add to frame_model.roi_list
│
├─ Calibration Mode
│     User: Clicks "Calibration" button
│         ↓
│     CalibrationHandler.start_ruler_calibration()
│         ↓
│     Overlay: overlay_widget.ruler_calibration()
│         ├─ self.drawing_ruler = True
│         └─ Mouse events:
│               Draw line, calculate distance
│               ruler_measured.emit(distance)
│                   ↓
│                   CalibrationHandler.handle_ruler_measurement()
│
├─ Arrow Drawing Mode (Gravity Direction)
│     User: Clicks "Add Arrow" button
│         ↓
│     CalibrationHandler.start_arrow_drawing()
│         ↓
│     Overlay: overlay_widget.start_arrow_drawing()
│         └─ Mouse events:
│               Draw arrow, calculate angle
│               arrow_drawn.emit(start, end, angle)
│                   ↓
│                   CalibrationHandler.handle_arrow_drawing()
│
└─ Display Mode (Default)
      OverlayWidget.paintEvent() called on every update()
          │
          ├─ if drawing_roi: Draw green rectangle preview
          ├─ if drawing_ruler: Draw red line with distance
          ├─ if drawing_arrow: Draw orange arrow with angle
          └─ else: Draw all ROIs from roi_list
                ├─ For each ROI in roi_list:
                │     ├─ Draw ROI rectangle (light blue)
                │     ├─ Draw ROI number (top-right)
                │     └─ Draw moving cross based on roi.delta_pixels
                │           └─ Cross position updated by optical flow
                │           └─ Shows direction of froth movement

┌─────────────────────────────────────────────────────────────────────┐
│                      FLOW CONTROL MECHANISM                         │
└─────────────────────────────────────────────────────────────────────┘

Purpose: Prevent frame buffer overflow when processing is slower than capture

CameraThread Side:
    while running:
        ret, frame = capture.read()
        if self.if_release:              # Check flag
            frame_available.emit(frame)  # Only emit if allowed
        else:
            # Frame is dropped, wait for processing to complete

FrameProcessor Side:
    def process_new_frame(frame):
        self.video_thread.if_release = False  # Block new frames
        _process_frame_with_model()           # Process current frame
        self.video_thread.if_release = True   # Allow next frame

Effect: Creates a natural backpressure system
    - Camera captures at full rate but only emits when processor is ready
    - Prevents Qt event queue overflow
    - Ensures sequential frame processing
    - Dropped frames = processing too slow

┌─────────────────────────────────────────────────────────────────────┐
│                      THREAD SAFETY ZONES                            │
└─────────────────────────────────────────────────────────────────────┘

Critical Race Condition Protection:

Zone 1: ROI List & Algorithm Parameters
    Thread A (Video Processing):
        FrameProcessor → FrameModel.process_frame()
            with self._processing_lock:
                for roi in roi_list:
                    roi.process_frame()  # Uses algorithm params
    
    Thread B (GUI - Algorithm Change):
        AlgorithmHandler → FrameModel.confirm_algorithm_n_params()
            with self._processing_lock:
                for roi in roi_list:
                    roi.get_algorithm_n_params()  # Updates params

Zone 2: ROI History Data
    Thread A (Video Processing):
        FrameModel.process_frame()
            with self._processing_lock:
                roi.velo_only_history_for_display.append()
    
    Thread B (GUI - Plot Update):
        DataHandler.update_velocity_plot()
            with frame_model._processing_lock:
                for roi in roi_list:
                    data = roi.velo_only_history_for_display

┌─────────────────────────────────────────────────────────────────────┐
│                    PLAYBACK STATE CONTROL                           │
└─────────────────────────────────────────────────────────────────────┘

VideoHandler.playing (Controlled by signal)
         ↓
    playback_state_changed.emit(bool)
         ↓
    FrameProcessor.set_playback_state(playing)
         ├─ self.playing = playing
         └─ process_new_frame() checks this flag first

Playback States:
    playing=True  → Frames are processed and displayed
    playing=False → process_new_frame() returns early, frames ignored

Pause/Resume Flow:
    User clicks play/pause button
         ↓
    VideoHandler._pause_play()
         ├─ if playing:
         │     ├─ video_thread.pause()
         │     ├─ self.playing = False
         │     └─ playback_state_changed.emit(False)
         └─ else:
               ├─ video_thread.resume()
               ├─ self.playing = True
               └─ playback_state_changed.emit(True)

┌─────────────────────────────────────────────────────────────────────┐
│                      KEY INSIGHTS                                   │
└─────────────────────────────────────────────────────────────────────┘

1. **Event-Driven Architecture**: Uses Qt signals for loose coupling
2. **Multi-Layer Processing**: Separate conversions for GUI vs processing
3. **Flow Control**: `if_release` flag prevents buffer overflow
4. **Thread Safety**: Shared lock protects concurrent ROI access
5. **Overlay Independence**: Transparent widget on top, not embedded
6. **Backpressure Handling**: Camera drops frames when processing slow
7. **Signal Routing**: MainHandler connects all components
8. **State Synchronization**: Playback state broadcast via signals

## Performance Characteristics 🚀

- **Frame Capture**: 30 FPS (video files) or camera native rate
- **Processing Time**: ~10-30ms per frame (depends on ROI count)
- **GUI Update**: Immediate via Qt event loop
- **Dropped Frames**: Happens when processing > capture rate
- **Thread Safety Overhead**: <1ms (lock contention minimal)

## Common Bottlenecks ⚠️

1. **Optical Flow Calculation**: Most CPU-intensive (in roi.process_frame)
2. **Multiple ROIs**: Linear scaling with ROI count
3. **Large Frames**: More data to convert/resize
4. **Plot Updates**: PyQtGraph rendering can be slow
5. **Recording**: If active, adds queue overhead
