# Logging Migration Guide

This guide explains how to replace `print()` statements with the new centralized logging system in the Froth Monitor application.

## Quick Start

### 1. Import the logger

```python
from logger_config import get_logger

# Get a logger for your module
logger = get_logger(__name__)
```

### 2. Replace print statements

**Before:**
```python
print("Starting LiDAR capture")
print(f"Error processing data: {e}")
print("Debug info:", some_variable)
```

**After:**
```python
logger.info("Starting LiDAR capture")
logger.error(f"Error processing data: {e}")
logger.debug(f"Debug info: {some_variable}")
```

## Log Levels

Use appropriate log levels for different types of messages:

- **`logger.debug()`**: Detailed diagnostic information, typically only of interest when diagnosing problems
- **`logger.info()`**: General information about program execution
- **`logger.warning()`**: Something unexpected happened, but the software is still working
- **`logger.error()`**: A serious problem occurred, the software couldn't perform some function
- **`logger.critical()`**: A very serious error occurred, the program may not be able to continue

## Migration Examples

### Example 1: Basic Information
```python
# Before
print("LiDAR capture started")

# After
logger.info("LiDAR capture started")
```

### Example 2: Error Handling
```python
# Before
print(f"Error updating LiDAR display: {e}")

# After
logger.error(f"Error updating LiDAR display: {e}")
```

### Example 3: Debug Information
```python
# Before
print("algo config draw")
print(self.arrow_start_point, self.arrow_end_point)

# After
logger.debug("Algorithm configuration draw initiated")
logger.debug(f"Arrow points: start={self.arrow_start_point}, end={self.arrow_end_point}")
```

### Example 4: Status Updates
```python
# Before
print("Live recording")
print(f"Recording stopped: {self.output_path}")

# After
logger.info("Live recording started")
logger.info(f"Recording stopped: {self.output_path}")
```

## Configuration

### Default Configuration
The logger is automatically configured when imported with:
- Log level: INFO
- File output: Enabled (logs/froth_monitor_YYYYMMDD.log)
- Console output: Enabled
- Log rotation: 10MB files, 5 backups

### Custom Configuration
```python
from logger_config import setup_logging

# Custom setup
setup_logging(
    log_level="DEBUG",  # More verbose logging
    log_to_file=True,
    log_to_console=True,
    log_dir="/custom/log/path"
)
```

## File-by-File Migration

### Priority Files to Migrate

1. **Core Application Files:**
   - `__main__.py`
   - `video_recorder.py`
   - `overlay_widget.py`

2. **LiDAR Components:**
   - `lidar_thread/lidar_thread.py`
   - `lidar_thread/lidar_data_processor.py`
   - `lidar_thread/lidar_control_dialog.py`

3. **Network Components:**
   - `video_threads/network_thread.py`
   - `network/windows_receiver.py`

### Migration Template

For each file:

1. Add import at the top:
```python
from logger_config import get_logger

logger = get_logger(__name__)
```

2. Replace print statements:
   - Information messages → `logger.info()`
   - Error messages → `logger.error()`
   - Debug messages → `logger.debug()`
   - Warnings → `logger.warning()`

3. Test the changes to ensure logging works correctly

## Benefits

1. **Centralized Control**: Change log levels and output destinations from one place
2. **Structured Output**: Consistent formatting with timestamps and source information
3. **File Rotation**: Automatic log file management prevents disk space issues
4. **Performance**: Log levels allow filtering out debug messages in production
5. **Debugging**: Easier to trace issues with proper log levels and source information

## Best Practices

1. **Use appropriate log levels**: Don't log everything as INFO
2. **Include context**: Add relevant variable values and state information
3. **Be descriptive**: Write clear, actionable log messages
4. **Avoid sensitive data**: Don't log passwords, API keys, or personal information
5. **Use f-strings**: For better performance and readability

```python
# Good
logger.info(f"Processing frame {frame_count} at {timestamp}")

# Avoid
logger.info("Processing frame " + str(frame_count) + " at " + str(timestamp))
```

## Testing the Migration

After migrating a file:

1. Run the application and check that log messages appear in both console and log file
2. Verify that different log levels work correctly
3. Check that log files are created in the `logs/` directory
4. Ensure no functionality is broken by the migration

## Troubleshooting

### Common Issues

1. **Import errors**: Make sure `logger_config.py` is in the correct location
2. **Permission errors**: Ensure the application can write to the logs directory
3. **Missing logs**: Check that the logger is properly initialized

### Debugging Logger Issues

```python
import logging

# Check current log level
print(f"Current log level: {logging.getLogger().level}")

# List all handlers
for handler in logging.getLogger().handlers:
    print(f"Handler: {handler}")
```