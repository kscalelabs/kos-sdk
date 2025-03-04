import json
import os
import platform
import queue
import tkinter as tk
import tkinter.messagebox
from dataclasses import asdict, dataclass
from multiprocessing import Process, Queue
from tkinter import ttk
from typing import Dict, List, Union

from loguru import logger
from planners.keyboard_tk import KeyboardActor
from unit_types import Degree

IS_MACOS = platform.system() == "Darwin"


@dataclass
class Frame:
    joint_positions: Dict[str, Union[int, Degree]]
    delay: float  # Delay in seconds before next frame


@dataclass
class SkillData:
    name: str
    frames: List[Frame]


class GUIProcess(Process):
    """A separate process for running the GUI."""

    def __init__(self, skill_name: str, command_queue: Queue, position_queue: Queue):
        super().__init__()
        self.skill_name = skill_name
        self.command_queue = command_queue
        self.position_queue = position_queue
        self.current_positions_queue = Queue()
        self.daemon = True

    def run(self):
        """Run the GUI in a separate process."""
        window = tk.Tk()
        window.title(f"Robot Control - Recording: {self.skill_name}")
        window.geometry("560x800")

        # Create notebook for tabs
        notebook = ttk.Notebook(window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Create keyboard control tab with scrollbar
        keyboard_frame = ttk.Frame(notebook)
        notebook.add(keyboard_frame, text="Joint Control")

        # Add canvas and scrollbar for scrolling
        canvas = tk.Canvas(keyboard_frame)
        scrollbar = ttk.Scrollbar(keyboard_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Pack scrollbar system
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        # Initialize keyboard control in the scrollable frame
        robot = KeyboardActor(
            joint_names=[
                "left_hip_yaw",
                "left_hip_roll",
                "left_hip_pitch",
                "left_knee",
                "left_ankle",
                "right_hip_yaw",
                "right_hip_roll",
                "right_hip_pitch",
                "right_knee",
                "right_ankle",
                "left_shoulder_yaw",
                "left_shoulder_pitch",
                "left_elbow_yaw",
                "right_shoulder_yaw",
                "right_shoulder_pitch",
                "right_elbow_yaw",
            ],
            parent_frame=scrollable_frame,
        )

        # Add mousewheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # Create recording control tab
        record_frame = ttk.Frame(notebook)
        notebook.add(record_frame, text="Recording")

        # Frame count label
        frame_count_label = ttk.Label(record_frame, text="Frames: 0")
        frame_count_label.pack(pady=10)

        # Delay selection
        delay_frame = ttk.Frame(record_frame)
        delay_frame.pack(pady=10)

        ttk.Label(delay_frame, text="Delay before next frame (seconds):").pack(side=tk.LEFT)
        delay_var = tk.StringVar(value="1.0")
        delay_entry = ttk.Entry(delay_frame, textvariable=delay_var, width=10)
        delay_entry.pack(side=tk.LEFT, padx=5)

        # Quick delay buttons
        delays_frame = ttk.Frame(record_frame)
        delays_frame.pack(pady=5)
        for delay in [0.5, 1.0, 2.0]:
            ttk.Button(
                delays_frame, text=f"{delay}s", command=lambda d=delay: delay_var.set(str(d))
            ).pack(side=tk.LEFT, padx=5)

        # Record button
        record_btn = ttk.Button(
            record_frame,
            text="Record Keyframe",
            command=lambda: self.command_queue.put(
                ("record", robot.get_joint_angles(), float(delay_var.get()))
            ),
        )
        record_btn.pack(pady=10)

        # Save button
        save_btn = ttk.Button(
            record_frame, text="Save and Exit", command=lambda: self.command_queue.put(("quit",))
        )
        save_btn.pack(pady=10)

        # Set up window close handler
        window.protocol("WM_DELETE_WINDOW", lambda: self.command_queue.put(("quit",)))

        def check_commands():
            try:
                while True:
                    cmd = self.position_queue.get_nowait()
                    if cmd[0] == "update_count":
                        frame_count_label.config(text=f"Frames: {cmd[1]}")
                    elif cmd[0] == "quit":
                        window.quit()
                        return
                    elif cmd[0] == "get_positions":
                        self.current_positions_queue.put(robot.get_joint_angles())
            except queue.Empty:
                pass
            window.after(10, check_commands)

        window.after(10, check_commands)
        window.mainloop()


class RecordSkill:
    def __init__(self, skill_name: str, frequency: float) -> None:
        """Initialize the skill recorder.

        Args:
            skill_name: Name of the skill to record
            frequency: Recording frequency in Hz (used for playback)
        """
        self.skill_name = skill_name
        self.frequency = frequency
        self.frames: List[Frame] = []
        self.recording = True
        self.last_positions: Dict[str, Union[int, Degree]] = {}
        self.is_sim = False

        # Create queues for process communication
        self.command_queue = Queue()
        self.position_queue = Queue()

        # Start GUI process
        self.gui_process = GUIProcess(skill_name, self.command_queue, self.position_queue)
        self.gui_process.start()

        logger.info(f"Started recording skill: {skill_name}")

        self.current_positions_queue = self.gui_process.current_positions_queue

    def update(self, feedback_state: Union[Dict[str, Union[int, Degree]], None]) -> None:
        """Process commands from GUI."""
        self.last_positions = feedback_state
        if feedback_state is None:
            self.is_sim = True
        if self.recording:
            try:
                while True:
                    cmd = self.command_queue.get_nowait()
                    if cmd[0] == "record":
                        positions, delay = cmd[1], cmd[2]
                        if not self.is_sim:
                            positions = self.last_positions
                        frame = Frame(joint_positions=positions, delay=delay)
                        self.frames.append(frame)
                        self.position_queue.put(("update_count", len(self.frames)))
                        logger.info(f"Recorded keyframe {len(self.frames)} with {delay}s delay")
                    elif cmd[0] == "quit":
                        self.save_and_exit()
            except queue.Empty:
                pass

    def get_command_positions(self) -> Dict[str, Union[int, Degree]]:
        """Return the current joint positions."""
        if not self.is_sim:
            return self.last_positions
        if self.recording:
            self.position_queue.put(("get_positions",))
            try:
                return self.current_positions_queue.get(timeout=0.1)
            except queue.Empty:
                logger.warning("Timeout getting positions from GUI")
                return {}
        return {}

    def save_and_exit(self) -> None:
        """Save the recorded skill and close the GUI."""
        self.save()
        self.recording = False
        self.position_queue.put(("quit",))
        self.gui_process.join(timeout=1.0)
        if self.gui_process.is_alive():
            self.gui_process.terminate()

    def save(self) -> None:
        """Save the recorded skill to a JSON file."""
        if not self.frames:
            logger.warning("No frames recorded, skipping save")
            return

        base_path = os.path.join(os.path.dirname(__file__), "recorded_skills")
        os.makedirs(base_path, exist_ok=True)

        skill_data = SkillData(name=self.skill_name, frames=self.frames)

        filename = f"{self.skill_name}.json"
        filepath = os.path.join(base_path, filename)

        try:
            with open(filepath, "w") as f:
                json.dump(asdict(skill_data), f, indent=2)
            logger.info(f"Saved {len(self.frames)} frames to {filepath}")
        except Exception as e:
            logger.error(f"Failed to save skill: {e}")

    def __del__(self):
        """Save the skill when the recorder is destroyed."""
        if self.recording and self.frames:
            self.save()
            if hasattr(self, "gui_process"):
                self.gui_process.join(timeout=1.0)
                if self.gui_process.is_alive():
                    self.gui_process.terminate()
