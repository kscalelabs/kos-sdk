"""
Interface for running the robot in real or simulation mode.

Contribute:
Add planner classes to the experiments directory and then add them to the get_planner function.
Every planner class should have a get_planner_commands method that returns a dictionary of joint names and their target positions in degrees.

Usage:
python run.py --real
python run.py --sim
python run.py --real --sim
"""

from robot import RobotInterface
from ks_digital_twin.puppet.mujoco_puppet import MujocoPuppet

import math
from loguru import logger
import argparse
import asyncio
import time

from typing import Dict, Union
from unit_types import Degree, Radian

import telemetry

from experiments.zmp_walking import ZMPWalkingPlanner

########################################################
# TODO: ADD YOUR PLANNER CLASSES HERE
########################################################

def get_planner(planner_name):
    if planner_name == "zmp":
        return ZMPWalkingPlanner(enable_lateral_motion=True)
    else:
        raise ValueError(f"Unsupported planner: {planner_name}")
    
########################################################

async def controller(planner, hz=1000, robot=None, puppet=None):
    hz_counter = telemetry.HzCounter(interval=1 / hz)  

    if robot is not None:
        try:
            async with robot:
                await robot.configure_actuators()

                for i in range(3, 0, -1):
                    logger.info(f"Homing actuators in {i}...")
                    await asyncio.sleep(1)
                    
                await robot.homing_actuators()

                for i in range(3, 0, -1):
                    logger.info(f"Starting in {i}...")
                    await asyncio.sleep(1)

                while True:
                    start = time.perf_counter()
                    
                    feedback_positions : Dict[str, Union[int, Degree]] = await robot.get_feedback_positions_only()

                    planner.update(feedback_positions)

                    command_positions : Dict[str, Union[int, Degree]] = planner.get_planner_commands()
                    
                    if command_positions:
                        await robot.set_command_positions(command_positions)
                    if puppet is not None and command_positions:
                        command_positions_rad : Dict[str, Union[int, Radian]] = {k: math.radians(v) for k, v in command_positions.items()}
                        await puppet.set_joint_angles(command_positions_rad)

                    hz_counter.update()
                    
                    elapsed = time.perf_counter() - start
                    remaining = 1 / hz - elapsed

                    await asyncio.sleep(remaining if remaining > 0 else 0)
        except KeyboardInterrupt:
            logger.info("Received KeyboardInterrupt, shutting down gracefully.")
        except Exception as e:
            logger.error(f"Error in real robot loop: {str(e)}", exc_info=True)
    else:
        try:
            while True:
                start = time.perf_counter()
                
                planner.update()

                command_positions : Dict[str, Union[int, Degree]] = planner.get_planner_commands()
                command_positions_rad : Dict[str, Union[int, Radian]] = {k: math.radians(v) for k, v in command_positions.items()}

                await puppet.set_joint_angles(command_positions_rad)                            

                hz_counter.update()
                
                elapsed = time.perf_counter() - start
                remaining = 1 / hz - elapsed
                await asyncio.sleep(remaining if remaining > 0 else 0)

        except KeyboardInterrupt:
            logger.info("Received KeyboardInterrupt, shutting down gracefully.")
        except Exception as e:
            logger.error(f"Error in simulation loop: {str(e)}", exc_info=True)

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--real", action="store_true", help="Use PyKOS to command actual actuators.")
    parser.add_argument("--sim", action="store_true", help="Also send commands to Mujoco simulation.")
    parser.add_argument("--ip", default="192.168.42.1", help="IP address of the robot.")
    parser.add_argument("--planner", default="zmp", help="Name of the planner to use.")
    args = parser.parse_args()

    ip_address = args.ip if args.real else None
    mjcf_name = "zbot-v2"

    robot = RobotInterface(ip=ip_address) if args.real else None
    puppet = MujocoPuppet(mjcf_name) if args.sim else None

    planner = get_planner(args.planner)
    logger.info("Running in real mode..." if args.real else "Running in sim mode...")
    
    try:
        await controller(planner, hz=1000, robot=robot, puppet=puppet)
    except Exception as e:
        logger.error(f"Fatal error in main loop: {str(e)}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(main())