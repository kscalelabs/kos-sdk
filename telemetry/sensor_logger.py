"""Simple data logger for IMU and actuator data from Z-Bot.

This script logs IMU and actuator data to CSV files for later analysis.
"""

import asyncio
import csv
import datetime
import logging
import os
from typing import List, Optional

import pykos

logger = logging.getLogger(__name__)

class SensorLogger:
    def __init__(self, ip_address: str, actuator_ids: List[int], log_dir: str = "telemetry_logs"):
        """Initialize the sensor logger.
        
        Args:
            ip_address: IP address of the Z-Bot
            actuator_ids: List of actuator IDs to monitor
            log_dir: Directory to store log files
        """
        self.ip_address = ip_address
        self.actuator_ids = actuator_ids
        self.log_dir = log_dir
        self.kos: Optional[pykos.KOS] = None
        
        # Create log directory if it doesn't exist
        os.makedirs(log_dir, exist_ok=True)
        
        # Generate timestamp for filenames
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create CSV files and writers
        self.imu_file = open(f"{log_dir}/imu_{timestamp}.csv", "w", newline="")
        self.actuator_file = open(f"{log_dir}/actuator_{timestamp}.csv", "w", newline="")
        
        # Setup CSV writers with headers
        self.imu_writer = csv.writer(self.imu_file)
        self.imu_writer.writerow([
            "timestamp", "accel_x", "accel_y", "accel_z",
            "gyro_x", "gyro_y", "gyro_z",
            "mag_x", "mag_y", "mag_z"
        ])
        
        self.actuator_writer = csv.writer(self.actuator_file)
        self.actuator_writer.writerow([
            "timestamp", "actuator_id", "position", "velocity", "torque",
            "current", "temperature", "voltage"
        ])

    async def connect(self):
        """Connect to the Z-Bot."""
        self.kos = pykos.KOS(self.ip_address)
        await self.kos.connect()

    async def log_data(self, duration_seconds: float = 10.0):
        """Log IMU and actuator data for the specified duration.
        
        Args:
            duration_seconds: How long to log data for
        """
        if not self.kos:
            raise RuntimeError("Not connected to Z-Bot. Call connect() first.")

        start_time = datetime.datetime.now()
        end_time = start_time + datetime.timedelta(seconds=duration_seconds)

        logger.info("Starting data logging for %.1f seconds", duration_seconds)
        
        while datetime.datetime.now() < end_time:
            timestamp = datetime.datetime.now().isoformat()
            
            # Log IMU data
            imu_data = await self.kos.imu.get_imu_values()
            self.imu_writer.writerow([
                timestamp,
                imu_data.accel_x, imu_data.accel_y, imu_data.accel_z,
                imu_data.gyro_x, imu_data.gyro_y, imu_data.gyro_z,
                imu_data.mag_x, imu_data.mag_y, imu_data.mag_z
            ])
            
            # Log actuator data - get states for all actuators at once
            states = await self.kos.actuator.get_actuators_state([actuator_id for actuator_id in self.actuator_ids])
            
            # Write each actuator's state
            for actuator_id, state in zip(self.actuator_ids, states.states):
                self.actuator_writer.writerow([
                    timestamp,
                    actuator_id,
                    state.position,
                    state.velocity,
                    state.torque,
                    state.current,
                    state.temperature,
                    state.voltage
                ])

            # Add a small delay to prevent overwhelming the system
            await asyncio.sleep(0.01)

    async def close(self):
        """Close the connection and log files."""
        # KOS doesn't need explicit disconnection
        self.imu_file.close()
        self.actuator_file.close()

async def main():
    """Example usage of the SensorLogger."""
    # Initialize logger with actuator IDs 11, 12, and 13
    sensor_logger = SensorLogger("10.33.11.170", [11, 12, 13])
    
    try:
        await sensor_logger.connect()
        await sensor_logger.log_data(duration_seconds=10.0)
    except Exception as e:
        logger.exception("Error during logging: %s", str(e))
    finally:
        await sensor_logger.close()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main()) 