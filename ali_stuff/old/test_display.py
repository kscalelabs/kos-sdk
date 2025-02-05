import asyncio
from demos.robot import RobotInterface
from loguru import logger

async def main():
    robot = RobotInterface(ip="10.33.11.170")
    
    try:
        async with robot:
            logger.info("Getting LED Matrix info...")
            
            try:
                # First get the matrix info to know what we're working with
                info = await robot.kos.led_matrix.get_matrix_info()
                logger.info(f"Matrix info: {info}")
                
                # Create a simple pattern (all LEDs on)
                width = info.width
                height = info.height
                buffer_size = width * height // 8  # 8 LEDs per byte
                buffer = bytes([0xFF] * buffer_size)  # All bits set to 1
                
                # Write the pattern
                logger.info(f"Writing pattern to {width}x{height} display...")
                response = await robot.kos.led_matrix.write_buffer(buffer)
                logger.info(f"Write response: {response}")
                
                try:
                    # Wait indefinitely until interrupted
                    while True:
                        await asyncio.sleep(1)
                except KeyboardInterrupt:
                    logger.info("Keyboard interrupt detected, turning off display...")
                finally:
                    # Turn all LEDs off
                    off_buffer = bytes([0x00] * buffer_size)  # All bits set to 0
                    await robot.kos.led_matrix.write_buffer(off_buffer)
                    logger.info("Display turned off")
                
            except Exception as e:
                logger.error(f"Error controlling display: {e}")
                logger.error("Traceback:", exc_info=True)

    except Exception as e:
        logger.error(f"Error: {e}")
        logger.error("Traceback:", exc_info=True)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Program terminated by user") 
        
        
