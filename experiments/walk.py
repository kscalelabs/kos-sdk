import argparse
import asyncio
import math
import time

from pykos import KOS
from ks_digital_twin.puppet.mujoco_puppet import MujocoPuppet


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

        self.hip_pitch_offset = math.radians(25)  # Reduced back to 15 degrees
        self.roll_offset = math.radians(0)  # Added for hip roll control

    def visualize_robot_state(self):
        """Show ASCII visualization of current robot state"""
        phase_names = {
            0: "GETTING READY - Lowering to walking height",
            10: "READY STANCE - Standing stable, ready to walk",
            20: "WEIGHT SHIFT - Both feet down, shifting weight",
            30: "TAKING STEP - One foot lifting and moving forward",
        }

        # Basic robot visualization
        if self.gait_phase == 0:
            height = self.initial_leg_height
            print(
                """
                Getting Ready
                   ___
                  |. .|
                   |-|
                  /   \\
                 |     |
                 |     |
                /       \\
               |         |
            ==================
            Both feet together, slowly lowering
            """
            )

        elif self.gait_phase == 10:
            print(
                """
                Ready Stance
                   ___
                  |. .|
                   |-|
                  /   \\
                 |     |
                 |     |
                /       \\
               |         |
            ==================
            Standing stable, ready to walk
            """
            )

        elif self.gait_phase == 20:
            stance = "LEFT" if self.stance_foot_index == 0 else "RIGHT"
            print(
                f"""
                Weight Shift to {stance}
                   ___
                  |. .|    Weight
                   |-|      -->
                  /   \\
                 |     |
                 |     |
                /       \\
               |         |
            ==================
            Shifting weight to {stance} foot
            """
            )

        elif self.gait_phase == 30:
            swing = "RIGHT" if self.stance_foot_index == 0 else "LEFT"
            stance = "LEFT" if self.stance_foot_index == 0 else "RIGHT"
            print(
                f"""
                Taking Step with {swing}
                   ___
                  |. .|
                   |-|     {swing}
                  /   \\   foot
                 |     | lifting
                 |     |   -->
                /       \\
               |         |
            ==================
            {stance} foot planted, {swing} foot stepping
            """
            )

        print(f"\nPHASE {self.gait_phase}: {phase_names[self.gait_phase]}")
        print(f"Step Cycle: {self.step_cycle_counter}/{self.step_cycle_length}")

        if self.gait_phase >= 20:
            stance = "Left" if self.stance_foot_index == 0 else "Right"
            swing = "Right" if self.stance_foot_index == 0 else "Left"
            print(f"\nStance (planted) foot: {stance}")
            print(f"Swing (moving) foot: {swing}")
            if self.current_foot_lift > 0:
                print(f"Foot lift height: {self.current_foot_lift:.1f}mm")

        input("\nPress Enter to continue to next update...")

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
        """Update the walking state machine with clear visualization"""
        self.visualize_robot_state()

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
        angles["right_elbow"] = 0.0  # Fixed: was using self.H[1]
        angles["right_gripper"] = 0.0

        return angles


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


def angles_to_pykos_commands(angles_dict):
    """
    Convert each angle (in radians) to a pykos command dictionary.
    Here we do a naive 1 rad -> ~57 deg.
    In reality, you'll likely need gear ratio, zero offset, sign flips, etc.
    """
    cmds = []
    for joint_name, angle_radians in angles_dict.items():
        if joint_name not in joint_to_actuator_id:
            continue
        actuator_id = joint_to_actuator_id[joint_name]
        # Example: convert radians to degrees
        angle_degrees = math.degrees(angle_radians)
        if actuator_id in [32]:
            angle_degrees = -angle_degrees

        # You might need an offset or gear ratio here:
        # position_counts = angle_degrees * (some_gain)

        # For demonstration, let's just send angle_degrees as the position:
        cmds.append({"actuator_id": actuator_id, "position": angle_degrees})
    return cmds


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--ip",
        type=str,
        default="10.33.85.8",
        help="IP for the KOS device, default=192.168.42.1",
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

    # Create our biped controller with lateral movements disabled if --no-lateral is used
    controller = BipedController(lateral_movement_enabled=not args.no_lateral)

    # If --mjcf_name is provided, set up a MujocoPuppet
    puppet = None
    if args.mjcf_name:
        puppet = MujocoPuppet(args.mjcf_name)

    dt = 0.001

    if not args.no_pykos:
        # Connect to KOS and enable actuators
        async with KOS(ip=args.ip) as kos:
            for actuator_id in joint_to_actuator_id.values():
                print(f"Enabling torque for actuator {actuator_id}")
                await kos.actuator.configure_actuator(
                    actuator_id=actuator_id,
                    kp=32,
                    kd=32,
                    max_torque=80,
                    torque_enabled=True,
                )

            # Optionally initialize to 0 position
            for actuator_id in joint_to_actuator_id.values():
                print(f"Setting actuator {actuator_id} to 0 position")
                await kos.actuator.command_actuators(
                    [{"actuator_id": actuator_id, "position": 0}]
                )

            # Countdown before starting movement
            for i in range(5, 0, -1):
                print(f"Starting in {i}...")
                await asyncio.sleep(1)

            # Counters to measure commands per second
            commands_sent = 0
            start_time = time.time()
            i = 0
            try:
                while True:
                    if i >= 1000:
                        i = 0
                    i += 1
                    # 1) Update the gait state machine
                    controller.update_gait()

                    # 2) Retrieve angles from the BipedController
                    angles_dict = controller.get_joint_angles()

                    # 3) Convert angles to PyKOS commands and send to the real robot
                    commands = angles_to_pykos_commands(angles_dict)
                    if commands:
                        await kos.actuator.command_actuators(commands)

                    # 4) Also send the same angles to MuJoCo puppet, if available
                    # Uncomment below if you wish to update the puppet as well:
                    # if puppet is not None:
                    #     await puppet.set_joint_angles(angles_dict)

                    # Count how many loops (or 'commands sent') per second
                    commands_sent += 1
                    current_time = time.time()
                    if current_time - start_time >= 1.0:
                        print(f"Commands per second (CPS): {commands_sent}")
                        commands_sent = 0
                        start_time = current_time

                    await asyncio.sleep(dt)
            except KeyboardInterrupt:
                print("\nShutting down gracefully.")
                # Optionally disable torque at the end if desired
                # for actuator_id in joint_to_actuator_id.values():
                #     await kos.actuator.configure_actuator(actuator_id=actuator_id, torque_enabled=False)
    else:
        # Simulation-only mode; PyKOS commands are disabled.
        print("Running in simulation-only mode (PyKOS commands are disabled).")
        commands_sent = 0
        start_time = time.time()
        i = 0
        try:
            while True:
                if i >= 1000:
                    i = 0
                i += 1
                controller.update_gait()
                angles_dict = controller.get_joint_angles()
                commands = angles_to_pykos_commands(angles_dict)
                # Instead of sending commands, we simply log them.
                # print("Simulated PyKOS command:", commands)
                if puppet is not None:
                    await puppet.set_joint_angles(angles_dict)
                commands_sent += 1
                current_time = time.time()
                if current_time - start_time >= 1.0:
                    # print(f"Simulated Commands per second (CPS): {commands_sent}")
                    commands_sent = 0
                    start_time = current_time
                await asyncio.sleep(dt)
        except KeyboardInterrupt:
            print("\nShutting down gracefully.")


if __name__ == "__main__":
    asyncio.run(main())
