from vidgear.gears import NetGear
from typing import cast
import numpy as np


class VideoReceiver:
    """
    This script demonstrates how to receive video frames and data from a server using NetGear.
    This is the client. It receives data. The ip address is the address of itself.
    It activates the bidirectional mode, allowing both sending and receiving of data.
    """

    def __init__(self, client_address, client_port=5454, request_timeout = 60, verbose_level=0):
        self.client_ip = client_address
        self.client_port = client_port
        self.verbose_level = verbose_level
        self.request_timeout = request_timeout

        # activate Bidirectional mode
        options = {"bidirectional_mode": True}

        # Define NetGear Client at given IP address and define parameters 
        # !!! change following IP address '192.168.x.xxx' with yours !!!
        self.client = NetGear(
            address=self.client_ip,
            port=self.client_port,
            protocol="tcp",
            pattern=1,
            receive_mode=True,
            request_timeout=self.request_timeout,
            logging=True,
            **options
        )

        if self.verbose_level >= 2:
            print(f"[VideoSender] Initialized NetGear server at {self.client_ip}:{self.client_port} with options: {options}")


    def recv(self, message=None):
        """
        Receive data from the server. In bidirectional mode, can also send data back to server.
        
        Args:
            message: Optional data to send back to the server
            
        Returns:
            tuple: (server_data, frame) where server_data is dict and frame is numpy array
        
        Example usage:
        client = VideoReceiver(server_ip="192.168.x.xxx", server_port=5555, verbose_level=2)
        server_data, frame = client.recv()
        # or send data back:
        server_data, frame = client.recv(message={"command": "adjust_settings"})
        """
        # In bidirectional mode, recv() returns the frame and send() data is passed via message
        if message is not None:
            # Send message back to server and receive frame+data
            data = self.client.recv(return_data=message)
        else:
            # Just receive data from server
            data = self.client.recv()

        if self.verbose_level >= 5:
            print("[VideoReceiver] Data received from server. length:", len(data) if data else "None")
        
        if data is None:
            return cast(dict, None), cast(np.ndarray, None)

            
        # NetGear in bidirectional mode returns (frame, message) tuple
        if isinstance(data, tuple) and len(data) == 2:
            frame, server_data = data
            return cast(dict, server_data), cast(np.ndarray, frame)

        else:
            # Fallback - assume it's just the frame
            return {}, cast(np.ndarray, data)

    
    def close(self):
        """
        Safely close the NetGear client.
        """
        if self.verbose_level >= 2:
            print("[VideoReceiver] Closing NetGear client...")

        self.client.close()

        if self.verbose_level >= 2:
            print("[VideoReceiver] NetGear client closed.")
