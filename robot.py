from pykos import KOS
from loguru import logger

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


class RobotInterface:
    def __init__(self, ip):
        self.ip = ip

    async def __aenter__(self):
        self.kos = KOS(ip=self.ip)
        await self.kos.__aenter__()
        return self

    async def __aexit__(self, *args):
        await self.kos.__aexit__(*args)

    async def configure_actuators(self):
        for actuator_id in JOINT_TO_ID.values():
            logger.info(f"Enabling torque for actuator {actuator_id}")
            await self.kos.actuator.configure_actuator(
                actuator_id=actuator_id, kp=32, kd=32, torque_enabled=True
            )

    async def homing_actuators(self):
        for actuator_id in JOINT_TO_ID.values():
            logger.info(f"Setting actuator {actuator_id} to 0 position")
            await self.kos.actuator.command_actuators([{"actuator_id": actuator_id, "position": 0}])

    async def command_positions(self, positions):
        if positions:
            await self.kos.actuator.command_actuators(positions)

    async def feedback_state(self):
        return await self.kos.actuator.get_actuators_state(list(JOINT_TO_ID.values()))

    async def feedback_positions(self):
        feedback_state = await self.feedback_state()
        return [state.position for state in feedback_state.states]