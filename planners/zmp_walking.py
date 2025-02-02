import math
from typing import Dict, Union
from unit_types import Degree

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
    def __init__(self, enable_lateral_motion=True):
        # Parameter to control lateral movements
        self.enable_lateral_motion = enable_lateral_motion

        self.roll_offset = math.radians(0)
        self.hip_pitch_offset = math.radians(20)

        # -----------
        # Gait params
        # -----------
        self.LEG_LENGTH = 180.0  # mm
        self.hip_forward_offset = 2.04
        self.nominal_leg_height = 170.0
        self.initial_leg_height = 180.0
        self.gait_phase = 0
        self.walking_enabled = True

        # -----------
        # Variables for cyclical stepping
        # -----------
        self.stance_foot_index = 0  # 0 or 1
        self.step_cycle_length = 4
        self.step_cycle_counter = 0
        self.lateral_foot_shift = (
            12  # This controls side-to-side movement during walking
        )
        self.max_foot_lift = 10
        self.double_support_fraction = 0.2
        self.current_foot_lift = 0.0

        # Add a base lateral offset to widen the stance
        self.base_stance_width = 2.0  # Increase this value to widen the stance

        self.forward_offset = [0.0, 0.0]
        self.accumulated_forward_offset = 0.0
        self.previous_stance_foot_offset = 0.0
        self.previous_swing_foot_offset = 0.0
        self.step_length = 15.0

        self.lateral_offset = 0.0
        self.dyi = 0.0
        self.pitch = 0.0
        self.roll = 0.0

        # The joint angle arrays
        self.K0 = [0.0, 0.0]  # hip pitch
        self.K1 = [0.0, 0.0]  # hip roll
        self.H = [0.0, 0.0]  # knee
        self.A0 = [0.0, 0.0]  # ankle pitch
        # A1 is omitted, only 1 DOF ankles

    def control_foot_position(self, x, y, h, side):
        """
        Compute joint angles given the desired foot position (x, y, h).
        """
        k = math.sqrt(x * x + (y * y + h * h))
        k = min(k, self.LEG_LENGTH)  # Ensure k does not exceed LEG_LENGTH

        if abs(k) < 1e-8:
            alpha = 0.0
        else:
            alpha = math.asin(x / k)

        cval = max(min(k / self.LEG_LENGTH, 1.0), -1.0)
        gamma = math.acos(cval)

        self.K0[side] = gamma + alpha  # hip pitch
        self.H[side] = 2.0 * gamma + 0.3  # knee, increased pitch by adding 0.3 radians
        ankle_pitch_offset = (
            0.3  # Increased from 0.2 to 0.4 radians to compensate for forward lean
        )

        self.A0[side] = gamma - alpha + ankle_pitch_offset  # ankle pitch with offset

        hip_roll = math.atan2(y, h) if abs(h) >= 1e-8 else 0.0
        self.K1[side] = hip_roll + self.roll_offset

    def virtual_balance_adjustment(self):
        """
        Compute a virtual center-of-mass (CoM) based on the current foot positions,
        and use a simple proportional feedback to adjust the lateral offset.

        For demonstration assumptions:
          - The left foot (index 0) is computed as being at:
              x: self.forward_offset[0] - self.hip_forward_offset
              y: -self.lateral_offset + 1.0
          - The right foot (index 1) is computed as being at:
              x: self.forward_offset[1] - self.hip_forward_offset
              y: self.lateral_offset + 1.0

        We assume the desired CoM (projected on the ground) should have a
        lateral (y-axis) position of 1.0.
        """
        left_foot_x = self.forward_offset[0] - self.hip_forward_offset
        left_foot_y = -self.lateral_offset + 1.0
        right_foot_x = self.forward_offset[1] - self.hip_forward_offset
        right_foot_y = self.lateral_offset + 1.0

        # Compute estimated CoM as the average of the feet positions:
        com_x = (left_foot_x + right_foot_x) / 2.0
        com_y = (left_foot_y + right_foot_y) / 2.0

        # Desired CoM lateral position
        desired_com_y = 1.0

        # Compute the lateral error
        error_y = desired_com_y - com_y

        # Apply a proportional gain to adjust lateral offset
        feedback_gain = 0.1
        adjustment = feedback_gain * error_y

        # Update the lateral_offset value to help steer the CoM
        self.lateral_offset += adjustment

    def update(self, feedback_positions=None):
        if self.gait_phase == 0:
            # Ramping down from initial_leg_height to nominal_leg_height
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
            # Idle
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
            sin_value = math.sin(
                math.pi * self.step_cycle_counter / self.step_cycle_length
            )
            half_cycle = self.step_cycle_length / 2.0

            if self.enable_lateral_motion:
                lateral_shift = self.lateral_foot_shift * sin_value
                self.lateral_offset = (
                    lateral_shift if self.stance_foot_index == 0 else -lateral_shift
                )
                self.virtual_balance_adjustment()
            else:
                self.lateral_offset = 0.0

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

            i = int(self.double_support_fraction * self.step_cycle_length)
            if self.step_cycle_counter > i:
                self.current_foot_lift = self.max_foot_lift * math.sin(
                    math.pi
                    * (self.step_cycle_counter - i)
                    / (self.step_cycle_length - i)
                )
            else:
                self.current_foot_lift = 0.0

            if self.stance_foot_index == 0:
                # left foot = stance
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
                # right foot = stance
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

    def add_offsets(self):
        angles = {}
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

        # Arms & others as placeholders:
        angles["left_shoulder_yaw"] = 0.0
        angles["left_shoulder_pitch"] = 3 * self.K1[0]
        angles["left_elbow"] = 0.0
        angles["left_gripper"] = 0.0

        angles["right_shoulder_yaw"] = 0.0
        angles["right_shoulder_pitch"] = 3 * self.K1[1]
        angles["right_elbow"] = self.H[1]
        angles["right_gripper"] = 0.0

        return angles

    def get_planner_commands(self) -> Dict[str, Union[int, Degree]]:
        angles = self.add_offsets()
        cmds = {}
        for joint_name, angle_radians in angles.items():
            if joint_name not in joint_to_actuator_id:
                continue
            angle_degrees = math.degrees(angle_radians)
            cmds[joint_name] = angle_degrees
        return cmds

    def get_simulation_commands(self) -> Dict[str, float]:
        angles = self.add_offsets()
        cmds = {}
        for joint, angle_radians in angles.items():
            if joint not in joint_to_actuator_id:
                continue
            cmds[joint] = angle_radians
        return cmds
