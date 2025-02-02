import json
import os
import time
from unit_types import Degree
from typing import Union
from planners.skills_data import SkillData, Frame, load_skill


class PlaySkill:
    def __init__(self, skill_name : str) -> None:
        self.skill_data = None
        self.current_frame_index = 0
        self.last_frame_time = 0.0
        self.frame_delay = 0.0
        self.load_skill_file(skill_name)

    def load_skill_file(self, filename: str) -> None:
        base_path = os.path.join(os.path.dirname(__file__), "recorded_skills")
        if not filename.endswith(".json"):
            filename += ".json"
        filepath = os.path.join(base_path, filename)
        self.skill_data = load_skill(filepath)
        self.current_frame_index = 0
        self.last_frame_time = time.time()
        self.frame_delay = 1.0 / self.skill_data.frequency

    def update(self) -> None:
        if not self.skill_data or self.current_frame_index >= len(self.skill_data.frames):
            return

        current_time = time.time()
        if current_time - self.last_frame_time >= self.frame_delay:
            self.current_frame_index += 1
            self.last_frame_time = current_time

    def get_command_positions(self) -> dict[str, Union[int, Degree]]:
        """
        Return joint commands for the current frame.
        This will be called during each simulation cycle in run.py.
        """
        if not self.skill_data or self.current_frame_index >= len(self.skill_data.frames):
            return {}

        frame = self.skill_data.frames[self.current_frame_index]
        return frame.joint_positions