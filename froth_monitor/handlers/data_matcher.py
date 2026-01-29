import time
from typing import cast

from PySide6.QtCore import QObject, Signal, QTimer

# Import FrameModel from fm_model module
from froth_monitor.processing import FrameModel, ROI
from froth_monitor.handlers.logger_config import get_logger

# Initialize logger for this module
logger = get_logger(__name__)

class VelocityLidarMatcher(QObject):
    """Asynchronous matcher for velocity and lidar data based on Unix timestamps."""
    
    # Signals
    # context: ROI instance
    # velo_data: The velocity data being matched
    # lidar_data: The matched lidar data (or None if failed)
    match_found = Signal(ROI, list, list) 
    match_failed = Signal(ROI, list)
    
    def __init__(self):
        super().__init__()
        self.context: ROI | None = None
        self.data_provider = None
        self.current_velo_data = None
        self.target_unix_time = None
        
        self.matching_timer = QTimer()
        self.matching_timer.timeout.connect(self._check_for_match)
        
        self.start_time = cast(float, None)
        self.max_wait_time = 3.0
        self.initial_lidar_count = 0
        self.time_tolerance = 1.5 # seconds
        
    def start_matching(self, context: ROI, velo_data: list, data_provider):
        """
        Start matching process.
        
        Args:
            context: ROI instance to track this request. Passed back in signals.
            velo_data: List containing [velocity, str_timestamp, unix_timestamp].
            data_provider: Callable that returns the current list of lidar history.
        """
        self.context = context
        self.current_velo_data = velo_data
        self.data_provider = data_provider
        
        # Use Unix timestamp (index 2)
        if len(velo_data) > 2:
            self.target_unix_time = velo_data[2]
        else:
            logger.error("DataMatcher: Velocity data missing Unix timestamp")
            self.match_failed.emit(self.context, self.current_velo_data)
            return

        # Get current lidar data using the provider
        lidar_history = self.data_provider()

        # Check for immediate match
        if self._check_immediate_match(lidar_history):
            return

        # Start timer for periodic checking
        self.initial_lidar_count = len(lidar_history)
        self.start_time = time.time()
        self.matching_timer.start(100) # Check every 100ms
        
    def _check_immediate_match(self, lidar_history):
        """Check for immediate match in current lidar data."""
        if not lidar_history:
            return False
            
        for lidar_entry in reversed(lidar_history):
            # Access the inner list
            data_point = lidar_entry[0]
            if len(data_point) > 3:
                lidar_unix_time = data_point[3]
                
                diff = abs(lidar_unix_time - self.target_unix_time)
                if diff < self.time_tolerance:
                    self.match_found.emit(self.context, self.current_velo_data, lidar_entry)
                    return True
                
                if self.target_unix_time - lidar_unix_time > self.time_tolerance:
                    break
                    
        return False

    def _check_for_match(self):
        """Periodic check for new lidar data."""
        if time.time() - self.start_time > self.max_wait_time:
            self.matching_timer.stop()
            self.match_failed.emit(self.context, self.current_velo_data)
            return
        
        try:
            formatted_history = self.data_provider()
        except Exception as e:
            logger.error(f"DataMatcher: Error getting lidar history: {e}")
            self.match_failed.emit(self.context, self.current_velo_data)
            return
            
        if len(formatted_history) > self.initial_lidar_count:
            new_items = formatted_history[self.initial_lidar_count:]
            self.initial_lidar_count = len(formatted_history)
            
            if self._check_immediate_match(new_items):
                self.matching_timer.stop()
                return
    
    def stop_matching(self):
        """Stop the matching timer."""
        if self.matching_timer.isActive():
            self.matching_timer.stop() 
