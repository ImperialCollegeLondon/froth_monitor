import sys
from PyQt5 import QtWidgets, QtCore
from network import VideoReceiver
from visualizer import VisualizerWindow
import cv2

SELF_NETWORK_ADDRESS = "0.0.0.0"
SELF_NETWORK_PORT    = 5001

class ReceiverThread(QtCore.QThread):
    data_received = QtCore.pyqtSignal(dict, object)  # server_data, frame

    def __init__(self, addr, port):
        super().__init__()
        self.addr = addr
        self.port = port
        self._running = True

    def run(self):
        receiver = VideoReceiver(self.addr, self.port, verbose_level=2)
        while self._running:
            server_data, frame = receiver.recv()
            if frame is None:
                break

            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            
            # emit right away; slot runs in GUI thread
            self.data_received.emit(server_data, frame)
        receiver.close()

    def stop(self):
        self._running = False

def main():
    app = QtWidgets.QApplication(sys.argv)

    visualizer = VisualizerWindow()
    visualizer.show()

    thread = ReceiverThread(SELF_NETWORK_ADDRESS, SELF_NETWORK_PORT)
    thread.data_received.connect(lambda sd, fr: (
        visualizer.update_frame(fr),
        visualizer.add_distance(sd["lidar_timestamp"], sd["lidar_reading"])
    ))
    thread.start()

    exit_code = app.exec_()
    thread.stop()
    thread.wait()
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
