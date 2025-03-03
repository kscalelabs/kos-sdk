from pykos import KOS

from unit_types import Degree
from typing import Any, Dict, Union

import subprocess
from loguru import logger
import asyncio

JOINT_TO_ID = {
    # Left arm
    "left_shoulder_yaw": 11,
    "left_shoulder_pitch": 12,
    "left_elbow_yaw": 13,
    "left_elbow": 13,  # Add alias for compatibility with recorded skills
    "left_gripper": 14,
    # Right arm
    "right_shoulder_yaw": 21,
    "right_shoulder_pitch": 22,
    "right_elbow_yaw": 23,
    "right_elbow": 23,  # Add alias for compatibility with recorded skills
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

ID_TO_JOINT = {v: k for k, v in JOINT_TO_ID.items()}


class RobotInterface:
    def __init__(self, ip: str) -> None:
        self.ip: str = ip

    async def __aenter__(self) -> "RobotInterface":
        self.check_connection()
        self.kos = KOS(ip=self.ip)
        await self.kos.__aenter__()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.kos.__aexit__(*args)

    def check_connection(self) -> None:
        try:
            logger.info(f"Pinging robot at {self.ip}")
            subprocess.run(
                ["ping", "-c", "1", self.ip],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
            )
            logger.success(f"Successfully pinged robot at {self.ip}")
        except subprocess.CalledProcessError:
            logger.error(f"Could not ping robot at {self.ip}")
            raise ConnectionError("Robot connection failed.")

    async def configure_actuators(self) -> None:
        for actuator_id in JOINT_TO_ID.values():
            logger.info(f"Enabling torque for actuator...")
            await self.kos.actuator.configure_actuator(
                actuator_id=actuator_id, kp=32, kd=32, torque_enabled=True
            )
            logger.success(f"Successfully enabled torque for actuator {actuator_id}")

    async def configure_actuators_record(self) -> None:
        logger.info(f"Enabling soft torque for actuator...")
        for actuator_id in JOINT_TO_ID.values():
            await self.kos.actuator.configure_actuator(
                actuator_id=actuator_id, torque_enabled=False
            )
            logger.success(f"Successfully enabled torque for actuator {actuator_id}")

    async def homing_actuators(self) -> None:
        """Set all actuators to position zero gradually to prevent abrupt movements."""
        # First ensure torque is enabled with lower gains for gentler movement
        logger.info("Enabling torque with reduced gains for gentle zeroing...")
        await self.enable_gentle_torque()

        # Get current positions
        current_positions = await self.get_feedback_positions()
        logger.info(f"Current positions before zeroing: {current_positions}")

        # Calculate steps for gradual movement (5 steps instead of 10)
        steps = 5
        step_delay = 0.15  # 150ms between steps instead of 300ms

        logger.info(f"Gradually moving to zero position in {steps} steps...")

        for step in range(1, steps + 1):
            # Calculate intermediate positions (step/steps of the way to zero)
            fraction = step / steps
            for joint_name, current_pos in current_positions.items():
                # Calculate target position for this step (moving toward zero)
                target_pos = current_pos * (1 - fraction)
                actuator_id = JOINT_TO_ID[joint_name]

                # Send command for this step
                await self.kos.actuator.command_actuators(
                    [{"actuator_id": actuator_id, "position": target_pos}]
                )

            # Wait for movement to complete before next step
            logger.info(
                f"Zeroing step {step}/{steps} complete - waiting for movement..."
            )
            await asyncio.sleep(step_delay)

        # Final step - set exactly to zero
        logger.info("Setting final zero position...")
        for actuator_id in JOINT_TO_ID.values():
            await self.kos.actuator.command_actuators(
                [{"actuator_id": actuator_id, "position": 0}]
            )

        logger.success("Gradual zeroing complete")

    async def enable_gentle_torque(self) -> None:
        """Enable torque with lower gains for gentler movement"""
        logger.info("Enabling gentle torque for all actuators...")
        for actuator_id in JOINT_TO_ID.values():
            await self.kos.actuator.configure_actuator(
                actuator_id=actuator_id,
                kp=16,  # Lower kp for gentler movement
                kd=16,  # Lower kd for gentler movement
                max_torque=50,  # Lower max torque
                torque_enabled=True,
            )
        logger.success("Successfully enabled gentle torque for all actuators")

    async def set_real_command_positions(
        self, positions: Dict[str, Union[int, Degree]]
    ) -> None:
        await self.kos.actuator.command_actuators(
            [
                {"actuator_id": JOINT_TO_ID[name], "position": pos}
                for name, pos in positions.items()
            ]
        )

    async def get_feedback_state(self) -> Any:
        return await self.kos.actuator.get_actuators_state(list(JOINT_TO_ID.values()))

    async def get_feedback_positions(self) -> Dict[str, Union[int, Degree]]:
        feedback_state = await self.get_feedback_state()
        return {
            ID_TO_JOINT[state.actuator_id]: state.position
            for state in feedback_state.states
        }

    async def disable_all_torque(self) -> None:
        """Disable torque for all actuators"""
        logger.info("Disabling torque for all actuators...")
        for actuator_id in JOINT_TO_ID.values():
            await self.kos.actuator.configure_actuator(
                actuator_id=actuator_id, kp=32, kd=50, torque_enabled=False
            )
        logger.success("Successfully disabled torque for all actuators")

    async def enable_all_torque(self) -> None:
        """Enable torque for all actuators"""
        logger.info("Enabling torque for all actuators...")
        for actuator_id in JOINT_TO_ID.values():
            await self.kos.actuator.configure_actuator(
                actuator_id=actuator_id,
                kp=32,
                kd=32,
                max_torque=90,
                torque_enabled=True,
            )
        logger.success("Successfully enabled torque for all actuators")

    async def zero_and_disable(self) -> None:
        """Set all actuators to position zero, then disable torque"""
        logger.info("Setting all actuators to position zero...")
        await self.homing_actuators()
        logger.info("Waiting for actuators to reach zero position...")
        await asyncio.sleep(3)  # Give time for actuators to reach position
        logger.info("Disabling torque...")
        await self.disable_all_torque()
        logger.success("All actuators set to zero and torque disabled")
