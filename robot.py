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
                actuator_id=actuator_id, kp=32, kd=32, max_torque=80, torque_enabled=True
            )

    async def homing_actuators(self):
        for actuator_id in JOINT_TO_ID.values():
            logger.info(f"Setting actuator {actuator_id} to 0 position")
            await self.kos.actuator.command_actuators([{"actuator_id": actuator_id, "position": 0}])

    async def send_commands(self, commands):
        if commands:
            await self.kos.actuator.command_actuators(commands)
