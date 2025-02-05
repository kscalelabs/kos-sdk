import asyncio
import numpy as np
from PIL import Image
from demos.robot import RobotInterface
from loguru import logger
from enum import Enum
from typing import Tuple

class ScaleMode(Enum):
    FIT = "fit"        # Maintain aspect ratio
    STRETCH = "stretch"  # Stretch to fill display

class ImageDisplay:
    def __init__(self, ip="10.33.11.170"):
        self.robot = RobotInterface(ip=ip)
        self.width = 32  # Default, will be updated from matrix info
        self.height = 16 # Default, will be updated from matrix info

    async def connect(self):
        """Connect and get display dimensions"""
        await self.robot.__aenter__()
        info = await self.robot.kos.led_matrix.get_matrix_info()
        self.width = info.width
        self.height = info.height
        logger.info(f"Connected to {self.width}x{self.height} display")

    async def close(self):
        """Clean shutdown"""
        await self.robot.__aexit__(None, None, None)

    def _resize_image(self, image: Image.Image, mode: ScaleMode) -> Image.Image:
        """Resize image according to the selected mode"""
        if mode == ScaleMode.STRETCH:
            # Simple stretch to display dimensions
            return image.resize((self.width, self.height), Image.Resampling.LANCZOS)
        else:  # FIT mode
            # Calculate scaling factor to maintain aspect ratio
            img_ratio = image.width / image.height
            display_ratio = self.width / self.height
            
            if img_ratio > display_ratio:
                # Image is wider - fit to width
                new_width = self.width
                new_height = int(self.width / img_ratio)
            else:
                # Image is taller - fit to height
                new_height = self.height
                new_width = int(self.height * img_ratio)
            
            # Resize image
            resized = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # Create black background
            final = Image.new('L', (self.width, self.height), 0)
            
            # Center the image
            x = (self.width - new_width) // 2
            y = (self.height - new_height) // 2
            final.paste(resized, (x, y))
            
            return final

    def _image_to_binary_buffer(self, image: Image.Image) -> bytes:
        """Convert image to binary buffer for LED matrix"""
        # Convert to grayscale and threshold to binary
        gray = image.convert('L')
        binary = gray.point(lambda x: 0 if x < 128 else 1, '1')
        
        # Convert to numpy array for easier bit manipulation
        arr = np.array(binary, dtype=np.uint8)
        
        # Pack bits into bytes (8 pixels per byte)
        packed = np.packbits(arr)
        
        return bytes(packed)

    async def display_image(self, image_path: str, mode: ScaleMode = ScaleMode.FIT):
        """Display an image on the LED matrix"""
        try:
            # Load and process image
            image = Image.open(image_path)
            logger.info(f"Loaded image: {image.size}")
            
            # Resize according to mode
            resized = self._resize_image(image, mode)
            logger.info(f"Resized to: {resized.size}")
            
            # Convert to binary buffer
            buffer = self._image_to_binary_buffer(resized)
            
            # Display on LED matrix
            logger.info("Sending to display...")
            await self.robot.kos.led_matrix.write_buffer(buffer)
            
        except Exception as e:
            logger.error(f"Error displaying image: {e}")
            logger.error("Traceback:", exc_info=True)

async def main():
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("image_path", help="Path to image file to display")
    parser.add_argument("--mode", choices=["fit", "stretch"], default="fit",
                      help="Scaling mode: 'fit' preserves aspect ratio, 'stretch' fills screen")
    parser.add_argument("--ip", default="10.33.11.170", help="Robot IP address")
    args = parser.parse_args()

    display = ImageDisplay(ip=args.ip)
    try:
        await display.connect()
        await display.display_image(args.image_path, ScaleMode(args.mode))
        
        # Keep displaying until interrupted
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Display interrupted by user")
            
    finally:
        await display.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Program terminated by user") 