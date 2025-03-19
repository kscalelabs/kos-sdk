import asyncio
from dataclasses import dataclass
from typing import Any, Callable, List

from loguru import logger

from kos_sdk.tests import actuators_connection, connection, imu, led, servos
from kos_sdk.utils.robot import RobotInterface


@dataclass
class Test:
    name: str
    func: Callable
    args: List[Any]
    enabled: bool = True


robot = RobotInterface(ip="10.33.10.65")


async def run_test(test: Test) -> Any:
    """Run a test function, handling both sync and async functions."""
    if not test.enabled:
        logger.info(f"Skipping disabled test: {test.name}")
        return {"success": True, "skipped": True}

    logger.info(f"Running {test.name}...")
    try:
        if asyncio.iscoroutinefunction(test.func):
            result = await test.func(*test.args)
        else:
            result = test.func(*test.args)

        if isinstance(result, dict) and "success" in result and not result["success"]:
            logger.error(f"{test.name} failed: {result.get('error', 'Unknown error')}")
            return result

        logger.success(f"{test.name} completed successfully")
        return result
    except Exception as e:
        logger.error(f"{test.name} failed with exception: {e}")
        return {"success": False, "error": str(e)}


async def main() -> None:
    tests = [
        Test("Connection Test", connection.test_connection, [robot.ip]),
        Test("Actuator Connection Test", actuators_connection.test_actuator_connection, [robot.ip]),
        Test("LED Test", led.test_led, [robot.ip]),
        Test("Actuator Movement Test", servos.test_actuator_movement, [robot.ip]),
        Test("IMU Test", imu.plot_imu_data, [robot.ip]),
    ]

    for test in tests:
        result = await run_test(test)
        if isinstance(result, dict) and not result.get("success", True):
            logger.error(f"Test suite stopped due to failure in {test.name}")
            return

    logger.success("All tests completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())
