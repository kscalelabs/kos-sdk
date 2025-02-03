import asyncio
from demos.robot import RobotInterface
from loguru import logger

async def main():
    robot = RobotInterface(ip="10.33.11.170")
    
    try:
        async with robot:
            logger.info("Checking inference service capabilities...")
            
            # Print all available methods
            logger.info("Available inference methods:")
            for method in dir(robot.kos.inference):
                if not method.startswith('_'):
                    logger.info(f"- {method}")
            
            # Try to get service info
            try:
                logger.info("\nTrying to get inference service info...")
                logger.info(robot.kos.inference.stub)
            except Exception as e:
                logger.error(f"Error accessing inference service: {e}")

    except Exception as e:
        logger.error(f"Error: {e}")
        logger.error("Traceback:", exc_info=True)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Program terminated by user") 