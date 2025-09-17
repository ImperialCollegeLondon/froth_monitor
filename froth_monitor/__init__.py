"""The main module for froth monitor."""

from froth_monitor.processing.image_analysis import VideoAnalysis
from froth_monitor.handlers.autosaver import AutoSaver




try:
    from importlib.metadata import version

    __version__ = version(__name__)

except Exception:
    __version__ = "0.1.0"  # Default version if metadata is unavailable
