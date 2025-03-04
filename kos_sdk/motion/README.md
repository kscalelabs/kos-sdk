# Motion

A high-level robot motion control library for KOS (K-Scale Operating System).

## Overview

The Motion library provides a simplified interface for robot control with:

- Joint abstraction with human-readable names and actuator IDs
- Joint grouping for organizing joints into logical collections
- Configuration management for handling different settings between simulated and real robots
- Asynchronous API built with Python's asyncio
- State tracking for accessing joint positions, velocities, and torques
- Testing and monitoring tools for comparing simulator vs real robot performance

## Usage

### Basic Usage

```python
import asyncio
from pykos import KOS
from kos_sdk.motion import Robot

async def main():
    # Create a robot with default joint mapping
    robot = Robot()
    
    # Connect to KOS
    async with KOS() as kos:
        # Configure robot
        await robot.configure(kos, is_real=False)
        
        # Move left shoulder to position 45 degrees
        await robot.move(kos, {"left_shoulder_yaw": 45})
        
        # Get joint states
        states = await robot.get_states(kos)
        print(f"Left shoulder position: {states['left_shoulder_yaw'].position}")
        
        # Zero all joints
        await robot.zero_all(kos)

if __name__ == "__main__":
    asyncio.run(main())
```

### Grouping Joints

```python
# Define joint groups
groups = {
    "left_arm": ["left_shoulder_yaw", "left_shoulder_pitch", "left_elbow"],
    "right_arm": ["right_shoulder_yaw", "right_shoulder_pitch", "right_elbow"],
    "grippers": ["left_gripper", "right_gripper"],
}

# Create robot with groups
robot = Robot(groups=groups)

# Use a specific group
left_arm = robot.get_group("left_arm")
if left_arm:
    print(f"Left arm has {len(left_arm)} joints")
    for joint in left_arm:
        print(f"Joint: {joint.name}, ID: {joint.actuator_id}")
```

### Custom Configuration

```python
from kos_sdk.motion import Robot, RobotConfig

# Create custom configuration
config = RobotConfig(
    sim_gains=(80, 40),  # Lower kp, kd for simulator
    real_gains=(24, 20),  # Lower gains for real robot
    max_torque=50.0      # Limit maximum torque
)

# Create robot with custom configuration
robot = Robot(config=config)
```

### Migration from RobotInterface

If you've been using the original RobotInterface class, you can easily migrate to the new Robot class:

```python
from kos_sdk.utils.robot import RobotInterface

# Create the original interface
robot_interface = RobotInterface(ip="192.168.1.1")

# Convert to the new Robot class
robot = robot_interface.to_motion_robot()

# You can also pass custom configuration
from kos_sdk.motion import RobotConfig
config = RobotConfig(max_torque=50.0)
robot = robot_interface.to_motion_robot(config=config)
```

## Key Features

- **Joint Abstraction**: Map actuator IDs to human-readable joint names
- **Joint Groups**: Organize joints into logical groups (arms, legs, etc.)
- **Configuration Management**: Different settings for simulation vs real robots
- **State Tracking**: Access positions, velocities, and torques for all joints
- **Monitoring**: Monitor joint states at regular intervals