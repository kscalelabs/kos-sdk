#!/usr/bin/env python3
"""
Basic example of using the motion library.
"""
import asyncio
from pykos import KOS
from kos_sdk.motion import Robot


async def main():
    # Define joint groups (optional)
    groups = {
        "left_arm": ["left_shoulder_yaw", "left_shoulder_pitch", "left_elbow"],
        "right_arm": ["right_shoulder_yaw", "right_shoulder_pitch", "right_elbow"],
        "grippers": ["left_gripper", "right_gripper"],
        "legs": [
            "left_hip_yaw",
            "left_hip_roll",
            "left_hip_pitch",
            "left_knee",
            "left_ankle",
            "right_hip_yaw",
            "right_hip_roll",
            "right_hip_pitch",
            "right_knee",
            "right_ankle",
        ],
    }

    # Create robot instance with default joint mapping
    robot = Robot(groups=groups)

    # Connect to KOS
    async with KOS(ip="localhost", port=50051) as kos:
        # Configure robot for simulator
        await robot.configure(kos, is_real=False)

        # Move joints
        await robot.move(kos, {"left_shoulder_yaw": 45, "left_elbow": -30})

        # Get joint states
        states = await robot.get_states(kos)
        for name, state in states.items():
            print(f"{name}: pos={state.position:.2f}, vel={state.velocity:.2f}")

        # Work with a specific group
        left_arm = robot.get_group("left_arm")
        if left_arm:
            print(f"Left arm has {len(left_arm)} joints")

        # Zero all joints
        await robot.zero_all(kos)


if __name__ == "__main__":
    asyncio.run(main())
