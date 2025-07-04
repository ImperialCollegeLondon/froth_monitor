#!/usr/bin/env python3
"""Dummy LiDAR Simulator for Testing.

This module simulates a LiDAR device by generating realistic distance measurements
and outputting them in the "D=X.XXXm" format over a virtual serial port.
It's designed to work with the froth monitor LiDAR integration for testing purposes.
"""

import serial
import time
import random
import math
import sys
import threading
from datetime import datetime


class DummyLidar:
    """Simulates a LiDAR device with realistic distance measurements."""
    
    def __init__(self, port="COM3", baudrate=115200):
        """
        Initialize the dummy LiDAR simulator.
        
        Args:
            port (str): Serial port to use for output
            baudrate (int): Baud rate for serial communication
        """
        self.port = port
        self.baudrate = baudrate
        self.serial_connection = None
        self.running = False
        self.frequency = 10  # Hz - measurements per second
        self.base_distance = 1.5  # meters - base distance
        self.noise_amplitude = 0.05  # meters - noise amplitude
        self.drift_amplitude = 0.2  # meters - slow drift amplitude
        self.drift_period = 30  # seconds - drift period
        self.measurement_count = 0
        self.start_time = None
        
        # Command handling
        self.command_buffer = ""
        self.last_command_time = time.time()
        
    def connect(self):
        """
        Connect to the specified serial port.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            self.serial_connection = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=0.1,  # Non-blocking read
                write_timeout=1.0
            )
            print(f"Dummy LiDAR connected to {self.port} at {self.baudrate} baud")
            return True
        except Exception as e:
            print(f"Failed to connect to {self.port}: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from the serial port."""
        if self.serial_connection and self.serial_connection.is_open:
            self.serial_connection.close()
            print("Dummy LiDAR disconnected")
    
    def generate_realistic_distance(self):
        """
        Generate a realistic distance measurement with noise and drift.
        
        Returns:
            float: Distance in meters
        """
        current_time = time.time()
        if self.start_time is None:
            self.start_time = current_time
        
        elapsed_time = current_time - self.start_time
        
        # Base distance with slow sinusoidal drift
        drift = self.drift_amplitude * math.sin(2 * math.pi * elapsed_time / self.drift_period)
        
        # Add random noise
        noise = random.gauss(0, self.noise_amplitude)
        
        # Occasional larger variations (simulating real-world conditions)
        if random.random() < 0.05:  # 5% chance
            noise += random.gauss(0, self.noise_amplitude * 2)
        
        # Calculate final distance
        distance = self.base_distance + drift + noise
        
        # Ensure distance is positive and within reasonable range
        distance = max(0.1, min(distance, 10.0))
        
        return distance
    
    def format_distance_output(self, distance_m):
        """
        Format distance measurement in LiDAR protocol format.
        
        Args:
            distance_m (float): Distance in meters
            
        Returns:
            str: Formatted distance string
        """
        return f"D={distance_m:.3f}m\r\n"
    
    def send_measurement(self):
        """
        Generate and send a distance measurement.
        
        Returns:
            bool: True if measurement sent successfully, False otherwise
        """
        if not self.serial_connection or not self.serial_connection.is_open:
            return False
        
        try:
            distance = self.generate_realistic_distance()
            output = self.format_distance_output(distance)
            
            self.serial_connection.write(output.encode('ascii'))
            self.serial_connection.flush()
            
            self.measurement_count += 1
            
            # Print status every 50 measurements
            if self.measurement_count % 50 == 0:
                print(f"Sent {self.measurement_count} measurements. Latest: {distance:.3f}m")
            
            return True
            
        except Exception as e:
            print(f"Error sending measurement: {e}")
            return False
    
    def handle_commands(self):
        """
        Handle incoming commands from the serial port.
        """
        if not self.serial_connection or not self.serial_connection.is_open:
            return
        
        try:
            # Read any available data
            if self.serial_connection.in_waiting > 0:
                data = self.serial_connection.read(self.serial_connection.in_waiting)
                self.command_buffer += data.decode('ascii', errors='ignore')
                
                # Process complete commands (ending with \n or \r)
                while '\n' in self.command_buffer or '\r' in self.command_buffer:
                    if '\n' in self.command_buffer:
                        command, self.command_buffer = self.command_buffer.split('\n', 1)
                    else:
                        command, self.command_buffer = self.command_buffer.split('\r', 1)
                    
                    command = command.strip()
                    if command:
                        self.process_command(command)
                        
        except Exception as e:
            print(f"Error handling commands: {e}")
    
    def process_command(self, command):
        """
        Process a received command.
        
        Args:
            command (str): Command string to process
        """
        command = command.upper().strip()
        print(f"Received command: {command}")
        
        try:
            if command.startswith('FREQ'):
                # Set frequency command: FREQ=10
                if '=' in command:
                    freq_str = command.split('=')[1]
                    new_freq = float(freq_str)
                    if 0.1 <= new_freq <= 100:
                        self.frequency = new_freq
                        response = f"FREQ={self.frequency}\r\n"
                        self.serial_connection.write(response.encode('ascii'))
                        print(f"Frequency set to {self.frequency} Hz")
                    else:
                        self.send_error("Invalid frequency range (0.1-100 Hz)")
                else:
                    # Query current frequency
                    response = f"FREQ={self.frequency}\r\n"
                    self.serial_connection.write(response.encode('ascii'))
            
            elif command == 'START':
                # Start measurements
                response = "OK\r\n"
                self.serial_connection.write(response.encode('ascii'))
                print("Start command acknowledged")
            
            elif command == 'STOP':
                # Stop measurements
                response = "OK\r\n"
                self.serial_connection.write(response.encode('ascii'))
                print("Stop command acknowledged")
            
            elif command == 'STATUS':
                # Status query
                uptime = time.time() - self.start_time if self.start_time else 0
                response = f"STATUS=RUNNING,COUNT={self.measurement_count},UPTIME={uptime:.1f}\r\n"
                self.serial_connection.write(response.encode('ascii'))
            
            elif command.startswith('DIST'):
                # Set base distance: DIST=1.5
                if '=' in command:
                    dist_str = command.split('=')[1]
                    new_dist = float(dist_str)
                    if 0.1 <= new_dist <= 10.0:
                        self.base_distance = new_dist
                        response = f"DIST={self.base_distance}\r\n"
                        self.serial_connection.write(response.encode('ascii'))
                        print(f"Base distance set to {self.base_distance} m")
                    else:
                        self.send_error("Invalid distance range (0.1-10.0 m)")
                else:
                    # Query current base distance
                    response = f"DIST={self.base_distance}\r\n"
                    self.serial_connection.write(response.encode('ascii'))
            
            elif command == 'HELP':
                # Help command
                help_text = (
                    "Commands:\r\n"
                    "FREQ[=value] - Set/get frequency (Hz)\r\n"
                    "DIST[=value] - Set/get base distance (m)\r\n"
                    "START - Start measurements\r\n"
                    "STOP - Stop measurements\r\n"
                    "STATUS - Get status\r\n"
                    "HELP - Show this help\r\n"
                )
                self.serial_connection.write(help_text.encode('ascii'))
            
            else:
                self.send_error(f"Unknown command: {command}")
                
        except ValueError as e:
            self.send_error(f"Invalid parameter: {e}")
        except Exception as e:
            self.send_error(f"Command error: {e}")
    
    def send_error(self, message):
        """
        Send an error message.
        
        Args:
            message (str): Error message to send
        """
        try:
            error_msg = f"ERROR: {message}\r\n"
            self.serial_connection.write(error_msg.encode('ascii'))
            print(f"Sent error: {message}")
        except Exception as e:
            print(f"Failed to send error message: {e}")
    
    def run(self):
        """
        Main simulation loop.
        """
        if not self.connect():
            return False
        
        self.running = True
        self.start_time = time.time()
        
        print(f"Dummy LiDAR simulation started")
        print(f"Frequency: {self.frequency} Hz")
        print(f"Base distance: {self.base_distance} m")
        print(f"Press Ctrl+C to stop")
        
        try:
            while self.running:
                # Handle incoming commands
                self.handle_commands()
                
                # Send measurement
                if not self.send_measurement():
                    print("Failed to send measurement, stopping...")
                    break
                
                # Wait for next measurement based on frequency
                time.sleep(1.0 / self.frequency)
                
        except KeyboardInterrupt:
            print("\nStopping dummy LiDAR...")
        except Exception as e:
            print(f"Error in simulation loop: {e}")
        finally:
            self.running = False
            self.disconnect()
        
        return True
    
    def stop(self):
        """Stop the simulation."""
        self.running = False


def main():
    """Main function to run the dummy LiDAR simulator."""
    # Parse command line arguments
    port = "COM3"  # Default port
    baudrate = 115200  # Default baud rate
    
    if len(sys.argv) > 1:
        port = sys.argv[1]
    if len(sys.argv) > 2:
        try:
            baudrate = int(sys.argv[2])
        except ValueError:
            print(f"Invalid baud rate: {sys.argv[2]}")
            return
    
    print(f"Dummy LiDAR Simulator")
    print(f"Port: {port}")
    print(f"Baud rate: {baudrate}")
    print(f"Data format: D=X.XXXm")
    print()
    
    # Create and run the simulator
    simulator = DummyLidar(port, baudrate)
    
    try:
        simulator.run()
    except Exception as e:
        print(f"Simulation failed: {e}")
    
    print("Dummy LiDAR simulator stopped")


if __name__ == "__main__":
    main()