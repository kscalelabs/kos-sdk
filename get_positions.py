"""Script to continuously get all 18 actuator positions using actuator service."""

import asyncio
import grpc.aio
from loguru import logger
import argparse
from pykos import KOS
import time
import subprocess
import math

# All actuator IDs we want to monitor
ACTUATOR_IDS = [
    # Left arm
    11,
    12,
    13,
    14,
    # Right arm
    21,
    22,
    23,
    24,
    # Left leg
    31,
    32,
    33,
    34,
    35,
    # Right leg
    41,
    42,
    43,
    44,
    45,
]

# Names for clearer logging
ACTUATOR_NAMES = {
    # Left arm
    11: "L_SHOULDER_YAW ",
    12: "L_SHOULDER_PITCH",
    13: "L_ELBOW        ",
    14: "L_GRIPPER      ",
    # Right arm
    21: "R_SHOULDER_YAW ",
    22: "R_SHOULDER_PITCH",
    23: "R_ELBOW        ",
    24: "R_GRIPPER      ",
    # Left leg
    31: "L_HIP_YAW      ",
    32: "L_HIP_ROLL     ",
    33: "L_HIP_PITCH    ",
    34: "L_KNEE         ",
    35: "L_ANKLE        ",
    # Right leg
    41: "R_HIP_YAW      ",
    42: "R_HIP_ROLL     ",
    43: "R_HIP_PITCH    ",
    44: "R_KNEE         ",
    45: "R_ANKLE        ",
}


def print_positions(positions):
    """Print positions in a clean format."""
    print("\033[2J\033[H")  # Clear screen and move to top
    print("=== ACTUATOR POSITIONS ===")
    print("Left Arm:")
    for id in [11, 12, 13, 14]:
        # Convert radians to degrees for display
        pos_deg = math.degrees(positions.get(id, 0.0))
        print(f"  {ACTUATOR_NAMES[id]}: {pos_deg:8.2f}°")
    print("\nRight Arm:")
    for id in [21, 22, 23, 24]:
        pos_deg = math.degrees(positions.get(id, 0.0))
        print(f"  {ACTUATOR_NAMES[id]}: {pos_deg:8.2f}°")
    print("\nLeft Leg:")
    for id in [31, 32, 33, 34, 35]:
        pos_deg = math.degrees(positions.get(id, 0.0))
        print(f"  {ACTUATOR_NAMES[id]}: {pos_deg:8.2f}°")
    print("\nRight Leg:")
    for id in [41, 42, 43, 44, 45]:
        pos_deg = math.degrees(positions.get(id, 0.0))
        print(f"  {ACTUATOR_NAMES[id]}: {pos_deg:8.2f}°")


def check_connection(ip: str) -> None:
    """Verify robot is reachable via ping before attempting connection."""
    try:
        logger.info(f"Pinging robot at {ip}")
        subprocess.run(
            ["ping", "-c", "1", ip],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        logger.success(f"Successfully pinged robot at {ip}")
    except subprocess.CalledProcessError:
        logger.error(f"Could not ping robot at {ip}")
        raise ConnectionError("Robot connection failed.")


async def main():
    """Continuously get actuator positions at high frequency."""
    parser = argparse.ArgumentParser(description="Get actuator positions continuously")
    parser.add_argument("--ip", default="10.33.11.170", help="Robot IP address")
    parser.add_argument(
        "--hz", type=float, default=20.0, help="Display update rate in Hz"
    )
    args = parser.parse_args()

    print(f"Connecting to robot at {args.ip}...")

    # First check if robot is reachable
    check_connection(args.ip)

    # Then create KOS instance
    kos = KOS(ip=args.ip)

    try:
        async with kos:
            logger.info("Connected to robot, starting position polling...")
            print("Press Ctrl+C to stop...")
            time.sleep(1)  # Give time to read message

            # Track timing
            last_time = time.perf_counter()
            count = 0

            while True:
                try:
                    # Get positions as fast as possible using actuator service
                    response = await kos.actuator.get_actuators_state(ACTUATOR_IDS)

                    # Extract positions and convert from degrees to radians
                    positions = {
                        state.actuator_id: math.radians(state.position)
                        for state in response.states
                    }

                    # Print positions continuously
                    print_positions(positions)

                    # Update Hz counter
                    count += 1
                    current_time = time.perf_counter()
                    if current_time - last_time >= 1.0:
                        hz = count / (current_time - last_time)
                        print(f"\nPolling at {hz:.1f} Hz")
                        count = 0
                        last_time = current_time

                    # Control display update rate
                    await asyncio.sleep(1.0 / args.hz)

                except grpc.aio.AioRpcError as e:
                    logger.error(f"Connection error: {e.details()}")
                    logger.info("Attempting to reconnect in 1 second...")
                    await asyncio.sleep(1)
                except Exception as e:
                    logger.error(f"Error during polling: {e}")
                    await asyncio.sleep(1)

    except KeyboardInterrupt:
        print("\nStopping position polling...")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
    finally:
        print("Disconnected from robot")


if __name__ == "__main__":
    asyncio.run(main())
