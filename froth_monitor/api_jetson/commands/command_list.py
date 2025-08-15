"""
Command List System for Jetson Communication Interface

This module defines a structured command system with three types of commands:
- software_command: Software/algorithm related commands
- hardware_command: Hardware control commands  
- general_command: General system commands

Commands can be queued and combined, with proper validation and serialization.
"""

import time
import uuid
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, asdict
from enum import Enum
import json


class CommandType(Enum):
    """Enumeration of command types."""
    SOFTWARE = "software_command"
    HARDWARE = "hardware_command" 
    GENERAL = "general_command"


class CommandPriority(Enum):
    """Command priority levels."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class Command:
    """Base command structure."""
    command_id: str
    command_type: CommandType
    action: str
    parameters: Dict[str, Any]
    timestamp: float
    priority: CommandPriority = CommandPriority.NORMAL
    timeout: Optional[float] = None
    retry_count: int = 0
    max_retries: int = 3
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert command to dictionary for JSON serialization."""
        return {
            "command_id": self.command_id,
            "command_type": self.command_type.value,
            "action": self.action,
            "parameters": self.parameters,
            "timestamp": self.timestamp,
            "priority": self.priority.value,
            "timeout": self.timeout,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Command':
        """Create command from dictionary."""
        return cls(
            command_id=data["command_id"],
            command_type=CommandType(data["command_type"]),
            action=data["action"],
            parameters=data["parameters"],
            timestamp=data["timestamp"],
            priority=CommandPriority(data["priority"]),
            timeout=data.get("timeout"),
            retry_count=data.get("retry_count", 0),
            max_retries=data.get("max_retries", 3)
        )


class CommandList:
    """
    Centralized command management system for Jetson communication.
    
    Handles command creation, queuing, validation, and serialization.
    Supports command stacking when multiple commands are queued.
    """
    
    def __init__(self):
        self.command_queue: List[Command] = []
        self.command_history: List[Command] = []
        self.max_history_size = 100
        
    # =================================================================
    # HARDWARE COMMANDS
    # =================================================================
    
    def create_roi_command(self, x: int, y: int, width: int, height: int, 
                          roi_id: Optional[str] = None, priority: CommandPriority = CommandPriority.NORMAL) -> Command:
        """
        Create ROI (Region of Interest) hardware command.
        
        Args:
            x: X coordinate of ROI top-left corner
            y: Y coordinate of ROI top-left corner  
            width: Width of ROI rectangle
            height: Height of ROI rectangle
            roi_id: Optional ROI identifier
            priority: Command priority
            
        Returns:
            Command object for ROI setting
        """
        return Command(
            command_id=self._generate_command_id("roi"),
            command_type=CommandType.HARDWARE,
            action="set_roi",
            parameters={
                "x": x,
                "y": y,
                "width": width,
                "height": height,
                "roi_id": roi_id or f"roi_{int(time.time())}"
            },
            timestamp=time.time(),
            priority=priority,
            timeout=5.0  # 5 second timeout for hardware commands
        )
    
    def create_camera_adjustment_command(self, brightness: Optional[float] = None, 
                                       contrast: Optional[float] = None,
                                       exposure: Optional[float] = None,
                                       priority: CommandPriority = CommandPriority.NORMAL) -> Command:
        """
        Create camera adjustment hardware command.
        
        Args:
            brightness: Brightness level (0.0 to 1.0)
            contrast: Contrast level (0.0 to 2.0)
            exposure: Exposure level (-10.0 to 10.0)
            priority: Command priority
            
        Returns:
            Command object for camera adjustment
        """
        parameters = {}
        if brightness is not None:
            parameters["brightness"] = max(0.0, min(1.0, brightness))
        if contrast is not None:
            parameters["contrast"] = max(0.0, min(2.0, contrast))
        if exposure is not None:
            parameters["exposure"] = max(-10.0, min(10.0, exposure))
            
        return Command(
            command_id=self._generate_command_id("camera"),
            command_type=CommandType.HARDWARE,
            action="adjust_camera",
            parameters=parameters,
            timestamp=time.time(),
            priority=priority,
            timeout=3.0
        )
    
    def create_lidar_calibration_command(self, offset_mm: float, 
                                       sampling_rate: Optional[int] = None,
                                       priority: CommandPriority = CommandPriority.HIGH) -> Command:
        """
        Create LiDAR calibration hardware command.
        
        Args:
            offset_mm: Offset calibration in millimeters
            sampling_rate: Optional sampling rate (Hz)
            priority: Command priority
            
        Returns:
            Command object for LiDAR calibration
        """
        parameters = {"offset_mm": offset_mm}
        if sampling_rate is not None:
            parameters["sampling_rate"] = max(1, min(100, sampling_rate))
            
        return Command(
            command_id=self._generate_command_id("lidar"),
            command_type=CommandType.HARDWARE,
            action="calibrate_lidar",
            parameters=parameters,
            timestamp=time.time(),
            priority=priority,
            timeout=10.0  # Longer timeout for calibration
        )
    
    # =================================================================
    # SOFTWARE COMMANDS  
    # =================================================================
    
    def create_algorithm_config_command(self, algorithm: str, config: Dict[str, Any],
                                      priority: CommandPriority = CommandPriority.NORMAL) -> Command:
        """
        Create algorithm configuration software command.
        
        Args:
            algorithm: Algorithm name (e.g., "froth_detection", "blob_analysis")
            config: Configuration parameters
            priority: Command priority
            
        Returns:
            Command object for algorithm configuration
        """
        return Command(
            command_id=self._generate_command_id("algo"),
            command_type=CommandType.SOFTWARE,
            action="configure_algorithm",
            parameters={
                "algorithm": algorithm,
                "config": config
            },
            timestamp=time.time(),
            priority=priority,
            timeout=15.0
        )
    
    def create_processing_mode_command(self, mode: str, parameters: Optional[Dict[str, Any]] = None,
                                     priority: CommandPriority = CommandPriority.NORMAL) -> Command:
        """
        Create processing mode software command.
        
        Args:
            mode: Processing mode ("normal", "debug", "calibration", "test")
            parameters: Optional mode-specific parameters
            priority: Command priority
            
        Returns:
            Command object for processing mode change
        """
        return Command(
            command_id=self._generate_command_id("mode"),
            command_type=CommandType.SOFTWARE,
            action="set_processing_mode",
            parameters={
                "mode": mode,
                "parameters": parameters or {}
            },
            timestamp=time.time(),
            priority=priority,
            timeout=5.0
        )
    
    # =================================================================
    # GENERAL COMMANDS
    # =================================================================
    
    def create_system_status_command(self, priority: CommandPriority = CommandPriority.LOW) -> Command:
        """
        Create system status general command.
        
        Args:
            priority: Command priority
            
        Returns:
            Command object for system status request
        """
        return Command(
            command_id=self._generate_command_id("status"),
            command_type=CommandType.GENERAL,
            action="get_system_status",
            parameters={},
            timestamp=time.time(),
            priority=priority,
            timeout=10.0
        )
    
    def create_heartbeat_command(self, client_id: str, priority: CommandPriority = CommandPriority.LOW) -> Command:
        """
        Create heartbeat general command.
        
        Args:
            client_id: Identifier of the client sending heartbeat
            priority: Command priority
            
        Returns:
            Command object for heartbeat
        """
        return Command(
            command_id=self._generate_command_id("heartbeat"),
            command_type=CommandType.GENERAL,
            action="heartbeat",
            parameters={
                "client_id": client_id,
                "client_timestamp": time.time()
            },
            timestamp=time.time(),
            priority=priority,
            timeout=2.0
        )
    
    def create_shutdown_command(self, force: bool = False, 
                              priority: CommandPriority = CommandPriority.CRITICAL) -> Command:
        """
        Create system shutdown general command.
        
        Args:
            force: Whether to force shutdown
            priority: Command priority
            
        Returns:
            Command object for system shutdown
        """
        return Command(
            command_id=self._generate_command_id("shutdown"),
            command_type=CommandType.GENERAL,
            action="shutdown_system",
            parameters={
                "force": force,
                "requested_by": "testbench"
            },
            timestamp=time.time(),
            priority=priority,
            timeout=30.0
        )
    
    # =================================================================
    # QUEUE MANAGEMENT
    # =================================================================
    
    def add_command(self, command: Command) -> bool:
        """
        Add command to the queue.
        
        Args:
            command: Command to add
            
        Returns:
            True if command was added successfully
        """
        if self._validate_command(command):
            self.command_queue.append(command)
            self._sort_queue_by_priority()
            return True
        return False
    
    def add_commands(self, commands: List[Command]) -> int:
        """
        Add multiple commands to the queue.
        
        Args:
            commands: List of commands to add
            
        Returns:
            Number of commands successfully added
        """
        added_count = 0
        for command in commands:
            if self.add_command(command):
                added_count += 1
        return added_count
    
    def get_next_command(self) -> Optional[Command]:
        """
        Get and remove the next command from the queue.
        
        Returns:
            Next command or None if queue is empty
        """
        if self.command_queue:
            command = self.command_queue.pop(0)
            self._add_to_history(command)
            return command
        return None
    
    def peek_next_command(self) -> Optional[Command]:
        """
        Look at the next command without removing it.
        
        Returns:
            Next command or None if queue is empty
        """
        return self.command_queue[0] if self.command_queue else None
    
    def get_all_commands(self) -> List[Command]:
        """
        Get all queued commands and clear the queue.
        
        Returns:
            List of all queued commands
        """
        commands = self.command_queue.copy()
        for command in commands:
            self._add_to_history(command)
        self.command_queue.clear()
        return commands
    
    def clear_queue(self):
        """Clear all commands from the queue."""
        self.command_queue.clear()
    
    def get_queue_size(self) -> int:
        """Get the number of commands in the queue."""
        return len(self.command_queue)
    
    def is_empty(self) -> bool:
        """Check if the command queue is empty."""
        return len(self.command_queue) == 0
    
    # =================================================================
    # SERIALIZATION
    # =================================================================
    
    def serialize_commands(self, commands: Optional[List[Command]] = None) -> Dict[str, Any]:
        """
        Serialize commands to JSON-compatible dictionary.
        
        Args:
            commands: Commands to serialize (uses queue if None)
            
        Returns:
            Serialized command data
        """
        if commands is None:
            commands = self.command_queue
            
        return {
            "command_batch": [cmd.to_dict() for cmd in commands],
            "batch_id": str(uuid.uuid4()),
            "batch_timestamp": time.time(),
            "total_commands": len(commands)
        }
    
    def to_json_string(self, commands: Optional[List[Command]] = None) -> str:
        """
        Convert commands to JSON string.
        
        Args:
            commands: Commands to serialize (uses queue if None)
            
        Returns:
            JSON string representation
        """
        return json.dumps(self.serialize_commands(commands), indent=2)
    
    # =================================================================
    # HELPER METHODS
    # =================================================================
    
    def _generate_command_id(self, prefix: str) -> str:
        """Generate unique command ID."""
        return f"{prefix}_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"
    
    def _validate_command(self, command: Command) -> bool:
        """Validate command structure and parameters."""
        if not command.command_id or not command.action:
            return False
        if not isinstance(command.parameters, dict):
            return False
        return True
    
    def _sort_queue_by_priority(self):
        """Sort command queue by priority (highest first)."""
        self.command_queue.sort(key=lambda cmd: cmd.priority.value, reverse=True)
    
    def _add_to_history(self, command: Command):
        """Add command to history with size limit."""
        self.command_history.append(command)
        if len(self.command_history) > self.max_history_size:
            self.command_history.pop(0)
    
    # =================================================================
    # STATUS AND DEBUGGING
    # =================================================================
    
    def get_queue_summary(self) -> Dict[str, Any]:
        """Get summary of current queue state."""
        type_counts = {}
        priority_counts = {}
        
        for cmd in self.command_queue:
            cmd_type = cmd.command_type.value
            priority = cmd.priority.name
            
            type_counts[cmd_type] = type_counts.get(cmd_type, 0) + 1
            priority_counts[priority] = priority_counts.get(priority, 0) + 1
        
        return {
            "total_commands": len(self.command_queue),
            "commands_by_type": type_counts,
            "commands_by_priority": priority_counts,
            "next_command": self.peek_next_command().action if self.peek_next_command() else None # type: ignore
        }
    
    def print_queue_status(self):
        """Print current queue status to console."""
        summary = self.get_queue_summary()
        print(f"\n📋 Command Queue Status:")
        print(f"   Total commands: {summary['total_commands']}")
        print(f"   By type: {summary['commands_by_type']}")
        print(f"   By priority: {summary['commands_by_priority']}")
        print(f"   Next command: {summary['next_command']}")


# =================================================================
# CONVENIENCE FUNCTIONS
# =================================================================

def create_command_list() -> CommandList:
    """Create a new CommandList instance."""
    return CommandList()


# Example usage and testing
if __name__ == "__main__":
    # Create command list
    cmd_list = CommandList()
    
    # Create some example commands
    roi_cmd = cmd_list.create_roi_command(100, 150, 200, 250)
    camera_cmd = cmd_list.create_camera_adjustment_command(brightness=0.7, contrast=1.2)
    algo_cmd = cmd_list.create_algorithm_config_command("froth_detection", {"threshold": 0.5})
    status_cmd = cmd_list.create_system_status_command()
    
    # Add commands to queue
    cmd_list.add_commands([roi_cmd, camera_cmd, algo_cmd, status_cmd])
    
    # Print status
    cmd_list.print_queue_status()
    
    # Serialize commands
    print(f"\n📦 Serialized commands:")
    print(cmd_list.to_json_string())