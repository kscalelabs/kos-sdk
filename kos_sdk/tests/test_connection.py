"""
Connection Testing Module for KOS Robots
=======================================

This module provides tools for testing and verifying the connection to KOS robots.
It allows you to check connectivity and measure latency.

Available Functions:
------------------
test_connection_sync(robot_ip="10.33.10.65")
    Test basic connectivity to the robot and verify that essential services are responding.

measure_latency_sync(robot_ip="10.33.10.65", num_pings=10)
    Measure the round-trip latency between the client and the robot.

Technical Details:
----------------
- Tests TCP/IP connectivity to the robot
- Verifies that the KOS API services are responding
- Measures round-trip latency for performance assessment

Example Usage:
------------
# Import the module
from kos_sdk.tests import connection

# Test basic connectivity
result = connection.test_connection_sync()
if result["success"]:
    print("Robot is connected!")

# Measure connection latency
latency = connection.measure_latency_sync()
print(f"Average latency: {latency['avg_latency_ms']} ms")

# For detailed help
connection.help()
"""

import asyncio
import logging
import socket
import time
from typing import Dict, List, Any, Optional

import pykos

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_ROBOT_IP = "10.33.10.65"
DEFAULT_TIMEOUT = 5.0  # seconds


async def test_connection(robot_ip: str = DEFAULT_ROBOT_IP) -> Dict[str, Any]:
    """Test basic connectivity to the robot.
    
    This function checks if the robot is reachable and if the KOS API is responding.
    """
    result = {
        "success": False,
        "ip_reachable": False,
        "api_responding": False,
        "message": "",
        "details": {}
    }
    
    # First, check if the IP is reachable with a simple socket connection
    try:
        logger.info(f"Testing TCP connectivity to {robot_ip}...")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(DEFAULT_TIMEOUT)
        
        # Try to connect to port 22 (SSH) which should be open on the robot
        start_time = time.time()
        sock.connect((robot_ip, 22))
        connection_time = time.time() - start_time
        
        sock.close()
        result["ip_reachable"] = True
        result["details"]["tcp_connection_time_ms"] = round(connection_time * 1000, 2)
        logger.info(f"TCP connection successful ({result['details']['tcp_connection_time_ms']} ms)")
    except socket.error as e:
        result["message"] = f"Failed to connect to robot at {robot_ip}: {str(e)}"
        logger.error(f"{result['message']}")
        return result
    
    # Now check if the KOS API is responding
    try:
        logger.info(f"Testing KOS API connectivity...")
        start_time = time.time()
        kos = pykos.KOS(ip=robot_ip)
        
        # Try to get a simple response from the API
        await kos.actuator.get_actuators_state([11])
        api_time = time.time() - start_time
        
        result["api_responding"] = True
        result["details"]["api_response_time_ms"] = round(api_time * 1000, 2)
        result["success"] = True
        result["message"] = "Connection to robot successful"
        logger.info(f"KOS API responding ({result['details']['api_response_time_ms']} ms)")
    except Exception as e:
        result["message"] = f"Robot is reachable but KOS API is not responding: {str(e)}"
        logger.error(f"{result['message']}")
    
    return result


async def measure_latency(robot_ip: str = DEFAULT_ROBOT_IP, num_pings: int = 10) -> Dict[str, Any]:
    """Measure the round-trip latency between the client and the robot.
    
    Args:
        robot_ip: IP address of the robot
        num_pings: Number of ping measurements to take
        
    Returns:
        Dictionary with latency statistics
    """
    result = {
        "success": False,
        "message": "",
        "latencies_ms": [],
        "avg_latency_ms": 0,
        "min_latency_ms": 0,
        "max_latency_ms": 0,
        "jitter_ms": 0
    }
    
    try:
        logger.info(f"Measuring latency to {robot_ip} ({num_pings} pings)...")
        kos = pykos.KOS(ip=robot_ip)
        
        latencies = []
        for i in range(num_pings):
            start_time = time.time()
            # Use a lightweight API call for latency measurement
            await kos.actuator.get_actuators_state([11])
            latency = time.time() - start_time
            latencies.append(latency * 1000)  # Convert to milliseconds
            logger.info(f"Ping {i+1}/{num_pings}: {latency * 1000:.2f} ms")
            await asyncio.sleep(0.1)  # Small delay between pings
        
        # Calculate statistics
        result["latencies_ms"] = [round(lat, 2) for lat in latencies]
        result["avg_latency_ms"] = round(sum(latencies) / len(latencies), 2)
        result["min_latency_ms"] = round(min(latencies), 2)
        result["max_latency_ms"] = round(max(latencies), 2)
        result["jitter_ms"] = round(max(latencies) - min(latencies), 2)
        
        result["success"] = True
        result["message"] = f"Latency measurement completed. Average: {result['avg_latency_ms']} ms"
        logger.info(f"{result['message']}")
    except Exception as e:
        result["message"] = f"Failed to measure latency: {str(e)}"
        logger.error(f"{result['message']}")
    
    return result


def test_connection_sync(robot_ip: str = DEFAULT_ROBOT_IP) -> Dict[str, Any]:
    """Synchronous wrapper for test_connection."""
    return asyncio.run(test_connection(robot_ip))


def measure_latency_sync(robot_ip: str = DEFAULT_ROBOT_IP, num_pings: int = 10) -> Dict[str, Any]:
    """Synchronous wrapper for measure_latency."""
    return asyncio.run(measure_latency(robot_ip, num_pings))


def help():
    """Print help information about the connection testing module."""
    print("""
Connection Testing Module for KOS Robots
=======================================

Available Functions:
------------------
test_connection_sync(robot_ip="10.33.10.65")
    Test basic connectivity to the robot and verify that essential services are responding.

measure_latency_sync(robot_ip="10.33.10.65", num_pings=10)
    Measure the round-trip latency between the client and the robot.

Technical Details:
----------------
- Tests TCP/IP connectivity to the robot
- Verifies that the KOS API services are responding
- Measures round-trip latency for performance assessment

Example Usage:
------------
# Import the module
from kos_sdk.tests import connection

# Test basic connectivity
result = connection.test_connection_sync()
if result["success"]:
    print("Robot is connected!")

# Measure connection latency
latency = connection.measure_latency_sync()
print(f"Average latency: {latency['avg_latency_ms']} ms")
""")


# Define what gets imported with "from kos_sdk.tests.connection import *"
__all__ = [
    'test_connection_sync',
    'measure_latency_sync',
    'help'
]


if __name__ == "__main__":
    try:
        # Run basic connection test
        result = asyncio.run(test_connection())
        if result["success"]:
            print(f"Connection test successful!")
            print(f"IP reachable: {result['ip_reachable']}")
            print(f"API responding: {result['api_responding']}")
            if "details" in result:
                print(f"TCP connection time: {result['details'].get('tcp_connection_time_ms', 'N/A')} ms")
                print(f"API response time: {result['details'].get('api_response_time_ms', 'N/A')} ms")
            
            # If connection is successful, measure latency
            print("\nMeasuring connection latency...")
            latency_result = asyncio.run(measure_latency())
            if latency_result["success"]:
                print(f"Average latency: {latency_result['avg_latency_ms']} ms")
                print(f"Minimum latency: {latency_result['min_latency_ms']} ms")
                print(f"Maximum latency: {latency_result['max_latency_ms']} ms")
                print(f"Jitter: {latency_result['jitter_ms']} ms")
        else:
            print(f"Connection test failed: {result['message']}")
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    except Exception as e:
        logger.error(f"Unhandled exception: {e}")
