"""Script to demonstrate how hip pitch, knee, and ankle joints work together."""

import argparse
import asyncio
import logging
import time
import math
import colorlogging
from pykos import KOS

logger = logging.getLogger(__name__)

# We only care about one leg's joints for this demo
ACTUATOR_MAPPING = {
    "hip_pitch": 33,  # left hip pitch
    "knee": 34,  # left knee
    "ankle": 35,  # left ankle
}


class SingleLegController:
    """Controller to demonstrate leg geometry with just hip, knee, and ankle."""

    def __init__(self):
        self.cycle_length = 400  # Very slow for demonstration
        self.cycle_counter = 0

        # Current joint angles in radians
        self.hip_pitch = 0.0
        self.knee = 0.0
        self.ankle = 0.0

        # Demo modes
        self.demo_modes = [
            self._knee_bend_demo,  # Just bend knee, compensate with hip
            self._ankle_parallel_demo,  # Keep foot parallel while moving
            self._forward_step_demo,  # Basic forward step motion
        ]
        self.current_mode = 0
        self.mode_name = "knee_bend"

    def _knee_bend_demo(self, phase):
        """Demonstrate how hip compensates for knee bend to keep torso upright."""
        # Knee bends from 0° to 45° and back
        self.knee = math.radians(45 * math.sin(phase))
        # Hip compensates with half the angle to keep torso upright
        self.hip_pitch = -self.knee * 0.5
        # Ankle stays fixed
        self.ankle = math.radians(0)

        if self.cycle_counter % 20 == 0:
            logger.info(f"\nKnee Bend Demo - Phase: {phase:.2f}")
            logger.info(f"Knee: {math.degrees(self.knee):.1f}°")
            logger.info(f"Hip: {math.degrees(self.hip_pitch):.1f}°")
            logger.info(f"Ankle: {math.degrees(self.ankle):.1f}°")

    def _ankle_parallel_demo(self, phase):
        """Demonstrate keeping foot parallel to ground while moving leg."""
        # Knee bends
        self.knee = math.radians(30 * math.sin(phase))
        # Hip moves opposite to knee
        self.hip_pitch = -self.knee
        # Ankle compensates to keep foot parallel
        self.ankle = self.knee - self.hip_pitch

        if self.cycle_counter % 20 == 0:
            logger.info(f"\nParallel Foot Demo - Phase: {phase:.2f}")
            logger.info(f"Knee: {math.degrees(self.knee):.1f}°")
            logger.info(f"Hip: {math.degrees(self.hip_pitch):.1f}°")
            logger.info(f"Ankle: {math.degrees(self.ankle):.1f}°")

    def _forward_step_demo(self, phase):
        """Demonstrate basic forward step motion."""
        # Knee bends more in middle of motion
        self.knee = math.radians(45 * math.sin(phase))
        # Hip moves forward as knee straightens
        self.hip_pitch = math.radians(20 * math.cos(phase))
        # Ankle keeps foot parallel to ground
        self.ankle = self.knee - self.hip_pitch

        if self.cycle_counter % 20 == 0:
            logger.info(f"\nForward Step Demo - Phase: {phase:.2f}")
            logger.info(f"Knee: {math.degrees(self.knee):.1f}°")
            logger.info(f"Hip: {math.degrees(self.hip_pitch):.1f}°")
            logger.info(f"Ankle: {math.degrees(self.ankle):.1f}°")

    def update(self):
        """Update joint angles based on current demo mode."""
        # Calculate phase (0 to 2π)
        phase = (2.0 * math.pi * self.cycle_counter) / self.cycle_length

        # Run current demo mode
        self.demo_modes[self.current_mode](phase)

        # Switch demo mode every cycle
        if self.cycle_counter % self.cycle_length == 0:
            self.current_mode = (self.current_mode + 1) % len(self.demo_modes)
            if self.current_mode == 0:
                logger.info("\n=== Knee Bend Demo ===")
            elif self.current_mode == 1:
                logger.info("\n=== Parallel Foot Demo ===")
            else:
                logger.info("\n=== Forward Step Demo ===")

        self.cycle_counter += 1

    def get_joint_angles(self):
        """Convert internal angles to robot's convention."""
        return {
            "hip_pitch": -self.hip_pitch,  # Negative for left side
            "knee": self.knee,
            "ankle": self.ankle,
        }


async def run_robot(kos: KOS, controller: SingleLegController, dt: float, is_real: bool) -> None:
    """Run the leg geometry demo on a robot."""
    # Configure actuators
    for actuator_id in ACTUATOR_MAPPING.values():
        if is_real:
            kp, kd = 50, 100
        else:
            kp, kd = 150, 15

        await kos.actuator.configure_actuator(
            actuator_id=actuator_id,
            kp=kp,
            kd=kd,
            max_torque=100,
            torque_enabled=True,
        )

    # Start at zero position
    zero_pose = [{"actuator_id": id, "position": 0} for id in ACTUATOR_MAPPING.values()]
    await kos.actuator.command_actuators(zero_pose)
    await asyncio.sleep(2)

    logger.info("\n=== Starting Leg Geometry Demo ===")
    logger.info("=== Knee Bend Demo ===")

    # Main control loop
    while True:
        # Update controller
        controller.update()

        # Convert angles to commands
        commands = []
        angles_dict = controller.get_joint_angles()
        for joint_name, angle_radians in angles_dict.items():
            if joint_name in ACTUATOR_MAPPING:
                actuator_id = ACTUATOR_MAPPING[joint_name]
                angle_degrees = math.degrees(angle_radians)
                commands.append({"actuator_id": actuator_id, "position": angle_degrees})

        # Send commands
        if commands:
            await kos.actuator.command_actuators(commands)

        await asyncio.sleep(dt)


async def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--sim-host", type=str, default="localhost")
    parser.add_argument("--port", type=int, default=50051)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    colorlogging.configure(level=logging.DEBUG if args.debug else logging.INFO)
    controller = SingleLegController()

    async with KOS(ip=args.sim_host, port=args.port) as sim_kos:
        await sim_kos.sim.reset()
        sim_task = asyncio.create_task(run_robot(sim_kos, controller, 0.002, False))

        try:
            while True:
                await asyncio.sleep(0.1)
        except KeyboardInterrupt:
            logger.info("\n=== Demo stopped by user ===")
            sim_task.cancel()
            try:
                await sim_task
            except asyncio.CancelledError:
                pass


if __name__ == "__main__":
    asyncio.run(main())
