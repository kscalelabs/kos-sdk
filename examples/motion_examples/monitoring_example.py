"""
Motion monitoring example demonstrating how to track joint states and visualize the results.

This example shows how to initialize a robot, enable monitoring, run a motion,
and then visualize the results.
"""

import asyncio
import logging
import os
from pykos import KOS
from demos.planners.motion import Robot, run_sine_wave_test
from demos.utils.motion_utils import setup_data_directory

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    """Run the monitoring example."""
    # Create a data directory
    data_dir = setup_data_directory()
    
    # Create a robot with default joint mapping
    robot = Robot()
    
    # Connect to robot
    async with KOS() as kos:
        # Configure for simulator (change to True for real robot)
        is_real = False
        
        logger.info("Running sine wave test on left arm joints...")
        # Run a sine wave test on left arm joints
        joints_to_test = ["left_shoulder_pitch", "left_elbow"]
        
        # Configure monitoring and logging
        await robot.configure(kos, is_real=is_real, enable_monitoring=True)
        log_path = robot.enable_logging(log_dir=data_dir)
        logger.info(f"Logging enabled to {log_path}")
        
        # Run a custom motion sequence
        try:
            # Move to starting position
            await robot.move(kos, {joint: 0 for joint in joints_to_test})
            await asyncio.sleep(1)
            
            # Run a sequence of movements
            logger.info("Running movement sequence...")
            for angle in [30, 0, -30, 0, 45, 0]:
                positions = {joint: angle for joint in joints_to_test}
                await robot.move(kos, positions)
                await asyncio.sleep(1)
                
        finally:
            # Stop monitoring and disable logging
            await robot.stop_monitoring()
            robot.disable_logging()
        
        # Plot the results
        logger.info("Plotting results...")
        fig, _ = robot.plot_history(joints_to_test, plot_velocity=True)
        
        # Save the plot
        if fig:
            plot_path = os.path.join(data_dir, "plots", "motion_sequence.png")
            fig.savefig(plot_path)
            logger.info(f"Saved plot to {plot_path}")
        
        # Save the data
        data_path = os.path.join(data_dir, "motion_sequence_data.json")
        robot.save_data(data_path)
        logger.info(f"Saved data to {data_path}")
        
        logger.info("Done!")

if __name__ == "__main__":
    asyncio.run(main())