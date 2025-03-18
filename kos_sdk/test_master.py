import tests
import asyncio
from utils.robot import RobotInterface
from loguru import logger

robot = RobotInterface(ip="10.33.10.65")


async def main():
    test_functions = [
        ("Connection Test", tests.connection.test_connection, [robot.ip]),
        ("Actuator Connection Test", tests.actuators_connection.test_actuator_connection, [robot.ip]),
        ("LED Test", tests.led.test_led, [robot.ip]),
        ("Actuator Movement Test", tests.servos.test_actuator_movement, [robot.ip]),
        ("IMU Data Test", tests.imu.plot_imu_data, [robot.ip, 2]),
    ]

    for test_name, test_func, args in test_functions:
        logger.info(f"Running {test_name}...")
        try:
            result = await test_func(*args)

            # Check if the test returned a dictionary with a success field
            if isinstance(result, dict) and "success" in result and not result["success"]:
                logger.error(f"{test_name} failed: {result.get('error', 'Unknown error')}")
                logger.error(f"Test suite stopped due to failure in {test_name}")
                return

            logger.success(f"{test_name} completed successfully")
        except Exception as e:
            logger.error(f"{test_name} failed with exception: {e}")
            logger.error(f"Test suite stopped due to failure in {test_name}")
            return

    logger.success("All tests completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())
