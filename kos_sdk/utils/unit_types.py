import math
from typing import NewType, cast

Radian = NewType("Radian", float)
Degree = NewType("Degree", float)


def deg_to_rad(degrees: Degree) -> Radian:
    """Convert degrees to radians."""
    return cast(Radian, math.radians(degrees))


def rad_to_deg(radians: Radian) -> Degree:
    """Convert radians to degrees."""
    return cast(Degree, math.degrees(radians))
