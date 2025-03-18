import asyncio
from loguru import logger
from typing import Any, Dict, List, Optional, Union
from utils.robot import ID_TO_JOINT, RobotInterface

DEFAULT_MOVEMENT_DEGREES = 10.0
DEFAULT_WAIT_TIME = 0.5

def create_result(success: bool, actuator_id: int, name: str, reason: str = None) -> Dict[str, Any]:
    """Create a standardized result dictionary for actuator tests."""
    result = {"success": success, "data": {"id": actuator_id, "name": name}}
    if not success and reason:
        result["data"]["reason"] = reason
    return result

async def test_actuator_movement(
    robot_ip: str = "", 
    actuator_id: Optional[int] = None
) -> Dict[str, Any]:
    """Test actuators and report which ones moved successfully."""
    
    async with RobotInterface(ip=robot_ip) as robot:
        kos = robot.kos
        results = {"success": [], "failed": []}
        
        try:
            await robot.configure_actuators()
            
            if actuator_id is not None:
                # Test a single specific actuator
                name = ID_TO_JOINT.get(actuator_id, f"Actuator {actuator_id}")
                result = await test_single_actuator(kos, actuator_id, name)
                results["success" if result["success"] else "failed"].append(result["data"])
            else:
                # Test all actuators
                actuator_ids = list(ID_TO_JOINT.keys())
                for act_id in actuator_ids:
                    name = ID_TO_JOINT.get(act_id, f"Actuator {act_id}")
                    result = await test_single_actuator(kos, act_id, name)
                    results["success" if result["success"] else "failed"].append(result["data"])
                    await asyncio.sleep(0.5)
                
        except Exception as e:
            logger.error(f"Actuator test failed: {e}")
            return {"success": [], "failed": [], "error": str(e)}
        
        log_test_results(results)
        return results

async def test_single_actuator(kos, actuator_id: int, name: str) -> Dict[str, Any]:
    try:
        state = await kos.actuator.get_actuators_state([actuator_id])
        if not state.states:
            return create_result(False, actuator_id, name, "Could not get state")
            
        current_position = state.states[0].position
        
        target_position = current_position + DEFAULT_MOVEMENT_DEGREES
        await kos.actuator.command_actuators(
            [{"actuator_id": actuator_id, "position": target_position}])
        await asyncio.sleep(DEFAULT_WAIT_TIME)
        
        state = await kos.actuator.get_actuators_state([actuator_id])
        new_position = state.states[0].position
        moved = abs(new_position - current_position) > 1.0
        
        await kos.actuator.command_actuators(
            [{"actuator_id": actuator_id, "position": current_position}])
        await asyncio.sleep(DEFAULT_WAIT_TIME)
        
        await kos.actuator.configure_actuator(actuator_id=actuator_id, torque_enabled=False)
        
        if moved:
            logger.info(f"{name} moved successfully")
            return create_result(True, actuator_id, name)
        else:
            logger.warning(f"{name} did not move")
            return create_result(False, actuator_id, name, "Did not move")
            
    except Exception as e:
        logger.error(f"Error testing {name}: {e}")
        try:
            await kos.actuator.configure_actuator(actuator_id=actuator_id, torque_enabled=False)
        except:
            pass
        return create_result(False, actuator_id, name, str(e))

def log_test_results(results: Dict[str, List]) -> None:
    logger.info("\n=== Actuator Test Results ===")
    logger.info(f"Successfully moved ({len(results['success'])}):")
    for actuator in results["success"]:
        logger.info(f"  - {actuator['name']} (ID: {actuator['id']})")
    
    logger.info(f"\nFailed to move ({len(results['failed'])}):")
    for actuator in results["failed"]:
        logger.info(f"  - {actuator['name']} (ID: {actuator['id']}): {actuator.get('reason', 'Unknown')}")

def test_servo_sync(
    robot_ip: str = "", 
    actuator_id: Optional[int] = None
) -> Dict[str, Any]:
    """Synchronous wrapper for test_actuator_movement."""
    return asyncio.run(test_actuator_movement(robot_ip))

__all__ = ["test_servo_sync"]