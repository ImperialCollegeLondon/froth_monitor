from vidgear.gears import NetGear
from typing import cast
import numpy as np
import time


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
        self.connection_active = True
        self.retry_count = 0
        self.max_retries = 3

        # activate Bidirectional mode
        options = {"bidirectional_mode": True}

        # Define NetGear Client at given IP address and define parameters 
        # !!! change following IP address '192.168.x.xxx' with yours !!!
        try:
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
                print(f"[VideoReceiver] Initialized NetGear client at {self.client_ip}:{self.client_port} with options: {options}")
                
        except Exception as e:
            print(f"[VideoReceiver] Failed to initialize NetGear client: {e}")
            self.connection_active = False
            self.client = None

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
        if not self.connection_active or self.client is None:
            if self.verbose_level >= 1:
                print("[VideoReceiver] Connection not active, returning None")
            return cast(dict, None), cast(np.ndarray, None)
        
        try:
            # In bidirectional mode, recv() returns the frame and send() data is passed via message
            if message is not None:
                # Send message back to server and receive frame+data
                data = self.client.recv(return_data=message)
            else:
                # Just receive data from server
                data = self.client.recv()

            if self.verbose_level >= 5:
                print("[VideoReceiver] Data received from server. length:", len(data) if data else "None")
            
            # Reset retry count on successful receive
            self.retry_count = 0
            
            if data is None:
                if self.verbose_level >= 2:
                    print("[VideoReceiver] Received None data from server")
                return cast(dict, None), cast(np.ndarray, None)

            # NetGear in bidirectional mode returns (frame, message) tuple
            if isinstance(data, tuple) and len(data) == 2:
                frame, server_data = data
                
                # Additional validation for frame data
                if frame is None:
                    if self.verbose_level >= 2:
                        print("[VideoReceiver] Received None frame from server")
                    return cast(dict, server_data), cast(np.ndarray, None)
                    
                return cast(dict, server_data), cast(np.ndarray, frame)
            else:
                # Fallback - assume it's just the frame
                if data is None:
                    if self.verbose_level >= 2:
                        print("[VideoReceiver] Received None frame data")
                    return {}, cast(np.ndarray, None)
                return {}, cast(np.ndarray, data)
                
        except Exception as e:
            self.retry_count += 1
            if self.verbose_level >= 1:
                print(f"[VideoReceiver] Error receiving data (attempt {self.retry_count}/{self.max_retries}): {e}")
            
            # If we've exceeded max retries, mark connection as inactive
            if self.retry_count >= self.max_retries:
                if self.verbose_level >= 1:
                    print(f"[VideoReceiver] Max retries exceeded, marking connection as inactive")
                self.connection_active = False
                
            # Wait a bit before next attempt
            time.sleep(0.1)
            return cast(dict, None), cast(np.ndarray, None)
    
    def close(self):
        """
        Safely close the NetGear client.
        """
        if self.verbose_level >= 2:
            print("[VideoReceiver] Closing NetGear client...")

        self.connection_active = False
        
        if self.client is not None:
            try:
                self.client.close()
            except Exception as e:
                if self.verbose_level >= 1:
                    print(f"[VideoReceiver] Error closing client: {e}")

        if self.verbose_level >= 2:
            print("[VideoReceiver] NetGear client closed.")
