"""
KOS SDK Testing Package
======================

This package provides testing tools for various components of KOS robots.

Available Modules:
----------------
- servos: Test and control servo motors
- camera: Test and access camera functionality
- microphone: Test and access microphone functionality
- led: Test and control the LED matrix
- imu: Test and analyze the Inertial Measurement Unit
- connection: Test and diagnose robot connectivity

Usage:
-----
# Import the entire package
import kos_sdk.tests

# Access specific test modules
from kos_sdk.tests import servos, camera, microphone, led, imu, connection

# Or import specific functions
from kos_sdk.tests.servos import test_servo_sync
"""

# Import submodules to make them available directly
from . import test_servos as servos
# from . import test_camera as camera
from . import test_microphone as microphone
from . import test_led as led
from . import test_imu as imu
from . import test_connection as connection

# Define what gets imported with "from kos_sdk.tests import *"
__all__ = ['servos', 'camera', 'microphone', 'led', 'imu', 'connection']

# Package version
__version__ = '0.1.0'


def help():
    """Print help information about the testing package."""
    print("""
KOS SDK Testing Package
======================

This package provides testing tools for various components of KOS robots.

Available Test Modules:
---------------------
servos:
    Test and control servo motors on KOS robots.
    Key functions: test_servo_sync(), move_servo_sync(), get_servo_state_sync()

camera:
    Test and access camera functionality.
    Key functions: test_camera_sync(), capture_image_sync()

microphone:
    Test and access microphone functionality.
    Key functions: test_microphone_sync(), record_audio_sync()

led:
    Test and control the LED matrix.
    Key functions: run_test_sequence_sync(), display_pattern_sync()

imu:
    Test and analyze the Inertial Measurement Unit.
    Key functions: test_imu_sync(), visualize_orientation_sync()

connection:
    Test and diagnose robot connectivity.
    Key functions: test_connection_sync(), measure_latency_sync()

Example Usage:
------------
# Test a servo
from kos_sdk.tests.servos import test_servo_sync
result = test_servo_sync(actuator_id=11)

# Test the LED matrix
from kos_sdk.tests.led import run_test_sequence_sync
result = run_test_sequence_sync()

# Test the IMU
from kos_sdk.tests.imu import test_imu_sync
result = test_imu_sync()

# Test the connection
from kos_sdk.tests.connection import test_connection_sync
result = test_connection_sync()

# For more details on each module, use their specific help functions:
from kos_sdk.tests import servos
servos.help()
""") 