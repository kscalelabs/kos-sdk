"""
Motion module for robot control with a focus on simplicity and monitoring.

This module provides the core functionality for joint control, grouping,
monitoring, and configuration. It allows for easy control of robot joints
with human-readable names, joint grouping, and state tracking.
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple, Union, Any
import numpy as np
import matplotlib.pyplot as plt

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Types
JointName = str
ActuatorId = int
Position = float
Velocity = float
Torque = float
Gains = Tuple[float, float]  # (kp, kd)


class JointState:
    """Represents the state of a joint."""
    
    def __init__(self, position: Position = 0.0, velocity: Velocity = 0.0, torque: Torque = 0.0):
        self.position = position
        self.velocity = velocity
        self.torque = torque

    def __repr__(self) -> str:
        return f"JointState(pos={self.position:.2f}, vel={self.velocity:.2f}, torque={self.torque:.2f})"


class Joint:
    """Represents a single robot joint."""
    
    def __init__(self, name: JointName, actuator_id: ActuatorId):
        self.name = name
        self.actuator_id = actuator_id
        self.state = JointState()
        
    def __repr__(self) -> str:
        return f"Joint(name={self.name}, id={self.actuator_id}, {self.state})"


class JointGroup:
    """A collection of joints that can be controlled together."""
    
    def __init__(self, name: str, joints: List[Joint]):
        self.name = name
        self.joints = joints
        
    def __len__(self) -> int:
        return len(self.joints)
    
    def __repr__(self) -> str:
        return f"JointGroup(name={self.name}, joints={[j.name for j in self.joints]})"

    def get_joint_names(self) -> List[JointName]:
        """Returns the names of all joints in the group."""
        return [joint.name for joint in self.joints]
    

class RobotConfig:
    """Configuration settings for joint control parameters."""
    
    def __init__(
        self, 
        sim_gains: Gains = (120, 30),  # Default simulator gains
        real_gains: Gains = (24, 12),  # Default real robot gains
        max_torque: float = 100.0,      # Maximum allowed torque
        default_velocity: float = 30.0,  # Default joint velocity
        monitoring_interval: float = 0.05,  # Default monitoring interval (s)
    ):
        self.sim_gains = sim_gains
        self.real_gains = real_gains
        self.max_torque = max_torque
        self.default_velocity = default_velocity
        self.monitoring_interval = monitoring_interval


class Robot:
    """Main interface for controlling joints and groups."""
    
    # Default joint map for common joint names to actuator IDs
    DEFAULT_JOINT_MAP = {
        # Left leg
        "left_hip_yaw": 1,
        "left_hip_roll": 2,
        "left_hip_pitch": 3,
        "left_knee": 4,
        "left_ankle_pitch": 5,
        "left_ankle_roll": 6,
        
        # Right leg
        "right_hip_yaw": 7,
        "right_hip_roll": 8,
        "right_hip_pitch": 9,
        "right_knee": 10,
        "right_ankle_pitch": 11,
        "right_ankle_roll": 12,
        
        # Left arm
        "left_shoulder_pitch": 13,
        "left_shoulder_roll": 14,
        "left_shoulder_yaw": 15,
        "left_elbow": 16,
        
        # Right arm
        "right_shoulder_pitch": 17,
        "right_shoulder_roll": 18,
        "right_shoulder_yaw": 19,
        "right_elbow": 20,
        
        # Neck
        "neck_yaw": 21,
        "neck_pitch": 22,
    }
    
    # Default joint groups
    DEFAULT_GROUPS = {
        "left_leg": ["left_hip_yaw", "left_hip_roll", "left_hip_pitch", "left_knee", "left_ankle_pitch", "left_ankle_roll"],
        "right_leg": ["right_hip_yaw", "right_hip_roll", "right_hip_pitch", "right_knee", "right_ankle_pitch", "right_ankle_roll"],
        "left_arm": ["left_shoulder_pitch", "left_shoulder_roll", "left_shoulder_yaw", "left_elbow"],
        "right_arm": ["right_shoulder_pitch", "right_shoulder_roll", "right_shoulder_yaw", "right_elbow"],
        "neck": ["neck_yaw", "neck_pitch"],
        "legs": ["left_hip_yaw", "left_hip_roll", "left_hip_pitch", "left_knee", "left_ankle_pitch", "left_ankle_roll",
                 "right_hip_yaw", "right_hip_roll", "right_hip_pitch", "right_knee", "right_ankle_pitch", "right_ankle_roll"],
        "arms": ["left_shoulder_pitch", "left_shoulder_roll", "left_shoulder_yaw", "left_elbow",
                 "right_shoulder_pitch", "right_shoulder_roll", "right_shoulder_yaw", "right_elbow"],
    }
    
    def __init__(
        self, 
        joint_map: Dict[JointName, ActuatorId] = None,
        groups: Dict[str, List[JointName]] = None,
        config: RobotConfig = None,
    ):
        # Use defaults if not provided
        self.joint_map = joint_map or self.DEFAULT_JOINT_MAP
        self.group_map = groups or self.DEFAULT_GROUPS
        self.config = config or RobotConfig()
        
        # Create joint objects
        self.joints: Dict[JointName, Joint] = {
            name: Joint(name, actuator_id)
            for name, actuator_id in self.joint_map.items()
        }
        
        # Create joint groups
        self.groups: Dict[str, JointGroup] = {}
        for group_name, joint_names in self.group_map.items():
            # Filter out joint names that don't exist in the joint map
            valid_joints = [self.joints[name] for name in joint_names if name in self.joints]
            if valid_joints:
                self.groups[group_name] = JointGroup(group_name, valid_joints)
        
        # Runtime attributes
        self.is_real = False
        self.is_configured = False
        self.is_monitoring = False
        self.monitor_task = None
        self.joint_history = {}
        self.start_time = None
        self.logging_enabled = False
        self.log_file = None
        
    async def configure(self, kos, is_real: bool = False, enable_monitoring: bool = False):
        """Configure the robot with KOS interface."""
        self.is_real = is_real
        
        # Apply the appropriate gains to all actuators
        gains = self.config.real_gains if is_real else self.config.sim_gains
        
        for joint in self.joints.values():
            await kos.actuator.configure_actuator(
                actuator_id=joint.actuator_id, 
                kp=gains[0], 
                kd=gains[1], 
                max_torque=self.config.max_torque,
                torque_enabled=True
            )
            
        self.is_configured = True
        
        # Start monitoring if requested
        if enable_monitoring:
            await self.start_monitoring(kos)
        
    async def start_monitoring(self, kos, interval: float = None):
        """Start monitoring joint states periodically."""
        if self.is_monitoring:
            return
        
        # Use the specified interval or the default
        interval = interval or self.config.monitoring_interval
        self.is_monitoring = True
        self.start_time = time.time()
        
        # Initialize history for all joints
        self.joint_history = {
            joint_name: {
                'time': [],
                'position': [],
                'velocity': [],
                'torque': [],
            }
            for joint_name in self.joints
        }
        
        # Create and start the monitoring task
        async def monitor_states():
            while self.is_monitoring:
                try:
                    states = await self.get_states(kos)
                    current_time = time.time() - self.start_time
                    
                    for joint_name, state in states.items():
                        self.joint_history[joint_name]['time'].append(current_time)
                        self.joint_history[joint_name]['position'].append(state.position)
                        self.joint_history[joint_name]['velocity'].append(state.velocity)
                        self.joint_history[joint_name]['torque'].append(state.torque)
                        
                    # Log to file if enabled
                    if self.logging_enabled and self.log_file:
                        log_entry = {
                            'time': current_time,
                            'joints': {
                                jname: {
                                    'position': jstate.position,
                                    'velocity': jstate.velocity,
                                    'torque': jstate.torque
                                }
                                for jname, jstate in states.items()
                            }
                        }
                        self.log_file.write(json.dumps(log_entry) + '\n')
                        self.log_file.flush()
                        
                    await asyncio.sleep(interval)
                except Exception as e:
                    logger.error(f"Monitoring error: {e}")
                    await asyncio.sleep(interval)
        
        self.monitor_task = asyncio.create_task(monitor_states())
        
    def enable_logging(self, log_dir: str = 'logs'):
        """Enable logging of joint states to a file."""
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = os.path.join(log_dir, f"robot_log_{timestamp}.jsonl")
        self.log_file = open(log_path, 'w')
        self.logging_enabled = True
        logger.info(f"Logging enabled to {log_path}")
        return log_path
        
    def disable_logging(self):
        """Disable logging of joint states."""
        if self.logging_enabled and self.log_file:
            self.log_file.close()
            self.log_file = None
            self.logging_enabled = False
            logger.info("Logging disabled")
        
    async def stop_monitoring(self):
        """Stop the monitoring task."""
        if not self.is_monitoring:
            return
            
        self.is_monitoring = False
        if self.monitor_task:
            try:
                self.monitor_task.cancel()
                await self.monitor_task
            except asyncio.CancelledError:
                pass
            self.monitor_task = None
        
        # Disable logging if it was enabled
        if self.logging_enabled:
            self.disable_logging()
            
    async def get_states(self, kos) -> Dict[JointName, JointState]:
        """Get the current state of all joints."""
        states = {}
        
        for name, joint in self.joints.items():
            # Get position, velocity and torque from KOS
            position = await kos.get_position(joint.actuator_id)
            velocity = await kos.get_velocity(joint.actuator_id)
            torque = await kos.get_torque(joint.actuator_id)
            
            # Update joint state
            joint.state = JointState(position, velocity, torque)
            states[name] = joint.state
            
        return states
            
    async def move(self, kos, positions: Dict[JointName, Position], velocity: float = None):
        """Move specified joints to given positions."""
        if not self.is_configured:
            raise RuntimeError("Robot not configured. Call configure() first.")
            
        # Use the specified velocity or the default
        velocity = velocity or self.config.default_velocity
        
        # Move each joint
        for joint_name, position in positions.items():
            if joint_name in self.joints:
                joint = self.joints[joint_name]
                await kos.set_position(joint.actuator_id, position, velocity)
            else:
                logger.warning(f"Unknown joint: {joint_name}")
                
    async def move_group(self, kos, group_name: str, positions: Dict[JointName, Position], velocity: float = None):
        """Move all joints in a group to specified positions."""
        if group_name not in self.groups:
            raise ValueError(f"Unknown group: {group_name}")
            
        # Filter the positions to only include joints in this group
        group_joint_names = self.groups[group_name].get_joint_names()
        group_positions = {
            name: pos for name, pos in positions.items()
            if name in group_joint_names
        }
        
        # Move the joints
        await self.move(kos, group_positions, velocity)
        
    async def zero_all(self, kos):
        """Move all joints to zero position."""
        zero_positions = {name: 0.0 for name in self.joints}
        await self.move(kos, zero_positions)
        
    async def zero_group(self, kos, group_name: str):
        """Move all joints in a group to zero position."""
        if group_name not in self.groups:
            raise ValueError(f"Unknown group: {group_name}")
            
        group_joint_names = self.groups[group_name].get_joint_names()
        zero_positions = {name: 0.0 for name in group_joint_names}
        await self.move(kos, zero_positions)
    
    def get_group(self, group_name: str) -> Optional[JointGroup]:
        """Get a joint group by name."""
        return self.groups.get(group_name)
        
    def plot_history(self, joint_names=None, plot_velocity=False, plot_torque=False, 
                    sim_data=None, title_suffix=""):
        """Plot the joint history for specified joints."""
        if not self.joint_history:
            logger.warning("No history data available. Start monitoring first.")
            return
            
        # Use all joints if none specified
        if joint_names is None:
            joint_names = list(self.joints.keys())
            
        # Filter to only include joints that exist
        joint_names = [jn for jn in joint_names if jn in self.joint_history]
        
        if not joint_names:
            logger.warning("No valid joint names provided.")
            return
            
        # Determine how many subplots we need
        num_plots = 1
        if plot_velocity:
            num_plots += 1
        if plot_torque:
            num_plots += 1
            
        # Create the figure and axes
        fig, axes = plt.subplots(num_plots, 1, figsize=(10, 4 * num_plots), sharex=True)
        if num_plots == 1:
            axes = [axes]
            
        # Plot each joint
        for joint_name in joint_names:
            hist = self.joint_history[joint_name]
            
            # Plot position
            axes[0].plot(hist['time'], hist['position'], label=f"{joint_name} (real)")
            axes[0].set_ylabel("Position (degrees)")
            axes[0].set_title(f"Joint Positions{title_suffix}")
            axes[0].legend()
            axes[0].grid(True)
            
            # Plot velocity if requested
            if plot_velocity and len(axes) > 1:
                axes[1].plot(hist['time'], hist['velocity'], label=f"{joint_name} (real)")
                axes[1].set_ylabel("Velocity (deg/s)")
                axes[1].set_title(f"Joint Velocities{title_suffix}")
                axes[1].legend()
                axes[1].grid(True)
                
            # Plot torque if requested
            if plot_torque and len(axes) > 2:
                axes[2].plot(hist['time'], hist['torque'], label=f"{joint_name} (real)")
                axes[2].set_ylabel("Torque")
                axes[2].set_title(f"Joint Torques{title_suffix}")
                axes[2].legend()
                axes[2].grid(True)
                
            # If we have simulation data, plot it
            if sim_data and joint_name in sim_data:
                sim_hist = sim_data[joint_name]
                axes[0].plot(sim_hist['time'], sim_hist['position'], '--', label=f"{joint_name} (sim)")
                
                if plot_velocity and len(axes) > 1:
                    axes[1].plot(sim_hist['time'], sim_hist['velocity'], '--', label=f"{joint_name} (sim)")
                    
                if plot_torque and len(axes) > 2:
                    axes[2].plot(sim_hist['time'], sim_hist['torque'], '--', label=f"{joint_name} (sim)")
        
        # Set the x-axis label on the bottom plot
        axes[-1].set_xlabel("Time (s)")
        
        # Adjust spacing between subplots
        plt.tight_layout()
        
        # Show the plot
        plt.show()
        
        return fig, axes
        
    def save_data(self, filename=None, data_type="real"):
        """Save joint history data to a JSON file."""
        if not self.joint_history:
            logger.warning("No history data available. Start monitoring first.")
            return None
            
        # Generate a default filename if none provided
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"joint_data_{data_type}_{timestamp}.json"
            
        # Prepare the data
        data = {
            joint_name: {
                'time': hist['time'],
                'position': hist['position'],
                'velocity': hist['velocity'],
                'torque': hist['torque']
            }
            for joint_name, hist in self.joint_history.items()
        }
        
        # Save to file
        with open(filename, 'w') as f:
            json.dump(data, f)
            
        logger.info(f"Saved data to {filename}")
        return filename
        
    @staticmethod
    def load_data(filename):
        """Load joint history data from a JSON file."""
        with open(filename, 'r') as f:
            data = json.load(f)
        return data


# Testing utilities
async def run_sine_wave_test(kos, robot, joint_names, amplitude=30.0, frequency=0.5, 
                            duration=10.0, real_robot=True, plot=True, save_data=True):
    """Test joints with a sine wave input and record their response."""
    if not isinstance(joint_names, list):
        joint_names = [joint_names]
        
    # Configure and start monitoring
    await robot.configure(kos, is_real=real_robot, enable_monitoring=True)
    
    # Run the sine wave for the specified duration
    start_time = time.time()
    end_time = start_time + duration
    
    try:
        while time.time() < end_time:
            elapsed = time.time() - start_time
            # Calculate sine wave positions for each joint
            positions = {}
            for joint_name in joint_names:
                # Calculate sine wave position (centered at 0)
                angle = amplitude * np.sin(2 * np.pi * frequency * elapsed)
                positions[joint_name] = angle
                
            # Move joints to calculated positions
            await robot.move(kos, positions)
            
            # Small sleep to avoid overwhelming the system
            await asyncio.sleep(0.01)
            
    finally:
        # Return joints to zero
        await robot.zero_all(kos)
        
        # Stop monitoring
        await robot.stop_monitoring()
        
    # Save data if requested
    data_file = None
    if save_data:
        robot_type = "real" if real_robot else "sim"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        data_file = f"sine_test_{robot_type}_{timestamp}.json"
        robot.save_data(data_file, data_type=robot_type)
        
    # Plot if requested
    if plot:
        robot.plot_history(joint_names, plot_velocity=True, 
                          title_suffix=f" Sine Test ({robot_type})")
        
    return data_file


async def run_step_response_test(kos, robot, joint_names, step_value=30.0, 
                               duration=5.0, real_robot=True, plot=True, save_data=True):
    """Test joints with a step input and record their response."""
    if not isinstance(joint_names, list):
        joint_names = [joint_names]
        
    # Configure and start monitoring
    await robot.configure(kos, is_real=real_robot, enable_monitoring=True)
    
    try:
        # Apply step input
        positions = {jn: step_value for jn in joint_names}
        await robot.move(kos, positions)
        
        # Wait for duration
        await asyncio.sleep(duration)
        
    finally:
        # Return joints to zero
        await robot.zero_all(kos)
        
        # Stop monitoring
        await robot.stop_monitoring()
        
    # Save data if requested
    data_file = None
    if save_data:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        data_file = f"step_test_{timestamp}.json"
        robot.save_data(data_file)
        
    # Plot if requested
    if plot:
        fig, axes = robot.plot_history(joint_names, plot_velocity=True)
        # Add step reference line
        if fig is not None and axes is not None:
            axes[0].axhline(y=step_value, color='r', linestyle='--', label='Target')
            axes[0].legend()
        
        # Save plot if data is being saved
        if save_data and fig is not None:
            plot_file = f"step_test_{timestamp}.png"
            fig.savefig(plot_file)
            logger.info(f"Saved plot to {plot_file}")
            
    return data_file


def compare_real_vs_sim(real_data_file, sim_data_file, joint_names=None, plot_velocity=False, save_plot=True):
    """Compare real and simulation data."""
    # Load the data
    real_data = Robot.load_data(real_data_file)
    sim_data = Robot.load_data(sim_data_file)
    
    # Use all joints if none specified
    if joint_names is None:
        # Use the intersection of joint names from both datasets
        joint_names = list(set(real_data.keys()) & set(sim_data.keys()))
        
    # Create figure and axes
    num_plots = 1 + (1 if plot_velocity else 0)
    fig, axes = plt.subplots(num_plots, 1, figsize=(12, 6 * num_plots), sharex=True)
    if num_plots == 1:
        axes = [axes]
        
    # Plot each joint
    for joint_name in joint_names:
        if joint_name in real_data and joint_name in sim_data:
            real_hist = real_data[joint_name]
            sim_hist = sim_data[joint_name]
            
            # Plot position
            axes[0].plot(real_hist['time'], real_hist['position'], '-', linewidth=2, label=f"{joint_name} (real)")
            axes[0].plot(sim_hist['time'], sim_hist['position'], '--', linewidth=2, label=f"{joint_name} (sim)")
            axes[0].set_ylabel("Position (degrees)")
            axes[0].set_title("Joint Positions: Real vs Simulation")
            axes[0].legend()
            axes[0].grid(True)
            
            # Plot velocity if requested
            if plot_velocity and len(axes) > 1:
                axes[1].plot(real_hist['time'], real_hist['velocity'], '-', linewidth=2, label=f"{joint_name} (real)")
                axes[1].plot(sim_hist['time'], sim_hist['velocity'], '--', linewidth=2, label=f"{joint_name} (sim)")
                axes[1].set_ylabel("Velocity (deg/s)")
                axes[1].set_title("Joint Velocities: Real vs Simulation")
                axes[1].legend()
                axes[1].grid(True)
                
    # Set the x-axis label on the bottom plot
    axes[-1].set_xlabel("Time (s)")
    
    # Adjust spacing between subplots
    plt.tight_layout()
    
    # Save the plot if requested
    if save_plot:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        plot_file = f"comparison_{timestamp}.png"
        fig.savefig(plot_file)
        logger.info(f"Saved comparison plot to {plot_file}")
    
    # Show the plot
    plt.show()
    
    return fig, axes


async def run_parameter_sweep(kos, joint_name, param_values, test_func, real_robot=True, **kwargs):
    """Run a test with different parameter values."""
    results = {}
    
    for param_value in param_values:
        # Create a robot with the specified parameter
        robot = Robot()
        
        # Run the test
        data_file = await test_func(kos, robot, joint_name, 
                                   real_robot=real_robot, 
                                   param_value=param_value, 
                                   **kwargs)
        
        # Store the result
        results[param_value] = data_file
        
    return results