from dataclasses import dataclass
from typing import Optional

@dataclass
class JointState:
    """Represents the current state of a joint.

    Examples:
        ```python
        # Create a joint state
        state = JointState(position=1.57, velocity=0.5, torque=0.2)

        # Access state properties
        current_position = state.position
        current_velocity = state.velocity
        current_torque = state.torque
        ```
    """
    position: float
    velocity: float
    torque: float

class Joint:
    """Represents a single robot joint with a human-readable name.

    Examples:
        ```python
        # Create a new joint
        shoulder_joint = Joint(name="shoulder", actuator_id=1)

        # Access joint properties
        joint_name = shoulder_joint.name  # "shoulder"
        actuator_id = shoulder_joint.actuator_id  # 1

        # Access the joint's state (might be None if not updated yet)
        if shoulder_joint.state:
            current_position = shoulder_joint.state.position
        ```
    """

    def __init__(self, name: str, actuator_id: int):
        self.name = name
        self.actuator_id = actuator_id
        self._state: Optional[JointState] = None

    @property
    def state(self) -> Optional[JointState]:
        """Get the last known state of the joint.

        Returns:
            The current JointState or None if state hasn't been updated yet.

        Examples:
            ```python
            # Check if joint has state before accessing
            if joint.state:
                print(f"Current position: {joint.state.position}")
            ```
        """
        return self._state

    def __repr__(self) -> str:
        return f"Joint(name='{self.name}', id={self.actuator_id})"

class JointGroup:
    """A collection of joints that can be controlled together.

    Examples:
        ```python
        # Create individual joints
        shoulder = Joint(name="shoulder", actuator_id=1)
        elbow = Joint(name="elbow", actuator_id=2)
        wrist = Joint(name="wrist", actuator_id=3)

        # Create a joint group
        arm_group = JointGroup(name="arm", joints=[shoulder, elbow, wrist])

        # Iterate through joints in a group
        for joint in arm_group:
            print(joint.name)  # Prints: shoulder, elbow, wrist

        # Access group properties
        print(len(arm_group))  # Prints: 3
        ```
    """

    def __init__(self, name: str, joints: list[Joint]):
        self.name = name
        self.joints = joints

    @property
    def actuator_ids(self) -> list[int]:
        """Get list of actuator IDs in this group.

        Returns:
            List of actuator IDs for all joints in this group.

        Examples:
            ```python
            # Get all actuator IDs to send a command to multiple joints
            ids = arm_group.actuator_ids  # [1, 2, 3]
            ```
        """
        return [joint.actuator_id for joint in self.joints]

    def get_joint(self, name: str) -> Optional[Joint]:
        """Get a joint by name.

        Args:
            name: The name of the joint to find

        Returns:
            The joint if found, None otherwise

        Examples:
            ```python
            # Get a specific joint from the group
            elbow = arm_group.get_joint("elbow")
            if elbow:
                print(f"Found elbow joint with ID: {elbow.actuator_id}")
            ```
        """
        for joint in self.joints:
            if joint.name == name:
                return joint
        return None

    def __iter__(self):
        return iter(self.joints)

    def __len__(self):
        return len(self.joints)

    def __repr__(self) -> str:
        return f"JointGroup(name='{self.name}', joints={len(self.joints)})"
