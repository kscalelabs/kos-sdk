"""Runs reinforcement learning unit tests.

To see a video of the policy running in simulation, look in
`assets/model_checkpoints/zbot_rl_policy/policy.mp4`.

To see the input actuator positions and output policy actions for each timestep,
uncomment the `logger.setLevel(logging.DEBUG)` line.
"""

import asyncio
import logging
import math
import os
import time
from typing import cast

import colorlogging
import numpy as np
import onnxruntime as ort
import pykos
from numpy.typing import NDArray

logger = logging.getLogger(__name__)


# Constants for actuator IDs and policy indices
ACTUATOR_IDS = [11, 12, 13, 14, 21, 22, 23, 24, 31, 32, 33, 34, 35, 41, 42, 43, 44, 45]

ACTUATOR_ID_TO_NAME = {
    11: "left_shoulder_yaw",
    12: "left_shoulder_pitch",
    13: "left_elbow",
    14: "left_gripper",
    21: "right_shoulder_yaw",
    22: "right_shoulder_pitch",
    23: "right_elbow",
    24: "right_gripper",
    31: "left_hip_yaw",
    32: "left_hip_roll",
    33: "left_hip_pitch",
    34: "left_knee",
    35: "left_ankle",
    41: "right_hip_yaw",
    42: "right_hip_roll",
    43: "right_hip_pitch",
    44: "right_knee",
    45: "right_ankle",
}

# Policy input constants
COMMAND_VELOCITY = np.array([-0.5, 0.0, 0.0], dtype=np.float32)
PROJECTED_GRAVITY = np.array([0.0, 0.0, -1.0], dtype=np.float32)

# Map actuator IDs to policy indices (just enumerate them in order)
ACTUATOR_ID_TO_POLICY_IDX = {
    11: 0,  # left_shoulder_yaw
    12: 1,  # left_shoulder_pitch
    13: 2,  # left_elbow
    14: 3,  # left_gripper
    21: 4,  # right_shoulder_yaw
    22: 5,  # right_shoulder_pitch
    23: 6,  # right_elbow
    24: 7,  # right_gripper
    31: 8,  # left_hip_yaw
    32: 9,  # left_hip_roll
    33: 10,  # left_hip_pitch
    34: 11,  # left_knee
    35: 12,  # left_ankle
    41: 13,  # right_hip_yaw
    42: 14,  # right_hip_roll
    43: 15,  # right_hip_pitch
    44: 16,  # right_knee
    45: 17,  # right_ankle
}


def load_policy(checkpoint_dir: str) -> ort.InferenceSession:
    """Load ONNX policy from checkpoint directory."""
    policy_files = [f for f in os.listdir(checkpoint_dir) if f.endswith(".onnx")]
    if not policy_files:
        raise FileNotFoundError(f"Could not find .onnx file in {checkpoint_dir}")
    policy_file = policy_files[0]
    policy_path = os.path.join(checkpoint_dir, policy_file)
    logger.info("Loading policy from: %s", os.path.abspath(policy_path))
    return ort.InferenceSession(policy_path)


def create_policy_input(
    positions: dict[int, float], 
    prev_actions: np.ndarray
) -> NDArray[np.float32]:
    """Create observation vector for policy from current state."""
    joint_angles = np.zeros(18, dtype=np.float32)

    for actuator_id, policy_idx in ACTUATOR_ID_TO_POLICY_IDX.items():
        joint_angles[policy_idx] = positions.get(actuator_id, 0.0)

    joint_velocities = np.zeros(18, dtype=np.float32)

    obs = np.concatenate(
        [
            COMMAND_VELOCITY,
            PROJECTED_GRAVITY,
            joint_angles,
            joint_velocities,
            prev_actions,
        ],
    ).astype(np.float32)

    return cast(NDArray[np.float32], obs.astype(np.float32))


def print_state_and_actions(
    count: int,
    positions: dict[int, float],
    actions: np.ndarray,
) -> None:
    """Print current joint positions and policy actions."""
    logger.debug("=== Current State and Actions ===")

    # Find the longest name for alignment
    max_name_length = max(len(name) for name in ACTUATOR_ID_TO_NAME.values())

    for actuator_id in ACTUATOR_IDS:
        pos_deg = math.degrees(positions.get(actuator_id, 0.0))
        policy_idx = ACTUATOR_ID_TO_POLICY_IDX[actuator_id]
        action = actions[policy_idx]
        logger.debug(
            "timestep %4d: %s: pos=%6.2f deg, action=%6.3f rad",
            count,
            f"{ACTUATOR_ID_TO_NAME[actuator_id]:<{max_name_length}}",
            pos_deg,
            action,
        )


async def main() -> None:
    colorlogging.configure()
    logger.warning("Starting test-02")
    try:
        async with pykos.KOS("192.168.42.1") as kos:
            await reinforcement_learning_test(kos)
    except Exception:
        logger.exception("Ensure the Z-Bot is connected over USB and the IP address is accessible.")
        raise


async def reinforcement_learning_test(kos: pykos.KOS) -> None:
    """Runs reinforcement learning unit tests."""
    # Load policy
    policy_dir = "assets/models/ppo"
    session = load_policy(policy_dir)
    input_name = session.get_inputs()[0].name

    # Initialize previous actions
    prev_actions = np.zeros(18, dtype=np.float32)

    # Performance tracking variables
    count = 0
    start_time = time.time()
    end_time = start_time + 10  # Run for 10 seconds like test_00

    last_second = int(time.time())
    second_count = 0

    while time.time() < end_time:
        # Get robot state and run inference
        response = await kos.actuator.get_actuators_state(ACTUATOR_IDS)
        positions = {state.actuator_id: math.radians(state.position) for state in response.states}

        # Create policy input and run inference
        obs = create_policy_input(positions, prev_actions)
        actions = session.run(None, {input_name: obs.reshape(1, -1)})[0][0]

        # Store actions for next iteration
        prev_actions = actions.copy()

        # Scale actions by 0.5
        actions *= 0.5

        # Print detailed state and actions (in debug level)
        print_state_and_actions(count, positions, actions)

        # Update performance counters
        count += 1
        second_count += 1

        # Log performance each second
        current_second = int(time.time())
        if current_second != last_second:
            logger.info(
                "Time: %.2f seconds - Inference calls this second: %d",
                current_second - start_time,
                second_count,
            )
            second_count = 0
            last_second = current_second

        # Small sleep to prevent overwhelming the system
        await asyncio.sleep(0.001)

    # Print final statistics
    elapsed_time = time.time() - start_time
    logger.info("Total inference calls: %d", count)
    logger.info("Elapsed time: %.2f seconds", elapsed_time)
    logger.info("Average inference calls per second: %.2f", count / elapsed_time)
    logger.info("\nPolicy test completed successfully")


if __name__ == "__main__":
    asyncio.run(main())
