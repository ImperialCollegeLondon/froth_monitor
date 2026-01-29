"""Centralized logging configuration for the Froth Monitor application.

This module provides a standardized logging system to replace print statements
throughout the application. It supports different log levels, file output,
and console output with proper formatting.
"""

import logging
import logging.handlers
import os
from datetime import datetime
from pathlib import Path
from typing import Optional


class FrothMonitorLogger:
    """Centralized logger for the Froth Monitor application."""
    
    _instance: Optional['FrothMonitorLogger'] = None
    _initialized = False
    
    def __new__(cls) -> 'FrothMonitorLogger':
        """Singleton pattern to ensure only one logger instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize the logger configuration."""
        if self._initialized:
            return
            
        self._initialized = True
        self.setup_logging()
    
    def setup_logging(self, 
                     log_level: str = "INFO",
                     log_to_file: bool = True,
                     log_to_console: bool = True,
                     log_dir: Optional[str] = None) -> None:
        """Setup logging configuration.
        
        Args:
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            log_to_file: Whether to log to file
            log_to_console: Whether to log to console
            log_dir: Directory for log files (defaults to logs/ in project root)
        """
        # Create log directory if needed
        if log_dir is None:
            project_root = Path(__file__).parent.parent
            log_dir = project_root / "logs" # type: ignore
        else:
            log_dir = Path(log_dir) # type: ignore
            
        log_dir.mkdir(exist_ok=True) # type: ignore
        
        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, log_level.upper()))
        
        # Clear existing handlers
        root_logger.handlers.clear()
        
        # Create formatters
        detailed_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        simple_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )
        
        # File handler with rotation
        if log_to_file:
            log_file = log_dir / f"froth_monitor_{datetime.now().strftime('%Y%m%d')}.log" # type: ignore
            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=10*1024*1024,  # 10MB
                backupCount=5
            )
            file_handler.setFormatter(detailed_formatter)
            root_logger.addHandler(file_handler)
        
        # Console handler
        if log_to_console:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(simple_formatter)
            root_logger.addHandler(console_handler)
    
    def get_logger(self, name: str) -> logging.Logger:
        """Get a logger instance for a specific module.
        
        Args:
            name: Logger name (typically __name__ of the module)
            
        Returns:
            Configured logger instance
        """
        return logging.getLogger(name)


# Convenience functions for easy migration from print statements
def get_logger(name: str = __name__) -> logging.Logger:
    """Get a logger instance.
    
    Args:
        name: Logger name (typically __name__ of the module)
        
    Returns:
        Configured logger instance
    """
    logger_manager = FrothMonitorLogger()
    return logger_manager.get_logger(name)


def setup_logging(log_level: str = "INFO",
                 log_to_file: bool = True,
                 log_to_console: bool = True,
                 log_dir: Optional[str] = None) -> None:
    """Setup application-wide logging configuration.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_to_file: Whether to log to file
        log_to_console: Whether to log to console
        log_dir: Directory for log files
    """
    logger_manager = FrothMonitorLogger()
    logger_manager.setup_logging(log_level, log_to_file, log_to_console, log_dir)


# Migration helpers
def debug(message: str, logger_name: str = "froth_monitor") -> None:
    """Log debug message."""
    get_logger(logger_name).debug(message)


def info(message: str, logger_name: str = "froth_monitor") -> None:
    """Log info message."""
    get_logger(logger_name).info(message)


def warning(message: str, logger_name: str = "froth_monitor") -> None:
    """Log warning message."""
    get_logger(logger_name).warning(message)


def error(message: str, logger_name: str = "froth_monitor") -> None:
    """Log error message."""
    get_logger(logger_name).error(message)


def critical(message: str, logger_name: str = "froth_monitor") -> None:
    """Log critical message."""
    get_logger(logger_name).critical(message)


# Initialize logging when module is imported
if __name__ != "__main__":
    setup_logging()