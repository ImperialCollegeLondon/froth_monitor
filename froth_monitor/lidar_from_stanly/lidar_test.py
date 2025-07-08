import sys
import time
import re
import csv
import serial
import serial.tools.list_ports
from datetime import datetime
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtCore import QSettings
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt

# Minimum Y-axis window amplitude in mm
MIN_Y_WINDOW = 10.0

class DataViewerWindow(QtWidgets.QMainWindow):
    def __init__(self, timestamps, distances, title="Imported Data Viewer"):
        super().__init__()
        self.setWindowTitle(title)
        self.resize(800, 500)

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QVBoxLayout(central)

        fig, ax = plt.subplots()
        canvas = FigureCanvas(fig)
        layout.addWidget(canvas)

        # Convert datetime to relative seconds
        rel = []
        if timestamps:
            t0 = timestamps[0]
            rel = [(t - t0).total_seconds() for t in timestamps]

        ax.plot(rel, distances, marker='o', linestyle='-')
        ax.set_xlabel('Time (s)')
        ax.set_ylabel('Distance (mm, inverted)')
        ax.set_title('Imported Distance vs Time (mm)')
        ax.grid(True)
        fig.tight_layout()
        canvas.draw()

class LidarWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("L1 Laser Distance Monitor")
        self.resize(900, 600)

        # Persistent settings
        self.settings = QSettings('MyCompany', 'LidarApp')

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        vbox = QtWidgets.QVBoxLayout(central)

        ctrl = QtWidgets.QHBoxLayout()
        vbox.addLayout(ctrl)

        ctrl.addWidget(QtWidgets.QLabel("COM Port:"))
        self.combobox = QtWidgets.QComboBox()
        ctrl.addWidget(self.combobox)

        ctrl.addWidget(QtWidgets.QLabel("Freq (Hz):"))
        self.freq_spin = QtWidgets.QSpinBox()
        self.freq_spin.setRange(1, 50)
        self.freq_spin.setValue(20)
        ctrl.addWidget(self.freq_spin)

        ctrl.addWidget(QtWidgets.QLabel("Window Size (pts):"))
        self.win_spin = QtWidgets.QSpinBox()
        self.win_spin.setRange(1, 5000)
        self.win_spin.setValue(100)
        ctrl.addWidget(self.win_spin)

        ctrl.addWidget(QtWidgets.QLabel("Offset (mm):"))
        self.offset_spin = QtWidgets.QDoubleSpinBox()
        self.offset_spin.setRange(-100000.0, 100000.0)
        self.offset_spin.setSingleStep(1.0)
        self.offset_spin.setDecimals(2)
        # Load saved offset
        offset_default = self.settings.value('offsetMm', 0.0, type=float)
        self.offset_spin.setValue(offset_default)
        ctrl.addWidget(self.offset_spin)

        self.btn_start  = QtWidgets.QPushButton("Start")
        self.btn_stop   = QtWidgets.QPushButton("Stop")
        self.btn_export = QtWidgets.QPushButton("Export CSV")
        self.btn_import = QtWidgets.QPushButton("Import CSV")
        self.btn_stop.setEnabled(False)
        ctrl.addWidget(self.btn_start)
        ctrl.addWidget(self.btn_stop)
        ctrl.addWidget(self.btn_export)
        ctrl.addWidget(self.btn_import)

        self.fig, self.ax = plt.subplots()
        self.canvas = FigureCanvas(self.fig)
        vbox.addWidget(self.canvas)

        self.full_timestamps = []  # list of datetime
        self.full_distances  = []
        self.timestamps = []       # list of seconds
        self.distances  = []
        self.pattern    = re.compile(r"D=([0-9.]+)m")

        self.sensor_timer = QtCore.QTimer(self)
        self.sensor_timer.timeout.connect(self.read_from_sensor)
        self.gui_timer = QtCore.QTimer(self)
        self.gui_timer.timeout.connect(self.update_plot)

        self.btn_start.clicked.connect(self.start_reading)
        self.btn_stop.clicked.connect(self.stop_reading)
        self.btn_export.clicked.connect(self.export_data)
        self.btn_import.clicked.connect(self.import_data)

        self.refresh_ports()
        self._viewer_windows = []

    def refresh_ports(self):
        self.combobox.clear()
        for p in serial.tools.list_ports.comports():
            self.combobox.addItem(p.device)

    def start_reading(self):
        port = self.combobox.currentText()
        if not port:
            QtWidgets.QMessageBox.warning(self, "No Port", "Please select a COM port.")
            return
        try:
            self.ser = serial.Serial(port=port, baudrate=38400,
                                     bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE,
                                     stopbits=serial.STOPBITS_ONE, timeout=0)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Serial Error", str(e))
            return
        self.ser.reset_input_buffer()

        freq = self.freq_spin.value()
        self.window_size = self.win_spin.value()
        self.offset_mm = float(self.offset_spin.value())

        self.ser.write(f"iSET:7,{freq}\r\n".encode())
        time.sleep(0.1)
        self.ser.write(b"iFACM\r\n")

        self.start_time = time.time()
        self.full_timestamps.clear(); self.full_distances.clear()
        self.timestamps.clear(); self.distances.clear()

        self.ax.clear()
        self.line, = self.ax.plot([], [], marker="o")
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("Distance (mm)")
        self.ax.set_title(f"L1 @ {freq} Hz (window={self.window_size}, offset={self.offset_mm} mm)")
        self.ax.grid(True)
        self.canvas.draw()

        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.freq_spin.setEnabled(False)
        self.win_spin.setEnabled(False)
        self.offset_spin.setEnabled(False)

        interval = int(1000 / freq)
        self.sensor_timer.start(interval)
        self.gui_timer.start(interval)

    def stop_reading(self):
        self.sensor_timer.stop()
        self.gui_timer.stop()
        try:
            self.ser.write(b"iHALT\r\n")
            self.ser.close()
        except:
            pass
        # Save offset
        self.settings.setValue('offsetMm', self.offset_spin.value())

        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.freq_spin.setEnabled(True)
        self.win_spin.setEnabled(True)
        self.offset_spin.setEnabled(True)

    def read_from_sensor(self):
        latest = None
        while self.ser.in_waiting:
            latest = self.ser.readline().decode("ascii", errors="ignore").strip()
        if not latest:
            return
        m = self.pattern.match(latest)
        if not m:
            return
        t = time.time() - self.start_time
        dt = datetime.now()
        raw_mm = float(m.group(1)) * 1000.0
        d_mm = self.offset_mm - raw_mm

        self.full_timestamps.append(dt)
        self.full_distances.append(d_mm)

        self.timestamps.append(t)
        self.distances.append(d_mm)
        if len(self.timestamps) > self.window_size:
            self.timestamps.pop(0)
            self.distances.pop(0)

    def update_plot(self):
        if not self.timestamps:
            return
        self.line.set_data(self.timestamps, self.distances)
        # X limits only if >1 point
        if len(self.timestamps) > 1:
            self.ax.set_xlim(self.timestamps[0], self.timestamps[-1])
        else:
            t0 = self.timestamps[0]
            self.ax.set_xlim(t0 - 0.5, t0 + 0.5)
        # Y limits with minimum window
        y_min, y_max = min(self.distances), max(self.distances)
        y_range = y_max - y_min
        if y_range < MIN_Y_WINDOW:
            mid = (y_max + y_min) / 2.0
            y_min = mid - MIN_Y_WINDOW/2.0
            y_max = mid + MIN_Y_WINDOW/2.0
        self.ax.set_ylim(y_min, y_max)
        self.canvas.draw_idle()

    def export_data(self):
        if not self.full_timestamps:
            QtWidgets.QMessageBox.information(self, "No Data", "No measurements to export.")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save CSV", "",
                                                         "CSV files (*.csv);;All Files (*)")
        if not path:
            return
        try:
            with open(path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["timestamp", "distance_mm_inverted"])
                for dt, d in zip(self.full_timestamps, self.full_distances):
                    ts = dt.strftime("%Y/%m/%d %H:%M:%S.%f")[:-3]
                    writer.writerow([ts, f"{d:.2f}"])
            QtWidgets.QMessageBox.information(self, "Exported",
                                              f"Saved {len(self.full_timestamps)} samples to:\n{path}")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Export Error", str(e))

    def import_data(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Open CSV", "",
                                                         "CSV files (*.csv);;All Files (*)")
        if not path:
            return
        ts, ds = [], []
        try:
            with open(path, newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # ignore timestamp, just use index
                    pass
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Import Error", str(e))
            return
        # Re-read for floats and compute relative
        with open(path, newline="") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                ds.append(float(row['distance_mm']))
                ts.append(i * (1.0 / self.freq_spin.value()))
        viewer = DataViewerWindow(ts, ds, title=f"Imported: {path}")
        viewer.show()
        self._viewer_windows.append(viewer)

    def closeEvent(self, event):
        if self.sensor_timer.isActive() or self.gui_timer.isActive():
            self.stop_reading()
        event.accept()

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = LidarWindow()
    window.show()
    sys.exit(app.exec_())
