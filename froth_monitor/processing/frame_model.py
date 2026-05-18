"""Frame Model Module for Froth Tracker Application.

This module defines the FrameModel class, which processes video frames,
tracks frame numbers, and manages ROI processing.
"""

import numpy as np
import cv2
import threading
import logging
from PySide6.QtCore import QObject, Signal
from typing import TYPE_CHECKING
from datetime import datetime
from PySide6.QtCore import QRect
from froth_monitor.processing.roi import ROI

if TYPE_CHECKING:
    from froth_monitor.handlers.realtime_export import RealtimeExporter

logger = logging.getLogger(__name__)


class FrameModel(QObject):
    """
    Frame Model Class for Video Frame Processing.

    The `FrameModel` class processes video frames passed from the event handler,
    tracks frame sequence numbers, and provides a foundation for additional
    image processing capabilities.

    Attributes:
    ----------
    frame_count : int
        Counter for the number of frames processed.
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
    get_current_time() -> str
        Returns the current timestamp in the format "dd/mm/yyyy HH:MM:SS.sss".
    """
    initialize_roi_sheets = Signal(list)
    release_roi_movement_data = Signal(int, list)
    create_roi_sheets = Signal(int)
    delete_roi_sheets = Signal(int)

    def __init__(self) -> None:
        """
        Initialize the FrameModel with default values.
        """
        super().__init__()
        
        self.frame_count = 0

        self.export_enable = False
        self.exporter: 'RealtimeExporter | None' = None

        self.roi_list: list[ROI] = []
        self.last_processed_time: str | None = None
        
        # Thread safety: Lock for protecting roi_list and algorithm parameters
        self._processing_lock = threading.RLock()

        self.px2mm = 1.0
        self.degree = -90.0

        # Algorithm parameters
        self.current_algorithm = "DIS"
        self.algorithm_list = ["Farneback", "Lucas-Kanade", "DIS"]
        
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
        self.dis_params = dict(
            preset="Medium"
        )

    def confirm_algorithm_n_params(self, algorithm: str, params: dict) -> None:
        """
        Confirm the algorithm and parameters for optical flow.
        
        This method is thread-safe and can be called while video processing is active.

        Parameters
        ----------
        algorithm : str
            The algorithm to use for optical flow.
        params : dict
            The parameters for the optical flow algorithm.
        """
        # Acquire lock to prevent race condition with process_frame()
        with self._processing_lock:
            self.current_algorithm = algorithm

            if algorithm == "Farneback":
                self.of_params = params
            elif algorithm == "Lucas-Kanade":
                self.lk_params = params
            elif algorithm == "DIS":
                self.dis_params = params

            # Update all existing ROIs with the new algorithm and parameters
            for roi in self.roi_list:
                roi.get_algorithm_n_params(algorithm, params)

            logger.info(f"Frame model: Algorithm set as: {self.current_algorithm}, Parameters: {params}")
            self.algo_roi.get_algorithm_n_params(self.current_algorithm, params)

    def process_frame(self, frame: np.ndarray) -> tuple[int, list[ROI], bool, bool]:
        """
        Process a video frame, increment the frame counter, and return the frame number
        along with the processed frame. For each ROI in the roi_list, crop the frame
        according to the ROI coordinates and pass the cropped frame to the ROI's
        process_frame method.
        
        This method is thread-safe and protected against concurrent algorithm parameter changes.

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
            return None, None, False, False

        # Increment the frame counter
        self.frame_count += 1

        # Record the current time
        current_time = self.get_current_time()
        self.last_processed_time = current_time

        if_new_velo = 0
        if_new_average = 0
        update_velo_plot = False
        update_average_velo = False

        # Acquire lock to prevent race condition with confirm_algorithm_n_params()
        with self._processing_lock:
            # Process each ROI in the roi_list
            for roi_id, roi in enumerate(self.roi_list):
                roi.id = roi_id + 1

                # Get the ROI coordinates
                if roi.coordinate is None:
                    continue
                x1 = roi.coordinate[0]
                y1 = roi.coordinate[1]
                x2 = roi.coordinate[2]
                y2 = roi.coordinate[3]

                # Crop the frame according to the ROI coordinates
                # Ensure the coordinates are within the frame boundaries
                if x1 >= 0 and y1 >= 0 and x2 > 0 and y2 > 0:
                    cropped_frame = frame[y1 : y1 + y2, x1 : x1 + x2]

                    # Pass the cropped frame to the ROI's process_frame method
                    _new_velo, _new_average = roi.process_frame(cropped_frame)
                    if _new_velo:
                        if_new_velo += 1
                    if _new_average:
                        if_new_average += 1
                
                if self.export_enable:
                    if len(roi.delta_history)>1:
                        self.release_roi_movement_data.emit(roi.id, roi.delta_history[-1])
                        # self.exporter.write_roi_movement_data(roi.id, roi.delta_history[-1])

            if if_new_velo > 0:
                update_velo_plot = True
            if if_new_average > 0:
                update_average_velo = True
        
        # print("time to process a frame: ", time.time() - time_1, "s")
        return self.frame_count, self.roi_list, update_velo_plot, update_average_velo

    def initialize_algo_config(self):
        roi = QRect(0, 0, 0, 0)
        self.algo_roi = ROI(1, 1)
        self.algo_roi.set_processing_coordinate(roi) # type: ignore
        self.algo_roi.get_algorithm_n_params(self.current_algorithm, self.of_params)

    def process_frame_for_algo_config(self, frame: np.ndarray) -> tuple[float, float] | None:
        """Process frame for algorithm configuration."""
        self.algo_roi.process_frame(frame)
        return self.algo_roi.delta_pixels

    def get_frame_count(self) -> int:
        """
        Return the total number of frames processed.

        Returns
        -------
        int
            The number of frames processed.
        """
        return self.frame_count

    def get_current_time(self) -> str:
        """
        Return the current time in the format dd/mm/yyyy HH:MM:SS.sss.

        Returns
        -------
        str
            The current time as a string.
        """
        return datetime.now().strftime("%d/%m/%Y %H:%M:%S.%f")[:-3]

    def get_px_to_mm(self, px_ratio: float) -> None:
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
        self.px2mm = px_ratio
        logger.info(f"Frame model: px2mm set as: {self.px2mm}")

    def get_overflow_direction(self, degree: float) -> None:
        self.degree = degree

    def add_roi(self):
        new_roi = ROI(self.px2mm, self.degree)
        
        # Select the correct parameters based on the current algorithm
        if self.current_algorithm == "Farneback":
            params = self.of_params
        elif self.current_algorithm == "Lucas-Kanade":
            params = self.lk_params
        elif self.current_algorithm == "DIS":
            params = self.dis_params
        else:
            params = self.of_params # Default fallback
            
        new_roi.get_algorithm_n_params(self.current_algorithm, params)
        
        self.roi_list.append(new_roi)

        if self.export_enable:
            logger.info(f"Frame model: Release signal to create ROI sheets of number: {len(self.roi_list)}")
            self.create_roi_sheets.emit(len(self.roi_list))

        return new_roi
        
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

        if self.export_enable:
            logger.info(f"Frame model: Release signal to delete ROI sheets for {len(self.roi_list)} ROIs")
            self.delete_roi_sheets.emit(len(self.roi_list))

        # Remove the last ROI from the list
        self.roi_list.pop()

        return True

    def update_export_status(self, status: bool):

        if len(self.roi_list) > 0 and status:
            if status:
                self.initialize_roi_sheets.emit(self.roi_list)
        self.export_enable = status
        logger.info(f"Frame model: Export status set to {self.export_enable}")

    # def load_exporter(self, exporter: 'RealtimeExporter'):
    #     self.exporter = exporter
        
    #     if len(self.roi_list) > 0 :
    #         self.exporter.initialize_roi_sheets(self.roi_list)

    def reset(self):
        self.frame_count = 0

        self.roi_list = []
