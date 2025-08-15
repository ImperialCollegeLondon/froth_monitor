"""Simplified Delta Filter Module with Low-Pass Filtering Only."""

import numpy as np
from collections import deque
from typing import List
from froth_monitor.logger_config import get_logger

logger = get_logger(__name__)

class DeltaFilter:
    """
    Simplified Delta Filter with only low-pass filtering for real-time processing.
    
    This implementation preserves true values while applying only low-pass
    filtering to reduce high-frequency instrumental noise.
    """
    
    def __init__(self, max_history_size: int = 1000, lowpass_alpha: float = 0.1):
        """
        Initialize the simplified delta filter with low-pass filtering only.
        
        Parameters
        ----------
        max_history_size : int
            Maximum history size to maintain
        lowpass_alpha : float
            Low-pass filter coefficient (0 < alpha <= 1)
            Higher values = less filtering, lower values = more filtering
        """
        self.max_history_size = max(10, max_history_size)
        self.lowpass_alpha = max(0.01, min(1.0, lowpass_alpha))
        
        # Use deque for efficient append/pop operations
        self.history = deque(maxlen=self.max_history_size)
        
        # Low-pass filter state
        self._lowpass_output = 0.0
        self._lowpass_initialized = False
        
        logger.info(f"Simplified DeltaFilter initialized with lowpass_alpha={self.lowpass_alpha}")
    
    def _validate_value(self, value: float) -> float:
        """Validate and sanitize a single value."""
        if not np.isfinite(value) or abs(value) > 1e6:
            return 0.0
        return float(value)
    
    def _apply_lowpass_filter(self, input_value: float) -> float:
        """
        Apply exponential low-pass filter to reduce high-frequency noise.
        
        This preserves the true signal while reducing instrumental noise.
        """
        if not self._lowpass_initialized:
            self._lowpass_output = input_value
            self._lowpass_initialized = True
            return input_value
        
        self._lowpass_output = (self.lowpass_alpha * input_value + 
                               (1.0 - self.lowpass_alpha) * self._lowpass_output)
        
        return self._lowpass_output
    
    def filter(self, new_delta: float, delta_history: List[float]) -> List[float]:
        """
        Simplified filtering with only low-pass filtering.
        
        Processing pipeline:
        1. Input validation
        2. Low-pass filtering for noise reduction only
        
        Parameters
        ----------
        new_delta : float
            New delta value to be added
        delta_history : List[float]
            Existing delta history (used for initialization only)
            
        Returns
        -------
        List[float]
            Updated filtered history
        """
        # Initialize from history if this is the first call
        if len(self.history) == 0 and delta_history:
            for value in delta_history[-self.max_history_size:]:
                validated_value = self._validate_value(value)
                filtered_value = self._apply_lowpass_filter(validated_value)
                self.history.append(filtered_value)
        
        # Step 1: Validate new value
        validated_delta = self._validate_value(new_delta)
        
        # Step 2: Apply low-pass filter to reduce instrumental noise
        filtered_value = self._apply_lowpass_filter(validated_delta)
        
        # Add to history
        self.history.append(filtered_value)
        
        return list(self.history)
    
    def get_current_stats(self) -> dict:
        """Get current filter statistics."""
        if len(self.history) == 0:
            return {
                'count': 0,
                'lowpass_output': 0.0
            }
        
        return {
            'count': len(self.history),
            'lowpass_output': self._lowpass_output
        }
    
    def update_lowpass_alpha(self, new_alpha: float):
        """Update the low-pass filter coefficient dynamically."""
        old_alpha = self.lowpass_alpha
        self.lowpass_alpha = max(0.01, min(1.0, new_alpha))
        logger.info(f"Updated low-pass filter alpha from {old_alpha:.3f} to {self.lowpass_alpha:.3f}")
    
    def reset_lowpass_filter(self):
        """Reset the low-pass filter state."""
        self._lowpass_output = 0.0
        self._lowpass_initialized = False
        logger.info("Low-pass filter state reset")