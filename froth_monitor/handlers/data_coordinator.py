from typing import cast
from PySide6.QtCore import QObject, Signal

from froth_monitor.processing import FrameModel, ROI
from froth_monitor.lidar_thread.lidar_data_processor import LidarDataProcessor
from froth_monitor.air_recovery.air_recovery_data_processor import AirRecoveryDataProcessor
from froth_monitor.handlers.realtime_export import RealtimeExporter
from froth_monitor.handlers.logger_config import get_logger
from froth_monitor.handlers.data_matcher import VelocityLidarMatcher
from froth_monitor.utils.performance_monitor import PerformanceMonitor

logger = get_logger(__name__)

class DataCoordinator(QObject):
    """
    Coordinates data flow between processing modules, matching services, and export.
    Responsible for:
    1. Validating and Cleaning data.
    2. Matching Velocity and LiDAR data.
    3. Triggering Air Recovery Calculations.
    4. Orchestrating data export.
    """
    
    # Signals to notify UI or other components that new processed data is ready
    air_recovery_updated = Signal(list) # Emitted when a match is found and AR is calculated

    def __init__(self, frame_model: FrameModel, 
                 lidar_data_processor: LidarDataProcessor, 
                 air_recovery_data_processor: AirRecoveryDataProcessor):
        super().__init__()
        self.frame_model = frame_model
        self.lidar_data_processor = lidar_data_processor
        self.air_recovery_data_processor = air_recovery_data_processor
        
        self.perf_monitor = PerformanceMonitor()
        self.exporter: RealtimeExporter = cast(RealtimeExporter, None)

    def load_exporter(self, exporter: RealtimeExporter):
        self.exporter = exporter

    def process_new_velocity_data(self, roi_list: list[ROI]):
        """
        Slot to be called when new velocity data is available (e.g. from FrameProcessor).
        Initiates the matching process for Air Recovery.
        """
        self.perf_monitor.start_timer("data_coordinator_process")
        
        # Acquire lock to safely read roi_list
        with self.frame_model._processing_lock:
            for i, roi in enumerate(roi_list):
                 # Only proceed if we have Lidar data and enough history
                if self.lidar_data_processor.if_lidar and len(self.lidar_data_processor.reading_history_for_display) > 1:
                    # Start asynchronous matching
                    # The index logic len(roi.delta_history)-2 seems specific to previous implementation
                    # assuming the last items are the ones we want to match.
                    logger.debug(f"DataCoordinator: Start matching velocity and lidar for ROI {i + 1}")
                    self.start_matching_velo_n_lidar(i, roi, len(roi.delta_history)-1)
        
        self.perf_monitor.stop_timer("data_coordinator_process")

    def start_matching_velo_n_lidar(self, roi_number, roi: ROI, index):
        """Start asynchronous matching of velocity and lidar data."""
        
        # if not hasattr(roi, 'matcher'):
        #     logger.info(f"DataCoordinator: Initialize matcher for ROI {roi_number}")
        #     roi.matcher = VelocityLidarMatcher() # No args
        #     roi.matcher.match_found.connect(self._on_match_found)
        #     roi.matcher.match_failed.connect(self._on_match_failed)
        
        # Define provider callback
        def get_lidar_history():
            return self.lidar_data_processor.reading_history_av1s
        
        matcher = VelocityLidarMatcher()
        matcher.match_found.connect(self._on_match_found)
        matcher.match_failed.connect(self._on_match_failed)

        matcher.start_matching(
            context=roi, 
            velo_data=roi.velo_history_with_time[-1], 
            data_provider=get_lidar_history
        )

    def _on_match_found(self, roi: ROI, velo_data, lidar_data):
        """Handle successful match between velocity and lidar data."""
        # velo_data: [velocity, str_timestamp, unix_timestamp]
        # lidar_data: [[0, average_fh, str_timestamp, unix_timestamp]] (nested list from history)
        
        # Flatten structure if needed, based on previous implementation usage
        froth_height = lidar_data[0][1]
        velocity = velo_data[0]
        timestamp = velo_data[1]

        logger.debug(f"DataCoordinator: Match Found. V: {velocity}, FH: {froth_height}, T: {timestamp}")

        # Calculate Air Recovery
        air_rec, current_air_flow, current_air_flow_in_mm = self._calculate_air_recovery(roi, velocity, froth_height, timestamp)
        self._store_air_recovery(roi, timestamp, velocity, froth_height, air_rec, current_air_flow, current_air_flow_in_mm)

        # Notify UI to update
        self.air_recovery_updated.emit(self.frame_model.roi_list)

    def _on_match_failed(self, roi, velo_data):
        # logger.debug(f"DataCoordinator: Match failed for velocity timestamp: {velo_data[1][:8]}")
        pass

    def _calculate_air_recovery(self, roi, velocity, froth_height, timestamp) -> tuple[float, float, float]:
        try:
            timestamp, velocity, froth_height, air_rec, current_air_flow, current_air_flow_in_mm = \
                self.air_recovery_data_processor.process_air_recovery_data(velocity, froth_height, timestamp) # type: ignore
            return air_rec, current_air_flow, current_air_flow_in_mm
            
        except Exception as e:
            logger.error(f"DataCoordinator: Error in air recovery calculation: {e}")
            return 0.0, 0.0, 0.0

    def _store_air_recovery(self, roi, timestamp, velocity, froth_height, air_rec, \
        current_air_flow, current_air_flow_in_mm):
        
        append_list = [timestamp, velocity, froth_height, air_rec, current_air_flow, current_air_flow_in_mm]
        roi.update_sum_history(append_list)

        if self.exporter is not None:
            self.exporter.write_roi_summary_data(roi.id, append_list)

    def stop_all_matchers(self):
        """Helper to stop matchers on closing."""
        with self.frame_model._processing_lock:
            for roi in self.frame_model.roi_list:
                if hasattr(roi, 'matcher'):
                    roi.matcher.stop_matching()
