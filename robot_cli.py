import click
import asyncio
from robot import RobotInterface, JOINT_TO_ID, ARM_JOINTS, LEG_JOINTS
from functools import partial, wraps
from utils import ROBOT_IP


async def _run_robot_cmd(ip: str, coro_func, success_msg: str):
    """Helper to run a robot command with standard connection handling"""
    async with RobotInterface(ip=ip) as robot:
        await coro_func(robot)
        click.echo(success_msg)


def common_options(f):
    """Common options for all commands"""
    f = click.option("--ip", default=ROBOT_IP, help="Robot IP address")(f)
    return f


@click.group()
def cli():
    """Command line interface for robot control"""
    pass


def handle_joints_argument(joints):
    """Common handling for joint name validation"""
    if not joints:
        click.echo("Please specify at least one joint name")
        click.echo("Available joints:")
        for joint in JOINT_TO_ID.keys():
            click.echo(f"  {joint}")
        return None

    invalid_joints = [j for j in joints if j not in JOINT_TO_ID]
    if invalid_joints:
        click.echo(f"Invalid joint names: {', '.join(invalid_joints)}")
        return None

    return list(joints)


# Disable commands
@cli.group()
def disable():
    """Commands for disabling torque"""
    pass


@disable.command(name="all")
@common_options
def disable_all(ip):
    """Disable torque on all joints"""
    asyncio.run(
        _run_robot_cmd(ip, lambda r: r.disable_all_torque(), "All torque disabled")
    )


@disable.command(name="arms")
@common_options
def disable_arms(ip):
    """Disable torque on arm joints only"""
    asyncio.run(
        _run_robot_cmd(ip, lambda r: r.disable_arms_torque(), "Arms torque disabled")
    )


@disable.command(name="legs")
@common_options
def disable_legs(ip):
    """Disable torque on leg joints only"""
    asyncio.run(
        _run_robot_cmd(ip, lambda r: r.disable_legs_torque(), "Legs torque disabled")
    )


@disable.command(name="joints")
@common_options
@click.argument("joints", nargs=-1)
def disable_joints(ip, joints):
    """Disable torque on specific joints

    Example: python robot_cli.py disable joints left_elbow right_elbow

    Available joints:
    Arms: left_shoulder_yaw, left_shoulder_pitch, left_elbow, left_gripper,
         right_shoulder_yaw, right_shoulder_pitch, right_elbow, right_gripper

    Legs: left_hip_yaw, left_hip_roll, left_hip_pitch, left_knee, left_ankle,
         right_hip_yaw, right_hip_roll, right_hip_pitch, right_knee, right_ankle
    """
    joint_list = handle_joints_argument(joints)
    if joint_list is None:
        return

    asyncio.run(
        _run_robot_cmd(
            ip,
            lambda r: r.disable_torque(joint_list),
            f"Disabled torque for joints: {', '.join(joint_list)}",
        )
    )


# Enable commands
@cli.group()
def enable():
    """Commands for enabling torque"""
    pass


@enable.command(name="all")
@common_options
def enable_all(ip):
    """Enable torque on all joints"""
    asyncio.run(
        _run_robot_cmd(ip, lambda r: r.enable_all_torque(), "All torque enabled")
    )


@enable.command(name="arms")
@common_options
def enable_arms(ip):
    """Enable torque on arm joints only"""
    asyncio.run(
        _run_robot_cmd(ip, lambda r: r.enable_arms_torque(), "Arms torque enabled")
    )


@enable.command(name="legs")
@common_options
def enable_legs(ip):
    """Enable torque on leg joints only"""
    asyncio.run(
        _run_robot_cmd(ip, lambda r: r.enable_legs_torque(), "Legs torque enabled")
    )


@enable.command(name="joints")
@common_options
@click.argument("joints", nargs=-1)
def enable_joints(ip, joints):
    """Enable torque on specific joints"""
    joint_list = handle_joints_argument(joints)
    if joint_list is None:
        return

    asyncio.run(
        _run_robot_cmd(
            ip,
            lambda r: r.enable_torque(joint_list),
            f"Enabled torque for joints: {', '.join(joint_list)}",
        )
    )


# Zero commands
@cli.group()
def zero():
    """Commands for zeroing joints"""
    pass


@zero.command(name="all")
@common_options
def zero_all(ip):
    """Zero all joints"""
    asyncio.run(
        _run_robot_cmd(ip, lambda r: r.zero_all_actuators(), "All joints zeroed")
    )


@zero.command(name="arms")
@common_options
def zero_arms(ip):
    """Zero arm joints only"""
    asyncio.run(_run_robot_cmd(ip, lambda r: r.zero_arms(), "Arms zeroed"))


@zero.command(name="legs")
@common_options
def zero_legs(ip):
    """Zero leg joints only"""
    asyncio.run(_run_robot_cmd(ip, lambda r: r.zero_legs(), "Legs zeroed"))


@zero.command(name="joints")
@common_options
@click.argument("joints", nargs=-1)
def zero_joints(ip, joints):
    """Zero specific joints"""
    joint_list = handle_joints_argument(joints)
    if joint_list is None:
        return

    asyncio.run(
        _run_robot_cmd(
            ip,
            lambda r: r.zero_actuators(joint_list),
            f"Zeroed joints: {', '.join(joint_list)}",
        )
    )


if __name__ == "__main__":
    cli()
