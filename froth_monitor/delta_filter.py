"""Delta Filter Module for Froth Monitor Application.

This module provides the DeltaFilter class for applying various filtering
techniques to delta/projection data, including noise reduction and outlier detection.
Designed to integrate with the ROI module for improved delta data quality.

Classes:
--------
DeltaFilter
    Manages and applies filtering techniques to delta/projection data streams.

Example Usage:
--------------
```python
from delta_filter import DeltaFilter

# Initialize the filter
delta_filter = DeltaFilter(window_size=5, outlier_threshold=2.0)

# Apply filtering to new delta data
filtered_history = delta_filter.filter(new_delta, delta_history)
```
"""

import numpy as np
from typing import List, Union, Optional
# from scipy import signal
from froth_monitor.logger_config import get_logger

# Initialize logger for this module
logger = get_logger(__name__)


class DeltaFilter:
    """
    Delta Filter Class for Signal Processing.
    
    This class provides methods for filtering delta/projection data to reduce noise
    and handle outliers. It's designed to integrate with the ROI module
    for real-time delta data processing.
    
    Attributes:
    ----------
    window_size : int
        Size of the moving window for noise filtering (default: 35)
    outlier_threshold : float
        Z-score threshold for outlier detection (default: 2.0)
    max_history_size : int
        Maximum size of delta history to maintain (default: 1000)
    
    Methods:
    -------
    noise_filter(delta_data: List[float]) -> List[float]
        Apply noise reduction using moving average filter
    outlier_filter(delta_data: List[float]) -> List[float]
        Detect and handle outliers using Z-score method
    filter(new_delta: float, delta_history: List[float]) -> List[float]
        Main filtering method that orchestrates noise and outlier filtering
    """
    
    def __init__(self, window_size: int = 35, outlier_threshold: float = 2.0, 
                 max_history_size: int = 1000):
        """
        Initialize the DeltaFilter with configurable parameters.
        
        Parameters
        ----------
        window_size : int, optional
            Size of the moving window for noise filtering (default: 35)
        outlier_threshold : float, optional
            Z-score threshold for outlier detection (default: 2.0)
        max_history_size : int, optional
            Maximum size of delta history to maintain (default: 1000)
        """
        self.window_size = max(1, window_size)  # Ensure minimum window size of 1
        self.outlier_threshold = max(0.1, outlier_threshold)  # Minimum threshold
        self.max_history_size = max(10, max_history_size)  # Minimum history size
        
        logger.info(f"DeltaFilter initialized with window_size={self.window_size}, "
                   f"outlier_threshold={self.outlier_threshold}, "
                   f"max_history_size={self.max_history_size}")
    
    def _validate_and_sanitize_data(self, delta_data: List[float]) -> np.ndarray:
        """
        Validate and sanitize delta data.
        
        Parameters
        ----------
        delta_data : List[float]
            Input delta data
            
        Returns
        -------
        np.ndarray
            Sanitized delta data as numpy array
        """
        if not delta_data:
            return np.array([])
        
        # Convert to numpy array and handle invalid values
        data = np.array(delta_data, dtype=float)
        
        # Replace infinite values with NaN
        data[np.isinf(data)] = np.nan
        
        # Replace extremely large values (> 1e6) with NaN
        data[np.abs(data) > 1e6] = np.nan
        
        return data
    
    def noise_filter(self, delta_data: List[float]) -> List[float]:
        """
        Apply noise reduction to delta data using moving average filter.
        
        This method implements a moving average filter to smooth delta data
        and reduce high-frequency noise. The filter uses a configurable window
        size and handles edge cases appropriately.
        
        Parameters
        ----------
        delta_data : List[float]
            Input delta data to be filtered
            
        Returns
        -------
        List[float]
            Noise-filtered delta data
        """
        data = self._validate_and_sanitize_data(delta_data)
        
        if len(data) == 0:
            return []
        
        if len(data) < self.window_size:
            # If data is shorter than window, use simple mean of available data
            valid_data = data[~np.isnan(data)]
            if len(valid_data) > 0:
                filtered_value = np.mean(valid_data)
                return [filtered_value if np.isfinite(filtered_value) else 0.0] * len(data)
            else:
                return [0.0] * len(data)
        
        # Apply moving average filter
        filtered_data = []
        
        for i in range(len(data)):
            # Define window boundaries
            start_idx = max(0, i - self.window_size // 2)
            end_idx = min(len(data), i + self.window_size // 2 + 1)
            
            # Extract window data and remove NaN values
            window_data = data[start_idx:end_idx]
            valid_window = window_data[~np.isnan(window_data)]
            
            if len(valid_window) > 0:
                filtered_value = np.mean(valid_window)
                # Validate the filtered value
                if np.isfinite(filtered_value) and abs(filtered_value) < 1e6:
                    filtered_data.append(float(filtered_value))
                else:
                    filtered_data.append(0.0)
            else:
                # If no valid data in window, use 0.0
                filtered_data.append(0.0)
        
        logger.debug(f"Applied noise filter to {len(delta_data)} data points")
        return filtered_data
    
    def outlier_filter(self, delta_data: List[float]) -> List[float]:
        """
        Detect and handle outliers in delta data using Z-score method.
        
        This method identifies outliers using the Z-score statistical method
        and replaces them with the median of the remaining data. The Z-score
        threshold is configurable.
        
        Parameters
        ----------
        delta_data : List[float]
            Input delta data to be filtered
            
        Returns
        -------
        List[float]
            Outlier-filtered delta data
        """
        data = self._validate_and_sanitize_data(delta_data)
        
        if len(data) == 0:
            return []
        
        # Remove NaN values for statistical calculations
        valid_data = data[~np.isnan(data)]
        
        if len(valid_data) < 3:
            # Need at least 3 points for meaningful outlier detection
            return [float(val) if np.isfinite(val) else 0.0 for val in data]
        
        # Calculate Z-scores
        mean_val = np.mean(valid_data)
        std_val = np.std(valid_data)
        
        if std_val == 0:
            # If standard deviation is 0, no outliers can be detected
            return [float(val) if np.isfinite(val) else 0.0 for val in data]
        
        # Calculate median for outlier replacement
        median_val = np.median(valid_data)
        
        # Process each data point
        filtered_data = []
        outlier_count = 0
        
        for val in data:
            if np.isnan(val):
                filtered_data.append(0.0)
            else:
                z_score = abs((val - mean_val) / std_val)
                
                if z_score > self.outlier_threshold:
                    # Replace outlier with median
                    filtered_data.append(float(median_val))
                    outlier_count += 1
                else:
                    # Keep original value
                    filtered_data.append(float(val))
        
        if outlier_count > 0:
            logger.debug(f"Detected and replaced {outlier_count} outliers out of {len(delta_data)} data points")
        
        return filtered_data
    
    def filter(self, new_delta: float, delta_history: List[float]) -> List[float]:
        """
        Main filtering method that orchestrates noise and outlier filtering.
        
        This method combines the new delta with the existing history,
        applies both noise and outlier filtering, and returns the refined
        delta history. It also manages the history size to prevent
        unlimited growth.
        
        Parameters
        ----------
        new_delta : float
            New delta value to be added to the history
        delta_history : List[float]
            Existing delta history
            
        Returns
        -------
        List[float]
            Filtered and refined delta history
        """
        # Validate new delta
        if not np.isfinite(new_delta) or abs(new_delta) > 1e6:
            logger.warning(f"Invalid new delta value: {new_delta}, replacing with 0.0")
            new_delta = 0.0
        
        # Create updated history
        updated_history = list(delta_history) + [float(new_delta)]
        
        # Limit history size to prevent memory issues
        if len(updated_history) > self.max_history_size:
            updated_history = updated_history[-self.max_history_size:]
            logger.debug(f"Trimmed delta history to {self.max_history_size} elements")
        
        # Apply outlier filtering first to remove extreme values
        outlier_filtered = self.outlier_filter(updated_history)
        
        # Apply noise filtering to smooth the data
        noise_filtered = self.noise_filter(outlier_filtered)
        
        logger.info(f"Applied complete filtering to delta history of length {len(updated_history)}")
        return noise_filtered
    
    def get_filter_stats(self, delta_data: List[float]) -> dict:
        """
        Get statistical information about the delta data.
        
        Parameters
        ----------
        delta_data : List[float]
            Delta data to analyze
            
        Returns
        -------
        dict
            Dictionary containing statistical measures
        """
        data = self._validate_and_sanitize_data(delta_data)
        valid_data = data[~np.isnan(data)]
        
        if len(valid_data) == 0:
            return {
                'count': 0,
                'mean': 0.0,
                'std': 0.0,
                'median': 0.0,
                'min': 0.0,
                'max': 0.0
            }
        
        return {
            'count': len(valid_data),
            'mean': float(np.mean(valid_data)),
            'std': float(np.std(valid_data)),
            'median': float(np.median(valid_data)),
            'min': float(np.min(valid_data)),
            'max': float(np.max(valid_data))
        }
    
    def update_parameters(self, window_size: Optional[int] = None, 
                         outlier_threshold: Optional[float] = None,
                         max_history_size: Optional[int] = None):
        """
        Update filter parameters dynamically.
        
        Parameters
        ----------
        window_size : int, optional
            New window size for noise filtering
        outlier_threshold : float, optional
            New threshold for outlier detection
        max_history_size : int, optional
            New maximum history size
        """
        if window_size is not None:
            self.window_size = max(1, window_size)
            logger.info(f"Updated window_size to {self.window_size}")
        
        if outlier_threshold is not None:
            self.outlier_threshold = max(0.1, outlier_threshold)
            logger.info(f"Updated outlier_threshold to {self.outlier_threshold}")
        
        if max_history_size is not None:
            self.max_history_size = max(10, max_history_size)
            logger.info(f"Updated max_history_size to {self.max_history_size}")