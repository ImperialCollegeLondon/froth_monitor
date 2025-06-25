"""
TODO list:
1. the code is scrapped from the windows version, we need to test where the device is on ubuntu
"""

import random
import time
import re
# import serial


class LidarDataStream:
    def __init__(self, source, port=None, freq=20, offset_mm=0.0):
        self.source = source
        self.port = port
        self.freq = freq
        self.offset_mm = offset_mm
        self.pattern = re.compile(r"D=([0-9.]+)m")
        self.ser = None

    # def connect(self):
    #     if self.port is not None:
    #         self.ser = serial.Serial(
    #             port=self.port,
    #             baudrate=38400,
    #             bytesize=serial.EIGHTBITS,
    #             parity=serial.PARITY_NONE,
    #             stopbits=serial.STOPBITS_ONE,
    #             timeout=0
    #         )
    #         self.ser.reset_input_buffer()
    #         # set frequency
    #         self.ser.write(f"iSET:7,{self.freq}\r\n".encode())
    #         # set resolution
    #         self.ser.write(b"iSET:5,1\r\n") # 0: 3 decimals (1mm), 1: 4 decimals (0.1mm)
    #         time.sleep(0.1)
    #         self.ser.write(b"iFACM\r\n")
    #         self.start_time = time.time()

    # def disconnect(self):
    #     if self.ser:
    #         try:
    #             self.ser.write(b"iHALT\r\n")
    #             self.ser.close()
    #         except Exception:
    #             pass

    # def start_stream(self):
    #     """Generator: yields (timestamp, distance_mm) immediately on each call."""
    #     if self.ser is None:
    #         self.connect()
    #     while True:
    #         # Try to read latest line from serial, else yield dummy data
    #         latest = None
    #         if self.ser is not None:
    #             while self.ser.in_waiting:
    #                 latest = self.ser.readline().decode("ascii", errors="ignore").strip()
    #         if latest:
    #             m = self.pattern.match(latest)
    #             if m:
    #                 t = time.time() - self.start_time
    #                 dt = datetime.now()
    #                 raw_mm = float(m.group(1)) * 1000.0
    #                 d_mm = self.offset_mm - raw_mm
    #                 yield (dt, d_mm)
    #                 continue
    #         # If no data, yield dummy data
    #         yield (time.time(), None)

    # a debug data stream that generates random Lidar data of value: xxx.xx
    def generate_debug_data(self):
        while True:
            # Simulate Lidar data as a random float
            data = round(random.uniform(0.0, 100.0), 2)
            timestamp = time.time()
            yield (timestamp, data)
