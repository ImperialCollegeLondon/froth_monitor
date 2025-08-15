"""The main module for froth monitor."""

try:
    from importlib.metadata import version

    __version__ = version(__name__)

except Exception:
    __version__ = "0.1.0"  # Default version if metadata is unavailable
