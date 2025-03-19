import subprocess
from typing import Any, Dict

from loguru import logger


async def test_connection(robot_ip: str = "") -> Dict[str, Any]:
    """Test connection to the robot."""
    logger.info(f"Starting connection test to {robot_ip}...")

    try:
        subprocess.run(
            ["ping", "-c", "1", robot_ip],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        return {"success": True, "message": "Robot is reachable via ping"}
    except subprocess.CalledProcessError:
        result = {
            "success": False,
            "message": "Robot not reachable via ping",
            "api_responding": False,
        }
        logger.error(f"Connection test failed: {result['message']}")
        return result