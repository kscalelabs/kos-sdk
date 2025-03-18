"""
KOS SDK Testing Package

Provides testing tools for various components of KOS robots.
"""

# Import submodules
from . import test_connection as connection
from . import test_imu as imu
from . import test_led as led
from . import test_servos as servos
from . import test_actuators_connection as actuators_connection

# Define what gets imported with "from kos_sdk.tests import *"
__all__ = ["servos", "led", "imu", "connection", "actuators_connection"]

# Package version
__version__ = "0.1.0"