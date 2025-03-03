# Motion Examples

This directory contains examples that demonstrate how to use the motion planner module for robot control and testing.

## Overview

The motion planner provides a high-level interface for robot motion control with features like:

- Simple joint control with human-readable names
- Joint grouping for easier management
- Monitoring and logging of joint states
- Testing utilities for evaluating joint performance
- Visualization tools for analyzing results

## Examples

- **basic_motion.py**: Simple example showing how to initialize a robot, configure it, and move joints
- **monitoring_example.py**: Demonstrates how to enable monitoring, run a sequence of movements, and visualize the results
- **sine_wave_test.py**: Shows how to run a sine wave test to evaluate joint tracking performance in both simulation and real robot environments

## Usage

Each example can be run directly from the command line:

```bash
# Run the basic motion example
python -m demos.examples.motion_examples.basic_motion

# Run the monitoring example
python -m demos.examples.motion_examples.monitoring_example

# Run the sine wave test example
python -m demos.examples.motion_examples.sine_wave_test
```

## Custom Joint Maps

You can create a robot with a custom joint map:

```python
from demos.planners.motion import Robot

# Custom joint map
custom_joint_map = {
    "base": 1,
    "arm": 2,
    "wrist": 3
}

# Create a robot with the custom joint map
robot = Robot(joint_map=custom_joint_map)
```

## Joint Groups

You can define logical groups of joints:

```python
from demos.planners.motion import Robot

# Define joint groups
groups = {
    "left_arm": ["left_shoulder_yaw", "left_shoulder_pitch", "left_elbow"],
    "right_arm": ["right_shoulder_yaw", "right_shoulder_pitch", "right_elbow"],
    "grippers": ["left_gripper", "right_gripper"]
}

# Create a robot with the custom groups
robot = Robot(groups=groups)

# Move all joints in a group
await robot.move_group(kos, "left_arm", {
    "left_shoulder_yaw": 0,
    "left_shoulder_pitch": 45,
    "left_elbow": 30
})
```

## Logging and Monitoring

Enable logging and monitoring to track joint states:

```python
# Configure the robot with monitoring enabled
await robot.configure(kos, is_real=True, enable_monitoring=True)

# Enable logging to a file
log_path = robot.enable_logging(log_dir="logs")

# Run your motion sequence
# ...

# Stop monitoring and disable logging
await robot.stop_monitoring()
robot.disable_logging()

# Plot the results
robot.plot_history(joint_names=["left_knee", "right_knee"], plot_velocity=True)
```

## Testing

Run sine wave tests to evaluate joint performance:

```python
from demos.planners.motion import run_sine_wave_test

# Run a sine wave test
data_file = await run_sine_wave_test(
    kos,
    robot,
    joint_names=["left_knee"],
    amplitude=30.0,
    frequency=0.5,
    duration=10.0,
    real_robot=True,
    plot=True,
    save_data=True
)
```

Compare simulation and real robot results:

```python
from demos.planners.motion import compare_real_vs_sim

# Compare results
compare_real_vs_sim(
    real_data_file,
    sim_data_file,
    joint_names=["left_knee"],
    plot_velocity=True,
    save_plot=True
)
```