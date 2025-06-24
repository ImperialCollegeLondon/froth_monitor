import time
import sys
from collections import deque

import numpy as np
from PyQt5 import QtWidgets, QtCore, QtGui
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt

# Minimum Y-axis window amplitude in mm
MIN_Y_WINDOW = 10.0

class VisualizerWindow(QtWidgets.QMainWindow):
    def __init__(self, window_size=100, min_y_window=MIN_Y_WINDOW, title="Lidar + Video Visualizer"):
        super().__init__()
        self.setWindowTitle(title)
        self.resize(1200, 650)

        self.window_size = window_size
        self.min_y_window = min_y_window

        # buffers for plot
        self.timestamps = deque(maxlen=window_size)
        self.distances = deque(maxlen=window_size)
        self.start_time = time.time()

        # buffers for FPS and distance frequency calculation
        self.frame_times = deque(maxlen=30)
        self.distance_times = deque(maxlen=30)

        # central widget & layouts
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        hbox = QtWidgets.QHBoxLayout(central)

        # matplotlib figure
        self.fig, self.ax = plt.subplots()
        self.canvas = FigureCanvas(self.fig)
        hbox.addWidget(self.canvas, stretch=3)

        # video and stats display
        stats_layout = QtWidgets.QVBoxLayout()
        self.fps_label = QtWidgets.QLabel("FPS: 0.0")
        stats_layout.addWidget(self.fps_label)
        self.res_label = QtWidgets.QLabel("Resolution: 0x0")
        stats_layout.addWidget(self.res_label)
        self.latency_label = QtWidgets.QLabel("Latency: 0.0 ms")
        stats_layout.addWidget(self.latency_label)

        # video display
        self.video_label = QtWidgets.QLabel()
        self.video_label.setFixedSize(640, 480)
        self.video_label.setStyleSheet("background-color: black;")
        stats_layout.addWidget(self.video_label)
        hbox.addLayout(stats_layout, stretch=2)

        # initialize plot line
        self.line, = self.ax.plot([], [], marker='o', linestyle='-')
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("Distance (mm)")
        self.ax.grid(True)

        # timer to refresh the plot
        self.gui_timer = QtCore.QTimer(self)
        self.gui_timer.timeout.connect(self._refresh_plot)
        self.gui_timer.start(50)

    def add_distance(self, timestamp: float, distance_mm: float):
        """
        Call this whenever you have a new measurement.
        :param timestamp: absolute time (e.g. time.time())
        :param distance_mm: measured distance in mm
        """
        now = time.time()

        # latency in ms
        latency_ms = (now - timestamp) * 1000.0
        self.latency_label.setText(f"Latency: {latency_ms:.1f} ms")

        # plot data
        rel = timestamp - self.start_time
        self.timestamps.append(rel)
        self.distances.append(distance_mm)

    def update_frame(self, frame: np.ndarray):
        """
        Call this whenever you have a new video frame (HxWx3 np.uint8 RGB).
        """
        # track frame time
        now = time.time()
        self.frame_times.append(now)
        if len(self.frame_times) >= 2:
            dt = self.frame_times[-1] - self.frame_times[0]
            fps = (len(self.frame_times) - 1) / dt if dt > 0 else 0.0
            self.fps_label.setText(f"FPS: {fps:.1f}")

        # resolution
        h, w, _ = frame.shape
        self.res_label.setText(f"Resolution: {w}x{h}")

        # display frame
        img = QtGui.QImage(frame.data, w, h, 3*w, QtGui.QImage.Format_RGB888)
        pix = QtGui.QPixmap.fromImage(img).scaled(
            self.video_label.size(),
            QtCore.Qt.KeepAspectRatio,
            QtCore.Qt.FastTransformation
        )
        self.video_label.setPixmap(pix)

    def _refresh_plot(self):
        if not self.timestamps:
            return
        xs = list(self.timestamps)
        ys = list(self.distances)

        self.line.set_data(xs, ys)

        # adjust X limits
        if len(xs) > 1:
            self.ax.set_xlim(xs[0], xs[-1])
        else:
            self.ax.set_xlim(xs[0] - 0.5, xs[0] + 0.5)

        # adjust Y limits with minimum window
        y_min, y_max = min(ys), max(ys)
        y_range = y_max - y_min
        if y_range < self.min_y_window:
            mid = (y_max + y_min) / 2.0
            y_min = mid - self.min_y_window/2.0
            y_max = mid + self.min_y_window/2.0
        self.ax.set_ylim(y_min, y_max)

        self.canvas.draw_idle()

if __name__ == "__main__":
    import threading, cv2

    app = QtWidgets.QApplication(sys.argv)
    win = VisualizerWindow(window_size=200)
    win.show()

    def video_loop():
        cap = cv2.VideoCapture(0)
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            win.update_frame(rgb)
            time.sleep(1/30)

    threading.Thread(target=video_loop, daemon=True).start()

    def lidar_loop():
        while True:
            t = time.time()
            d = 500 + 200 * np.sin((t - win.start_time) * 2.0)
            win.add_distance(t, d)
            time.sleep(0.05)

    threading.Thread(target=lidar_loop, daemon=True).start()

    sys.exit(app.exec_())
