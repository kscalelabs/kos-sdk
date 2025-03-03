"""
Example showing how to integrate the motion module with existing walking demos.

This script demonstrates how to use the motion module's monitoring and visualization
capabilities with an existing walking planner.
"""

import asyncio
import os
import logging
from pykos import KOS
from demos.planners.motion import Robot
from demos.planners.zmp_walking import ZMPWalkingPlanner
from demos.utils.motion_utils import setup_data_directory

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    """Run the walking with monitoring example."""
    # Create a data directory
    data_dir = setup_data_directory()
    
    # Create a robot with default joint mapping
    robot = Robot()
    
    # Create a ZMP walking planner
    planner = ZMPWalkingPlanner()
    
    # Connect to robot
    async with KOS() as kos:
        # Configure for simulator (change to True for real robot)
        is_real = False
        
        # Configure with monitoring enabled
        await robot.configure(kos, is_real=is_real, enable_monitoring=True)
        
        # Enable logging
        log_path = robot.enable_logging(log_dir=data_dir)
        logger.info(f"Logging enabled to {log_path}")
        
        try:
            # Initialize the planner
            planner.initialize()
            
            # Run walking sequence for a limited number of steps
            logger.info("Starting walking sequence...")
            step_count = 0
            max_steps = 20  # Limit steps for this example
            
            while step_count < max_steps:
                # Get planner commands
                commands = planner.get_planner_commands()
                
                # Move robot using the motion module
                await robot.move(kos, commands)
                
                # Small delay to match the planner frequency
                await asyncio.sleep(1/50)  # Assuming 50Hz control frequency
                
                step_count += 1
                
        finally:
            # Stop walking
            logger.info("Stopping walking sequence...")
            
            # Return to home position
            await robot.zero_all(kos)
            
            # Stop monitoring and disable logging
            await robot.stop_monitoring()
            robot.disable_logging()
        
        # Plot the joint history for legs
        logger.info("Plotting leg joint history...")
        fig, _ = robot.plot_history(robot.groups["legs"].get_joint_names(), 
                                  plot_velocity=True,
                                  title_suffix=" During Walking")
        
        # Save the plot
        if fig:
            plot_path = os.path.join(data_dir, "plots", "walking_leg_motion.png")
            fig.savefig(plot_path)
            logger.info(f"Saved plot to {plot_path}")
        
        # Save the data
        data_path = os.path.join(data_dir, "walking_data.json")
        robot.save_data(data_path)
        logger.info(f"Saved data to {data_path}")
        
        logger.info("Done!")

if __name__ == "__main__":
    asyncio.run(main())