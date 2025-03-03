"""
Unit types for robot control.
"""

from typing import Union, NewType

# Define types for clarity in function signatures
Degree = NewType("Degree", float)
Radian = NewType("Radian", float)


# Allow for conversion between degrees and radians
def degrees_to_radians(degrees: Union[float, Degree]) -> Radian:
    """Convert degrees to radians."""
    return Radian(float(degrees) * 0.017453292519943295)  # pi/180


def radians_to_degrees(radians: Union[float, Radian]) -> Degree:
    """Convert radians to degrees."""
    return Degree(float(radians) * 57.29577951308232)  # 180/pi
