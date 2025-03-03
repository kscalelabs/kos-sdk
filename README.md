# Z-Bot Demos

## Overview

Unified interface and telemetry system for both real and sim robots to make it easy to test, develop, and deploy different planners, policies, and Skilit skills in MuJoCo digital twin (ground truth) and real robot. The goal is to create reliable and replicable demos.


## Features

1. Digital Twin - MuJoCo is the ground truth. Deploy and check scripts in MuJoCo before deploying onto real robot. Check if there's a MuJoCo and physical robot mismatch.
2. Controller interface - 50HZ getting feedback and sending commands, to real robot and sim robot while managing telemetry.
3. Planner interface - ZMP, CV leaf picking, RL walking, Xbox controller. Input: Feedback state -> Ouput: command state.
4. Telemetry - Async log: Actuator position, current, torque, temperature, errors. Command per second, frequency, communication status.
5. Scripts creation - Record and play skills using the controller and intialization inteface with the Skillit library. 
6. Robot test, config, and initalization - Minimize failure points by testing connection, actuator states, set to the same starting position, and adding necessary offsets
7. Skills - Playing and recording actions
8. Motion module - High-level interface for robot motion control with:
   - Simple joint control with human-readable joint names
   - Joint grouping for easier management
   - Real-time monitoring and state tracking
   - Visualization tools for performance analysis
   - Tools for comparing real vs. simulated performance

Unfinished features:
- Xbox controller interface
- Configs and parameters that can be changed while running
- More demos

## Requirements

- Milk-V Image with kos version 0.6.1
- Python 3.11 with pykos version 0.7.1


## Installation
1. Clone the repository
```
git clone https://github.com/kscalelabs/demos
cd demos
```
2. Create and activate a virtual environment
```
conda create -n demos python=3.11
conda activate demos
```

3. Install dependencies
```
pip install -r requirements.txt
```

4. Download MuJoCo models
```
kscale user key # you'll be prompted to login
kscale robots urdf download zbot-v2
```

## Usage

Add planner classes to the experiments directory and then add them to the get_planner function. Every planner class should have a get_planner_commands method that returns a dictionary of joint names and their target positions in degrees.

Usage:
```
python run.py --real --planner zmp

python run.py --sim --planner zmp 

python run.py --real --sim 
```

### Robot Selection

You can easily control different robots by specifying the robot type or IP:

```
# Using predefined robot types
python run.py --real --robot alum1 --planner zmp
python run.py --real --robot white --planner zmp

# Or using a custom IP
python run.py --real --ip 10.33.85.8 --planner zmp
```

For convenience, you can also use the `run_robot.py` script:

```
# Control the alum1 robot with the ZMP planner
./run_robot.py alum1 --planner zmp

# Control the white robot and show simulation
./run_robot.py white --sim
```


## Architecture
`robot.py` - Interface for the robot and setup the connection to the robot and sending commands to the robot.
`robot_config.py` - Configuration module for robot IP addresses and settings.
`run_robot.py` - Convenience script for running different robots.
`experiments/` - Random experiments and demos.
`planners/` - Defines the planner classes and programs that run the robot. You can add your own planners to this folder.
`planners/motion.py` - High-level motion control module with joint grouping, monitoring, and testing utilities.
`run.py` - Controller interface for real and simulation.
`telemetry.py` - Collects data from the robot.
`utils/motion_utils.py` - Utilities for working with the motion module.
`examples/motion_examples/` - Example scripts demonstrating how to use the motion module.


## License
