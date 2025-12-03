# Import MainGUIWindow at the beginning
from froth_monitor.handlers.gui_window import MainGUIWindow
from froth_monitor.handlers.logger_config import get_logger

# Initialize logger for this module
logger = get_logger(__name__)

class AirRecoveryHandler:
    """Handler for air recovery functionality."""
    
    def __init__(self, air_recovery_data_processor, gui: MainGUIWindow, event_handler):
        self.air_recovery_data_processor = air_recovery_data_processor

        self.gui = gui
        self.gui.apply_flow_btn.clicked.connect(self.apply_main_flow_changes)

        self.event_handler = event_handler

    def main_gui_show_air_flow_rate(self):

        if self.air_recovery_data_processor.use_jg_calculation:
            logger.info("JG method is used.")
            self.gui.show_air_flow_control_panel(event = "jg_method")
            self.gui.main_jg_spin.setValue(self.air_recovery_data_processor.jg_value)
        else:
            logger.info("Direct air flow method is used")
            logger.info(f'Air flow unit is {self.air_recovery_data_processor.air_flow_unit}')
            self.gui.show_air_flow_control_panel(event = "normal_method")
            self.gui.main_flow_rate_spin.setValue(self.air_recovery_data_processor.air_flow_rate)
            self.gui.main_flow_unit_label.setText(self.air_recovery_data_processor.air_flow_unit)
    
    def apply_main_flow_changes(self):
        
        if self.air_recovery_data_processor.use_jg_calculation:
            self.air_recovery_data_processor.jg_value = self.gui.main_jg_spin.value()
        else:
            self.air_recovery_data_processor.air_flow_rate = self.gui.main_flow_rate_spin.value()

    def open_air_recovery_control(self):
        """Open the air recovery control dialog."""
        try:
            from froth_monitor.air_recovery.air_recovery_control_dialog import AirRecoveryControlDialog
            dialog = AirRecoveryControlDialog(self.air_recovery_data_processor, self.gui)
            dialog.configuration_lock.connect(self.main_gui_show_air_flow_rate)
            dialog.show()

        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(
                self.gui,
                "Error",
                f"Failed to open air recovery control dialog: {str(e)}"
            )
            logger.error(f"Error opening air recovery control dialog: {e}")
