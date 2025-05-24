"""Frame Model Module for Froth Tracker Application.

This module defines the `FrameModel` class, which processes video frames passed from the
event handler. It tracks frame sequence numbers and can be extended to perform additional
image processing on each frame or consecutive frames.

Classes:
--------
FrameModel
    Processes video frames, tracks frame numbers, and provides a foundation for
    additional image processing capabilities.

Imports:
--------
- cv2 (OpenCV): For image processing operations.
- numpy: For numerical operations on frame data.
- datetime: For timestamp generation.

Example Usage:
--------------
To use the module, instantiate the `FrameModel` class, and call the `process_frame`
method on each video frame received from the event handler.

```python
from fm_model import FrameModel

# Initialize the frame model
frame_model = FrameModel()

# Process each frame
frame_number, processed_frame = frame_model.process_frame(current_frame)
print(f"Processing frame {frame_number}")
```
"""

import numpy as np
import time
from datetime import datetime
from PySide6.QtCore import QRect
from froth_monitor.image_analysis import VideoAnalysis


class ROI:
    def __init__(self, roi_coordinate: QRect, px2mm, degree) -> None:
        self.coordinate = roi_coordinate
        self.analysis = VideoAnalysis(0, 0)

        self.delta_pixels = None
        self.cross_position = None

        self.delta_history = []
        self.arrow_dir = 0.0
        self.px2mm = px2mm
        self.mm2px = 1 / px2mm
        self.degree = degree

        # Initialize timestamp
        self.timestamp = time.strftime("%H:%M:%S", time.localtime())
        self.timestamp_buffer = self.timestamp
        self.current_velocity = 0.0
        self.velo_only_history = []

    def process_frame(self, frame: np.ndarray) -> None:
        """
        Process a cropped frame using the VideoAnalysis.analyze function and store the results.

        Parameters
        ----------
        frame : np.ndarray
            The cropped video frame to process.
        """

        self.delta_pixels = self.analysis.analyze(frame)

        if self.delta_pixels is None:
            return None

        self.calibrated_delta = self.calculate_real_delta(self.delta_pixels)

        # Update timestamp
        self.timestamp = time.strftime("%H:%M:%S", time.localtime())
        self.calculate_velocity(self.calibrated_delta)
        self.delta_history.append(
            [self.timestamp, self.delta_pixels, self.calibrated_delta, None]
        )
        # self.calculate_velocity(self.calibrated_delta)

    def calculate_real_delta(self, delta_pixels):
        """
        Calculate the projection of delta_pixels onto the direction specified by self.degree.

        Parameters
        ----------
        delta_pixels : tuple or list
            A tuple or list containing (x, y) movement in pixels, where positive x means
            movement to the right and positive y means movement downward.

        Returns
        -------
        float
            The projected velocity in the direction of self.degree in mm/frame.
        """

        import math

        # Convert degree to radians
        rad = math.radians(self.degree)

        # Create a unit vector in the direction of self.degree
        # Note: In the coordinate system, 0 degrees points right, and angles increase counterclockwise
        # But y-axis is inverted (positive y is downward), so we need to negate the y component
        direction_x = math.cos(rad)
        direction_y = -math.sin(rad)  # Negative because positive y is downward

        # Extract delta_x and delta_y from delta_pixels
        delta_x, delta_y = delta_pixels

        # Calculate the dot product (projection)
        projection = delta_x * direction_x + delta_y * direction_y

        # Convert from pixels to millimeters
        projection_mm = projection * self.mm2px

        return projection_mm

    def calculate_velocity(self, delta):
        if self.timestamp == self.timestamp_buffer:
            self.current_velocity += delta

        else:
            self.timestamp_buffer = self.timestamp
            self.delta_history[-1][-1] = self.current_velocity
            self.velo_only_history.append(self.current_velocity)
            self.current_velocity = delta


class FrameModel:
    """
    Frame Model Class for Video Frame Processing.

    The `FrameModel` class processes video frames passed from the event handler,
    tracks frame sequence numbers, and provides a foundation for additional
    image processing capabilities.

    Attributes:
    ----------
    frame_count : int
        Counter for the number of frames processed.
    frame_history : list
        Stores information about processed frames.
    last_processed_time : datetime
        Timestamp of the last processed frame.

    Methods:
    -------
    __init__() -> None
        Initializes the FrameModel with default values.
    process_frame(frame: np.ndarray) -> tuple[int, np.ndarray]
        Processes a video frame and returns its sequence number and the processed frame.
    get_frame_count() -> int
        Returns the total number of frames processed.
    get_frame_history() -> list
        Returns the history of processed frames.
    get_current_time() -> str
        Returns the current timestamp in the format "dd/mm/yyyy HH:MM:SS.sss".
    """

    def __init__(self) -> None:
        """
        Initialize the FrameModel with default values.
        """
        self.frame_count = 0
        self.frame_history = []

        self.roi_list = []
        self.last_processed_time = None

        self.px2mm = 1.0
        self.degree = -90.0

    def process_frame(self, frame: np.ndarray):
        """
        Process a video frame, increment the frame counter, and return the frame number
        along with the processed frame. For each ROI in the roi_list, crop the frame
        according to the ROI coordinates and pass the cropped frame to the ROI's
        process_frame method.

        Parameters
        ----------
        frame : np.ndarray
            The video frame to process.

        Returns
        -------
        tuple[int, np.ndarray]
            A tuple containing the frame number and the processed frame.
        """
        if frame is None:
            return None, None

        # Increment the frame counter
        self.frame_count += 1

        # Record the current time
        current_time = self.get_current_time()
        self.last_processed_time = current_time

        # Store frame information in history
        self.frame_history.append(
            {"frame_number": self.frame_count, "timestamp": current_time}
        )

        # Process each ROI in the roi_list
        for roi in self.roi_list:
            # Get the ROI coordinates
            x1 = roi.coordinate[0]
            y1 = roi.coordinate[1]
            x2 = roi.coordinate[2]
            y2 = roi.coordinate[3]

            # Crop the frame according to the ROI coordinates
            # Ensure the coordinates are within the frame boundaries
            if x1 >= 0 and y1 >= 0 and x2 > 0 and y2 > 0:
                cropped_frame = frame[y1 : y1 + y2, x1 : x1 + x2]

                # Pass the cropped frame to the ROI's process_frame method
                roi.process_frame(cropped_frame)

        return self.frame_count, self.roi_list

    def get_frame_count(self) -> int:
        """
        Return the total number of frames processed.

        Returns
        -------
        int
            The number of frames processed.
        """
        return self.frame_count

    def get_frame_history(self) -> list:
        """
        Return the history of processed frames.

        Returns
        -------
        list
            A list of dictionaries containing information about each processed frame.
        """
        return self.frame_history

    def get_current_time(self) -> str:
        """
        Return the current time in the format dd/mm/yyyy HH:MM:SS.sss.

        Returns
        -------
        str
            The current time as a string.
        """
        return datetime.now().strftime("%d/%m/%Y %H:%M:%S.%f")[:-3]

    def get_px_to_mm(self, px: float) -> None:
        """
        Convert a distance in pixels to millimeters.

        Parameters
        ----------
        px : int
            The distance in pixels.

        Returns
        -------
        float
            The distance in millimeters.
        """

        # pixels of 20mm
        self.px2mm = px / 20

    def get_overflow_direction(self, degree: float) -> None:
        self.degree = degree

    def add_roi(self, roi):
        new_roi = ROI(roi, self.px2mm, self.degree)
        self.roi_list.append(new_roi)

    def delete_last_roi(self):
        """
        Delete the last ROI from the roi_list and release its memory.

        Returns
        -------
        bool
            True if an ROI was successfully deleted, False if the roi_list was empty.
        """
        if not self.roi_list:
            return False

        # Remove the last ROI from the list
        self.roi_list.pop()

        return True
