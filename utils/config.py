"""Configuration loader for robot settings with runtime update support"""

import yaml
import os
from typing import Dict, Any
from loguru import logger


class DynamicConfig:
    """Configuration manager that supports runtime updates from YAML"""

    def __init__(self):
        self._config: Dict[str, Any] = {}
        self._config_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "config.yaml"
        )
        self.reload()

    def reload(self) -> None:
        """Reload configuration from YAML file"""
        try:
            with open(self._config_path, "r") as f:
                self._config = yaml.safe_load(f)
            logger.info("Configuration reloaded successfully")
        except Exception as e:
            logger.error(f"Failed to reload configuration: {e}")

    @property
    def robot_ip(self) -> str:
        """Get robot IP with live reload support"""
        return self._config["robot"]["network"]["ip"]

    @property
    def robot_model(self) -> str:
        """Get robot model with live reload support"""
        return self._config["robot"]["model"]

    @property
    def default_hz(self) -> int:
        """Get default Hz with live reload support"""
        return self._config["control"]["hz"]

    @property
    def default_target_hz(self) -> int:
        """Get default target Hz with live reload support"""
        return self._config["control"]["target_hz"]

    @property
    def default_kp(self) -> int:
        """Get default Kp with live reload support"""
        return self._config["control"]["pid"]["kp"]

    @property
    def default_kd(self) -> int:
        """Get default Kd with live reload support"""
        return self._config["control"]["pid"]["kd"]

    @property
    def raw_config(self) -> Dict[str, Any]:
        """Get the raw configuration dictionary"""
        return self._config.copy()


# Create a singleton instance
config = DynamicConfig()

# For backwards compatibility
ROBOT_IP = config.robot_ip
ROBOT_MODEL = config.robot_model
DEFAULT_HZ = config.default_hz
DEFAULT_TARGET_HZ = config.default_target_hz
DEFAULT_KP = config.default_kp
DEFAULT_KD = config.default_kd
