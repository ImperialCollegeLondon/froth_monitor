import time
from typing import cast

from PySide6.QtCore import QObject, Signal, QTimer

# Import MainGUIWindow at the beginning
from froth_monitor.handlers.gui_window import MainGUIWindow

# Import FrameModel from fm_model module
from froth_monitor.processing.fm_model import FrameModel, ROI
from froth_monitor.lidar_thread.lidar_data_processor import LidarDataProcessor
from froth_monitor.air_recovery.air_recovery_data_processor import AirRecoveryDataProcessor
from froth_monitor.handlers.realtime_export import RealtimeExporter
from froth_monitor.handlers.logger_config import get_logger

# Initialize logger for this module
logger = get_logger(__name__)

class DataHandler:
    def __init__(self, gui: MainGUIWindow, frame_model: FrameModel, 
    lidar_data_processor: LidarDataProcessor, air_recovery_data_processor: AirRecoveryDataProcessor):
        self.gui = gui
        self.frame_model = frame_model
        self.plot_widget = self.gui.plot_widget

        self.lidar_data_processor = lidar_data_processor
        self.lidar_data_processor.display_data_available.connect(self.update_fh_plot)

        self.air_recovery_data_processor = air_recovery_data_processor

        self.if_lidar = False
        self.if_air_rec = False

        self.table_list_data = []
        self.frame_lidar_hist = []

        self.exporter: RealtimeExporter = cast(RealtimeExporter, None)

    # ------------------------------------Plotting Functions------------------------------------------

    def update_arec_data(self):
        """Update the average velocity table with data from all ROIs.
        
        Thread-safe: Acquires frame_model lock to prevent race conditions.
        """
        logger.info("Data handler: Updating velocity table")

        # Acquire lock to safely read roi_list
        with self.frame_model._processing_lock:
            # Add data to the table
            for i, roi in enumerate(self.frame_model.roi_list):
                if self.lidar_data_processor.if_lidar and len(self.lidar_data_processor.reading_history_for_display) > 1:
                    # Start asynchronous matching - results will be handled by signal callbacks
                    self.start_matching_velo_n_lidar(i, roi, len(roi.delta_history)-2)

    def update_arec_table(self):
        table_list_data = []

        if len(self.frame_model.roi_list) == 0:
            return

        for i, roi in enumerate(self.frame_model.roi_list):
            if len(roi.sum_history) == 0:
                continue

            timestamp = roi.sum_history[len(roi.sum_history)-1][0][:8]
            list_data_a = roi.sum_history[len(roi.sum_history)-1][1:4]
            # timestamp, velocity, froth_height, air_recovery, air flow rate, crcted air flrt
            table_list_data.append([timestamp] + list_data_a)

        self.gui.velo_widget.setData(table_list_data)
        self.gui.velo_widget.setHorizontalHeaderLabels(["timestamp", "v(mm/s)", "f_height(mm)", "air_rec(%)"])
        self.gui.velo_widget.setFormat("%.2f")
        self.gui.velo_widget.setMinimumHeight(110)
        self.gui.velo_widget.setColumnWidth(0, 65)
        self.gui.velo_widget.setColumnWidth(1, 65)
        self.gui.velo_widget.setColumnWidth(2, 65)
        self.gui.velo_widget.setColumnWidth(3, 65)

        self.gui.velo_widget.setStyleSheet(
            """
            background-color: #f0f0f0; 
            font-size: 10px;
            border: 1px solid #ccc;
            border-radius: 4px;
            """
        )
        
        # Update air recovery plot with data from all ROIs
        self._update_arec_plot()
    
    def _update_arec_plot(self):
        """Update the air recovery plot with data from all ROIs.

        This method extracts air recovery history data from each ROI in the frame_model's roi_list
        and plots it on the ar_plot_widget. Each ROI's air recovery history is plotted as a separate
        line with a different color and labeled in the legend.

        The plot displays a fixed window of 30 elements (3 seconds) with new data appearing
        from the right edge and older data scrolling to the left. When the history exceeds
        30 elements, the oldest elements are removed to maintain the fixed window size.
        
        Thread-safe: Acquires frame_model lock to prevent race conditions.
        """
        import numpy as np
        
        all_list = []

        # Clear the air recovery plot widget
        self.gui.ar_plot_widget.clear()

        # Acquire lock to safely read roi_list and roi data
        with self.frame_model._processing_lock:
            # Check if there are any ROIs to plot
            if not self.frame_model.roi_list:
                return

            # Define a list of colors for different ROIs
            colors = [
                "r",
                "g",
                "b",
                "c",
                "m",
                "y",
                "w",
            ]  # Red, green, blue, cyan, magenta, yellow, white

            # Fixed window size (3 seconds)
            WINDOW_SIZE = 30

            # Helper function to sanitize air recovery data
            def sanitize_air_recovery_data(data):
                """Remove invalid values (inf, nan, extremely large values) from air recovery data."""
                sanitized = []
                for value in data:
                    if value is not None and np.isfinite(value) and abs(value) < 1e6:
                        sanitized.append(value)
                    else:
                        sanitized.append(0.0)  # Replace invalid values with 0
                return sanitized

            # Extract air recovery history from sum_history (4th element, index 3)
            def extract_air_recovery_history(roi):
                """Extract air recovery values from roi.sum_history."""
                air_recovery_history = []
                for entry in roi.sum_history_for_display:
                    if len(entry) > 3:  # Ensure air_recovery exists (4th element)
                        air_recovery_history.append(entry[3])  # air_recovery is at index 3
                    else:
                        air_recovery_history.append(0.0)  # Default value if not available
                return air_recovery_history

            # Find the maximum air recovery across all ROIs for y-axis scaling
            max_air_recovery = 0
            if self.frame_model.roi_list and any(
                roi.sum_history_for_display for roi in self.frame_model.roi_list
            ):
                all_air_recoveries = []
                for roi in self.frame_model.roi_list:
                    if roi.sum_history_for_display:
                        air_recovery_history = extract_air_recovery_history(roi)
                        sanitized_history = sanitize_air_recovery_data(air_recovery_history)
                        all_air_recoveries.extend(sanitized_history)
                
                if all_air_recoveries:
                    max_air_recovery = max(all_air_recoveries)

            max_len = 0
            # Plot air recovery history for each ROI
            for i, roi in enumerate(self.frame_model.roi_list):
                # Skip if no sum_history
                if not roi.sum_history_for_display:
                    continue

                # Get color for this ROI (cycle through colors if more ROIs than colors)
                color = colors[i % len(colors)]

                # Get the air recovery history data and sanitize it
                air_recovery_history = extract_air_recovery_history(roi)
                history = sanitize_air_recovery_data(air_recovery_history)
                history_length = len(history)

                all_list.append(history)

                # Limit history to the most recent WINDOW_SIZE elements
                if history_length > WINDOW_SIZE:
                    history = history[-WINDOW_SIZE:]


                if i == 0:
                    max_len = history_length
                    # Limit history to the most recent WINDOW_SIZE elements
                    if history_length > WINDOW_SIZE:
                        history = history[-WINDOW_SIZE:]
                        start_pos = history_length - WINDOW_SIZE
                    else:
                        start_pos = 0
                else:
                    if history_length > WINDOW_SIZE:
                        start_pos = max_len - WINDOW_SIZE
                    else:
                        start_pos = max_len - history_length
                    
                # Create x-axis data - higher x-values are on the right
                x_data = []
                for j in range(len(history)):
                    x_data.append(start_pos + j)

                # Create y-axis data with None values filtered out for plotting
                # (pyqtgraph will skip None values when plotting)
                plot_x = []
                plot_y = []
                for x, y in zip(x_data, history):
                    if y is not None and np.isfinite(y):
                        plot_x.append(x)
                        plot_y.append(y)

                # Add the plot with a label for the legend
                if plot_x and plot_y:  # Only plot if we have data
                    self.gui.ar_plot_widget.plot(
                        plot_x, plot_y, pen=color, name=f"ROI {i + 1}"
                    )


        x_max = max_len - 1
        x_min = x_max - WINDOW_SIZE + 1
        
        self.gui.ar_plot_widget.setXRange(x_min, x_max)

        # Set appropriate y-axis range if there's data
        if max_air_recovery > 0 and np.isfinite(max_air_recovery):
            # Add some padding to the top of the y-axis
            self.gui.ar_plot_widget.setYRange(0, max_air_recovery * 1.1)

        # Update the plot
        self.gui.ar_plot_widget.update()

    def update_fh_plot(self, lidar_reading_history):
        """Update the velocity plot with data from all ROIs.

        This method extracts velocity history data from each ROI in the frame_model's roi_list
        and plots it on the plot_widget. Each ROI's velocity history is plotted as a separate
        line with a different color and labeled in the legend.

        The plot displays a fixed window of 30 elements (3 seconds) with new data appearing
        from the right edge and older data scrolling to the left. When the history exceeds
        30 elements, the oldest elements are removed to maintain the fixed window size.
        """
        import numpy as np
        
        # Clear the plot widget
        self.gui.froth_height_plot_widget.clear()

        # Check if there are any ROIs to plot
        if not lidar_reading_history:
            return

        # Define a list of colors for different ROIs
        colors = [
            "r",
            "g",
            "b",
            "c",
            "m",
            "y",
            "w",
        ]  # Red, green, blue, cyan, magenta, yellow, white

        # Fixed window size (3 seconds)
        WINDOW_SIZE = 30

        # Helper function to sanitize froth height data
        def sanitize_data(data):
            """Remove invalid values (inf, nan, extremely large values) from data."""
            sanitized = []
            for value in data:
                if value is not None and np.isfinite(value) and abs(value) < 1e6:
                    sanitized.append(value)
                else:
                    sanitized.append(0.0)  # Replace invalid values with 0
            return sanitized

        # Sanitize the lidar reading history
        sanitized_history = sanitize_data(lidar_reading_history)

        # Find the maximum froth height for y-axis scaling
        max_fh = 0
        if sanitized_history:
            max_fh = max(sanitized_history)

        # Get the velocity history data
        history = sanitized_history
        history_length = len(history)

        # Limit history to the most recent WINDOW_SIZE elements
        if history_length > WINDOW_SIZE:
            history = history[-WINDOW_SIZE:]
            start_pos = history_length - WINDOW_SIZE
        else:
            start_pos = 0

        # Create x-axis data - higher x-values are on the right
        x_data = []
        for j in range(len(history)):
            x_data.append(start_pos + j)

        # Create y-axis data with None values filtered out for plotting
        # (pyqtgraph will skip None values when plotting)
        plot_x = []
        plot_y = []
        for x, y in zip(x_data, history):
            if y is not None and np.isfinite(y):
                plot_x.append(x)
                plot_y.append(y)

        # Add the plot with a label for the legend
        if plot_x and plot_y:  # Only plot if we have data
            self.gui.froth_height_plot_widget.plot(
                plot_x, plot_y, pen=colors[2], name=f"froth height"
            )
        
        x_max = history_length - 1
        x_min = x_max - WINDOW_SIZE + 1
        
        self.gui.froth_height_plot_widget.setXRange(x_min, x_max)

        # Set appropriate y-axis range if there's data
        if max_fh > 0 and np.isfinite(max_fh):
            # Add some padding to the top of the y-axis
            self.gui.froth_height_plot_widget.setYRange(0, max_fh * 1.1)

        # Update the plot
        self.gui.froth_height_plot_widget.update()

    def update_velocity_plot(self):
        """Update the velocity plot with data from all ROIs.

        This method extracts velocity history data from each ROI in the frame_model's roi_list
        and plots it on the plot_widget. Each ROI's velocity history is plotted as a separate
        line with a different color and labeled in the legend.

        The plot displays a fixed window of 30 elements (3 seconds) with new data appearing
        from the right edge and older data scrolling to the left. When the history exceeds
        30 elements, the oldest elements are removed to maintain the fixed window size.
        
        Thread-safe: Acquires frame_model lock to prevent race conditions.
        """
        import numpy as np
        
        # Clear the plot widget
        self.gui.plot_widget.clear()

        # Acquire lock to safely read roi_list and roi data
        with self.frame_model._processing_lock:
            # Check if there are any ROIs to plot
            if not self.frame_model.roi_list:
                return

            # Define a list of colors for different ROIs
            colors = [
                "r",
                "g",
                "b",
                "c",
                "m",
                "y",
                "w",
            ]  # Red, green, blue, cyan, magenta, yellow, white

            # Fixed window size (3 seconds)
            WINDOW_SIZE = 30

            # Helper function to sanitize velocity data
            def sanitize_velocity_data(data):
                """Remove invalid values (inf, nan, extremely large values) from velocity data."""
                sanitized = []
                for value in data:
                    if value is not None and np.isfinite(value) and abs(value) < 1e6:
                        sanitized.append(value)
                    else:
                        sanitized.append(0.0)  # Replace invalid values with 0
                return sanitized

            # Find the maximum velocity across all ROIs for y-axis scaling
            max_velocity = 0
            if self.frame_model.roi_list and any(
                roi.velo_only_history_for_display for roi in self.frame_model.roi_list
            ):
                all_velocities = []
                for roi in self.frame_model.roi_list:
                    if roi.velo_only_history_for_display:
                        sanitized_history = sanitize_velocity_data(roi.velo_only_history_for_display)
                        all_velocities.extend(sanitized_history)
                
                if all_velocities:
                    max_velocity = max(all_velocities)

            max_len = 0
            # Plot velocity history for each ROI
            for i, roi in enumerate(self.frame_model.roi_list):
                # Skip if no velocity history
                if not roi.velo_only_history_for_display:
                    continue

                # Get color for this ROI (cycle through colors if more ROIs than colors)
                color = colors[i % len(colors)]

                # Get the velocity history data and sanitize it
                history = sanitize_velocity_data(roi.velo_only_history_for_display)
                history_length = len(history)

                # Limit history to the most recent WINDOW_SIZE elements
                if len(history) > WINDOW_SIZE:
                    history = history[-WINDOW_SIZE:]

                # Position the data at the right side of the display
                # For example, if we have 5 elements, they go in positions 25-29 (0-indexed)
                # start_pos = len(history) - WINDOW_SIZE
                if i == 0:
                    max_len = history_length
                    # Limit history to the most recent WINDOW_SIZE elements
                    if history_length > WINDOW_SIZE:
                        history = history[-WINDOW_SIZE:]
                        start_pos = history_length - WINDOW_SIZE
                    else:
                        start_pos = 0
                else:
                    if history_length > WINDOW_SIZE:
                        start_pos = max_len - WINDOW_SIZE
                    else:
                        start_pos = max_len - history_length
                    
                # Create x-axis data - higher x-values are on the right
                x_data = []
                for j in range(len(history)):
                    x_data.append(start_pos + j)

                # Create y-axis data with None values filtered out for plotting
                # (pyqtgraph will skip None values when plotting)
                plot_x = []
                plot_y = []
                for x, y in zip(x_data, history):
                    if y is not None and np.isfinite(y):
                        plot_x.append(x)
                        plot_y.append(y)

                # Add the plot with a label for the legend
                if plot_x and plot_y:  # Only plot if we have data
                    self.gui.plot_widget.plot(
                        plot_x, plot_y, pen=color, name=f"ROI {i + 1}"
                    )


        max_history_length = max(len(roi.velo_only_history_for_display) for roi in self.frame_model.roi_list if roi.velo_only_history)
        x_max = max_history_length - 1
        x_min = x_max - WINDOW_SIZE + 1
        
        self.gui.plot_widget.setXRange(x_min, x_max)

        # Set appropriate y-axis range if there's data
        if max_velocity > 0 and np.isfinite(max_velocity):
            # Add some padding to the top of the y-axis
            self.gui.plot_widget.setYRange(0, max_velocity * 1.1)

        # Update the plot
        self.gui.plot_widget.update()

    def start_matching_velo_n_lidar(self, roi_number, roi, index):
        """Start asynchronous matching of velocity and lidar data.
        
        Args:
            velo_data: Velocity data with timestamp
        """

        if not hasattr(roi, 'matcher'):
            roi.matcher = VelocityLidarMatcher(self.lidar_data_processor)
            roi.matcher.match_found.connect(self._on_match_found)
            roi.matcher.match_failed.connect(self._on_match_failed)
        
        logger.info(f"Data handler: ===Start matching frame and lidar for ROI {roi_number + 1}===")
        logger.info(f"Data handler: Frame index {index}")
        roi.matcher.start_matching(roi, index)

    def _on_match_found(self, roi, velo_data, lidar_data, index):
        """Handle successful match between velocity and lidar data."""

        velo_n_fh = [velo_data, lidar_data]
        logger.info(f"Data handler: Velocity and Froth Height Match Found: {velo_n_fh}")

        froth_height = lidar_data[0][1]
        velocity = velo_data[0]
        timestamp = velo_data[1]
        air_rec = self.air_rec_calculation(roi, velocity, froth_height, timestamp)
        logger.info(f"Data handler: Air Recovery{air_rec}")

        self.update_arec_table()

    def _on_match_failed(self, roi, velo_data, index):
        """Handle failed match between velocity and lidar data."""
        logger.info(f"Data handler: No matching lidar data found for velocity timestamp: {velo_data[1][:8]}")
    
    def stop_matcher(self, roi):
        """Stop the velocity-lidar matcher if it exists."""
        if hasattr(roi, 'matcher'):
            roi.matcher.stop_matching()
    
    def air_rec_calculation(self, roi, velocity, froth_height, timestamp) -> float:
        """
        Calculate air recovery using the air recovery data processor.
        
        Args:
            velocity (float): Overflow velocity in mm/s
            froth_height (float): Froth height in mm
            
        Returns:
            float: Air recovery percentage
        """
        try:
            # Get current timestamp
            
            # Process data through air recovery processor
            if hasattr(self, 'air_recovery_data_processor'):
                if self.air_recovery_data_processor is not None:
                    timestamp, velocity, froth_height, air_rec, current_air_flow, current_air_flow_in_mm = \
                        self.air_recovery_data_processor.process_air_recovery_data(velocity, froth_height, timestamp) # type: ignore

                    self.roi_sum_history_append(roi, timestamp, velocity, froth_height, air_rec, current_air_flow, current_air_flow_in_mm)
                air_rec = self.air_recovery_data_processor.get_current_air_recovery()
            

            else:
                logger.warning("Data handler: Air recovery data processor not available")
                air_rec = 0.0
                
            return air_rec
            
        except Exception as e:
            logger.error(f"Data handler: Error in air recovery calculation: {e}")
            return 0.0
    
    def roi_sum_history_append(self, roi, timestamp, velocity, froth_height, air_rec, \
        current_air_flow, current_air_flow_in_mm):
        append_list = [timestamp, velocity, froth_height, air_rec, current_air_flow, current_air_flow_in_mm]
        roi.update_sum_history(append_list)

        if self.exporter is not None:
            self.exporter.write_roi_summary_data(roi.id, append_list)

    def load_exporter(self, exporter: RealtimeExporter):
        self.exporter = exporter

    def clear_display_history(self):
        """Clear display history for all ROIs and plots.
        
        Thread-safe: Acquires frame_model lock to prevent race conditions.
        """
        try:
            # Acquire lock to safely modify roi data
            with self.frame_model._processing_lock:
                for roi in self.frame_model.roi_list:
                    roi.clear_display_history()
            
            self.lidar_data_processor.clear_display_history()

            self.gui.froth_height_plot_widget.clear()
            self.gui.ar_plot_widget.clear()
            self.gui.plot_widget.clear()

        except Exception as e:
            logger.error(f"Data handler: Error in clear_display_history: {e}")

class VelocityLidarMatcher(QObject):
    """Asynchronous matcher for velocity and lidar data based on timestamps."""
    
    # Signals
    match_found = Signal(ROI, list, list, int)  # velo_data, lidar_data, frame index
    match_failed = Signal(ROI, list, int)  # velo_data
    
    def __init__(self, lidar_data_processor):
        super().__init__()
        self.lidar_data_processor = lidar_data_processor
        self.roi: ROI = cast(ROI, None)
        self.index = 0
        self.matching_timer = QTimer()
        self.matching_timer.timeout.connect(self._check_for_match)
        self.current_velo_data = None
        self.target_timestamp = None
        self.current_roi_number = 0
        self.start_time = cast(float, None)
        self.max_wait_time = 1.0  # 1 second maximum wait
        self.initial_lidar_count = 0
        
    def start_matching(self, roi: ROI, index):

        """Start matching process for given velocity data."""
        self.roi = roi
        self.index = index

        velo_data = roi.velo_history_with_time[-1]
        self.current_velo_data = velo_data
        self.target_timestamp = velo_data[1][:8] # Extract HH:MM:SS
        self.target_time_marker = velo_data[2]
        self.start_time = cast(float, None)

        # Get current lidar data
        lidar_history = self.lidar_data_processor.reading_history_av1s

        if not lidar_history:
            self.match_failed.emit(self.current_roi_number, velo_data)
            return

        self.initial_lidar_count = len(lidar_history)

        # Check for immediate match
        if self._check_immediate_match(lidar_history):
            return

        # Start timer for periodic checking
        self.start_time = time.time()
        self.matching_timer.start(100) # Check every 100ms
        
    def _check_immediate_match(self, lidar_history):
        """Check for immediate match in current lidar data."""
        latest_lidar_data = lidar_history[-1]
        latest_lidar_timestamp = latest_lidar_data[0][2][:8]  # Extract HH:MM:SS
        
        # Scenario 1: Exact match
        if self.target_timestamp == latest_lidar_timestamp:
            self.match_found.emit(self.roi, self.current_velo_data, latest_lidar_data, self.index)
            return True
            
        # Scenario 2: Lidar timestamp is later - search backwards
        elif latest_lidar_timestamp > self.target_timestamp:
            for lidar_data in reversed(lidar_history):
                lidar_ts = lidar_data[2][:8]
                if lidar_ts == self.target_timestamp:
                    self.match_found.emit(self.roi, self.current_velo_data, latest_lidar_data, self.index)
                    return True
                elif lidar_ts < self.target_timestamp:
                    break

            # No match found in history
            self.match_failed.emit(self.roi, self.current_velo_data, self.index)
            return True
            
        # Scenario 3: Lidar timestamp is earlier - need to wait
        return False
        
    def _check_for_match(self):
        """Periodic check for new lidar data during waiting period."""
        import time
        
        # Check timeout
        if time.time() - self.start_time > self.max_wait_time:
            self.matching_timer.stop()
            self.match_failed.emit(self.roi, self.current_velo_data, self.index)
            return
            
        # Check for new lidar data
        current_lidar_history = self.lidar_data_processor.reading_history_av1s
        if len(current_lidar_history) > self.initial_lidar_count:
            # New data arrived
            new_latest_data = current_lidar_history[-1]
            new_latest_timestamp = new_latest_data[0][2][:8]
            
            if new_latest_timestamp == self.target_timestamp:
                self.matching_timer.stop()
                self.match_found.emit(self.roi, self.current_velo_data, new_latest_data, self.index)
            elif new_latest_timestamp > self.target_timestamp:
                # Timestamp jumped past target
                self.matching_timer.stop()
                self.match_failed.emit(self.roi, self.current_velo_data, self.index)
            
            # Update count for next iteration
            self.initial_lidar_count = len(current_lidar_history)
    
    def stop_matching(self):
        """Stop the matching timer if it's running."""
        if self.matching_timer.isActive():
            self.matching_timer.stop() 
