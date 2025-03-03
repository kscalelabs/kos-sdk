import asyncio
import time
import math
from pykos import KOS
from walking import BipedController, joint_to_actuator_id, angles_to_pykos_commands


async def run_walk_sequence(ip: str):
    dt = 1.0
    async with KOS(ip=ip) as kos:
        # Initial setup - only configure leg actuators
        leg_actuators = [
            31,
            32,
            33,
            34,
            35,
            41,
            42,
            43,
            44,
            45,
            11,
            12,
            13,
            14,
            21,
            22,
            23,
            24,
        ]
        for actuator_id in leg_actuators:
            print(f"Enabling torque for leg actuator {actuator_id}")
            await kos.actuator.configure_actuator(
                actuator_id=actuator_id,
                kp=32,
                kd=32,
                max_torque=100,
                torque_enabled=True,
            )

        # Countdown
        for i in range(5, 0, -1):
            print(f"Starting sequence in {i}...")
            await asyncio.sleep(1)

        try:
            # Get pre-walk stance first
            walker = BipedController(lateral_movement_enabled=False)
            walker.hip_pitch_offset = math.radians(10)  # Initial lean
            walker.control_foot_position(
                -walker.hip_forward_offset, 0.0, walker.nominal_leg_height, 0
            )
            walker.control_foot_position(
                -walker.hip_forward_offset, 0.0, walker.nominal_leg_height, 1
            )
            pre_walk_angles = walker.get_joint_angles()

            # Convert to leg-only commands
            pre_walk_commands = []
            for joint_name, angle_radians in pre_walk_angles.items():
                if joint_name in joint_to_actuator_id:
                    actuator_id = joint_to_actuator_id[joint_name]
                    if actuator_id in leg_actuators:
                        angle_degrees = math.degrees(angle_radians)
                        if actuator_id in [32]:
                            angle_degrees = -angle_degrees
                        pre_walk_commands.append(
                            {"actuator_id": actuator_id, "position": angle_degrees}
                        )

            # Hold the pre-walk stance for 3 seconds
            print("Holding pre-walk stance...")
            hold_start = time.time()
            while time.time() - hold_start < 3.0:
                await kos.actuator.command_actuators(pre_walk_commands)
                await asyncio.sleep(dt)

            # Walking sequence
            print("Starting walk...")
            walker.hip_pitch_offset = math.radians(10)  # Walking pitch
            walker.gait_phase = 20  # Skip the initial ramping phase
            start_time = time.time()
            while time.time() - start_time < 10.0:
                walker.step_length = 20.0
                walker.step_cycle_length = 1
                walker.update_gait()
                angles_dict = walker.get_joint_angles()

                commands = []
                for joint_name, angle_radians in angles_dict.items():
                    if joint_name in joint_to_actuator_id:
                        actuator_id = joint_to_actuator_id[joint_name]
                        if actuator_id in leg_actuators:
                            angle_degrees = math.degrees(angle_radians)
                            if actuator_id in [32]:
                                angle_degrees = -angle_degrees
                            commands.append(
                                {"actuator_id": actuator_id, "position": angle_degrees}
                            )

                if commands:
                    await kos.actuator.command_actuators(commands)
                await asyncio.sleep(dt)

            # End with stable stance
            print("Ending sequence...")
            walker.hip_pitch_offset = math.radians(10)  # Final stance
            walker.control_foot_position(
                -walker.hip_forward_offset, 0.0, walker.nominal_leg_height, 0
            )
            walker.control_foot_position(
                -walker.hip_forward_offset, 0.0, walker.nominal_leg_height, 1
            )
            final_angles = walker.get_joint_angles()

            final_commands = []
            for joint_name, angle_radians in final_angles.items():
                if joint_name in joint_to_actuator_id:
                    actuator_id = joint_to_actuator_id[joint_name]
                    if actuator_id in leg_actuators:
                        angle_degrees = math.degrees(angle_radians)
                        if actuator_id in [32]:
                            angle_degrees = -angle_degrees
                        final_commands.append(
                            {"actuator_id": actuator_id, "position": angle_degrees}
                        )

            # Hold final position
            start_time = time.time()
            transition_duration = 1.0
            while time.time() - start_time < transition_duration:
                await kos.actuator.command_actuators(final_commands)
                await asyncio.sleep(dt)

            print("Sequence complete!")

        except KeyboardInterrupt:
            print("\nStopping sequence...")
            return


async def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--ip", type=str, default="10.33.12.76", help="IP for the KOS device"
    )
    parser.add_argument(
        "--no-lateral",
        action="store_true",
        help="Disable lateral movements",
        default=True,
    )
    args = parser.parse_args()

    await run_walk_sequence(ip=args.ip)


if __name__ == "__main__":
    asyncio.run(main())
