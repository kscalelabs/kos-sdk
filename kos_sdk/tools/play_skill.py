import json
import os
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Union

from loguru import logger
from unit_types import Degree


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
        self.load_skill_file(skill_name)

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
                    Frame(joint_positions=frame["joint_positions"], delay=frame["delay"])
                    for frame in data["frames"]
                ]
                self.skill_data = SkillData(name=data["name"], frames=frames)
            logger.info(f"Loaded skill {skill_name} with {len(self.skill_data.frames)} frames")
            if self.skill_data.frames:
                self.current_positions = self.skill_data.frames[0].joint_positions.copy()
        except Exception as e:
            logger.error(f"Failed to load skill {skill_name}: {e}")
            self.skill_data = None

    def update(self, feedback_positions: Dict[str, Union[int, Degree]]) -> None:
        """Update interpolation between keyframes."""
        if not self.skill_data or self.current_frame_index >= len(self.skill_data.frames):
            return

        current_time = time.time()
        dt = current_time - self.last_update_time
        self.last_update_time = current_time

        current_frame = self.skill_data.frames[self.current_frame_index]
        self.interpolation_time += dt

        # If we've reached the delay time, move to next frame
        if self.interpolation_time >= current_frame.delay:
            self.current_frame_index += 1
            self.interpolation_time = 0.0
            if self.current_frame_index < len(self.skill_data.frames):
                self.current_positions = self.skill_data.frames[
                    self.current_frame_index
                ].joint_positions.copy()
            return

        # Interpolate between current and next frame
        if self.current_frame_index + 1 < len(self.skill_data.frames):
            next_frame = self.skill_data.frames[self.current_frame_index + 1]
            t = self.interpolation_time / current_frame.delay

            for joint in current_frame.joint_positions:
                current_pos = current_frame.joint_positions[joint]
                next_pos = next_frame.joint_positions[joint]
                self.current_positions[joint] = current_pos + (next_pos - current_pos) * t

    def get_command_positions(self) -> Dict[str, Union[int, Degree]]:
        """Get the interpolated joint positions.

        Returns:
            Dictionary of joint positions, or empty dict if no skill loaded
            or playback complete
        """
        if not self.skill_data or self.current_frame_index >= len(self.skill_data.frames):
            return {}
        return self.current_positions
