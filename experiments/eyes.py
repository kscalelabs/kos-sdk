import pykos
from PIL import Image
import asyncio

# Configuration
GRID_WIDTH = 32
GRID_HEIGHT = 16

# Define your matrix here (16x32 grid of 1s and 0s)
# 1 represents LED on, 0 represents LED off
MATRIX_STRING = """
00000000000000000000000000000000
00000000000000000000000000000000
00000000000000000000000000000000
00000111100000000000000111100000
00001111110000000000001111110000
00011111111000000000011111111000
00011111111111111111111111111000
00011111111111111111111111111000
00011111111000000000011111111000
00001111110000000000001111110000
00000111100000000000000111100000
00000000000000000000000000000000
00000000000000000000000000000000
00000000000000000000000000000000
00000000000000000000000000000000
00000000000000000000000000000000
""".strip()

MATRIX = [list(row) for row in MATRIX_STRING.split("\n")]

async def main():
    # Initialize KOS connection
    kos = pykos.KOS("10.33.14.50")

    # Create image from matrix
    image = Image.new("1", (GRID_WIDTH, GRID_HEIGHT), "black")
    for y in range(GRID_HEIGHT):
        for x in range(GRID_WIDTH):
            if MATRIX[y][x] == "1":
                image.putpixel((x, y), 1)

    # Send bitmap to KOS
    try:
        bitmap_data = image.tobytes()
        response = await kos.led_matrix.write_buffer(bitmap_data)
        if response.success:
            print("Bitmap sent successfully")
        else:
            print("Failed to send bitmap")
    except Exception as e:
        print(f"Error sending bitmap: {e}")

if __name__ == "__main__":
    asyncio.run(main())
