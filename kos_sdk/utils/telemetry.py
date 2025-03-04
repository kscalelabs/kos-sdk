"""Telemetry logging and visualization utilities for KOS robots."""

import asyncio
import csv
import datetime
import logging
import os
from dataclasses import dataclass
import time
from typing import List, Optional
from pathlib import Path

import pykos
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec

logger = logging.getLogger(__name__)

@dataclass
class Actuator:
    actuator_id: int
    nn_id: int
    kp: float
    kd: float
    max_torque: float
    joint_name: str

class TelemetryLogger:
    """Telemetry logging for KOS robots (real or simulated)."""
    
    def __init__(self, kos: pykos.KOS, actuator_ids: List[int], log_dir: str = "telemetry_logs"):
        """Initialize telemetry logger.
        
        Args:
            kos: Connected KOS instance (real or sim)
            actuator_ids: List of actuator IDs to monitor
            log_dir: Directory to store telemetry logs
        """
        self.kos = kos
        self.log_dir = Path(log_dir)
        self.actuator_ids = actuator_ids  # Now required parameter
        
        # Create log directory
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Will be initialized in start()
        self.imu_writer = None
        self.actuator_writer = None
        self.control_writer = None
        self.imu_file = None
        self.actuator_file = None
        self.control_file = None
        self.start_time = None
        self._is_logging = False
        
        # Performance tracking
        self.last_loop_time = time.time()
        self.loop_times: List[float] = []

    async def start(self):
        """Start telemetry logging."""
        if self._is_logging:
            return
            
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Open log files and initialize CSV writers
        self.imu_file = open(self.log_dir / f"imu_{timestamp}.csv", "w", newline="")
        self.actuator_file = open(self.log_dir / f"actuator_{timestamp}.csv", "w", newline="")
        self.control_file = open(self.log_dir / f"control_{timestamp}.csv", "w", newline="")
        
        # Initialize CSV writers with headers
        self.imu_writer = csv.writer(self.imu_file)
        self.imu_writer.writerow([
            "timestamp",
            "roll", "pitch", "yaw",              # Orientation (Euler angles)
            "accel_x", "accel_y", "accel_z",     # Linear acceleration
            "gyro_x", "gyro_y", "gyro_z",        # Angular velocity
            "quat_w", "quat_x", "quat_y", "quat_z"  # Quaternion
        ])
        
        self.actuator_writer = csv.writer(self.actuator_file)
        self.actuator_writer.writerow([
            "timestamp", "actuator_id", 
            "position", "velocity_rad_s", "torque",
            "current", "temperature", "voltage",
            "online", "faults"
        ])

        self.control_writer = csv.writer(self.control_file)
        self.control_writer.writerow([
            "timestamp",
            "loop_frequency",      # Measured control loop frequency
            "command_latency",     # Time between command and response
            "grpc_latency"         # gRPC round-trip time
        ])
        
        self.start_time = time.time()
        self._is_logging = True
        
        # Start background logging task
        asyncio.create_task(self._log_loop())

    async def stop(self):
        """Stop telemetry logging and close files."""
        self._is_logging = False
        if self.imu_file:
            self.imu_file.close()
        if self.actuator_file:
            self.actuator_file.close()
        if self.control_file:
            self.control_file.close()

    async def _log_loop(self):
        """Background task for continuous logging."""
        while self._is_logging:
            try:
                await self._log_single_frame()
            except Exception as e:
                logger.error(f"Error in telemetry logging: {e}")
            await asyncio.sleep(0.01)  # 100Hz target rate

    async def _log_single_frame(self):
        """Log a single frame of telemetry data."""
        loop_start_time = time.time()
        timestamp = datetime.datetime.now().isoformat()
        
        # Log IMU data
        try:
            cmd_start = time.time()
            imu_euler = await self.kos.imu.get_euler_angles()
            imu_values = await self.kos.imu.get_imu_values()
            quat = await self.kos.imu.get_quaternion()
            cmd_latency = time.time() - cmd_start
            
            self.imu_writer.writerow([
                timestamp,
                imu_euler.roll, imu_euler.pitch, imu_euler.yaw,
                imu_values.accel_x, imu_values.accel_y, imu_values.accel_z,
                imu_values.gyro_x, imu_values.gyro_y, imu_values.gyro_z,
                quat.w, quat.x, quat.y, quat.z
            ])
        except Exception as e:
            logger.warning(f"Failed to get IMU data: {e}")
            
        # Log actuator data
        try:
            cmd_start = time.time()
            states = await self.kos.actuator.get_actuators_state(self.actuator_ids)
            cmd_latency = time.time() - cmd_start
            
            for actuator_id, state in zip(self.actuator_ids, states.states):
                self.actuator_writer.writerow([
                    timestamp,
                    actuator_id,
                    state.position,
                    state.velocity,
                    state.torque,
                    state.current,
                    state.temperature,
                    state.voltage,
                    state.online,
                    ','.join(state.faults) if state.faults else ''
                ])
        except Exception as e:
            logger.warning(f"Failed to get actuator data: {e}")

        # Calculate and log control metrics
        current_time = time.time()
        loop_duration = current_time - self.last_loop_time
        self.last_loop_time = current_time
        self.loop_times.append(loop_duration)
        
        if len(self.loop_times) > 100:  # Keep a rolling window
            self.loop_times.pop(0)
        
        avg_frequency = 1.0 / (sum(self.loop_times) / len(self.loop_times))
        
        self.control_writer.writerow([
            timestamp,
            avg_frequency,
            cmd_latency,
            cmd_latency  # Using command latency as proxy for gRPC latency
        ])

def plot_latest_logs(log_dir: str = "telemetry_logs"):
    """Plot the most recent telemetry logs."""
    # Find latest log files
    imu_files = sorted(Path(log_dir).glob("imu_*.csv"))
    actuator_files = sorted(Path(log_dir).glob("actuator_*.csv"))
    control_files = sorted(Path(log_dir).glob("control_*.csv"))
    
    if not (imu_files and actuator_files and control_files):
        raise FileNotFoundError("No log files found in directory")
        
    # Load most recent files
    imu_data = pd.read_csv(imu_files[-1])
    actuator_data = pd.read_csv(actuator_files[-1])
    control_data = pd.read_csv(control_files[-1])
    
    # Convert timestamps to relative seconds for plotting
    for df in [imu_data, actuator_data, control_data]:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['time'] = (df['timestamp'] - df['timestamp'].min()).dt.total_seconds()
    
    # Create plots using code from plot.py
    plt.style.use('ggplot')
    fig = plt.figure(figsize=(15, 24))
    gs = GridSpec(8, 2, figure=fig)
    
    # IMU Data Plots (Left Column)
    plot_imu_data(fig, gs, imu_data)
    
    # Control Metrics (Bottom Left)
    plot_control_metrics(fig, gs, control_data)
    
    # Actuator Data (Right Column)
    plot_actuator_data(fig, gs, actuator_data)
    
    plt.tight_layout()
    
    # Save plot
    timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    plot_filename = f"telemetry_plot_{timestamp}.png"
    plt.savefig(plot_filename, dpi=300, bbox_inches='tight')
    logger.info(f"Plot saved as {plot_filename}")
    
    plt.show()

def plot_imu_data(fig, gs, imu_data):
    """Plot IMU data in the left column."""
    # Euler Angles
    ax_euler = fig.add_subplot(gs[0, 0])
    ax_euler.plot(imu_data['time'], imu_data['roll'], label='Roll')
    ax_euler.plot(imu_data['time'], imu_data['pitch'], label='Pitch')
    ax_euler.plot(imu_data['time'], imu_data['yaw'], label='Yaw')
    ax_euler.set_title('IMU Orientation (Euler Angles)')
    ax_euler.set_xlabel('Time (s)')
    ax_euler.set_ylabel('Angle (°)')
    ax_euler.grid(True)
    ax_euler.legend()

    # Acceleration
    ax_accel = fig.add_subplot(gs[1, 0])
    ax_accel.plot(imu_data['time'], imu_data['accel_x'], label='X')
    ax_accel.plot(imu_data['time'], imu_data['accel_y'], label='Y')
    ax_accel.plot(imu_data['time'], imu_data['accel_z'], label='Z')
    ax_accel.set_title('Linear Acceleration')
    ax_accel.set_xlabel('Time (s)')
    ax_accel.set_ylabel('Acceleration (m/s²)')
    ax_accel.grid(True)
    ax_accel.legend()

    # Angular Velocity
    ax_gyro = fig.add_subplot(gs[2, 0])
    ax_gyro.plot(imu_data['time'], imu_data['gyro_x'], label='X')
    ax_gyro.plot(imu_data['time'], imu_data['gyro_y'], label='Y')
    ax_gyro.plot(imu_data['time'], imu_data['gyro_z'], label='Z')
    ax_gyro.set_title('Angular Velocity')
    ax_gyro.set_xlabel('Time (s)')
    ax_gyro.set_ylabel('Angular Velocity (rad/s)')
    ax_gyro.grid(True)
    ax_gyro.legend()

def plot_control_metrics(fig, gs, control_data):
    """Plot control metrics."""
    ax_control = fig.add_subplot(gs[4, 0])
    ax_control.plot(control_data['time'], control_data['loop_frequency'], 
                   label='Loop Frequency')
    ax_control2 = ax_control.twinx()
    ax_control2.plot(control_data['time'], control_data['command_latency'] * 1000, 
                    'r-', label='Command Latency')
    ax_control.set_title('Control Performance Metrics')
    ax_control.set_xlabel('Time (s)')
    ax_control.set_ylabel('Frequency (Hz)')
    ax_control2.set_ylabel('Latency (ms)')
    ax_control.grid(True)
    ax_control.legend(loc='upper left')
    ax_control2.legend(loc='upper right')

def plot_actuator_data(fig, gs, actuator_data):
    """Plot actuator data in the right column."""
    axes = {
        'position': fig.add_subplot(gs[0, 1]),
        'velocity_rad_s': fig.add_subplot(gs[1, 1]),
        'torque': fig.add_subplot(gs[2, 1]),
        'current': fig.add_subplot(gs[3, 1]),
        'temperature': fig.add_subplot(gs[4, 1]),
        'voltage': fig.add_subplot(gs[5, 1])
    }
    
    titles = {
        'position': ('Actuator Positions', 'Position (rad)'),
        'velocity_rad_s': ('Actuator Velocities', 'Velocity (rad/s)'),
        'torque': ('Actuator Torques', 'Torque (Nm)'),
        'current': ('Actuator Currents', 'Current (A)'),
        'temperature': ('Actuator Temperatures', 'Temperature (°C)'),
        'voltage': ('Actuator Voltages', 'Voltage (V)')
    }
    
    for actuator_id in actuator_data['actuator_id'].unique():
        mask = actuator_data['actuator_id'] == actuator_id
        data = actuator_data[mask]
        
        for param, ax in axes.items():
            ax.plot(data['time'], data[param], label=f'ID {actuator_id}')
    
    for param, (title, ylabel) in titles.items():
        ax = axes[param]
        ax.set_title(title)
        ax.set_xlabel('Time (s)')
        ax.set_ylabel(ylabel)
        ax.grid(True)
        ax.legend()

# Convenience function
async def log_telemetry(kos: pykos.KOS, actuator_ids: List[int], duration: float):
    """Log telemetry for a specified duration.
    
    Args:
        kos: Connected KOS instance
        actuator_ids: List of actuator IDs to monitor
        duration: Duration in seconds to log data
    """
    logger = TelemetryLogger(kos, actuator_ids)
    await logger.start()
    await asyncio.sleep(duration)
    await logger.stop()
    plot_latest_logs()