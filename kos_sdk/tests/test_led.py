import asyncio
from PIL import Image
from loguru import logger
import pykos

GRID_SIZE = (32, 16)


async def test_led(robot_ip="", blink_times=3, delay=0.5):
    logger.info("Starting LED test...")

    try:
        kos = pykos.KOS(ip=robot_ip)
        image_on = Image.new("1", GRID_SIZE, "white")
        image_off = Image.new("1", GRID_SIZE, "black")

        await kos.led_matrix.write_buffer(image_off.tobytes())
        print("LED will start blinking...")
        for i in range(blink_times):
            await kos.led_matrix.write_buffer(image_on.tobytes())
            await asyncio.sleep(delay)
            await kos.led_matrix.write_buffer(image_off.tobytes())
            await asyncio.sleep(delay)
        return {"success": True, "message": f"Completed {blink_times} blinks"}

    except Exception as e:
        logger.error(f"LED test failed: {e}")
        return {"success": False, "message": str(e)}


__all__ = ["test_led"]
