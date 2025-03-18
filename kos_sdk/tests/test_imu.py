import asyncio
from typing import Any, Dict
import matplotlib.pyplot as plt
import numpy as np
from utils.imu_utils import collect_data


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
        fig, axs = plt.subplots(2, 2, figsize=(12, 10))
        fig.suptitle("IMU Sensor Data Analysis", fontsize=16)
        ax_rate, ax_accel, ax_gyro, ax_mag = axs.flatten()
        
        # Plot sampling rate
        ax_rate.plot(
            results.timestamps[1:], 
            results.samples_per_second[1:],
            marker="o", 
            linestyle="-", 
            label="Samples/second"
        )
        ax_rate.set_xlabel("Time (seconds)")
        ax_rate.set_ylabel("Samples per Second")
        ax_rate.set_title("IMU Sampling Rate")
        ax_rate.grid(True)
        ax_rate.legend()
        
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
        
        # Plot magnetometer
        ax_mag.plot(times, results.mag_x, label="X")
        ax_mag.plot(times, results.mag_y, label="Y")
        ax_mag.plot(times, results.mag_z, label="Z")
        ax_mag.set_xlabel("Time (seconds)")
        ax_mag.set_ylabel("Mag (units)")
        ax_mag.set_title("Magnetometer")
        ax_mag.grid(True)
        ax_mag.legend()
        
        plt.tight_layout(rect=[0, 0, 1, 0.96])
        plt.show()
        
        return {
            "success": True, 
            "message": "IMU data plotted successfully", 
            "results": results
        }
        
    except Exception as e:
        return {"success": False, "message": f"Error plotting IMU data: {str(e)}"}

# Synchronous wrapper
def plot_imu_data_sync(robot_ip: str = "", duration_seconds: int = 5) -> Dict[str, Any]:
    """Synchronous wrapper for plot_imu_data."""
    return asyncio.run(plot_imu_data(robot_ip, duration_seconds))

# Define exports
__all__ = ["plot_imu_data_sync"]