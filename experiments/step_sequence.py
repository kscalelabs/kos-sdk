"""Script to demonstrate the full sequence needed for a forward step."""

import argparse
import asyncio
import logging
import math
import colorlogging
from pykos import KOS

logger = logging.getLogger(__name__)

ACTUATOR_MAPPING = {
    # Left leg
    "left_hip_roll": 32,
    "left_hip_pitch": 33,
    "left_knee": 34,
    "left_ankle": 35,
    # Right leg
    "right_hip_roll": 42,
    "right_hip_pitch": 43,
    "right_knee": 44,
    "right_ankle": 45,
}


class StepSequenceController:
    """Controller to demonstrate complete stepping sequence."""

    def __init__(self):
        # Left leg angles
        self.left_hip_roll = 0.0
        self.left_hip_pitch = 0.0
        self.left_knee = 0.0
        self.left_ankle = 0.0

        # Right leg angles
        self.right_hip_roll = 0.0
        self.right_hip_pitch = 0.0
        self.right_knee = 0.0
        self.right_ankle = 0.0

        # Demo states
        self.current_demo = 0
        self.demos = [
            ("1. Initial ready pose (15-30-15)", self._ready_pose),
            ("2. Shift weight to left leg", self._weight_shift_left),
            ("3. Begin lifting right leg", self._lift_right),
            ("4. Right leg forward swing", self._swing_right),
            ("5. Right leg touch down", self._touch_down_right),
            ("6. Transfer weight forward", self._weight_transfer),
            ("7. Back to ready pose", self._ready_pose),
        ]

    def _ready_pose(self):
        """Basic 15-30-15 ready position."""
        # Left leg
        self.left_hip_roll = 0.0
        self.left_hip_pitch = math.radians(15)
        self.left_knee = math.radians(30)
        self.left_ankle = math.radians(15)

        # Right leg (mirror)
        self.right_hip_roll = 0.0
        self.right_hip_pitch = math.radians(15)
        self.right_knee = math.radians(30)
        self.right_ankle = math.radians(15)

        logger.info("Ready pose - stable but prepared for movement")

    def _weight_shift_left(self):
        """Shift weight to left leg using hip roll."""
        # Left leg (stance)
        self.left_hip_roll = math.radians(-10)  # Roll left
        self.left_hip_pitch = math.radians(15)
        self.left_knee = math.radians(35)  # Slightly more bend for weight
        self.left_ankle = math.radians(15)

        # Right leg (about to lift)
        self.right_hip_roll = math.radians(-10)  # Follow left roll
        self.right_hip_pitch = math.radians(15)
        self.right_knee = math.radians(30)
        self.right_ankle = math.radians(15)

        logger.info("Weight shifted left - ZMP moves to left foot")

    def _lift_right(self):
        """Begin lifting right leg."""
        # Left leg (stance)
        self.left_hip_roll = math.radians(-10)
        self.left_hip_pitch = math.radians(15)
        self.left_knee = math.radians(35)
        self.left_ankle = math.radians(15)

        # Right leg (lifting)
        self.right_hip_roll = math.radians(-10)
        self.right_hip_pitch = math.radians(20)  # More forward pitch
        self.right_knee = math.radians(45)  # More bend to lift
        self.right_ankle = math.radians(15)

        logger.info("Right leg lifting - maintaining ZMP on left foot")

    def _swing_right(self):
        """Swing right leg forward."""
        # Left leg (stance)
        self.left_hip_roll = math.radians(-10)
        self.left_hip_pitch = math.radians(15)
        self.left_knee = math.radians(35)
        self.left_ankle = math.radians(20)  # More ankle for balance

        # Right leg (swinging)
        self.right_hip_roll = math.radians(-10)
        self.right_hip_pitch = math.radians(30)  # Full forward swing
        self.right_knee = math.radians(45)
        self.right_ankle = math.radians(15)

        logger.info("Right leg swinging - dynamic balance needed")

    def _touch_down_right(self):
        """Right leg touches down in front."""
        # Left leg (stance)
        self.left_hip_roll = math.radians(-5)  # Reducing roll
        self.left_hip_pitch = math.radians(15)
        self.left_knee = math.radians(35)
        self.left_ankle = math.radians(20)

        # Right leg (landing)
        self.right_hip_roll = math.radians(-5)
        self.right_hip_pitch = math.radians(25)  # Extended forward
        self.right_knee = math.radians(30)  # Straightening
        self.right_ankle = math.radians(15)

        logger.info("Right foot touchdown - preparing for weight transfer")

    def _weight_transfer(self):
        """Transfer weight to right foot."""
        # Left leg (pushing off)
        self.left_hip_roll = 0.0
        self.left_hip_pitch = math.radians(20)  # Push off
        self.left_knee = math.radians(25)
        self.left_ankle = math.radians(25)  # Ankle push

        # Right leg (receiving weight)
        self.right_hip_roll = 0.0
        self.right_hip_pitch = math.radians(15)
        self.right_knee = math.radians(35)  # Absorb weight
        self.right_ankle = math.radians(15)

        logger.info("Weight transferring forward - ZMP moves to right foot")

    def next_demo(self):
        """Move to next demonstration."""
        if self.current_demo < len(self.demos):
            name, demo_func = self.demos[self.current_demo]
            logger.info(f"\n=== {name} ===")
            logger.info("Press Enter to continue...")
            input()
            demo_func()
            self.current_demo += 1
            return True
        return False

    def get_joint_angles(self):
        """Convert internal angles to robot's convention."""
        return {
            "left_hip_roll": self.left_hip_roll,
            "left_hip_pitch": -self.left_hip_pitch,  # Negative for left side
            "left_knee": self.left_knee,
            "left_ankle": self.left_ankle,
            "right_hip_roll": self.right_hip_roll,
            "right_hip_pitch": self.right_hip_pitch,
            "right_knee": -self.right_knee,  # Negative for right side
            "right_ankle": -self.right_ankle,  # Negative for right side
        }


async def run_robot(kos: KOS, controller: StepSequenceController) -> None:
    """Run the stepping sequence demo on the robot."""
    # Configure actuators
    for actuator_id in ACTUATOR_MAPPING.values():
        await kos.actuator.configure_actuator(
            actuator_id=actuator_id,
            kp=150,
            kd=15,
            max_torque=100,
            torque_enabled=True,
        )

    # Start at zero position
    zero_pose = [{"actuator_id": id, "position": 0} for id in ACTUATOR_MAPPING.values()]
    await kos.actuator.command_actuators(zero_pose)
    await asyncio.sleep(2)

    logger.info("\n=== Starting Step Sequence Demo ===")
    logger.info("This demo shows all the phases needed for a complete step")
    logger.info("including weight shifts, leg lift, and forward transfer.")
    logger.info("\nPress Enter to start...")
    input()

    # Main demo loop
    while controller.next_demo():
        # Convert angles to commands
        commands = []
        angles_dict = controller.get_joint_angles()
        for joint_name, angle_radians in angles_dict.items():
            if joint_name in ACTUATOR_MAPPING:
                actuator_id = ACTUATOR_MAPPING[joint_name]
                angle_degrees = math.degrees(angle_radians)
                commands.append({"actuator_id": actuator_id, "position": angle_degrees})
                logger.info(f"{joint_name}: {angle_degrees:.1f}°")

        # Send commands
        if commands:
            await kos.actuator.command_actuators(commands)
            await asyncio.sleep(0.5)  # Give time for movement

    logger.info("\n=== Demo Complete! ===")


async def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--sim-host", type=str, default="localhost")
    parser.add_argument("--port", type=int, default=50051)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    colorlogging.configure(level=logging.DEBUG if args.debug else logging.INFO)
    controller = StepSequenceController()

    async with KOS(ip=args.sim_host, port=args.port) as sim_kos:
        await sim_kos.sim.reset()
        await run_robot(sim_kos, controller)


if __name__ == "__main__":
    asyncio.run(main())
