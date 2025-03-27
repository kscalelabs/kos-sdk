"""Plot logged IMU and actuator data from CSV files.

This script reads and plots the sensor data logged by sensor_logger.py.
"""

import argparse
import glob
import os
from typing import Tuple

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.gridspec import GridSpec
import numpy as np

def load_latest_logs(log_dir: str = "telemetry_logs") -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Load the most recent IMU and actuator log files.
    
    Args:
        log_dir: Directory containing the log files
        
    Returns:
        Tuple of (imu_data, actuator_data) as pandas DataFrames
    """
    # Find latest log files
    imu_files = glob.glob(os.path.join(log_dir, "imu_*.csv"))
    actuator_files = glob.glob(os.path.join(log_dir, "actuator_*.csv"))
    
    if not imu_files or not actuator_files:
        raise FileNotFoundError("No log files found in directory")
        
    # Get most recent files
    latest_imu = max(imu_files, key=os.path.getctime)
    latest_actuator = max(actuator_files, key=os.path.getctime)
    
    # Load data
    imu_data = pd.read_csv(latest_imu)
    actuator_data = pd.read_csv(latest_actuator)
    
    # Convert timestamps to datetime
    imu_data['timestamp'] = pd.to_datetime(imu_data['timestamp'])
    actuator_data['timestamp'] = pd.to_datetime(actuator_data['timestamp'])
    
    return imu_data, actuator_data

def calculate_heading(mag_x: float, mag_y: float) -> float:
    """Calculate heading angle from magnetometer X and Y values.
    
    Returns angle in degrees from North (0-360)
    """
    heading = np.arctan2(mag_y, mag_x) * 180.0 / np.pi
    # Convert to 0-360 range
    if heading < 0:
        heading += 360.0
    return heading

def plot_sensor_data(imu_data: pd.DataFrame, actuator_data: pd.DataFrame) -> None:
    """Create plots of the sensor data."""
    # Create figure with GridSpec for flexible subplot layout
    fig = plt.figure(figsize=(15, 20))  # Made figure taller
    gs = GridSpec(5, 2, figure=fig)  # 5 rows, 2 columns
    
    # Convert timestamps to seconds from start
    t0 = min(imu_data['timestamp'].min(), actuator_data['timestamp'].min())
    imu_times = (imu_data['timestamp'] - t0).dt.total_seconds()
    actuator_times = (actuator_data['timestamp'] - t0).dt.total_seconds()
    
    # Left column: IMU Data
    # Accelerometer
    ax_accel = fig.add_subplot(gs[0, 0])
    ax_accel.plot(imu_times, imu_data['accel_x'], label='X')
    ax_accel.plot(imu_times, imu_data['accel_y'], label='Y')
    ax_accel.plot(imu_times, imu_data['accel_z'], label='Z')
    ax_accel.set_title('Accelerometer Data')
    ax_accel.set_xlabel('Time (s)')
    ax_accel.set_ylabel('Acceleration (m/s²)')
    ax_accel.grid(True)
    ax_accel.legend()
    
    # Gyroscope
    ax_gyro = fig.add_subplot(gs[1, 0])
    ax_gyro.plot(imu_times, imu_data['gyro_x'], label='X')
    ax_gyro.plot(imu_times, imu_data['gyro_y'], label='Y')
    ax_gyro.plot(imu_times, imu_data['gyro_z'], label='Z')
    ax_gyro.set_title('Gyroscope Data')
    ax_gyro.set_xlabel('Time (s)')
    ax_gyro.set_ylabel('Angular Velocity (deg/s)')
    ax_gyro.grid(True)
    ax_gyro.legend()
    
    # Magnetometer
    ax_mag = fig.add_subplot(gs[2, 0])
    ax_mag.plot(imu_times, imu_data['mag_x'], label='X')
    ax_mag.plot(imu_times, imu_data['mag_y'], label='Y')
    ax_mag.plot(imu_times, imu_data['mag_z'], label='Z')
    ax_mag.set_title('Magnetometer Data')
    ax_mag.set_xlabel('Time (s)')
    ax_mag.set_ylabel('Magnetic Field')
    ax_mag.grid(True)
    ax_mag.legend()
    
    # Heading
    ax_heading = fig.add_subplot(gs[3, 0])
    headings = [calculate_heading(x, y) for x, y in zip(imu_data['mag_x'], imu_data['mag_y'])]
    ax_heading.plot(imu_times, headings, label='Heading')
    ax_heading.set_title('Magnetic Heading')
    ax_heading.set_xlabel('Time (s)')
    ax_heading.set_ylabel('Degrees from North')
    ax_heading.grid(True)
    ax_heading.legend()
    
    # Right column: Actuator Data
    # Position and Velocity
    ax_pos = fig.add_subplot(gs[0, 1])
    ax_vel = fig.add_subplot(gs[1, 1])
    ax_torque = fig.add_subplot(gs[2, 1])
    ax_current = fig.add_subplot(gs[3, 1])
    
    # Temperature and Voltage share the last row
    ax_temp = fig.add_subplot(gs[4, 0])
    ax_voltage = fig.add_subplot(gs[4, 1])
    
    # Plot data for each actuator
    for actuator_id in actuator_data['actuator_id'].unique():
        actuator_mask = actuator_data['actuator_id'] == actuator_id
        actuator_times_masked = actuator_times[actuator_mask]
        
        # Position
        ax_pos.plot(actuator_times_masked, 
                   actuator_data.loc[actuator_mask, 'position'], 
                   label=f'ID {actuator_id}')
        
        # Velocity
        ax_vel.plot(actuator_times_masked, 
                   actuator_data.loc[actuator_mask, 'velocity'], 
                   label=f'ID {actuator_id}')
        
        # Torque
        ax_torque.plot(actuator_times_masked, 
                      actuator_data.loc[actuator_mask, 'torque'], 
                      label=f'ID {actuator_id}')
        
        # Current
        ax_current.plot(actuator_times_masked, 
                       actuator_data.loc[actuator_mask, 'current'], 
                       label=f'ID {actuator_id}')
        
        # Temperature
        ax_temp.plot(actuator_times_masked, 
                    actuator_data.loc[actuator_mask, 'temperature'], 
                    label=f'ID {actuator_id}')
        
        # Voltage
        ax_voltage.plot(actuator_times_masked, 
                       actuator_data.loc[actuator_mask, 'voltage'], 
                       label=f'ID {actuator_id}')
    
    # Set titles and labels for actuator plots
    ax_pos.set_title('Actuator Positions')
    ax_pos.set_xlabel('Time (s)')
    ax_pos.set_ylabel('Position')
    ax_pos.grid(True)
    ax_pos.legend()
    
    ax_vel.set_title('Actuator Velocities')
    ax_vel.set_xlabel('Time (s)')
    ax_vel.set_ylabel('Velocity')
    ax_vel.grid(True)
    ax_vel.legend()
    
    ax_torque.set_title('Actuator Torques')
    ax_torque.set_xlabel('Time (s)')
    ax_torque.set_ylabel('Torque')
    ax_torque.grid(True)
    ax_torque.legend()
    
    ax_current.set_title('Actuator Currents')
    ax_current.set_xlabel('Time (s)')
    ax_current.set_ylabel('Current (A)')
    ax_current.grid(True)
    ax_current.legend()
    
    ax_temp.set_title('Actuator Temperatures')
    ax_temp.set_xlabel('Time (s)')
    ax_temp.set_ylabel('Temperature (°C)')
    ax_temp.grid(True)
    ax_temp.legend()
    
    ax_voltage.set_title('Actuator Voltages')
    ax_voltage.set_xlabel('Time (s)')
    ax_voltage.set_ylabel('Voltage (V)')
    ax_voltage.grid(True)
    ax_voltage.legend()
    
    plt.tight_layout()
    plt.show()

def main():
    """Main entry point for the plotting script."""
    parser = argparse.ArgumentParser(description='Plot sensor log data')
    parser.add_argument('--log-dir', default='telemetry_logs',
                      help='Directory containing the log files')
    args = parser.parse_args()
    
    try:
        imu_data, actuator_data = load_latest_logs(args.log_dir)
        plot_sensor_data(imu_data, actuator_data)
    except Exception as e:
        print(f"Error plotting data: {str(e)}")
        raise

if __name__ == "__main__":
    main() 