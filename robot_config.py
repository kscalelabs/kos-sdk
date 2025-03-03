"""
Configuration module for robot IP addresses and settings.
This module lets you easily switch between different robots.
"""

from enum import Enum

class RobotType(Enum):
    """Enum defining different robot types for easy selection."""
    ALUM1 = "alum1"
    WHITE = "white"
    # Add more robots as needed
    DEFAULT = "default"

# Robot IP address mapping
ROBOT_IPS = {
    RobotType.ALUM1: "10.33.85.8",
    RobotType.WHITE: "10.33.14.50",
    RobotType.DEFAULT: "192.168.42.1"  # Default IP from run.py
}

# Add any robot-specific configurations here if needed
ROBOT_CONFIGS = {
    RobotType.ALUM1: {},
    RobotType.WHITE: {},
    RobotType.DEFAULT: {}
}

def get_robot_ip(robot_type: RobotType = RobotType.DEFAULT) -> str:
    """Get the IP address for the specified robot type."""
    return ROBOT_IPS.get(robot_type, ROBOT_IPS[RobotType.DEFAULT])

def get_robot_config(robot_type: RobotType = RobotType.DEFAULT) -> dict:
    """Get any special configurations for the specified robot type."""
    return ROBOT_CONFIGS.get(robot_type, ROBOT_CONFIGS[RobotType.DEFAULT])