# LiDAR Integration for Froth Monitor

This document explains how to integrate and use LiDAR functionality in the Froth Monitor application.

## Overview

The LiDAR integration provides real-time distance measurements that can be used alongside video analysis for comprehensive froth monitoring. The system supports both physical LiDAR devices and simulated data for testing.

## Components

The LiDAR integration consists of several key components:

### Core Components

1. **`lidar_thread.py`** - Main LiDAR data acquisition thread
2. **`lidar_data_processor.py`** - Data processing and analysis
3. **`lidar_control_dialog.py`** - GUI control interface
4. **`event_handler.py`** - Integration with main application

### Testing Components

1. **`dummy_lidar.py`** - LiDAR simulator for testing
2. **`test_lidar_integration.py`** - Standalone test application
3. **`test_virtual_ports.py`** - Virtual port testing utility
4. **`run_dummy_lidar.bat`** - Easy launcher for simulator

## Features

### LiDAR Thread (`LidarThread`)
- Serial communication with LiDAR devices
- Real-time data parsing ("D=X.XXXm" format)
- Distance offset calibration
- Data buffering and timestamping
- Export to CSV format
- Thread-safe operation

### Data Processor (`LidarDataProcessor`)
- Real-time data averaging
- Statistical analysis (min, max, average, std dev)
- Data buffering with configurable size
- Integration with GUI updates

### Control Dialog (`LidarControlDialog`)
- Start/stop data capture
- Serial port configuration
- Real-time data display
- Distance offset adjustment
- Data export and clearing
- Statistics visualization

## Integration with Froth Monitor

### Event Handler Integration

The LiDAR functionality is integrated into the main `EventHandler` class:

```python
# Initialization
self.lidar_thread = LidarThread()
self.lidar_data_processor = LidarDataProcessor(self, self.lidar_thread)

# Signal connections
self.lidar_thread.data_available.connect(
    self.lidar_data_processor.process_lidar_data
)
```

### Available Methods

- `start_lidar_capture(port, baudrate)` - Start LiDAR data collection
- `stop_lidar_capture()` - Stop data collection
- `pause_lidar_capture()` - Pause collection
- `resume_lidar_capture()` - Resume collection
- `set_lidar_offset(offset_mm)` - Set distance offset
- `export_lidar_data(filename)` - Export data to CSV
- `get_lidar_statistics()` - Get statistical summary
- `clear_lidar_data()` - Clear all data
- `open_lidar_control()` - Open control dialog

## Usage Instructions

### 1. Hardware Setup

#### Physical LiDAR Device
1. Connect your LiDAR device to a serial port (USB-to-Serial adapter if needed)
2. Note the COM port number (e.g., COM3, COM4)
3. Ensure the device outputs data in "D=X.XXXm" format

#### Simulated LiDAR (for testing)
1. Set up virtual serial ports (see `setup_virtual_ports.md`)
2. Run the dummy LiDAR simulator:
   ```bash
   python dummy_lidar.py COM3
   ```
   Or use the batch file:
   ```bash
   run_dummy_lidar.bat
   ```

### 2. Software Integration

#### In Main Application
1. The LiDAR functionality is automatically available in the `EventHandler`
2. Access through the LiDAR control dialog:
   ```python
   event_handler.open_lidar_control()
   ```

#### Standalone Testing
1. Run the test application:
   ```bash
   python test_lidar_integration.py
   ```
2. This provides a simple interface to test all LiDAR functionality

### 3. Configuration

#### Serial Port Settings
- **Port**: COM port where LiDAR is connected (e.g., COM3)
- **Baud Rate**: Communication speed (default: 115200)
- **Timeout**: Read timeout in seconds (default: 1.0)

#### Distance Settings
- **Offset**: Distance offset in millimeters for calibration
- **Buffer Size**: Number of readings to keep in memory (default: 1000)

### 4. Data Format

#### Input Format
The LiDAR device should output data in the format:
```
D=1.234m
```
Where `1.234` is the distance in meters.

#### Output Data
Processed data includes:
- **Timestamp**: When the reading was taken
- **Distance (mm)**: Distance in millimeters
- **Inverted Distance**: 1000 - distance (for certain applications)
- **Formatted Time**: Human-readable timestamp

#### CSV Export Format
```csv
Timestamp,Distance_mm,Inverted_Distance_mm,Formatted_Time
1704067200.123,1234.0,766.0,2024-01-01 12:00:00.123
```

## API Reference

### LidarThread Methods

```python
# Start capture
success = lidar_thread.start_lidar_capture(port="COM3", baudrate=115200)

# Control capture
lidar_thread.pause_lidar_capture()
lidar_thread.resume_lidar_capture()
lidar_thread.stop_lidar_capture()

# Configuration
lidar_thread.set_distance_offset(50.0)  # 50mm offset

# Data access
latest_data = lidar_thread.get_latest_data()
data_count = lidar_thread.get_data_count()

# Export and clear
lidar_thread.export_data("lidar_data.csv")
lidar_thread.clear_data()
```

### LidarDataProcessor Methods

```python
# Get statistics
stats = processor.get_statistics()
# Returns: {'count': int, 'average': float, 'min': float, 'max': float, 'range': float, 'std_dev': float}

# Get current reading
current = processor.get_current_reading()  # Returns float in mm

# Clear data
processor.clear_data()
```

### Signals

```python
# LidarThread signals
lidar_thread.data_available.connect(callback)  # Emitted when new data arrives
# Signal data: {'timestamp': float, 'distance_mm': float, 'inverted_distance_mm': float, 'formatted_time': str}
```

## Troubleshooting

### Common Issues

1. **"Port not found" error**
   - Check if the COM port exists
   - Ensure no other application is using the port
   - Try different COM ports

2. **"No data received" error**
   - Verify LiDAR device is powered and working
   - Check baud rate settings
   - Ensure correct data format ("D=X.XXXm")

3. **"Permission denied" error**
   - Run application as administrator
   - Check if antivirus is blocking serial access

4. **Inconsistent readings**
   - Check for electromagnetic interference
   - Verify stable power supply
   - Adjust distance offset if needed

### Testing Steps

1. **Test with dummy LiDAR**:
   ```bash
   python dummy_lidar.py COM3
   python test_lidar_integration.py
   ```

2. **Test virtual ports**:
   ```bash
   python test_virtual_ports.py COM3
   ```

3. **Check available ports**:
   ```python
   import serial.tools.list_ports
   ports = serial.tools.list_ports.comports()
   for port in ports:
       print(f"{port.device}: {port.description}")
   ```

## Performance Considerations

- **Data Rate**: The system can handle up to 100 readings per second
- **Memory Usage**: Each reading uses approximately 100 bytes
- **Buffer Size**: Default 1000 readings ≈ 100KB memory
- **Export Performance**: CSV export is optimized for large datasets

## Future Enhancements

- Support for multiple LiDAR devices
- Real-time data visualization
- Advanced filtering algorithms
- Integration with video frame synchronization
- Support for different LiDAR protocols
- Automatic device detection

## Dependencies

- `PySide6` - GUI framework
- `pyserial` - Serial communication
- `numpy` - Numerical operations (if used)
- `csv` - Data export
- `threading` - Concurrent operation
- `time` - Timestamping

## License

This LiDAR integration follows the same license as the main Froth Monitor application.