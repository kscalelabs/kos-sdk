# Z-Bot Demos

## Overview
This repo contains demos for the Z-Bot and includes a controller interface for real and simulation for easy testing, creating, and deploying different planners, controllers, and skillit skills while ensuring the same interface for the robot and ground truth in MuJoCo.

## Features
- Abstracted digital twin and Skillit packages
- Common controller interface for real and simulation
- Modular planners (e.g., ZMP Walking)
- Real-time telemetry and logging
- Robot initialization and configuration

Unfinished features:
- Skillit interface
- Xbox controller interface
- Configs and parameters that can be changed while running
- More demos

## Requirements

- Milk-V Image with kos version 0.6.1
- Conda
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

`robot.py` - Interface for the robot and setup the connection to the robot and sending commands to the robot.
`experiments/` - Random experiments and demos.
`planners/` - Defines the planner classes and programs that run the robot. You can add your own planners to this folder.
`run.py` - Controller interface for real and simulation.
`telemetry.py` - Collects data from the robot.

## Architecture


## License
