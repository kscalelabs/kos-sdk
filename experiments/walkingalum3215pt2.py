import argparse
import asyncio
import math
import time

from pykos import KOS
from ks_digital_twin.puppet.mujoco_puppet import MujocoPuppet


class BipedController:
    """
    Simplified bipedal walking logic with feet parallel to the ground.
    """

    def __init__(self):
        # Gait params
        self.LEG_LENGTH = 180.0  # mm
        self.hip_forward_offset = 2.04
        self.nominal_leg_height = 170.0
        self.gait_phase = 0
        self.walking_enabled = True

        # Variables for cyclical stepping
        self.stance_foot_index = 0  # 0 or 1
        self.step_cycle_length = 8
        self.step_cycle_counter = 0
        self.max_foot_lift = 30
        self.current_foot_lift = 0.0

        self.forward_offset = [0.0, 0.0]
        self.step_length = 100.0

        # The joint angle arrays
        self.K0 = [0.0, 0.0]  # hip pitch
        self.H = [0.0, 0.0]  # knee
        self.A0 = [0.0, 0.0]  # ankle pitch

    def control_foot_position(self, x, y, h, side):
        """
        Compute joint angles given the desired foot position (x, y, h).
        Ensure the foot stays parallel to the ground.
        """
        k = math.sqrt(x * x + (y * y + h * h))
        k = min(k, self.LEG_LENGTH)  # Ensure k does not exceed LEG_LENGTH

        if abs(k) < 1e-8:
            alpha = 0.0
        else:
            alpha = math.asin(x / k)

        cval = max(min(k / self.LEG_LENGTH, 1.0), -1.0)
        gamma = math.acos(cval)

        # Hip pitch and knee angles
        self.K0[side] = gamma + alpha  # hip pitch
        self.H[side] = 2.0 * gamma  # knee

        # Ankle pitch angle to keep the foot parallel to the ground
        self.A0[side] = -gamma + alpha  # ankle pitch

    def update_gait(self):
        """
        Update the internal state machine and foot positions each timestep.
        """
        if self.gait_phase == 0:
            # Idle phase
            self.control_foot_position(
                -self.hip_forward_offset, 0.0, self.nominal_leg_height, 0
            )
            self.control_foot_position(
                -self.hip_forward_offset, 0.0, self.nominal_leg_height, 1
            )
            if self.walking_enabled:
                self.gait_phase = 20

        elif self.gait_phase == 20:
            # Walking phase
            fraction = self.step_cycle_counter / self.step_cycle_length

            # Update forward offset for the stance foot
            self.forward_offset[self.stance_foot_index] = -self.step_length * fraction

            # Lift the swing foot
            if self.step_cycle_counter > self.step_cycle_length / 2:
                self.current_foot_lift = self.max_foot_lift * math.sin(
                    math.pi
                    * (self.step_cycle_counter - self.step_cycle_length / 2)
                    / (self.step_cycle_length / 2)
                )
            else:
                self.current_foot_lift = 0.0

            # Control foot positions
            if self.stance_foot_index == 0:
                # Left foot is stance, right foot is swing
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
                # Right foot is stance, left foot is swing
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

            # Update step cycle
            if self.step_cycle_counter >= self.step_cycle_length:
                self.stance_foot_index ^= 1
                self.step_cycle_counter = 0
            else:
                self.step_cycle_counter += 1

    def get_joint_angles(self):
        """
        Return a dictionary with all the joint angles in radians.
        """
        angles = {
            "left_hip_pitch": -self.K0[0],
            "left_knee": self.H[0],
            "left_ankle": self.A0[0],
            "right_hip_pitch": self.K0[1],
            "right_knee": -self.H[1],
            "right_ankle": -self.A0[1],
        }
        return angles


joint_to_actuator_id = {
    # Left leg
    "left_hip_pitch": 33,
    "left_knee": 34,
    "left_ankle": 35,
    # Right leg
    "right_hip_pitch": 43,
    "right_knee": 44,
    "right_ankle": 45,
}


def angles_to_pykos_commands(angles_dict):
    """
    Convert each angle (in radians) to a pykos command dictionary.
    """
    cmds = []
    for joint_name, angle_radians in angles_dict.items():
        if joint_name not in joint_to_actuator_id:
            continue
        actuator_id = joint_to_actuator_id[joint_name]
        angle_degrees = math.degrees(angle_radians)
        cmds.append({"actuator_id": actuator_id, "position": angle_degrees})
    return cmds


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--ip",
        type=str,
        default="10.33.12.76",
        help="IP for the KOS device, default=192.168.42.1",
    )
    parser.add_argument(
        "--mjcf_name",
        type=str,
        default="zbot-v2-fixed",
        help="Name of the Mujoco model in the K-Scale API (optional).",
    )
    parser.add_argument(
        "--no-pykos",
        action="store_true",
        help="Disable sending commands to PyKOS (simulation-only mode).",
    )
    args = parser.parse_args()

    # Create the biped controller
    controller = BipedController()

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
                    max_torque=90,
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

            # Main control loop
            commands_sent = 0
            start_time = time.time()
            try:
                while True:
                    # Update the gait state machine
                    controller.update_gait()

                    # Retrieve angles from the BipedController
                    angles_dict = controller.get_joint_angles()

                    # Convert angles to PyKOS commands and send to the real robot
                    commands = angles_to_pykos_commands(angles_dict)
                    if commands:
                        await kos.actuator.command_actuators(commands)

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
    else:
        # Simulation-only mode
        print("Running in simulation-only mode (PyKOS commands are disabled).")
        commands_sent = 0
        start_time = time.time()
        try:
            while True:
                controller.update_gait()
                angles_dict = controller.get_joint_angles()
                commands = angles_to_pykos_commands(angles_dict)
                if puppet is not None:
                    await puppet.set_joint_angles(angles_dict)
                commands_sent += 1
                current_time = time.time()
                if current_time - start_time >= 1.0:
                    print(f"Simulated Commands per second (CPS): {commands_sent}")
                    commands_sent = 0
                    start_time = current_time
                await asyncio.sleep(dt)
        except KeyboardInterrupt:
            print("\nShutting down gracefully.")


if __name__ == "__main__":
    asyncio.run(main())
