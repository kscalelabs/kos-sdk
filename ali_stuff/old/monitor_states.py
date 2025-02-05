import asyncio
from robot import RobotInterface
from loguru import logger

async def main():
    robot = RobotInterface(ip="10.33.11.170")
    
    try:
        async with robot:
            while True:
                positions = await robot.get_feedback_positions()
                logger.info("\nCurrent Joint Positions:")
                for joint_name, position in positions.items():
                    logger.info(f"{joint_name}: {position:.2f} degrees")
                
                await asyncio.sleep(0.1)  # Read every 100ms
                
    except KeyboardInterrupt:
        logger.info("Monitoring stopped by user")
    except ConnectionError as e:
        logger.error(f"Connection failed: {e}")
    except Exception as e:
        logger.error(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main()) 