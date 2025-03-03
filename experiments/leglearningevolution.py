import asyncio
import subprocess
import time
import argparse
import math
from pykos import KOS
from typing import List, Dict
import numpy as np

# Joint IDs for both legs
LEG_JOINT_IDS = {
    # Left leg
    "hip_pitch": 33,
    "knee": 34,
    "ankle": 35,
    "hip_roll": 32,
    # Right leg
    "right_hip_pitch": 43,
    "right_knee": 44,
    "right_ankle": 45,
    "right_hip_roll": 42,
}

# Known working positions from your code
WORKING_POSITIONS = {
    "standing": {
        "left": {"hip_pitch": -20, "knee": 10, "ankle": -5, "hip_roll": 0},
        "right": {"hip_pitch": -20, "knee": 10, "ankle": 0, "hip_roll": 0},
    },
    "left_step_forward": {
        "left": {"hip_pitch": -30, "knee": 16, "ankle": -13, "hip_roll": 5},
        "right": {"hip_pitch": -20, "knee": 10, "ankle": -5, "hip_roll": 0},
    },
    "left_foot_down": {
        "left": {"hip_pitch": -20, "knee": 16, "ankle": -10, "hip_roll": -5},
        "right": {"hip_pitch": -20, "knee": 10, "ankle": -5, "hip_roll": 0},
    },
    "right_step_ready": {
        "left": {"hip_pitch": -12, "knee": 8, "ankle": -2, "hip_roll": 0},
        "right": {"hip_pitch": -12, "knee": 8, "ankle": -2, "hip_roll": 0},
    },
    "right_step_forward": {
        "left": {"hip_pitch": -12, "knee": 9, "ankle": -1, "hip_roll": 0},
        "right": {"hip_pitch": 20, "knee": -10, "ankle": 3, "hip_roll": -3},
    },
}


def interpolate_positions(start_pos: Dict, end_pos: Dict, t: float) -> Dict:
    """
    Interpolate between two positions with value t between 0 and 1
    Ensures we stay within safe ranges by using linear interpolation
    """
    result = {}
    for joint in start_pos:
        start_val = start_pos[joint]
        end_val = end_pos[joint]
        result[joint] = start_val + (end_val - start_val) * t
    return result


def generate_trajectory(
    start_pos: Dict, end_pos: Dict, num_points: int = 10
) -> List[Dict]:
    """
    Generate a trajectory between two positions while staying within safe ranges
    """
    trajectory = []
    for i in range(num_points):
        t = i / (num_points - 1)
        pos = interpolate_positions(start_pos, end_pos, t)
        trajectory.append(pos)
    return trajectory


async def execute_position(kos: KOS, left_pos: Dict, right_pos: Dict):
    """Execute a single position for both legs"""
    commands = [
        # Left leg
        {"actuator_id": LEG_JOINT_IDS["hip_pitch"], "position": left_pos["hip_pitch"]},
        {"actuator_id": LEG_JOINT_IDS["knee"], "position": left_pos["knee"]},
        {"actuator_id": LEG_JOINT_IDS["ankle"], "position": left_pos["ankle"]},
        {"actuator_id": LEG_JOINT_IDS["hip_roll"], "position": left_pos["hip_roll"]},
        # Right leg
        {
            "actuator_id": LEG_JOINT_IDS["right_hip_pitch"],
            "position": right_pos["hip_pitch"],
        },
        {"actuator_id": LEG_JOINT_IDS["right_knee"], "position": right_pos["knee"]},
        {"actuator_id": LEG_JOINT_IDS["right_ankle"], "position": right_pos["ankle"]},
        {
            "actuator_id": LEG_JOINT_IDS["right_hip_roll"],
            "position": right_pos["hip_roll"],
        },
    ]
    await kos.actuator.command_actuators(commands)


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sim", action="store_true", help="Run in simulation mode")
    parser.add_argument("--ip", default="10.33.12.76", help="Robot IP address")
    args = parser.parse_args()

    sim_process = None
    if args.sim:
        print("Starting simulator...")
        sim_process = subprocess.Popen(["kos-sim", "zbot-v2-fixed", "--no-gravity"])
        time.sleep(2)
        ip = "localhost"
    else:
        ip = args.ip

    try:
        async with KOS(ip=ip, port=50051) as kos:
            if args.sim:
                await kos.sim.reset()

            # Configure the joints
            for joint_id in LEG_JOINT_IDS.values():
                print(f"Configuring joint {joint_id}...")
                await kos.actuator.configure_actuator(
                    actuator_id=joint_id,
                    kp=150,
                    kd=15,
                    max_torque=100,
                    torque_enabled=True,
                )

            # Execute a walking sequence using interpolation between known good positions
            print("\nStarting walking sequence...")

            # Start with standing position
            print("Moving to standing position...")
            await execute_position(
                kos,
                WORKING_POSITIONS["standing"]["left"],
                WORKING_POSITIONS["standing"]["right"],
            )
            await asyncio.sleep(1)

            # Generate and execute trajectory for left step
            print("Executing left step...")
            left_step_trajectory = generate_trajectory(
                WORKING_POSITIONS["standing"]["left"],
                WORKING_POSITIONS["left_step_forward"]["left"],
            )

            for pos in left_step_trajectory:
                await execute_position(kos, pos, WORKING_POSITIONS["standing"]["right"])
                await asyncio.sleep(0.1)

            # Bring left foot down
            print("Bringing left foot down...")
            down_trajectory = generate_trajectory(
                WORKING_POSITIONS["left_step_forward"]["left"],
                WORKING_POSITIONS["left_foot_down"]["left"],
            )

            for pos in down_trajectory:
                await execute_position(kos, pos, WORKING_POSITIONS["standing"]["right"])
                await asyncio.sleep(0.1)

            # Prepare for right step
            print("Preparing for right step...")
            right_prep_trajectory = generate_trajectory(
                WORKING_POSITIONS["left_foot_down"]["left"],
                WORKING_POSITIONS["right_step_ready"]["left"],
            )

            for pos in right_prep_trajectory:
                await execute_position(
                    kos, pos, WORKING_POSITIONS["right_step_ready"]["right"]
                )
                await asyncio.sleep(0.1)

            # Execute right step
            print("Executing right step...")
            right_step_trajectory = generate_trajectory(
                WORKING_POSITIONS["right_step_ready"]["right"],
                WORKING_POSITIONS["right_step_forward"]["right"],
            )

            for pos in right_step_trajectory:
                await execute_position(
                    kos, WORKING_POSITIONS["right_step_forward"]["left"], pos
                )
                await asyncio.sleep(0.1)

    finally:
        if sim_process:
            print("Stopping simulator...")
            sim_process.terminate()
            sim_process.wait()


if __name__ == "__main__":
    asyncio.run(main())
