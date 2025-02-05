import asyncio
from demos.robot import RobotInterface
from loguru import logger
from typing import AsyncGenerator

async def generate_sine_wave(frequency: float, duration: float, sample_rate: int = 44100, bit_depth: int = 16) -> AsyncGenerator[bytes, None]:
    """Generate a sine wave as PCM audio data."""
    import math
    import struct
    
    num_samples = int(duration * sample_rate)
    for i in range(num_samples):
        t = float(i) / sample_rate
        # Generate sine wave value between -1 and 1
        value = math.sin(2.0 * math.pi * frequency * t)
        # Convert to 16-bit PCM
        pcm_value = int(value * 32767)  # Scale to 16-bit range
        yield struct.pack('<h', pcm_value)  # Pack as 16-bit little-endian

async def main():
    robot = RobotInterface(ip="10.33.11.170")
    
    try:
        async with robot:
            logger.info("Getting audio info...")
            info = await robot.kos.sound.get_audio_info()
            logger.info(f"Audio capabilities: {info}")
            
            # Play a 440Hz tone for 1 second
            frequency = 440  # Hz (A4 note)
            duration = 1.0   # seconds
            
            try:
                logger.info("Playing tone...")
                response = await robot.kos.sound.play_audio(
                    generate_sine_wave(frequency, duration),
                    sample_rate=44100,
                    bit_depth=16,
                    channels=1
                )
                logger.info(f"Play response: {response}")
                
            except Exception as e:
                logger.error(f"Error playing audio: {e}")

    except ConnectionError as e:
        logger.error(f"Connection failed: {e}")
    except Exception as e:
        logger.error(f"Error: {e}")
        logger.error("Traceback:", exc_info=True)

if __name__ == "__main__":
    asyncio.run(main()) 