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

Unfinished features:
- Skillit interface
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




## Architecture
`robot.py` - Interface for the robot and setup the connection to the robot and sending commands to the robot.
`experiments/` - Random experiments and demos.
`planners/` - Defines the planner classes and programs that run the robot. You can add your own planners to this folder.
`run.py` - Controller interface for real and simulation.
`telemetry.py` - Collects data from the robot.


## License
