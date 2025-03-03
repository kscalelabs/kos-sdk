import asyncio
import subprocess
import time
import argparse
import math
import logging
from pykos import KOS

# Set up detailed logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# Actual leg segment lengths in mm
FOOT_LENGTH = 35.0  # Bottom of foot to ankle servo pivot
SHIN_LENGTH = 100.0  # Ankle servo to knee servo
THIGH_LENGTH = 100.0  # Knee servo to hip pitch servo

# Joint IDs for both legs
ACTUATOR_IDS = {
    # left arm
    "left_shoulder_pitch": 11,
    "left_shoulder_roll": 12,
    "left_elbow": 13,
    "left_gripper": 14,
    # right arm
    "right_shoulder_pitch": 21,
    "right_shoulder_roll": 22,
    "right_elbow": 23,
    "right_gripper": 24,
    # left leg
    "left_hip_yaw": 31,
    "left_hip_pitch": 33,
    "left_knee": 34,
    "left_ankle": 35,
    "left_hip_roll": 32,
    # right leg
    "right_hip_yaw": 41,
    "right_hip_pitch": 43,
    "right_knee": 44,
    "right_ankle": 45,
    "right_hip_roll": 42,
}


def calculate_foot_position(
    left_hip_pitch_deg: float,
    left_knee_deg: float,
    left_ankle_deg: float,
    right_ankle_deg: float,
    left_hip_roll_deg: float,
    right_hip_pitch_deg: float,
    right_knee_deg: float,
    right_hip_roll_deg: float,
    right_hip_yaw_deg: float,
    left_hip_yaw_deg: float,
) -> tuple:
    """
    Calculate the X,Y position of the foot given the joint angles.
    - X: Horizontal distance (positive = forward)
    - Y: Vertical distance (positive = up)
    - All angles in degrees
    - Position relative to hip pitch servo
    """
    # Convert angles to radians for math calculations
    left_hip_pitch_rad = math.radians(left_hip_pitch_deg)
    left_knee_rad = math.radians(left_knee_deg)
    left_ankle_rad = math.radians(left_ankle_deg)
    right_ankle_rad = math.radians(right_ankle_deg)
    left_hip_roll_rad = math.radians(left_hip_roll_deg)
    right_hip_pitch_rad = math.radians(right_hip_pitch_deg)
    right_knee_rad = math.radians(right_knee_deg)
    right_hip_roll_rad = math.radians(right_hip_roll_deg)
    right_hip_yaw_rad = math.radians(right_hip_yaw_deg)
    left_hip_yaw_rad = math.radians(left_hip_yaw_deg)

    # Calculate absolute segment angles relative to vertical
    # Note: These angles tell us how each segment is oriented in space
    left_thigh_angle = left_hip_pitch_rad  # Thigh angle set by hip pitch
    left_shin_angle = (
        left_hip_pitch_rad + left_knee_rad
    )  # Shin affected by hip AND knee
    left_foot_angle = (
        left_hip_pitch_rad + left_knee_rad + left_ankle_rad
    )  # Foot affected by all joints
    right_hip_roll_angle = right_hip_roll_rad
    right_foot_angle = (
        right_hip_pitch_rad + right_knee_rad + right_ankle_rad + right_hip_roll_rad
    )  # Foot affected by all joints
    logger.info("\nSegment angles relative to vertical:")
    logger.info(f"Left Thigh: {math.degrees(left_thigh_angle):.1f}°")
    logger.info(f"Left Shin:  {math.degrees(left_shin_angle):.1f}°")
    logger.info(f"Left Foot:  {math.degrees(left_foot_angle):.1f}°")
    logger.info(f"Right Foot: {math.degrees(right_foot_angle):.1f}°")
    logger.info(f"Right Hip Roll: {math.degrees(right_hip_roll_angle):.1f}°")
    # Calculate how each segment contributes to final foot position

    # Thigh contribution - from hip pitch to knee
    left_thigh_x = THIGH_LENGTH * math.sin(left_thigh_angle)
    left_thigh_y = -THIGH_LENGTH * math.cos(
        left_thigh_angle
    )  # Negative because Y increases downward

    # Shin contribution - from knee to ankle
    left_shin_x = SHIN_LENGTH * math.sin(left_shin_angle)
    left_shin_y = -SHIN_LENGTH * math.cos(left_shin_angle)

    # Foot contribution - from ankle to bottom of foot
    foot_x = FOOT_LENGTH * math.sin(left_foot_angle)
    foot_y = -FOOT_LENGTH * math.cos(left_foot_angle)

    # Right foot contribution - from ankle to bottom of foot
    right_foot_x = FOOT_LENGTH * math.sin(right_foot_angle)
    right_foot_y = -FOOT_LENGTH * math.cos(right_foot_angle)

    # Total position is sum of all segments
    total_x = left_thigh_x + left_shin_x + foot_x + right_foot_x
    total_y = left_thigh_y + left_shin_y + foot_y + right_foot_y

    logger.info("\nSegment contributions to position:")
    logger.info(
        f"Left Thigh: ({left_thigh_x:.1f}mm forward, {left_thigh_y:.1f}mm down)"
    )
    logger.info(f"Left Shin:  ({left_shin_x:.1f}mm forward, {left_shin_y:.1f}mm down)")
    logger.info(f"Left Foot:  ({foot_x:.1f}mm forward, {foot_y:.1f}mm down)")
    logger.info(
        f"Right Foot: ({right_foot_x:.1f}mm forward, {right_foot_y:.1f}mm down)"
    )
    logger.info(
        f"\nFinal foot position: {total_x:.1f}mm forward, {-total_y:.1f}mm up from hip"
    )
    logger.info(
        f"Right Foot position: {right_foot_x:.1f}mm forward, {-right_foot_y:.1f}mm up from hip"
    )

    # Calculate straight-line distance from hip to foot
    total_distance = math.sqrt(total_x**2 + total_y**2)
    angle_from_vertical = math.degrees(math.atan2(total_x, -total_y))
    logger.info(f"Straight-line distance from hip to foot: {total_distance:.1f}mm")
    logger.info(f"Angle from vertical: {angle_from_vertical:.1f}°")

    return total_x, total_y, right_foot_x, right_foot_y


# the parameters are in the order to which they matter to a good gait
# ie, since the left leg is the one that is moving, the left hip pitch initiates, the left knee and ankle follow, the right leg has to compensate so the feet stay parallel
# the left hip roll does not become important until like the second left foot forward because it needs to squat so you can push off
async def move_leg_and_log_position(
    kos: KOS,
    left_hip_pitch: float,
    left_knee: float,
    left_ankle: float,
    right_ankle: float,
    left_hip_roll: float,
    right_hip_pitch: float,
    right_knee: float,
    right_hip_roll: float,
    right_hip_yaw: float,
    left_hip_yaw: float,
):
    """Move leg to specified angles and show resulting foot position."""
    logger.info(f"\nMoving to angles:")
    logger.info(f"Left Hip Pitch: {left_hip_pitch}° (positive = forward rotation)")
    logger.info(f"Left Knee: {left_knee}° (positive = forward/down)")
    logger.info(f"Left Ankle: {left_ankle}° (positive = forward)")
    logger.info(f"Right Ankle: {right_ankle}° (positive = forward)")
    logger.info(f"Left Hip Roll: {left_hip_roll}° (positive = right)")
    logger.info(f"Right Hip Pitch: {right_hip_pitch}° (positive = forward rotation)")
    logger.info(f"Right Knee: {right_knee}° (positive = forward/down)")
    logger.info(f"Right Hip Roll: {right_hip_roll}° (positive = right)")
    logger.info(f"Left Hip Yaw: {left_hip_yaw}° (positive = right)")
    logger.info(f"Right Hip Yaw: {right_hip_yaw}° (positive = right)")
    # Command the servos
    commands = [
        {"actuator_id": ACTUATOR_IDS["left_hip_pitch"], "position": left_hip_pitch},
        {"actuator_id": ACTUATOR_IDS["left_knee"], "position": left_knee},
        {"actuator_id": ACTUATOR_IDS["left_ankle"], "position": left_ankle},
        {"actuator_id": ACTUATOR_IDS["right_ankle"], "position": right_ankle},
        {"actuator_id": ACTUATOR_IDS["left_hip_roll"], "position": left_hip_roll},
        {"actuator_id": ACTUATOR_IDS["right_hip_pitch"], "position": right_hip_pitch},
        {"actuator_id": ACTUATOR_IDS["right_knee"], "position": right_knee},
        {"actuator_id": ACTUATOR_IDS["right_hip_roll"], "position": right_hip_roll},
        {"actuator_id": ACTUATOR_IDS["right_hip_yaw"], "position": right_hip_yaw},
        {"actuator_id": ACTUATOR_IDS["left_hip_yaw"], "position": left_hip_yaw},
    ]
    await kos.actuator.command_actuators(commands)

    # Calculate and display resulting position
    calculate_foot_position(
        left_hip_pitch,
        left_knee,
        left_ankle,
        right_ankle,
        left_hip_roll,
        right_hip_pitch,
        right_knee,
        right_hip_roll,
        right_hip_yaw,
        left_hip_yaw,
    )


async def move_right_leg(
    kos: KOS,
    right_hip_pitch: float,
    right_knee: float,
    right_ankle: float,
    right_hip_yaw: float,
    left_ankle: float,
    right_hip_roll: float,
    left_hip_pitch: float,
    left_knee: float,
    left_hip_roll: float,
    left_hip_yaw: float,
):
    """Move right leg and show resulting foot position."""
    logger.info(f"\nMoving to angles:")
    logger.info(f"Hip Pitch: {right_hip_pitch}° (positive = forward rotation)")
    logger.info(f"Knee: {right_knee}° (positive = forward/down)")
    logger.info(f"Right Ankle: {right_ankle}° (positive = forward)")
    logger.info(f"Left Ankle: {left_ankle}° (compensates)")
    logger.info(f"Hip Roll: {right_hip_roll}° (positive = right)")
    logger.info(f"Left Hip Pitch: {left_hip_pitch}° (positive = forward rotation)")
    logger.info(f"Left Knee: {left_knee}° (positive = forward/down)")
    logger.info(f"Left Hip Yaw: {left_hip_yaw}° (positive = right)")
    logger.info(f"Right Hip Yaw: {right_hip_yaw}° (positive = right)")
    logger.info(f"Left Hip Roll: {left_hip_roll}° (positive = right)")
    logger.info(f"Right Hip Roll: {right_hip_roll}° (positive = right)")

    # Command the servos
    commands = [
        {"actuator_id": 43, "position": right_hip_pitch},  # right hip pitch
        {"actuator_id": 44, "position": right_knee},  # right knee
        {"actuator_id": 45, "position": right_ankle},  # right ankle
        {"actuator_id": 35, "position": left_ankle},  # left ankle for compensation
        {"actuator_id": 42, "position": right_hip_roll},  # right hip roll
        {"actuator_id": 33, "position": left_hip_pitch},  # left hip pitch
        {"actuator_id": 34, "position": left_knee},  # left kneee
        {"actuator_id": 32, "position": left_hip_yaw},  # left hip yaw
        {"actuator_id": 41, "position": right_hip_yaw},  # right hip yaw
        {"actuator_id": 31, "position": left_hip_roll},  # left hip roll
        {"actuator_id": 42, "position": right_hip_roll},  # right hip roll
    ]
    await kos.actuator.command_actuators(commands)

    # Calculate and display resulting position
    calculate_foot_position(
        right_hip_pitch,
        right_knee,
        right_ankle,
        left_ankle,
        right_hip_roll,
        left_hip_pitch,
        left_knee,
        left_hip_roll,
        right_hip_yaw,
        left_hip_yaw,
    )


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sim", action="store_true", help="Run in simulation mode")
    args = parser.parse_args()

    sim_process = None
    if args.sim:
        logger.info("Starting simulator...")
        sim_process = subprocess.Popen(["kos-sim", "zbot-v2-fixed", "--no-gravity"])
        time.sleep(2)
        ip = "localhost"
    else:
        ip = "10.33.85.8"

    try:
        async with KOS(ip=ip, port=50051) as kos:
            if args.sim:
                await kos.sim.reset()

            # Configure the joints
            for joint_id in ACTUATOR_IDS.values():
                logger.info(f"Configuring joint {joint_id}...")
                await kos.actuator.configure_actuator(
                    actuator_id=joint_id,
                    kp=32,
                    kd=32,
                    max_torque=95,
                    torque_enabled=True,
                )
                logger.info(f"Successfully configured joint {joint_id}")

            # Give time for configuration to take effect
            await asyncio.sleep(1)

            # Try different leg positions
            logger.info("\n=== just bring knee forward to 90 degrees ===")
            await move_leg_and_log_position(kos, -30, 30, 0, 0, 0, 0, 0, 0, 0, 0)
            input("Press Enter to continue...")

            logger.info("\n=== bring knee down ===")
            await move_leg_and_log_position(kos, -30, 10, 0, 0, 0, 0, 0, 0, 0, 0)
            input("Press Enter to continue...")

            logger.info("\n=== fully step forward ===")
            await move_leg_and_log_position(kos, -25, 20, 0, 0, 0, 0, 0, 0, 0, 0)
            input("Press Enter to continue...")

            logger.info("\n=== Starting at zero (standing) position ===")
            await move_leg_and_log_position(kos, -20, 10, -5, 0, 0, 0, 0, 0, 0, 0)
            input("Press Enter to continue...")

            logger.info("\n=== Large left foot step forward ===")
            await move_leg_and_log_position(kos, -30, 16, -13, -5, 2, 0, 0, 0, 0, 0)
            input("Press Enter to continue...")

            logger.info("\n=== bring left foot down ===")
            await move_leg_and_log_position(kos, -20, 16, -10, -5, 1, 0, 0, 0, 0, 0)
            input("Press Enter to continue...")

            logger.info("\n=== adjust right foot ===")
            await move_leg_and_log_position(kos, -18, 10, -5, 0, 0, 0, 0, 0, 0, 0)
            input("Press Enter to continue...")

            logger.info("\n=== prepare for right foot step forward ===")
            await move_leg_and_log_position(kos, -12, 8, -2, 0, 0, 0, 0, 0, 0, 0)
            input("Press Enter to continue...")

            logger.info("\n=== right foot step forward ===")
            await move_leg_and_log_position(kos, -12, 9, -1, 0, 0, 0, 0, 0, 0, 0)
            input("Press Enter to continue...")

            # Right foot lift and forward (mirror of left sequence):
            logger.info("\n=== right foot ready for forward ===")
            await move_right_leg(
                kos,
                45,
                -35,
                15,
                0,
                -10,
                0,
                0,
                0,
                0,
                0,
            )  # Lift and forward
            input("Press Enter to continue...")

            # Right foot lift and forward (mirror of left sequence):
            logger.info("\n=== right foot lift and forward ===")
            await move_right_leg(
                kos,
                70,
                -50,
                25,
                0,
                -15,
                0,
                0,
                0,
                0,
                0,
            )  # Lift and forward
            input("Press Enter to continue...")

            # Right foot down:
            logger.info("\n=== right foot down ===")
            await move_right_leg(
                kos,
                50,
                -35,
                15,
                0,
                -10,
                25,
                15,
                0,
                0,
                0,
            )  # Bring down
            input("Press Enter to continue...")

            # Adjust left foot:
            logger.info("\n=== adjust left foot ===")
            await move_right_leg(
                kos,
                18,
                -10,
                0,
                0,
                0,
                10,
                5,
                0,
                0,
                0,
            )  # Adjust stance
            input("Press Enter to continue...")

            # Ready for next left step:
            logger.info("\n=== prepare for next left step ===")
            await move_right_leg(
                kos,
                12,
                -8,
                2,
                0,
                0,
                0,
                5,
                0,
                0,
                0,
            )  # Prepare for next step
            input("Press Enter to continue...")

            logger.info("\n=== return to neutral ===")
            await move_right_leg(
                kos,
                8,
                -5,
                0,
                0,
                0,
                0,
                5,
                0,
                0,
                0,
            )  # Return to neutral
            input("Press Enter to continue...")

    finally:
        if sim_process:
            logger.info("Stopping simulator...")
            sim_process.terminate()
            sim_process.wait()


if __name__ == "__main__":
    asyncio.run(main())
