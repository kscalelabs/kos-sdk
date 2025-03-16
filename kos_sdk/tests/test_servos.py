"""
Servo Testing Module for KOS Robots
===================================

This module provides tools for testing, controlling, and monitoring servo motors
on KOS-based robots.

Available Functions:
-------------------
test_servos_sync(robot_ip="10.33.10.65", actuator_ids=[11, 21, 31, 41])
    Test multiple servos by moving them slightly and checking response.

test_servo_sync(robot_ip="10.33.10.65", actuator_id=11)
    Test a single servo by moving it slightly and checking response.

get_servo_state_sync(robot_ip="10.33.10.65", actuator_id=11)
    Get detailed state information about a servo (position, temperature, etc).

move_servo_sync(robot_ip="10.33.10.65", actuator_id=11, position=None, relative_movement=None)
    Move a servo to an absolute position or by a relative amount.

list_available_servos_sync(robot_ip="10.33.10.65")
    List all available servos and their current status.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Set

import pykos

# Configure logging
logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_ROBOT_IP = "10.33.10.65"

# Mapping between joint names and actuator IDs
JOINT_MAP = {
    "left_shoulder_yaw": 11,
    "left_shoulder_pitch": 12,
    "left_elbow_yaw": 13,
    "left_gripper": 14,
    "right_shoulder_yaw": 21,
    "right_shoulder_pitch": 22,
    "right_elbow_yaw": 23,
    "right_gripper": 24,
    "left_hip_yaw": 31,
    "left_hip_roll": 32,
    "left_hip_pitch": 33,
    "left_knee_pitch": 34,
    "left_ankle_pitch": 35,
    "right_hip_yaw": 41,
    "right_hip_roll": 42,
    "right_hip_pitch": 43,
    "right_knee_pitch": 44,
    "right_ankle_pitch": 45,
}

# Reverse mapping from ID to name
ID_TO_NAME = {v: k for k, v in JOINT_MAP.items()}

# List of all valid actuator IDs
VALID_ACTUATOR_IDS = list(ID_TO_NAME.keys())

# Default actuators to test
DEFAULT_TEST_ACTUATORS = [11, 21, 31, 41]  # Yaw joints

# Default movement parameters
DEFAULT_MOVEMENT_DEGREES = 5.0
DEFAULT_WAIT_TIME = 1.0
DEFAULT_KP = 20
DEFAULT_KD = 10
DEFAULT_MAX_TORQUE = 30


def validate_actuator_id(actuator_id: int) -> bool:
    """Check if an actuator ID is valid."""
    return actuator_id in VALID_ACTUATOR_IDS


def validate_actuator_ids(actuator_ids: List[int]) -> Set[int]:
    """Return set of invalid actuator IDs from a list."""
    return {id for id in actuator_ids if not validate_actuator_id(id)}


async def connect_to_robot(robot_ip: str) -> Optional[pykos.KOS]:
    """Connect to a robot and verify the connection."""
    try:
        logger.info(f"Connecting to robot at {robot_ip}...")
        kos = pykos.KOS(ip=robot_ip)

        # Test connection with a simple query
        await kos.actuator.get_actuators_state([DEFAULT_TEST_ACTUATORS[0]])
        logger.info("✅ Successfully connected to robot")
        return kos
    except Exception as e:
        logger.error(f"❌ Failed to connect to robot: {e}")
        return None


async def test_actuator_movement(
    kos, 
    actuator_id: int, 
    movement_degrees: float = DEFAULT_MOVEMENT_DEGREES, 
    wait_time: float = DEFAULT_WAIT_TIME
) -> Dict[str, Any]:
    """Test if an actuator can move and return to its original position."""
    if not validate_actuator_id(actuator_id):
        logger.error(f"Invalid actuator ID: {actuator_id}")
        return {"success": False, "message": f"Invalid actuator ID: {actuator_id}"}

    try:
        # Get current position
        state = await kos.actuator.get_actuators_state([actuator_id])
        if not state.states:
            logger.error(f"Could not get state for actuator {actuator_id}")
            return {"success": False, "message": f"Could not get state for actuator {actuator_id}"}

        current_position = state.states[0].position
        name = ID_TO_NAME.get(actuator_id, f"Actuator {actuator_id}")
        logger.info(f"{name} (ID: {actuator_id}) current position: {current_position:.2f} degrees")

        # Configure the actuator
        logger.info(f"Configuring {name}...")
        await kos.actuator.configure_actuator(
            actuator_id=actuator_id, 
            kp=DEFAULT_KP, 
            kd=DEFAULT_KD, 
            max_torque=DEFAULT_MAX_TORQUE, 
            torque_enabled=True
        )

        # Move forward
        target_position = current_position + movement_degrees
        logger.info(f"Moving {name} to {target_position:.2f} degrees...")
        await kos.actuator.command_actuators([{"actuator_id": actuator_id, "position": target_position}])
        await asyncio.sleep(wait_time)

        # Check if it moved
        state = await kos.actuator.get_actuators_state([actuator_id])
        new_position = state.states[0].position
        moved_forward = abs(new_position - current_position) > 1.0

        logger.info(f"{name} new position: {new_position:.2f} degrees")
        if moved_forward:
            logger.info(f"✅ {name} successfully moved forward")
        else:
            logger.warning(f"❌ {name} did not move forward as expected")

        # Store results
        test_results = {
            "success": moved_forward,
            "actuator_id": actuator_id,
            "name": name,
            "start_position": current_position,
            "forward_movement": {
                "target": target_position,
                "achieved": new_position,
                "delta": abs(new_position - current_position),
                "moved": moved_forward,
            },
        }

        # Move back to original position
        logger.info(f"Moving {name} back to {current_position:.2f} degrees...")
        await kos.actuator.command_actuators([{"actuator_id": actuator_id, "position": current_position}])
        await asyncio.sleep(wait_time)

        # Disable torque
        try:
            await kos.actuator.configure_actuator(actuator_id=actuator_id, torque_enabled=False)
            logger.info(f"Disabled torque on {name}")
        except Exception as e:
            logger.warning(f"Error disabling torque: {e}")

        return test_results

    except Exception as e:
        logger.error(f"Error testing actuator {actuator_id}: {e}")
        try:
            await kos.actuator.configure_actuator(actuator_id=actuator_id, torque_enabled=False)
        except Exception:
            pass
        return {"success": False, "message": f"Error testing actuator {actuator_id}: {str(e)}"}


async def get_actuator_state(kos, actuator_id: int) -> Dict[str, Any]:
    """Get detailed state of an actuator."""
    if not validate_actuator_id(actuator_id):
        return {"error": f"Invalid actuator ID: {actuator_id}"}

    try:
        state = await kos.actuator.get_actuators_state([actuator_id])
        if not state.states:
            return {"error": f"Could not get state for actuator {actuator_id}"}

        actuator_state = state.states[0]
        name = ID_TO_NAME.get(actuator_id, f"Actuator {actuator_id}")

        return {
            "id": actuator_id,
            "name": name,
            "position": actuator_state.position,
            "velocity": actuator_state.velocity,
            "torque": actuator_state.torque,
            "temperature": actuator_state.temperature,
            "torque_enabled": actuator_state.torque_enabled,
            "error_code": actuator_state.error_code,
        }
    except Exception as e:
        return {"error": f"Error getting state for actuator {actuator_id}: {str(e)}"}


async def test_servos(
    robot_ip: str = DEFAULT_ROBOT_IP, 
    actuator_ids: List[int] = DEFAULT_TEST_ACTUATORS
) -> Dict[int, Dict[str, Any]]:
    """Test multiple servos."""
    # Input validation with user-friendly messages
    if not actuator_ids:
        print("❌ Error: No actuator IDs provided. Please specify at least one actuator ID.")
        return {"error": "No actuator IDs provided"}

    invalid_ids = validate_actuator_ids(actuator_ids)
    if invalid_ids:
        print(f"❌ Error: Invalid actuator IDs: {invalid_ids}")
        print(f"Valid actuator IDs are: {VALID_ACTUATOR_IDS}")
        return {"error": f"Invalid actuator IDs: {invalid_ids}"}

    kos = await connect_to_robot(robot_ip)
    if not kos:
        print(
            f"❌ Error: Failed to connect to robot at {robot_ip}. "
            f"Please check the IP address and network connection."
        )
        return {"error": "Failed to connect to robot"}

    results = {}
    for actuator_id in actuator_ids:
        logger.info(f"\n--- Testing actuator {actuator_id} ---")
        result = await test_actuator_movement(kos, actuator_id)
        results[actuator_id] = result
        await asyncio.sleep(0.5)

    # Print summary
    print("\n=== Test Results Summary ===")
    all_success = True

    for actuator_id, result in results.items():
        success = result.get("success", False)
        name = result.get("name", f"Actuator {actuator_id}")
        status = "✅ PASS" if success else "❌ FAIL"

        if not success:
            all_success = False

        print(f"{name} (ID: {actuator_id}): {status}")

    if all_success:
        print("\n✅ All actuators passed the movement test!")
    else:
        print("\n⚠️ Some actuators failed the movement test.")

    return results


async def test_servo(robot_ip: str = DEFAULT_ROBOT_IP, actuator_id: int = 11) -> Dict[str, Any]:
    """Test a single servo."""
    if not validate_actuator_id(actuator_id):
        return {"success": False, "message": f"Invalid actuator ID: {actuator_id}"}

    kos = await connect_to_robot(robot_ip)
    if not kos:
        return {"success": False, "message": "Failed to connect to robot"}

    return await test_actuator_movement(kos, actuator_id)


async def move_servo(
    robot_ip: str = DEFAULT_ROBOT_IP, 
    actuator_id: int = 11, 
    position: float = None, 
    relative_movement: float = None
) -> Dict[str, Any]:
    """Move a servo to a position or by a relative amount."""
    if position is None and relative_movement is None:
        return {"error": "Either position or relative_movement must be specified"}

    if not validate_actuator_id(actuator_id):
        return {"success": False, "message": f"Invalid actuator ID: {actuator_id}"}

    kos = await connect_to_robot(robot_ip)
    if not kos:
        return {"success": False, "message": "Failed to connect to robot"}

    try:
        # If relative movement is specified, get current position
        target_position = position
        if relative_movement is not None:
            state = await kos.actuator.get_actuators_state([actuator_id])
            if not state.states:
                return {"success": False, "message": f"Could not get state for actuator {actuator_id}"}

            current_position = state.states[0].position
            target_position = current_position + relative_movement

        # Configure actuator for safe movement
        name = ID_TO_NAME.get(actuator_id, f"Actuator {actuator_id}")
        logger.info(f"Configuring {name}...")
        await kos.actuator.configure_actuator(
            actuator_id=actuator_id, 
            kp=DEFAULT_KP, 
            kd=DEFAULT_KD, 
            max_torque=DEFAULT_MAX_TORQUE, 
            torque_enabled=True
        )

        # Get state before moving
        before_state = await kos.actuator.get_actuators_state([actuator_id])
        before_position = before_state.states[0].position

        # Move actuator
        logger.info(f"Moving {name} to {target_position:.2f} degrees...")
        await kos.actuator.command_actuators([{"actuator_id": actuator_id, "position": target_position}])
        await asyncio.sleep(DEFAULT_WAIT_TIME)

        # Get state after movement
        after_state = await kos.actuator.get_actuators_state([actuator_id])
        after_position = after_state.states[0].position

        # Calculate movement metrics
        movement_delta = abs(after_position - before_position)
        moved = movement_delta > 1.0

        result = {
            "success": moved,
            "name": name,
            "id": actuator_id,
            "start_position": before_position,
            "target_position": target_position,
            "final_position": after_position,
            "movement_delta": movement_delta,
            "moved": moved,
        }

        # Disable torque
        await kos.actuator.configure_actuator(actuator_id=actuator_id, torque_enabled=False)
        logger.info(f"Disabled torque on {name}")

        return result

    except Exception as e:
        logger.error(f"Error moving actuator {actuator_id}: {e}")
        try:
            await kos.actuator.configure_actuator(actuator_id=actuator_id, torque_enabled=False)
        except Exception:
            pass
        return {"success": False, "message": str(e)}


async def get_servo_state(robot_ip: str = DEFAULT_ROBOT_IP, actuator_id: int = 11) -> Dict[str, Any]:
    """Get the state of a single servo."""
    if not validate_actuator_id(actuator_id):
        return {"error": f"Invalid actuator ID: {actuator_id}"}

    kos = await connect_to_robot(robot_ip)
    if not kos:
        return {"error": "Failed to connect to robot"}

    state = await get_actuator_state(kos, actuator_id)

    # Print state in a readable format
    if "error" not in state:
        name = state["name"]
        print(f"\n=== State of {name} (ID: {actuator_id}) ===")
        print(f"  Position: {state['position']:.2f} degrees")
        print(f"  Velocity: {state['velocity']:.2f} deg/s")
        print(f"  Torque: {state['torque']:.2f}")
        print(f"  Temperature: {state['temperature']:.1f}°C")
        print(f"  Torque enabled: {state['torque_enabled']}")

        if state["error_code"]:
            print(f"  ❌ Error code: {state['error_code']}")
    else:
        print(f"❌ Error: {state['error']}")

    return state


async def list_available_servos(robot_ip: str = DEFAULT_ROBOT_IP) -> Dict[str, Any]:
    """List all available servos and their current status."""
    kos = await connect_to_robot(robot_ip)
    if not kos:
        return {"error": "Failed to connect to robot"}

    results = {}
    print("\n=== Available Servos ===")
    print(f"{'ID':<5} {'Name':<20} {'Status':<10}")
    print("-" * 40)

    for actuator_id in VALID_ACTUATOR_IDS:
        try:
            state = await kos.actuator.get_actuators_state([actuator_id])
            if state.states:
                name = ID_TO_NAME.get(actuator_id, f"Actuator {actuator_id}")
                status = "✅ OK" if not state.states[0].error_code else f"❌ Error: {state.states[0].error_code}"
                print(f"{actuator_id:<5} {name:<20} {status:<10}")
                results[actuator_id] = {
                    "name": name,
                    "status": "ok" if not state.states[0].error_code else "error",
                    "error_code": state.states[0].error_code,
                    "position": state.states[0].position,
                    "temperature": state.states[0].temperature,
                }
            else:
                print(f"{actuator_id:<5} {ID_TO_NAME.get(actuator_id, 'Unknown'):<20} {'❓ Not responding':<10}")
                results[actuator_id] = {"status": "not_responding"}
        except Exception:
            print(f"{actuator_id:<5} {ID_TO_NAME.get(actuator_id, 'Unknown'):<20} {'❌ Error':<10}")
            results[actuator_id] = {"status": "error"}

    return results


# Synchronous wrapper functions
def test_servo_sync(robot_ip: str = DEFAULT_ROBOT_IP, actuator_id: int = 11) -> Dict[str, Any]:
    """Synchronous wrapper for test_servo."""
    return asyncio.run(test_servo(robot_ip, actuator_id))


def test_servos_sync(
    robot_ip: str = DEFAULT_ROBOT_IP, 
    actuator_ids: List[int] = DEFAULT_TEST_ACTUATORS
) -> Dict[int, Dict[str, Any]]:
    """Synchronous wrapper for test_servos."""
    # Input validation before running async code
    if not actuator_ids:
        print("❌ Error: No actuator IDs provided. Please specify at least one actuator ID.")
        return {"error": "No actuator IDs provided"}

    invalid_ids = validate_actuator_ids(actuator_ids)
    if invalid_ids:
        print(f"❌ Error: Invalid actuator IDs: {invalid_ids}")
        print(f"Valid actuator IDs are: {VALID_ACTUATOR_IDS}")
        return {"error": f"Invalid actuator IDs: {invalid_ids}"}

    return asyncio.run(test_servos(robot_ip, actuator_ids))


def get_servo_state_sync(robot_ip: str = DEFAULT_ROBOT_IP, actuator_id: int = 11) -> Dict[str, Any]:
    """Synchronous wrapper for get_servo_state."""
    # Input validation before running async code
    if not validate_actuator_id(actuator_id):
        print(f"❌ Error: Invalid actuator ID: {actuator_id}")
        print(f"Valid actuator IDs are: {VALID_ACTUATOR_IDS}")
        return {"error": f"Invalid actuator ID: {actuator_id}"}

    return asyncio.run(get_servo_state(robot_ip, actuator_id))


def move_servo_sync(
    robot_ip: str = DEFAULT_ROBOT_IP, 
    actuator_id: int = 11, 
    position: float = None, 
    relative_movement: float = None
) -> Dict[str, Any]:
    """Synchronous wrapper for move_servo."""
    # Input validation before running async code
    if position is None and relative_movement is None:
        print("❌ Error: Either position or relative_movement must be specified")
        return {"error": "Either position or relative_movement must be specified"}

    if not validate_actuator_id(actuator_id):
        print(f"❌ Error: Invalid actuator ID: {actuator_id}")
        print(f"Valid actuator IDs are: {VALID_ACTUATOR_IDS}")
        return {"success": False, "message": f"Invalid actuator ID: {actuator_id}"}

    return asyncio.run(move_servo(robot_ip, actuator_id, position, relative_movement))


def list_available_servos_sync(robot_ip: str = DEFAULT_ROBOT_IP) -> Dict[str, Any]:
    """Synchronous wrapper for list_available_servos."""
    return asyncio.run(list_available_servos(robot_ip))


def help():
    """Print help information about the servo testing module."""
    print(
        """
Servo Testing Module for KOS Robots
===================================

Available Functions:
-------------------
test_servos_sync(robot_ip="10.33.10.65", actuator_ids=[11, 21, 31, 41])
    Test multiple servos by moving them slightly and checking response.

test_servo_sync(robot_ip="10.33.10.65", actuator_id=11)
    Test a single servo by moving it slightly and checking response.

get_servo_state_sync(robot_ip="10.33.10.65", actuator_id=11)
    Get detailed state information about a servo (position, temperature, etc).

move_servo_sync(robot_ip="10.33.10.65", actuator_id=11, position=None, relative_movement=None)
    Move a servo to an absolute position or by a relative amount.

list_available_servos_sync(robot_ip="10.33.10.65")
    List all available servos and their current status.

Common Servo IDs:
---------------
11: left_shoulder_yaw     21: right_shoulder_yaw
12: left_shoulder_pitch   22: right_shoulder_pitch
13: left_elbow_yaw        23: right_elbow_yaw
14: left_gripper          24: right_gripper
31: left_hip_yaw          41: right_hip_yaw
32: left_hip_roll         42: right_hip_roll
33: left_hip_pitch        43: right_hip_pitch
34: left_knee_pitch       44: right_knee_pitch
35: left_ankle_pitch      45: right_ankle_pitch

Example Usage:
------------
# Import the module
from kos_sdk.tests import servos

# List all available servos
servos.list_available_servos_sync()

# Test a specific servo
servos.test_servo_sync(actuator_id=11)

# Move a servo
servos.move_servo_sync(actuator_id=11, position=10.0)
"""
    )


# Add this at the end of your file, just before the if __name__ == "__main__" block
# Define what gets imported with "from kos_sdk.tests.servos import *"
__all__ = [
    "test_servo_sync",
    "test_servos_sync",
    "get_servo_state_sync",
    "move_servo_sync",
    "list_available_servos_sync",
    "help",
    "JOINT_MAP",
    "VALID_ACTUATOR_IDS",
]


if __name__ == "__main__":
    try:
        asyncio.run(test_servos())
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    except Exception as e:
        logger.error(f"Unhandled exception: {e}")
