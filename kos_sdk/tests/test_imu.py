"""
IMU Testing Module for KOS Robots
================================

This module provides tools for testing and analyzing the Inertial Measurement Unit (IMU)
on KOS robots. It allows you to measure performance, visualize orientation data,
and analyze sensor stability.

Available Functions:
------------------
test_imu_sync(robot_ip="10.33.10.65", duration_seconds=5)
    Run a performance test on the IMU and return detailed statistics.

plot_imu_data_sync(robot_ip="10.33.10.65", duration_seconds=5)
    Collect IMU data and generate plots showing acceleration, gyroscope, and magnetometer readings.

visualize_orientation_sync(robot_ip="10.33.10.65", duration_seconds=10)
    Display a real-time 3D visualization of the robot's orientation.

get_imu_values_sync(robot_ip="10.33.10.65")
    Get a single reading from the IMU sensors.

Technical Details:
----------------
- Measures IMU sampling rate and stability
- Visualizes 3D orientation using Euler angles
- Plots acceleration, gyroscope, and magnetometer data
- Provides statistical analysis of sensor performance

Example Usage:
------------
# Import the module
from kos_sdk.tests import imu

# Run a basic IMU test
result = imu.test_imu_sync()
print(f"IMU sampling rate: {result['avg_rate']} Hz")

# Generate plots of IMU data
imu.plot_imu_data_sync()

# Visualize orientation in real-time
imu.visualize_orientation_sync(duration_seconds=30)
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pykos
from mpl_toolkits.mplot3d import Axes3D

# Configure logging
logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_ROBOT_IP = "10.33.10.65"


@dataclass
class ImuTestResults:
    """Results from running the IMU test."""

    avg_rate: float
    total_samples: int
    duration: float
    timestamps: List[float]
    samples_per_second: List[int]
    accel_x: List[float]
    accel_y: List[float]
    accel_z: List[float]
    gyro_x: List[float]
    gyro_y: List[float]
    gyro_z: List[float]
    mag_x: List[float]
    mag_y: List[float]
    mag_z: List[float]


async def connect_to_robot(robot_ip: str) -> Optional[pykos.KOS]:
    """Connect to a robot and verify the connection."""
    try:
        logger.info(f"Connecting to robot at {robot_ip}...")
        kos = pykos.KOS(ip=robot_ip)

        # Test connection with a simple query
        await kos.imu.get_imu_values()
        logger.info("✅ Successfully connected to robot")
        return kos
    except Exception as e:
        logger.error(f"❌ Failed to connect to robot: {e}")
        return None


async def test_imu(robot_ip: str = DEFAULT_ROBOT_IP, duration_seconds: int = 5) -> Dict[str, Any]:
    """Run IMU performance and data collection test."""
    kos = await connect_to_robot(robot_ip)
    if not kos:
        return {"success": False, "message": "Failed to connect to robot"}

    try:
        logger.info(f"Starting IMU test for {duration_seconds} seconds...")

        count = 0
        start_time = time.time()
        end_time = start_time + duration_seconds

        timestamps: List[float] = []
        samples_per_second: List[int] = []
        accel_x: List[float] = []
        accel_y: List[float] = []
        accel_z: List[float] = []
        gyro_x: List[float] = []
        gyro_y: List[float] = []
        gyro_z: List[float] = []
        mag_x: List[float] = []
        mag_y: List[float] = []
        mag_z: List[float] = []

        last_second = int(start_time)
        second_count = 0

        while time.time() < end_time:
            # Get IMU values
            imu_values = await kos.imu.get_imu_values()
            count += 1
            second_count += 1

            # Store values
            accel_x.append(imu_values.accel_x)
            accel_y.append(imu_values.accel_y)
            accel_z.append(imu_values.accel_z)
            gyro_x.append(imu_values.gyro_x)
            gyro_y.append(imu_values.gyro_y)
            gyro_z.append(imu_values.gyro_z)
            mag_x.append(imu_values.mag_x if imu_values.mag_x is not None else 0.0)
            mag_y.append(imu_values.mag_y if imu_values.mag_y is not None else 0.0)
            mag_z.append(imu_values.mag_z if imu_values.mag_z is not None else 0.0)

            # Track samples per second
            current_second = int(time.time())
            if current_second != last_second:
                timestamps.append(current_second - start_time)
                samples_per_second.append(second_count)
                logger.info(
                    f"Time: {current_second - start_time:.2f} seconds - "
                    f"Samples this second: {second_count}"
                )
                second_count = 0
                last_second = current_second

        elapsed_time = time.time() - start_time
        avg_rate = count / elapsed_time

        logger.info("Test Complete:")
        logger.info(f"Total samples: {count}")
        logger.info(f"Elapsed time: {elapsed_time:.2f} seconds")
        logger.info(f"Average sampling rate: {avg_rate:.2f} Hz")

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

        # Create results object
        results = ImuTestResults(
            avg_rate=avg_rate,
            total_samples=count,
            duration=elapsed_time,
            timestamps=timestamps,
            samples_per_second=samples_per_second,
            accel_x=accel_x,
            accel_y=accel_y,
            accel_z=accel_z,
            gyro_x=gyro_x,
            gyro_y=gyro_y,
            gyro_z=gyro_z,
            mag_x=mag_x,
            mag_y=mag_y,
            mag_z=mag_z,
        )

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
        logger.error(f"Error testing IMU: {e}")
        return {"success": False, "message": f"Error testing IMU: {str(e)}"}


async def plot_imu_data(robot_ip: str = DEFAULT_ROBOT_IP, duration_seconds: int = 5) -> Dict[str, Any]:
    """Collect IMU data and generate plots."""
    try:
        # Run the IMU test to collect data
        result = await test_imu(robot_ip, duration_seconds)

        if not result.get("success", False):
            return result

        results = result["results"]

        # Create figure with 2x2 subplots
        fig, axs = plt.subplots(2, 2, figsize=(12, 10))
        fig.suptitle("IMU Sensor Data Analysis", fontsize=16)
        ax_rate, ax_accel, ax_gyro, ax_mag = axs.flatten()

        times = np.linspace(0, results.duration, len(results.accel_x))

        # Plot 1: Sampling rate over time
        ax_rate.plot(
            results.timestamps[1:], 
            results.samples_per_second[1:], 
            marker="o", 
            linestyle="-", 
            label="Samples/second"
        )
        ax_rate.set_xlabel("Time (seconds)")
        ax_rate.set_ylabel("Samples per Second")
        ax_rate.set_title("IMU Sampling Rate Over Time")
        ax_rate.grid(True)
        ax_rate.legend()

        # Plot 2: IMU acceleration values over time
        ax_accel.plot(times, results.accel_x, label="Acc X")
        ax_accel.plot(times, results.accel_y, label="Acc Y")
        ax_accel.plot(times, results.accel_z, label="Acc Z")
        ax_accel.set_xlabel("Time (seconds)")
        ax_accel.set_ylabel("Acceleration (m/s²)")
        ax_accel.set_title("IMU Acceleration")
        ax_accel.grid(True)
        ax_accel.legend()

        # Plot 3: Gyroscope values over time
        ax_gyro.plot(times, results.gyro_x, label="Gyro X")
        ax_gyro.plot(times, results.gyro_y, label="Gyro Y")
        ax_gyro.plot(times, results.gyro_z, label="Gyro Z")
        ax_gyro.set_xlabel("Time (seconds)")
        ax_gyro.set_ylabel("Gyro (deg/s)")
        ax_gyro.set_title("IMU Gyroscope")
        ax_gyro.grid(True)
        ax_gyro.legend()

        # Plot 4: Magnetometer values over time
        ax_mag.plot(times, results.mag_x, label="Mag X")
        ax_mag.plot(times, results.mag_y, label="Mag Y")
        ax_mag.plot(times, results.mag_z, label="Mag Z")
        ax_mag.set_xlabel("Time (seconds)")
        ax_mag.set_ylabel("Mag (units)")
        ax_mag.set_title("IMU Magnetometer")
        ax_mag.grid(True)
        ax_mag.legend()

        plt.tight_layout(rect=[0, 0, 1, 0.96])  # Adjust for the suptitle
        plt.show()

        return {"success": True, "message": "IMU data plotted successfully", "results": results}

    except Exception as e:
        logger.error(f"Error plotting IMU data: {e}")
        return {"success": False, "message": f"Error plotting IMU data: {str(e)}"}


async def get_imu_values(robot_ip: str = DEFAULT_ROBOT_IP) -> Dict[str, Any]:
    """Get a single reading from the IMU sensors."""
    kos = await connect_to_robot(robot_ip)
    if not kos:
        return {"success": False, "message": "Failed to connect to robot"}

    try:
        imu_values = await kos.imu.get_imu_values()

        return {
            "success": True,
            "message": "IMU values retrieved successfully",
            "accel_x": imu_values.accel_x,
            "accel_y": imu_values.accel_y,
            "accel_z": imu_values.accel_z,
            "gyro_x": imu_values.gyro_x,
            "gyro_y": imu_values.gyro_y,
            "gyro_z": imu_values.gyro_z,
            "mag_x": imu_values.mag_x,
            "mag_y": imu_values.mag_y,
            "mag_z": imu_values.mag_z,
        }

    except Exception as e:
        logger.error(f"Error getting IMU values: {e}")
        return {"success": False, "message": f"Error getting IMU values: {str(e)}"}


def compute_euler_angles(
    accel_x: float,
    accel_y: float,
    accel_z: float,
    mag_x: Optional[float],
    mag_y: Optional[float],
    mag_z: Optional[float],
) -> Tuple[float, float, float]:
    """Compute Euler angles (roll, pitch, yaw) from IMU sensor values."""
    # Compute roll and pitch from accelerometer
    roll = np.arctan2(accel_y, accel_z)
    pitch = np.arctan2(-accel_x, np.sqrt(accel_y**2 + accel_z**2))

    # Use magnetometer for yaw if available
    if mag_x is not None and mag_y is not None and mag_z is not None:
        # Tilt compensation for magnetometer
        mag_x_comp = mag_x * np.cos(pitch) + mag_z * np.sin(pitch)
        mag_y_comp = (
            mag_x * np.sin(roll) * np.sin(pitch) 
            + mag_y * np.cos(roll) 
            - mag_z * np.sin(roll) * np.cos(pitch)
        )
        yaw = np.arctan2(-mag_y_comp, mag_x_comp)
    else:
        yaw = 0.0  # Default if no magnetometer

    return roll, pitch, yaw


def euler_to_rotation_matrix(roll: float, pitch: float, yaw: float) -> np.ndarray:
    """Convert Euler angles to a rotation matrix."""
    r_x = np.array([
        [1, 0, 0], 
        [0, np.cos(roll), -np.sin(roll)], 
        [0, np.sin(roll), np.cos(roll)]
    ])
    r_y = np.array([
        [np.cos(pitch), 0, np.sin(pitch)], 
        [0, 1, 0], 
        [-np.sin(pitch), 0, np.cos(pitch)]
    ])
    r_z = np.array([
        [np.cos(yaw), -np.sin(yaw), 0], 
        [np.sin(yaw), np.cos(yaw), 0], 
        [0, 0, 1]
    ])
    return r_z.dot(r_y).dot(r_x)


def reset_3d_axis(
    ax: Axes3D,
    xlim: Tuple[float, float],
    ylim: Tuple[float, float],
    zlim: Tuple[float, float],
    xlabel: str,
    ylabel: str,
    zlabel: str,
    title: str,
) -> None:
    """Reset a 3D axis with the given limits, labels, and title."""
    ax.cla()
    ax.set_xlim(xlim)
    ax.set_ylim(ylim)
    ax.set_zlim(zlim)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_zlabel(zlabel)
    ax.set_title(title)


async def visualize_orientation(
    robot_ip: str = DEFAULT_ROBOT_IP, 
    duration_seconds: int = 10
) -> Dict[str, Any]:
    """Display a real-time 3D visualization of the robot's orientation."""
    kos = await connect_to_robot(robot_ip)
    if not kos:
        return {"success": False, "message": "Failed to connect to robot"}

    try:
        plt.ion()  # enable interactive mode
        fig = plt.figure(figsize=(12, 6))
        ax_orient = fig.add_subplot(121, projection="3d")
        ax_accel = fig.add_subplot(122, projection="3d")
        fig.suptitle("Real-time IMU Visualization", fontsize=16)

        # Set axis properties
        reset_3d_axis(
            ax_orient, (-1.5, 1.5), (-1.5, 1.5), (-1.5, 1.5), "X", "Y", "Z", "Orientation"
        )
        reset_3d_axis(
            ax_accel, (-10, 10), (-10, 10), (-10, 10), "X", "Y", "Z", "Acceleration Vector"
        )

        start_time = time.time()
        last_update_time = start_time
        # Initialize orientation as zero
        orientation_euler = np.array([0.0, 0.0, 0.0])
        last_second = int(start_time)
        second_count = 0

        logger.info(f"Starting orientation visualization for {duration_seconds} seconds...")
        logger.info("Press Ctrl+C to stop early")

        while time.time() < start_time + duration_seconds:
            imu_values = await kos.imu.get_imu_values()
            second_count += 1

            current_time = time.time()
            dt = current_time - last_update_time
            last_update_time = current_time

            # Update orientation by integrating gyro values
            orientation_euler[0] += np.deg2rad(imu_values.gyro_x) * dt
            orientation_euler[1] += np.deg2rad(imu_values.gyro_y) * dt
            orientation_euler[2] += np.deg2rad(imu_values.gyro_z) * dt

            # Periodically log the sampling rate
            current_second = int(time.time())
            if current_second != last_second:
                logger.info(
                    f"Time: {current_second - start_time:.2f} seconds - "
                    f"Samples this second: {second_count}"
                )
                second_count = 0
                last_second = current_second

            # Compute rotation matrix
            r = euler_to_rotation_matrix(
                orientation_euler[0], orientation_euler[1], orientation_euler[2]
            )

            # Compute rotated coordinate axes
            x_axis = r.dot(np.array([1, 0, 0]))
            y_axis = r.dot(np.array([0, 1, 0]))
            z_axis = r.dot(np.array([0, 0, 1]))

            # Reset axes
            reset_3d_axis(
                ax_orient, (-1.5, 1.5), (-1.5, 1.5), (-1.5, 1.5), "X", "Y", "Z", "Orientation"
            )
            reset_3d_axis(
                ax_accel, (-10, 10), (-10, 10), (-10, 10), "X", "Y", "Z", "Acceleration Vector"
            )

            # Plot coordinate frame
            ax_orient.quiver(0, 0, 0, x_axis[0], x_axis[1], x_axis[2], color="r", label="X")
            ax_orient.quiver(0, 0, 0, y_axis[0], y_axis[1], y_axis[2], color="g", label="Y")
            ax_orient.quiver(0, 0, 0, z_axis[0], z_axis[1], z_axis[2], color="b", label="Z")

            # Plot acceleration vector
            accel_vec = np.array([imu_values.accel_x, imu_values.accel_y, imu_values.accel_z])
            ax_accel.quiver(
                0, 0, 0, accel_vec[0], accel_vec[1], accel_vec[2], color="m", label="Accel"
            )

            plt.draw()
            plt.pause(0.01)

        plt.ioff()
        plt.close()

        return {"success": True, "message": "Orientation visualization completed successfully"}

    except KeyboardInterrupt:
        plt.ioff()
        plt.close()
        logger.info("Visualization interrupted by user")
        return {"success": True, "message": "Orientation visualization interrupted by user"}

    except Exception as e:
        plt.ioff()
        plt.close()
        logger.error(f"Error visualizing orientation: {e}")
        return {"success": False, "message": f"Error visualizing orientation: {str(e)}"}


# Synchronous wrapper functions
def test_imu_sync(robot_ip: str = DEFAULT_ROBOT_IP, duration_seconds: int = 5) -> Dict[str, Any]:
    """Synchronous wrapper for test_imu."""
    return asyncio.run(test_imu(robot_ip, duration_seconds))


def plot_imu_data_sync(robot_ip: str = DEFAULT_ROBOT_IP, duration_seconds: int = 5) -> Dict[str, Any]:
    """Synchronous wrapper for plot_imu_data."""
    return asyncio.run(plot_imu_data(robot_ip, duration_seconds))


def get_imu_values_sync(robot_ip: str = DEFAULT_ROBOT_IP) -> Dict[str, Any]:
    """Synchronous wrapper for get_imu_values."""
    return asyncio.run(get_imu_values(robot_ip))


def visualize_orientation_sync(
    robot_ip: str = DEFAULT_ROBOT_IP, 
    duration_seconds: int = 10
) -> Dict[str, Any]:
    """Synchronous wrapper for visualize_orientation."""
    return asyncio.run(visualize_orientation(robot_ip, duration_seconds))


def help():
    """Print help information about the IMU testing module."""
    print(
        """
IMU Testing Module for KOS Robots
================================

Available Functions:
------------------
test_imu_sync(robot_ip="10.33.10.65", duration_seconds=5)
    Run a performance test on the IMU and return detailed statistics.

plot_imu_data_sync(robot_ip="10.33.10.65", duration_seconds=5)
    Collect IMU data and generate plots showing acceleration, gyroscope, and magnetometer readings.

visualize_orientation_sync(robot_ip="10.33.10.65", duration_seconds=10)
    Display a real-time 3D visualization of the robot's orientation.

get_imu_values_sync(robot_ip="10.33.10.65")
    Get a single reading from the IMU sensors.

Technical Details:
----------------
- Measures IMU sampling rate and stability
- Visualizes 3D orientation using Euler angles
- Plots acceleration, gyroscope, and magnetometer data
- Provides statistical analysis of sensor performance

Example Usage:
------------
# Import the module
from kos_sdk.tests import imu

# Run a basic IMU test
result = imu.test_imu_sync()
print(f"IMU sampling rate: {result['avg_rate']} Hz")

# Generate plots of IMU data
imu.plot_imu_data_sync()

# Visualize orientation in real-time
imu.visualize_orientation_sync(duration_seconds=30)
"""
    )


# Define what gets imported with "from kos_sdk.tests.imu import *"
__all__ = [
    "test_imu_sync", 
    "plot_imu_data_sync", 
    "get_imu_values_sync", 
    "visualize_orientation_sync", 
    "help"
]


if __name__ == "__main__":
    try:
        result = asyncio.run(test_imu())
        if result["success"]:
            print(f"IMU test completed successfully!")
            print(f"Average sampling rate: {result['avg_rate']:.2f} Hz")
            print(f"Total samples: {result['total_samples']}")
            print(f"Duration: {result['duration']:.2f} seconds")
        else:
            print(f"IMU test failed: {result['message']}")
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    except Exception as e:
        logger.error(f"Unhandled exception: {e}")
