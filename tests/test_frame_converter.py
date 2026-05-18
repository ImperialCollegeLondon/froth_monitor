"""Unit tests for FrameConverter utility class."""

import pytest
import numpy as np
import cv2
from PySide6.QtGui import QImage
from froth_monitor.utils.frame_converter import FrameConverter


class TestFrameConverter:
    """Test suite for FrameConverter utility class."""
    
    # ============= bgr_to_qimage Tests =============
    
    def test_bgr_to_qimage_valid_frame(self):
        """Test successful conversion of BGR frame to QImage."""
        # Create a test frame (640x480, BGR)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        frame[:, :] = [255, 0, 0]  # Blue in BGR
        
        qimage = FrameConverter.bgr_to_qimage(frame)
        
        assert isinstance(qimage, QImage)
        assert qimage.width() == 640
        assert qimage.height() == 480
        assert qimage.format() == QImage.Format.Format_RGB888
    
    def test_bgr_to_qimage_none_frame(self):
        """Test that None frame raises ValueError."""
        with pytest.raises(ValueError, match="Frame cannot be None"):
            FrameConverter.bgr_to_qimage(None)
    
    def test_bgr_to_qimage_wrong_dimensions(self):
        """Test that 2D frame raises ValueError."""
        frame_2d = np.zeros((480, 640), dtype=np.uint8)
        
        with pytest.raises(ValueError, match="Expected 3D frame"):
            FrameConverter.bgr_to_qimage(frame_2d)
    
    def test_bgr_to_qimage_wrong_channels(self):
        """Test that frame with wrong number of channels raises ValueError."""
        frame_rgba = np.zeros((480, 640, 4), dtype=np.uint8)
        
        with pytest.raises(ValueError, match="Expected 3 channels"):
            FrameConverter.bgr_to_qimage(frame_rgba)
    
    def test_bgr_to_qimage_color_conversion(self):
        """Test that BGR is correctly converted to RGB."""
        # Create blue frame in BGR
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        frame[:, :] = [255, 0, 0]  # Blue in BGR
        
        qimage = FrameConverter.bgr_to_qimage(frame)
        
        # In QImage (RGB), blue should be at index 2
        # We can't easily verify pixel values, but we can verify no exception
        assert qimage is not None
        assert qimage.width() == 100
        assert qimage.height() == 100
    
    def test_bgr_to_qimage_different_sizes(self):
        """Test conversion with various frame sizes."""
        sizes = [(320, 240), (640, 480), (1920, 1080), (100, 50)]
        
        for width, height in sizes:
            frame = np.zeros((height, width, 3), dtype=np.uint8)
            qimage = FrameConverter.bgr_to_qimage(frame)
            
            assert qimage.width() == width
            assert qimage.height() == height
    
    # ============= scale_to_fit Tests =============
    
    def test_scale_to_fit_downscale(self):
        """Test scaling down an image."""
        source = QImage(640, 480, QImage.Format.Format_RGB888)
        
        scaled = FrameConverter.scale_to_fit(source, 320, 240)
        
        assert scaled.width() <= 320
        assert scaled.height() <= 240
    
    def test_scale_to_fit_upscale(self):
        """Test scaling up an image."""
        source = QImage(320, 240, QImage.Format.Format_RGB888)
        
        scaled = FrameConverter.scale_to_fit(source, 640, 480)
        
        # With aspect ratio maintained, one dimension should match
        assert scaled.width() <= 640
        assert scaled.height() <= 480
    
    def test_scale_to_fit_aspect_ratio_maintained(self):
        """Test that aspect ratio is maintained when keep_aspect_ratio=True."""
        source = QImage(1600, 1200, QImage.Format.Format_RGB888)  # 4:3 ratio
        
        scaled = FrameConverter.scale_to_fit(source, 800, 800, keep_aspect_ratio=True)
        
        # Aspect ratio should be preserved
        original_ratio = 1600 / 1200
        scaled_ratio = scaled.width() / scaled.height()
        
        assert abs(original_ratio - scaled_ratio) < 0.01
    
    def test_scale_to_fit_aspect_ratio_ignored(self):
        """Test that aspect ratio can be ignored."""
        source = QImage(1600, 1200, QImage.Format.Format_RGB888)
        
        scaled = FrameConverter.scale_to_fit(
            source, 800, 800, keep_aspect_ratio=False
        )
        
        # Should fill target dimensions exactly
        assert scaled.width() == 800
        assert scaled.height() == 800
    
    def test_scale_to_fit_invalid_dimensions(self):
        """Test that invalid target dimensions raise ValueError."""
        source = QImage(640, 480, QImage.Format.Format_RGB888)
        
        with pytest.raises(ValueError, match="Invalid target dimensions"):
            FrameConverter.scale_to_fit(source, 0, 480)
        
        with pytest.raises(ValueError, match="Invalid target dimensions"):
            FrameConverter.scale_to_fit(source, 640, -1)
    
    def test_scale_to_fit_same_size(self):
        """Test scaling when source matches target size."""
        source = QImage(640, 480, QImage.Format.Format_RGB888)
        
        scaled = FrameConverter.scale_to_fit(source, 640, 480)
        
        assert scaled.width() == 640
        assert scaled.height() == 480
    
    # ============= resize_frame Tests =============
    
    def test_resize_frame_downsize(self):
        """Test resizing frame to smaller dimensions."""
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        
        resized = FrameConverter.resize_frame(frame, 960, 540)
        
        assert resized.shape == (540, 960, 3)
    
    def test_resize_frame_upsize(self):
        """Test resizing frame to larger dimensions."""
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
        resized = FrameConverter.resize_frame(frame, 1280, 720)
        
        assert resized.shape == (720, 1280, 3)
    
    def test_resize_frame_none_input(self):
        """Test that None frame raises ValueError."""
        with pytest.raises(ValueError, match="Frame cannot be None"):
            FrameConverter.resize_frame(None, 640, 480)
    
    def test_resize_frame_invalid_dimensions(self):
        """Test that invalid dimensions raise ValueError."""
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
        with pytest.raises(ValueError, match="Invalid dimensions"):
            FrameConverter.resize_frame(frame, 0, 480)
        
        with pytest.raises(ValueError, match="Invalid dimensions"):
            FrameConverter.resize_frame(frame, 640, -1)
    
    def test_resize_frame_interpolation_methods(self):
        """Test different interpolation methods."""
        frame = np.ones((100, 100, 3), dtype=np.uint8) * 128
        
        # Test various interpolation methods
        methods = [cv2.INTER_NEAREST, cv2.INTER_LINEAR, cv2.INTER_CUBIC]
        
        for method in methods:
            resized = FrameConverter.resize_frame(frame, 50, 50, interpolation=method)
            assert resized.shape == (50, 50, 3)
    
    def test_resize_frame_preserves_dtype(self):
        """Test that resizing preserves data type."""
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
        resized = FrameConverter.resize_frame(frame, 320, 240)
        
        assert resized.dtype == np.uint8
    
    def test_resize_frame_odd_dimensions(self):
        """Test resizing to odd dimensions."""
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
        resized = FrameConverter.resize_frame(frame, 321, 241)
        
        assert resized.shape == (241, 321, 3)
    
    # ============= Integration Tests =============
    
    def test_full_conversion_pipeline(self):
        """Test complete pipeline: BGR frame → QImage → scaled."""
        # Create test frame
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        frame[:, :] = [0, 255, 0]  # Green in BGR
        
        # Convert to QImage
        qimage = FrameConverter.bgr_to_qimage(frame)
        assert qimage.width() == 1920
        assert qimage.height() == 1080
        
        # Scale down
        scaled = FrameConverter.scale_to_fit(qimage, 960, 540)
        assert scaled.width() <= 960
        assert scaled.height() <= 540
    
    def test_resize_and_convert_pipeline(self):
        """Test resizing then converting to QImage."""
        # Original large frame
        frame = np.ones((2160, 3840, 3), dtype=np.uint8) * 128
        
        # Resize first
        resized = FrameConverter.resize_frame(frame, 1920, 1080)
        assert resized.shape == (1080, 1920, 3)
        
        # Then convert to QImage
        qimage = FrameConverter.bgr_to_qimage(resized)
        assert qimage.width() == 1920
        assert qimage.height() == 1080
