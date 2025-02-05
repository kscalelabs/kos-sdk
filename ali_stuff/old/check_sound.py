import asyncio
from demos.robot import RobotInterface
from loguru import logger

async def main():
    robot = RobotInterface(ip="10.33.11.170")
    
    try:
        async with robot:
            logger.info("Sound service details:")
            # Print all methods of the sound service
            logger.info("Methods:")
            for method in dir(robot.kos.sound):
                if not method.startswith('_'):
                    logger.info(f"- {method}")
            
            # Try to get the stub info
            logger.info("\nStub info:")
            logger.info(robot.kos.sound.stub)
            
            # Try to get audio info with error details
            try:
                logger.info("\nTrying to get audio info...")
                info = await robot.kos.sound.get_audio_info()
                logger.info(f"Audio info: {info}")
            except Exception as e:
                logger.error(f"Error getting audio info: {e}")
                logger.error("This suggests the sound service is not fully implemented on the robot")
                logger.error("You may need to check if audio support is enabled in your KOS build")

    except Exception as e:
        logger.error(f"Error: {e}")
        logger.error("Traceback:", exc_info=True)

if __name__ == "__main__":
    asyncio.run(main()) 