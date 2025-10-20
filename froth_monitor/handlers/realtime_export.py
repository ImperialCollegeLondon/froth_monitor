import csv
import threading
import queue
import time
from PySide6.QtWidgets import (
    QMainWindow,
    QPushButton,
    QLabel,
    QVBoxLayout,
    QMessageBox,
    QDialog,
    QLineEdit,
    QHBoxLayout,
    QFileDialog,
    QRadioButton,
    QFrame,
)
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QFont
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Set, cast
from openpyxl import Workbook
from openpyxl.utils import get_column_letter
from openpyxl.styles import Font, PatternFill

import time

import logging
logger = logging.getLogger(__name__)

class RealtimeExporter(QFileDialog):
    """
    Real-time data export module that handles concurrent data writing
    to different sheets in a single Excel file with dynamic ROI sheet management
    """
    setting_finished = Signal()

    def __init__(self, gui):
        super().__init__()
        self.gui = gui
        self.font_big = QFont("Arial", 13)
        self.font_small = QFont("Arial", 12)
        self.export_directory = ""
        self.video_directory = ""
        self.export_filename = datetime.now().strftime("%Y%m%d")
        self.video_filename = datetime.now().strftime("%Y%m%d")
        self.save_video_in_same_dir = True
        self.record_video = True
        self.finish_save_setting = False

        # Thread-safe queues for different data types
        self.calibration_queue = queue.Queue()
        self.lidar_queue = queue.Queue()
        self.roi_queues = {}  # Dictionary to store queues for each ROI
        
        # Configurable write interval (seconds)
        self.write_interval = 5.0  # Write to Excel every 5 seconds
        
        # Excel workbook and worksheets
        self.workbook = cast(Workbook, None)
        self.worksheets = {}
        self.row_counters = {}  # Track current row for each sheet
        self.excel_file_path = cast(str, None)
        
        # Threading control
        self.writer_thread = None
        self.is_running = False
        self.lock = threading.Lock()
        
        # Session info
        self.session_id = None
        self.start_time = None
        
        # Track active ROIs
        self.active_rois: Set[int] = set()
        
        # Base sheet configurations
        self.base_sheet_configs = {
            "calibration_data": {
                "headers": ["Arrow Direction", "Pixels per mm"],
                "queue": "calibration_queue"
            },
            "lidar_data": {
                "headers": ["timestamp", "raw_reading(mm)", "calibrated_reading(mm)"],
                "queue": "lidar_queue"
            }
        }
        
        # ROI sheet configurations
        self.roi_movement_headers = [
            "timestamp", "delta_pixels_x(px/frame)", 
            "delta_pixels_y(px/frame)", "calibrated_delta(px/frame)"
        ]
        
        self.roi_summary_headers = [
            "timestamp", "velocity(mm/s)", "froth_height(mm)", "air_recovery(%)", 
            "air_flow_Jg(cm/s)", "air_flow_rate(L/min)"
        ]

    def add_video_selection_section(self, layout: QVBoxLayout, dialog: QDialog) -> None:
        """
        Add a section to the dialog that allows the user to select whether to save the video in the same directory as the data.

        The section includes a QLabel, two radio buttons, a checkbox for video recording, a button to set the recording directory, and a QLabel to display the selected recording directory.

        The checkbox for video recording is initially hidden. If the user selects "No" to save the video in the same directory, the checkbox is shown and the value of self.record_video is copied to its state.

        If the checkbox is checked, the button to set the recording directory and the display label are shown. Otherwise, they are hidden.
        """

        def update_ui() -> None:
            """
            Update the UI based on whether the user selected to save the video in the same directory.

            If the user selected "Yes", hide the additional options.
            If the user selected "No", show the additional options and set the "Record Video" checkbox to the current value of self.record_video.
            """
            is_same_dir = yes_radio.isChecked()
            self.save_video_in_same_dir = is_same_dir
            no_radio.setChecked(not is_same_dir)

            if not is_same_dir:
                self.recording_video_directory_button.setVisible(self.record_video)
                recording_video_directory_display.setVisible(self.record_video)

        def on_radio_selection() -> None:
            """
            Handle the event when a radio button is selected.

            If the "Yes" radio button is selected, set save_video_in_same_dir to True.
            If the "No" radio button is selected, set save_video_in_same_dir to False.
            After updating the selection state, invoke the update_ui function to refresh the UI based on the new selection.
            """
            if yes_radio.isChecked():
                self.save_video_in_same_dir = True
                self.recording_video_directory_button.setVisible(False)

            elif no_radio.isChecked():
                self.save_video_in_same_dir = False
            update_ui()

        title_label = QLabel("Video Recording Options")
        title_label.setFont(self.font_big)
        title_label.setStyleSheet(
            "color: black; font-size: 18px; \
            font-weight:bold; border-radius: 4px;"
        )
        layout.addWidget(title_label)

        # Save Recording Video Options
        video_label = QLabel(
            "Save the recording video in the same or a different directory?"
        )
        video_label.setFont(self.font_big)
        layout.addWidget(video_label)

        # Create radio buttons
        yes_radio = QRadioButton("Same directory")
        no_radio = QRadioButton("Different directory")
        video_radio_layout = QHBoxLayout()
        video_radio_layout.addWidget(yes_radio)
        video_radio_layout.addWidget(no_radio)
        layout.addLayout(video_radio_layout)

        # Set initial state
        if self.save_video_in_same_dir:
            yes_radio.setChecked(True)
        else:
            no_radio.setChecked(True)

        # Connect signals to the slots
        yes_radio.toggled.connect(on_radio_selection)
        no_radio.toggled.connect(on_radio_selection)

        self.recording_video_directory_button = QPushButton(
            "Set Export Location for Recording"
        )
        self.recording_video_directory_button.setStyleSheet(
            "\
            QPushButton {\
                background-color: #4285f4; color: white; font-size: 15px; \
            padding: 5px; border-radius: 4px;\
            }\
            QPushButton:hover {\
                background-color: #3367d6;\
            }\
            "
        )
        recording_video_directory_display = QLabel("Not selected", dialog)
        recording_video_directory_display.setObjectName(
            "recording_video_directory_display"
        )

        # recording_video_checkbox.setVisible(False)
        self.recording_video_directory_button.setVisible(False)
        # recording_video_directory_display.setVisible(False)

        # layout.addWidget(recording_video_checkbox)
        layout.addWidget(self.recording_video_directory_button)
        layout.addWidget(recording_video_directory_display)

        self.recording_video_directory_button.clicked.connect(
            lambda: self.select_video_directory(dialog)
        )

        video_filename_label = QLabel("Video Filename (without extension):", dialog)
        video_filename_label.setFont(self.font_big)
        layout.addWidget(video_filename_label)

        video_filename_input = QLineEdit(self.export_filename, dialog)
        video_filename_input.setObjectName("video_filename_input")
        layout.addWidget(video_filename_input)

    def export_setting_window(self) -> None:
        """
        Opens a dialog window to set export settings.

        The dialog window consists of input fields for setting the export directory, export filename,
        and video recording settings. The settings are saved when the user clicks the "Save Settings" button.
        """

        dialog = QDialog(self.gui)
        dialog.setWindowTitle("Export Settings")
        dialog.setMinimumWidth(400)
        layout = QVBoxLayout(dialog)

        # Export Directory Selection
        directory_label = QLabel("Data Export Location:", dialog)
        directory_label.setFont(self.font_big)
        directory_label.setStyleSheet(
            "color: black; font-size: 18px; \
            font-weight:bold; border-radius: 4px;"
        )
        layout.addWidget(directory_label)

        directory_button = QPushButton("Select export location for csv data", dialog)
        directory_button.setStyleSheet(
            """
            QPushButton {
                background-color: #4285f4; color: white; font-size: 15px; \
            padding: 5px; border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #3367d6;
            }
            """
        )
        directory_button.clicked.connect(lambda: self.select_data_directory(dialog))
        layout.addWidget(directory_button)

        # Add QLabel to display the selected directory and set an object name
        directory_display = QLabel(
            self.export_directory if self.export_directory else "Not selected", dialog
        )
        directory_display.setStyleSheet(
            "color: black; font-size: 15px; \
            padding: 5px; border-radius: 4px;"
        )
        directory_display.setObjectName(
            "directory_display"
        )  # Assign a unique name for findChild
        layout.addWidget(directory_display)

        # Export Filename Input
        filename_label = QLabel("CSV Data Filename (without extension):", dialog)
        filename_label.setFont(self.font_big)
        layout.addWidget(filename_label)

        filename_input = QLineEdit(self.export_filename, dialog)
        layout.addWidget(filename_input)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)  # Horizontal line
        separator.setFrameShadow(QFrame.Shadow.Sunken)  # Sunken style
        separator.setFixedHeight(10)  # Set the height of the separator
        layout.addWidget(separator)

        self.add_video_selection_section(layout, dialog)

        # Save Button
        save_button = QPushButton("Save Settings", dialog)
        save_button.setStyleSheet(
            """
            QPushButton {
                background-color: #4285f4; color: white; font-size: 15px; \
            padding: 5px; border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #3367d6;
            }
            """
        )
        save_button.clicked.connect(
            lambda: self.save_export_settings(dialog, filename_input)
        )
        layout.addWidget(save_button)

        dialog.exec()

    def select_video_directory(self, parent_dialog) -> None:
        """
        Opens a file dialog to select the video recording directory.

        Args:
            parent_dialog (object): The parent dialog containing the QLabel to be updated.
        """
        directory = QFileDialog.getExistingDirectory(
            self.gui, "Select Recording Saving Directory"
        )

        if directory:
            self.video_directory = directory
            # Update directory label in the parent dialog
            directory_display = parent_dialog.findChild(
                QLabel, "recording_video_directory_display"
            )
            self.record_video = True
            if directory_display:  # Ensure the QLabel is found
                logger.info(f"Recording video directory set to: {self.video_directory}")
                directory_display.setText(self.video_directory)

    def select_data_directory(self, parent_dialog) -> None:
        """
        Opens a file dialog to select the export directory.
        """
        directory = QFileDialog.getExistingDirectory(
            self.gui, "Select Data Saving Directory"
        )

        if directory:
            self.export_directory = directory

            # Update directory label in the parent dialog
            directory_display = parent_dialog.findChild(QLabel, "directory_display")
            if directory_display:  # Ensure the QLabel is found
                logger.info(f"Export directory set to: {self.export_directory}")
                directory_display.setText(self.export_directory)

    def save_export_settings(self, dialog: QDialog, filename_input: QLineEdit) -> None:
        """
        Saves the export settings.
        """
        # Save the entered filename
        self.export_filename = filename_input.text()

        video_filename_input = dialog.findChild(QLineEdit, "video_filename_input")
        self.video_filename = video_filename_input.text()  # pyright: ignore

        # Display a warning if the directory is not set
        if not self.export_directory:
            QMessageBox.warning(
                self.gui, "Warning", "Data Export directory is not set."
            )
            return

        if self.save_video_in_same_dir and self.record_video:
            self.video_directory = self.export_directory

        # Display a warning if the directory is not set
        if not self.video_directory and self.record_video:
            QMessageBox.warning(
                self.gui, "Warning", "Recoroding Export directory is not set."
            )
            return

        QMessageBox.information(
            self.gui,
            "Settings Saved",
            f"Data export settings saved:\nDirectory: {self.export_directory}\nFilename: {self.export_filename}\
            \n\n\nRecording export settings saved:\nDirectory: {self.video_directory}\nFilename: {self.video_filename}",
        )
        self.finish_save_setting = True

        self.start_session()
        self.setting_finished.emit()
        dialog.accept()

    def start_session(self) -> None:
        """
        Start a new export session with a single Excel file containing base sheets
        
        Parameters
        ----------
        session_name : str, optional
            Custom session name, defaults to timestamp
            
        Returns
        -------
        str
            Session ID for reference
        """
        self.start_time = datetime.now()
    
        
        # Create Excel file path
        self.excel_file_path = f"{self.export_directory}/{self.export_filename}.xlsx"

        
        # Initialize Excel workbook with base sheets
        self._initialize_excel_file()
        
        # Start writer thread
        self.is_running = True
        self.writer_thread = threading.Thread(target=self._writer_worker, daemon=True)
        self.writer_thread.start()
        
        logger.info(f"Started realtime export session: {self.export_filename}")
        logger.info(f"Excel file: {self.excel_file_path}")
    
    def _initialize_excel_file(self):
        """
        Initialize Excel workbook with base sheets (calibration_data and lidar_data)
        """
        self.workbook = Workbook()
        
        # Remove default sheet
        if "Sheet" in self.workbook.sheetnames:
            self.workbook.remove(self.workbook["Sheet"])
        
        # Create base sheets with headers
        for sheet_name, config in self.base_sheet_configs.items():
            worksheet = self.workbook.create_sheet(title=sheet_name)
            self.worksheets[sheet_name] = worksheet
            self.row_counters[sheet_name] = 1
            
            # Add headers with formatting
            headers = config["headers"]
            for col_idx, header in enumerate(headers, 1):
                cell = worksheet.cell(row=1, column=col_idx, value=header)
                cell.font = Font(bold=True)
                cell.fill = PatternFill(start_color="CCCCCC", end_color="CCCCCC", fill_type="solid")
            
            # Auto-adjust column widths
            for col_idx in range(1, len(headers) + 1):
                column_letter = get_column_letter(col_idx)
                worksheet.column_dimensions[column_letter].width = 15
            
            self.row_counters[sheet_name] = 2  # Next row for data
        
        # Save initial file
        self.workbook.save(self.excel_file_path)
        logger.info(f"Initialized Excel file with base sheets: {list(self.base_sheet_configs.keys())}")
    
    def create_roi_sheets(self, roi_id: int) -> bool:
        """
        Create movement and summary sheets for a new ROI
        
        Parameters
        ----------
        roi_id : int
            ID of the ROI to create sheets for
            
        Returns
        -------
        bool
            True if sheets were created successfully
        """
        if not self.is_running or roi_id in self.active_rois:
            return False
        
        with self.lock:
            try:
                # Create movement data sheet
                movement_sheet_name = f"ROI_{roi_id}_movement_data"

                if self.workbook is None:
                    self.workbook = Workbook()

                movement_worksheet = self.workbook.create_sheet(title=movement_sheet_name)
                self.worksheets[movement_sheet_name] = movement_worksheet
                self.row_counters[movement_sheet_name] = 1
                
                # Add headers for movement sheet
                for col_idx, header in enumerate(self.roi_movement_headers, 1):
                    cell = movement_worksheet.cell(row=1, column=col_idx, value=header)
                    cell.font = Font(bold=True)
                    cell.fill = PatternFill(start_color="CCCCCC", end_color="CCCCCC", fill_type="solid")
                
                # Auto-adjust column widths
                for col_idx in range(1, len(self.roi_movement_headers) + 1):
                    column_letter = get_column_letter(col_idx)
                    movement_worksheet.column_dimensions[column_letter].width = 15
                
                self.row_counters[movement_sheet_name] = 2
                
                # Create summary sheet
                summary_sheet_name = f"ROI_{roi_id}_summary"
                summary_worksheet = self.workbook.create_sheet(title=summary_sheet_name)
                self.worksheets[summary_sheet_name] = summary_worksheet
                self.row_counters[summary_sheet_name] = 1
                
                # Add headers for summary sheet
                for col_idx, header in enumerate(self.roi_summary_headers, 1):
                    cell = summary_worksheet.cell(row=1, column=col_idx, value=header)
                    cell.font = Font(bold=True)
                    cell.fill = PatternFill(start_color="CCCCCC", end_color="CCCCCC", fill_type="solid")
                
                # Auto-adjust column widths
                for col_idx in range(1, len(self.roi_summary_headers) + 1):
                    column_letter = get_column_letter(col_idx)
                    summary_worksheet.column_dimensions[column_letter].width = 15
                
                self.row_counters[summary_sheet_name] = 2
                
                # Create queues for this ROI
                self.roi_queues[f"roi_{roi_id}_movement"] = queue.Queue()
                self.roi_queues[f"roi_{roi_id}_summary"] = queue.Queue()
                
                # Add to active ROIs
                self.active_rois.add(roi_id)
                
                # Save workbook
                self.workbook.save(self.excel_file_path)
                
                logger.info(f"Created ROI sheets for ROI {roi_id}: {movement_sheet_name}, {summary_sheet_name}")
                return True
                
            except Exception as e:
                logger.error(f"Error creating ROI sheets for ROI {roi_id}: {e}")
                return False
    
    def delete_roi_sheets(self, roi_id: int) -> bool:
        """
        Delete movement and summary sheets for an ROI
        
        Parameters
        ----------
        roi_id : int
            ID of the ROI to delete sheets for
            
        Returns
        -------
        bool
            True if sheets were deleted successfully
        """
        if not self.is_running or roi_id not in self.active_rois:
            return False
        
        with self.lock:
            try:

                if self.workbook is None:
                    self.workbook = Workbook()

                movement_sheet_name = f"ROI_{roi_id}_movement_data"
                summary_sheet_name = f"ROI_{roi_id}_summary"
                
                # Remove worksheets
                if movement_sheet_name in self.worksheets:
                    self.workbook.remove(self.worksheets[movement_sheet_name])
                    del self.worksheets[movement_sheet_name]
                    del self.row_counters[movement_sheet_name]
                
                if summary_sheet_name in self.worksheets:
                    self.workbook.remove(self.worksheets[summary_sheet_name])
                    del self.worksheets[summary_sheet_name]
                    del self.row_counters[summary_sheet_name]
                
                # Remove queues
                if f"roi_{roi_id}_movement" in self.roi_queues:
                    del self.roi_queues[f"roi_{roi_id}_movement"]
                if f"roi_{roi_id}_summary" in self.roi_queues:
                    del self.roi_queues[f"roi_{roi_id}_summary"]
                
                # Remove from active ROIs
                self.active_rois.discard(roi_id)
                
                # Save workbook
                self.workbook.save(self.excel_file_path)
                
                logger.info(f"Deleted ROI sheets for ROI {roi_id}")
                return True
                
            except Exception as e:
                logger.error(f"Error deleting ROI sheets for ROI {roi_id}: {e}")
                return False
    
    def _writer_worker(self):
        """
        Background thread worker that processes all queues and writes data to Excel sheets
        """
        while self.is_running:
            try:
                # Process base queues
                self._process_queue("calibration_data", self.calibration_queue)
                self._process_queue("lidar_data", self.lidar_queue)
                
                # Process ROI queues
                for queue_name, roi_queue in list(self.roi_queues.items()):
                    if "movement" in queue_name:
                        roi_id = queue_name.split("_")[1]
                        sheet_name = f"ROI_{roi_id}_movement_data"
                        self._process_queue(sheet_name, roi_queue)
                    elif "summary" in queue_name:
                        roi_id = queue_name.split("_")[1]
                        sheet_name = f"ROI_{roi_id}_summary"
                        self._process_queue(sheet_name, roi_queue)
                
                # Sleep for configured interval to reduce Excel save frequency
                time.sleep(self.write_interval)
                
            except Exception as e:
                logger.error(f"Error in writer worker: {e}")
    
    def _process_queue(self, sheet_name: str, data_queue: queue.Queue):
        """
        Process items from a specific queue and write to Excel sheet
        """
        items_processed = 0
        try:
            while True:
                data_row = data_queue.get_nowait()
                
                with self.lock:
                    if sheet_name in self.worksheets:
                        worksheet = self.worksheets[sheet_name]
                        current_row = self.row_counters[sheet_name]
                        
                        # Write data to current row
                        for col_idx, value in enumerate(data_row, 1):
                            worksheet.cell(row=current_row, column=col_idx, value=value)
                        
                        # Increment row counter
                        self.row_counters[sheet_name] += 1
                        items_processed += 1
                
                data_queue.task_done()
                
        except queue.Empty:
            pass  # No more items in queue
        
        # Save file if any items were processed
        if items_processed > 0:
            with self.lock:
                try:
                    self.workbook.save(self.excel_file_path) #type: ignore
                except Exception as e:
                    logger.error(f"Error saving Excel file: {e}")
    
    # ============ INITIALIZE EXPORTER DURING RUN =========
    def initialize_roi_sheets(self, roi_list: list):
        """
        Initialize ROI sheets when the exporter is loaded
        """
        logger.info("Initializing ROI sheets")

        for id, roi in enumerate(roi_list):

            self.create_roi_sheets(roi.id)
            for data in roi.delta_history:
                self.write_roi_movement_data(roi.id, data)
            for data in roi.sum_history:
                self.write_roi_summary_data(roi.id, data)

    # ============ PUBLIC API FUNCTIONS ============
    def write_calibration_data(self, arrow_direction: float, px2mm: float):
        """
        Write calibration data to calibration_data sheet
        """
        if not self.is_running:
            return
            
        data_row = [arrow_direction, px2mm]
        
        try:
            self.calibration_queue.put_nowait(data_row)
        except queue.Full:
            logger.warning("Calibration queue full, dropping data point")
    
    def write_lidar_data(self, timestamp: str, raw_reading: float, calibrated_reading: float):
        """
        Write LIDAR data to lidar_data sheet
        """
        if not self.is_running:
            return
            
        data_row = [timestamp, raw_reading, calibrated_reading]
        
        try:
            self.lidar_queue.put_nowait(data_row)
        except queue.Full:
            logger.warning("LIDAR queue full, dropping data point")
    
    def write_roi_movement_data(self, roi_id: int, frame_data_list: list):

        """
        Write ROI movement data to ROI movement sheet
        """
        if not self.is_running or roi_id not in self.active_rois:
            return

        timestamp = frame_data_list[0]
        delta_pixels_x = frame_data_list[1][0]
        delta_pixels_y = frame_data_list[1][1]
        calibrated_delta = frame_data_list[2]

        data_row = [
            timestamp, 
            delta_pixels_x, 
            delta_pixels_y, 
            calibrated_delta
        ]

        queue_name = f"roi_{roi_id}_movement"
        if queue_name in self.roi_queues:
            try:
                self.roi_queues[queue_name].put_nowait(data_row)
            except queue.Full:
                logger.warning(f"ROI {roi_id} movement queue full, dropping data point")

    def write_roi_summary_data(self, roi_id: int, sum_data_list: list):
        """
        Write ROI summary data to ROI summary sheet
        """
        if not self.is_running or roi_id not in self.active_rois:
            return
        
        # list format
        # timestamp, velocity, froth_height, air_rec, current_air_flow, current_air_flow_in_mm
        data_row = sum_data_list
        
        queue_name = f"roi_{roi_id}_summary"
        if queue_name in self.roi_queues:
            try:
                self.roi_queues[queue_name].put_nowait(data_row)
            except queue.Full:
                logger.warning(f"ROI {roi_id} summary queue full, dropping data point")
    
    def get_active_rois(self) -> Set[int]:
        """
        Get set of currently active ROI IDs
        """
        return self.active_rois.copy()
    
    def get_sheet_info(self) -> Dict[str, Dict[str, Any]]:
        """
        Get information about all sheets
        
        Returns
        -------
        Dict[str, Dict[str, Any]]
            Information about each sheet including row count
        """
        sheet_info = {}
        
        with self.lock:
            for sheet_name, worksheet in self.worksheets.items():
                sheet_info[sheet_name] = {
                    "current_row": self.row_counters.get(sheet_name, 1),
                    "data_rows": max(0, self.row_counters.get(sheet_name, 1) - 2),  # Exclude header
                    "columns": worksheet.max_column
                }
        
        return sheet_info
    
    def stop_session(self):
        """
        Stop the current export session and close Excel file
        """
        if not self.is_running:
            return
            
        self.is_running = False
        
        # Wait for writer thread to finish
        if self.writer_thread and self.writer_thread.is_alive():
            self.writer_thread.join(timeout=5.0)
        
        # Final save and close
        with self.lock:
            try:
                if self.workbook:
                    self.workbook.save(self.excel_file_path)
                    self.workbook.close()
                    
                self.workbook = None
                self.worksheets.clear()
                self.row_counters.clear()
                self.roi_queues.clear()
                self.active_rois.clear()
                
            except Exception as e:
                logger.error(f"Error closing Excel file: {e}")
        
        logger.info(f"Stopped realtime export session: {self.session_id}")
        logger.info(f"Final Excel file saved: {self.excel_file_path}")
        self.session_id = None
    
    def get_session_info(self) -> Dict[str, Any]:
        """
        Get information about the current session
        """
        queue_sizes = {
            "calibration": self.calibration_queue.qsize(),
            "lidar": self.lidar_queue.qsize()
        }
        
        # Add ROI queue sizes
        for queue_name, roi_queue in self.roi_queues.items():
            queue_sizes[queue_name] = roi_queue.qsize()
        
        return {
            "session_id": self.session_id,
            "start_time": self.start_time,
            "is_running": self.is_running,
            "excel_file": str(self.excel_file_path) if self.excel_file_path else None,
            "active_rois": list(self.active_rois),
            "queue_sizes": queue_sizes,
            "sheet_info": self.get_sheet_info()
        }


    # """Get currently active ROI IDs"""
    # return get_realtime_exporter().get_active_rois()