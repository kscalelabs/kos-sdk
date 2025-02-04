from pykos import KOS

from unit_types import Degree
from typing import Any, Dict, Union, List

import subprocess
from loguru import logger
import click
import asyncio

# Mapping between human-readable joint names and their actuator IDs
JOINT_TO_ID = {
    # Left arm
    "left_shoulder_yaw": 11,
    "left_shoulder_pitch": 12,
    "left_elbow": 13,
    "left_gripper": 14,
    # Right arm
    "right_shoulder_yaw": 21,
    "right_shoulder_pitch": 22,
    "right_elbow": 23,
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

# Reverse mapping from ID to joint name for feedback processing
ID_TO_JOINT = {v: k for k, v in JOINT_TO_ID.items()}

# Group definitions for easier control
ARM_JOINTS = [
    "left_shoulder_yaw",
    "left_shoulder_pitch",
    "left_elbow",
    "left_gripper",
    "right_shoulder_yaw",
    "right_shoulder_pitch",
    "right_elbow",
    "right_gripper",
]

LEG_JOINTS = [
    "left_hip_yaw",
    "left_hip_roll",
    "left_hip_pitch",
    "left_knee",
    "left_ankle",
    "right_hip_yaw",
    "right_hip_roll",
    "right_hip_pitch",
    "right_knee",
    "right_ankle",
]


class RobotInterface:
    """
    Interface to the physical robot using PyKOS.
    Handles connection, configuration, and command sending.
    """

    def __init__(self, ip: str) -> None:
        """
        Initialize robot interface.

        Args:
            ip: IP address of the robot
        """
        self.ip: str = ip

    async def __aenter__(self) -> "RobotInterface":
        """
        Context manager entry - establishes connection to robot.
        Verifies connection and initializes KOS interface.
        """
        self.check_connection()
        self.kos = KOS(ip=self.ip)
        await self.kos.__aenter__()
        return self

    async def __aexit__(self, *args: Any) -> None:
        """
        Context manager exit - closes connection cleanly.
        """
        await self.kos.__aexit__(*args)

    def check_connection(self) -> None:
        """
        Verify robot is reachable via ping before attempting connection.
        Raises ConnectionError if robot cannot be reached.
        """
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

    async def enable_torque(
        self, joints: Union[List[str], List[int]], kp: int = 32, kd: int = 32
    ) -> None:
        """
        Enable torque for specified joints or actuator IDs.

        Args:
            joints: List of joint names or actuator IDs
            kp: Proportional gain for PID control
            kd: Derivative gain for PID control
        """
        actuator_ids = []
        for joint in joints:
            if isinstance(joint, str):
                if joint in JOINT_TO_ID:
                    actuator_ids.append(JOINT_TO_ID[joint])
            else:
                actuator_ids.append(joint)

        for actuator_id in actuator_ids:
            logger.info(f"Enabling torque for actuator {actuator_id}...")
            await self.kos.actuator.configure_actuator(
                actuator_id=actuator_id, kp=kp, kd=kd, torque_enabled=True
            )
            logger.success(f"Successfully enabled torque for actuator {actuator_id}")

    async def disable_torque(self, joints: Union[List[str], List[int]]) -> None:
        """
        Disable torque for specified joints or actuator IDs.

        Args:
            joints: List of joint names or actuator IDs
        """
        actuator_ids = []
        for joint in joints:
            if isinstance(joint, str):
                if joint in JOINT_TO_ID:
                    actuator_ids.append(JOINT_TO_ID[joint])
            else:
                actuator_ids.append(joint)

        for actuator_id in actuator_ids:
            logger.info(f"Disabling torque for actuator {actuator_id}...")
            await self.kos.actuator.configure_actuator(
                actuator_id=actuator_id, kp=0, kd=0, torque_enabled=False
            )
            logger.success(f"Successfully disabled torque for actuator {actuator_id}")

    async def enable_all_torque(self, kp: int = 32, kd: int = 32) -> None:
        """Enable torque for all actuators"""
        await self.enable_torque(list(JOINT_TO_ID.keys()), kp, kd)

    async def disable_all_torque(self) -> None:
        """Disable torque for all actuators"""
        await self.disable_torque(list(JOINT_TO_ID.keys()))

    async def enable_arms_torque(self, kp: int = 32, kd: int = 32) -> None:
        """Enable torque for arm joints only"""
        await self.enable_torque(ARM_JOINTS, kp, kd)

    async def disable_arms_torque(self) -> None:
        """Disable torque for arm joints only"""
        await self.disable_torque(ARM_JOINTS)

    async def enable_legs_torque(self, kp: int = 32, kd: int = 32) -> None:
        """Enable torque for leg joints only"""
        await self.enable_torque(LEG_JOINTS, kp, kd)

    async def disable_legs_torque(self) -> None:
        """Disable torque for leg joints only"""
        await self.disable_torque(LEG_JOINTS)

    async def homing_actuators(self) -> None:
        """
        Set all actuators to their zero position.
        This is the 'home' or 'neutral' stance of the robot.
        """
        for actuator_id in JOINT_TO_ID.values():
            logger.info(f"Setting actuator {actuator_id} to 0 position")
            await self.kos.actuator.command_actuators(
                [{"actuator_id": actuator_id, "position": 0}]
            )
            logger.success(f"Successfully set actuator {actuator_id} to 0 position")

    async def set_real_command_positions(
        self, positions: Dict[str, Union[int, Degree]]
    ) -> None:
        """
        Send position commands to actuators.

        Args:
            positions: Dictionary mapping joint names to target positions
        """
        await self.kos.actuator.command_actuators(
            [
                {"actuator_id": JOINT_TO_ID[name], "position": pos}
                for name, pos in positions.items()
            ]
        )

    async def get_feedback_state(self) -> Any:
        """
        Get raw state feedback from all actuators.
        Returns full actuator state including position, velocity, etc.
        """
        return await self.kos.actuator.get_actuators_state(list(JOINT_TO_ID.values()))

    async def get_feedback_positions(self) -> Dict[str, Union[int, Degree]]:
        """
        Get current position of all joints.
        Returns dictionary mapping joint names to their current positions.
        """
        feedback_state = await self.get_feedback_state()
        return {
            ID_TO_JOINT[state.actuator_id]: state.position
            for state in feedback_state.states
        }

    async def zero_actuators(self, joints: Union[List[str], List[int]]) -> None:
        """
        Zero specific actuators using configure_actuators.
        This sets their zero position reference point.

        Args:
            joints: List of joint names or actuator IDs to zero
        """
        actuator_ids = []
        for joint in joints:
            if isinstance(joint, str):
                if joint in JOINT_TO_ID:
                    actuator_ids.append(JOINT_TO_ID[joint])
            else:
                actuator_ids.append(joint)

        for actuator_id in actuator_ids:
            logger.info(f"Zeroing actuator {actuator_id}...")
            await self.kos.actuator.configure_actuator(
                actuator_id=actuator_id, zero_position=True
            )
            logger.success(f"Successfully zeroed actuator {actuator_id}")

    async def zero_all_actuators(self) -> None:
        """Zero all actuators"""
        await self.zero_actuators(list(JOINT_TO_ID.keys()))

    async def zero_arms(self) -> None:
        """Zero arm joints only"""
        await self.zero_actuators(ARM_JOINTS)

    async def zero_legs(self) -> None:
        """Zero leg joints only"""
        await self.zero_actuators(LEG_JOINTS)
