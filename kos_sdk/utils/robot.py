"""Interface for the robot."""

import subprocess
from typing import Any, Dict, Union

from loguru import logger
from pykos import KOS
from sdk.utils.unit_types import Degree

JOINT_TO_ID = {
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
            logger.info("Enabling torque for actuator...")
            await self.kos.actuator.configure_actuator(
                actuator_id=actuator_id, kp=32, kd=32, torque_enabled=True
            )
            logger.success(f"Successfully enabled torque for actuator {actuator_id}")

    async def configure_actuators_record(self) -> None:
        logger.info("Enabling soft torque for actuator...")
        for actuator_id in JOINT_TO_ID.values():
            await self.kos.actuator.configure_actuator(
                actuator_id=actuator_id, torque_enabled=False
            )
            logger.success(f"Successfully enabled torque for actuator {actuator_id}")

    async def homing_actuators(self) -> None:
        for actuator_id in JOINT_TO_ID.values():
            logger.info(f"Setting actuator {actuator_id} to 0 position")
            await self.kos.actuator.command_actuators([{"actuator_id": actuator_id, "position": 0}])
            logger.success(f"Successfully set actuator {actuator_id} to 0 position")

    async def set_real_command_positions(self, positions: Dict[str, Union[int, Degree]]) -> None:
        await self.kos.actuator.command_actuators(
            [{"actuator_id": JOINT_TO_ID[name], "position": pos} for name, pos in positions.items()]
        )

    async def get_feedback_state(self) -> Any:
        return await self.kos.actuator.get_actuators_state(list(JOINT_TO_ID.values()))

    async def get_feedback_positions(self) -> Dict[str, Union[int, Degree]]:
        feedback_state = await self.get_feedback_state()
        return {ID_TO_JOINT[state.actuator_id]: state.position for state in feedback_state.states}
