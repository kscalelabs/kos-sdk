from utils.robot import RobotInterface, JOINT_TO_ID, ID_TO_JOINT
from loguru import logger
from typing import Dict

async def test_actuator_connection(robot_ip: str = "") -> Dict:
    """Test connection to all actuators and report which ones are responding."""
    async with RobotInterface(ip=robot_ip) as robot:
        all_actuator_ids = set(JOINT_TO_ID.values())
        
        logger.info("Checking actuator responses...")
        try:
            feedback_state = await robot.kos.actuator.get_actuators_state(list(all_actuator_ids))
            responding_ids = {state.actuator_id for state in feedback_state.states}
            missing_ids = all_actuator_ids - responding_ids
            
            if not missing_ids:
                logger.success(f"All {len(all_actuator_ids)} actuators are responding!")
            else:
                logger.warning(f"Found {len(responding_ids)} of {len(all_actuator_ids)} actuators.")
                logger.error(f"Missing actuators: {sorted(missing_ids)}")
                missing_joints = [ID_TO_JOINT.get(id, f"Unknown-{id}") for id in missing_ids]
                logger.error(f"Missing joints: {sorted(missing_joints)}")
            
            return {
                "success": len(missing_ids) == 0,
                "total_actuators": len(all_actuator_ids),
                "responding_actuators": len(responding_ids),
                "responding_ids": sorted(list(responding_ids)),
                "missing_ids": sorted(list(missing_ids)),
                "missing_joints": sorted([ID_TO_JOINT.get(id, f"Unknown-{id}") for id in missing_ids]) if missing_ids else []
            }
            
        except Exception as e:
            logger.error(f"Failed to get actuator feedback: {e}")
            return {
                "success": False,
                "error": str(e)
            }

__all__ = ["test_actuator_connection"]