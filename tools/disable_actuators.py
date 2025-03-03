#!/usr/bin/env python3
"""
Script to disable torque for all actuators.
This will make the robot go limp and allow for manual positioning.
"""

import asyncio
import argparse
from loguru import logger
from robot import RobotInterface


async def disable_actuators(ip: str):
    """Disable torque for all actuators."""
    logger.info(f"Connecting to robot at {ip}...")
    robot = RobotInterface(ip=ip)

    try:
        async with robot:
            logger.info("Disabling torque for all actuators...")
            await robot.disable_all_torque()
            logger.success("All actuators have been disabled - robot is now limp")

    except Exception as e:
        logger.error(f"Error: {e}")


async def main():
    parser = argparse.ArgumentParser(description="Disable torque for all actuators")
    parser.add_argument("--ip", default="10.33.85.9", help="IP address of the robot")
    args = parser.parse_args()

    await disable_actuators(args.ip)


if __name__ == "__main__":
    asyncio.run(main())
