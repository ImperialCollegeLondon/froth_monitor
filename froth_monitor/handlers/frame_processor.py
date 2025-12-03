import cv2
import queue
from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QImage, QPixmap

# Import MainGUIWindow at the beginning
from froth_monitor.handlers.gui_window import MainGUIWindow

# Import FrameModel from fm_model module
from froth_monitor.processing.fm_model import FrameModel, ROI
from froth_monitor.utils.performance_monitor import PerformanceMonitor

# Import the camera and network threads
from froth_monitor.video_threads.camera_thread import CameraThread
from froth_monitor.video_threads.network_thread import NetworkThread


# Import the video recorder module
from froth_monitor.handlers.video_recorder import VideoRecorder
# from froth_monitor.event_handler import EventHandler
from froth_monitor.handlers.logger_config import get_logger



from froth_monitor.handlers.overlay_widget import OverlayWidget
from froth_monitor.handlers.roi_handler import ROIHandler
from froth_monitor.handlers.recorder_thread import VideoRecordingWorker 
from froth_monitor.handlers.video_recorder import VideoRecorder
from froth_monitor.handlers.data_handler import DataHandler

# Initialize logger for this module
logger = get_logger(__name__)

class FrameProcessor:
    def __init__(
        self,
        event_handler,
        gui: MainGUIWindow,
        frame_model: FrameModel,
        video_thread: CameraThread | NetworkThread,
        overlay_widget: OverlayWidget,
        video_recorder: VideoRecorder,
        roi_handler: ROIHandler,
        velocity_plotter: DataHandler,
    ):
        self.gui = gui
        self.event_handler = event_handler
        self.playing = True # Set to True by default, frame processor can only be initialised when the video is playing
        self.frame_model = frame_model
        self.video_thread = video_thread
        self.overlay_widget = overlay_widget
        self.video_recorder = video_recorder
        self.roi_handler = roi_handler
        self.velocity_plotter = velocity_plotter

        self.canvas_width = self.gui.video_canvas_label.width()
        self.canvas_height = self.gui.video_canvas_label.height()
        
        # Initialize and start the video recording worker thread
        self.video_queue = queue.Queue(maxsize=30)
        self.video_recording_worker = VideoRecordingWorker(
            self.video_recorder, self.video_queue
        )
        self.video_recording_worker.start()
        self.perf_monitor = PerformanceMonitor()

    def set_playback_state(self, playing: bool):
        self.playing = playing

    # -----------------------------------Frame Processing-----------------------------------------------
    def process_new_frame(self, frame):
        """
        Process and display a new frame received from the camera thread.

        This method is called whenever a new frame is available from the camera thread.
        It processes the frame, updates the UI, and handles ROI display.

        Args:
            frame: The new frame from the camera thread
        """
        if not self.playing:  # Access playing state from VideoHandler
            return

        # Store the current frame for potential further processing
        self.current_frame = frame

        # Convert frame to QImage and scale it
        qt_image = self._convert_frame_to_qimage(frame)
        scaled_image = self._scale_image_to_canvas(qt_image)

        # Create a resized frame for processing
        resized_frame = self._create_resized_frame(
            frame, scaled_image.width(), scaled_image.height()
        )

        # Process the frame with the frame model
        # Only allow to let frame pass in when the previous frame has been processed
        # This is to prevent the overstacking of frames
        self.video_thread.if_release = False
        self._process_frame_with_model(resized_frame)
        self.video_thread.if_release = True

        # Display the frame on the canvas
        pixmap = self._display_frame_on_canvas(scaled_image)

        # Update the overlay position
        self._update_overlay_position(pixmap)

        # Record frame if recording is active (non-blocking)
        if self.event_handler.recording_active and self.video_recorder.is_active():
            self.video_recording_worker.add_frame(frame)

        # Update status bar
        self._update_status_bar()

    def _convert_frame_to_qimage(self, frame):
        """
        Convert an OpenCV frame (BGR) to a Qt QImage (RGB).

        Args:
            frame: OpenCV frame in BGR format

        Returns:
            QImage: The converted Qt image
        """
        # Convert the frame from BGR to RGB format (OpenCV uses BGR, Qt uses RGB)
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Create a QImage from the frame data
        h, w, ch = rgb_frame.shape
        bytes_per_line = ch * w
        return QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)

    def _scale_image_to_canvas(self, qt_image):
        """
        Scale the QImage to fit the canvas while maintaining aspect ratio.

        Args:
            qt_image: The QImage to scale

        Returns:
            QImage: The scaled image
        """
        return qt_image.scaled(
            self.canvas_width, self.canvas_height, Qt.AspectRatioMode.KeepAspectRatio
        )

    def _create_resized_frame(self, frame, width, height):
        """
        Create a resized NumPy array with the specified dimensions.

        Args:
            frame: The original frame
            width: Target width
            height: Target height

        Returns:
            ndarray: Resized frame
        """
        return cv2.resize(frame, (width, height))

    def _process_frame_with_model(self, resized_frame):
        """
        Process the frame with the frame model and display ROIs.

        Args:
            resized_frame: The resized frame to process
        """
        # start_time = time.time()
        # Process the frame
        self.perf_monitor.start_timer("fm_model_processing")
        self.current_frame_number, roi_list, update_velo_plot, update_average_velo = (
            self.frame_model.process_frame(resized_frame)
        )
        self.perf_monitor.stop_timer("fm_model_processing")

        self.roi_handler.display_roi(roi_list)

        # Update the velocity plot with the latest data
        if update_velo_plot:
            self.perf_monitor.start_timer("gui_display")
            self.velocity_plotter.update_velocity_plot()
            self.velocity_plotter.update_arec_data()
            self.perf_monitor.stop_timer("gui_display")
            
        self.perf_monitor.log_frame(self.current_frame_number)

    def _display_frame_on_canvas(self, scaled_image):
        """
        Convert the QImage to a QPixmap and display it on the video canvas.

        Args:
            scaled_image: The scaled QImage to display

        Returns:
            QPixmap: The pixmap that was set on the canvas
        """
        pixmap = QPixmap.fromImage(scaled_image)
        self.gui.video_canvas_label.setPixmap(pixmap)
        return pixmap

    def _update_overlay_position(self, pixmap):
        """
        Update the position and size of the overlay widget based on the video dimensions.

        Args:
            pixmap: The pixmap displayed on the canvas
        """
        if pixmap.width() < self.canvas_width or pixmap.height() < self.canvas_height:
            # Calculate the position of the video within the canvas (centered)
            x_offset = (self.canvas_width - pixmap.width()) // 2
            y_offset = (self.canvas_height - pixmap.height()) // 2
            self.video_rect = QRect(x_offset, y_offset, pixmap.width(), pixmap.height())

            # Update overlay widget geometry if it exists
            if self.overlay_widget:
                self.overlay_widget.setGeometry(self.video_rect)
        else:
            # Video fills the canvas
            self.video_rect = QRect(0, 0, self.canvas_width, self.canvas_height)

    def _update_status_bar(self):
        """
        Update status bar with frame information.
        """
        if hasattr(self.gui, "statusBar"):
            self.gui.statusBar().showMessage(
                f"Frame: {self.current_frame_number} | Time: {self.frame_model.last_processed_time}"
            )
    
    def cleanup(self):
        """
        Clean up resources, particularly the video recording worker thread.
        
        This method should be called when the FrameProcessor is being destroyed
        to ensure proper cleanup of the video recording worker thread.
        """
        if hasattr(self, 'video_recording_worker'):
            self.video_recording_worker.stop()
            logger.info("Video recording worker thread stopped")
