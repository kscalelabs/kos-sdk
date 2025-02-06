# Standard imports
import os
import json
import time
import math
from typing import Dict, Union, List, Optional
from unit_types import Degree
from dataclasses import dataclass
from loguru import logger


# Data structures for storing skill information
@dataclass
class Frame:
    # Single frame of a recorded skill containing joint positions and timing
    joint_positions: Dict[str, Union[int, Degree]]  # Joint angles
    delay: float  # Time to next frame


@dataclass
class SkillData:
    # Container for entire skill
    name: str
    frames: List[Frame]


class PlaySkill:
    def __init__(self, skill_name: str, frequency: float) -> None:
        """
        Initialization of skill playback system.

        Key components:
        - frequency: How often we update positions (e.g. 100Hz = 100 updates/second)
        - dt: Time step between updates (e.g. 1/100 = 0.01s)
        - current_positions: Current commanded joint positions
        - initial_transition: True while moving to start position
        - transition_duration: How long to take to reach start position (10s)
        """
        self.frequency = frequency
        self.dt = 1.0 / frequency
        self.skill_data: Optional[SkillData] = None
        self.current_frame_index = 0
        self.current_positions: Dict[str, Union[int, Degree]] = {}
        self.playback_complete = False
        self.needs_torque = True
        self.transitioning_to_start = True
        self.transition_start_time = None
        self.transition_duration = 10.0  # seconds to reach start position
        self.initial_positions = None
        self.first_update = True

        # Load the skill file
        self.load_skill_file(skill_name)

    def smooth_interpolation(self, t: float) -> float:
        """
        Smooth acceleration/deceleration using cosine interpolation.
        Takes a linear 0-1 input and produces smooth 0-1 output.

        The cosine curve gives:
        - Slow start (gradual acceleration)
        - Faster middle
        - Slow end (gradual deceleration)
        """
        return (1 - math.cos(t * math.pi)) / 2

    def load_skill_file(self, skill_name: str) -> None:
        """
        Load recorded skill from JSON file.
        Each frame contains joint positions and timing information.
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
        except Exception as e:
            logger.error(f"Failed to load skill {skill_name}: {e}")
            self.skill_data = None

    def update(self, feedback_positions: Dict[str, Union[int, Degree]]) -> None:
        """Update with smooth transition to start and interpolation between frames"""
        if not self.skill_data or not self.skill_data.frames or self.playback_complete:
            return

        # Handle very first update - just capture current positions
        if self.first_update:
            self.current_positions = feedback_positions.copy()
            self.initial_positions = feedback_positions.copy()
            self.first_update = False
            self.transition_start_time = time.time()
            logger.info("Starting transition to initial position...")
            return

        # Handle transition to start position
        if self.transitioning_to_start:
            # Calculate transition progress
            elapsed = time.time() - self.transition_start_time
            t = min(1.0, elapsed / self.transition_duration)
            smooth_t = self.smooth_interpolation(t)

            # Smoothly move to start position
            target_positions = self.skill_data.frames[0].joint_positions
            for joint in target_positions:
                if joint in self.initial_positions:
                    start_pos = self.initial_positions[joint]
                    end_pos = target_positions[joint]
                    self.current_positions[joint] = (
                        start_pos + (end_pos - start_pos) * smooth_t
                    )

            # Check if transition is complete
            if elapsed >= self.transition_duration:
                self.transitioning_to_start = False
                self._last_frame_time = time.time()
                logger.info("Transition complete, starting playback")
            return

        # Normal playback logic
        if self.current_frame_index >= len(self.skill_data.frames) - 1:
            logger.info("Playback complete")
            self.playback_complete = True
            return

        # Get current and next frame
        current_frame = self.skill_data.frames[self.current_frame_index]
        next_frame = self.skill_data.frames[self.current_frame_index + 1]

        # Calculate interpolation factor
        elapsed = time.time() - self._last_frame_time
        t = min(1.0, elapsed / current_frame.delay)
        smooth_t = self.smooth_interpolation(t)

        # Interpolate between frames
        for joint in current_frame.joint_positions:
            if joint in next_frame.joint_positions:
                start_pos = current_frame.joint_positions[joint]
                end_pos = next_frame.joint_positions[joint]
                self.current_positions[joint] = (
                    start_pos + (end_pos - start_pos) * smooth_t
                )

        # Move to next frame when delay is reached
        if elapsed >= current_frame.delay:
            logger.info(f"Moving to frame {self.current_frame_index + 1}")
            self.current_frame_index += 1
            self._last_frame_time = time.time()

    def get_command_positions(self) -> Dict[str, Union[int, Degree]]:
        """
        Return current commanded positions.
        This could be:
        1. Positions during initial transition
        2. Positions during normal playback
        3. Empty dict if playback complete
        """
        if not self.skill_data or self.current_frame_index >= len(
            self.skill_data.frames
        ):
            return {}
        return self.current_positions

    def needs_torque_enable(self) -> bool:
        """
        Manage torque enabling.
        Returns True only once when we first need torque.
        """
        if self.needs_torque and self.skill_data is not None:
            self.needs_torque = False
            return True
        return False
