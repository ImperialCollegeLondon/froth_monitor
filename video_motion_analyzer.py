#!/usr/bin/env python3
"""
Simple Video Motion Analyzer

This script uses the VideoAnalysis module to analyze motion in video files
and print delta information (optical flow data) to the terminal.

Usage:
    python video_motion_analyzer.py <video_file_path>
"""

import cv2
import sys
import os
from froth_monitor.image_analysis import VideoAnalysis


def analyze_video_motion(video_path: str, arrow_dir_x: float = 1.0, arrow_dir_y: float = 0.0):
    """
    Analyze motion in a video file and print delta information to terminal.
    
    Args:
        video_path (str): Path to the video file
        arrow_dir_x (float): X direction for motion analysis (default: 1.0 - rightward)
        arrow_dir_y (float): Y direction for motion analysis (default: 0.0 - no vertical preference)
    """
    
    # Check if video file exists
    if not os.path.exists(video_path):
        print(f"Error: Video file '{video_path}' not found.")
        return
    
    # Initialize video capture
    cap = cv2.VideoCapture(video_path)
    
    if not cap.isOpened():
        print(f"Error: Could not open video file '{video_path}'.")
        return
    
    # Get video properties
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    print(f"Video Info:")
    print(f"  File: {video_path}")
    print(f"  Resolution: {width}x{height}")
    print(f"  FPS: {fps:.2f}")
    print(f"  Total Frames: {total_frames}")
    print(f"  Duration: {total_frames/fps:.2f} seconds")
    print(f"\nMotion Analysis (Arrow Direction: X={arrow_dir_x}, Y={arrow_dir_y}):")
    print(f"{'Frame':<8} {'Time(s)':<10} {'Flow_X':<12} {'Flow_Y':<12} {'Magnitude':<12}")
    print("-" * 60)
    
    # Initialize video analysis module
    analyzer = VideoAnalysis(arrow_dir_x, arrow_dir_y)
    
    frame_count = 0
    
    try:
        while True:
            ret, frame = cap.read()
            
            if not ret:
                break
            
            # Analyze motion in current frame
            flow_x, flow_y = analyzer.analyze(frame)
            
            # Calculate time and magnitude
            current_time = frame_count / fps if fps > 0 else 0
            
            if flow_x is not None and flow_y is not None:
                magnitude = (flow_x**2 + flow_y**2)**0.5
                
                print(f"{frame_count:<8} {current_time:<10.2f} {flow_x:<12.4f} {flow_y:<12.4f} {magnitude:<12.4f}")
            else:
                print(f"{frame_count:<8} {current_time:<10.2f} {'N/A':<12} {'N/A':<12} {'N/A':<12}")
            
            frame_count += 1
            
            # Optional: Show progress for long videos
            if frame_count % 100 == 0:
                progress = (frame_count / total_frames) * 100
                print(f"  Progress: {progress:.1f}%")
    
    except KeyboardInterrupt:
        print("\nAnalysis interrupted by user.")
    
    finally:
        cap.release()
        print(f"\nAnalysis complete. Processed {frame_count} frames.")


def main():
    """
    Main function to handle command line arguments and run video analysis.
    """
    if len(sys.argv) < 2:
        print("Usage: python video_motion_analyzer.py <video_file_path> [arrow_dir_x] [arrow_dir_y]")
        print("\nExample:")
        print("  python video_motion_analyzer.py video.mp4")
        print("  python video_motion_analyzer.py video.mp4 1.0 0.0  # Analyze rightward motion")
        print("  python video_motion_analyzer.py video.mp4 0.0 1.0  # Analyze downward motion")
        sys.exit(1)
    
    video_path = sys.argv[1]
    
    # Parse optional direction arguments
    arrow_dir_x = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
    arrow_dir_y = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0
    
    analyze_video_motion(video_path, arrow_dir_x, arrow_dir_y)


if __name__ == "__main__":
    main()