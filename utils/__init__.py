"""Utility modules for robot control"""

from .config import (
    config,  # Dynamic config instance
    # Constants for backward compatibility
    ROBOT_IP,
    ROBOT_MODEL,
    DEFAULT_HZ,
    DEFAULT_TARGET_HZ,
    DEFAULT_KP,
    DEFAULT_KD,
)

__all__ = [
    "config",
    "ROBOT_IP",
    "ROBOT_MODEL",
    "DEFAULT_HZ",
    "DEFAULT_TARGET_HZ",
    "DEFAULT_KP",
    "DEFAULT_KD",
]
