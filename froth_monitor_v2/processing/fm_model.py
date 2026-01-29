"""Backward compatibility module for fm_model imports.

DEPRECATED: This module exists for backward compatibility only.

New code should import from:
  - froth_monitor.processing.roi import ROI, ROIConstants
  - froth_monitor.processing.frame_model import FrameModel

Example:
    # Old way (still works)
    from froth_monitor.processing.fm_model import ROI, FrameModel
    
    # New way (preferred)
    from froth_monitor.processing.roi import ROI, ROIConstants
    from froth_monitor.processing.frame_model import FrameModel
"""

# Re-export for backward compatibility
from froth_monitor.processing.roi import ROI, ROIConstants
from froth_monitor.processing.frame_model import FrameModel

__all__ = ['ROI', 'ROIConstants', 'FrameModel']
