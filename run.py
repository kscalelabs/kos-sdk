"""
Interface for running the robot in real or simulation mode.

Contribute:

Please add to /planners director your planner. You must have update() and get_command_positions() methods.

Usage:
python run.py --real # only real robot via PyKOS
python run.py --sim # only simulation via Mujoco
python run.py --real --sim # real robot and simulation
"""

from robot import RobotInterface
from ks_digital_twin.puppet.mujoco_puppet import MujocoPuppet

from loguru import logger
import argparse
import asyncio
import time
import traceback
import math

from typing import Dict, Union
from unit_types import Degree, Radian

import telemetry

from planners.zmp_walking import ZMPWalkingPlanner
from planners.record_skill import RecordSkill
from planners.play_skill import PlaySkill

########################################################
# TODO: ADD YOUR PLANNER CLASSES HERE
########################################################

def get_planner(planner_name: str, args: argparse.Namespace):
    planners = {
        "zmp": lambda: ZMPWalkingPlanner(enable_lateral_motion=True),
        "play_skill": lambda: PlaySkill(skill_name=args.play_skill, frequency=args.HZ),
        "record_skill": lambda: RecordSkill(skill_name=args.record_skill, frequency=args.HZ)
    }
    
    if planner_name not in planners:
        raise ValueError(f"Unsupported planner: {planner_name}")
        
    return planners[planner_name]()


########################################################


async def controller(planner, hz=100, target_hz=100, robot=None, puppet=None):
    hz_counter = telemetry.HzCounter(interval=1 / hz)
    period = 1 / target_hz
    next_update = time.perf_counter() + period
    start_time = time.perf_counter()
    executed_commands = 0
    last_command_positions = None
    command_counter = 0

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
                    try:
                        current_time = time.perf_counter()
                        elapsed_time = current_time - start_time
                        target_commands = hz * elapsed_time
                        should_send = (executed_commands + 1) / target_commands >= 0.95 or (executed_commands + 1) / target_commands <= 1.05  # Allow 5% margin

                        # logger.info(f"Should send: {should_send}, {executed_commands/target_commands:.2f}")
                        
                        if not should_send:
                            logger.warning(f"Skipping command send - ratio {executed_commands/target_commands:.2f}")

                        # Only get new commands at target_hz rate
                        if command_counter % max(1, round(target_hz/hz)) == 0:
                            planner.update(robot.get_feedback_state())
                            last_command_positions = planner.get_command_positions()
                        command_counter += 1

                        if should_send:
                            async def control_real() -> None:
                                if last_command_positions:
                                    await robot.set_real_command_positions(last_command_positions)

                            async def control_sim() -> None:
                                if puppet is not None and last_command_positions:
                                    radian_command_positions: Dict[str, Union[int, Radian]] = {
                                        joint: math.radians(value)
                                        for joint, value in last_command_positions.items()
                                    }
                                    await puppet.set_joint_angles(radian_command_positions)

                            await asyncio.gather(
                                control_real(),
                                control_sim(),
                            )
                            executed_commands += 1

                        await hz_counter.update()
                        
                        # Sleep until next scheduled update
                        sleep_time = next_update - time.perf_counter()
                        if sleep_time > 0:
                            await asyncio.sleep(sleep_time)
                        next_update += period

                    except Exception as inner_e:
                        logger.error(f"Error inside controller loop: {str(inner_e)}")
                        logger.debug(traceback.format_exc())
                        raise
        except KeyboardInterrupt:
            logger.info("Received KeyboardInterrupt, shutting down gracefully.")
        except Exception as e:
            logger.error(f"Error in real robot loop: {str(e)}", exc_info=True)
    else:
        try:
            while True:
                current_time = time.perf_counter()
                elapsed_time = current_time - start_time
                target_commands = hz * elapsed_time
                should_send = (executed_commands + 1) / target_commands >= 0.95  # Allow 5% margin
                
                # logger.info(f"Should send: {should_send}, {executed_commands/target_commands:.2f}")
                if not should_send:
                    logger.warning(f"Skipping command send - ratio {executed_commands/target_commands:.2f}")

                # Only get new commands at target_hz rate
                if command_counter % max(1, round(target_hz/hz)) == 0:
                    planner.update(last_command_positions)
                    last_command_positions = planner.get_command_positions()
                command_counter += 1

                if should_send and last_command_positions:
                    radian_command_positions: Dict[str, Union[int, Radian]] = {
                        joint: math.radians(value)
                        for joint, value in last_command_positions.items()
                    }
                    await puppet.set_joint_angles(radian_command_positions)
                executed_commands += 1

                await hz_counter.update()

                # Sleep until next scheduled update
                sleep_time = next_update - time.perf_counter()
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)

                if should_send:
                    next_update += period

        except KeyboardInterrupt:
            logger.info("Received KeyboardInterrupt, shutting down gracefully.")
        except Exception as e:
            logger.error(f"Error in simulation loop: {str(e)}", exc_info=True)


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--real", action="store_true", help="Use PyKOS to command actual actuators."
    )
    parser.add_argument(
        "--sim", action="store_true", help="Also send commands to Mujoco simulation."
    )
    parser.add_argument("--ip", default="192.168.42.1", help="IP address of the roboot.")

    parser.add_argument("--HZ", type=int, default=50, help="Frequency of the skill to play.")
    parser.add_argument("--target_HZ", type=int, default=50, help="Target frequency of the skill to play.")


    parser.add_argument("--planner", default="zmp", help="Name of the planner to use.")

    parser.add_argument("--play_skill", default="pickup", help="Name of the skill to play.")
    parser.add_argument("--record_skill", default=time.strftime("%Y%m%d_%H%M%S_skill"), help="Name of the skill to record.")

    args = parser.parse_args()

    ip_address = args.ip if args.real else None
    mjcf_name = "zbot-v2"

    robot = RobotInterface(ip=ip_address) if args.real else None
    puppet = MujocoPuppet(mjcf_name) if args.sim else None

    planner = get_planner(args.planner, args)
    logger.info("Running in real mode..." if args.real else "Running in sim mode...")

    try:
        await controller(planner, hz=args.HZ, target_hz=args.target_HZ, robot=robot, puppet=puppet)
    except Exception as e:
        logger.error(f"Fatal error in main loop: {str(e)}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(main())
