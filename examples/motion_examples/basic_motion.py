"""
Basic motion example demonstrating how to use the motion planner.

This example shows how to initialize a robot, configure it, and move joints
to specific positions using the motion module.
"""

import asyncio
import logging
import sys
import os

# Add the root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from pykos import KOS
from planners.motion import Robot

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    """Run the basic motion example."""
    # Create a robot with default joint mapping
    robot = Robot()
    
    # Connect to robot
    async with KOS() as kos:
        # Configure for simulator (change to True for real robot)
        is_real = False
        await robot.configure(kos, is_real=is_real)
        
        logger.info("Moving left arm joints...")
        # Move left arm joints to specific positions
        await robot.move(kos, {
            "left_shoulder_pitch": 45,  # degrees
            "left_shoulder_roll": 30,
            "left_elbow": 30
        })
        
        # Wait a moment
        await asyncio.sleep(2)
        
        logger.info("Getting current joint states...")
        # Get current joint states
        states = await robot.get_states(kos)
        for name, state in states.items():
            if name.startswith("left_"):
                logger.info(f"{name}: pos={state.position:.2f}, vel={state.velocity:.2f}")
        
        logger.info("Moving left arm back to zero...")
        # Return left arm to zero position
        await robot.move_group(kos, "left_arm", {
            "left_shoulder_pitch": 0,
            "left_shoulder_roll": 0,
            "left_shoulder_yaw": 0,
            "left_elbow": 0
        })
        
        await asyncio.sleep(1)
        logger.info("Done!")

if __name__ == "__main__":
    asyncio.run(main())