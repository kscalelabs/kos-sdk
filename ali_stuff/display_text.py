import asyncio
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from demos.robot import RobotInterface
from loguru import logger
import emoji

class TextDisplay:
    def __init__(self, ip="10.33.11.170"):
        self.robot = RobotInterface(ip=ip)
        self.width = 32
        self.height = 16
        
    async def connect(self):
        await self.robot.__aenter__()
        info = await self.robot.kos.led_matrix.get_matrix_info()
        self.width = info.width
        self.height = info.height
        logger.info(f"Connected to {self.width}x{self.height} display")

    async def close(self):
        """Clean shutdown - ensure display is off"""
        try:
            # Create an all-off buffer
            buffer_size = self.width * self.height // 8
            off_buffer = bytes([0x00] * buffer_size)
            await self.robot.kos.led_matrix.write_buffer(off_buffer)
            logger.info("Display turned off")
        finally:
            await self.robot.__aexit__(None, None, None)

    def _text_to_image(self, text: str) -> Image.Image:
        """Convert text or emoji to image"""
        # Create a new image with black background
        image = Image.new('L', (self.width, self.height), 0)
        draw = ImageDraw.Draw(image)
        
        # Try to find a font size that fits
        font_size = self.height
        text_width = self.width + 1
        
        # Use a monospace font for better emoji support
        while text_width > self.width and font_size > 1:
            try:
                # Try to use a system emoji font if available
                font = ImageFont.truetype("/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf", font_size)
            except OSError:
                # Fallback to default font
                font = ImageFont.load_default()
            
            # Get text size
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            font_size -= 1

        # Calculate position to center the text
        x = (self.width - text_width) // 2
        y = (self.height - text_height) // 2
        
        # Draw the text in white
        draw.text((x, y), text, font=font, fill=255)
        return image

    def _image_to_binary_buffer(self, image: Image.Image) -> bytes:
        """Convert image to binary buffer for LED matrix"""
        # Threshold to binary
        binary = image.point(lambda x: 0 if x < 128 else 1, '1')
        arr = np.array(binary, dtype=np.uint8)
        packed = np.packbits(arr)
        return bytes(packed)

    async def display_text(self, text: str):
        """Display text or emoji on the LED matrix"""
        try:
            # Convert emoji shortcodes to unicode
            text = emoji.emojize(text, language='alias')
            logger.info(f"Displaying: {text}")
            
            # Convert to image
            image = self._text_to_image(text)
            
            # Convert to binary buffer
            buffer = self._image_to_binary_buffer(image)
            
            # Display on LED matrix
            await self.robot.kos.led_matrix.write_buffer(buffer)
            
        except Exception as e:
            logger.error(f"Error displaying text: {e}")
            logger.error("Traceback:", exc_info=True)

async def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("text", help="Text or emoji to display (use emoji shortcodes like :smile:)")
    parser.add_argument("--ip", default="10.33.11.170", help="Robot IP address")
    args = parser.parse_args()

    display = TextDisplay(ip=args.ip)
    try:
        await display.connect()
        await display.display_text(args.text)
        
        # Keep displaying until interrupted
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Display interrupted by user")
            
    finally:
        # This will ensure the display is turned off
        await display.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Program terminated by user") 