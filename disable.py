from robot import RobotInterface
import asyncio


async def main():
    async with RobotInterface(ip="10.33.11.170") as robot:
        await robot.disable_all_torque()
        print("Torque disabled")


if __name__ == "__main__":
    asyncio.run(main())
