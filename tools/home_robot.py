#!/usr/bin/env python3
"""
Script to home the robot actuators and optionally disable torque.
"""

import asyncio
import argparse
from loguru import logger
from robot import RobotInterface


async def main():
    parser = argparse.ArgumentParser(
        description="Home robot actuators and optionally disable torque"
    )
    parser.add_argument("--ip", default="192.168.42.1", help="IP address of the robot")
    parser.add_argument(
        "--disable-torque", action="store_true", help="Disable torque after homing"
    )
    parser.add_argument(
        "--wait", type=float, default=3.0, help="Wait time after homing (seconds)"
    )
    args = parser.parse_args()

    logger.info(f"Connecting to robot at {args.ip}...")
    robot = RobotInterface(ip=args.ip)

    try:
        async with robot:
            # First ensure torque is enabled
            logger.info("Enabling torque for all actuators...")
            await robot.enable_all_torque()
            logger.success("Torque enabled for all actuators")

            # Give a moment for torque to take effect
            await asyncio.sleep(0.5)

            # Home all actuators
            logger.info("Homing all actuators to position zero...")
            await robot.homing_actuators()

            # Wait for actuators to reach position
            logger.info(
                f"Waiting {args.wait} seconds for actuators to reach zero position..."
            )
            await asyncio.sleep(args.wait)

            # Optionally disable torque
            if args.disable_torque:
                logger.info("Disabling torque for all actuators...")
                await robot.disable_all_torque()
                logger.success("Torque disabled for all actuators")
            else:
                logger.info("Torque remains enabled. Robot will maintain position.")

            logger.success("Robot homing completed successfully")

    except Exception as e:
        logger.error(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
