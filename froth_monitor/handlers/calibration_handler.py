from typing import cast
from PySide6.QtWidgets import (
    QMessageBox,
)
from PySide6.QtCore import QObject, Signal

# Import MainGUIWindow at the beginning
from froth_monitor.handlers.realtime_export import RealtimeExporter
from froth_monitor.handlers.logger_config import get_logger

# Initialize logger for this module
logger = get_logger(__name__)


class CalibrationHandler(QObject):
    """Handles ruler calibration and arrow direction setup."""

    calibration_confirmed = Signal()
    def __init__(self, gui, frame_model, overlay_widget):
        super().__init__()
        self.gui = gui
        self.frame_model = frame_model
        self.overlay_widget = overlay_widget
        self.confirm_calibration = False
        self.exporter = cast(RealtimeExporter, None)

    # ------------------------------------Ruler Drawing------------------------------------------------
    def start_ruler_calibration(self):
        """Start the ruler calibration mode for measuring distances in pixels."""

        if self.confirm_calibration:
            QMessageBox.warning(
                self.gui,
                "Warning",
                "You have already confirmed the arrow and ruler. Please reset the application if you want to change them.",
            )
            return
        # Start ruler calibration mode
        self.overlay_widget.ruler_calibration()

        # Inform the user
        self.gui.statusBar().showMessage(
            "Click and drag to draw a line of 2cm for pixel measurement"
        )

    def handle_ruler_measurement(self, px):
        """Handle the ruler measurement result.

        Args:
            distance: The measured distance in pixels
        """
        distance = self.gui.px2mm_spinbox.value()
        px_ratio = float(px / distance)

        self.frame_model.get_px_to_mm(px_ratio)
        self.gui.px2mm_result_textbox.setText(f"{self.frame_model.px2mm:.1f}")
        # Display the measurement result to the user
        QMessageBox.information(
            self.gui,
            "Ruler Calibration",
            f"Px to mm ratio: {self.frame_model.px2mm:.1f} per mm",
        )

        # Update the status bar
        self.gui.statusBar().showMessage(
            f"Px to mm ratio: {self.frame_model.px2mm:.1f} per mm"
        )

        # You could store this calibration value for future use if needed
        # self.calibration_value = distance

    # ------------------------------------Arrow Drawing------------------------------------------------
    def confirm_arrow_n_ruler(self):
        """Confirm the current arrow direction."""

        if self.frame_model.px2mm is None:
            QMessageBox.warning(
                self.gui, "Warning", "Please calibrate the ruler first."
            )
            return

        try:
            arrow_direction = float(self.gui.direction_textbox.text())
            px_distance = float(self.gui.px2mm_result_textbox.text())
            self.frame_model.get_px_to_mm(px_distance)
            self.frame_model.get_overflow_direction(arrow_direction)


        except ValueError:
            print(ValueError)
            QMessageBox.warning(
                self.gui,
                "Warning",
                "Please enter valid arrow direction and px2mm values.",
            )
            return

        self.confirm_calibration = True
        self.calibration_confirmed.emit()
        QMessageBox.information(
            self.gui,
            "Info",
            "Overflow direction (arrow) and calibration (ruler) confirmed.",
        )
        self.write_data_to_exporter(arrow_direction, px_distance)

    def start_arrow_drawing(self):
        """Start the arrow drawing mode."""

        if self.confirm_calibration:
            QMessageBox.warning(
                self.gui,
                "Warning",
                "You have already confirmed the arrow and ruler. Please reset the application if you want to change them.",
            )
            return

        # Start ruler calibration mode
        self.overlay_widget.start_arrow_drawing()

        # Inform the user
        self.gui.statusBar().showMessage(
            "Click and drag to draw a line of 2cm for pixel measurement"
        )

    def handle_arrow_drawing(self, start_pos, end_pos, degree):
        # Placeholder for arrow drawing result handling
        """Handle the ruler measurement result.

        Args:
            distance: The measured distance in pixels
        """

        self.frame_model.get_overflow_direction(degree)
        self.gui.direction_textbox.setText(f"{degree:.2f}")

        # Display the measurement result to the user
        QMessageBox.information(
            self.gui,
            "Arrow drawed",
            f"angle: {degree:.1f} degrees (from the horizontal axis anticlockwisely)",
        )

        # Update the status bar
        self.gui.statusBar().showMessage(f"arrow angle: {degree:.1f} degrees")

    # -----------------------------------Exporter Setting----------------------------------------------
    def load_exporter(self, exporter: RealtimeExporter):
        self.exporter = exporter

        if self.confirm_calibration == True:
            self.exporter.write_calibration_data(self.frame_model.degree, self.frame_model.px2mm)

    def write_data_to_exporter(self, degree, px2mm):
        if self.exporter is not None:
            self.exporter.write_calibration_data(degree, px2mm)
