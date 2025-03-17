import asyncio
from loguru import logger
import subprocess
from typing import Dict, Any

async def test_connection(robot_ip: str = "") -> Dict[str, Any]:
    """Test connection to the robot."""
    logger.info(f"Starting connection test to {robot_ip}...")
    
    try:
        subprocess.run(["ping", "-c", "1", robot_ip], 
                      stdout=subprocess.DEVNULL, 
                      stderr=subprocess.DEVNULL, 
                      check=True)
        logger.success(f"Robot {robot_ip} is reachable via ping")
    except subprocess.CalledProcessError:
        result = {
            "success": False, 
            "message": "Robot not reachable via ping", 
            "api_responding": False
        }
        logger.error(f"Connection test failed: {result['message']}")
        return result

def test_connection_sync(robot_ip: str = "") -> Dict[str, Any]:
    """Synchronous wrapper for test_connection."""
    return asyncio.run(test_connection(robot_ip))

__all__ = ["test_connection_sync"]

