import asyncio
from typing import Callable, List

from loguru import logger

from kos_sdk.tests import actuators_connection, connection, imu, led, servos
from kos_sdk.utils.robot import RobotInterface

robot = RobotInterface(ip="10.33.10.65")


async def main() -> None:
    test_functions: List[tuple[str, Callable, list]] = [
        ("Connection Test", connection.test_connection, [robot.ip]),
        ("Actuator Connection Test", actuators_connection.test_actuator_connection, [robot.ip]),
        ("LED Test", led.test_led, [robot.ip]),
        ("Actuator Movement Test", servos.test_actuator_movement, [robot.ip]),
        ("IMU Test", imu.plot_imu_data, [robot.ip]),
    ]

    for test_name, test_func, args in test_functions:
        logger.info(f"Running {test_name}...")
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func(*args)
            else:
                result = test_func(*args)

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
