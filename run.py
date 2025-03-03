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
from robot_config import RobotType, get_robot_ip, get_robot_config

from loguru import logger
import argparse
import asyncio
import time
import traceback
import math
import platform

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
    planner, hz=100, target_hz=100, robot=None, puppet=None, planner_name: str = "zmp"
):
    """Main controller loop."""
    start_time = time.perf_counter()
    period = 1.0 / hz
    next_update = start_time + period
    executed_commands = 0
    command_counter = 0
    last_command_positions = {}
    hz_counter = telemetry.HzCounter(name="controller", interval=5.0)

    # Flag to indicate if we're in command mode
    in_command_mode = False

    # Set up keyboard listener for continuous recording
    if (
        planner_name == "record_skill"
        and hasattr(planner, "continuous_mode")
        and planner.continuous_mode
    ):
        logger.info("Continuous recording mode active:")
        logger.info("  - Press Ctrl+C to stop recording and save")

        # Set up keyboard listener in a separate thread
        if platform.system() == "Windows":
            logger.info("  - Press 's' key to save current frames without stopping")
            logger.info("  - Press 'c' key to enter command mode")

            def windows_keyboard_listener():
                try:
                    import msvcrt

                    nonlocal in_command_mode

                    while True:
                        if msvcrt.kbhit():
                            key = msvcrt.getch().decode("utf-8").lower()
                            if key == "s":
                                logger.info("Saving current frames...")
                                planner.save()
                            elif key == "c":
                                # Enter command mode
                                in_command_mode = True
                                logger.info(
                                    "Command mode: Enter command (e.g., 'save my_skill_name'):"
                                )
                                cmd_input = ""
                                while True:
                                    if msvcrt.kbhit():
                                        char = msvcrt.getch().decode("utf-8")
                                        if char == "\r":  # Enter key
                                            break
                                        elif char == "\b":  # Backspace
                                            if cmd_input:
                                                cmd_input = cmd_input[:-1]
                                                # Erase character from console
                                                print("\b \b", end="", flush=True)
                                        else:
                                            cmd_input += char
                                            print(char, end="", flush=True)
                                    time.sleep(0.01)
                                print()  # New line after command

                                if cmd_input.strip():
                                    parts = cmd_input.strip().split()
                                    command = parts[0]
                                    args = parts[1:] if len(parts) > 1 else []
                                    if hasattr(planner, "handle_command"):
                                        planner.handle_command(command, args)
                                    else:
                                        logger.warning(
                                            f"Planner does not support commands"
                                        )
                                in_command_mode = False
                        time.sleep(0.1)
                except Exception as e:
                    logger.warning(f"Could not start keyboard listener: {e}")

            # Start Windows keyboard listener
            try:
                import threading

                keyboard_thread = threading.Thread(
                    target=windows_keyboard_listener, daemon=True
                )
                keyboard_thread.start()
            except Exception as e:
                logger.warning(f"Could not start keyboard listener: {e}")
        else:
            logger.info(
                "  - Press 's' key followed by Enter to save current frames without stopping"
            )
            logger.info("  - Press 'c' key followed by Enter to enter command mode")

            def unix_keyboard_listener():
                try:
                    import sys
                    import select
                    import termios
                    import tty

                    nonlocal in_command_mode

                    # Set up stdin for non-blocking reads
                    old_settings = termios.tcgetattr(sys.stdin)
                    try:
                        tty.setcbreak(sys.stdin.fileno())
                        while True:
                            # Check if there's input available
                            if select.select([sys.stdin], [], [], 0.1)[0]:
                                key = sys.stdin.read(1).lower()
                                if key == "s":
                                    logger.info("Saving current frames...")
                                    planner.save()
                                elif key == "c":
                                    # Enter command mode
                                    in_command_mode = True
                                    termios.tcsetattr(
                                        sys.stdin, termios.TCSADRAIN, old_settings
                                    )
                                    logger.info(
                                        "Command mode: Enter command (e.g., 'save my_skill_name'):"
                                    )
                                    cmd_input = input().strip()
                                    if cmd_input:
                                        parts = cmd_input.split()
                                        command = parts[0]
                                        args = parts[1:] if len(parts) > 1 else []
                                        if hasattr(planner, "handle_command"):
                                            planner.handle_command(command, args)
                                        else:
                                            logger.warning(
                                                f"Planner does not support commands"
                                            )
                                    # Reset to non-blocking mode
                                    tty.setcbreak(sys.stdin.fileno())
                                    in_command_mode = False
                            time.sleep(0.1)
                    finally:
                        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
                except Exception as e:
                    logger.warning(f"Could not start keyboard listener: {e}")

            # Start Unix keyboard listener
            try:
                import threading

                keyboard_thread = threading.Thread(
                    target=unix_keyboard_listener, daemon=True
                )
                keyboard_thread.start()
            except Exception as e:
                logger.warning(f"Could not start keyboard listener: {e}")
                logger.info("You can still use Ctrl+C to stop and save.")

    if robot is not None:
        try:
            async with robot:
                if planner_name == "record_skill":
                    logger.info("Configuring actuators for recording skill")
                    await robot.configure_actuators_record()

                    # For continuous recording, make sure torque is enabled during zeroing
                    if hasattr(planner, "continuous_mode") and planner.continuous_mode:
                        logger.info(
                            "Continuous recording mode detected - ensuring robot is zeroed with torque enabled"
                        )
                        await robot.enable_all_torque()
                else:
                    # For playback, use gentler settings
                    if planner_name == "play_skill":
                        logger.info(
                            "Configuring actuators with gentle settings for playback"
                        )
                        await robot.enable_gentle_torque()
                    else:
                        await robot.configure_actuators()

                # Shorter countdown for zeroing
                for i in range(3, 0, -1):
                    logger.info(f"Preparing to home actuators in {i}...")
                    await asyncio.sleep(1)

                # Use the gradual homing function
                logger.info("Starting gradual homing process...")
                await robot.homing_actuators()

                # Shorter wait time after homing
                logger.info("Waiting for robot to stabilize...")
                await asyncio.sleep(1)

                # Shorter countdown before starting
                for i in range(3, 0, -1):
                    logger.info(f"Starting in {i}...")
                    await asyncio.sleep(1)

                while True:
                    try:
                        current_time = time.perf_counter()
                        elapsed_time = current_time - start_time
                        target_commands = hz * elapsed_time
                        should_send = (
                            executed_commands + 1
                        ) / target_commands >= 0.95 or (
                            executed_commands + 1
                        ) / target_commands <= 1.05  # Allow 5% margin

                        # Skip processing if in command mode
                        if in_command_mode:
                            await asyncio.sleep(0.1)
                            continue

                        # Only get new commands at target_hz rate
                        if command_counter % max(1, round(target_hz / hz)) == 0:
                            planner.update(await robot.get_feedback_positions())
                            last_command_positions = planner.get_command_positions()

                            # Handle manual mode for record_skill planner
                            if planner_name == "record_skill" and hasattr(
                                planner, "should_toggle_torque"
                            ):
                                if planner.should_toggle_torque():
                                    # Disable torque for manual positioning
                                    logger.info(
                                        "Manual positioning enabled - disabling torque"
                                    )
                                    await robot.disable_all_torque()
                                else:
                                    # Enable torque when not in manual mode
                                    logger.info(
                                        "Manual positioning disabled - enabling torque"
                                    )
                                    await robot.enable_all_torque()

                        command_counter += 1

                        if should_send and (
                            planner_name != "record_skill"
                            or not hasattr(planner, "should_toggle_torque")
                            or not planner.should_toggle_torque()
                        ):
                            # Only send commands when not in manual mode
                            async def control_real() -> None:
                                if last_command_positions:
                                    await robot.set_real_command_positions(
                                        last_command_positions
                                    )

                            async def control_sim() -> None:
                                if puppet is not None and last_command_positions:
                                    radian_command_positions: Dict[
                                        str, Union[int, Radian]
                                    ] = {
                                        joint: math.radians(value)
                                        for joint, value in last_command_positions.items()
                                    }
                                    await puppet.set_joint_angles(
                                        radian_command_positions
                                    )

                            # Only run control_sim if puppet is not None
                            tasks = [control_real()]
                            if puppet is not None:
                                tasks.append(control_sim())

                            await asyncio.gather(*tasks)
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
            # Save continuous recording if applicable
            if (
                planner_name == "record_skill"
                and hasattr(planner, "continuous_mode")
                and planner.continuous_mode
            ):
                logger.info("Saving continuous recording...")
                planner.save_and_exit()
        except Exception as e:
            logger.error(f"Error in real robot loop: {str(e)}", exc_info=True)
    else:
        try:
            while True:
                current_time = time.perf_counter()
                elapsed_time = current_time - start_time
                target_commands = hz * elapsed_time
                should_send = (
                    executed_commands + 1
                ) / target_commands >= 0.95  # Allow 5% margin

                # Skip processing if in command mode
                if in_command_mode:
                    await asyncio.sleep(0.1)
                    continue

                # Only get new commands at target_hz rate
                if command_counter % max(1, round(target_hz / hz)) == 0:
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
    parser.add_argument("--ip", default=None, help="Custom IP address of the robot.")
    parser.add_argument(
        "--robot",
        type=str,
        default="default",
        choices=[r.value for r in RobotType],
        help="Robot type to use (alum1, white, default)",
    )

    parser.add_argument(
        "--HZ", type=int, default=20, help="Frequency of the skill to play."
    )
    parser.add_argument(
        "--target_HZ",
        type=int,
        default=20,
        help="Target frequency of the skill to play.",
    )

    parser.add_argument("--planner", default="zmp", help="Name of the planner to use.")

    parser.add_argument(
        "--play_skill", default="pickup", help="Name of the skill to play."
    )
    parser.add_argument(
        "--record_skill",
        default=time.strftime("%Y%m%d_%H%M%S_skill"),
        help="Name of the skill to record. Prefix with 'continuous_' to enable continuous recording mode.",
    )

    args = parser.parse_args()

    # If record_skill is provided, automatically set planner to record_skill
    if args.record_skill and args.record_skill != time.strftime("%Y%m%d_%H%M%S_skill"):
        args.planner = "record_skill"

    # If play_skill is provided, automatically set planner to play_skill
    if args.play_skill and args.play_skill != "pickup":
        args.planner = "play_skill"

    # Determine IP address - prioritize explicit IP if provided, otherwise use robot type
    if args.real:
        if args.ip:
            ip_address = args.ip
            logger.info(f"Using custom IP address: {ip_address}")
        else:
            robot_type = RobotType(args.robot)
            ip_address = get_robot_ip(robot_type)
            logger.info(f"Using {robot_type.value} robot IP: {ip_address}")
    else:
        ip_address = None

    mjcf_name = "zbot-v2-fixed"

    robot = RobotInterface(ip=ip_address) if args.real else None
    puppet = MujocoPuppet(mjcf_name) if args.sim else None

    planner = get_planner(args.planner, args)
    logger.info("Running in real mode..." if args.real else "Running in sim mode...")

    try:
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
