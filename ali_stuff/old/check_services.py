import asyncio
from demos.robot import RobotInterface
from loguru import logger

async def main():
    robot = RobotInterface(ip="10.33.11.170")
    
    try:
        async with robot:
            # Print available services and methods
            logger.info("Available KOS services:")
            for service in dir(robot.kos):
                if not service.startswith('_'):
                    logger.info(f"- {service}")
            
            # Try to get version info if available
            try:
                version = await robot.kos.process_manager.get_version()
                logger.info(f"KOS Version: {version}")
            except Exception as e:
                logger.error(f"Could not get version: {e}")

    except Exception as e:
        logger.error(f"Error: {e}")
        logger.error("Traceback:", exc_info=True)

if __name__ == "__main__":
    asyncio.run(main()) 