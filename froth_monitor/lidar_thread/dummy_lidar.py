import os
import pty
import time
import random

def main():
    """
    Simulate a LiDAR device by creating a virtual serial port (PTY) 
    and streaming random distance data.
    """
    # Create a pseudo-terminal pair
    master, slave = pty.openpty()
    s_name = os.ttyname(slave)
    
    print("Dummy LiDAR started.")
    print(f"Connect to this serial port: {s_name}")
    print("Press Ctrl+C to stop.")

    try:
        while True:
            # Generate smooth sine wave data to simulate froth level
            # Period: 10 seconds, Amplitude: 0.5m, Base: 1.5m
            t = time.time()
            frequency = 0.1  # Hz (10s period)
            amplitude = 0.2  # meters
            base_dist = 0.2  # meters
            
            import math
            distance_m = base_dist + amplitude * math.sin(2 * math.pi * frequency * t)
            
            # Add small noise (1mm)
            noise = (random.random() - 0.5) * 0.002
            distance_m += noise
            
            # Format: D=X.XXXm
            # Example: D=1.234m
            data = f"D={distance_m:.3f}m\r\n"
            
            # Write to the master device
            os.write(master, data.encode('ascii'))
            
            # Print to console for verification
            print(f"Sent: {data.strip()}")
            
            # 30Hz update rate -> ~0.0333 seconds
            time.sleep(1.0/30.0)
            
    except KeyboardInterrupt:
        print("\nStopping Dummy LiDAR...")
    except OSError as e:
        print(f"\nError: {e}")
    finally:
        # Close the file descriptors
        try:
            os.close(master)
            os.close(slave)
        except Exception:
            pass
        print("Disconnected.")

if __name__ == "__main__":
    main()
