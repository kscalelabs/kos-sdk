import tests
import asyncio
from utils.robot import RobotInterface

robot = RobotInterface("10.33.10.65")

async def main():
    await tests.led.test_led(robot.ip)
    await tests.connection.test_connection(robot.ip)
    await tests.servos.test_actuator_movement(robot.ip)

if __name__ == "__main__":
    asyncio.run(main())