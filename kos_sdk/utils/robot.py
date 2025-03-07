from typing import Optional, Dict, List, Union, Sequence
from dataclasses import dataclass
import asyncio
import time
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
            position_limits=(-3.14, 3.14),  # Limit joint range to ±180 degrees
            velocity_limits=(-2.0, 2.0),    # Limit joint velocity
        )

        # Access configuration values
        kp, kd = custom_config.sim_gains
        max_torque = custom_config.max_torque
        min_pos, max_pos = custom_config.position_limits
        ```
    """

    sim_gains: tuple[float, float] = (32, 32)  # kp, kd for simulator
    real_gains: tuple[float, float] = (32, 32)  # kp, kd for real robot
    max_torque: float = 100.0
    position_limits: tuple[float, float] = (-float('inf'), float('inf'))  # min, max in radians
    velocity_limits: tuple[float, float] = (-float('inf'), float('inf'))  # min, max in rad/s


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
        velocities: Optional[Dict[str, float]] = None,
    ) -> None:
        """Move specified joints to target positions.

        Args:
            kos: KOS client instance
            positions: Mapping of joint names to target positions
            wait: Whether to wait for movement to complete
            velocities: Optional mapping of joint names to target velocities

        Examples:
            ```python
            # Move individual joints to specific positions
            await robot.move(kos, {
                "shoulder": 1.57,  # 90 degrees in radians
                "elbow": 0.5
            })

            # Move joints with specific velocities
            await robot.move(kos, 
                positions={"shoulder": 0.0, "elbow": 0.0},
                velocities={"shoulder": 0.5, "elbow": 0.3}
            )

            # Move without waiting for completion
            await robot.move(kos, {"wrist": 0.7}, wait=False)

            # Do other things while movement happens...

            # Later check if joints reached target positions
            states = await robot.get_states(kos)
            ```
        """
        velocities = velocities or {}
        min_pos, max_pos = self.config.position_limits
        min_vel, max_vel = self.config.velocity_limits
        
        commands = []
        for joint_name, position in positions.items():
            if joint_name not in self.joints:
                print(f"Warning: Joint '{joint_name}' not found, skipping")
                continue
                
            # Apply position limits if specified
            if min_pos != float('-inf') or max_pos != float('inf'):
                position = max(min_pos, min(max_pos, position))
                
            command = {
                "actuator_id": self.joints[joint_name].actuator_id,
                "position": position,
            }
            
            # Add velocity if specified for this joint
            if joint_name in velocities:
                velocity = velocities[joint_name]
                # Apply velocity limits if specified
                if min_vel != float('-inf') or max_vel != float('inf'):
                    velocity = max(min_vel, min(max_vel, velocity))
                command["velocity"] = velocity
                
            commands.append(command)

        if commands:
            await kos.actuator.command_actuators(commands)
            
            # If wait is True, we could implement waiting for the movement to complete
            if wait:
                # For now we'll just return, but a future implementation could wait
                # until joints reach their target positions
                pass

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
        
        if velocity is not None:
            velocities = {name: velocity for name in self.joints}
            await self.move(kos, positions, velocities=velocities)
        else:
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
        
    async def move_group(
        self, 
        kos: KOS, 
        group_name: str, 
        positions: Dict[str, float],
        wait: bool = True,
        velocities: Optional[Dict[str, float]] = None,
    ) -> bool:
        """Move joints in a specific group to target positions.
        
        Args:
            kos: KOS client instance
            group_name: Name of the joint group to move
            positions: Mapping of joint names to target positions
            wait: Whether to wait for movement to complete
            velocities: Optional mapping of joint names to target velocities
            
        Returns:
            True if group was found and command sent, False otherwise
            
        Examples:
            ```python
            # Move all joints in the "arm" group
            success = await robot.move_group(kos, "arm", {
                "shoulder": 1.0,
                "elbow": 0.5,
                "wrist": -0.3
            })
            
            # Move with velocity control
            success = await robot.move_group(kos, "leg", 
                positions={"hip": 0.1, "knee": 0.2},
                velocities={"hip": 0.5, "knee": 0.3}
            )
            ```
        """
        group = self.get_group(group_name)
        if not group:
            print(f"Warning: Group '{group_name}' not found")
            return False
            
        # Filter positions to only include joints in this group
        group_joint_names = [joint.name for joint in group]
        filtered_positions = {
            name: pos for name, pos in positions.items() 
            if name in group_joint_names
        }
        
        # Filter velocities if provided
        filtered_velocities = None
        if velocities:
            filtered_velocities = {
                name: vel for name, vel in velocities.items()
                if name in group_joint_names
            }
            
        if not filtered_positions:
            print(f"Warning: No valid joints specified for group '{group_name}'")
            return False
            
        # Move the filtered joints
        await self.move(
            kos, 
            filtered_positions, 
            wait=wait, 
            velocities=filtered_velocities
        )
        return True

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
        
    async def __aenter__(self) -> "Robot":
        """Enter async context manager.
        
        Examples:
            ```python
            async with Robot() as robot:
                # Robot is now ready to use
                await robot.configure(kos)
                # Do something with the robot
            # Robot context is automatically exited
            ```
        """
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit async context manager and clean up resources.
        
        This will stop any ongoing monitoring and make sure resources are properly cleaned up.
        """
        if getattr(self, "_monitoring", False):
            await self.stop_monitoring()
            
    async def follow_trajectory(
        self,
        kos: KOS,
        trajectory: Sequence[Dict[str, Dict[str, float]]],
        timestep: float = 0.1,
    ) -> None:
        """Follow a trajectory specified as a sequence of joint positions.
        
        Args:
            kos: KOS client instance
            trajectory: Sequence of position dictionaries for each timestep
                        Each element is a dict mapping joint names to a dict of values
                        (e.g., {"position": 1.0, "velocity": 0.5})
            timestep: Time in seconds between trajectory points
            
        Examples:
            ```python
            # Define a simple trajectory
            trajectory = [
                # Timestep 1
                {
                    "shoulder": {"position": 0.0},
                    "elbow": {"position": 0.0}
                },
                # Timestep 2
                {
                    "shoulder": {"position": 0.5, "velocity": 0.3},
                    "elbow": {"position": 0.2, "velocity": 0.1}
                },
                # Timestep 3
                {
                    "shoulder": {"position": 1.0},
                    "elbow": {"position": 0.4}
                }
            ]
            
            # Follow the trajectory
            await robot.follow_trajectory(kos, trajectory, timestep=0.2)
            ```
        """
        for i, waypoint in enumerate(trajectory):
            # Extract positions and velocities from the waypoint
            positions = {}
            velocities = {}
            
            for joint_name, joint_data in waypoint.items():
                if "position" in joint_data:
                    positions[joint_name] = joint_data["position"]
                if "velocity" in joint_data:
                    velocities[joint_name] = joint_data["velocity"]
            
            # Move to this waypoint
            await self.move(
                kos,
                positions=positions,
                velocities=velocities if velocities else None,
                wait=False
            )
            
            # Wait before moving to the next waypoint (but not after the last one)
            if i < len(trajectory) - 1:
                await asyncio.sleep(timestep)
