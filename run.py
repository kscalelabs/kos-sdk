"""
Interface for running the robot in real or simulation mode.

Contribute:
 
Please add to /planners director your planner. You must have update() and get_command_positions() methods.

This is the main control interface that:
1. Handles both real robot and simulation
2. Manages the control loop timing
3. Coordinates planners and feedback
4. Handles command sending and state updates

Usage:
python run.py --real # only real robot via PyKOS
python run.py --sim # only simulation via Mujoco
python run.py --real --sim # real robot and simulation
"""

from robot import RobotInterface
from ks_digital_twin.puppet.mujoco_puppet import MujocoPuppet
from config import ROBOT_IP, ROBOT_MODEL, DEFAULT_HZ, DEFAULT_TARGET_HZ

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
# Planner registry - add new planners here
########################################################


def get_planner(planner_name: str, args: argparse.Namespace):
    """
    Factory function to create planners based on command line arguments.
    Each planner must implement update() and get_command_positions().
    """
    planners = {
        "zmp": lambda: ZMPWalkingPlanner(enable_lateral_motion=True),
        "play_skill": lambda: PlaySkill(skill_name=args.play_skill, frequency=args.HZ),
        "record_skill": lambda: RecordSkill(
            skill_name=args.record_skill, frequency=args.HZ
        ),
    }
    logger.info(f"Planner: {planner_name}")

    if planner_name not in planners:
        raise ValueError(f"Unsupported planner: {planner_name}")
    return planners[planner_name]()


########################################################


async def controller(
    planner, hz=100, target_hz=100, robot=None, puppet=None, planner_name=None
):
    """
    Main control loop that coordinates planners, robot, and simulation.

    Args:
        planner: Motion planner instance (ZMP, skill playback, etc)
        hz: Control loop frequency
        target_hz: Target frequency for sending commands
        robot: Real robot interface (if --real specified)
        puppet: MuJoCo simulation interface (if --sim specified)
        planner_name: Name of the active planner for planner-specific behavior
    """
    hz_counter = telemetry.HzCounter(interval=1 / hz)
    period = 1 / target_hz
    next_update = time.perf_counter() + period
    start_time = time.perf_counter()
    executed_commands = 0
    last_command_positions = None
    command_counter = 0

    if robot is not None:
        # Real robot control loop
        try:
            async with robot:
                # Initialize robot
                await robot.enable_all_torque()  # Enable torque for all joints

                # Countdown before homing
                for i in range(3, 0, -1):
                    logger.info(f"Homing actuators in {i}...")
                    await asyncio.sleep(1)

                # Set to zero position
                await robot.homing_actuators()

                # Countdown before starting motion
                for i in range(3, 0, -1):
                    logger.info(f"Starting in {i}...")
                    await asyncio.sleep(1)

                # Main control loop
                while True:
                    try:
                        # Calculate timing for this iteration
                        current_time = time.perf_counter()
                        elapsed_time = current_time - start_time
                        target_commands = hz * elapsed_time

                        # Check if we should send commands this iteration
                        should_send = (
                            executed_commands + 1
                        ) / target_commands >= 0.95 or (
                            executed_commands + 1
                        ) / target_commands <= 1.05  # Allow 5% margin

                        logger.info(
                            f"Should send: {should_send}, {executed_commands/target_commands:.2f}"
                        )

                        if not should_send:
                            logger.warning(
                                f"Skipping command send - ratio {executed_commands/target_commands:.2f}"
                            )

                        # Update planner at target frequency
                        if command_counter % max(1, round(target_hz / hz)) == 0:
                            # Get current joint positions from robot
                            feedback_state = (
                                await robot.get_feedback_positions() if robot else {}
                            )
                            # Update planner with current state
                            planner.update(feedback_state)
                            # Get new target positions
                            last_command_positions = planner.get_command_positions()
                        command_counter += 1

                        if should_send:
                            # Define control functions for real and sim
                            async def control_real() -> None:
                                if last_command_positions:
                                    # Send commands to real robot
                                    await robot.set_real_command_positions(
                                        last_command_positions
                                    )

                            async def control_sim() -> None:
                                if puppet is not None and last_command_positions:
                                    # Convert degrees to radians for MuJoCo
                                    radian_command_positions: Dict[
                                        str, Union[int, Radian]
                                    ] = {
                                        joint: math.radians(value)
                                        for joint, value in last_command_positions.items()
                                    }
                                    # Send commands to simulation
                                    await puppet.set_joint_angles(
                                        radian_command_positions
                                    )

                            # Send commands to both real and sim simultaneously
                            await asyncio.gather(
                                control_real(),
                                control_sim(),
                            )
                            executed_commands += 1

                        # Update timing stats
                        await hz_counter.update()

                        # Sleep to maintain target frequency
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
        # Simulation-only control loop
        try:
            while True:
                # Calculate timing
                current_time = time.perf_counter()
                elapsed_time = current_time - start_time
                target_commands = hz * elapsed_time
                should_send = (
                    executed_commands + 1
                ) / target_commands >= 0.95  # Allow 5% margin

                logger.info(
                    f"Should send: {should_send}, {executed_commands/target_commands:.2f}"
                )
                if not should_send:
                    logger.warning(
                        f"Skipping command send - ratio {executed_commands/target_commands:.2f}"
                    )

                # Update planner at target frequency
                if command_counter % max(1, round(target_hz / hz)) == 0:
                    # Get feedback from simulation
                    if puppet:
                        model, data = await puppet.get_mj_model_and_data()
                        joint_names = await puppet.get_joint_names()
                        feedback_state = {
                            name: pos
                            for name, pos in zip(joint_names[1:], data.qpos[7:])
                        }  # Skip root joint and its qpos
                    else:
                        feedback_state = {}
                    # Update planner and get new commands
                    planner.update(feedback_state)
                    last_command_positions = planner.get_command_positions()
                command_counter += 1

                # Send commands to simulation
                if should_send and last_command_positions:
                    radian_command_positions: Dict[str, Union[int, Radian]] = {
                        joint: math.radians(value)
                        for joint, value in last_command_positions.items()
                    }
                    await puppet.set_joint_angles(radian_command_positions)
                executed_commands += 1

                # Update timing stats
                await hz_counter.update()

                # Sleep to maintain target frequency
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
    """
    Main entry point. Parses arguments and sets up control loop.
    """
    # Parse command line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--real", action="store_true", help="Use PyKOS to command actual actuators."
    )
    parser.add_argument(
        "--sim", action="store_true", help="Also send commands to Mujoco simulation."
    )
    parser.add_argument("--ip", default=ROBOT_IP, help="IP address of the robot.")

    parser.add_argument(
        "--HZ", type=int, default=DEFAULT_HZ, help="Frequency of the skill to play."
    )
    parser.add_argument(
        "--target_HZ",
        type=int,
        default=DEFAULT_TARGET_HZ,
        help="Target frequency of the skill to play.",
    )

    parser.add_argument("--planner", default="zmp", help="Name of the planner to use.")

    parser.add_argument(
        "--play_skill", default="pickup", help="Name of the skill to play."
    )
    parser.add_argument(
        "--record_skill",
        default=time.strftime("%Y%m%d_%H%M%S_skill"),
        help="Name of the skill to record.",
    )

    args = parser.parse_args()

    # Setup interfaces based on arguments
    ip_address = args.ip if args.real else None
    mjcf_name = "zbot-v2"

    robot = RobotInterface(ip=ip_address) if args.real else None
    puppet = MujocoPuppet(mjcf_name) if args.sim else None

    # Create planner
    planner = get_planner(args.planner, args)
    logger.info("Running in real mode..." if args.real else "Running in sim mode...")

    try:
        # Start control loop
        await controller(
            planner,
            hz=args.HZ,
            target_hz=args.target_HZ,
            robot=robot,
            puppet=puppet,
            planner_name=args.planner,
        )
    except Exception as e:
        logger.error(f"Fatal error in main loop: {str(e)}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())
