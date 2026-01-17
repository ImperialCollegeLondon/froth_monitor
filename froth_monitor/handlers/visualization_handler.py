from PySide6.QtCore import QObject, Slot
from PySide6.QtWidgets import QTableWidgetItem
import numpy as np
import logging

from froth_monitor.handlers.gui_window import MainGUIWindow
from froth_monitor.processing.roi import ROI
from froth_monitor.utils.performance_monitor import PerformanceMonitor

logger = logging.getLogger(__name__)

class CompatibleTableWidgetItem(QTableWidgetItem):
    """Helper class to silence pyqtgraph's TableWidget AttributeError."""
    def itemChanged(self):
        """No-op method to satisfy pyqtgraph's internal signal handling."""
        pass

class PlotHelper:
    """Helper class to consolidate repetitive plotting logic."""
    
    @staticmethod
    def update_plot_widget(widget, series_list: list[dict], window_size=30, y_range_padding=1.1, y_axis_label=""):
        """
        Update a plot widget with multiple data series.
        """
        widget.clear()
        
        if not series_list:
            return

        all_values = []
        max_val = 0
        
        # Collect all valid data to determine ranges
        processed_series = []
        
        for series in series_list:
            raw_data = series.get('data', [])
            if not raw_data:
                continue
                
            # Sanitize data
            sanitized = []
            for value in raw_data:
                if value is not None and np.isfinite(value) and abs(value) < 1e6:
                    sanitized.append(value)
                else:
                    sanitized.append(0.0)
            
            # Trim to window size
            history_length = len(sanitized)
            if history_length > window_size:
                sanitized = sanitized[-window_size:]
                
            processed_series.append({
                'data': sanitized,
                'color': series.get('color', 'w'),
                'name': series.get('name', ''),
                'full_len': history_length # Original length before trimming
            })
            all_values.extend(sanitized)

        if not processed_series:
            return

        if all_values:
            max_val = max(all_values)

        # Plotting Logic
        # See DataHandler for original comments regarding scrolling logic
        max_full_len = max((s['full_len'] for s in processed_series), default=0)
        
        # Determine strict X-window
        x_max = max_full_len - 1
        x_min = x_max - window_size + 1
        
        for p_series in processed_series:
            data = p_series['data']
            length = len(data)
            # full_len = p_series['full_len']
            
            # Align the last element to x_max (right alignment)
            # This ensures that if series B is shorter than A (started later), 
            # its latest point still aligns with A's latest point.
            start_pos = x_max - length + 1
            x_data = [start_pos + j for j in range(length)]
            
            if data:
                widget.plot(x_data, data, pen=p_series['color'], name=p_series['name'])
                
        widget.setXRange(x_min, x_max)
        
        if max_val > 0 and np.isfinite(max_val):
            widget.setYRange(0, max_val * y_range_padding)
            
        widget.update()

class VisualizationHandler(QObject):
    """
    Handles all GUI updates for the Froth Monitor.
    Listens to signals from DataCoordinator and Processors.
    """
    
    def __init__(self, gui: MainGUIWindow):
        super().__init__()
        self.gui = gui
        self.perf_monitor = PerformanceMonitor()
        
        # Initialize table headers once
        self.gui.velo_widget.setHorizontalHeaderLabels([
            "timestamp", "v(mm/s)", "f_height(mm)", "air_rec(%)"
        ])

    @Slot(list)
    def update_velocity_plot(self, roi_list: list[ROI]):
        """Update the velocity plot with data from all ROIs."""
        # logger.debug("VisualizationHandler: Updating velocity plot")
        self.perf_monitor.stop_timer("receive_plot_signal")
        
        if not roi_list:
            self.gui.plot_widget.clear()
            return
        
        colors = ["r", "g", "b", "c", "m", "y", "w"]
        series_list = []
        
        for i, roi in enumerate(roi_list):
            if not roi.velo_only_history_for_display:
                continue
                
            series_list.append({
                'data': roi.velo_only_history_for_display,
                'color': colors[i % len(colors)],
                'name': f"ROI {i + 1}"
            })
            
        PlotHelper.update_plot_widget(self.gui.plot_widget, series_list)

    @Slot(list)
    def update_fh_plot(self, lidar_reading_history):
        """Update the froth height (lidar) plot."""
        # logger.debug("VisualizationHandler: Updating froth height plot")
        
        if not lidar_reading_history:
            self.gui.froth_height_plot_widget.clear()
            return

        series_list = [{
            'data': lidar_reading_history,
            'color': 'b',
            'name': 'froth height'
        }]
        
        PlotHelper.update_plot_widget(self.gui.froth_height_plot_widget, series_list)

    @Slot()
    def update_arec_display(self, roi_list: list[ROI]):
        """Update Air Recovery table and plot."""
        # logger.debug("VisualizationHandler: Updating Air Recovery display")
        
        self._update_arec_table(roi_list)
        self._update_arec_plot(roi_list)

    def _update_arec_table(self, roi_list: list[ROI]):
        table_list_data = []

        if not roi_list:
            return

        for i, roi in enumerate(roi_list):
            if len(roi.sum_history) == 0:
                continue

            # Expecting sum_history format: [timestamp, velocity, froth_height, air_rec, ...]
            timestamp = roi.sum_history[-1][0][:8]
            list_data_a = roi.sum_history[-1][1:4]
            table_list_data.append([timestamp] + list_data_a)

        # Update table rows without clearing headers
        self.gui.velo_widget.setRowCount(len(table_list_data))
        
        for row, row_data in enumerate(table_list_data):
            for col, value in enumerate(row_data):
                # Format floats
                if isinstance(value, float):
                    text = f"{value:.1f}"
                else:
                    text = str(value)
                
                item = CompatibleTableWidgetItem(text)
                self.gui.velo_widget.setItem(row, col, item)
        
    def _update_arec_plot(self, roi_list: list[ROI]):
        if not roi_list:
            self.gui.ar_plot_widget.clear()
            return

        colors = ["r", "g", "b", "c", "m", "y", "w"]
        series_list = []

        for i, roi in enumerate(roi_list):
            if not roi.sum_history_for_display:
                continue

            # Extract air recovery (index 3)
            ar_history = []
            for entry in roi.sum_history_for_display:
                if len(entry) > 3:
                     ar_history.append(entry[3])
                else:
                    ar_history.append(0.0)

            series_list.append({
                'data': ar_history,
                'color': colors[i % len(colors)],
                'name': f"ROI {i + 1}"
            })

        PlotHelper.update_plot_widget(self.gui.ar_plot_widget, series_list)

    def clear_display(self):
        """Clear all plots and tables."""
        self.gui.froth_height_plot_widget.clear()
        self.gui.ar_plot_widget.clear()
        self.gui.plot_widget.clear()