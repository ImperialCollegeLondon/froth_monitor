"""Air Recovery Module for Froth Monitor Application.

This module provides air recovery calculation and monitoring functionality
for froth flotation systems.
"""

from .air_recovery_data_processor import AirRecoveryDataProcessor
from .air_recovery_control_dialog import AirRecoveryControlDialog

__all__ = ["AirRecoveryDataProcessor", "AirRecoveryControlDialog"]
