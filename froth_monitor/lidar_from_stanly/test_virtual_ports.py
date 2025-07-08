#!/usr/bin/env python3
"""
Virtual Serial Port Tester

This script helps test if your virtual serial port setup is working correctly
before running the full LiDAR application.

Usage:
    python test_virtual_ports.py COM4

This will connect to the specified port and listen for LiDAR data.
Run dummy_lidar.py on the paired port (e.g., COM3) to test the connection.
"""

import sys
import time
import serial
import serial.tools.list_ports
from datetime import datetime

def list_available_ports():
    """List all available COM ports"""
    print("Available COM ports:")
    ports = serial.tools.list_ports.comports()
    if not ports:
        print("  No COM ports found")
        return []
    
    for port in ports:
        print(f"  {port.device} - {port.description}")
    return [port.device for port in ports]

def test_port_connection(port_name):
    """Test connection to a specific port"""
    print(f"\nTesting connection to {port_name}...")
    
    try:
        # Try to open the port with LiDAR settings
        ser = serial.Serial(
            port=port_name,
            baudrate=38400,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=1
        )
        
        print(f"✓ Successfully connected to {port_name}")
        print(f"  Baudrate: {ser.baudrate}")
        print(f"  Timeout: {ser.timeout}s")
        
        return ser
        
    except Exception as e:
        print(f"✗ Failed to connect to {port_name}: {e}")
        return None

def send_lidar_commands(ser):
    """Send LiDAR commands to test communication"""
    print("\nSending LiDAR commands...")
    
    commands = [
        ("iSET:7,10\r\n", "Set frequency to 10 Hz"),
        ("iFACM\r\n", "Start continuous measurement")
    ]
    
    for command, description in commands:
        print(f"Sending: {description}")
        ser.write(command.encode('ascii'))
        time.sleep(0.1)
        
        # Try to read response
        if ser.in_waiting > 0:
            response = ser.readline().decode('ascii', errors='ignore').strip()
            print(f"Response: {response}")
        else:
            print("No response received")

def listen_for_data(ser, duration=10):
    """Listen for incoming LiDAR data"""
    print(f"\nListening for data for {duration} seconds...")
    print("Expected format: D=X.XXXm")
    print("-" * 50)
    
    start_time = time.time()
    data_count = 0
    
    try:
        while time.time() - start_time < duration:
            if ser.in_waiting > 0:
                try:
                    line = ser.readline().decode('ascii', errors='ignore').strip()
                    if line:
                        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                        print(f"[{timestamp}] {line}")
                        data_count += 1
                except Exception as e:
                    print(f"Error reading data: {e}")
            
            time.sleep(0.01)  # Small delay to prevent busy waiting
            
    except KeyboardInterrupt:
        print("\nStopped by user")
    
    print("-" * 50)
    print(f"Received {data_count} data packets")
    
    if data_count > 0:
        print("✓ Virtual port communication is working!")
    else:
        print("✗ No data received. Check if dummy LiDAR is running on paired port.")

def main():
    print("Virtual Serial Port Tester")
    print("=" * 40)
    
    # List available ports
    available_ports = list_available_ports()
    
    # Get port from command line or prompt user
    if len(sys.argv) > 1:
        port_name = sys.argv[1]
    else:
        if not available_ports:
            print("\nNo COM ports available. Please set up virtual serial ports first.")
            print("See setup_virtual_ports.md for instructions.")
            return
        
        print("\nUsage: python test_virtual_ports.py <COM_PORT>")
        print("Example: python test_virtual_ports.py COM4")
        return
    
    # Test connection
    ser = test_port_connection(port_name)
    if not ser:
        return
    
    try:
        # Send commands to start LiDAR (if dummy LiDAR is listening)
        send_lidar_commands(ser)
        
        # Listen for data
        listen_for_data(ser, duration=10)
        
    finally:
        # Clean up
        print("\nClosing connection...")
        ser.close()
        print("Test completed.")

if __name__ == "__main__":
    main()