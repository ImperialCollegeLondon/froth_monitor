"""Froth Tracker Application Overlay Widget.

This module contains the custom QWidget implementation for creating a translucent overlay
on top of the video canvas to display timestamps and other information.
"""

from typing import cast
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QTimer, QRect, QPoint, Signal
from PySide6.QtGui import QPainter, QFont, QColor, QPen, QPolygon
import time
import math


class OverlayWidget(QWidget):
    """
    A custom QWidget that creates a translucent overlay on top of the video canvas.

    This widget displays a timestamp in the middle of the overlay and can be used
    for other visual elements like ROI selection. It also supports drawing rectangles
    for defining regions of interest (ROIs).
    """

    # Signals to emit when ROI rectangle is completed, ruler measurement is done, or arrow is drawn
    roi_created = Signal(QRect)
    ruler_measured = Signal(float)  # Signal to emit the measured distance in pixels
    arrow_drawn = Signal(
        QPoint, QPoint, float
    )  # Signal to emit start point, end point, and angle

    def __init__(self, parent=None):
        """
        Initialize the OverlayWidget.

        Args:
            parent: The parent widget (typically the video canvas label)
        """
        super(OverlayWidget, self).__init__(parent)

        # Set widget properties for transparency
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Initialize timestamp
        self.timestamp = time.strftime("%H:%M:%S", time.localtime())

        # # Set font for timestamp
        # self.font = QFont("Arial", 24, QFont.Weight.Bold)

        # Store video dimensions
        self.video_width = 0
        self.video_height = 0

        self.current_event = cast(str, None)

        # Store video position within the canvas
        self.video_rect = QRect()

        # Rectangle drawing attributes
        self.drawing_roi = False
        self.roi_start_point = QPoint()
        self.roi_end_point = QPoint()
        self.current_roi_rect = QRect()

        # Ruler calibration attributes
        self.drawing_ruler = False
        self.ruler_drawed = False
        self.ruler_start_point = QPoint()
        self.ruler_end_point = QPoint()
        self.ruler_distance = 0.0

        # Arrow drawing attributes
        self.drawing_arrow = False
        self.arrow_start_point = QPoint()
        self.arrow_end_point = QPoint()
        self.arrow_angle = 0.0

        # List of ROIs to display
        self.roi_list = []

        # Enable mouse tracking for drawing
        self.setMouseTracking(True)

    def set_video_dimensions(self, width, height):
        """
        Set the dimensions of the video being displayed.

        Args:
            width: Width of the video in pixels
            height: Height of the video in pixels
        """
        self.video_width = width
        self.video_height = height
        self.update()

    def set_video_rect(self, rect):
        """
        Set the rectangle where the video is displayed within the canvas.

        Args:
            rect: QRect representing the position and size of the video
        """
        self.video_rect = rect
        self.setGeometry(rect)
        self.update()

    def paintEvent(self, event):
        """
        Paint the overlay with timestamp and any other visual elements.

        Args:
            event: The paint event
        """

        # Create painter
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Set semi-transparent background
        # painter.fillRect(self.rect(), QColor(0, 0, 0, 50))  # RGBA with alpha=50 (20% opacity)

        if self.drawing_roi:
            # Draw ROI rectangle if we're in drawing mode
            if (
                self.drawing_roi
                and not self.roi_start_point.isNull()
                and not self.roi_end_point.isNull()
            ):
                # Draw the rectangle with a semi-transparent fill
                roi_rect = QRect(self.roi_start_point, self.roi_end_point).normalized()
                painter.fillRect(
                    roi_rect, QColor(0, 255, 0, 50)
                )  # Green with 20% opacity
                # Draw the rectangle border
                painter.setPen(
                    QPen(QColor(0, 255, 0, 200), 2)
                )  # Green with 80% opacity, 2px width
                painter.drawRect(roi_rect)

        elif self.drawing_ruler:
            # Draw ruler line if we're in ruler calibration mode
            if (
                not self.ruler_start_point.isNull()
                and not self.ruler_end_point.isNull()
            ):
                # Draw the line
                painter.setPen(
                    QPen(QColor(255, 0, 0, 200), 2)
                )  # Red with 80% opacity, 2px width
                painter.drawLine(self.ruler_start_point, self.ruler_end_point)

                # Calculate and display the distance
                if self.ruler_distance > 0:
                    # Draw the distance text near the end point
                    painter.setFont(QFont("Arial", 12))
                    painter.setPen(QColor(255, 255, 255))  # White text
                    # Draw text with black outline for better visibility
                    text_x = self.ruler_end_point.x() + 10
                    text_y = self.ruler_end_point.y() + 10
                    painter.setPen(QColor(0, 0, 0))
                    for dx in [-1, 0, 1]:
                        for dy in [-1, 0, 1]:
                            painter.drawText(
                                text_x + dx,
                                text_y + dy,
                                f"{self.ruler_distance:.1f} px",
                            )
                    painter.setPen(QColor(255, 255, 255))
                    painter.drawText(text_x, text_y, f"{self.ruler_distance:.1f} px")

        elif self.drawing_arrow:
            # Draw arrow if we're in arrow drawing mode
            if (
                not self.arrow_start_point.isNull()
                and not self.arrow_end_point.isNull()
            ):
                # Draw the arrow line
                painter.setPen(
                    QPen(QColor(255, 165, 0, 200), 2)
                )  # Orange with 80% opacity, 2px width
                painter.drawLine(self.arrow_start_point, self.arrow_end_point)

                # Draw the arrowhead
                self.draw_arrowhead(
                    painter, self.arrow_start_point, self.arrow_end_point
                )

                # Calculate and display the angle
                if self.arrow_start_point != self.arrow_end_point:
                    # Draw the angle text near the end point
                    painter.setFont(QFont("Arial", 12))
                    text_x = self.arrow_end_point.x() + 15
                    text_y = self.arrow_end_point.y() + 15

                    # Draw text with black outline for better visibility
                    painter.setPen(QColor(0, 0, 0))
                    for dx in [-1, 0, 1]:
                        for dy in [-1, 0, 1]:
                            painter.drawText(
                                text_x + dx, text_y + dy, f"{self.arrow_angle:.1f}°"
                            )
                    painter.setPen(QColor(255, 255, 255))
                    painter.drawText(text_x, text_y, f"{self.arrow_angle:.1f}°")

        else:
            if self.roi_list:
                self.drawROIs(painter)

        painter.end()

    def showEvent(self, event):
        """
        Handle the show event to ensure the timer is running.

        Args:
            event: The show event
        """
        super().showEvent(event)

    def hideEvent(self, event):
        """
        Handle the hide event to stop the timer when not visible.

        Args:
            event: The hide event
        """
        super().hideEvent(event)

    def mousePressEvent(self, event):
        """
        Handle mouse press events for starting ROI rectangle, ruler line, or arrow drawing.

        Args:
            event: The mouse event
        """
        if event.button() == Qt.MouseButton.LeftButton:
            if self.drawing_roi:
                self.roi_start_point = event.position().toPoint()
                self.roi_end_point = self.roi_start_point
                self.update()
            elif self.drawing_ruler:
                self.ruler_start_point = event.position().toPoint()
                self.ruler_end_point = self.ruler_start_point
                self.ruler_distance = 0.0
                self.update()
            elif self.drawing_arrow:
                self.arrow_start_point = event.position().toPoint()
                self.arrow_end_point = self.arrow_start_point
                self.arrow_angle = 0.0
                self.update()

    def mouseMoveEvent(self, event):
        """
        Handle mouse move events for updating ROI rectangle, ruler line, or arrow during drawing.

        Args:
            event: The mouse event
        """
        if self.drawing_roi and not self.roi_start_point.isNull():
            self.roi_end_point = event.position().toPoint()
            self.update()
        elif self.drawing_ruler and not self.ruler_start_point.isNull():
            self.ruler_end_point = event.position().toPoint()
            # Calculate the distance between start and end points
            dx = self.ruler_end_point.x() - self.ruler_start_point.x()
            dy = self.ruler_end_point.y() - self.ruler_start_point.y()
            self.ruler_distance = math.sqrt(dx * dx + dy * dy)
            self.update()
        elif self.drawing_arrow and not self.arrow_start_point.isNull():
            self.arrow_end_point = event.position().toPoint()
            # Calculate the angle between the arrow and the horizontal
            dx = self.arrow_end_point.x() - self.arrow_start_point.x()
            dy = self.arrow_end_point.y() - self.arrow_start_point.y()
            # Calculate angle in degrees, with 0 degrees being horizontal to the right
            # and positive angles going clockwise
            self.arrow_angle = math.degrees(math.atan2(dy, dx))
            # Adjust to make 0 degrees horizontal and positive angles going counterclockwise
            self.arrow_angle = -self.arrow_angle
            self.update()

    def mouseReleaseEvent(self, event):
        """
        Handle mouse release events for completing ROI rectangle, ruler line, or arrow drawing.

        Args:
            event: The mouse event
        """

        if event.button() == Qt.MouseButton.LeftButton:
            if self.drawing_roi:
                self.roi_end_point = event.position().toPoint()

                # Create the final rectangle and normalize it (ensure top-left and bottom-right are correct)
                self.current_roi_rect = QRect(
                    self.roi_start_point, self.roi_end_point
                ).normalized()
                # self.current_roi_rect = QRect(self.roi_start_point, self.roi_end_point)

                # Emit signal with the created rectangle
                self.roi_created.emit(self.current_roi_rect)

                # Reset drawing state
                self.drawing_roi = False
                self.update()

            elif self.drawing_ruler:
                self.ruler_end_point = event.position().toPoint()

                # Calculate the final distance
                dx = self.ruler_end_point.x() - self.ruler_start_point.x()
                dy = self.ruler_end_point.y() - self.ruler_start_point.y()
                self.ruler_distance = math.sqrt(dx * dx + dy * dy)

                # Emit signal with the measured distance
                self.ruler_measured.emit(self.ruler_distance)

                # Keep the ruler visible but exit drawing mode after a short delay
                QTimer.singleShot(2000, self.reset_ruler_mode)

                self.reset_ruler_mode()
                self.update()

            elif self.drawing_arrow:
                self.arrow_end_point = event.position().toPoint()

                # Calculate the final angle
                dx = self.arrow_end_point.x() - self.arrow_start_point.x()
                dy = self.arrow_end_point.y() - self.arrow_start_point.y()
                # Calculate angle in degrees, with 0 degrees being horizontal to the right
                # and positive angles going clockwise
                self.arrow_angle = math.degrees(math.atan2(dy, dx))
                # Adjust to make 0 degrees horizontal and positive angles going counterclockwise
                self.arrow_angle = -self.arrow_angle

                # Emit signal with the arrow start point, end point, and angle
                self.arrow_drawn.emit(
                    self.arrow_start_point, self.arrow_end_point, self.arrow_angle
                )

                # Reset drawing state after a short delay to keep the arrow visible briefly
                QTimer.singleShot(2000, self.reset_arrow_mode)

                self.reset_arrow_mode()
                self.update()

    def start_roi_drawing(self):
        """
        Start the ROI drawing mode.
        """
        self.drawing_roi = True
        self.drawing_ruler = False
        self.roi_start_point = QPoint()
        self.roi_end_point = QPoint()

    def ruler_calibration(self):
        """
        Start the ruler calibration mode for measuring distances in pixels.
        This method should be called from the EventHandler.
        """
        self.drawing_ruler = True
        self.drawing_roi = False
        self.ruler_start_point = QPoint()
        self.ruler_end_point = QPoint()
        self.ruler_distance = 0.0

    def reset_ruler_mode(self):
        """
        Reset the ruler drawing mode after measurement is complete.
        """
        self.drawing_ruler = False
        self.ruler_drawed = True
        self.update()

    def start_arrow_drawing(self):
        """
        Start the arrow drawing mode.
        """
        self.drawing_arrow = True
        self.drawing_roi = False
        self.drawing_ruler = False
        self.arrow_start_point = QPoint()
        self.arrow_end_point = QPoint()
        self.arrow_angle = 0.0

    def reset_arrow_mode(self):
        """
        Reset the arrow drawing mode after drawing is complete.
        """
        self.drawing_arrow = False
        self.update()

    def draw_arrowhead(self, painter, start_point, end_point):
        """
        Draw an arrowhead at the end of the arrow line.

        Args:
            painter: QPainter object to use for drawing
            start_point: Start point of the arrow line
            end_point: End point of the arrow line
        """
        if start_point == end_point:
            return

        # Arrow properties
        arrowhead_length = 15.0
        arrowhead_angle = 30.0  # degrees

        # Calculate the direction vector of the line
        dx = end_point.x() - start_point.x()
        dy = end_point.y() - start_point.y()
        line_length = math.sqrt(dx * dx + dy * dy)

        # Normalize the direction vector
        if line_length > 0:
            dx /= line_length
            dy /= line_length

        # Calculate the two points that form the arrowhead
        angle1 = math.radians(arrowhead_angle)
        angle2 = math.radians(-arrowhead_angle)

        # Rotate the direction vector by arrowhead_angle and -arrowhead_angle
        p1x = dx * math.cos(angle1) - dy * math.sin(angle1)
        p1y = dx * math.sin(angle1) + dy * math.cos(angle1)
        p2x = dx * math.cos(angle2) - dy * math.sin(angle2)
        p2y = dx * math.sin(angle2) + dy * math.cos(angle2)

        # Scale by arrowhead_length and translate to the end point
        p1x = end_point.x() - p1x * arrowhead_length
        p1y = end_point.y() - p1y * arrowhead_length
        p2x = end_point.x() - p2x * arrowhead_length
        p2y = end_point.y() - p2y * arrowhead_length

        # Create a polygon for the arrowhead
        arrowhead = QPolygon()
        arrowhead.append(end_point)
        arrowhead.append(QPoint(int(p1x), int(p1y)))
        arrowhead.append(QPoint(int(p2x), int(p2y)))

        # Draw the arrowhead
        painter.setBrush(QColor(255, 165, 0, 150))  # Orange with 60% opacity
        painter.drawPolygon(arrowhead)

    def get_roi_coordinates(self):
        """
        Get the coordinates of the drawn ROI rectangle relative to the video dimensions.

        Returns:
            tuple: (x, y, width, height) of the ROI rectangle
        """
        if self.current_roi_rect.isValid():
            return (
                self.current_roi_rect.x(),
                self.current_roi_rect.y(),
                self.current_roi_rect.width(),
                self.current_roi_rect.height(),
            )
        return None

    def display_roi(self, roi_list):
        """
        Set the ROI list and trigger a repaint to display the ROIs.

        Args:
            roi_list: List of ROI objects to display
        """
        self.roi_list = roi_list
        self.update()  # Trigger a repaint to display the ROIs

    def drawROIs(self, painter):
        """
        Helper method to draw ROIs on the overlay.

        Args:
            painter: QPainter object to use for drawing
        """
        # Set font for ROI sequence numbers
        number_font = QFont("Arial", 12, QFont.Weight.Bold)
        painter.setFont(number_font)

        # Draw each ROI in the list
        for i, roi in enumerate(self.roi_list):
            # Get the ROI coordinates
            x1 = roi.coordinate[0]
            y1 = roi.coordinate[1]
            x2 = roi.coordinate[2]
            y2 = roi.coordinate[3]

            # Calculate width and height of the ROI
            width = x2
            height = y2

            # Create a rectangle from the coordinates
            roi_rect = QRect(x1, y1, x2, y2)

            # Draw the rectangle with a semi-transparent fill
            # painter.fillRect(roi_rect, QColor(0, 200, 255, 40))  # Light blue with 16% opacity

            # Draw the rectangle border
            painter.setPen(
                QPen(QColor(0, 200, 255, 200), 2)
            )  # Light blue with 80% opacity, 2px width

            # Draw horizontal line of the cross (spanning the full width of ROI)
            painter.drawRect(roi_rect)

            # Draw the ROI sequence number in the top-right corner
            sequence_number = str(i + 1)  # 1-based indexing for user-friendly display
            painter.setPen(QPen(QColor(255, 255, 255, 230)))  # White with 90% opacity

            # Calculate position for the sequence number (top-right corner with small padding)
            number_x = x1 + x2 - 20
            number_y = y1 + 20

            # Draw the sequence number
            painter.drawText(number_x, number_y, sequence_number)

            # Draw the moving cross based on delta_pixels if available
            if roi.delta_pixels is not None:
                delta_x, delta_y = roi.delta_pixels

                if roi.cross_position is None:
                    roi.cross_position = int(x1 + x2 // 2), int(y1 + y1 // 2)

                # Calculate the new position for the cross
                cross_x, cross_y = roi.cross_position
                cross_x += int(delta_x)
                cross_y += int(delta_y)

                # Ensure the cross is within the ROI boundaries
                if cross_x < x1:
                    cross_x += width
                if cross_y < y1:
                    cross_y += height
                if cross_x >= x1 + x2:
                    cross_x -= width
                if cross_y >= y1 + y2:
                    cross_y -= height

                # Draw the cross with a bright color
                painter.setPen(
                    QPen(QColor(255, 50, 50, 230), 2)
                )  # Red with 90% opacity, 2px width

                # Draw horizontal line of the cross (spanning the full width of ROI)
                painter.drawLine(x1, cross_y, x1 + x2, cross_y)

                # # Draw vertical line of the cross (spanning the full height of ROI)
                painter.drawLine(cross_x, y1, cross_x, y1 + y2)

                roi.cross_position = cross_x, cross_y

    def reset(self) -> None:
        """
        Reset the overlay to its initial state.
        """
        self.roi_list = []
        self.current_roi_rect = QRect()