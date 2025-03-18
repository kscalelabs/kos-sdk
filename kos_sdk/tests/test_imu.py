import asyncio
from typing import Any, Dict

from utils.imu_utils import collect_data, plot_imu_data


def collect_data_sync(robot_ip: str = "", duration_seconds: int = 5) -> Dict[str, Any]:
    """Synchronous wrapper for collect_data."""
    return asyncio.run(collect_data(robot_ip, duration_seconds))


def plot_imu_data_sync(robot_ip: str = "", duration_seconds: int = 5) -> Dict[str, Any]:
    """Synchronous wrapper for plot_imu_data."""
    return asyncio.run(plot_imu_data(robot_ip, duration_seconds))


__all__ = ["collect_data_sync", "plot_imu_data_sync"]