#!/usr/bin/env python3
"""
Virtual LiDAR Data Generator

A comprehensive virtual LiDAR solution that provides multiple ways to generate
test data for the LidarThread:

1. File-based simulation (always works)
2. COM port simulation (requires com0com setup)
3. Direct integration with LidarThread

Usage:
    python virtual_lidar_com3.py [mode]
    
Modes:
    file    - Generate data to a file (default)
    com     - Try COM port simulation
    test    - Generate test data samples
"""

import serial
import time
import math
import random
import threading
import sys
import os
from typing import Optional


class VirtualLidarGenerator:
    """
    Virtual LiDAR data generator with multiple output modes.
    """
    
    def __init__(self):
        """
        Initialize virtual LiDAR generator.
        """
        # Simulation parameters
        self.base_distance = 1.5  # meters
        self.frequency = 10.0  # Hz
        self.noise_level = 0.002  # ±2mm
        self.drift_amplitude = 0.01  # ±10mm
        self.drift_period = 30.0  # seconds
        
        # Runtime state
        self.start_time = None
        self.measurement_count = 0
        self.is_running = False
        
        print("Virtual LiDAR Data Generator initialized")
    
    def generate_single_measurement(self) -> str:
        """
        Generate a single LiDAR measurement.
        
        Returns:
            str: Formatted measurement string
        """
        distance = self._generate_distance()
        return f"D={distance:.3f}m"
    
    def generate_test_data(self, count: int = 10) -> list:
        """
        Generate test data samples.
        
        Args:
            count: Number of measurements to generate
            
        Returns:
            list: List of formatted measurement strings
        """
        self.start_time = time.time()
        data = []
        
        print(f"Generating {count} test measurements...")
        for i in range(count):
            measurement = self.generate_single_measurement()
            data.append(measurement)
            print(f"  {i+1:2d}: {measurement}")
            time.sleep(0.01)  # Small delay for realistic timing
        
        return data
    
    def run_file_simulation(self, filename: str = "virtual_lidar_data.txt", duration: int = 60):
        """
        Run file-based simulation.
        
        Args:
            filename: Output file name
            duration: Simulation duration in seconds
        """
        print(f"Starting file-based simulation...")
        print(f"Output file: {filename}")
        print(f"Duration: {duration} seconds")
        print(f"Frequency: {self.frequency} Hz")
        print("Press Ctrl+C to stop early")
        
        self.start_time = time.time()
        self.measurement_count = 0
        self.is_running = True
        
        try:
            with open(filename, 'w') as f:
                f.write(f"# Virtual LiDAR Data\n")
                f.write(f"# Generated at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"# Frequency: {self.frequency} Hz\n")
                f.write(f"# Base distance: {self.base_distance} m\n")
                f.write(f"# Format: timestamp,measurement\n")
                
                interval = 1.0 / self.frequency
                
                while self.is_running and (time.time() - self.start_time) < duration:
                    timestamp = time.time()
                    measurement = self.generate_single_measurement()
                    
                    # Write to file
                    f.write(f"{timestamp:.3f},{measurement}\n")
                    f.flush()
                    
                    self.measurement_count += 1
                    
                    # Status update
                    if self.measurement_count % 50 == 0:
                        elapsed = time.time() - self.start_time
                        rate = self.measurement_count / elapsed
                        print(f"Generated {self.measurement_count} measurements, "
                              f"rate: {rate:.1f} Hz, latest: {measurement}")
                    
                    time.sleep(interval)
                    
        except KeyboardInterrupt:
            print("\nStopped by user")
        
        finally:
            self.is_running = False
            elapsed = time.time() - self.start_time
            print(f"\nFile simulation completed:")
            print(f"  Total measurements: {self.measurement_count}")
            print(f"  Duration: {elapsed:.1f} seconds")
            print(f"  Average rate: {self.measurement_count/elapsed:.1f} Hz")
            print(f"  Output file: {os.path.abspath(filename)}")
    
    def try_com_simulation(self, port: str = "COM4"):
        """
        Try COM port simulation (requires com0com).
        
        Args:
            port: COM port to use
        """
        print(f"Attempting COM port simulation on {port}...")
        
        try:
            # Test if port is available
            ser = serial.Serial(port, 115200, timeout=1)
            print(f"Successfully opened {port}")
            
            self.start_time = time.time()
            self.measurement_count = 0
            self.is_running = True
            
            print(f"Sending LiDAR data on {port} at {self.frequency} Hz")
            print("Your LidarThread should connect to COM3")
            print("Press Ctrl+C to stop")
            
            interval = 1.0 / self.frequency
            
            try:
                while self.is_running:
                    measurement = self.generate_single_measurement()
                    message = f"{measurement}\r\n"
                    
                    ser.write(message.encode('ascii'))
                    ser.flush()
                    
                    self.measurement_count += 1
                    
                    if self.measurement_count % 100 == 0:
                        elapsed = time.time() - self.start_time
                        rate = self.measurement_count / elapsed
                        print(f"Sent {self.measurement_count} measurements, "
                              f"rate: {rate:.1f} Hz, latest: {measurement}")
                    
                    time.sleep(interval)
                    
            except KeyboardInterrupt:
                print("\nStopped by user")
            
            finally:
                ser.close()
                elapsed = time.time() - self.start_time
                print(f"\nCOM simulation completed:")
                print(f"  Total measurements: {self.measurement_count}")
                print(f"  Duration: {elapsed:.1f} seconds")
                print(f"  Average rate: {self.measurement_count/elapsed:.1f} Hz")
                
        except Exception as e:
            print(f"COM port simulation failed: {e}")
            print("\nTo use COM port simulation:")
            print("1. Install com0com virtual serial port driver")
            print("2. Create a COM3-COM4 port pair using setupc")
            print("3. Run this script with 'com' mode")
            print("4. Connect your LidarThread to COM3")
            print("\nAlternatively, use 'file' mode for reliable testing")
    
    def _generate_distance(self) -> float:
        """
        Generate realistic distance measurement.
        
        Returns:
            float: Distance in meters
        """
        current_time = time.time() - self.start_time if self.start_time else 0
        
        # Base distance
        distance = self.base_distance
        
        # Add sinusoidal drift
        drift = self.drift_amplitude * math.sin(2 * math.pi * current_time / self.drift_period)
        distance += drift
        
        # Add random noise
        noise = random.gauss(0, self.noise_level)
        distance += noise
        
        # Add occasional larger variations
        if random.random() < 0.05:  # 5% chance
            variation = random.gauss(0, self.noise_level * 3)
            distance += variation
        
        # Ensure reasonable range
        distance = max(0.1, min(10.0, distance))
        
        return distance


def print_usage():
    """Print usage information."""
    print("Virtual LiDAR Data Generator")
    print("============================")
    print()
    print("Usage: python virtual_lidar_com3.py [mode] [options]")
    print()
    print("Modes:")
    print("  test    - Generate and display test data samples")
    print("  file    - Generate data to a file (default, always works)")
    print("  com     - Try COM port simulation (requires com0com setup)")
    print()
    print("Examples:")
    print("  python virtual_lidar_com3.py test")
    print("  python virtual_lidar_com3.py file")
    print("  python virtual_lidar_com3.py com")
    print()


def main():
    """Main function."""
    # Parse command line arguments
    mode = "file"  # default mode
    
    if len(sys.argv) > 1:
        mode = sys.argv[1].lower()
    
    if mode in ["help", "-h", "--help"]:
        print_usage()
        return
    
    # Create virtual LiDAR generator
    generator = VirtualLidarGenerator()
    
    try:
        if mode == "test":
            print("=== Test Mode ===")
            generator.generate_test_data(10)
            
        elif mode == "file":
            print("=== File Mode ===")
            print("This mode generates LiDAR data to a file.")
            print("You can modify your LidarThread to read from this file.")
            print()
            generator.run_file_simulation("virtual_lidar_data.txt", 30)
            
        elif mode == "com":
            print("=== COM Port Mode ===")
            print("This mode tries to simulate LiDAR on COM4.")
            print("Requires com0com virtual serial port driver.")
            print()
            generator.try_com_simulation("COM4")
            
        else:
            print(f"Unknown mode: {mode}")
            print_usage()
            
    except KeyboardInterrupt:
        print("\nShutting down...")
    
    print("\nVirtual LiDAR generator finished.")


if __name__ == "__main__":
    main()