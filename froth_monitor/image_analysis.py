"""Video Analysis Module for Froth Tracker Application.

This module defines the `VideoAnalysisModule` class, which provides methods
for analyzing video frames using optical flow to calculate motion in a
specific direction. It supports calculating velocities, storing motion
history, and generating timestamps for each frame.

Classes:
--------
VideoAnalysisModule
    Provides functionality to process video frames and calculate motion
    velocities based on dense optical flow.

Imports:
--------
- cv2: For video frame processing and optical flow calculations.
- numpy: For mathematical operations and averaging flow data.
- random: For generating random colors for visualization.
- datetime: For timestamp generation.

Example Usage:
--------------
To use the module, instantiate the `VideoAnalysisModule` class with the
desired scrolling axis directions (`arrow_dir_x` and `arrow_dir_y`), and
call the `analyze` method on each video frame. Use `get_results` to retrieve
the velocity history.
"""

import cv2
import numpy as np
from cv2.typing import MatLike
from typing import cast


class VideoAnalysis:
    """
    Video Analysis Class for Motion Detection and Analysis.

    The `VideoAnalysisModule` class processes video frames to calculate
    motion velocities in a specific direction using dense optical flow.
    It stores velocity history, generates timestamps for each frame, and
    calculates motion relative to a specified scrolling axis.

    Attributes:
    ----------
    previous_frame : np.ndarray
        The last processed frame for motion analysis.
    velocity_history : list
        Stores the history of motion velocities and timestamps for each frame.
    color : tuple[int, int, int]
        A random RGB color for visualizing motion.
    current_velocity : float
        The most recent velocity calculated in the direction of the scrolling axis.
    arrow_dir_x : float
        The x component of the scrolling axis direction.
    arrow_dir_y : float
        The y component of the scrolling axis direction.

    Methods:
    -------
    __init__(arrow_dir_x: float, arrow_dir_y: float) -> None
        Initializes the VideoAnalysisModule with the given scrolling axis direction.
    analyze(current_frame: np.ndarray) -> tuple[float, float]
        Processes the current frame to calculate motion velocities using dense optical flow.
    get_current_velocity(avg_flow_x: float, avg_flow_y: float) -> float
        Calculates the velocity in the scrolling axis direction.
    get_current_time() -> str
        Returns the current timestamp in the format "dd/mm/yyyy HH:MM:SS.sss".
    get_frame_count() -> int
        Returns the total number of frames processed.
    get_results() -> list
        Retrieves the history of velocities and timestamps for all processed frames.
    generate_random_color() -> tuple[int, int, int]
        Generates a random RGB color.
    """

    def __init__(self, arrow_dir_x: float, arrow_dir_y: float) -> None:
        """
        Initialize the VideoAnalysisModule with the given direction for the scrolling axis.

        Parameters
        ----------
        arrow_dir_x : float
            The x direction for the scrolling axis (positive is right, negative is left).
        arrow_dir_y : float
            The y direction for the scrolling axis (positive is down, negative is up).
        """

        self.previous_frame = None  # Store the previous frame for motion analysis
        self.current_velocity = 0
        self.arrow_dir_x = arrow_dir_x
        self.arrow_dir_y = arrow_dir_y
        self.current_algorithm = "Farneback"  # or "lucas-kanade"

        self.lk_params = dict(
            winSize=(15, 15),
            maxLevel=2,
            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03),
        )

        self.of_params = dict(
            pyr_scale=0.5,
            levels=int(3),
            winsize=int(15),
            iterations=int(3),
            poly_n=int(7),
            poly_sigma=1.5,
        )

    def analyze(self, current_frame: np.ndarray) -> tuple[float, float]:
        if self.previous_frame is None:
            self.previous_frame = current_frame
            self.prev_pts = None
            return cast(float, None), cast(float, None)

        gray_current: MatLike = cv2.cvtColor(current_frame, cv2.COLOR_BGR2GRAY)
        gray_previous: MatLike = cv2.cvtColor(self.previous_frame, cv2.COLOR_BGR2GRAY)

        if self.current_algorithm == "Farneback":
            flow = cv2.calcOpticalFlowFarneback(
                prev=gray_previous,
                next=gray_current,
                flow=cast(MatLike, None),
                **self.of_params,  # type: ignore
                flags=0,
            )  # type: ignore

            flow_x = flow[..., 0]
            flow_y = flow[..., 1]
            avg_flow_x = cast(float, np.mean(flow_x))  # type: ignore
            avg_flow_y = cast(float, np.mean(flow_y))  # type: ignore

        elif self.current_algorithm == "Lucas-Kanade":
            if getattr(self, "prev_pts", None) is None:
                # Detect good features to track in the previous frame
                self.prev_pts = cv2.goodFeaturesToTrack(
                    gray_previous,
                    maxCorners=100,
                    qualityLevel=0.3,
                    minDistance=7,
                    blockSize=7,
                )

            if self.prev_pts is not None:
                next_pts, status, err = cv2.calcOpticalFlowPyrLK(
                    gray_previous,
                    gray_current,
                    self.prev_pts,
                    None, # type: ignore
                    **self.lk_params,  # type: ignore
                )  # type: ignore
                good_new = (
                    next_pts[status == 1] if next_pts is not None else np.array([])
                )
                good_old = (
                    self.prev_pts[status == 1]
                    if self.prev_pts is not None
                    else np.array([])
                )

                if len(good_new) > 0 and len(good_old) > 0:
                    flow_vectors = good_new - good_old
                    avg_flow_x = float(np.mean(flow_vectors[:, 0]))  # type: ignore
                    avg_flow_y = float(np.mean(flow_vectors[:, 1]))  # type: ignore

                else:
                    avg_flow_x, avg_flow_y = 0.0, 0.0
                self.prev_pts = (
                    good_new.reshape(-1, 1, 2) if len(good_new) > 0 else None
                )

            else:
                avg_flow_x, avg_flow_y = 0.0, 0.0
        else:
            raise ValueError(f"Unknown algorithm: {self.current_algorithm}")

        self.previous_frame = current_frame

        return avg_flow_x, avg_flow_y
