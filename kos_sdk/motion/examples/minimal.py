#!/usr/bin/env python3
"""
Minimal example of using the motion library.
"""
import asyncio
from pykos import KOS
from kos_sdk.motion import Robot


async def main():
    # Create a robot with default joint mapping
    robot = Robot()

    # Connect to KOS
    async with KOS() as kos:
        # Configure robot
        await robot.configure(kos, is_real=False)

        # Move left shoulder to position 45 degrees
        await robot.move(kos, {"left_shoulder_yaw": 45})

        # Get joint states
        states = await robot.get_states(kos)
        print(f"Left shoulder position: {states['left_shoulder_yaw'].position}")

        # Zero all joints
        await robot.zero_all(kos)


if __name__ == "__main__":
    asyncio.run(main())
