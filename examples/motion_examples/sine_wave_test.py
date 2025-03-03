"""
Sine wave test example demonstrating how to test joint performance.

This example shows how to run a sine wave test on joints to evaluate their
tracking performance in both simulation and real robot environments.
"""

import asyncio
import logging
import os
from pykos import KOS
from demos.planners.motion import Robot, run_sine_wave_test, compare_real_vs_sim
from demos.utils.motion_utils import setup_data_directory

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def run_sim_test(joint_names, data_dir):
    """Run a sine wave test in simulation."""
    robot = Robot()
    
    async with KOS() as kos:
        logger.info(f"Running simulation sine wave test on {joint_names}...")
        sim_data_file = await run_sine_wave_test(
            kos, 
            robot, 
            joint_names, 
            amplitude=30.0,
            frequency=0.5,
            duration=10.0,
            real_robot=False,
            plot=False,
            save_data=True
        )
        
        # Move the data file to our data directory
        if sim_data_file and os.path.exists(sim_data_file):
            new_path = os.path.join(data_dir, os.path.basename(sim_data_file))
            os.rename(sim_data_file, new_path)
            logger.info(f"Moved simulation data to {new_path}")
            return new_path
        
        return None

async def run_real_test(joint_names, data_dir):
    """Run a sine wave test on the real robot."""
    robot = Robot()
    
    async with KOS() as kos:
        logger.info(f"Running real robot sine wave test on {joint_names}...")
        real_data_file = await run_sine_wave_test(
            kos, 
            robot, 
            joint_names, 
            amplitude=30.0,
            frequency=0.5,
            duration=10.0,
            real_robot=True,
            plot=False,
            save_data=True
        )
        
        # Move the data file to our data directory
        if real_data_file and os.path.exists(real_data_file):
            new_path = os.path.join(data_dir, os.path.basename(real_data_file))
            os.rename(real_data_file, new_path)
            logger.info(f"Moved real robot data to {new_path}")
            return new_path
        
        return None

async def main():
    """Run the sine wave test example."""
    # Create a data directory
    data_dir = setup_data_directory()
    
    # Joints to test
    # You can choose different joints depending on what you want to test
    joint_names = ["left_knee", "right_knee"]
    
    # Run tests
    # Uncomment the real test if you have a real robot available
    sim_data_file = await run_sim_test(joint_names, data_dir)
    # real_data_file = await run_real_test(joint_names, data_dir)
    
    # For demonstration, let's just use the sim data file twice
    # In practice, you would compare sim_data_file to real_data_file
    real_data_file = sim_data_file
    
    # Compare results if we have both files
    if sim_data_file and real_data_file:
        logger.info("Comparing simulation and real robot results...")
        fig, _ = compare_real_vs_sim(
            real_data_file, 
            sim_data_file, 
            joint_names=joint_names,
            plot_velocity=True,
            save_plot=True
        )
        
        # Save the comparison plot
        if fig:
            plot_path = os.path.join(data_dir, "plots", "sine_test_comparison.png")
            fig.savefig(plot_path)
            logger.info(f"Saved comparison plot to {plot_path}")
    
    logger.info("Done!")

if __name__ == "__main__":
    asyncio.run(main())