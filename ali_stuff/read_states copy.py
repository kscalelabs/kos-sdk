import asyncio
from robot import RobotInterface
from loguru import logger
import traceback

async def main():
    # Create robot interface with your IP
    robot = RobotInterface(ip="10.33.11.170")
    
    try:
        async with robot:
            # Get and print actuator states
            feedback_state = await robot.get_feedback_state()
            
            # Print each actuator's state
            for state in feedback_state.states:
                logger.info(f"Actuator {state.actuator_id}:")
                logger.info(f"  Position: {state.position} degrees")
                logger.info(f"  Velocity: {state.velocity}")
                logger.info(f"  Current: {state.current}")
                logger.info(f"  Temperature: {state.temperature}")
                logger.info("---")

            # Or get just positions as a dictionary
            positions = await robot.get_feedback_positions()
            logger.info("\nJoint Positions:")
            for joint_name, position in positions.items():
                logger.info(f"{joint_name}: {position} degrees")

    except ConnectionError as e:
        logger.error(f"Connection failed: {e}")
    except Exception as e:
        logger.error(f"Error: {e}")
        logger.error("Traceback:")
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    asyncio.run(main()) 