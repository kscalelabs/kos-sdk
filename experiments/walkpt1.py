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

# Add the parent directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from robot import RobotInterface
from ks_digital_twin.puppet.mujoco_puppet import MujocoPuppet
from utils import config  # Import dynamic config

# Configure logging
logging.basicConfig(level=logging.INFO)
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

    def __init__(self, lateral_movement_enabled=False):
        # Keep core parameters
        self.LEG_LENGTH = 180.0  # mm
        self.hip_forward_offset = 1.0  # Reduced from 2.04 to bring feet more under body
        self.nominal_leg_height = 170.0
        self.initial_leg_height = 175.0  # Slightly higher initial stance
        self.gait_phase = 0
        self.walking_enabled = True

        # Walking parameters
        self.stance_foot_index = 0  # 0=left foot is stance, 1=right foot is stance
        self.step_cycle_length = 20
        self.step_cycle_counter = 0
        self.max_foot_lift = 2  # Height of step in mm
        self.double_support_fraction = 0.4
        self.current_foot_lift = 0.0

        # Position tracking
        self.forward_offset = [0.0, 0.0]  # [left_foot, right_foot]
        self.accumulated_forward_offset = 0.0
        self.previous_stance_foot_offset = 0.0
        self.previous_swing_foot_offset = 0.0
        self.step_length = 10.0  # mm

        # Add lateral movement parameters
        self.lateral_enabled = lateral_movement_enabled
        self.lateral_foot_shift = (
            6 if lateral_movement_enabled else 0
        )  # mm - reduced from 12mm to 6mm
        self.base_stance_width = 2.0  # mm
        self.lateral_offset = 0.0

        # Joint angles for each leg [left, right]
        self.K0 = [0.0, 0.0]  # hip pitch
        self.K1 = [0.0, 0.0]  # hip roll - added for lateral movement
        self.H = [0.0, 0.0]  # knee
        self.A0 = [0.0, 0.0]  # ankle pitch

        self.hip_pitch_offset = math.radians(30)  # Reduced back to 15 degrees
        self.roll_offset = math.radians(0)  # Added for hip roll control

    def control_foot_position(self, x, y, h, side):
        """
        Control foot position with minimal ankle pitch for flat foot position.
        Now includes hip roll control for lateral movement.
        """
        # Calculate distance in the sagittal plane only
        k = math.sqrt(x * x + (y * y + h * h))
        k = min(k, self.LEG_LENGTH)

        # Calculate forward angle
        if abs(k) < 1e-8:
            alpha = 0.0
        else:
            alpha = math.asin(x / k)

        # Calculate leg bend
        cval = max(min(k / self.LEG_LENGTH, 1.0), -1.0)
        gamma = math.acos(cval)

        # Set joint angles for forward motion
        self.K0[side] = gamma + alpha  # hip pitch
        self.H[side] = (
            1.2 * gamma + 0.2
        )  # Moderate knee bend throughout (reduced from 2.0 * gamma + 0.3)

        # Add hip roll calculation
        hip_roll = math.atan2(y, h) if abs(h) >= 1e-8 else 0.0
        self.K1[side] = hip_roll + self.roll_offset

        # Minimal ankle pitch offset for nearly flat foot
        ankle_offset = -0.1  # About 2.9 degrees - very small offset
        self.A0[side] = gamma - alpha + ankle_offset

    def update_gait(self):
        """Update the walking state machine"""
        if self.gait_phase == 0:
            if self.initial_leg_height > self.nominal_leg_height + 0.1:
                self.initial_leg_height -= 1.0
            else:
                self.gait_phase = 10

            # Initial stance with base width
            self.control_foot_position(
                -self.hip_forward_offset,
                -self.base_stance_width,
                self.initial_leg_height,
                0,
            )
            self.control_foot_position(
                -self.hip_forward_offset,
                self.base_stance_width,
                self.initial_leg_height,
                1,
            )

        elif self.gait_phase == 10:
            # Ready stance with base width
            self.control_foot_position(
                -self.hip_forward_offset,
                -self.base_stance_width,
                self.nominal_leg_height,
                0,
            )
            self.control_foot_position(
                -self.hip_forward_offset,
                self.base_stance_width,
                self.nominal_leg_height,
                1,
            )

            if self.walking_enabled:
                self.gait_phase = 20

        elif self.gait_phase in [20, 30]:
            # Reset hip roll values to prevent cumulative error.
            self.K1 = [0.0, 0.0]

            half_cycle = self.step_cycle_length / 2.0

            # Add lateral movement during walking
            if self.lateral_enabled:
                sin_value = math.sin(
                    math.pi * self.step_cycle_counter / self.step_cycle_length
                )
                lateral_shift = self.lateral_foot_shift * sin_value
                self.lateral_offset = (
                    lateral_shift if self.stance_foot_index == 0 else -lateral_shift
                )

                # Add extra hip roll during the single support phase.
                if self.step_cycle_counter > (
                    self.double_support_fraction * self.step_cycle_length
                ):
                    swing_factor = math.sin(
                        math.pi
                        * (
                            self.step_cycle_counter
                            - self.double_support_fraction * self.step_cycle_length
                        )
                        / (self.step_cycle_length * (1 - self.double_support_fraction))
                    )
                    # Only add positive swing adjustments.
                    if self.stance_foot_index == 0:
                        self.K1[1] += math.radians(5) * max(swing_factor, 0)
                    else:
                        self.K1[0] += math.radians(10) * max(swing_factor, 0)

                # Clamp hip roll values so they never drop below 0.
                self.K1[0] = max(self.K1[0], 0)
                self.K1[1] = max(self.K1[1], 0)
            else:
                self.lateral_offset = 0.0

            # Update forward positions
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

            # Calculate foot lift height
            i = int(self.double_support_fraction * self.step_cycle_length)
            if self.step_cycle_counter > i:
                self.current_foot_lift = self.max_foot_lift * math.sin(
                    math.pi
                    * (self.step_cycle_counter - i)
                    / (self.step_cycle_length - i)
                )
            else:
                self.current_foot_lift = 0.0

            # Position feet with lateral offset
            if self.stance_foot_index == 0:
                left_lateral = -self.base_stance_width - abs(self.lateral_offset)
                right_lateral = self.base_stance_width + abs(self.lateral_offset)
                self.control_foot_position(
                    self.forward_offset[0] - self.hip_forward_offset,
                    left_lateral,
                    self.nominal_leg_height,
                    0,
                )
                self.control_foot_position(
                    self.forward_offset[1] - self.hip_forward_offset,
                    right_lateral,
                    self.nominal_leg_height - self.current_foot_lift,
                    1,
                )
            else:
                left_lateral = -self.base_stance_width - abs(self.lateral_offset)
                right_lateral = self.base_stance_width + abs(self.lateral_offset)
                self.control_foot_position(
                    self.forward_offset[0] - self.hip_forward_offset,
                    left_lateral,
                    self.nominal_leg_height - self.current_foot_lift,
                    0,
                )
                self.control_foot_position(
                    self.forward_offset[1] - self.hip_forward_offset,
                    right_lateral,
                    self.nominal_leg_height,
                    1,
                )

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
        Return a dictionary with all the joint angles in radians.
        Now includes hip roll angles.
        """
        angles = {}
        angles["left_hip_yaw"] = 0.0
        angles["right_hip_yaw"] = 0.0

        angles["left_hip_roll"] = -self.K1[0]  # Added hip roll control
        angles["left_hip_pitch"] = -self.K0[0] - self.hip_pitch_offset  # Fixed sign
        angles["left_knee"] = self.H[0]
        angles["left_ankle"] = self.A0[0]

        angles["right_hip_roll"] = self.K1[1]  # Added hip roll control
        angles["right_hip_pitch"] = self.K0[1] + self.hip_pitch_offset
        angles["right_knee"] = -self.H[1]
        angles["right_ankle"] = -self.A0[1]

        # Arms & others as placeholders:
        angles["left_shoulder_yaw"] = 0.0
        angles["left_shoulder_pitch"] = 0.0
        angles["left_elbow"] = 0.0
        angles["left_gripper"] = 0.0

        angles["right_shoulder_yaw"] = 0.0
        angles["right_shoulder_pitch"] = 0.0
        angles["right_elbow"] = 0.0
        angles["right_gripper"] = 0.0

        return angles


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--ip",
        type=str,
        default=config.robot_ip,  # Use config default
        help=f"IP for the KOS device, default={config.robot_ip}",
    )
    parser.add_argument(
        "--mjcf_name",
        type=str,
        default="zbot-v2",
        help="Name of the Mujoco model in the K-Scale API (optional).",
    )
    parser.add_argument(
        "--no-pykos",
        action="store_true",
        help="Disable sending commands to PyKOS (simulation-only mode).",
    )
    parser.add_argument(
        "--no-lateral", action="store_true", help="Disable lateral movements."
    )
    args = parser.parse_args()

    logger.info(f"Connecting to robot at {args.ip}")

    # Create our biped controller with lateral movements disabled if --no-lateral is used
    controller = BipedController(lateral_movement_enabled=not args.no_lateral)

    # If --mjcf_name is provided, set up a MujocoPuppet
    puppet = None
    if args.mjcf_name:
        puppet = MujocoPuppet(args.mjcf_name)

    dt = 0.02  # Increased from 0.001 to reduce command frequency

    if not args.no_pykos:
        # Use RobotInterface instead of direct PyKOS
        robot = RobotInterface(ip=args.ip)
        async with robot:
            try:
                # Enable torque for all actuators with higher gains for legs
                logger.info("Enabling torque for all actuators...")
                await robot.enable_all_torque()

                # Verify torque is enabled by checking positions
                logger.info("Verifying initial positions...")
                initial_positions = await robot.get_feedback_positions()
                logger.info(f"Initial positions: {initial_positions}")

                # Initialize to home position
                logger.info("Moving to home position...")
                await robot.homing_actuators()
                await asyncio.sleep(2.0)  # Give time to reach position

                # Countdown before starting movement
                for i in range(5, 0, -1):
                    logger.info(f"Starting in {i}...")
                    await asyncio.sleep(1)

                # Counters to measure commands per second
                commands_sent = 0
                start_time = time.time()
                last_log_time = time.time()

                while True:
                    # 1) Update the gait state machine
                    controller.update_gait()

                    # 2) Retrieve angles from the BipedController
                    angles_dict = controller.get_joint_angles()

                    # 3) Send commands directly using RobotInterface
                    await robot.set_real_command_positions(angles_dict)

                    # 4) Also send the same angles to MuJoCo puppet, if available
                    if puppet is not None:
                        await puppet.set_joint_angles(angles_dict)

                    # Log actual positions every second
                    current_time = time.time()
                    if current_time - last_log_time >= 1.0:
                        positions = await robot.get_feedback_positions()
                        logger.info(f"Current positions: {positions}")
                        logger.info(f"Target positions: {angles_dict}")
                        logger.info(f"Commands per second (CPS): {commands_sent}")
                        commands_sent = 0
                        last_log_time = current_time
                        start_time = current_time
                    else:
                        commands_sent += 1

                    await asyncio.sleep(dt)

            except KeyboardInterrupt:
                logger.info("\nShutting down gracefully...")
            except Exception as e:
                logger.error(f"Error during operation: {e}")
            finally:
                # Always try to disable torque on shutdown
                try:
                    logger.info("Disabling torque...")
                    await robot.disable_all_torque()
                except Exception as e:
                    logger.error(f"Error disabling torque: {e}")
    else:
        # Simulation-only mode
        logger.info("Running in simulation-only mode (PyKOS commands are disabled).")
        try:
            while True:
                controller.update_gait()
                angles_dict = controller.get_joint_angles()
                if puppet is not None:
                    await puppet.set_joint_angles(angles_dict)
                await asyncio.sleep(dt)
        except KeyboardInterrupt:
            logger.info("\nShutting down gracefully.")


if __name__ == "__main__":
    asyncio.run(main())
