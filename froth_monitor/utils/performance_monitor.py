import time
import json
import threading
import os
from datetime import datetime
from typing import Dict, Any, List
from froth_monitor.handlers.logger_config import get_logger

logger = get_logger(__name__)

class PerformanceMonitor:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(PerformanceMonitor, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
            
        self._initialized = True
        # Use absolute path to ensure logging works even if CWD changes
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        self.log_dir = os.path.join(base_dir, "logs")
        self.log_file = os.path.join(self.log_dir, "performance_log.jsonl")
        
        # Ensure log directory exists
        os.makedirs(self.log_dir, exist_ok=True)
        
        # Buffering
        self.buffer: List[Dict[str, Any]] = []
        self.buffer_size = 100
        self.buffer_lock = threading.Lock()
        
        # Current frame timing storage
        self.current_frame_timings: Dict[str, float] = {}
        self.start_times: Dict[str, float] = {}
        
        logger.info(f"Performance monitor: Performance monitor initialized. Logging to {self.log_file}")

    def start_timer(self, tag: str):
        """Start a timer for a specific tag."""
        self.start_times[tag] = time.perf_counter()

    def stop_timer(self, tag: str):
        """Stop the timer for a tag and record the duration."""
        if tag in self.start_times:
            duration = time.perf_counter() - self.start_times[tag]
            self.current_frame_timings[tag] = duration
            del self.start_times[tag]

    def log_frame(self, frame_id: int):
        """
        Commit the current frame's timings to the buffer.
        Should be called at the end of frame processing.
        """
        if not self.current_frame_timings:
            return

        record = {
            "timestamp": datetime.now().isoformat(),
            "frame_id": frame_id,
            "timings": self.current_frame_timings.copy()
        }
        
        with self.buffer_lock:
            self.buffer.append(record)
            if len(self.buffer) >= self.buffer_size:
                self._flush_buffer()
        
        # Reset for next frame
        # Reset for next frame
        self.current_frame_timings.clear()
        self.start_times.clear()

    def log_generic_event(self, event_type: str, details: Dict[str, Any]):
        """
        Log a generic event not tied to a specific frame (e.g., background tasks).
        Thread-safe.
        """
        record = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "details": details
        }
        
        with self.buffer_lock:
            self.buffer.append(record)
            if len(self.buffer) >= self.buffer_size:
                self._flush_buffer()

    def _flush_buffer(self):
        """Write buffered records to disk."""
        try:
            with open(self.log_file, "a") as f:
                for record in self.buffer:
                    f.write(json.dumps(record) + "\n")
            self.buffer.clear()
        except Exception as e:
            logger.error(f"Failed to flush performance logs: {e}")

    def flush(self):
        """Manually flush remaining records."""
        with self.buffer_lock:
            if self.buffer:
                self._flush_buffer()
