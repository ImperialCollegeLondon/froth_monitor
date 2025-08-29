"""Air Recovery Data Processor Module for Froth Monitor Application.

This module defines the `AirRecoveryDataProcessor` class, which processes velocity and
froth height data to calculate air recovery percentages in froth flotation systems.
It handles data buffering, averaging, and statistical analysis.
"""

from typing import List, Dict
from datetime import datetime
import statistics
from froth_monitor.logger_config import get_logger

# Initialize logger for this module
logger = get_logger(__name__)

class AirRecoveryDataProcessor:
    """
    Processes velocity and froth height data to calculate air recovery percentages.
    
    This class handles air recovery calculations based on the formula:
    Air Recovery (%) = (velocity × froth_height × cell_perimeter) / air_flow_rate
    """

    def __init__(self, event_handler):
        """
        Initialize the air recovery data processor.
        
        Args:
            event_handler: The main event handler instance
        """
        self.event_handler = event_handler
        self.gui = self.event_handler.gui

        # Current readings
        self.current_velocity = 0.0
        self.current_froth_height = 0.0
        self.current_air_recovery = 0.0
        self.current_timestamp = ""

        # Configuration parameters (user-configurable)
        self.cell_perimeter = 1000.0  # mm, default value
        self.air_flow_rate = 100.0  # L/min, default value
        self.air_flow_unit = "L/min"  # Options: "m3/hr", "L/min", "cm3/s"
        self.use_jg_calculation = False
        self.jg_value = 1.0  # cm/s, superficial gas velocity
        self.cell_area = 1000000.0  # mm², default value
        
        # Configuration state tracking
        self.is_configured = False
        self.configuration_locked = False

        # Historical data storage
        self.air_recovery_history = []  # All air recovery calculations
        self.velocity_history = []  # Velocity values used in calculations
        self.froth_height_history = []  # Froth height values used in calculations
        self.timestamp_history = []  # Timestamps for each calculation

        # Data buffering for averaging
        self.data_buffer = []  # Buffer for (velocity, froth_height, timestamp) tuples
        self.buffer_size = 10  # Number of readings to average
        
        # Statistics
        self.statistics_cache = {}
        self.last_stats_update = datetime.now()
        self.stats_update_interval = 1.0  # seconds

    def process_air_recovery_data(self, 
    velocity: float, 
    froth_height: float, 
    timestamp: str) -> tuple[str, float, float, float, float, float] | None:
        """
        Process new velocity and froth height data to calculate air recovery.

        Args:
            velocity (float): Overflow velocity in mm/s
            froth_height (float): Froth height in mm
            timestamp (str, optional): Timestamp string, defaults to current time
        """
        try:
            # Update current readings
            self.current_velocity = velocity
            self.current_froth_height = froth_height
            self.current_timestamp = timestamp

            # Calculate air recovery
            air_recovery = self._calculate_air_recovery(velocity, froth_height)
            self.current_air_recovery = air_recovery

            # Add to historical data
            self.air_recovery_history.append(air_recovery)
            self.velocity_history.append(velocity)
            self.froth_height_history.append(froth_height)
            self.timestamp_history.append(timestamp)

            # Add to buffer for averaging
            self.data_buffer.append((velocity, froth_height, air_recovery, timestamp))
            if len(self.data_buffer) > self.buffer_size:
                self.data_buffer.pop(0)

            # Update statistics periodically
            current_time = datetime.now()
            if (current_time - self.last_stats_update).total_seconds() > self.stats_update_interval:
                self._update_statistics()
                self.last_stats_update = current_time

            # Update GUI if available
            self._update_gui()

            logger.debug(f"Air recovery calculated: {air_recovery:.2f}% (V={velocity:.1f}, FH={froth_height:.1f})")
            
            # if self.use_jg_calculation:
            #     current_air_flow = f'{self.jg_value} cm/s'
            # else:
            #     current_air_flow = f'{self.air_flow_rate} {self.air_flow_unit}'
            

            current_air_flow_in_litre = self._get_air_flow_in_litre_per_min()

            return timestamp, velocity, froth_height, \
                air_recovery, self.jg_value, current_air_flow_in_litre

        except Exception as e:
            logger.error(f"Error processing air recovery data: {e}")

    def _calculate_air_recovery(self, velocity: float, froth_height: float) -> float:
        """
        Calculate air recovery percentage using the flotation formula.
        
        Formula: Air Recovery (%) = (velocity × froth_height × cell_perimeter) / air_flow_rate
        
        Args:
            velocity (float): Overflow velocity in mm/s
            froth_height (float): Froth height in mm
            
        Returns:
            float: Air recovery percentage
        """
        try:
            # Get air flow rate in consistent units
            air_flow_mm3_per_s = self._get_air_flow_in_mm3_per_s()
            
            if air_flow_mm3_per_s <= 0:
                logger.warning("Air flow rate is zero or negative, cannot calculate air recovery")
                return 0.0

            # Calculate numerator: velocity (mm/s) × froth_height (mm) × perimeter (mm)
            numerator = velocity * froth_height * self.cell_perimeter
            
            # Calculate air recovery percentage
            air_recovery = (numerator / air_flow_mm3_per_s) * 100
            
            return max(0.0, air_recovery)  # Ensure non-negative result
            
        except Exception as e:
            logger.error(f"Error calculating air recovery: {e}")
            return 0.0

    def _get_air_flow_in_mm3_per_s(self) -> float:
        """
        Convert air flow rate to mm³/s for consistent calculations.
        
        Returns:
            float: Air flow rate in mm³/s
        """
        if self.use_jg_calculation:
            # Calculate from Jg (superficial gas velocity) and cell area
            # Jg is in cm/s, cell_area is in mm²
            # Convert: cm/s × mm² = (mm/s × 0.1) × mm² = mm³/s × 0.1
            return self.jg_value * 10 * self.cell_area  # Convert cm/s to mm/s
        else:
            # Convert from user-specified units
            if self.air_flow_unit == "m3/hr":
                # m³/hr to mm³/s: × 1e9 / 3600
                return self.air_flow_rate * 1e9 / 3600
            elif self.air_flow_unit == "L/min":
                # L/min to mm³/s: × 1e6 / 60
                return self.air_flow_rate * 1e6 / 60
            elif self.air_flow_unit == "cm3/s":
                # cm³/s to mm³/s: × 1000
                return self.air_flow_rate * 1000
            else:
                logger.error(f"Unknown air flow unit: {self.air_flow_unit}")
                return 1.0  # Fallback to prevent division by zero
        
    def _get_air_flow_in_litre_per_min(self) -> float:
        """
        Convert air flow rate to L/min for display and reporting purposes.
        
        Returns:
            float: Air flow rate in L/min
        """
        if self.use_jg_calculation:
            # Calculate from Jg (superficial gas velocity) and cell area
            # Jg is in cm/s, cell_area is in mm²
            # Convert: cm/s × mm² = (mm/s × 0.1) × mm² = mm³/s × 0.1
            # Then convert mm³/s to L/min: × 60 / 1e6
            air_flow_mm3_per_s = self.jg_value * 10 * self.cell_area
            return air_flow_mm3_per_s * 60 / 1e6
        else:
            # Convert from user-specified units
            if self.air_flow_unit == "m3/hr":
                # m³/hr to L/min: × 1000 / 60
                return self.air_flow_rate * 1000 / 60
            elif self.air_flow_unit == "L/min":
                # Already in L/min
                return self.air_flow_rate
            elif self.air_flow_unit == "cm3/s":
                # cm³/s to L/min: × 60 / 1000
                return self.air_flow_rate * 60 / 1000
            else:
                logger.error(f"Unknown air flow unit: {self.air_flow_unit}")
                return 1.0  # Fallback to prevent division by zero

    def _update_statistics(self):
        """
        Update statistical information about air recovery data.
        """
        try:
            if not self.air_recovery_history:
                self.statistics_cache = {}
                return

            self.statistics_cache = {
                'count': len(self.air_recovery_history),
                'current': self.current_air_recovery,
                'average': statistics.mean(self.air_recovery_history),
                'median': statistics.median(self.air_recovery_history),
                'min': min(self.air_recovery_history),
                'max': max(self.air_recovery_history),
                'range': max(self.air_recovery_history) - min(self.air_recovery_history)
            }
            
            if len(self.air_recovery_history) > 1:
                self.statistics_cache['std_dev'] = statistics.stdev(self.air_recovery_history)
            else:
                self.statistics_cache['std_dev'] = 0.0
                
        except Exception as e:
            logger.error(f"Error updating air recovery statistics: {e}")
            self.statistics_cache = {}

    def _update_gui(self):
        """
        Update the GUI with current air recovery data.
        """
        try:
            # Update status bar with current reading
            if hasattr(self.gui, 'statusBar'):
                status_text = f"Air Recovery: {self.current_air_recovery:.1f}% | V: {self.current_velocity:.1f} mm/s | FH: {self.current_froth_height:.1f} mm"
                # Note: This might interfere with other status updates, consider a dedicated display area
                
        except Exception as e:
            logger.error(f"Error updating GUI with air recovery data: {e}")

    # Configuration methods
    def set_cell_perimeter(self, perimeter: float):
        """Set the cell perimeter in mm."""
        self.cell_perimeter = max(0.0, perimeter)
        logger.info(f"Cell perimeter set to {self.cell_perimeter} mm")

    def set_air_flow_rate(self, flow_rate: float, unit: str):
        """Set the air flow rate and unit."""
        self.air_flow_rate = max(0.0, flow_rate)
        self.air_flow_unit = unit
        self.use_jg_calculation = False
        self.is_configured = True
        logger.info(f"Air flow rate set to {self.air_flow_rate} {self.air_flow_unit}")

    def set_jg_parameters(self, jg: float, cell_area: float):
        """Set Jg (superficial gas velocity) and cell area for air flow calculation."""
        self.jg_value = max(0.0, jg)
        self.cell_area = max(0.0, cell_area)
        self.use_jg_calculation = True
        self.is_configured = True
        logger.info(f"Jg parameters set: Jg={self.jg_value} cm/s, Area={self.cell_area} mm²")
        
    def lock_configuration(self):
        """Lock the current configuration to prevent changes."""
        if self.is_configured:
            self.configuration_locked = True
            logger.info("Air flow rate locked")
        else:
            logger.warning("Cannot lock configuration - not yet configured")
            
    def is_configuration_locked(self) -> bool:
        """Check if configuration is locked."""
        return self.configuration_locked
        
    def reset_configuration(self):
        """Reset configuration state and unlock settings."""
        self.is_configured = False
        self.configuration_locked = False
        # Reset to default values
        self.cell_perimeter = 1000.0
        self.air_flow_rate = 100.0
        self.air_flow_unit = "L/min"
        self.use_jg_calculation = False
        self.jg_value = 1.0
        self.cell_area = 1000000.0
        logger.info("Air recovery configuration reset to defaults")

    # Data access methods
    def get_current_air_recovery(self) -> float:
        """Get the current air recovery percentage."""
        return self.current_air_recovery

    def get_average_air_recovery(self) -> float:
        """Get the average air recovery from the current buffer."""
        if not self.data_buffer:
            return 0.0
        return statistics.mean([data[2] for data in self.data_buffer])

    def get_air_recovery_history(self) -> List[float]:
        """Get the complete history of air recovery calculations."""
        return self.air_recovery_history.copy()

    def get_statistics(self) -> Dict:
        """Get statistical information about air recovery data."""
        return self.statistics_cache.copy()

    def get_configuration(self) -> Dict:
        """Get current configuration parameters."""
        return {
            'cell_perimeter': self.cell_perimeter,
            'air_flow_rate': self.air_flow_rate,
            'air_flow_unit': self.air_flow_unit,
            'use_jg_calculation': self.use_jg_calculation,
            'jg_value': self.jg_value,
            'cell_area': self.cell_area,
            'is_configured': self.is_configured,
            'configuration_locked': self.configuration_locked
        }

    # Data management methods
    def clear_data(self):
        """Clear all stored air recovery data and reset buffers."""
        self.air_recovery_history.clear()
        self.velocity_history.clear()
        self.froth_height_history.clear()
        self.timestamp_history.clear()
        self.data_buffer.clear()
        
        self.current_velocity = 0.0
        self.current_froth_height = 0.0
        self.current_air_recovery = 0.0
        self.current_timestamp = ""
        
        self.statistics_cache = {}
        
        logger.info("Air recovery data processor cleared")

    def export_data(self, filename: str) -> bool:
        """
        Export air recovery data to a CSV file.
        
        Args:
            filename (str): Path to the output file
            
        Returns:
            bool: True if export was successful, False otherwise
        """
        try:
            import csv
            
            with open(filename, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                
                # Write headers
                writer.writerow([
                    'index', 
                    'timestamp',
                    'velocity_mm_per_s', 
                    'froth_height_mm', 
                    'air_recovery_percent',
                    'cell_perimeter_mm',
                    'air_flow_rate',
                    'air_flow_unit'
                ])
                
                # Write configuration as comment rows
                config = self.get_configuration()
                writer.writerow(['# Configuration:'])
                for key, value in config.items():
                    writer.writerow([f'# {key}', value])
                writer.writerow(['# Data:'])
                
                # Write data
                max_len = len(self.air_recovery_history)
                
                for i in range(max_len):
                    timestamp = self.timestamp_history[i] if i < len(self.timestamp_history) else ''
                    velocity = self.velocity_history[i] if i < len(self.velocity_history) else ''
                    froth_height = self.froth_height_history[i] if i < len(self.froth_height_history) else ''
                    air_recovery = self.air_recovery_history[i] if i < len(self.air_recovery_history) else ''
                    
                    writer.writerow([
                        i, timestamp, velocity, froth_height, air_recovery,
                        self.cell_perimeter, self.air_flow_rate, self.air_flow_unit
                    ])
            
            logger.info(f"Air recovery data exported to {filename}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export air recovery data: {e}")
            return False