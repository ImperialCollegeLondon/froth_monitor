# import required libraries
from vidgear.gears import VideoGear

# debug codes
from jeston_api.lidar_data_stream import LidarDataStream
from jeston_api.video_sender import VideoSender

import time
from froth_monitor.logger_config import get_logger

# Initialize logger for this module
logger = get_logger(__name__)
# ---- Debug video source ----
# open any valid video stream(for e.g `test.mp4` file)
stream = VideoGear(source="dummy_video.mp4").start() # type: ignore

# ---- Jetson Network ----
# RECEIVER_NETWORK_ADDRESS = "10.42.0.85"
RECEIVER_NETWORK_ADDRESS = "localhost"  # Use localhost for testing on the same machine
RECEIVER_NETWORK_PORT = 5001

# ---- Camera Capture ----
CAM_RESOLUTION = (1280, 1024)  # Width, Height
CAM_FPS = 30
# no need to compress - NetGear will handle it
CAM_QUALITY = 100  # JPEG quality (0-100)

# ---- Lidar Data Stream ----
LIDAR_DEBUG = True  # Set to True to enable debug data stream


def main():
    # Initialize VideoSender
    video_sender = VideoSender(
        address=RECEIVER_NETWORK_ADDRESS, port=RECEIVER_NETWORK_PORT, verbose_level=2
    )

    # Initialize LidarDataStream
    lidar_stream = LidarDataStream(source="debug" if LIDAR_DEBUG else "real")

    try:
        print("[Main] Starting video stream...")
        lidar_stream = (
            lidar_stream.generate_debug_data()
            if LIDAR_DEBUG
            else lidar_stream.start_stream() # type: ignore
        )

        # Main loop to capture and send video frames
        while True:
            frame = stream.read()
            if frame is None:
                break

            lidar_timestamp, lidar_reading = next(lidar_stream)
            additional_info = {
                "camera_timestamp": time.time(),
                "lidar_timestamp": lidar_timestamp,
                "lidar_reading": lidar_reading,
            }
            if frame is not None:
                video_sender.send_frame(frame, message=additional_info)
            else:
                print("[Main] No frame captured.")

            time.sleep(1 / CAM_FPS)  # Control frame rate

    except KeyboardInterrupt:
        print("\n[Main] Shutting down...")
    finally:
        video_sender.close()

        print("[Main] Cleanup complete.")


if __name__ == "__main__":
    main()
