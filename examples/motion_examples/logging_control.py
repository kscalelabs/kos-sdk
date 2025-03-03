"""
Example showing how to enable and disable logging in the motion module.

This example demonstrates how to configure logging settings and control 
when logging is active during robot operation.
"""

import asyncio
import logging
from pykos import KOS
from demos.planners.motion import Robot
from demos.utils.motion_utils import setup_data_directory

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    """Run the logging control example."""
    # Create a data directory
    data_dir = setup_data_directory()
    
    # Create a robot with default joint mapping
    robot = Robot()
    
    # Connect to robot
    async with KOS() as kos:
        # Configure for simulator (change to True for real robot)
        is_real = False
        
        # Configure with monitoring enabled
        await robot.configure(kos, is_real=is_real, enable_monitoring=True)
        
        # Start with logging disabled
        logger.info("Starting motion sequence with logging disabled...")
        
        # Move joints
        await robot.move(kos, {
            "left_shoulder_pitch": 30,
            "left_elbow": 45
        })
        await asyncio.sleep(2)
        
        # Enable logging
        logger.info("Enabling logging...")
        log_path = robot.enable_logging(log_dir=data_dir)
        logger.info(f"Logging enabled to {log_path}")
        
        # Continue motion sequence with logging enabled
        logger.info("Continuing motion sequence with logging enabled...")
        await robot.move(kos, {
            "left_shoulder_pitch": -30,
            "left_elbow": 60
        })
        await asyncio.sleep(2)
        
        # Disable logging
        logger.info("Disabling logging...")
        robot.disable_logging()
        
        # Continue motion sequence with logging disabled again
        logger.info("Continuing motion sequence with logging disabled...")
        await robot.move(kos, {
            "left_shoulder_pitch": 0,
            "left_elbow": 0
        })
        await asyncio.sleep(2)
        
        # Stop monitoring
        await robot.stop_monitoring()
        
        # Plot the history
        logger.info("Plotting joint history...")
        robot.plot_history(["left_shoulder_pitch", "left_elbow"], plot_velocity=True)
        
        logger.info("Done!")

if __name__ == "__main__":
    asyncio.run(main())