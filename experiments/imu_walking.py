"""Script to demonstrate IMU-based balanced walking."""

import asyncio
import math
import time
import numpy as np
from scipy.spatial.transform import Rotation as R
from pykos import KOS
from walkingsequence import BipedController, joint_to_actuator_id, angles_to_pykos_commands


class IMUBalancedWalker:
    """Walker that uses IMU feedback for balance control."""

    def __init__(self, lateral_movement_enabled=False):
        self.walker = BipedController(lateral_movement_enabled=lateral_movement_enabled)

        # Balance control gains - More aggressive correction
        self.pitch_correction_gain = 2.0  # Increased for faster response
        self.roll_correction_gain = 1.0

        # Velocity gains - Much higher for predictive correction
        self.pitch_velocity_gain = 0.8  # Increased from 0.3
        self.roll_velocity_gain = 0.3

        # IMU feedback state
        self.current_pitch = 0.0
        self.current_roll = 0.0
        self.pitch_velocity = 0.0
        self.roll_velocity = 0.0
        self.last_update_time = time.time()

        # Store velocity history for trend analysis
        self.velocity_history_size = 5
        self.pitch_velocity_history = [0.0] * self.velocity_history_size
        self.roll_velocity_history = [0.0] * self.velocity_history_size

        # Balance thresholds - Lower thresholds to start correction earlier
        self.MAX_PITCH_CORRECTION = math.radians(25)  # Increased range
        self.MAX_ROLL_CORRECTION = math.radians(20)

        # Early correction thresholds
        self.PITCH_CORRECTION_START = math.radians(5)  # Start correcting at smaller angles
        self.ROLL_CORRECTION_START = math.radians(3)

        # Low pass filter for IMU values - More responsive
        self.alpha = 0.5  # Increased from 0.3 for faster response
        self.filtered_pitch = 0.0
        self.filtered_roll = 0.0

        # Initial pose adjustments - Much more upright
        self.base_hip_pitch_offset = math.radians(15)  # Reduced from 32 to 15 degrees

        # Adjust walker parameters for more stable stance
        self.walker.hip_forward_offset = 2.0  # Reduced forward offset
        self.walker.nominal_leg_height = 165.0  # Slightly lower stance
        self.walker.initial_leg_height = 165.0  # Match nominal height

        # Fixed walking parameters - prevent any dynamic changes
        self.walker.step_cycle_length = 200  # Much longer step cycle for slower movement
        self.walker.step_length = 5.0  # Shorter steps for stability
        self.walker.double_support_fraction = 0.4  # More time in double support

        # Rate limiting
        self.last_gait_update = 0
        self.gait_update_interval = 0.02  # 50Hz gait updates
        self.last_command = {}  # Store last command for interpolation

    def update_velocity_history(self):
        """Update velocity history and detect trends."""
        self.pitch_velocity_history = self.pitch_velocity_history[1:] + [self.pitch_velocity]
        self.roll_velocity_history = self.roll_velocity_history[1:] + [self.roll_velocity]

        # Calculate acceleration (trend in velocity)
        pitch_accel = sum(np.diff(self.pitch_velocity_history))
        roll_accel = sum(np.diff(self.roll_velocity_history))

        return pitch_accel, roll_accel

    async def update_imu_state(self, kos: KOS):
        """Update internal state with latest IMU readings."""
        try:
            # Get quaternion from IMU
            quat = await kos.imu.get_quaternion()
            rotation = R.from_quat([quat.x, quat.y, quat.z, quat.w])

            # Convert to euler angles
            euler = rotation.as_euler("xyz", degrees=False)
            raw_roll, raw_pitch, _ = euler

            # Apply low pass filter
            self.filtered_roll = self.alpha * raw_roll + (1 - self.alpha) * self.filtered_roll
            self.filtered_pitch = self.alpha * raw_pitch + (1 - self.alpha) * self.filtered_pitch

            # Calculate velocities
            current_time = time.time()
            dt = current_time - self.last_update_time
            if dt > 0:
                self.pitch_velocity = (self.filtered_pitch - self.current_pitch) / dt
                self.roll_velocity = (self.filtered_roll - self.current_roll) / dt

            self.current_pitch = self.filtered_pitch
            self.current_roll = self.filtered_roll
            self.last_update_time = current_time

            # Update velocity history
            self.update_velocity_history()

        except Exception as e:
            print(f"Error reading IMU: {e}")

    def compute_balance_corrections(self):
        """Compute balance corrections based on IMU feedback and prediction."""
        # Get acceleration trends
        pitch_accel, roll_accel = self.update_velocity_history()

        # Predictive correction based on velocity and acceleration
        predictive_pitch = self.pitch_velocity * self.pitch_velocity_gain + pitch_accel * 0.3
        predictive_roll = self.roll_velocity * self.roll_velocity_gain + roll_accel * 0.2

        # Combine feedback and predictive corrections
        pitch_correction = self.pitch_correction_gain * self.current_pitch + predictive_pitch
        roll_correction = self.roll_correction_gain * self.current_roll + predictive_roll

        # Early correction scaling
        if abs(self.current_pitch) > self.PITCH_CORRECTION_START:
            pitch_correction *= 1.5  # More aggressive when starting to fall
        if abs(self.current_roll) > self.ROLL_CORRECTION_START:
            roll_correction *= 1.5

        # Extra correction for forward pitch
        if self.current_pitch > 0 or (self.current_pitch > -0.1 and self.pitch_velocity > 0):
            pitch_correction *= 2.0  # Even more aggressive for forward pitch

        # Limit corrections
        pitch_correction = np.clip(pitch_correction, -self.MAX_PITCH_CORRECTION, self.MAX_PITCH_CORRECTION)
        roll_correction = np.clip(roll_correction, -self.MAX_ROLL_CORRECTION, self.MAX_ROLL_CORRECTION)

        return pitch_correction, roll_correction

    def apply_balance_corrections(self, pitch_correction, roll_correction):
        """Apply computed corrections to the walker's joint angles."""
        # Adjust hip pitch offset based on IMU feedback
        self.walker.hip_pitch_offset = self.base_hip_pitch_offset - pitch_correction

        # More aggressive ankle correction
        ankle_correction = pitch_correction * 0.7  # Increased from 0.5

        # Adjust ankle angles to compensate for both pitch and roll
        if self.walker.stance_foot_index == 0:  # Left foot is stance
            self.walker.A0[0] += roll_correction + ankle_correction  # Left ankle
            self.walker.A0[1] -= roll_correction - ankle_correction  # Right ankle
        else:  # Right foot is stance
            self.walker.A0[0] -= roll_correction - ankle_correction  # Left ankle
            self.walker.A0[1] += roll_correction + ankle_correction  # Right ankle

    def get_joint_angles(self):
        """Get joint angles from the walker."""
        return self.walker.get_joint_angles()

    def update_gait(self):
        """Update the walking gait."""
        self.walker.update_gait()


async def run_balanced_walk(ip: str, sim_only: bool = False):
    """Run the IMU-balanced walking sequence."""
    # Slower control loop
    dt = 0.02  # 50Hz control loop instead of 1000Hz1
    async with KOS(ip=ip) as kos:
        if sim_only:
            print("Resetting simulation...")
            await kos.sim.reset()

        # Configure actuators with higher gains for better position holding
        leg_actuators = [31, 32, 33, 34, 35, 41, 42, 43, 44, 45]
        gains = {
            True: {"kp": 150, "kd": 15},  # Reduced gains to prevent oscillation
            False: {"kp": 32, "kd": 32},  # Real robot gains
        }[sim_only]

        for actuator_id in leg_actuators:
            print(f"Enabling torque for leg actuator {actuator_id}")
            await kos.actuator.configure_actuator(
                actuator_id=actuator_id,
                kp=gains["kp"],
                kd=gains["kd"],
                max_torque=100,
                torque_enabled=True,
            )

        try:
            # Initialize balanced walker
            balanced_walker = IMUBalancedWalker(lateral_movement_enabled=False)

            # Get to initial stance - more vertical position
            print("Moving to initial stance...")
            # Adjust initial foot positions for stability
            balanced_walker.walker.control_foot_position(
                -balanced_walker.walker.hip_forward_offset,
                0.0,
                balanced_walker.walker.nominal_leg_height,
                0,
            )
            balanced_walker.walker.control_foot_position(
                -balanced_walker.walker.hip_forward_offset,
                0.0,
                balanced_walker.walker.nominal_leg_height,
                1,
            )

            # Hold initial stance while gathering IMU data
            print("Stabilizing and calibrating IMU...")
            start_time = time.time()
            while time.time() - start_time < 3.0:
                await balanced_walker.update_imu_state(kos)
                angles_dict = balanced_walker.get_joint_angles()
                commands = angles_to_pykos_commands(angles_dict)
                if commands:
                    await kos.actuator.command_actuators(commands)
                await asyncio.sleep(dt)

            # Main walking loop with fixed parameters
            print("Starting balanced walk...")
            balanced_walker.walker.gait_phase = 20  # Skip initial ramp

            last_gait_update = time.time()
            start_time = time.time()

            while time.time() - start_time < 10.0:
                current_time = time.time()

                # Update IMU state
                await balanced_walker.update_imu_state(kos)

                # Compute and apply balance corrections
                pitch_correction, roll_correction = balanced_walker.compute_balance_corrections()
                balanced_walker.apply_balance_corrections(pitch_correction, roll_correction)

                # Update walking gait at a fixed rate
                if current_time - last_gait_update >= 0.02:  # 50Hz gait updates
                    balanced_walker.update_gait()
                    last_gait_update = current_time

                # Send commands
                angles_dict = balanced_walker.get_joint_angles()
                commands = angles_to_pykos_commands(angles_dict)
                if commands:
                    await kos.actuator.command_actuators(commands)

                # Log IMU state and step timing periodically
                if int((current_time - start_time) * 10) % 10 == 0:
                    print(
                        f"Pitch: {math.degrees(balanced_walker.current_pitch):.1f}°, "
                        f"Roll: {math.degrees(balanced_walker.current_roll):.1f}°, "
                        f"Step: {balanced_walker.walker.step_cycle_counter}/{balanced_walker.walker.step_cycle_length}"
                    )

                await asyncio.sleep(dt)

            # Return to stable stance
            print("Ending sequence...")
            balanced_walker.walker.control_foot_position(
                -balanced_walker.walker.hip_forward_offset,
                0.0,
                balanced_walker.walker.nominal_leg_height,
                0,
            )
            balanced_walker.walker.control_foot_position(
                -balanced_walker.walker.hip_forward_offset,
                0.0,
                balanced_walker.walker.nominal_leg_height,
                1,
            )

            # Hold final position
            start_time = time.time()
            while time.time() - start_time < 2.0:
                await balanced_walker.update_imu_state(kos)
                angles_dict = balanced_walker.get_joint_angles()
                commands = angles_to_pykos_commands(angles_dict)
                if commands:
                    await kos.actuator.command_actuators(commands)
                await asyncio.sleep(dt)

            print("Sequence complete!")

        except KeyboardInterrupt:
            print("\nStopping sequence...")
            return


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Run IMU-balanced walking sequence")
    parser.add_argument(
        "--ip",
        type=str,
        default="localhost",
        help="IP for the KOS device",
    )
    parser.add_argument(
        "--sim-only",
        action="store_true",
        help="Run in simulation only mode",
    )
    args = parser.parse_args()

    await run_balanced_walk(ip=args.ip, sim_only=args.sim_only)


if __name__ == "__main__":
    asyncio.run(main())
