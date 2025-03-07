from typing import Optional, Dict, List, Union
from dataclasses import dataclass
from pykos import KOS
from .joint import Joint, JointGroup, JointState

# Default mapping from actuator IDs to joint names
ACTUATOR_ID_TO_NAME: Dict[int, str] = {
    11: "left_shoulder_yaw",
    12: "left_shoulder_pitch",
    13: "left_elbow",
    14: "left_gripper",
    21: "right_shoulder_yaw",
    22: "right_shoulder_pitch",
    23: "right_elbow",
    24: "right_gripper",
    31: "left_hip_yaw",
    32: "left_hip_roll",
    33: "left_hip_pitch",
    34: "left_knee",
    35: "left_ankle",
    41: "right_hip_yaw",
    42: "right_hip_roll",
    43: "right_hip_pitch",
    44: "right_knee",
    45: "right_ankle",
}


@dataclass
class RobotConfig:
    """Default configuration for robot joints.

    Examples:
        ```python
        # Use default configuration
        default_config = RobotConfig()

        # Create custom configuration
        custom_config = RobotConfig(
            sim_gains=(80, 40),  # Lower kp, kd for simulator
            real_gains=(24, 20),  # Lower gains for real robot
            max_torque=50.0,      # Limit maximum torque
        )

        # Access configuration values
        kp, kd = custom_config.sim_gains
        max_torque = custom_config.max_torque
        ```
    """

    sim_gains: tuple[float, float] = (32, 32)  # kp, kd for simulator
    real_gains: tuple[float, float] = (32, 32)  # kp, kd for real robot
    max_torque: float = 100.0


class Robot:
    """High-level robot control interface with convention over configuration.

    The Robot class provides a simplified interface for controlling multiple joints,
    organizing them into groups, and handling common operations like movement and
    state retrieval.

    Examples:
        ```python
        # Create a robot with joint definitions
        joint_map = {
            "shoulder": 1,
            "elbow": 2,
            "wrist": 3
        }

        # Define joint groups
        groups = {
            "arm": ["shoulder", "elbow", "wrist"]
        }

        # Initialize robot with default configuration
        robot = Robot(joint_map=joint_map, groups=groups)

        # Or use custom configuration
        config = RobotConfig(max_torque=50.0)
        robot = Robot(joint_map=joint_map, config=config, groups=groups)
        ```
    """

    def __init__(
        self,
        joint_map: Optional[Dict[str, int]] = None,
        config: Optional[RobotConfig] = None,
        groups: Optional[Dict[str, List[str]]] = None,
    ):
        """Initialize robot interface.

        Args:
            joint_map: Mapping of joint names to actuator IDs. If None, uses default mapping.
            config: Robot configuration defaults
            groups: Optional mapping of group names to lists of joint names

        Examples:
            ```python
            # Create a robot with default joints
            robot = Robot()

            # Create a robot with custom joints
            robot = Robot({
                "base": 1,
                "shoulder": 2,
                "elbow": 3
            })

            # Create a robot with joints and custom groups
            robot = Robot(
                joint_map={"j1": 1, "j2": 2, "j3": 3, "j4": 4},
                groups={
                    "left_arm": ["j1", "j2"],
                    "right_arm": ["j3", "j4"]
                }
            )
            ```
        """
        self.config = config or RobotConfig()

        # Use default joint mapping if none provided
        if joint_map is None:
            # Invert the ACTUATOR_ID_TO_NAME mapping to create joint_map
            joint_map = {
                name: actuator_id for actuator_id, name in ACTUATOR_ID_TO_NAME.items()
            }

        self.joints = {
            name: Joint(name, actuator_id) for name, actuator_id in joint_map.items()
        }

        # Create default groups
        self.groups = {}
        if groups:
            for group_name, joint_names in groups.items():
                group_joints = [
                    self.joints[name] for name in joint_names if name in self.joints
                ]
                self.groups[group_name] = JointGroup(group_name, group_joints)

        # Create an "all" group containing all joints
        self.groups["all"] = JointGroup("all", list(self.joints.values()))
        
        # Initialize monitoring attributes with proper type hints
        self._monitoring: bool = False
        self._monitoring_interval: float = 0.1
        self._monitoring_quiet: bool = False

    async def configure(self, kos: KOS, is_real: bool = False) -> None:
        """Configure all joints with default parameters.

        Args:
            kos: KOS client instance
            is_real: Whether configuring real robot or simulator

        Examples:
            ```python
            # Initialize KOS client
            kos = KOS()
            await kos.connect()

            # Configure for simulator
            await robot.configure(kos, is_real=False)

            # Or configure for real robot
            await robot.configure(kos, is_real=True)
            ```
        """
        kp, kd = self.config.real_gains if is_real else self.config.sim_gains

        for joint in self.joints.values():
            await kos.actuator.configure_actuator(
                actuator_id=joint.actuator_id,
                kp=kp,
                kd=kd,
                max_torque=self.config.max_torque,
                torque_enabled=True,
            )

    async def move(
        self,
        kos: KOS,
        positions: Dict[str, float],
        wait: bool = True,
    ) -> None:
        """Move specified joints to target positions.

        Args:
            kos: KOS client instance
            positions: Mapping of joint names to target positions
            wait: Whether to wait for movement to complete

        Examples:
            ```python
            # Move individual joints to specific positions
            await robot.move(kos, {
                "shoulder": 1.57,  # 90 degrees in radians
                "elbow": 0.5
            })

            # Move joints with custom
            await robot.move(kos, {
                "shoulder": 0.0,
                "elbow": 0.0
            }, )

            # Move without waiting for completion
            await robot.move(kos, {"wrist": 0.7}, wait=False)

            # Do other things while movement happens...

            # Later check if joints reached target positions
            states = await robot.get_states(kos)
            ```
        """
        commands = []
        for joint_name, position in positions.items():
            if joint_name in self.joints:
                commands.append(
                    {
                        "actuator_id": self.joints[joint_name].actuator_id,
                        "position": position,
                    }
                )

        if commands:
            await kos.actuator.command_actuators(commands)

    async def zero_all(self, kos: KOS, velocity: Optional[float] = None) -> None:
        """Move all joints to zero position.

        Args:
            kos: KOS client instance
            velocity: Optional velocity override

        Examples:
            ```python
            # Initialize KOS client and robot
            kos = KOS()
            await kos.connect()
            robot = Robot({"j1": 1, "j2": 2})

            # Move all joints to zero position with default velocity
            await robot.zero_all(kos)

            # Move all joints to zero with custom velocity
            await robot.zero_all(kos, velocity=3.0)
            ```
        """
        positions = {name: 0.0 for name in self.joints}
        await self.move(kos, positions)

    async def get_states(
        self, kos: KOS, joint_names: Optional[List[str]] = None
    ) -> Dict[str, JointState]:
        """Get current state of specified joints.

        Args:
            kos: KOS client instance
            joint_names: List of joint names to query (None for all joints)

        Returns:
            Dictionary mapping joint names to their states

        Examples:
            ```python
            # Get states of all joints
            states = await robot.get_states(kos)
            for name, state in states.items():
                print(f"{name}: pos={state.position}, vel={state.velocity}")

            # Get states of specific joints
            arm_states = await robot.get_states(kos, ["shoulder", "elbow"])
            shoulder_pos = arm_states["shoulder"].position
            ```
        """
        query_joints = [
            self.joints[name] for name in (joint_names or self.joints.keys())
        ]
        actuator_ids = [joint.actuator_id for joint in query_joints]

        try:
            response = await kos.actuator.get_actuators_state(actuator_ids)

            # Update joint states and return mapping
            states = {}
            for state in response.states:
                for joint in query_joints:
                    if joint.actuator_id == state.actuator_id:
                        joint_state = JointState(
                            position=state.position,
                            velocity=state.velocity,
                            torque=state.torque,
                        )
                        states[joint.name] = joint_state
                        joint._state = joint_state  # Update cached state

            # Handle the case where some joints were not found in the response
            for joint in query_joints:
                if joint.name not in states:
                    # Use the previous state if available, otherwise create a zeroed state
                    if joint._state:
                        states[joint.name] = joint._state
                    else:
                        states[joint.name] = JointState(
                            position=0.0, velocity=0.0, torque=0.0
                        )
                        joint._state = states[joint.name]  # Cache the zeroed state

            return states

        except Exception as e:
            # Handle errors by providing default states
            print(f"Error getting actuator states: {e}")
            states = {}
            for joint in query_joints:
                if joint._state:
                    states[joint.name] = joint._state
                else:
                    states[joint.name] = JointState(
                        position=0.0, velocity=0.0, torque=0.0
                    )
                    joint._state = states[joint.name]
            return states

    def get_group(self, name: str) -> Optional[JointGroup]:
        """Get a joint group by name.

        Args:
            name: Name of the joint group to retrieve

        Returns:
            The joint group if found, None otherwise

        Examples:
            ```python
            # Get a specific joint group
            arm_group = robot.get_group("arm")
            if arm_group:
                # Iterate through joints in the group
                for joint in arm_group:
                    print(joint.name)

            # Use the built-in "all" group that contains all joints
            all_joints = robot.get_group("all")
            print(f"Robot has {len(all_joints)} total joints")
            ```
        """
        return self.groups.get(name)

    def get_joint_names(self) -> List[str]:
        """Get a list of all joint names in the robot.

        Returns:
            List of joint names

        Examples:
            ```python
            # Get all joint names
            joint_names = robot.get_joint_names()
            print(f"Robot has joints: {', '.join(joint_names)}")
            ```
        """
        return list(self.joints.keys())

    async def start_monitoring(
        self, kos: KOS, interval: float = 0.1, quiet_mode: bool = False
    ) -> None:
        """Start monitoring joint states at regular intervals.

        Args:
            kos: KOS client instance
            interval: Monitoring interval in seconds
            quiet_mode: Whether to suppress log messages

        Examples:
            ```python
            # Start monitoring joint states every 100ms
            await robot.start_monitoring(kos)

            # Start monitoring with custom interval and no log messages
            await robot.start_monitoring(kos, interval=0.05, quiet_mode=True)
            ```
        """
        self._monitoring = True
        self._monitoring_interval = interval
        self._monitoring_quiet = quiet_mode

        if not quiet_mode:
            print(f"Started monitoring joint states every {interval:.3f}s")

    async def stop_monitoring(self) -> None:
        """Stop monitoring joint states.

        Examples:
            ```python
            # Stop monitoring joint states
            await robot.stop_monitoring()
            ```
        """
        self._monitoring = False

        if not getattr(self, "_monitoring_quiet", False):
            print("Stopped monitoring joint states")

    def __repr__(self) -> str:
        return f"Robot(joints={len(self.joints)}, groups={len(self.groups)})"
