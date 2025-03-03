#!/usr/bin/env python3
"""
Script to enable torque for all actuators.
This will make the robot hold its position and respond to commands.
"""

import asyncio
import argparse
from loguru import logger
from robot import RobotInterface


async def enable_actuators(ip: str):
    """Enable torque for all actuators."""
    logger.info(f"Connecting to robot at {ip}...")
    robot = RobotInterface(ip=ip)

    try:
        async with robot:
            logger.info("Enabling torque for all actuators...")
            await robot.enable_all_torque()
            logger.success(
                "All actuators have been enabled - robot will now hold position"
            )

    except Exception as e:
        logger.error(f"Error: {e}")


async def main():
    parser = argparse.ArgumentParser(description="Enable torque for all actuators")
    parser.add_argument("--ip", default="10.33.85.9", help="IP address of the robot")
    args = parser.parse_args()

    await enable_actuators(args.ip)


if __name__ == "__main__":
    asyncio.run(main())
