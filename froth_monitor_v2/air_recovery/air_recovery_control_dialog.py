"""Air Recovery Control Dialog for Froth Monitor Application.

This module provides a GUI dialog for controlling air recovery functionality,
including configuration settings, real-time monitoring, and data management.
"""

import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QLineEdit, QSpinBox, QDoubleSpinBox,
    QComboBox, QTextEdit, QGroupBox, QFileDialog,
    QMessageBox, QCheckBox, QRadioButton, QButtonGroup
)
from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import QFont
from froth_monitor.handlers.logger_config import get_logger

# Initialize logger for this module
logger = get_logger(__name__)

class AirRecoveryControlDialog(QDialog):
    """
    Dialog for controlling air recovery functionality in the froth monitor application.
    
    Provides controls for:
    - Configuring cell parameters and air flow settings
    - Monitoring real-time air recovery calculations
    - Viewing statistics and historical data
    - Exporting data
    """
    configuration_lock = Signal()
    configuration_unlock = Signal()

    def __init__(self, air_recovery_data_processor, parent = None):
        """
        Initialize the air recovery control dialog.
        
        Args:
            event_handler: The main event handler instance
            parent: Parent widget
        """
        super().__init__(parent)

        self.air_recovery_processor = air_recovery_data_processor
        
        self.setWindowTitle("Air Recovery Control")
        self.setModal(False)
        self.resize(600, 700)
        
        # Update timer for real-time display
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_display)
        self.update_timer.start(1000)  # Update every second
        
        self.setup_ui()
        self.load_current_configuration()

    def setup_ui(self):
        """
        Set up the user interface.
        """
        self._create_stylesheets()
        
    def _create_stylesheets(self):
        """
        Initialize stylesheets for UI elements to match main GUI.
        """
        # Primary button style (matches main GUI ENABLED_BUTTON_STYLE)
        self.PRIMARY_BUTTON_STYLE = """
            QPushButton {
                background-color: #4285f4;
                color: white;
                font-size: 12px;
                padding: 5px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #3367d6;
            }
        """
        
        # Secondary button style (matches main GUI DISABLED_BUTTON_STYLE)
        self.SECONDARY_BUTTON_STYLE = """
            QPushButton {
                background-color: #808080;
                color: #404040;
                font-size: 12px;
                padding: 5px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #909090;
            }
        """
        
        # Input field style
        self.INPUT_FIELD_STYLE = """
            background-color: white;
            color: black;
            font-size: 12px;
            padding: 5px;
            border-radius: 4px;
            border: 1px solid #ccc;
        """
        
        # Label style for dark backgrounds
        self.DARK_LABEL_STYLE = """
            background-color: #3c4043;
            color: white;
            font-size: 12px;
            font-weight: bold;
            padding: 8px;
            border-radius: 4px;
        """
        
        # ComboBox style
        self.COMBO_BOX_STYLE = """
            QComboBox {
                background-color: #f0f0f0;
                font-size: 12px;
                color: black;
                padding: 5px;
                border-radius: 4px;
                border: 1px solid #ccc;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #666;
                margin-right: 5px;
            }
            QComboBox QAbstractItemView {
                background-color: white;
                color: black;
                selection-background-color: #4285f4;
                selection-color: white;
                border: 1px solid #ccc;
            }
        """

        layout = QVBoxLayout(self)
        
        # Configuration settings group
        config_group = QGroupBox("Configuration Settings")
        config_layout = QGridLayout(config_group)
        
        # Cell perimeter
        config_layout.addWidget(QLabel("Cell Perimeter (mm):"), 0, 0)
        self.perimeter_spin = QDoubleSpinBox()
        self.perimeter_spin.setRange(1.0, 100000.0)
        self.perimeter_spin.setValue(1000.0)
        self.perimeter_spin.setSingleStep(10.0)
        self.perimeter_spin.setStyleSheet(self.INPUT_FIELD_STYLE)
        self.perimeter_spin.valueChanged.connect(self.update_configuration)
        config_layout.addWidget(self.perimeter_spin, 0, 1)
        
        # Air flow calculation method
        config_layout.addWidget(QLabel("Air Flow Method:"), 1, 0)
        self.flow_method_group = QButtonGroup()
        
        self.direct_flow_radio = QRadioButton("Direct Air Flow Rate")
        self.jg_flow_radio = QRadioButton("Jg (Superficial Gas Velocity)")
        
        self.flow_method_group.addButton(self.direct_flow_radio, 0)
        self.flow_method_group.addButton(self.jg_flow_radio, 1)
        self.direct_flow_radio.setChecked(True)
        
        self.direct_flow_radio.toggled.connect(self.on_flow_method_changed)
        self.jg_flow_radio.toggled.connect(self.on_flow_method_changed)
        
        method_layout = QHBoxLayout()
        method_layout.addWidget(self.direct_flow_radio)
        method_layout.addWidget(self.jg_flow_radio)
        config_layout.addLayout(method_layout, 1, 1)
        
        layout.addWidget(config_group)
        
        # Direct air flow settings group
        self.direct_flow_group = QGroupBox("Direct Air Flow Settings")
        direct_layout = QGridLayout(self.direct_flow_group)
        
        # Air flow rate
        direct_layout.addWidget(QLabel("Air Flow Rate:"), 0, 0)
        self.flow_rate_spin = QDoubleSpinBox()
        self.flow_rate_spin.setRange(0.1, 10000.0)
        self.flow_rate_spin.setValue(100.0)
        self.flow_rate_spin.setSingleStep(1.0)
        self.flow_rate_spin.setStyleSheet(self.INPUT_FIELD_STYLE)
        self.flow_rate_spin.valueChanged.connect(self.update_configuration)
        direct_layout.addWidget(self.flow_rate_spin, 0, 1)
        
        # Air flow unit
        direct_layout.addWidget(QLabel("Unit:"), 0, 2)
        self.flow_unit_combo = QComboBox()
        self.flow_unit_combo.addItems(["L/min", "m3/hr", "cm3/s"])
        self.flow_unit_combo.setStyleSheet(self.COMBO_BOX_STYLE)
        self.flow_unit_combo.currentTextChanged.connect(self.update_configuration)
        direct_layout.addWidget(self.flow_unit_combo, 0, 3)
        
        layout.addWidget(self.direct_flow_group)
        
        # Jg settings group
        self.jg_flow_group = QGroupBox("Jg (Superficial Gas Velocity) Settings")
        jg_layout = QGridLayout(self.jg_flow_group)
        
        # Jg value
        jg_layout.addWidget(QLabel("Jg (cm/s):"), 0, 0)
        self.jg_spin = QDoubleSpinBox()
        self.jg_spin.setRange(0.01, 100.0)
        self.jg_spin.setValue(1.0)
        self.jg_spin.setSingleStep(0.1)
        self.jg_spin.setStyleSheet(self.INPUT_FIELD_STYLE)
        self.jg_spin.valueChanged.connect(self.update_configuration)
        jg_layout.addWidget(self.jg_spin, 0, 1)
        
        # Cell area
        jg_layout.addWidget(QLabel("Cell Area (mm²):"), 1, 0)
        self.cell_area_spin = QDoubleSpinBox()
        self.cell_area_spin.setRange(1.0, 1e10)
        self.cell_area_spin.setValue(1000000.0)
        self.cell_area_spin.setSingleStep(1000.0)
        self.cell_area_spin.setStyleSheet(self.INPUT_FIELD_STYLE)
        self.cell_area_spin.valueChanged.connect(self.update_configuration)
        jg_layout.addWidget(self.cell_area_spin, 1, 1)
        
        layout.addWidget(self.jg_flow_group)
        
        # Apply configuration and reset buttons
        apply_layout = QHBoxLayout()
        self.apply_config_btn = QPushButton("Apply Configuration")
        self.apply_config_btn.setStyleSheet(self.PRIMARY_BUTTON_STYLE)
        self.apply_config_btn.clicked.connect(self.apply_configuration)
        apply_layout.addWidget(self.apply_config_btn)
        
        # self.reset_config_btn = QPushButton("Reset Configuration")
        # self.reset_config_btn.setStyleSheet(self.PRIMARY_BUTTON_STYLE)
        # self.reset_config_btn.clicked.connect(self.reset_configuration)
        # apply_layout.addWidget(self.reset_config_btn)
        
        apply_layout.addStretch()
        layout.addLayout(apply_layout)
        
        # Current readings group
        readings_group = QGroupBox("Current Readings")
        readings_layout = QGridLayout(readings_group)
        
        # Current air recovery
        readings_layout.addWidget(QLabel("Air Recovery:"), 0, 0)
        self.air_recovery_label = QLabel("-- %")
        font = QFont()
        font.setPointSize(14)
        font.setBold(True)
        self.air_recovery_label.setFont(font)
        self.air_recovery_label.setStyleSheet("color: blue;")
        readings_layout.addWidget(self.air_recovery_label, 0, 1)
        
        # Current velocity
        readings_layout.addWidget(QLabel("Velocity:"), 1, 0)
        self.velocity_label = QLabel("-- mm/s")
        readings_layout.addWidget(self.velocity_label, 1, 1)
        
        # Current froth height
        readings_layout.addWidget(QLabel("Froth Height:"), 2, 0)
        self.froth_height_label = QLabel("-- mm")
        readings_layout.addWidget(self.froth_height_label, 2, 1)
        
        # Data count
        readings_layout.addWidget(QLabel("Calculations Count:"), 3, 0)
        self.count_label = QLabel("0")
        readings_layout.addWidget(self.count_label, 3, 1)
        
        layout.addWidget(readings_group)
        
        # Statistics group
        stats_group = QGroupBox("Statistics")
        stats_layout = QGridLayout(stats_group)
        
        self.stats_text = QTextEdit()
        self.stats_text.setMaximumHeight(150)
        self.stats_text.setReadOnly(True)
        self.stats_text.setStyleSheet(self.INPUT_FIELD_STYLE)
        stats_layout.addWidget(self.stats_text, 0, 0, 1, 2)
        
        layout.addWidget(stats_group)
        
        # Data management buttons
        data_layout = QHBoxLayout()
        
        self.export_btn = QPushButton("Export Data")
        self.export_btn.setStyleSheet(self.PRIMARY_BUTTON_STYLE)
        self.export_btn.clicked.connect(self.export_data)
        data_layout.addWidget(self.export_btn)
        
        self.clear_btn = QPushButton("Clear Data")
        self.clear_btn.setStyleSheet(self.PRIMARY_BUTTON_STYLE)
        self.clear_btn.clicked.connect(self.clear_data)
        data_layout.addWidget(self.clear_btn)
        
        layout.addLayout(data_layout)
        
        # Close button
        close_layout = QHBoxLayout()
        close_layout.addStretch()
        
        self.close_btn = QPushButton("Close")
        self.close_btn.setStyleSheet(self.PRIMARY_BUTTON_STYLE)
        self.close_btn.clicked.connect(self.close)
        close_layout.addWidget(self.close_btn)
        
        layout.addLayout(close_layout)
        
        # Initially hide Jg settings
        self.jg_flow_group.setVisible(False)

    def on_flow_method_changed(self):
        """
        Handle air flow calculation method change.
        """
        use_jg = self.jg_flow_radio.isChecked()
        
        self.direct_flow_group.setVisible(not use_jg)
        self.jg_flow_group.setVisible(use_jg)
        
        self.update_configuration()

    def load_current_configuration(self):
        """
        Load current configuration from the air recovery processor.
        """
        try:
            config = self.air_recovery_processor.get_configuration()
            
            # Load basic settings
            self.perimeter_spin.setValue(config.get('cell_perimeter', 1000.0))
            
            # Load air flow settings
            if config.get('use_jg_calculation', False):
                self.jg_flow_radio.setChecked(True)
                self.jg_spin.setValue(config.get('jg_value', 1.0))
                self.cell_area_spin.setValue(config.get('cell_area', 1000000.0))
            else:
                self.direct_flow_radio.setChecked(True)
                self.flow_rate_spin.setValue(config.get('air_flow_rate', 100.0))
                unit = config.get('air_flow_unit', 'L/min')
                index = self.flow_unit_combo.findText(unit)
                if index >= 0:
                    self.flow_unit_combo.setCurrentIndex(index)
            
            self.on_flow_method_changed()
            
            # Update UI based on configuration lock state
            if config.get('configuration_locked', False):
                self.update_ui_for_locked_state()
            else:
                self.update_ui_for_unlocked_state()
            
        except Exception as e:
            logger.error(f"Error loading air recovery configuration: {e}")

    def update_configuration(self):
        """
        Update configuration values (called when UI elements change).
        Note: This doesn't apply the configuration, just updates the UI state.
        """
        # This method is called when spinboxes change
        # The actual application happens when Apply button is clicked
        pass

    def apply_configuration(self):
        """
        Apply the current configuration to the air recovery processor.
        """
        try:
            # Apply cell perimeter
            self.air_recovery_processor.set_cell_perimeter(self.perimeter_spin.value())
            
            # Apply air flow settings
            if self.jg_flow_radio.isChecked():
                self.air_recovery_processor.set_jg_parameters(
                    self.jg_spin.value(),
                    self.cell_area_spin.value()
                )
            else:
                self.air_recovery_processor.set_air_flow_rate(
                    self.flow_rate_spin.value(),
                    self.flow_unit_combo.currentText()
                )
            
            # Lock configuration after first application
            self.air_recovery_processor.lock_configuration()
            
            # Update GUI to reflect locked state
            self.update_ui_for_locked_state()
            
            QMessageBox.information(
                self,
                "Configuration Applied",
                "Air recovery configuration has been successfully applied.\n"
                "The air flow control panel is now available in the main window."
            )
            
        except Exception as e:
            QMessageBox.warning(
                self,
                "Configuration Error",
                f"Failed to apply configuration: {str(e)}"
            )
            logger.error(f"Error applying air recovery configuration: {e}")
            
    def reset_configuration(self):
        """
        Reset the air recovery configuration to defaults.
        """
        reply = QMessageBox.question(
            self,
            "Confirm Reset",
            "Are you sure you want to reset the air recovery configuration?\n"
            "This will unlock the settings and restore default values.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                # Reset processor configuration
                self.air_recovery_processor.reset_configuration()
                
                # Reload default values in UI
                self.load_current_configuration()
                
                # Update UI to reflect unlocked state
                self.update_ui_for_unlocked_state()
                
                QMessageBox.information(
                    self,
                    "Configuration Reset",
                    "Air recovery configuration has been reset to defaults."
                )
                
            except Exception as e:
                QMessageBox.warning(
                    self,
                    "Reset Error",
                    f"Failed to reset configuration: {str(e)}"
                )
                logger.error(f"Error resetting air recovery configuration: {e}")
                
    def update_ui_for_locked_state(self):
        """
        Update UI elements to reflect locked configuration state.
        """
        self.configuration_lock.emit()
        
    def update_ui_for_unlocked_state(self):
        """
        Update UI elements to reflect unlocked configuration state.
        """
        # Enable flow method radio buttons
        self.configuration_unlock.emit()

    def export_data(self):
        """
        Export air recovery data to a file.
        """
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export Air Recovery Data",
            "air_recovery_data.csv",
            "CSV Files (*.csv);;All Files (*)"
        )
        
        if filename:
            success = self.air_recovery_processor.export_data(filename)
            if success:
                QMessageBox.information(
                    self,
                    "Export Successful",
                    f"Air recovery data exported to {filename}"
                )
            else:
                QMessageBox.warning(
                    self,
                    "Export Failed",
                    "Failed to export air recovery data. Check the log for details."
                )

    def clear_data(self):
        """
        Clear all air recovery data.
        """
        reply = QMessageBox.question(
            self,
            "Confirm Clear",
            "Are you sure you want to clear all air recovery data?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.air_recovery_processor.clear_data()
            QMessageBox.information(
                self,
                "Data Cleared",
                "All air recovery data has been cleared."
            )

    def update_display(self):
        """
        Update the real-time display with current air recovery data.
        """
        try:
            # Update current readings
            current_air_recovery = self.air_recovery_processor.get_current_air_recovery()
            self.air_recovery_label.setText(f"{current_air_recovery:.2f} %")
            
            self.velocity_label.setText(f"{self.air_recovery_processor.current_velocity:.1f} mm/s")
            self.froth_height_label.setText(f"{self.air_recovery_processor.current_froth_height:.1f} mm")
            
            # Update data count
            history = self.air_recovery_processor.get_air_recovery_history()
            self.count_label.setText(str(len(history)))
            
            # Update statistics
            stats = self.air_recovery_processor.get_statistics()
            if stats:
                stats_text = f"""Average: {stats.get('average', 0):.2f} %
Median: {stats.get('median', 0):.2f} %
Min: {stats.get('min', 0):.2f} %
Max: {stats.get('max', 0):.2f} %
Range: {stats.get('range', 0):.2f} %
Std Dev: {stats.get('std_dev', 0):.2f} %"""
                self.stats_text.setText(stats_text)
            else:
                self.stats_text.setText("No data available")
                
        except Exception as e:
            logger.error(f"Error updating air recovery display: {e}")

    def closeEvent(self, arg__1):
        """
        Handle dialog close event.
        """
        self.update_timer.stop()
        arg__1.accept()