import asyncio
from loguru import logger
from typing import Any, Dict, List, Optional, Tuple
from utils.robot import ID_TO_JOINT, RobotInterface

DEFAULT_MOVEMENT_DEGREES = 10.0
DEFAULT_WAIT_TIME = 0.5

async def test_actuator_movement(
    robot_ip: str = "", 
    actuator_id: Optional[int] = None
) -> Dict[str, Any]:
    """Test actuators and report which ones moved successfully."""
    
    async with RobotInterface(ip=robot_ip) as robot:
        results = {"success": [], "failed": []}
        
        try:
            await robot.configure_actuators()
            
            actuator_ids = [actuator_id] if actuator_id is not None else list(ID_TO_JOINT.keys())
            
            for act_id in actuator_ids:
                name = ID_TO_JOINT.get(act_id, f"Actuator {act_id}")
                success, reason = await test_single_actuator(robot, act_id, name)
                
                result_data = {"id": act_id, "name": name}
                if not success and reason:
                    result_data["reason"] = reason
                    
                results["success" if success else "failed"].append(result_data)
                
                if len(actuator_ids) > 1:
                    await asyncio.sleep(0.5)
                
        except Exception as e:
            logger.error(f"Actuator test failed: {e}")
            return {"success": [], "failed": [], "error": str(e)}
        
        log_test_results(results)
        return results

async def test_single_actuator(
    robot: RobotInterface, 
    actuator_id: int, 
    name: str
) -> Tuple[bool, Optional[str]]:
    """Test a single actuator and return (success, reason)."""
    try:
        state = await robot.kos.actuator.get_actuators_state([actuator_id])
        if not state.states:
            return False, "Could not get state"
            
        current_position = state.states[0].position
        target_position = current_position + DEFAULT_MOVEMENT_DEGREES
        
        await robot.set_real_command_positions({name: target_position})
        await asyncio.sleep(DEFAULT_WAIT_TIME)
        
        state = await robot.kos.actuator.get_actuators_state([actuator_id])
        new_position = state.states[0].position
        moved = abs(new_position - current_position) > 1.0
        
        await robot.set_real_command_positions({name: current_position})
        await asyncio.sleep(DEFAULT_WAIT_TIME)
        await robot.kos.actuator.configure_actuator(
            actuator_id=actuator_id, 
            torque_enabled=False
        )
        
        logger.info(f"{name} {'moved successfully' if moved else 'did not move'}")
        return moved, None if moved else "Did not move"
            
    except Exception as e:
        logger.error(f"Error testing {name}: {e}")
        try:
            await robot.kos.actuator.configure_actuator(
                actuator_id=actuator_id, 
                torque_enabled=False
            )
        except:
            pass
        return False, str(e)

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
    return asyncio.run(test_actuator_movement(robot_ip, actuator_id))

__all__ = ["test_servo_sync"]