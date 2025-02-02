# Z-Bot Demos

## Overview

## Features


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
`robot.py` defines the interface for the robot and setup the connection to the robot and sending commands to the robot.
`experiments/` defines the planner classes and programs that run the robot.
`run.py` is the main script that runs the robot in real or simulation mode.
`telemetry.py` is used to collect data from the robot.
`unit_types.py` defines the unit types for the robot.

## Contributing



## Architecture


## License
