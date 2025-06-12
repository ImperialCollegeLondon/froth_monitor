"""Export Module for Froth Tracker Application.

This module defines the `Export` class, which provides functionality for
configuring export settings, collecting ROI data, and saving results to an
Excel file. The module also supports recording video settings and exporting
videos to specified directories.

Classes:
--------
Export
    Handles export configuration, data collection, and file writing for
    ROI analysis and video recording.

Imports:
--------
- PySide6.QtWidgets:
    Provides GUI components such as QDialog, QPushButton, QLineEdit, QLabel, and QCheckBox.
- PySide6.QtCore:
    Core functionality for Qt, including Qt constants.
- PySide6.QtGui:
    Provides GUI components such as QFont.
- numpy:
    For mathematical computations.
- datetime:
    For timestamp generation and date manipulation.
- openpyxl.Workbook:
    For creating and saving Excel files.
"""

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
from PySide6.QtGui import QFont
from datetime import datetime
from openpyxl import Workbook


class Export(QFileDialog):
    """
    Export Class for Managing Data and Video Export Settings.

    The `Export` class provides methods for configuring export settings,
    collecting data from Regions of Interest (ROIs), and saving the data to
    Excel files. Additionally, it supports settings for video recording,
    including specifying directories and filenames for video export.

    Attributes:
    ----------
    parent : object
        The parent widget or object for dialog windows.
    export_directory : str
        Directory path for saving data export files.
    video_directory : str
        Directory path for saving recorded video files.
    export_filename : str
        Default filename for exported data, based on the current date.
    video_filename : str
        Default filename for recorded video, based on the current date.
    velocity_sum : float
        Temporary sum of velocities for calculating averages.
    save_video_in_same_dir : bool
        Indicates whether to save video files in the same directory as data files.
    record_video : bool
        Indicates whether video recording is enabled.
    font_big : QFont
        Font used for larger text elements in the export settings dialog.
    font_small : QFont
        Font used for smaller text elements in the export settings dialog.

    Methods:
    -------
    __init__(parent: object = None) -> None
        Initializes the Export class with default settings.
    export_setting_window() -> None
        Opens a dialog window for configuring export and video recording settings.
    add_video_selection_section(layout: QVBoxLayout, dialog: QDialog) -> None
        Adds video recording configuration options to the export settings dialog.
    enable_video_recording(if_record_video: bool) -> None
        Enables or disables video recording.
    select_video_directory(parent_dialog: object) -> None
        Opens a file dialog to select the directory for saving recorded videos.
    select_data_directory(parent_dialog: object) -> None
        Opens a file dialog to select the directory for saving data files.
    save_export_settings(dialog: QDialog, filename_input: QLineEdit) -> None
        Saves the configured export and video recording settings.
    excel_resutls(rois: list, arrow_angle: float) -> None
        Exports ROI analysis results to an Excel file.
    collect_export_data(rois: list, arrow_angle: float) -> dict
        Collects and structures export data, including ROI movement data and arrow direction.
    get_average_velocity(velocity: float, frame_count: int, timestamp: str) -> tuple
        Calculates the average velocity over 15 frames based on the given velocity and timestamps.
    write_csv(file_path: str, data: dict) -> None
        Writes the export data to an Excel file with separate sheets for each ROI.
    """

    def __init__(self, gui) -> None:
        """
        Initializes the Export class with default settings.

        Args:
            parent (object, optional): The parent widget or object for dialog windows. Defaults to None.

        Attributes:
            export_directory (str): Directory path for data export.
            video_directory (str): Directory path for video export.
            export_filename (str): Default export filename based on the current date.
            video_filename (str): Default video filename based on the current date.
            velocity_sum (float): Sum of velocities, initialized to 0.0.
            save_video_in_same_dir (bool): Flag indicating whether to save video in the same directory as data.
            record_video (bool): Flag indicating whether video recording is enabled.
            font_big (QFont): Font used for larger text elements.
            font_small (QFont): Font used for smaller text elements.
        """
        self.gui: QMainWindow = gui
        self.export_directory = ""
        self.video_directory = ""
        self.export_filename = datetime.now().strftime("%Y%m%d")
        self.video_filename = datetime.now().strftime("%Y%m%d")
        self.velocity_sum = 0.0

        self.save_video_in_same_dir = True
        self.record_video = True
        self.finish_save_setting = False

        self.font_big = QFont("Arial", 13)
        self.font_small = QFont("Arial", 12)

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
            "Would you like to save the recording video in the same directory?"
        )
        video_label.setFont(self.font_big)
        layout.addWidget(video_label)

        # Create radio buttons
        yes_radio = QRadioButton("Yes (Enable video recording)")
        no_radio = QRadioButton("No")
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

    def enable_video_recording(self, if_record_video: bool) -> None:
        """
        Enables or disables video recording.

        Args:
            if_record_video (bool): Flag indicating whether to enable video recording.
        """
        self.record_video = if_record_video
        print("if record video:", self.record_video)

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
                print(self.video_directory)
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
        dialog.accept()

    def excel_results(self, rois: list, arrow_angle: float, px2mm: float) -> bool:
        """
        Handles exporting data for the program.
        """
        try:
            # Check if export directory and filename are set
            if not self.export_directory or not self.export_filename:
                QMessageBox.warning(
                    self.gui,
                    "Export Error",
                    "Please configure export settings before exporting.",
                )
                return False

            # Prepare the full file path
            file_path_csv = f"{self.export_directory}/{self.export_filename}.csv"

            # Step 1: Collect data
            export_data = self.collect_export_data(rois, arrow_angle, px2mm)

            # Step 2: Write to both CSV and JSON
            self.write_csv(file_path_csv, export_data)

            QMessageBox.information(
                self.gui,
                "Export Successful",
                f"Data successfully exported:\n- CSV: {file_path_csv}\n-",
            )
            return True

        except Exception as e:
            QMessageBox.critical(
                self.gui, "Export Failed", f"An error occurred during export: {e}"
            )
            return False

    def collect_export_data(self, rois: list, arrow_angle: float, px2mm: float) -> dict:
        """
        Collects and structures export data from the given regions of interest (ROIs).

        This function processes the ROI data by iterating over each ROI and its frame
        data, calculating the average velocity, and organizing the information into
        a structured dictionary format. The arrow direction is converted from radians
        to degrees and included in the export data.

        Args:
            rois (list): A list of ROIs, each containing an analysis module with
                frame-level results including velocity and timestamp.
            arrow_angle (float): The direction of the arrow in radians.

        Returns:
            dict: A dictionary containing the arrow direction in degrees and an
            organized list of ROI data with movement data, including frame index,
            velocity, timestamp, and average velocity.
        """

        data = {
            "Arrow Direction": arrow_angle,  # Convert to degrees
            "Pixels per mm": px2mm,
            "roi_data": [],
        }

        for i, roi in enumerate(rois):
            roi_data = {
                "ROI Index": i + 1,
                "Movement Data": [],
            }

            for frame_index, frame_data in enumerate(roi.delta_history):
                timestamp = frame_data[0]
                delta_pixels = frame_data[1]
                calibrated_delta = frame_data[2]
                velocity = frame_data[3]

                # print("frame_index: ", frame_index + 1)
                # print("delta_pixels: ", delta_pixels)
                # print("calibrated_delta: ", calibrated_delta)  # Print the calibrated_delta element
                # print("Velocity: ", velocity)
                # print("timestamp: ", timestamp)
                # print("\n")

                roi_data["Movement Data"].append(
                    {
                        "Frame Index": frame_index + 1,
                        "Timestamp": timestamp,
                        "delta_pixels_x(px/frame)": delta_pixels[0],
                        "delta_pixels_y(px/frame)": delta_pixels[1],
                        "calibrated_delta(px/frame)": calibrated_delta,
                        "Velocity(mm/s)": velocity,
                    }
                )

            data["roi_data"].append(roi_data)

        return data

    def write_csv(self, file_path: str, data: dict) -> None:
        """
        Writes the export data to an Excel file, with each ROI in a separate sheet.
        """

        wb = Workbook()

        # Add the arrow direction in the first sheet
        # arrow_sheet = wb.active
        first_sheet = wb.active

        first_sheet.title = "Calibration Data"  # pyright: ignore
        first_sheet.append(["Arrow Direction"])  # pyright: ignore
        first_sheet.append([data["Arrow Direction"]])  # pyright: ignore
        first_sheet.append(["Pixels per mm"])  # pyright: ignore
        first_sheet.append([data["Pixels per mm"]])  # pyright: ignore

        # Create separate sheets for each ROI
        for roi in data["roi_data"]:
            sheet_name = f"ROI {roi['ROI Index']}"
            ws = wb.create_sheet(title=sheet_name)

            # Add headers
            ws.append(
                [
                    "Frame Index",
                    "Timestamp",
                    "delta_pixels_x(px/frame)",
                    "delta_pixels_y(px/frame)",
                    "calibrated_delta(px/frame)",
                    "Velocity(mm/s)",
                ]
            )

            # Add movement data
            for movement in roi["Movement Data"]:
                ws.append(
                    [
                        movement["Frame Index"],
                        movement["Timestamp"],
                        movement["delta_pixels_x(px/frame)"],
                        movement["delta_pixels_y(px/frame)"],
                        movement["calibrated_delta(px/frame)"],
                        movement["Velocity(mm/s)"],
                    ]
                )

        # Save the workbook
        wb.save(file_path)
