import os
import json
import time
import math
from typing import Dict, Union, List, Optional
from unit_types import Degree
from dataclasses import dataclass
from loguru import logger


@dataclass
class Frame:
    joint_positions: Dict[str, Union[int, Degree]]
    delay: float


@dataclass
class SkillData:
    name: str
    frames: List[Frame]


class PlaySkill:
    def __init__(self, skill_name: str, frequency: float) -> None:
        """Initialize the skill player.

        Args:
            skill_name: Name of the skill to play
            frequency: Interpolation frequency in Hz
        """
        self.frequency = frequency
        self.frame_delay = 1.0 / frequency
        self.skill_data: Optional[SkillData] = None
        self.current_frame_index = 0
        self.interpolation_time = 0.0
        self.last_update_time = time.time()
        self.current_positions: Dict[str, Union[int, Degree]] = {}
        self.previous_positions: Dict[str, Union[int, Degree]] = {}
        self.max_velocity = 40.0  # Maximum velocity in degrees per second
        self.use_smooth_interpolation = True  # Use smooth interpolation by default
        self.load_skill_file(skill_name)

        # Add a shorter startup delay to allow the robot to get ready
        self.startup_delay = 1.0  # 1 second before starting playback (reduced from 2)
        self.startup_timer = 0.0
        self.is_ready = False
        logger.info(f"Playback will start in {self.startup_delay} seconds...")

    def load_skill_file(self, skill_name: str) -> None:
        """Load a skill from a JSON file.

        Args:
            skill_name: Name of the skill file (without .json extension)
        """
        base_path = os.path.join(os.path.dirname(__file__), "recorded_skills")
        if not skill_name.endswith(".json"):
            skill_name += ".json"
        filepath = os.path.join(base_path, skill_name)

        try:
            with open(filepath, "r") as f:
                data = json.load(f)
                frames = [
                    Frame(
                        joint_positions=frame["joint_positions"], delay=frame["delay"]
                    )
                    for frame in data["frames"]
                ]
                self.skill_data = SkillData(name=data["name"], frames=frames)
            logger.info(
                f"Loaded skill {skill_name} with {len(self.skill_data.frames)} frames"
            )
            if self.skill_data.frames:
                # Normalize joint names in all frames to ensure compatibility
                self._normalize_joint_names()
                self.current_positions = self.skill_data.frames[
                    0
                ].joint_positions.copy()
                self.previous_positions = self.current_positions.copy()
        except Exception as e:
            logger.error(f"Failed to load skill {skill_name}: {e}")
            self.skill_data = None

    def _normalize_joint_names(self):
        """Normalize joint names in all frames to ensure compatibility with robot interface."""
        if not self.skill_data:
            return

        # Define joint name mappings for compatibility
        joint_name_map = {
            "left_elbow": "left_elbow_yaw",
            "right_elbow": "right_elbow_yaw",
        }

        # Check if we need to do any normalization
        needs_normalization = False
        for frame in self.skill_data.frames:
            for old_name in joint_name_map.keys():
                if old_name in frame.joint_positions:
                    needs_normalization = True
                    break
            if needs_normalization:
                break

        if not needs_normalization:
            logger.debug("Joint names already normalized, no changes needed")
            return

        # Normalize joint names in all frames
        logger.info("Normalizing joint names in skill data for compatibility")
        for frame in self.skill_data.frames:
            normalized_positions = {}
            for joint_name, position in frame.joint_positions.items():
                # Use the normalized name if available, otherwise keep the original
                normalized_name = joint_name_map.get(joint_name, joint_name)
                normalized_positions[normalized_name] = position
            frame.joint_positions = normalized_positions

    def smooth_interpolation(self, t: float) -> float:
        """Apply a smooth interpolation function (ease in/out).

        Args:
            t: Linear interpolation parameter (0.0 to 1.0)

        Returns:
            Smoothed interpolation parameter
        """
        # Cubic ease in/out function: smoother acceleration and deceleration
        if t < 0.5:
            return 4 * t * t * t
        else:
            return 1 - pow(-2 * t + 2, 3) / 2

    def update(self, feedback_positions: Dict[str, Union[int, Degree]]) -> None:
        """Update interpolation between keyframes."""
        if not self.skill_data or self.current_frame_index >= len(
            self.skill_data.frames
        ):
            return

        current_time = time.time()
        dt = current_time - self.last_update_time
        self.last_update_time = current_time

        # Handle startup delay
        if not self.is_ready:
            self.startup_timer += dt
            if self.startup_timer >= self.startup_delay:
                self.is_ready = True
                logger.info("Starting playback now...")
            else:
                # During startup, just use the feedback positions
                self.current_positions = feedback_positions.copy()
                return

        current_frame = self.skill_data.frames[self.current_frame_index]
        self.interpolation_time += dt

        # Save previous positions for velocity limiting
        self.previous_positions = self.current_positions.copy()

        # If we've reached the delay time, move to next frame
        if self.interpolation_time >= current_frame.delay:
            self.current_frame_index += 1
            self.interpolation_time = 0.0
            if self.current_frame_index < len(self.skill_data.frames):
                # Don't directly copy - we'll interpolate to avoid jumps
                next_frame = self.skill_data.frames[self.current_frame_index]
                logger.info(
                    f"Moving to frame {self.current_frame_index}/{len(self.skill_data.frames)}"
                )
            return

        # Interpolate between current and next frame
        if self.current_frame_index + 1 < len(self.skill_data.frames):
            next_frame = self.skill_data.frames[self.current_frame_index + 1]

            # Calculate linear interpolation parameter
            t = self.interpolation_time / current_frame.delay

            # Apply smooth interpolation if enabled
            if self.use_smooth_interpolation:
                t = self.smooth_interpolation(t)

            # Interpolate each joint position
            for joint in current_frame.joint_positions:
                if joint in next_frame.joint_positions:
                    current_pos = current_frame.joint_positions[joint]
                    next_pos = next_frame.joint_positions[joint]

                    # Calculate interpolated position
                    interpolated_pos = current_pos + (next_pos - current_pos) * t

                    # Apply velocity limiting
                    if joint in self.previous_positions:
                        prev_pos = self.previous_positions[joint]
                        # Calculate velocity in degrees per second
                        velocity = abs(interpolated_pos - prev_pos) / dt

                        # If velocity exceeds limit, cap it
                        if velocity > self.max_velocity:
                            # Direction of movement
                            direction = 1 if interpolated_pos > prev_pos else -1
                            # Limit movement to max_velocity * dt
                            max_change = self.max_velocity * dt
                            interpolated_pos = prev_pos + (direction * max_change)
                            logger.debug(
                                f"Velocity limited for {joint}: {velocity:.2f} deg/s -> {self.max_velocity:.2f} deg/s"
                            )

                    self.current_positions[joint] = interpolated_pos

    def get_command_positions(self) -> Dict[str, Union[int, Degree]]:
        """Get the interpolated joint positions.

        Returns:
            Dictionary of joint positions, or empty dict if no skill loaded
            or playback complete
        """
        if not self.skill_data or self.current_frame_index >= len(
            self.skill_data.frames
        ):
            return {}
        return self.current_positions
