from robot import RobotInterface
import asyncio


async def main():
    robot = RobotInterface(ip="10.33.11.170")  # Default IP from run.py
    async with robot:
        await robot.disable_all_torque()
        print("All torque disabled")


if __name__ == "__main__":
    asyncio.run(main())
