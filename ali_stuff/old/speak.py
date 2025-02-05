import asyncio
from demos.robot import RobotInterface
from loguru import logger
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
from elevenlabs import play
import numpy as np

class RobotSpeaker:
    def __init__(self, ip="10.33.11.170"):
        self.robot = RobotInterface(ip=ip)
        load_dotenv()
        self.eleven = ElevenLabs()
        
    async def connect(self):
        """Connect to robot"""
        await self.robot.__aenter__()
        logger.info("Connected to robot")

    async def close(self):
        """Clean shutdown"""
        try:
            # Turn off display
            info = await self.robot.kos.led_matrix.get_matrix_info()
            buffer_size = info.width * info.height // 8
            off_buffer = bytes([0x00] * buffer_size)
            await self.robot.kos.led_matrix.write_buffer(off_buffer)
            logger.info("Display turned off")
        finally:
            await self.robot.__aexit__(None, None, None)
        
    async def speak_and_display(self, text: str, voice_id="JBFqnCBsd6RMkjVDRZzb"):
        """Convert text to speech and display on robot"""
        try:
            logger.info(f"Converting text to speech and displaying: {text}")
            
            # Start displaying text on robot
            info = await self.robot.kos.led_matrix.get_matrix_info()
            
            # Create text image and display it
            from PIL import Image, ImageDraw, ImageFont
            image = Image.new('L', (info.width, info.height), 0)
            draw = ImageDraw.Draw(image)
            
            # Try to find a font size that fits
            font_size = info.height
            text_width = info.width + 1
            
            while text_width > info.width and font_size > 1:
                try:
                    font = ImageFont.load_default()
                    bbox = draw.textbbox((0, 0), text, font=font)
                    text_width = bbox[2] - bbox[0]
                    text_height = bbox[3] - bbox[1]
                    font_size -= 1
                except Exception:
                    font = ImageFont.load_default()
                    break

            # Center the text
            x = (info.width - text_width) // 2
            y = (info.height - text_height) // 2
            
            # Draw the text
            draw.text((x, y), text, font=font, fill=255)
            
            # Convert to binary and display
            binary = image.point(lambda x: 0 if x < 128 else 1, '1')
            arr = np.array(binary, dtype=np.uint8)
            packed = np.packbits(arr)
            buffer = bytes(packed)
            
            await self.robot.kos.led_matrix.write_buffer(buffer)
            
            # Generate and play audio locally
            audio = self.eleven.text_to_speech.convert(
                text=text,
                voice_id=voice_id,
                model_id="eleven_multilingual_v2",
                output_format="mp3_44100_128",
            )
            play(audio)
            
            logger.info("Finished speaking")
            
        except Exception as e:
            logger.error(f"Error speaking: {e}")
            logger.error("Traceback:", exc_info=True)

async def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("text", help="Text to speak and display")
    parser.add_argument("--ip", default="10.33.11.170", help="Robot IP address")
    parser.add_argument("--voice", default="JBFqnCBsd6RMkjVDRZzb", help="ElevenLabs voice ID")
    args = parser.parse_args()

    speaker = RobotSpeaker(ip=args.ip)
    try:
        await speaker.connect()
        await speaker.speak_and_display(args.text, args.voice)
        
        # Keep display on until interrupted
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Display interrupted by user")
            
    finally:
        await speaker.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Program terminated by user") 
