#!/usr/bin/env python3
"""Example script demonstrating the logging system usage.

This script shows how to use the centralized logging system
and can be used to test that logging is working correctly.
"""

from froth_monitor.handlers.logger_config import get_logger, setup_logging
import time

# Initialize logger for this module
logger = get_logger(__name__)

def demonstrate_logging():
    """Demonstrate different logging levels and features."""
    
    logger.info("=== Logging System Demonstration ===")
    
    # Basic logging levels
    logger.debug("This is a debug message - detailed diagnostic info")
    logger.info("This is an info message - general information")
    logger.warning("This is a warning message - something unexpected happened")
    logger.error("This is an error message - a serious problem occurred")
    logger.critical("This is a critical message - very serious error")
    
    # Logging with variables
    frame_count = 1234
    timestamp = time.time()
    logger.info(f"Processed {frame_count} frames at timestamp {timestamp:.2f}")
    
    # Simulating error handling
    try:
        # This will raise an exception
        result = 10 / 0
    except ZeroDivisionError as e:
        logger.error(f"Mathematical error occurred: {e}")
    
    # Simulating different components
    logger.info("Simulating LiDAR component")
    lidar_logger = get_logger("froth_monitor.lidar")
    lidar_logger.info("LiDAR sensor initialized")
    lidar_logger.debug("Reading distance: 1234.5 mm")
    
    logger.info("Simulating video component")
    video_logger = get_logger("froth_monitor.video")
    video_logger.info("Video recording started")
    video_logger.warning("Frame rate dropped below threshold")
    
    logger.info("=== Demonstration Complete ===")

def test_custom_configuration():
    """Test custom logging configuration."""
    
    print("\n=== Testing Custom Configuration ===")
    
    # Setup custom logging (DEBUG level, console only)
    setup_logging(
        log_level="DEBUG",
        log_to_file=False,  # Disable file logging for this test
        log_to_console=True
    )
    
    test_logger = get_logger("test_module")
    test_logger.debug("This debug message should now be visible")
    test_logger.info("Custom configuration test complete")
    
    # Reset to default configuration
    setup_logging()
    
if __name__ == "__main__":
    print("Starting logging system demonstration...")
    print("Check both console output and the logs/ directory for log files.")
    print("\n=== Default Configuration Test ===")
    
    demonstrate_logging()
    test_custom_configuration()
    
    print("\nLogging demonstration complete!")
    print("Check the logs/ directory for the generated log file.")