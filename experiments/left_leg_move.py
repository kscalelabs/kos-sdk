import asyncio
import subprocess
import time
import logging
import json
from dataclasses import dataclass
from typing import List, Dict
import numpy as np
from pykos import KOS
import argparse

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


@dataclass
class LegPosition:
    # Left leg
    left_hip_yaw: float
    left_hip_roll: float
    left_hip_pitch: float
    left_knee: float
    left_ankle: float
    # Right leg
    right_hip_yaw: float
    right_hip_roll: float
    right_hip_pitch: float
    right_knee: float
    right_ankle: float
    # Score for this position
    score: float = 0.0

    def to_dict(self):
        return {
            "left_hip_yaw": self.left_hip_yaw,
            "left_hip_roll": self.left_hip_roll,
            "left_hip_pitch": self.left_hip_pitch,
            "left_knee": self.left_knee,
            "left_ankle": self.left_ankle,
            "right_hip_yaw": self.right_hip_yaw,
            "right_hip_roll": self.right_hip_roll,
            "right_hip_pitch": self.right_hip_pitch,
            "right_knee": self.right_knee,
            "right_ankle": self.right_ankle,
            "score": self.score,
        }

    @classmethod
    def from_dict(cls, d):
        return cls(**d)


class DualLegTester:
    def __init__(self, kos: KOS):
        self.kos = kos
        self.best_positions: List[LegPosition] = []
        self.test_results_file = "dual_leg_results.json"

        # Actuator IDs
        self.actuator_map = {
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

    async def configure_all_actuators(self):
        """Configure all actuators with proper parameters."""
        for actuator_id in self.actuator_map.values():
            logger.info(f"Configuring actuator {actuator_id}")
            await self.kos.actuator.configure_actuator(
                actuator_id=actuator_id,
                kp=32,
                kd=32,
                ki=0,
                # acceleration=100.0,
                max_torque=95,
                protective_torque=90,
                protection_time=1.0,
                torque_enabled=True,
            )

    def load_previous_results(self):
        """Load previously saved good positions."""
        try:
            with open(self.test_results_file, "r") as f:
                data = json.load(f)
                self.best_positions = [LegPosition.from_dict(d) for d in data]
                logger.info(f"Loaded {len(self.best_positions)} previous positions")
        except FileNotFoundError:
            logger.info("No previous results found")

    def save_results(self):
        """Save current best positions to file."""
        with open(self.test_results_file, "w") as f:
            json.dump([pos.to_dict() for pos in self.best_positions], f, indent=2)

    async def test_variation(
        self, base_position: LegPosition, param_name: str, variation: float
    ) -> LegPosition:
        """Test a variation of a single parameter."""
        new_position = LegPosition(**base_position.to_dict())
        setattr(
            new_position, param_name, getattr(base_position, param_name) + variation
        )

        commands = []
        for joint_name, actuator_id in self.actuator_map.items():
            commands.append(
                {
                    "actuator_id": actuator_id,
                    "position": getattr(new_position, joint_name),
                    "velocity": 50.0,  # Add controlled velocity
                }
            )

        try:
            await self.kos.actuator.command_actuators(commands)
            logger.info(f"\nTesting variation of {param_name} by {variation:.1f}°")
            await asyncio.sleep(1.0)  # Let position stabilize

            while True:
                rating = input("Rate this position (0-10, or 'q' to quit): ")
                if rating.lower() == "q":
                    return None
                try:
                    score = float(rating)
                    if 0 <= score <= 10:
                        new_position.score = score
                        return new_position
                except ValueError:
                    pass
                print("Please enter a number between 0 and 10")

        except Exception as e:
            logger.error(f"Error testing position: {str(e)}")
            return None

    async def interpolate_between_positions(
        self, start_pos: LegPosition, end_pos: LegPosition, steps: int = 50
    ):
        """Create smooth transition between positions using minimum jerk trajectory."""
        for i in range(steps + 1):
            t = i / steps
            # Minimum jerk trajectory for smooth motion
            smooth_t = t * t * t * (10 - 15 * t + 6 * t * t)

            commands = []
            for joint_name, actuator_id in self.actuator_map.items():
                start_val = getattr(start_pos, joint_name)
                end_val = getattr(end_pos, joint_name)
                current_pos = start_val + smooth_t * (end_val - start_val)

                # Calculate velocity based on position change
                if i < steps:
                    next_t = (i + 1) / steps
                    next_smooth_t = (
                        next_t
                        * next_t
                        * next_t
                        * (10 - 15 * next_t + 6 * next_t * next_t)
                    )
                    next_pos = start_val + next_smooth_t * (end_val - start_val)
                    velocity = (
                        abs(next_pos - current_pos) / 0.02
                    )  # 0.02s is our time step
                else:
                    velocity = 0

                commands.append(
                    {
                        "actuator_id": actuator_id,
                        "position": current_pos,
                        "velocity": velocity,
                    }
                )

            await self.kos.actuator.command_actuators(commands)
            await asyncio.sleep(0.02)


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

            tester = DualLegTester(kos)
            await tester.configure_all_actuators()
            tester.load_previous_results()

            # Start with your known working positions
            # Left leg forward step sequence
            base_positions = [
                LegPosition(
                    # Left leg lifted
                    left_hip_yaw=0,
                    left_hip_roll=-5,
                    left_hip_pitch=-30,
                    left_knee=16,
                    left_ankle=-13,
                    # Right leg supporting
                    right_hip_yaw=0,
                    right_hip_roll=0,
                    right_hip_pitch=0,
                    right_knee=0,
                    right_ankle=0,
                ),
                LegPosition(
                    # Left leg down and forward
                    left_hip_yaw=0,
                    left_hip_roll=-5,
                    left_hip_pitch=-20,
                    left_knee=16,
                    left_ankle=-10,
                    # Right leg adjusting
                    right_hip_yaw=0,
                    right_hip_roll=0,
                    right_hip_pitch=0,
                    right_knee=5,
                    right_ankle=0,
                ),
                # Add more positions from your working sequence...
            ]

            # Test variations around each position
            for base_pos in base_positions:
                logger.info("\nTesting variations around position:")
                for param in base_pos.to_dict().keys():
                    if param != "score":
                        variations = np.linspace(-5, 5, 5)  # Test ±5° in 5 steps
                        for variation in variations:
                            result = await tester.test_variation(
                                base_pos, param, variation
                            )
                            if result is None:
                                return  # User quit
                            if result.score >= 7.0:
                                tester.best_positions.append(result)
                                tester.save_results()
                                logger.info(f"Saved position with score {result.score}")

            # Test transitions between good positions
            if len(tester.best_positions) >= 2:
                logger.info("\nTesting transitions between best positions")
                for i in range(len(tester.best_positions) - 1):
                    await tester.interpolate_between_positions(
                        tester.best_positions[i], tester.best_positions[i + 1]
                    )
                    input("Press Enter to continue to next transition...")

    finally:
        if sim_process:
            logger.info("Stopping simulator...")
            sim_process.terminate()
            sim_process.wait()


if __name__ == "__main__":
    asyncio.run(main())
