"""
LED Matrix Testing Module for KOS Robots
=======================================

This module provides tools for testing and controlling the LED matrix display
on KOS robots. It allows you to run test patterns, clear the display, and
create custom visualizations.

Available Functions:
-------------------
clear_display_sync(robot_ip="10.33.10.65")
    Turn off all LEDs on the matrix (set all pixels to black).

fill_display_sync(robot_ip="10.33.10.65")
    Turn on all LEDs on the matrix (set all pixels to white).

display_pattern_sync(pattern_type="checkerboard", robot_ip="10.33.10.65")
    Display a test pattern on the LED matrix.
    Valid pattern types:
      - "checkerboard": Alternating on/off pixels
      - "border": Outline of the display
      - "cross": Diagonal lines forming an X

run_test_sequence_sync(robot_ip="10.33.10.65")
    Run a complete test sequence showing various patterns with pauses between.
    The sequence: clear → fill → checkerboard → border → cross → clear

Technical Details:
----------------
- LED Matrix dimensions: 32×16 pixels (GRID_WIDTH × GRID_HEIGHT)
- Uses PIL (Python Imaging Library) to create bitmap patterns
- Communicates with the robot's LED matrix via the KOS API

Example Usage:
------------
# Import the module
from kos_sdk.tests import led

# Run the full test sequence
result = led.run_test_sequence_sync()

# Display a specific pattern
led.display_pattern_sync("border")

# Clear the display
led.clear_display_sync()

# For detailed help
led.help()
"""

import asyncio
import logging
from typing import Any, Dict, Optional

import pykos
from PIL import Image, ImageDraw

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_ROBOT_IP = "10.33.10.65"
GRID_WIDTH = 32
GRID_HEIGHT = 16


async def connect_to_robot(robot_ip: str) -> Optional[pykos.KOS]:
    """Connect to a robot and verify the connection."""
    try:
        logger.info(f"Connecting to robot at {robot_ip}...")
        kos = pykos.KOS(ip=robot_ip)

        # Test connection with a simple query
        # Just check if we can connect, no specific LED query needed
        await kos.actuator.get_actuators_state([11])
        logger.info("✅ Successfully connected to robot")
        return kos
    except Exception as e:
        logger.error(f"❌ Failed to connect to robot: {e}")
        return None


async def clear_display(robot_ip: str = DEFAULT_ROBOT_IP) -> Dict[str, Any]:
    """Clear the LED matrix (all LEDs off)."""
    kos = await connect_to_robot(robot_ip)
    if not kos:
        return {"success": False, "message": "Failed to connect to robot"}

    try:
        # Create a blank (black) image
        image = Image.new("1", (GRID_WIDTH, GRID_HEIGHT), "black")
        bitmap_data = image.tobytes()

        # Send to LED matrix
        logger.info("Clearing LED display...")
        response = await kos.led_matrix.write_buffer(bitmap_data)

        return {
            "success": response.success,
            "message": "LED display cleared successfully" if response.success else "Failed to clear LED display",
        }
    except Exception as e:
        logger.error(f"Error clearing LED display: {e}")
        return {"success": False, "message": f"Error clearing LED display: {str(e)}"}


async def fill_display(robot_ip: str = DEFAULT_ROBOT_IP) -> Dict[str, Any]:
    """Turn on all LEDs."""
    kos = await connect_to_robot(robot_ip)
    if not kos:
        return {"success": False, "message": "Failed to connect to robot"}

    try:
        # Create a white (all on) image
        image = Image.new("1", (GRID_WIDTH, GRID_HEIGHT), "white")
        bitmap_data = image.tobytes()

        # Send to LED matrix
        logger.info("Filling LED display...")
        response = await kos.led_matrix.write_buffer(bitmap_data)

        return {
            "success": response.success,
            "message": "LED display filled successfully" if response.success else "Failed to fill LED display",
        }
    except Exception as e:
        logger.error(f"Error filling LED display: {e}")
        return {"success": False, "message": f"Error filling LED display: {str(e)}"}


async def display_pattern(pattern_type: str = "checkerboard", robot_ip: str = DEFAULT_ROBOT_IP) -> Dict[str, Any]:
    """Display a test pattern on the LED matrix."""
    kos = await connect_to_robot(robot_ip)
    if not kos:
        return {"success": False, "message": "Failed to connect to robot"}

    try:
        # Create the pattern image
        image = Image.new("1", (GRID_WIDTH, GRID_HEIGHT), "black")
        draw = ImageDraw.Draw(image)

        if pattern_type == "checkerboard":
            logger.info("Creating checkerboard pattern...")
            for y in range(GRID_HEIGHT):
                for x in range(GRID_WIDTH):
                    if (x + y) % 2 == 0:
                        draw.point((x, y), fill="white")

        elif pattern_type == "border":
            logger.info("Creating border pattern...")
            # Draw border
            for x in range(GRID_WIDTH):
                draw.point((x, 0), fill="white")
                draw.point((x, GRID_HEIGHT - 1), fill="white")

            for y in range(GRID_HEIGHT):
                draw.point((0, y), fill="white")
                draw.point((GRID_WIDTH - 1, y), fill="white")

        elif pattern_type == "cross":
            logger.info("Creating cross pattern...")
            # Draw diagonal lines
            for i in range(GRID_WIDTH):
                y = i * GRID_HEIGHT // GRID_WIDTH
                draw.point((i, y), fill="white")
                draw.point((i, GRID_HEIGHT - 1 - y), fill="white")

        else:
            return {
                "success": False,
                "message": f"Unknown pattern type: {pattern_type}. " f"Valid types are: checkerboard, border, cross",
            }

        # Send to LED matrix
        bitmap_data = image.tobytes()
        response = await kos.led_matrix.write_buffer(bitmap_data)

        return {
            "success": response.success,
            "message": (
                f"{pattern_type} pattern displayed successfully"
                if response.success
                else f"Failed to display {pattern_type} pattern"
            ),
        }
    except Exception as e:
        logger.error(f"Error displaying pattern: {e}")
        return {"success": False, "message": f"Error displaying pattern: {str(e)}"}


async def run_test_sequence(robot_ip: str = DEFAULT_ROBOT_IP) -> Dict[str, Any]:
    """Run a sequence of tests to verify LED matrix functionality."""
    logger.info("Starting LED matrix test sequence...")
    results = {}

    # Test 1: Clear
    logger.info("Test 1: Clearing display...")
    results["clear"] = await clear_display(robot_ip)
    await asyncio.sleep(1)

    # Test 2: Fill
    logger.info("Test 2: Filling display...")
    results["fill"] = await fill_display(robot_ip)
    await asyncio.sleep(1)

    # Test 3: Checkerboard
    logger.info("Test 3: Checkerboard pattern...")
    results["checkerboard"] = await display_pattern("checkerboard", robot_ip)
    await asyncio.sleep(1)

    # Test 4: Border
    logger.info("Test 4: Border pattern...")
    results["border"] = await display_pattern("border", robot_ip)
    await asyncio.sleep(1)

    # Test 5: Cross
    logger.info("Test 5: Cross pattern...")
    results["cross"] = await display_pattern("cross", robot_ip)
    await asyncio.sleep(1)

    # Test 6: Clear again
    logger.info("Test 6: Clearing display...")
    results["final_clear"] = await clear_display(robot_ip)

    # Check overall success
    all_success = all(result.get("success", False) for result in results.values())

    logger.info("LED matrix test sequence completed.")
    return {
        "success": all_success,
        "message": "All LED tests passed" if all_success else "Some LED tests failed",
        "details": results,
    }


# Synchronous wrapper functions
def clear_display_sync(robot_ip: str = DEFAULT_ROBOT_IP) -> Dict[str, Any]:
    """Synchronous wrapper for clear_display."""
    return asyncio.run(clear_display(robot_ip))


def fill_display_sync(robot_ip: str = DEFAULT_ROBOT_IP) -> Dict[str, Any]:
    """Synchronous wrapper for fill_display."""
    return asyncio.run(fill_display(robot_ip))


def display_pattern_sync(pattern_type: str = "checkerboard", robot_ip: str = DEFAULT_ROBOT_IP) -> Dict[str, Any]:
    """Synchronous wrapper for display_pattern."""
    return asyncio.run(display_pattern(pattern_type, robot_ip))


def run_test_sequence_sync(robot_ip: str = DEFAULT_ROBOT_IP) -> Dict[str, Any]:
    """Synchronous wrapper for run_test_sequence."""
    return asyncio.run(run_test_sequence(robot_ip))


def help():
    """Print help information about the LED matrix testing module."""
    print(
        """
LED Matrix Testing Module for KOS Robots
=======================================

Available Functions:
-------------------
clear_display_sync(robot_ip="10.33.10.65")
    Turn off all LEDs on the matrix (set all pixels to black).

fill_display_sync(robot_ip="10.33.10.65")
    Turn on all LEDs on the matrix (set all pixels to white).

display_pattern_sync(pattern_type="checkerboard", robot_ip="10.33.10.65")
    Display a test pattern on the LED matrix.
    Valid pattern types: 
      - "checkerboard": Alternating on/off pixels
      - "border": Outline of the display
      - "cross": Diagonal lines forming an X

run_test_sequence_sync(robot_ip="10.33.10.65")
    Run a complete test sequence showing various patterns with pauses between.
    The sequence: clear → fill → checkerboard → border → cross → clear

Technical Details:
----------------
- LED Matrix dimensions: 32×16 pixels (GRID_WIDTH × GRID_HEIGHT)
- Uses PIL (Python Imaging Library) to create bitmap patterns
- Communicates with the robot's LED matrix via the KOS API

Example Usage:
------------
# Import the module
from kos_sdk.tests import led

# Run the full test sequence
result = led.run_test_sequence_sync()

# Display a specific pattern
led.display_pattern_sync("border")

# Clear the display
led.clear_display_sync()
"""
    )


# Define what gets imported with "from kos_sdk.tests.led import *"
__all__ = ["clear_display_sync", "fill_display_sync", "display_pattern_sync", "run_test_sequence_sync", "help"]


if __name__ == "__main__":
    try:
        result = asyncio.run(run_test_sequence())
        if result["success"]:
            print("✅ LED matrix test sequence completed successfully!")
        else:
            print(f"❌ LED matrix test sequence failed: {result['message']}")
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    except Exception as e:
        logger.error(f"Unhandled exception: {e}")
