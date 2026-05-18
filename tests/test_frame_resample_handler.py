"""Unit tests for FrameResampleHandler."""

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
        assert handler.source_resolution == (0, 0)
    
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
    
    def test_calculate_processing_size_high_preset(self):
        """Test high preset calculates 75% scale with 1920x1080 max."""
        handler = FrameResampleHandler()
        handler.set_preset(ResolutionPreset.HIGH)
        
        proc_w, proc_h = handler.calculate_processing_size(1920, 1080)
        assert proc_w == 1440
        assert proc_h == 810
    
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
        # Account for even dimension adjustment
        assert proc_w == expected_w - (expected_w % 2)
        assert proc_h == expected_h - (expected_h % 2)
    
    def test_custom_parameters_clamping(self):
        """Test custom parameters are clamped to valid ranges."""
        handler = FrameResampleHandler()
        
        # Test scale clamping
        handler.set_custom_parameters(scale=1.5, max_width=1000, max_height=800)
        assert handler.custom_scale <= 1.0
        
        handler.set_custom_parameters(scale=0.05, max_width=1000, max_height=800)
        assert handler.custom_scale >= 0.1
        
        # Test minimum dimension clamping
        handler.set_custom_parameters(scale=0.5, max_width=100, max_height=100)
        assert handler.custom_max_width >= 320
        assert handler.custom_max_height >= 240
    
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
    
    def test_resample_frame_caching(self):
        """Test that processing resolution is cached after first frame."""
        handler = FrameResampleHandler()
        
        frame1 = np.zeros((1080, 1920, 3), dtype=np.uint8)
        _, proc_res1 = handler.resample_frame(frame1)
        
        # Second frame should use cached resolution
        frame2 = np.ones((1080, 1920, 3), dtype=np.uint8)
        _, proc_res2 = handler.resample_frame(frame2)
        
        assert proc_res1 == proc_res2
        assert handler.processing_resolution == (960, 540)
    
    def test_resample_frame_no_resize_needed(self):
        """Test that frames matching processing resolution are not resized."""
        handler = FrameResampleHandler()
        handler.set_preset(ResolutionPreset.ULTRA)
        
        # Create small frame
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
        resampled, proc_res = handler.resample_frame(frame)
        
        # Should not be resized (ultra preset, small source)
        assert resampled.shape == frame.shape
        assert proc_res == (640, 480)
    
    def test_preset_change_signal(self, qtbot):
        """Test that preset change emits signal."""
        handler = FrameResampleHandler()
        
        with qtbot.waitSignal(handler.preset_changed, timeout=1000) as blocker:
            handler.set_preset(ResolutionPreset.HIGH)
        
        assert blocker.args[0] == "high"
    
    def test_resolution_changed_signal(self, qtbot):
        """Test that resolution change emits signal."""
        handler = FrameResampleHandler()
        
        with qtbot.waitSignal(handler.resolution_changed, timeout=1000) as blocker:
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
    
    def test_get_resolution_info(self):
        """Test resolution info dictionary."""
        handler = FrameResampleHandler()
        
        # Before processing
        info = handler.get_resolution_info()
        assert info["preset"] == "medium"
        assert info["source_resolution"] == (0, 0)
        assert info["scale_percent"] == 0
        
        # After processing
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        handler.resample_frame(frame)
        
        info = handler.get_resolution_info()
        assert info["preset"] == "medium"
        assert info["source_resolution"] == (1920, 1080)
        assert info["processing_resolution"] == (960, 540)
        assert info["scale_percent"] == 50.0
    
    def test_source_resolution_change(self):
        """Test behavior when source resolution changes."""
        handler = FrameResampleHandler()
        
        # Process first video at 1080p
        frame1 = np.zeros((1080, 1920, 3), dtype=np.uint8)
        _, res1 = handler.resample_frame(frame1)
        assert res1 == (960, 540)
        
        # Switch to 720p video
        frame2 = np.zeros((720, 1280, 3), dtype=np.uint8)
        _, res2 = handler.resample_frame(frame2)
        assert res2 == (640, 360)
        
        # Source resolution should update
        assert handler.source_resolution == (1280, 720)
    
    def test_preset_config_completeness(self):
        """Test that all presets have required config keys."""
        for preset in [ResolutionPreset.ULTRA, ResolutionPreset.HIGH, 
                       ResolutionPreset.MEDIUM, ResolutionPreset.LOW]:
            config = PRESET_CONFIG[preset]
            assert "scale" in config
            assert "max_width" in config
            assert "max_height" in config
            assert "description" in config
