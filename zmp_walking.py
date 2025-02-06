import math
from typing import Dict, Union
from unit_types import Degree

# Mapping of joint names to their actuator IDs on the physical robot
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


class ZMPWalkingPlanner:
    """
    Zero Moment Point (ZMP) walking planner for bipedal robot.
    ZMP is a point where the sum of all moments is zero, used for maintaining balance during walking.
    """

    def __init__(self, enable_lateral_motion=True):
        # Controls whether the robot sways side-to-side during walking
        self.enable_lateral_motion = enable_lateral_motion

        # Offset angles for balance adjustment
        self.roll_offset = math.radians(0)  # Side-to-side tilt
        self.hip_pitch_offset = math.radians(20)  # Forward lean

        # Physical parameters of the robot
        self.LEG_LENGTH = 180.0  # mm - Length of leg from hip to foot
        self.hip_forward_offset = 2.04  # Forward offset of hip from center
        self.nominal_leg_height = 170.0  # Normal standing height
        self.initial_leg_height = 180.0  # Starting height (higher for safety)

        # State machine variables
        self.gait_phase = 0  # Current phase of walking (0=init, 10=idle, 20/30=walking)
        self.walking_enabled = True

        # Walking cycle parameters
        self.stance_foot_index = 0  # Which foot is on ground (0=left, 1=right)
        self.step_cycle_length = 4  # How many steps in a complete cycle
        self.step_cycle_counter = 0  # Current step in the cycle
        self.lateral_foot_shift = 12  # How far to shift weight side-to-side
        self.max_foot_lift = 10  # How high to lift foot during step
        self.double_support_fraction = 0.2  # Time spent with both feet down
        self.current_foot_lift = 0.0  # Current height of lifted foot

        # Stance parameters
        self.base_stance_width = 2.0  # How far apart feet are normally

        # Movement tracking
        self.forward_offset = [0.0, 0.0]  # Forward position of each foot
        self.accumulated_forward_offset = 0.0  # Total distance walked
        self.previous_stance_foot_offset = 0.0  # Where stance foot was
        self.previous_swing_foot_offset = 0.0  # Where swing foot was
        self.step_length = 15.0  # How long each step is

        # Balance parameters
        self.lateral_offset = 0.0  # Side-to-side position
        self.dyi = 0.0  # Integral term for lateral balance
        self.pitch = 0.0  # Forward/backward tilt
        self.roll = 0.0  # Side-to-side tilt

        # Joint angle arrays for legs
        self.K0 = [0.0, 0.0]  # Hip pitch angles
        self.K1 = [0.0, 0.0]  # Hip roll angles
        self.H = [0.0, 0.0]  # Knee angles
        self.A0 = [0.0, 0.0]  # Ankle angles

    def virtual_balance_adjustment(self):
        """
        Adjusts lateral motion to maintain balance using a simple feedback controller.
        """
        # Calculate error from desired position
        error_y = self.lateral_offset

        # Apply proportional control
        feedback_gain = 0.1
        adjustment = feedback_gain * error_y

        # Update lateral offset to correct balance
        self.lateral_offset += adjustment

    def control_foot_position(self, x, y, h, side):
        """
        Calculates joint angles needed to place foot at desired position.
        Uses inverse kinematics to convert foot position to joint angles.

        Args:
            x: Forward position relative to hip
            y: Lateral position (left/right)
            h: Height from ground
            side: Which leg (0=left, 1=right)
        """
        # Calculate total reach distance
        k = math.sqrt(x * x + (y * y + h * h))
        k = min(k, self.LEG_LENGTH)  # Limit to maximum leg length

        # Calculate angles using inverse kinematics
        if abs(k) < 1e-8:
            alpha = 0.0
        else:
            alpha = math.asin(x / k)  # Angle from vertical to target

        # Calculate leg bend
        cval = max(min(k / self.LEG_LENGTH, 1.0), -1.0)
        gamma = math.acos(cval)  # Angle of leg bend

        # Set joint angles
        self.K0[side] = gamma + alpha  # Hip pitch
        self.H[side] = 2.0 * gamma + 0.3  # Knee angle with offset
        ankle_pitch_offset = 0.3  # Ankle compensation for forward lean
        self.A0[side] = gamma - alpha + ankle_pitch_offset  # Ankle pitch

        # Calculate and set hip roll for lateral movement
        hip_roll = math.atan2(y, h) if abs(h) >= 1e-8 else 0.0
        self.K1[side] = hip_roll + self.roll_offset

    def update(self, feedback_state: Dict[str, Union[int, Degree]]):
        """
        Main state machine for walking. Updates foot positions based on current phase.

        Args:
            feedback_state: Current joint positions from robot
        """
        if self.gait_phase == 0:
            # Initialization phase - gradually lower to walking height
            if self.initial_leg_height > self.nominal_leg_height + 0.1:
                self.initial_leg_height -= 1.0
            else:
                self.gait_phase = 10

            # Keep both feet together during initialization
            self.control_foot_position(
                -self.hip_forward_offset, 0.0, self.initial_leg_height, 0
            )
            self.control_foot_position(
                -self.hip_forward_offset, 0.0, self.initial_leg_height, 1
            )

        elif self.gait_phase == 10:
            # Idle phase - standing ready
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
            # Walking phases
            # Calculate sinusoidal motion for smooth movement
            sin_value = math.sin(
                math.pi * self.step_cycle_counter / self.step_cycle_length
            )
            half_cycle = self.step_cycle_length / 2.0

            # Handle lateral sway if enabled
            if self.enable_lateral_motion:
                lateral_shift = self.lateral_foot_shift * sin_value
                self.lateral_offset = (
                    lateral_shift if self.stance_foot_index == 0 else -lateral_shift
                )
                self.virtual_balance_adjustment()
            else:
                self.lateral_offset = 0.0

            # Calculate forward movement
            if self.step_cycle_counter < half_cycle:
                # First half of step - move stance foot
                fraction = self.step_cycle_counter / self.step_cycle_length
                self.forward_offset[self.stance_foot_index] = (
                    self.previous_stance_foot_offset * (1.0 - 2.0 * fraction)
                )
            else:
                # Second half - prepare for next step
                fraction = 2.0 * self.step_cycle_counter / self.step_cycle_length - 1.0
                self.forward_offset[self.stance_foot_index] = (
                    -(self.step_length - self.accumulated_forward_offset) * fraction
                )

            # Handle transition between double and single support
            if self.gait_phase == 20:
                if self.step_cycle_counter < (
                    self.double_support_fraction * self.step_cycle_length
                ):
                    # Double support phase
                    self.forward_offset[self.stance_foot_index ^ 1] = (
                        self.previous_swing_foot_offset
                        - (
                            self.previous_stance_foot_offset
                            - self.forward_offset[self.stance_foot_index]
                        )
                    )
                else:
                    # Transition to single support
                    self.previous_swing_foot_offset = self.forward_offset[
                        self.stance_foot_index ^ 1
                    ]
                    self.gait_phase = 30

            if self.gait_phase == 30:
                # Single support phase - swing foot movement
                start_swing = int(self.double_support_fraction * self.step_cycle_length)
                denom = (1.0 - self.double_support_fraction) * self.step_cycle_length
                if denom < 1e-8:
                    denom = 1.0

                # Calculate smooth swing trajectory
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

            # Calculate foot lifting height
            i = int(self.double_support_fraction * self.step_cycle_length)
            if self.step_cycle_counter > i:
                # Lift foot during swing phase
                self.current_foot_lift = self.max_foot_lift * math.sin(
                    math.pi
                    * (self.step_cycle_counter - i)
                    / (self.step_cycle_length - i)
                )
            else:
                self.current_foot_lift = 0.0

            # Apply foot positions based on which foot is stance
            if self.stance_foot_index == 0:
                # Left foot is stance foot
                self.control_foot_position(
                    self.forward_offset[0] - self.hip_forward_offset,
                    -self.lateral_offset - self.base_stance_width,
                    self.nominal_leg_height,
                    0,
                )
                self.control_foot_position(
                    self.forward_offset[1] - self.hip_forward_offset,
                    self.lateral_offset + self.base_stance_width,
                    self.nominal_leg_height - self.current_foot_lift,
                    1,
                )
            else:
                # Right foot is stance foot
                self.control_foot_position(
                    self.forward_offset[0] - self.hip_forward_offset,
                    -self.lateral_offset - self.base_stance_width,
                    self.nominal_leg_height - self.current_foot_lift,
                    0,
                )
                self.control_foot_position(
                    self.forward_offset[1] - self.hip_forward_offset,
                    self.lateral_offset + self.base_stance_width,
                    self.nominal_leg_height,
                    1,
                )

            # Check if step cycle is complete
            if self.step_cycle_counter >= self.step_cycle_length:
                # Switch stance foot and reset for next step
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

    def get_command_positions(self) -> Dict[str, Union[int, Degree]]:
        """
        Converts internal joint angles to command positions in degrees.
        Returns a dictionary of joint names to their target angles.
        """
        # Get joint angles with offsets applied
        angles = self.add_offsets()

        # Convert radians to degrees for each joint
        cmds = {}
        for joint_name, angle_radians in angles.items():
            if joint_name not in joint_to_actuator_id:
                continue
            angle_degrees = math.degrees(angle_radians)
            cmds[joint_name] = angle_degrees
        return cmds

    def add_offsets(self):
        """
        Adds balance offsets to raw joint angles and sets arm positions.
        Returns dictionary of all joint angles in radians.
        """
        angles = {}

        # Leg joints
        angles["left_hip_yaw"] = 0.0
        angles["right_hip_yaw"] = 0.0

        angles["left_hip_roll"] = -self.K1[0]
        angles["left_hip_pitch"] = -self.K0[0] + -self.hip_pitch_offset
        angles["left_knee"] = self.H[0]
        angles["left_ankle"] = self.A0[0]

        angles["right_hip_roll"] = self.K1[1]
        angles["right_hip_pitch"] = self.K0[1] + self.hip_pitch_offset
        angles["right_knee"] = -self.H[1]
        angles["right_ankle"] = -self.A0[1]

        # Arm positions - arms move opposite to hips for balance
        angles["left_shoulder_yaw"] = 0.0
        angles["left_shoulder_pitch"] = 3 * self.K1[0]
        angles["left_elbow"] = 0.0
        angles["left_gripper"] = 0.0

        angles["right_shoulder_yaw"] = 0.0
        angles["right_shoulder_pitch"] = 3 * self.K1[1]
        angles["right_elbow"] = self.H[1]
        angles["right_gripper"] = 0.0

        return angles
