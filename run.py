from robot import RobotInterface
import asyncio
import time
import argparse
import logging
from ks_digital_twin.puppet.mujoco_puppet import MujocoPuppet
from experiments.zmp_walking import ZMPWalkingController
import telemetry

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def get_controller(controller_name):
    if controller_name == "zmp":
        return ZMPWalkingController(enable_lateral_motion=True)
    else:
        raise ValueError(f"Unsupported controller: {controller_name}")

async def run_controller_loop(controller, hz=1000, robot=None, puppet=None):
    hz_counter = telemetry.HzCounter(interval=1 / hz)  

    if robot is not None:
        try:
            async with robot:
                await robot.configure_actuators()

                for i in range(3, 0, -1):
                    logger.info(f"Homing actuators in {i}...")
                    await asyncio.sleep(1)
                    
                await robot.homing_actuators()

                for i in range(3, 0, -1):
                    logger.info(f"Starting in {i}...")
                    await asyncio.sleep(1)

                while True:
                    start = time.perf_counter()
                    
                    feedback_positions = await robot.feedback_positions()
                    logger.info(f"Feedback positions: {feedback_positions}")

                    controller.update(feedback_positions)
                    command_positions = controller.get_controller_commands()

                    if command_positions:
                        await robot.command_positions(command_positions)
                    if puppet is not None and command_positions:
                        await puppet.set_joint_angles(command_positions)

                    hz_counter.update()
                    
                    elapsed = time.perf_counter() - start
                    remaining = 1 / hz - elapsed

                    await asyncio.sleep(remaining if remaining > 0 else 0)
        except KeyboardInterrupt:
            logger.info("Received KeyboardInterrupt, shutting down gracefully.")
        except Exception as e:
            logger.error("Error in real robot loop: %s", e)
    else:
        try:
            while True:
                start = time.perf_counter()
                
                controller.update()
                command_positions = controller.get_commands()

                if puppet is not None and command_positions:
                    await puppet.set_joint_angles(command_positions)
                hz_counter.update()
                
                elapsed = time.perf_counter() - start
                remaining = 1 / hz - elapsed
                await asyncio.sleep(remaining if remaining > 0 else 0)
        except KeyboardInterrupt:
            logger.info("Received KeyboardInterrupt, shutting down gracefully.")
        except Exception as e:
            logger.error("Error in simulation loop: %s", e)

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--real", action="store_true", help="Use PyKOS to command actual actuators.")
    parser.add_argument("--sim", action="store_true", help="Also send commands to Mujoco simulation.")
    parser.add_argument("--ip", default="192.168.42.1", help="IP address of the robot.")
    parser.add_argument("--controller", default="zmp", help="Name of the controller to use.")
    args = parser.parse_args()

    ip_address = args.ip if args.real else None
    mjcf_name = "zbot-v2"

    robot = RobotInterface(ip=ip_address) if args.real else None
    puppet = MujocoPuppet(mjcf_name) if args.sim else None

    controller = get_controller(args.controller)
    logger.info("Running in real mode..." if args.real else "Running in sim mode...")
    
    try:
        await run_controller_loop(controller, hz=1000, robot=robot, puppet=puppet)
    except Exception as e:
        logger.error("Fatal error in main loop: %s", e)

if __name__ == "__main__":
    asyncio.run(main())