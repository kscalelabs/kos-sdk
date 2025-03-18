import time
from dataclasses import dataclass
from typing import Any, Dict, List

import numpy as np
from loguru import logger
from kos_sdk.utils.robot import RobotInterface


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


async def collect_data(robot_ip: str = "", duration_seconds: int = 5) -> Dict[str, Any]:
    """Collect IMU data for the specified duration."""
    try:
        async with RobotInterface(robot_ip) as robot:
            logger.info(f"Starting IMU test for {duration_seconds} seconds...")
            
            # Initialize data storage
            count = 0
            start_time = time.time()
            end_time = start_time + duration_seconds
            
            timestamps = []
            samples_per_second = []
            accel_x, accel_y, accel_z = [], [], []
            gyro_x, gyro_y, gyro_z = [], [], []
            mag_x, mag_y, mag_z = [], [], []
            
            last_second = int(start_time)
            second_count = 0
            
            # Collect data
            while time.time() < end_time:
                imu_values = await robot.kos.imu.get_imu_values()
                count += 1
                second_count += 1
                
                # Store values
                accel_x.append(imu_values.accel_x)
                accel_y.append(imu_values.accel_y)
                accel_z.append(imu_values.accel_z)
                gyro_x.append(imu_values.gyro_x)
                gyro_y.append(imu_values.gyro_y)
                gyro_z.append(imu_values.gyro_z)
                mag_x_val = imu_values.mag_x if imu_values.mag_x is not None else 0.0
                mag_y_val = imu_values.mag_y if imu_values.mag_y is not None else 0.0
                mag_z_val = imu_values.mag_z if imu_values.mag_z is not None else 0.0
                mag_x.append(mag_x_val)
                mag_y.append(mag_y_val)
                mag_z.append(mag_z_val)
                
                # Track samples per second
                current_second = int(time.time())
                if current_second != last_second:
                    timestamps.append(current_second - start_time)
                    samples_per_second.append(second_count)
                    time_str = f"Time: {current_second - start_time:.2f}s"
                    logger.info(f"{time_str} - Samples: {second_count}")
                    second_count = 0
                    last_second = current_second
            
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
                timestamps=timestamps,
                samples_per_second=samples_per_second,
                accel_x=accel_x, accel_y=accel_y, accel_z=accel_z,
                gyro_x=gyro_x, gyro_y=gyro_y, gyro_z=gyro_z,
                mag_x=mag_x, mag_y=mag_y, mag_z=mag_z,
            )
            
            # Calculate statistics
            accel_stats = {
                "x_mean": np.mean(accel_x), "y_mean": np.mean(accel_y), "z_mean": np.mean(accel_z),
                "x_std": np.std(accel_x), "y_std": np.std(accel_y), "z_std": np.std(accel_z),
            }
            
            gyro_stats = {
                "x_mean": np.mean(gyro_x), "y_mean": np.mean(gyro_y), "z_mean": np.mean(gyro_z),
                "x_std": np.std(gyro_x), "y_std": np.std(gyro_y), "z_std": np.std(gyro_z),
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