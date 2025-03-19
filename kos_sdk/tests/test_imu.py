import time
from dataclasses import dataclass
from typing import Any, Dict, List

import matplotlib.pyplot as plt
import numpy as np
from loguru import logger

from kos_sdk.utils.robot import RobotInterface


@dataclass
class ImuTestResults:
    """Results from running the IMU test."""

    avg_rate: float
    total_samples: int
    duration: float
    accel_x: List[float]
    accel_y: List[float]
    accel_z: List[float]
    gyro_x: List[float]
    gyro_y: List[float]
    gyro_z: List[float]


async def collect_data(robot_ip: str = "", duration_seconds: int = 5) -> Dict[str, Any]:
    """Collect IMU data for the specified duration."""
    try:
        async with RobotInterface(robot_ip) as robot:
            logger.info(f"Starting IMU test for {duration_seconds} seconds...")

            # Initialize data storage
            count = 0
            start_time = time.time()
            end_time = start_time + duration_seconds

            accel_x, accel_y, accel_z = [], [], []
            gyro_x, gyro_y, gyro_z = [], [], []

            # Collect data
            while time.time() < end_time:
                imu_values = await robot.kos.imu.get_imu_values()
                count += 1

                accel_x.append(imu_values.accel_x)
                accel_y.append(imu_values.accel_y)
                accel_z.append(imu_values.accel_z)
                gyro_x.append(imu_values.gyro_x)
                gyro_y.append(imu_values.gyro_y)
                gyro_z.append(imu_values.gyro_z)

            # Calculate results
            elapsed_time = time.time() - start_time
            avg_rate = count / elapsed_time

            stats_str = f"Test Complete: {count} samples, {elapsed_time:.2f}s"
            logger.info(f"{stats_str}, {avg_rate:.2f} Hz")

            # Create results object
            results = ImuTestResults(
                avg_rate=avg_rate,
                total_samples=count,
                duration=elapsed_time,
                accel_x=accel_x,
                accel_y=accel_y,
                accel_z=accel_z,
                gyro_x=gyro_x,
                gyro_y=gyro_y,
                gyro_z=gyro_z,
            )

            # Calculate statistics
            accel_stats = {
                "x_mean": np.mean(accel_x),
                "y_mean": np.mean(accel_y),
                "z_mean": np.mean(accel_z),
                "x_std": np.std(accel_x),
                "y_std": np.std(accel_y),
                "z_std": np.std(accel_z),
            }

            gyro_stats = {
                "x_mean": np.mean(gyro_x),
                "y_mean": np.mean(gyro_y),
                "z_mean": np.mean(gyro_z),
                "x_std": np.std(gyro_x),
                "y_std": np.std(gyro_y),
                "z_std": np.std(gyro_z),
            }

            return {
                "success": True,
                "message": "IMU test completed successfully",
                "avg_rate": avg_rate,
                "total_samples": count,
                "duration": elapsed_time,
                "accel_stats": accel_stats,
                "gyro_stats": gyro_stats,
                "results": results,
            }

    except Exception as e:
        logger.error(f"Error testing IMU: {e}", exc_info=True)
        return {"success": False, "message": f"Error testing IMU: {str(e)}"}


async def plot_imu_data(robot_ip: str = "", duration_seconds: int = 5) -> Dict[str, Any]:
    """Collect IMU data and generate plots."""
    try:
        # Collect data
        result = await collect_data(robot_ip, duration_seconds)
        if not result.get("success", False):
            return result

        results = result["results"]
        times = np.linspace(0, results.duration, len(results.accel_x))

        # Create plots
        fig, (ax_accel, ax_gyro) = plt.subplots(1, 2, figsize=(12, 5))
        fig.suptitle("IMU Sensor Data Analysis", fontsize=16)

        # Plot acceleration
        ax_accel.plot(times, results.accel_x, label="X")
        ax_accel.plot(times, results.accel_y, label="Y")
        ax_accel.plot(times, results.accel_z, label="Z")
        ax_accel.set_xlabel("Time (seconds)")
        ax_accel.set_ylabel("Acceleration (m/s²)")
        ax_accel.set_title("Acceleration")
        ax_accel.grid(True)
        ax_accel.legend()

        # Plot gyroscope
        ax_gyro.plot(times, results.gyro_x, label="X")
        ax_gyro.plot(times, results.gyro_y, label="Y")
        ax_gyro.plot(times, results.gyro_z, label="Z")
        ax_gyro.set_xlabel("Time (seconds)")
        ax_gyro.set_ylabel("Gyro (deg/s)")
        ax_gyro.set_title("Gyroscope")
        ax_gyro.grid(True)
        ax_gyro.legend()

        plt.tight_layout(rect=(0, 0, 1, 0.96))
        plt.show()

        return {"success": True, "message": "IMU data plotted successfully", "results": results}

    except Exception as e:
        return {"success": False, "message": f"Error plotting IMU data: {str(e)}"}
