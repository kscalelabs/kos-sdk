#!/usr/bin/env python3
"""
Script to configure actuators with zero_position_equals_true.
This sets the current position of each actuator as the new zero position.
"""

import asyncio
import argparse
from loguru import logger
from robot import RobotInterface
from pykos import KOS


async def configure_zero_position_equals_true(ip: str):
    """Configure all actuators with zero_position_equals_true."""
    logger.info(f"Connecting to robot at {ip}...")

    try:
        # Connect directly to KOS for this operation
        async with KOS(ip=ip) as kos:
            from robot import JOINT_TO_ID

            logger.info("Configuring actuators with zero_position_equals_true...")
            for actuator_id in JOINT_TO_ID.values():
                logger.info(
                    f"Setting zero_position_equals_true for actuator {actuator_id}..."
                )
                try:
                    await kos.actuator.configure_actuator(
                        actuator_id=actuator_id,
                        zero_position=True,
                        kp=32,
                        kd=32,
                        max_torque=100,
                        torque_enabled=True,
                    )
                    logger.success(
                        f"Successfully set zero_position_equals_true for actuator {actuator_id}"
                    )
                except Exception as e:
                    logger.error(f"Failed to configure actuator {actuator_id}: {e}")

            logger.success("All actuators configured with zero_position_equals_true")

    except Exception as e:
        logger.error(f"Error: {e}")


async def main():
    parser = argparse.ArgumentParser(
        description="Configure actuators with zero_position_equals_true"
    )
    parser.add_argument("--ip", default="10.33.85.9", help="IP address of the robot")
    args = parser.parse_args()

    await configure_zero_position_equals_true(args.ip)


if __name__ == "__main__":
    asyncio.run(main())
