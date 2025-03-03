"""
Motion utilities for working with the motion planner module.

These utilities make it easy to run tests, log data, and visualize results
when working with the motion planner.
"""

import os
import json
import asyncio
import logging
from datetime import datetime
import matplotlib.pyplot as plt
import numpy as np
from typing import Dict, List, Optional, Tuple, Union

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import motion module
from demos.planners.motion import Robot, compare_real_vs_sim


def load_and_plot_data(data_file: str, joint_names: Optional[List[str]] = None, 
                      plot_velocity: bool = False, plot_torque: bool = False, 
                      title: Optional[str] = None) -> Tuple:
    """Load data from a file and plot it."""
    # Load the data
    try:
        with open(data_file, 'r') as f:
            data = json.load(f)
    except Exception as e:
        logger.error(f"Error loading data file: {e}")
        return None, None
    
    # Use all joints if none specified
    if joint_names is None:
        joint_names = list(data.keys())
    
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
        if joint_name in data:
            hist = data[joint_name]
            
            # Plot position
            axes[0].plot(hist['time'], hist['position'], label=f"{joint_name}")
            axes[0].set_ylabel("Position (degrees)")
            axes[0].set_title(title or "Joint Positions")
            axes[0].legend()
            axes[0].grid(True)
            
            # Plot velocity if requested
            if plot_velocity and len(axes) > 1:
                axes[1].plot(hist['time'], hist['velocity'], label=f"{joint_name}")
                axes[1].set_ylabel("Velocity (deg/s)")
                axes[1].set_title("Joint Velocities")
                axes[1].legend()
                axes[1].grid(True)
                
            # Plot torque if requested
            if plot_torque and len(axes) > 2:
                axes[2].plot(hist['time'], hist['torque'], label=f"{joint_name}")
                axes[2].set_ylabel("Torque")
                axes[2].set_title("Joint Torques")
                axes[2].legend()
                axes[2].grid(True)
    
    # Set the x-axis label on the bottom plot
    axes[-1].set_xlabel("Time (s)")
    
    # Adjust spacing between subplots
    plt.tight_layout()
    
    # Show the plot
    plt.show()
    
    return fig, axes


def setup_data_directory(base_dir: str = 'logs'):
    """Create a data directory for storing motion logs and plots."""
    # Create a timestamped directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    data_dir = os.path.join(base_dir, f"motion_data_{timestamp}")
    
    # Create the directory structure
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(os.path.join(data_dir, 'plots'), exist_ok=True)
    
    logger.info(f"Created data directory: {data_dir}")
    return data_dir


def extract_metrics(data_file: str, joint_names: Optional[List[str]] = None) -> Dict:
    """Extract performance metrics from a data file."""
    # Load the data
    try:
        with open(data_file, 'r') as f:
            data = json.load(f)
    except Exception as e:
        logger.error(f"Error loading data file: {e}")
        return {}
    
    # Use all joints if none specified
    if joint_names is None:
        joint_names = list(data.keys())
    
    metrics = {}
    for joint_name in joint_names:
        if joint_name in data:
            hist = data[joint_name]
            
            # Calculate metrics
            position_data = np.array(hist['position'])
            velocity_data = np.array(hist['velocity'])
            
            metrics[joint_name] = {
                'mean_position': float(np.mean(position_data)),
                'max_position': float(np.max(position_data)),
                'min_position': float(np.min(position_data)),
                'position_range': float(np.max(position_data) - np.min(position_data)),
                'mean_velocity': float(np.mean(velocity_data)),
                'max_velocity': float(np.max(velocity_data)),
                'min_velocity': float(np.min(velocity_data)),
                'velocity_range': float(np.max(velocity_data) - np.min(velocity_data)),
            }
            
            # If there are at least 2 data points, calculate frequency domain metrics
            if len(position_data) > 1:
                # Calculate time intervals
                time_data = np.array(hist['time'])
                dt = np.mean(np.diff(time_data))
                
                # Calculate FFT of position data
                n = len(position_data)
                fft_values = np.fft.fft(position_data) / n
                freqs = np.fft.fftfreq(n, dt)
                
                # Find the peak frequency (excluding DC component)
                mask = freqs > 0
                peak_idx = np.argmax(np.abs(fft_values[mask]))
                peak_freq = freqs[mask][peak_idx]
                
                metrics[joint_name]['peak_frequency'] = float(peak_freq)
    
    return metrics