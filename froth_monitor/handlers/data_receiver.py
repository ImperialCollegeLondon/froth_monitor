import sys
from froth_monitor.api_jetson.network import VideoReceiver
from froth_monitor.api_jetson.network import discover_and_connect
from froth_monitor.api_jetson.commands import CommandList
from typing import cast
import cv2

SELF_NETWORK_ADDRESS = "0.0.0.0"    # listen on all interfaces
SELF_NETWORK_PORT    = 5001
SELF_REQUEST_TIMEOUT  = 60 * 60  # 60 minutes

class DataReceiver():

    def __init__(self, addr = SELF_NETWORK_ADDRESS, port = SELF_NETWORK_PORT, request_timeout = SELF_REQUEST_TIMEOUT, verbose_level=2):
        super().__init__()
        self.addr = addr
        self.port = port
        self.verbose_level = verbose_level
        self.request_timeout = request_timeout
        self.receiver = VideoReceiver(self.addr, self.port, self.request_timeout, self.verbose_level)

        # json format data waiting to be sent to Jetson
        self.jetson_data = {}
        
        # Initialize command list for structured commands
        self.command_list = CommandList()

        # connect to Jetson
        self.jetson_ip, self.agreed_port = discover_and_connect(retries=3, timeout=5.0)
        if self.jetson_ip and self.agreed_port:
            print(f"\n[DataReceiver] ** CONNECTED ** to Jetson at {self.jetson_ip}:{self.agreed_port}")

    def get_data(self):
        server_data = cast(dict, None)
        consecutive_failures = 0
        max_consecutive_failures = 100

        while True:
            try:
                if (self.has_pending_data()):
                    frame, server_data = self.receiver.recv(self.jetson_data)
                    # clear the jetson_data after sending
                    self.clear_pending_data()
                else:
                    frame, server_data = self.receiver.recv()
                    
                # Check if we got valid data
                if frame is None and server_data is None:
                    consecutive_failures += 1
                    if consecutive_failures >= max_consecutive_failures:
                        if self.verbose_level >= 1:
                            print(f"[DataReceiver] Too many consecutive failures ({consecutive_failures}), stopping...")
                        break
                    continue
                else:
                    # Reset failure count on successful receive
                    consecutive_failures = 0
                    
                if frame is None:
                    continue

                # convert frame from RGB to BGR
                if frame is not None:
                    frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR) # type: ignore
                
                # package the data in a dictionary
                data = {
                    "frame": frame,
                    "camera_timestamp": server_data.get("camera_timestamp") if server_data else None,
                    "lidar_reading": server_data.get("lidar_reading") if server_data else None,
                    "lidar_timestamp": server_data.get("lidar_timestamp") if server_data else None
                }

                yield data
                
            except Exception as e:
                consecutive_failures += 1
                if self.verbose_level >= 1:
                    print(f"[DataReceiver] Error in get_data: {e}")
                if consecutive_failures >= max_consecutive_failures:
                    if self.verbose_level >= 1:
                        print(f"[DataReceiver] Too many consecutive errors, stopping...")
                    break

    def send_jeston_data(self, data):
        """
        Queue JSON formatted data to be sent to Jetson on the next recv() call.
        
        Args:
            data (dict): JSON-serializable dictionary to send to Jetson
            
        Example:
            receiver.send_jeston_data({"command": "add_roi", "rect": [100, 200, 300, 400]})

        """
        if not isinstance(data, dict):
            raise ValueError("Data must be a dictionary (JSON-serializable)")
        
        # Store the data to be sent on next recv() call
        self.jetson_data.update(data)
        
        if self.verbose_level >= 2:
            print(f"[DataReceiver] Queued data for Jetson: {data}")
            print(f"[DataReceiver] Total queued data: {self.jetson_data}")
    
    def send_command(self, command):
        """
        Send a structured command to Jetson.
        
        Args:
            command: Command object to send
        """
        command_dict = command.to_dict()
        self.send_jeston_data(command_dict)
        
        if self.verbose_level >= 2:
            print(f"[DataReceiver] Sent structured command: {command.action} (ID: {command.command_id})")
    
    def send_commands(self, commands):
        """
        Send multiple structured commands to Jetson.
        
        Args:
            commands: List of Command objects to send
        """
        for command in commands:
            self.send_command(command)
        
        if self.verbose_level >= 2:
            print(f"[DataReceiver] Sent {len(commands)} structured commands")
    
    def get_command_list(self):
        """
        Get the command list instance for creating structured commands.
        
        Returns:
            CommandList: The command list instance
        """
        return self.command_list
    
    def has_pending_data(self):
        """
        Check if there's data queued to be sent to Jetson.
        
        Returns:
            bool: True if there's data waiting to be sent
        """
        return bool(self.jetson_data)
    
    def clear_pending_data(self):
        """
        Clear any queued data without sending it.
        """
        if self.jetson_data:
            if self.verbose_level >= 2:
                print(f"[DataReceiver] Clearing queued data: {self.jetson_data}")
            self.jetson_data = {}
    
    def get_pending_data(self):
        """
        Get a copy of the currently queued data.
        
        Returns:
            dict: Copy of the data queued to be sent
        """
        return dict(self.jetson_data)

    def close(self):
        self.receiver.close()
