"""Unit tests for CoordinateMapper."""

import pytest
from froth_monitor.utils.coordinate_mapper import CoordinateMapper


class TestCoordinateMapper:
    """Test suite for CoordinateMapper coordinate transformations."""
    
    # ============= Initialization Tests =============
    
    def test_init_valid_resolutions(self):
        """Test initialization with valid resolutions."""
        mapper = CoordinateMapper((640, 480), (320, 240))
        
        assert mapper.display_width == 640
        assert mapper.display_height == 480
        assert mapper.proc_width == 320
        assert mapper.proc_height == 240
        assert mapper.scale_x == 0.5
        assert mapper.scale_y == 0.5
    
    def test_init_invalid_display_resolution(self):
        """Test that invalid display resolution raises ValueError."""
        with pytest.raises(ValueError, match="Invalid display resolution"):
            CoordinateMapper((0, 480), (320, 240))
        
        with pytest.raises(ValueError, match="Invalid display resolution"):
            CoordinateMapper((640, -1), (320, 240))
    
    def test_init_invalid_processing_resolution(self):
        """Test that invalid processing resolution raises ValueError."""
        with pytest.raises(ValueError, match="Invalid processing resolution"):
            CoordinateMapper((640, 480), (0, 240))
        
        with pytest.raises(ValueError, match="Invalid processing resolution"):
            CoordinateMapper((640, 480), (320, -1))
    
    # ============= Display to Processing Tests =============
    
    def test_display_to_processing_50_percent(self):
        """Test transformation with 50% scaling."""
        mapper = CoordinateMapper((640, 480), (320, 240))
        
        result = mapper.display_to_processing(100, 50, 200, 150)
        
        assert result == (50, 25, 100, 75)
    
    def test_display_to_processing_75_percent(self):
        """Test transformation with 75% scaling."""
        mapper = CoordinateMapper((1920, 1080), (1440, 810))
        
        result = mapper.display_to_processing(400, 300, 800, 600)
        
        assert result == (300, 225, 600, 450)
    
    def test_display_to_processing_25_percent(self):
        """Test transformation with 25% scaling."""
        mapper = CoordinateMapper((1280, 720), (320, 180))
        
        result = mapper.display_to_processing(800, 400, 400, 200)
        
        assert result == (200, 100, 100, 50)
    
    def test_display_to_processing_identity(self):
        """Test transformation with no scaling (1:1)."""
        mapper = CoordinateMapper((640, 480), (640, 480))
        
        result = mapper.display_to_processing(100, 50, 200, 150)
        
        assert result == (100, 50, 200, 150)
    
    def test_display_to_processing_minimum_size(self):
        """Test that minimum 1 pixel dimension is enforced."""
        mapper = CoordinateMapper((1920, 1080), (320, 180))
        
        # Very small ROI should still have minimum 1 pixel
        result = mapper.display_to_processing(0, 0, 3, 3)
        
        assert result[2] >= 1  # width >= 1
        assert result[3] >= 1  # height >= 1
    
    def test_display_to_processing_zero_origin(self):
        """Test transformation with ROI at origin."""
        mapper = CoordinateMapper((640, 480), (320, 240))
        
        result = mapper.display_to_processing(0, 0, 200, 150)
        
        assert result == (0, 0, 100, 75)
    
    # ============= Processing to Display Tests =============
    
    def test_processing_to_display_50_percent(self):
        """Test reverse transformation with 50% scaling."""
        mapper = CoordinateMapper((640, 480), (320, 240))
        
        result = mapper.processing_to_display(50, 25, 100, 75)
        
        assert result == (100, 50, 200, 150)
    
    def test_processing_to_display_75_percent(self):
        """Test reverse transformation with 75% scaling."""
        mapper = CoordinateMapper((1920, 1080), (1440, 810))
        
        result = mapper.processing_to_display(300, 225, 600, 450)
        
        assert result == (400, 300, 800, 600)
    
    def test_processing_to_display_identity(self):
        """Test reverse transformation with no scaling."""
        mapper = CoordinateMapper((640, 480), (640, 480))
        
        result = mapper.processing_to_display(100, 50, 200, 150)
        
        assert result == (100, 50, 200, 150)
    
    def test_round_trip_transformation(self):
        """Test that display→processing→display is consistent."""
        mapper = CoordinateMapper((1920, 1080), (960, 540))
        
        # Start with display coordinates
        original = (400, 300, 800, 600)
        
        # Transform to processing
        proc_coords = mapper.display_to_processing(*original)
        
        # Transform back to display
        result = mapper.processing_to_display(*proc_coords)
        
        # Should be close to original (may have rounding differences)
        assert abs(result[0] - original[0]) <= 1
        assert abs(result[1] - original[1]) <= 1
        assert abs(result[2] - original[2]) <= 1
        assert abs(result[3] - original[3]) <= 1
    
    # ============= Delta Scaling Tests =============
    
    def test_scale_delta_to_display(self):
        """Test scaling delta from processing to display."""
        mapper = CoordinateMapper((640, 480), (320, 240))
        
        # Motion of 10 pixels in processing space
        result = mapper.scale_delta(10.0, 5.0, to_display=True)
        
        # Should be 20 pixels in display space (2x scale)
        assert result == (20.0, 10.0)
    
    def test_scale_delta_to_processing(self):
        """Test scaling delta from display to processing."""
        mapper = CoordinateMapper((640, 480), (320, 240))
        
        # Motion of 20 pixels in display space
        result = mapper.scale_delta(20.0, 10.0, to_display=False)
        
        # Should be 10 pixels in processing space (0.5x scale)
        assert result == (10.0, 5.0)
    
    def test_scale_delta_identity(self):
        """Test delta scaling with no scaling."""
        mapper = CoordinateMapper((640, 480), (640, 480))
        
        result_to_display = mapper.scale_delta(10.0, 5.0, to_display=True)
        result_to_proc = mapper.scale_delta(10.0, 5.0, to_display=False)
        
        assert result_to_display == (10.0, 5.0)
        assert result_to_proc == (10.0, 5.0)
    
    def test_scale_delta_negative_values(self):
        """Test delta scaling with negative motion vectors."""
        mapper = CoordinateMapper((1920, 1080), (960, 540))
        
        result = mapper.scale_delta(-15.0, -10.0, to_display=True)
        
        assert result == (-30.0, -20.0)
    
    def test_scale_delta_zero_values(self):
        """Test delta scaling with zero motion."""
        mapper = CoordinateMapper((640, 480), (320, 240))
        
        result = mapper.scale_delta(0.0, 0.0, to_display=True)
        
        assert result == (0.0, 0.0)
    
    # ============= Utility Methods Tests =============
    
    def test_get_scale_factors(self):
        """Test getting scale factors."""
        mapper = CoordinateMapper((1920, 1080), (960, 540))
        
        scale_x, scale_y = mapper.get_scale_factors()
        
        assert scale_x == 0.5
        assert scale_y == 0.5
    
    def test_is_identity_true(self):
        """Test identity check with same resolutions."""
        mapper = CoordinateMapper((640, 480), (640, 480))
        
        assert mapper.is_identity() is True
    
    def test_is_identity_false(self):
        """Test identity check with different resolutions."""
        mapper = CoordinateMapper((640, 480), (320, 240))
        
        assert mapper.is_identity() is False
    
    # ============= Edge Cases =============
    
    def test_non_uniform_scaling(self):
        """Test with different X and Y scale factors."""
        # Display: 1600x1200 (4:3)
        # Processing: 640x360 (16:9)
        mapper = CoordinateMapper((1600, 1200), (640, 360))
        
        result = mapper.display_to_processing(400, 300, 800, 600)
        
        # X scale: 640/1600 = 0.4
        # Y scale: 360/1200 = 0.3
        assert result == (160, 90, 320, 180)
    
    def test_upscaling(self):
        """Test transformation when processing resolution > display."""
        # Unusual but possible case
        mapper = CoordinateMapper((320, 240), (640, 480))
        
        result = mapper.display_to_processing(50, 25, 100, 75)
        
        # Should scale up by 2x
        assert result == (100, 50, 200, 150)
    
    def test_large_coordinates(self):
        """Test with large coordinate values (4K)."""
        mapper = CoordinateMapper((3840, 2160), (1920, 1080))
        
        result = mapper.display_to_processing(1920, 1080, 1920, 1080)
        
        assert result == (960, 540, 960, 540)
    
    def test_very_small_roi(self):
        """Test with very small ROI dimensions."""
        mapper = CoordinateMapper((1920, 1080), (320, 180))
        
        # 10x10 pixel ROI on display
        result = mapper.display_to_processing(100, 100, 10, 10)
        
        # Should have minimum 1 pixel dimensions
        assert result[2] >= 1
        assert result[3] >= 1
