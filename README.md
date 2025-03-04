# KOS SDK 
Software Development Kit (SDK) for KOS robots that bundles together libraries, tools, APIs for developers to build, test, and deploy Z-Bot and K-Bot applications. 

## Overview
Pre-built modules for sensors, policies, motion planning, perception, simulation, and tests for rapid prototyping, acceptance testing, and problem diagnosis. 

## Features
- Tests: Comprehensive unit tests for all robot components such as IMU, servos, camera, speaker, microhpone, led.
- Simulation: KOS-SIM compatbility. https://github.com/kscalelabs/kos-sim
- Locomotion: PPO based locomotion. 
- Manipulation: ACT and IK based manipulation. 
- Perception: Object detection, human pose estimation, etc.
- Algorithms: Motion planning, ZMP, balance control, etc.
- Tools: Keyboard teleoperation, telemtry data logging.

## Requirements
- Milk-V Image with kos version 0.6.1
- Python 3.11 with pykos version 0.7.1


## Getting Started
1. Set up Git LFS and pull large files

```bash
# Install Git LFS
git lfs install

# Pull large files (URDF models, neural networks, etc.)
git lfs pull
```

2. Clone the repository

```bash
git clone git@github.com:kscalelabs/kos-sdk.git
```

3. Make sure you're using Python 3.11 or greater

```bash
python --version  # Should show Python 3.11 or greater
```

4. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

5. Run the tests

```bash
make test
```

### Additional Tests

Check that the URDF and MJCF models are realistic:

```bash
# To check the URDF model:
ks robots urdf pybullet zbot-v2 --fixed-base

# To check the MJCF model:
ks robots urdf mujoco zbot-v2
```