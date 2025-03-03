import argparse
import asyncio
import math
import time

from pykos import KOS
from ks_digital_twin.puppet.mujoco_puppet import MujocoPuppet


joint_to_actuator_id = {
    # Left arm
    "left_shoulder_yaw": 11,
    "left_shoulder_pitch": 12,
    "left_elbow_yaw": 13,
    "left_gripper": 14,
    # Right arm
    "right_shoulder_yaw": 21,
    "right_shoulder_pitch": 22,
    "right_elbow_yaw": 23,
    "right_gripper": 24,
    # Left leg
    "left_hip_yaw": 31,
    "left_hip_roll": 32,
    "left_hip_pitch": 33,
    "left_knee": 34,
    "left_ankle": 35,
    # Right leg
    "right_hip_yaw": 41,
    "right_hip_roll": 42,
    "right_hip_pitch": 43,
    "right_knee": 44,
    "right_ankle": 45,
}


def get_zero_angles():
    """Return a dictionary with all joint angles set to zero"""
    angles = {}
    for joint_name in joint_to_actuator_id.keys():
        angles[joint_name] = 0.0
    return angles


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mjcf_name",
        type=str,
        default="zbot-v2",
        help="Name of the Mujoco model in the K-Scale API.",
    )
    args = parser.parse_args()

    print("Starting MuJoCo visualization...")
    puppet = MujocoPuppet(args.mjcf_name)

    try:
        while True:
            # Get zero angles and update puppet
            angles_dict = get_zero_angles()
            await puppet.set_joint_angles(angles_dict)
            await asyncio.sleep(0.01)  # Small sleep to not overwhelm the system

    except KeyboardInterrupt:
        print("\nShutting down visualization gracefully.")


if __name__ == "__main__":
    asyncio.run(main())
