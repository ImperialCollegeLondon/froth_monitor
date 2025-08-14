# pc_connection_client.py
import socket
import json
import time
from typing import Optional, Tuple


class UdpConnectionClient:
    """
    UDP-based connection client for PC.
    Discovers Jetson Nano on network and establishes handshake for communication.
    """
    
    def __init__(self, discovery_port: int = 9999, broadcast_timeout: float = 5.0):
        """
        Initialize the connection client.
        
        Args:
            discovery_port: Port for UDP discovery broadcasts
            broadcast_timeout: Timeout for discovery response
        """
        self.discovery_port = discovery_port
        self.broadcast_timeout = broadcast_timeout
        self.jetson_ip: Optional[str] = None
        self.agreed_port: Optional[int] = None
    
    def discover_jetson(self, retries: int = 3) -> Tuple[Optional[str], Optional[int]]:
        """
        Discover Jetson Nano on the network via UDP broadcast.
        
        Args:
            retries: Number of discovery attempts
            
        Returns:
            Tuple[Optional[str], Optional[int]]: (jetson_ip, agreed_port) if found, (None, None) if not
        """
        print(f"[ConnectionClient] Searching for Jetson Nano on network...")

        # List of possible mDNS hostnames to try
        hostnames = [
            "localhost",    # DEBUG only!
            "frothMonitor.local",
            "jetson.local",
            "ubuntu.local"
        ]
        for attempt in range(retries):
            print(f"[ConnectionClient] Discovery attempt {attempt + 1}/{retries}")
        
            for hostname in hostnames:
                print(f"[ConnectionClient] Trying hostname: {hostname}")
                
                try:
                    # Resolve hostname to IP address
                    jetson_ip = socket.gethostbyname(hostname)
                    print(f"[ConnectionClient] Resolved {hostname} -> {jetson_ip}")
                    
                    # Create UDP socket for direct communication
                    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    sock.settimeout(self.broadcast_timeout)
                    
                    # Send discovery message directly to the resolved IP
                    message = "DISCOVER_JETSON"
                    sock.sendto(message.encode(), (jetson_ip, self.discovery_port))
                    print(f"[ConnectionClient] Direct message sent to {jetson_ip}:{self.discovery_port}")
                    
                    # Wait for response
                    try:
                        data, addr = sock.recvfrom(1024)
                        response = json.loads(data.decode())
                        responded_ip = response.get('jetson_ip')
                        agreed_port = response.get('agreed_port')
                        
                        if responded_ip and agreed_port:
                            print(f"[ConnectionClient] Found Jetson at {responded_ip}:{agreed_port} (via {hostname})")
                            print(f"[ConnectionClient] Handshake complete!")
                            
                            self.jetson_ip = responded_ip
                            self.agreed_port = agreed_port
                            
                            sock.close()
                            return responded_ip, agreed_port
                        else:
                            print(f"[ConnectionClient] Invalid response from {addr}: {response}")
                            
                    except socket.timeout:
                        print(f"[ConnectionClient] No response from {hostname} ({jetson_ip})")
                    except json.JSONDecodeError as e:
                        print(f"[ConnectionClient] Invalid JSON response from {hostname}: {e}")
                    
                    sock.close()
                        
                except socket.gaierror:
                        print(f"[ConnectionClient] Could not resolve hostname: {hostname}")
                        continue
                except Exception as e:
                    print(f"[ConnectionClient] Error with {hostname}: {e}")
                    if 'sock' in locals():
                        sock.close()
                    continue
                
            # Wait before next attempt if we didn't find anything
            if attempt < retries - 1:
                print(f"[ConnectionClient] No Jetson found in attempt {attempt + 1}, retrying...")
                time.sleep(1)
        
        print(f"[ConnectionClient] Jetson not found after {retries} attempts using mDNS")
        print(f"[ConnectionClient] Make sure:")
        print(f"[ConnectionClient]   1. Jetson has mDNS enabled (avahi-daemon)")
        print(f"[ConnectionClient]   2. Jetson hostname is set to one of: {', '.join(hostnames)}")
        print(f"[ConnectionClient]   3. Both devices are on the same network")
        return None, None
    


    def discover_jetson_broadcast(self, retries: int = 3) -> Tuple[Optional[str], Optional[int]]:
        """
        [Backup function] usually we would know the jetson's mDNS (e.g. jetson.local)
        Discover Jetson Nano on the network via UDP broadcast.
        
        Args:
            retries: Number of discovery attempts
            
        Returns:
            Tuple[Optional[str], Optional[int]]: (jetson_ip, agreed_port) if found, (None, None) if not
        """
        print(f"[ConnectionClient] Searching for Jetson Nano on network...")
        
        for attempt in range(retries):
            print(f"[ConnectionClient] Discovery attempt {attempt + 1}/{retries}")
            
            try:
                # Create UDP socket for broadcasting
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                sock.settimeout(self.broadcast_timeout)
                
                # Send discovery broadcast
                message = "DISCOVER_JETSON"
                sock.sendto(message.encode(), ('<broadcast>', self.discovery_port))
                print(f"[ConnectionClient] Broadcast sent on port {self.discovery_port}")
                
                # Wait for response
                try:
                    data, addr = sock.recvfrom(1024)
                    response = json.loads(data.decode())
                    jetson_ip = response.get('jetson_ip')
                    agreed_port = response.get('agreed_port')
                    
                    if jetson_ip and agreed_port:
                        print(f"[ConnectionClient] Found Jetson at {jetson_ip}:{agreed_port}")
                        print(f"[ConnectionClient] Handshake complete!")
                        
                        self.jetson_ip = jetson_ip
                        self.agreed_port = agreed_port
                        
                        sock.close()
                        return jetson_ip, agreed_port
                    else:
                        print(f"[ConnectionClient] Invalid response from {addr}: {response}")
                        
                except socket.timeout:
                    print(f"[ConnectionClient] No response received (timeout: {self.broadcast_timeout}s)")
                except json.JSONDecodeError as e:
                    print(f"[ConnectionClient] Invalid JSON response: {e}")
                
                sock.close()
                
                # Wait before next attempt
                if attempt < retries - 1:
                    time.sleep(1)
                    
            except Exception as e:
                print(f"[ConnectionClient] Discovery error: {e}")
                if 'sock' in locals():
                    sock.close()
        
        print(f"[ConnectionClient] Jetson not found after {retries} attempts")
        return None, None
    

    
    def get_jetson_address(self) -> Tuple[Optional[str], Optional[int]]:
        """
        Get the discovered Jetson address and agreed port.
        
        Returns:
            Tuple[Optional[str], Optional[int]]: (jetson_ip, agreed_port)
        """
        return self.jetson_ip, self.agreed_port
    
    def is_connected(self) -> bool:
        """Check if connection to Jetson has been established."""
        return self.jetson_ip is not None and self.agreed_port is not None


def discover_and_connect(retries: int = 3, timeout: float = 5.0) -> Tuple[Optional[str], Optional[int]]:
    """
    Convenience function to discover Jetson and get connection details.
    
    Args:
        retries: Number of discovery attempts
        timeout: Timeout for each discovery attempt
        
    Returns:
        Tuple[Optional[str], Optional[int]]: (jetson_ip, agreed_port) if found, (None, None) if not
    """
    client = UdpConnectionClient(broadcast_timeout=timeout)
    return client.discover_jetson(retries=retries)


# Example usage and testing (generated by Sonnet4)
if __name__ == "__main__":
    print("=== PC Connection Client Test ===")
    
    # # Method 1: Using the class
    # client = UdpConnectionClient(broadcast_timeout=3.0)
    # jetson_ip, port = client.discover_jetson(retries=3)
    
    # if jetson_ip and port:
    #     print(f"\n✅ Success! Jetson found at {jetson_ip}:{port}")
    #     print(f"You can now connect to the Jetson using this address for data communication.")
    # else:
    #     print("\n❌ No Jetson found on network")
    #     print("Make sure:")
    #     print("1. Jetson is running the connection listener")
    #     print("2. Both devices are on the same network")
    #     print("3. Firewall is not blocking UDP traffic on port 9999")
    
    # print("\n" + "="*50)
    
    # Method 2: Using convenience function
    print("Testing convenience function...")
    jetson_ip, port = discover_and_connect(retries=2, timeout=2.0)
    
    if jetson_ip:
        print(f"✅ Convenience function also found Jetson at {jetson_ip}:{port}")
    else:
        print("❌ Convenience function did not find Jetson")