"""
A comprehensive testbench script with GUI for testing all Jetson communication functions.

Tests included:
1. Connection to Jetson using 'jetson.local' mDNS name
2. Receiving data (video frames & lidar readings) from Jetson
3. Structured command system with three types: software, hardware, and general commands
4. Command queuing and stacking support
5. Visual display of received data
6. Status monitoring and error handling

Usage:
    python testbench.py
"""

import sys
import time
import random
from PyQt5 import QtWidgets, QtCore
from data_receiver import DataReceiver
from api.visualizer import VisualizerWindow
from api.commands import CommandList, CommandType, CommandPriority
import cv2

SELF_NETWORK_ADDRESS = "0.0.0.0"
SELF_NETWORK_PORT    = 5001
DUMMY_DATA_INTERVAL  = 5000  # Send dummy data every 5 seconds (in milliseconds)

class ReceiverThread(QtCore.QThread):
    data_received = QtCore.pyqtSignal(dict, object)  # server_data, frame
    connection_status = QtCore.pyqtSignal(bool, str)  # connected, status_message

    def __init__(self, addr, port):
        super().__init__()
        self.addr = addr
        self.port = port
        self._running = True
        self.data_receiver = None

    def run(self):
        try:
            # Initialize DataReceiver which handles connection and communication
            self.data_receiver = DataReceiver(self.addr, self.port, verbose_level=2)
            
            if self.data_receiver.jetson_ip and self.data_receiver.agreed_port:
                self.connection_status.emit(True, f"Connected to Jetson at {self.data_receiver.jetson_ip}:{self.data_receiver.agreed_port}")
            else:
                self.connection_status.emit(False, "Failed to connect to Jetson")
                return

            # Main data receiving loop
            for data in self.data_receiver.get_data():
                if not self._running:
                    break
                
                # Extract server data and frame from the data dictionary
                server_data = {
                    "camera_timestamp": data.get("camera_timestamp"),
                    "lidar_reading": data.get("lidar_reading"),
                    "lidar_timestamp": data.get("lidar_timestamp")
                }
                frame = data["frame"]

                # emit data to GUI thread
                self.data_received.emit(server_data, frame)
                
        except Exception as e:
            self.connection_status.emit(False, f"Error in receiver thread: {str(e)}")
        finally:
            if self.data_receiver:
                self.data_receiver.close()

    def send_data_to_jetson(self, data):
        """Send data to Jetson through the DataReceiver (legacy method)."""
        if self.data_receiver:
            self.data_receiver.send_jeston_data(data)
    
    def send_command_to_jetson(self, command):
        """Send structured command to Jetson through the DataReceiver."""
        if self.data_receiver:
            self.data_receiver.send_command(command)
    
    def send_commands_to_jetson(self, commands):
        """Send multiple structured commands to Jetson."""
        if self.data_receiver:
            self.data_receiver.send_commands(commands)

    def stop(self):
        self._running = False

class TestbenchWindow(QtWidgets.QMainWindow):
    """Extended visualizer with testbench controls and status display."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Jetson Communication Testbench")
        self.resize(1400, 700)
        
        # Initialize the visualizer
        self.visualizer = VisualizerWindow()
        
        # Create main layout
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QtWidgets.QVBoxLayout(central_widget)
        
        # Status panel
        self.create_status_panel(main_layout)
        
        # Add the visualizer widget
        main_layout.addWidget(self.visualizer, stretch=1)
        
        # Control panel
        self.create_control_panel(main_layout)
        
        # Command panel (new)
        self.create_command_panel(main_layout)
        
        # Log panel
        self.create_log_panel(main_layout)
        
        # Initialize timers and counters
        self.dummy_data_timer = QtCore.QTimer()
        self.dummy_data_timer.timeout.connect(self.send_dummy_data)
        self.command_timer = QtCore.QTimer()
        self.command_timer.timeout.connect(self.send_structured_commands)
        self.data_send_counter = 0
        self.command_send_counter = 0
        self.data_receive_counter = 0
        self.start_time = time.time()
        
    def create_status_panel(self, layout):
        """Create status information panel."""
        status_group = QtWidgets.QGroupBox("Connection Status")
        status_layout = QtWidgets.QHBoxLayout(status_group)
        
        self.connection_status_label = QtWidgets.QLabel("Disconnected")
        self.connection_status_label.setStyleSheet("color: red; font-weight: bold;")
        status_layout.addWidget(QtWidgets.QLabel("Status:"))
        status_layout.addWidget(self.connection_status_label)
        
        self.data_counter_label = QtWidgets.QLabel("Received: 0 | Legacy Sent: 0 | Commands Sent: 0")
        status_layout.addWidget(self.data_counter_label)
        
        status_layout.addStretch()
        layout.addWidget(status_group)
        
    def create_control_panel(self, layout):
        """Create control panel with test buttons."""
        control_group = QtWidgets.QGroupBox("Testbench Controls")
        control_layout = QtWidgets.QHBoxLayout(control_group)
        
        # Auto-send toggle
        self.auto_send_checkbox = QtWidgets.QCheckBox("Auto-send dummy data")
        self.auto_send_checkbox.stateChanged.connect(self.toggle_auto_send)
        control_layout.addWidget(self.auto_send_checkbox)
        
        # Interval spinner
        control_layout.addWidget(QtWidgets.QLabel("Interval (sec):"))
        self.interval_spinner = QtWidgets.QSpinBox()
        self.interval_spinner.setRange(1, 60)
        self.interval_spinner.setValue(5)
        self.interval_spinner.valueChanged.connect(self.update_timer_interval)
        control_layout.addWidget(self.interval_spinner)
        
        # Manual send button
        self.manual_send_button = QtWidgets.QPushButton("Send Test Data")
        self.manual_send_button.clicked.connect(self.send_dummy_data)
        control_layout.addWidget(self.manual_send_button)
        
        control_layout.addStretch()
        layout.addWidget(control_group)
    
    def create_command_panel(self, layout):
        """Create structured command testing panel."""
        command_group = QtWidgets.QGroupBox("Structured Command Testing")
        command_layout = QtWidgets.QVBoxLayout(command_group)
        
        # Command type selection
        type_layout = QtWidgets.QHBoxLayout()
        type_layout.addWidget(QtWidgets.QLabel("Command Type:"))
        
        self.hardware_button = QtWidgets.QPushButton("Hardware Command")
        self.hardware_button.clicked.connect(self.send_hardware_command)
        type_layout.addWidget(self.hardware_button)
        
        self.software_button = QtWidgets.QPushButton("Software Command")
        self.software_button.clicked.connect(self.send_software_command)
        type_layout.addWidget(self.software_button)
        
        self.general_button = QtWidgets.QPushButton("General Command")
        self.general_button.clicked.connect(self.send_general_command)
        type_layout.addWidget(self.general_button)
        
        command_layout.addLayout(type_layout)
        
        # Auto-command settings
        auto_cmd_layout = QtWidgets.QHBoxLayout()
        
        self.auto_command_checkbox = QtWidgets.QCheckBox("Auto-send structured commands")
        self.auto_command_checkbox.stateChanged.connect(self.toggle_auto_commands)
        auto_cmd_layout.addWidget(self.auto_command_checkbox)
        
        auto_cmd_layout.addWidget(QtWidgets.QLabel("Interval (sec):"))
        self.command_interval_spinner = QtWidgets.QSpinBox()
        self.command_interval_spinner.setRange(2, 30)
        self.command_interval_spinner.setValue(7)
        self.command_interval_spinner.valueChanged.connect(self.update_command_timer_interval)
        auto_cmd_layout.addWidget(self.command_interval_spinner)
        
        # Multi-command test
        self.multi_command_button = QtWidgets.QPushButton("Send Command Stack")
        self.multi_command_button.clicked.connect(self.send_command_stack)
        auto_cmd_layout.addWidget(self.multi_command_button)
        
        command_layout.addLayout(auto_cmd_layout)
        
        auto_cmd_layout.addStretch()
        layout.addWidget(command_group)
    
    def create_log_panel(self, layout):
        """Create log display panel."""
        log_group = QtWidgets.QGroupBox("Test Log")
        log_layout = QtWidgets.QVBoxLayout(log_group)
        
        self.log_display = QtWidgets.QTextEdit()
        self.log_display.setMaximumHeight(150)
        self.log_display.setReadOnly(True)
        log_layout.addWidget(self.log_display)
        
        # Clear log button
        clear_button = QtWidgets.QPushButton("Clear Log")
        clear_button.clicked.connect(self.log_display.clear)
        log_layout.addWidget(clear_button)
        
        layout.addWidget(log_group)
        
    def log_message(self, message):
        """Add a message to the log display."""
        timestamp = time.strftime("%H:%M:%S")
        self.log_display.append(f"[{timestamp}] {message}")
        # Auto-scroll to bottom
        self.log_display.moveCursor(self.log_display.textCursor().End)
        
    def update_connection_status(self, connected, message):
        """Update connection status display."""
        if connected:
            self.connection_status_label.setText(f"Connected - {message}")
            self.connection_status_label.setStyleSheet("color: green; font-weight: bold;")
            self.manual_send_button.setEnabled(True)
            self.auto_send_checkbox.setEnabled(True)
            # Enable command buttons
            self.hardware_button.setEnabled(True)
            self.software_button.setEnabled(True)
            self.general_button.setEnabled(True)
            self.multi_command_button.setEnabled(True)
            self.auto_command_checkbox.setEnabled(True)
            self.log_message(f"✅ Connection established: {message}")
        else:
            self.connection_status_label.setText(f"Disconnected - {message}")
            self.connection_status_label.setStyleSheet("color: red; font-weight: bold;")
            self.manual_send_button.setEnabled(False)
            self.auto_send_checkbox.setEnabled(False)
            self.auto_send_checkbox.setChecked(False)
            # Disable command buttons
            self.hardware_button.setEnabled(False)
            self.software_button.setEnabled(False)
            self.general_button.setEnabled(False)
            self.multi_command_button.setEnabled(False)
            self.auto_command_checkbox.setEnabled(False)
            self.auto_command_checkbox.setChecked(False)
            self.log_message(f"❌ Connection failed: {message}")
    
    def update_frame(self, frame):
        """Update video frame in visualizer."""
        self.data_receive_counter += 1
        self.update_counters()
        self.visualizer.update_frame(frame)
        
        # Log every 50th frame to avoid spam
        if self.data_receive_counter % 50 == 0:
            fps = self.data_receive_counter / (time.time() - self.start_time)
            self.log_message(f"📹 Received {self.data_receive_counter} frames (avg {fps:.1f} FPS)")
    
    def add_distance(self, timestamp, distance):
        """Add distance measurement to visualizer."""
        self.visualizer.add_distance(timestamp, distance)
    
    def toggle_auto_send(self, state):
        """Toggle automatic dummy data sending."""
        if state == QtCore.Qt.Checked:
            interval_ms = self.interval_spinner.value() * 1000
            self.dummy_data_timer.start(interval_ms)
            message = f"🔄 Auto-send enabled: every {self.interval_spinner.value()} seconds"
            print(f"[Testbench] {message}")
            self.log_message(message)
        else:
            self.dummy_data_timer.stop()
            message = "⏹️ Auto-send disabled"
            print(f"[Testbench] {message}")
            self.log_message(message)
    
    def update_timer_interval(self, value):
        """Update the timer interval when spinner changes."""
        if self.dummy_data_timer.isActive():
            self.dummy_data_timer.stop()
            self.dummy_data_timer.start(value * 1000)
            message = f"⏱️ Interval updated to {value} seconds"
            print(f"[Testbench] {message}")
            self.log_message(message)
    
    def send_dummy_data(self):
        """Send legacy dummy data to Jetson for testing (backward compatibility)."""
        # Generate various types of test data
        test_data_types = [
            {"command": "adjust_camera", "brightness": round(random.uniform(0.1, 1.0), 2)},
            {"command": "set_roi", "x": random.randint(50, 200), "y": random.randint(50, 200), 
             "width": random.randint(100, 300), "height": random.randint(100, 300)},
            {"lidar_offset": round(random.uniform(-10.0, 10.0), 2)},
            {"sampling_rate": random.choice([10, 15, 20, 25, 30])},
            {"test_mode": random.choice(["normal", "debug", "calibration"])},
            {"timestamp": time.time(), "counter": self.data_send_counter}
        ]
        
        # Select random test data
        dummy_data = random.choice(test_data_types)
        
        # Add a test identifier
        dummy_data["test_id"] = f"legacy_testbench_{self.data_send_counter:04d}"
        
        # Send the data through the receiver thread
        if hasattr(self, 'receiver_thread') and self.receiver_thread.data_receiver:
            self.receiver_thread.send_data_to_jetson(dummy_data)
            self.data_send_counter += 1
            self.update_counters()
            message = f"📤 Sent legacy data #{self.data_send_counter}: {dummy_data}"
            print(f"[Testbench] {message}")
            self.log_message(message)
        else:
            message = "⚠️ Cannot send data - not connected to Jetson"
            print(f"[Testbench] {message}")
            self.log_message(message)
    
    def update_counters(self):
        """Update the data counter display."""
        uptime = time.time() - self.start_time
        self.data_counter_label.setText(
            f"Received: {self.data_receive_counter} | Legacy Sent: {self.data_send_counter} | "
            f"Commands Sent: {self.command_send_counter} | Uptime: {uptime:.0f}s"
        )
    
    # =================================================================
    # STRUCTURED COMMAND METHODS
    # =================================================================
    
    def toggle_auto_commands(self, state):
        """Toggle automatic structured command sending."""
        if state == QtCore.Qt.Checked:
            interval_ms = self.command_interval_spinner.value() * 1000
            self.command_timer.start(interval_ms)
            message = f"🔄 Auto-commands enabled: every {self.command_interval_spinner.value()} seconds"
            print(f"[Testbench] {message}")
            self.log_message(message)
        else:
            self.command_timer.stop()
            message = "⏹️ Auto-commands disabled"
            print(f"[Testbench] {message}")
            self.log_message(message)
    
    def update_command_timer_interval(self, value):
        """Update the command timer interval when spinner changes."""
        if self.command_timer.isActive():
            self.command_timer.stop()
            self.command_timer.start(value * 1000)
            message = f"⏱️ Command interval updated to {value} seconds"
            print(f"[Testbench] {message}")
            self.log_message(message)
    
    def send_hardware_command(self):
        """Send a random hardware command."""
        if not hasattr(self, 'receiver_thread') or not self.receiver_thread.data_receiver:
            self.log_message("⚠️ Cannot send command - not connected to Jetson")
            return
        
        cmd_list = self.receiver_thread.data_receiver.get_command_list()
        
        # Random hardware command
        commands = [
            cmd_list.create_roi_command(
                random.randint(50, 200), random.randint(50, 200),
                random.randint(100, 300), random.randint(100, 300)
            ),
            cmd_list.create_camera_adjustment_command(
                brightness=round(random.uniform(0.1, 1.0), 2),
                contrast=round(random.uniform(0.5, 2.0), 2)
            ),
            cmd_list.create_lidar_calibration_command(
                round(random.uniform(-10.0, 10.0), 2),
                random.choice([10, 15, 20, 25, 30])
            )
        ]
        
        command = random.choice(commands)
        self.receiver_thread.send_command_to_jetson(command)
        self.command_send_counter += 1
        self.update_counters()
        
        message = f"🔧 Sent hardware command: {command.action} (ID: {command.command_id})"
        self.log_message(message)
        print(f"[Testbench] {message}")
    
    def send_software_command(self):
        """Send a random software command."""
        if not hasattr(self, 'receiver_thread') or not self.receiver_thread.data_receiver:
            self.log_message("⚠️ Cannot send command - not connected to Jetson")
            return
        
        cmd_list = self.receiver_thread.data_receiver.get_command_list()
        
        # Random software command
        commands = [
            cmd_list.create_algorithm_config_command(
                random.choice(["froth_detection", "blob_analysis", "edge_detection"]),
                {
                    "threshold": round(random.uniform(0.1, 0.9), 2),
                    "sensitivity": round(random.uniform(0.5, 1.5), 2),
                    "filter_size": random.choice([3, 5, 7, 9])
                }
            ),
            cmd_list.create_processing_mode_command(
                random.choice(["normal", "debug", "calibration", "test"]),
                {"debug_level": random.randint(1, 5)}
            )
        ]
        
        command = random.choice(commands)
        self.receiver_thread.send_command_to_jetson(command)
        self.command_send_counter += 1
        self.update_counters()
        
        message = f"💻 Sent software command: {command.action} (ID: {command.command_id})"
        self.log_message(message)
        print(f"[Testbench] {message}")
    
    def send_general_command(self):
        """Send a random general command."""
        if not hasattr(self, 'receiver_thread') or not self.receiver_thread.data_receiver:
            self.log_message("⚠️ Cannot send command - not connected to Jetson")
            return
        
        cmd_list = self.receiver_thread.data_receiver.get_command_list()
        
        # Random general command
        commands = [
            cmd_list.create_system_status_command(),
            cmd_list.create_heartbeat_command("testbench_client")
        ]
        
        command = random.choice(commands)
        self.receiver_thread.send_command_to_jetson(command)
        self.command_send_counter += 1
        self.update_counters()
        
        message = f"🌐 Sent general command: {command.action} (ID: {command.command_id})"
        self.log_message(message)
        print(f"[Testbench] {message}")
    
    def send_command_stack(self):
        """Send multiple commands as a stack to test queuing."""
        if not hasattr(self, 'receiver_thread') or not self.receiver_thread.data_receiver:
            self.log_message("⚠️ Cannot send commands - not connected to Jetson")
            return
        
        cmd_list = self.receiver_thread.data_receiver.get_command_list()
        
        # Create a stack of different command types
        commands = [
            cmd_list.create_roi_command(100, 100, 200, 200, priority=CommandPriority.HIGH),
            cmd_list.create_camera_adjustment_command(brightness=0.8, priority=CommandPriority.NORMAL),
            cmd_list.create_algorithm_config_command("froth_detection", {"threshold": 0.6}, priority=CommandPriority.NORMAL),
            cmd_list.create_system_status_command(priority=CommandPriority.LOW)
        ]
        
        self.receiver_thread.send_commands_to_jetson(commands)
        self.command_send_counter += len(commands)
        self.update_counters()
        
        message = f"📚 Sent command stack: {len(commands)} commands (mixed types/priorities)"
        self.log_message(message)
        print(f"[Testbench] {message}")
        
        # Log each command
        for cmd in commands:
            self.log_message(f"  └─ {cmd.command_type.value}: {cmd.action} (Priority: {cmd.priority.name})")
    
    def send_structured_commands(self):
        """Automatically send structured commands (called by timer)."""
        # Randomly choose which type of command to send
        command_types = [self.send_hardware_command, self.send_software_command, self.send_general_command]
        
        # 10% chance to send a command stack instead
        if random.random() < 0.1:
            self.send_command_stack()
        else:
            random.choice(command_types)()

def main():
    app = QtWidgets.QApplication(sys.argv)

    # Create testbench window
    testbench = TestbenchWindow()
    testbench.show()

    # Create and start receiver thread
    receiver_thread = ReceiverThread(SELF_NETWORK_ADDRESS, SELF_NETWORK_PORT)
    testbench.receiver_thread = receiver_thread  # Store reference for sending data
    
    # Connect signals
    receiver_thread.data_received.connect(
        lambda data, frame: (
            testbench.update_frame(frame),
            testbench.add_distance(
                data.get("lidar_timestamp", time.time()), 
                data.get("lidar_reading", 0.0)
            )
        )
    )
    receiver_thread.connection_status.connect(testbench.update_connection_status)
    
    receiver_thread.start()

    try:
        exit_code = app.exec_()
    except KeyboardInterrupt:
        print("\n[Testbench] Interrupted by user")
    finally:
        print("[Testbench] Shutting down...")
        receiver_thread.stop()
        receiver_thread.wait(3000)  # Wait up to 3 seconds
        if receiver_thread.isRunning():
            print("[Testbench] Force terminating receiver thread...")
            receiver_thread.terminate()
        
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
