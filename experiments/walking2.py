"""Interactive example script for walking in the KOS simulator."""

import os
import sys
import argparse
import asyncio
import logging
import time
import math
import colorlogging
import numpy as np
from pykos import KOS

# Add the parent directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utils import config  # Import dynamic config

logger = logging.getLogger(__name__)

ACTUATOR_MAPPING = {
    # Left arm
    "left_shoulder_yaw": 11,
    "left_shoulder_pitch": 12,
    "left_elbow": 13,
    "left_gripper": 14,
    # Right arm
    "right_shoulder_yaw": 21,
    "right_shoulder_pitch": 22,
    "right_elbow": 23,
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


class BipedController:
    """
    Simplified bipedal walking controller focused on forward/backward motion only.
    """

    def __init__(self, lateral_movement_enabled=False):  # Default to False now
        self.hip_pitch_offset = math.radians(15)

        # -----------
        # Gait params - Simplified for forward motion
        # -----------
        self.LEG_LENGTH = 180.0  # mm
        self.hip_forward_offset = 2.04
        self.nominal_leg_height = 175.0
        self.initial_leg_height = 175.0
        self.gait_phase = 0
        self.walking_enabled = True

        # -----------
        # Variables for stepping - Simplified for stability
        # -----------
        self.stance_foot_index = 0  # 0 or 1
        self.step_cycle_length = 8  # Slower steps for stability
        self.step_cycle_counter = 0
        self.max_foot_lift = 8  # Height of step
        self.double_support_fraction = 0.3
        self.current_foot_lift = 0.0

        self.forward_offset = [0.0, 0.0]
        self.accumulated_forward_offset = 0.0
        self.previous_stance_foot_offset = 0.0
        self.previous_swing_foot_offset = 0.0
        self.step_length = 10.0  # Conservative step length

        # The joint angle arrays - Only what we need for forward walking
        self.K0 = [0.0, 0.0]  # hip pitch
        self.H = [0.0, 0.0]  # knee
        self.A0 = [0.0, 0.0]  # ankle pitch

    def control_foot_position(self, x, y, h, side):
        """
        Simplified foot position control without lateral movement.
        Only considers forward/backward and up/down motion.
        """
        # Calculate distance in the sagittal plane only
        k = math.sqrt(x * x + h * h)
        k = min(k, self.LEG_LENGTH)

        # Calculate forward angle
        if abs(k) < 1e-8:
            alpha = 0.0
        else:
            alpha = math.asin(x / k)

        # Calculate leg bend
        cval = max(min(k / self.LEG_LENGTH, 1.0), -1.0)
        gamma = math.acos(cval)

        # Set joint angles for forward motion only
        self.K0[side] = gamma + alpha  # hip pitch
        self.H[side] = 2.0 * gamma + 0.3  # knee
        self.A0[side] = gamma - alpha + 0.3  # ankle pitch

    def update_gait(self):
        """
        Simplified gait update focusing only on forward motion.
        """
        if self.gait_phase == 0:
            # Initial standing phase
            if self.initial_leg_height > self.nominal_leg_height + 0.1:
                self.initial_leg_height -= 1.0
            else:
                self.gait_phase = 10

            # Keep both feet together
            self.control_foot_position(
                -self.hip_forward_offset, 0.0, self.initial_leg_height, 0
            )
            self.control_foot_position(
                -self.hip_forward_offset, 0.0, self.initial_leg_height, 1
            )

        elif self.gait_phase == 10:
            # Idle stance
            self.control_foot_position(
                -self.hip_forward_offset, 0.0, self.nominal_leg_height, 0
            )
            self.control_foot_position(
                -self.hip_forward_offset, 0.0, self.nominal_leg_height, 1
            )
            if self.walking_enabled:
                self.step_length = 20.0
                self.gait_phase = 20

        elif self.gait_phase in [20, 30]:
            half_cycle = self.step_cycle_length / 2.0

            # Update forward position
            if self.step_cycle_counter < half_cycle:
                fraction = self.step_cycle_counter / self.step_cycle_length
                self.forward_offset[self.stance_foot_index] = (
                    self.previous_stance_foot_offset * (1.0 - 2.0 * fraction)
                )
            else:
                fraction = 2.0 * self.step_cycle_counter / self.step_cycle_length - 1.0
                self.forward_offset[self.stance_foot_index] = (
                    -(self.step_length - self.accumulated_forward_offset) * fraction
                )

            # Handle swing foot
            if self.gait_phase == 20:
                if self.step_cycle_counter < (
                    self.double_support_fraction * self.step_cycle_length
                ):
                    self.forward_offset[self.stance_foot_index ^ 1] = (
                        self.previous_swing_foot_offset
                        - (
                            self.previous_stance_foot_offset
                            - self.forward_offset[self.stance_foot_index]
                        )
                    )
                else:
                    self.previous_swing_foot_offset = self.forward_offset[
                        self.stance_foot_index ^ 1
                    ]
                    self.gait_phase = 30

            if self.gait_phase == 30:
                start_swing = int(self.double_support_fraction * self.step_cycle_length)
                denom = (1.0 - self.double_support_fraction) * self.step_cycle_length
                if denom < 1e-8:
                    denom = 1.0
                frac = (
                    -math.cos(math.pi * (self.step_cycle_counter - start_swing) / denom)
                    + 1.0
                ) / 2.0
                self.forward_offset[self.stance_foot_index ^ 1] = (
                    self.previous_swing_foot_offset
                    + frac
                    * (
                        self.step_length
                        - self.accumulated_forward_offset
                        - self.previous_swing_foot_offset
                    )
                )

            # Calculate foot lift for swing phase
            i = int(self.double_support_fraction * self.step_cycle_length)
            if self.step_cycle_counter > i:
                self.current_foot_lift = self.max_foot_lift * math.sin(
                    math.pi
                    * (self.step_cycle_counter - i)
                    / (self.step_cycle_length - i)
                )
            else:
                self.current_foot_lift = 0.0

            # Position feet
            if self.stance_foot_index == 0:
                # left foot = stance
                self.control_foot_position(
                    self.forward_offset[0] - self.hip_forward_offset,
                    0.0,
                    self.nominal_leg_height,
                    0,
                )
                self.control_foot_position(
                    self.forward_offset[1] - self.hip_forward_offset,
                    0.0,
                    self.nominal_leg_height - self.current_foot_lift,
                    1,
                )
            else:
                # right foot = stance
                self.control_foot_position(
                    self.forward_offset[0] - self.hip_forward_offset,
                    0.0,
                    self.nominal_leg_height - self.current_foot_lift,
                    0,
                )
                self.control_foot_position(
                    self.forward_offset[1] - self.hip_forward_offset,
                    0.0,
                    self.nominal_leg_height,
                    1,
                )

            # Update cycle
            if self.step_cycle_counter >= self.step_cycle_length:
                self.stance_foot_index ^= 1
                self.step_cycle_counter = 1
                self.accumulated_forward_offset = 0.0
                self.previous_stance_foot_offset = self.forward_offset[
                    self.stance_foot_index
                ]
                self.previous_swing_foot_offset = self.forward_offset[
                    self.stance_foot_index ^ 1
                ]
                self.current_foot_lift = 0.0
                self.gait_phase = 20
            else:
                self.step_cycle_counter += 1

    def get_joint_angles(self):
        """
        Return joint angles, simplified for forward motion only.
        """
        angles = {}
        # Zero out yaw and roll joints
        angles["left_hip_yaw"] = 0.0
        angles["right_hip_yaw"] = 0.0
        angles["left_hip_roll"] = 0.0
        angles["right_hip_roll"] = 0.0

        # Set pitch joints for walking
        angles["left_hip_pitch"] = -self.K0[0] + -self.hip_pitch_offset
        angles["left_knee"] = self.H[0]
        angles["left_ankle"] = self.A0[0]

        angles["right_hip_pitch"] = self.K0[1] + self.hip_pitch_offset
        angles["right_knee"] = -self.H[1]
        angles["right_ankle"] = -self.A0[1]

        # Keep arms neutral
        angles["left_shoulder_yaw"] = 0.0
        angles["left_shoulder_pitch"] = 0.0
        angles["left_elbow"] = 0.0
        angles["left_gripper"] = 0.0

        angles["right_shoulder_yaw"] = 0.0
        angles["right_shoulder_pitch"] = 0.0
        angles["right_elbow"] = 0.0
        angles["right_gripper"] = 0.0

        return angles


async def run_walking(
    host: str = "localhost", port: int = 50051, no_lateral: bool = False
) -> None:
    """Run the walking controller in the simulator or on the real robot."""
    logger.info("Starting walking controller...")

    controller = BipedController(lateral_movement_enabled=not no_lateral)
    dt = 0.002  # Reduced from 1000Hz to 500Hz for simulation stability

    async with KOS(ip=host, port=port) as kos:
        # Only reset simulation if we're running in simulator mode
        is_simulator = host in ["localhost", "127.0.0.1"]
        if is_simulator:
            try:
                await kos.sim.reset()
            except Exception as e:
                logger.warning(f"Could not reset simulator: {e}")

        # Configure all actuators with adjusted gains
        for actuator_id in ACTUATOR_MAPPING.values():
            gains = {
                # Leg joints need higher gains
                31: (100, 10),  # left_hip_yaw
                32: (120, 12),  # left_hip_roll
                33: (150, 15),  # left_hip_pitch
                34: (150, 15),  # left_knee
                35: (100, 10),  # left_ankle
                41: (100, 10),  # right_hip_yaw
                42: (120, 12),  # right_hip_roll
                43: (150, 15),  # right_hip_pitch
                44: (150, 15),  # right_knee
                45: (100, 10),  # right_ankle
                # Arm joints can have lower gains
                11: (50, 5),  # left_shoulder_yaw
                12: (50, 5),  # left_shoulder_pitch
                13: (30, 3),  # left_elbow
                14: (20, 2),  # left_gripper
                21: (50, 5),  # right_shoulder_yaw
                22: (50, 5),  # right_shoulder_pitch
                23: (30, 3),  # right_elbow
                24: (20, 2),  # right_gripper
            }
            kp, kd = gains.get(actuator_id, (32, 32))
            try:
                await kos.actuator.configure_actuator(
                    actuator_id=actuator_id,
                    kp=kp,  # Position gain
                    kd=kd,  # Velocity gain
                    max_torque=100,  # Increased from 80 for better tracking
                    torque_enabled=True,
                )
            except Exception as e:
                logger.error(f"Failed to configure actuator {actuator_id}: {e}")
                raise

        # Start from a stable standing position
        initial_pose = [
            {"actuator_id": 33, "position": -10},  # left_hip_pitch - reduced from -15
            {"actuator_id": 34, "position": 15},  # left_knee - reduced from 30
            {"actuator_id": 35, "position": -5},  # left_ankle - reduced from -15
            {"actuator_id": 43, "position": 10},  # right_hip_pitch - reduced from 15
            {"actuator_id": 44, "position": -15},  # right_knee - reduced from -30
            {"actuator_id": 45, "position": 5},  # right_ankle - reduced from 15
        ]
        await kos.actuator.command_actuators(initial_pose)
        await asyncio.sleep(2)  # Give time to reach initial pose

        # Countdown before starting movement
        for i in range(5, 0, -1):
            logger.info(f"Starting in {i}...")
            await asyncio.sleep(1)

        commands_sent = 0
        start_time = time.time()

        try:
            while True:
                # Update the gait state machine
                controller.update_gait()

                # Get joint angles and convert to commands
                angles_dict = controller.get_joint_angles()
                commands = []
                for joint_name, angle_radians in angles_dict.items():
                    if joint_name in ACTUATOR_MAPPING:
                        actuator_id = ACTUATOR_MAPPING[joint_name]
                        angle_degrees = math.degrees(angle_radians)
                        if actuator_id == 32:  # Special case for left_hip_roll
                            angle_degrees = -angle_degrees
                        commands.append(
                            {"actuator_id": actuator_id, "position": angle_degrees}
                        )

                # Send commands to the robot
                if commands:
                    await kos.actuator.command_actuators(commands)

                # Track commands per second
                commands_sent += 1
                current_time = time.time()
                if current_time - start_time >= 1.0:
                    logger.info(f"Commands per second (CPS): {commands_sent}")
                    commands_sent = 0
                    start_time = current_time

                await asyncio.sleep(dt)

        except KeyboardInterrupt:
            logger.info("Walking controller stopped by user")
            return


async def main() -> None:
    """Main entry point for the walking simulation."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--host", type=str, default=config.robot_ip, help="Robot IP address"
    )
    parser.add_argument("--port", type=int, default=50051)
    parser.add_argument("--debug", action="store_true")
    parser.add_argument(
        "--no-lateral", action="store_true", help="Disable lateral movements"
    )
    args = parser.parse_args()

    colorlogging.configure(level=logging.DEBUG if args.debug else logging.INFO)
    await run_walking(host=args.host, port=args.port, no_lateral=args.no_lateral)


if __name__ == "__main__":
    asyncio.run(main())
