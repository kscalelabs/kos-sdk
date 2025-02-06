import os
import json
import time
import tkinter as tk
from tkinter import ttk
from typing import Dict, Union, List
from unit_types import Degree
from dataclasses import dataclass, asdict
from loguru import logger
from planners.keyboard_tk import KeyboardActor
import threading
import queue
from threading import Thread, Lock
import tkinter.messagebox
import platform
import multiprocessing as mp
from multiprocessing import Process, Queue

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

    def __init__(
        self,
        skill_name: str,
        command_queue: Queue,
        position_queue: Queue,
        current_positions_queue: Queue,
    ):
        super().__init__()
        self.skill_name = skill_name
        self.command_queue = command_queue
        self.position_queue = position_queue
        self.current_positions_queue = current_positions_queue
        self.daemon = True

    def check_commands(self):
        try:
            while True:
                cmd = self.position_queue.get_nowait()
                if cmd[0] == "update_count":
                    self.frame_count_label.config(text=f"Frames: {cmd[1]}")
                elif cmd[0] == "quit":
                    self.window.quit()
                    return
                elif cmd[0] == "get_positions":
                    self.current_positions_queue.put(self.robot.get_joint_angles())
                elif cmd[0] == "update_positions":
                    # Update GUI with real robot positions
                    self.robot.set_joint_angles(cmd[1])
        except queue.Empty:
            pass
        self.window.after(10, self.check_commands)

    def run(self):
        """Run the GUI in a separate process."""
        self.window = tk.Tk()
        self.window.title(f"Robot Control - Recording: {self.skill_name}")
        self.window.geometry("560x800")

        # Create notebook for tabs
        notebook = ttk.Notebook(self.window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Create keyboard control tab with scrollbar
        keyboard_frame = ttk.Frame(notebook)
        notebook.add(keyboard_frame, text="Joint Control")

        # Add canvas and scrollbar for scrolling
        canvas = tk.Canvas(keyboard_frame)
        scrollbar = ttk.Scrollbar(
            keyboard_frame, orient="vertical", command=canvas.yview
        )
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
        self.robot = KeyboardActor(
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
                "left_elbow",
                "right_shoulder_yaw",
                "right_shoulder_pitch",
                "right_elbow",
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
        self.frame_count_label = ttk.Label(record_frame, text="Frames: 0")
        self.frame_count_label.pack(pady=10)

        # Manual positioning toggle
        manual_frame = ttk.Frame(record_frame)
        manual_frame.pack(pady=5)
        manual_var = tk.BooleanVar(value=False)
        manual_check = ttk.Checkbutton(
            manual_frame,
            text="Manual Positioning (Disable Torque)",
            variable=manual_var,
            command=lambda: self.command_queue.put(("manual_mode", manual_var.get())),
        )
        manual_check.pack(pady=5)

        # Delay selection
        delay_frame = ttk.Frame(record_frame)
        delay_frame.pack(pady=10)

        ttk.Label(delay_frame, text="Delay before next frame (seconds):").pack(
            side=tk.LEFT
        )
        delay_var = tk.StringVar(value="1.0")
        delay_entry = ttk.Entry(delay_frame, textvariable=delay_var, width=10)
        delay_entry.pack(side=tk.LEFT, padx=5)

        # Quick delay buttons
        delays_frame = ttk.Frame(record_frame)
        delays_frame.pack(pady=5)
        for delay in [0.5, 1.0, 2.0]:
            ttk.Button(
                delays_frame,
                text=f"{delay}s",
                command=lambda d=delay: delay_var.set(str(d)),
            ).pack(side=tk.LEFT, padx=5)

        # Record button
        record_btn = ttk.Button(
            record_frame,
            text="Record Keyframe",
            command=lambda: self.command_queue.put(
                ("record", self.robot.get_joint_angles(), float(delay_var.get()))
            ),
        )
        record_btn.pack(pady=10)

        # Save button
        save_btn = ttk.Button(
            record_frame,
            text="Save and Exit",
            command=lambda: self.command_queue.put(("quit",)),
        )
        save_btn.pack(pady=10)

        # Set up window close handler
        self.window.protocol(
            "WM_DELETE_WINDOW", lambda: self.command_queue.put(("quit",))
        )

        # Start command checking
        self.window.after(10, self.check_commands)
        self.window.mainloop()


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
        self.manual_mode = False

        # Create queues for process communication
        self.command_queue = Queue()
        self.position_queue = Queue()
        self.current_positions_queue = Queue()

        # Start GUI process
        self.gui_process = GUIProcess(
            skill_name,
            self.command_queue,
            self.position_queue,
            self.current_positions_queue,
        )
        self.gui_process.start()

        logger.info(f"Started recording skill: {skill_name}")

    def update(
        self, feedback_state: Union[Dict[str, Union[int, Degree]], None]
    ) -> None:
        """Process commands from GUI and update state."""
        if feedback_state is None:
            self.is_sim = True
        else:
            self.last_positions = feedback_state
            # Update GUI with real robot positions
            self.position_queue.put(("update_positions", feedback_state))

        if self.recording:
            try:
                while True:
                    cmd = self.command_queue.get_nowait()
                    if cmd[0] == "record":
                        positions, delay = cmd[1], cmd[2]
                        # Use real robot positions if available
                        if not self.is_sim and self.last_positions:
                            positions = self.last_positions
                        frame = Frame(joint_positions=positions, delay=delay)
                        self.frames.append(frame)
                        self.position_queue.put(("update_count", len(self.frames)))
                        logger.info(
                            f"Recorded keyframe {len(self.frames)} with {delay}s delay"
                        )
                    elif cmd[0] == "manual_mode":
                        self.manual_mode = cmd[1]
                        if not self.is_sim:
                            self.position_queue.put(("manual_mode", self.manual_mode))
                            logger.info(
                                f"Manual mode {'enabled' if self.manual_mode else 'disabled'}"
                            )
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
                positions = self.current_positions_queue.get(timeout=0.1)
                return positions
            except queue.Empty:
                logger.warning("Timeout getting positions from GUI")
                return self.last_positions or {}
        return {}

    def save_and_exit(self) -> None:
        """Save the recorded skill and close the GUI."""
        if self.frames:  # Only save if we have recorded frames
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


class KeyboardActor:
    def __init__(self, joint_names, parent_frame):
        """Initialize keyboard control for joints.

        Args:
            joint_names: List of joint names to control
            parent_frame: Parent tkinter frame to add controls to
        """
        self.joint_names = joint_names
        self.joint_positions = {name: 0.0 for name in joint_names}
        self.joint_controls = {}

        # Create controls for each joint
        for name in joint_names:
            frame = ttk.Frame(parent_frame)
            frame.pack(fill=tk.X, padx=5, pady=2)

            # Joint label
            ttk.Label(frame, text=name).pack(side=tk.LEFT, padx=5)

            # Position display
            pos_var = tk.StringVar(value="0.0")
            pos_entry = ttk.Entry(frame, textvariable=pos_var, width=8)
            pos_entry.pack(side=tk.LEFT, padx=5)

            # Control buttons for simulation
            dec_btn = ttk.Button(
                frame,
                text="-10°",
                width=4,
                command=lambda n=name, v=pos_var: self._update_joint(n, v, -10),
            )
            dec_btn.pack(side=tk.LEFT, padx=2)

            fine_dec_btn = ttk.Button(
                frame,
                text="-5°",
                width=4,
                command=lambda n=name, v=pos_var: self._update_joint(n, v, -5),
            )
            fine_dec_btn.pack(side=tk.LEFT, padx=2)

            fine_inc_btn = ttk.Button(
                frame,
                text="+5°",
                width=4,
                command=lambda n=name, v=pos_var: self._update_joint(n, v, 5),
            )
            fine_inc_btn.pack(side=tk.LEFT, padx=2)

            inc_btn = ttk.Button(
                frame,
                text="+10°",
                width=4,
                command=lambda n=name, v=pos_var: self._update_joint(n, v, 10),
            )
            inc_btn.pack(side=tk.LEFT, padx=2)

            # Store controls
            self.joint_controls[name] = {
                "var": pos_var,
                "entry": pos_entry,
                "buttons": [dec_btn, fine_dec_btn, fine_inc_btn, inc_btn],
            }

    def _update_joint(self, name, var, delta):
        """Update joint position by delta degrees."""
        try:
            current = float(var.get())
            new_pos = current + delta
            # Clamp to reasonable range
            new_pos = max(-180, min(180, new_pos))
            var.set(f"{new_pos:.1f}")
            self.joint_positions[name] = new_pos
            # Make sure entry shows the new value
            self.joint_controls[name]["entry"].delete(0, tk.END)
            self.joint_controls[name]["entry"].insert(0, f"{new_pos:.1f}")
        except ValueError:
            # Reset to 0 if invalid value
            var.set("0.0")
            self.joint_positions[name] = 0.0

    def get_joint_angles(self) -> Dict[str, float]:
        """Get current joint positions."""
        # Always return the internal position state
        return self.joint_positions.copy()

    def set_joint_angles(self, positions: Dict[str, float]) -> None:
        """Set joint positions from external source."""
        for name, pos in positions.items():
            if name in self.joint_controls:
                self.joint_positions[name] = float(pos)
                self.joint_controls[name]["var"].set(f"{float(pos):.1f}")
                # Update entry directly
                self.joint_controls[name]["entry"].delete(0, tk.END)
                self.joint_controls[name]["entry"].insert(0, f"{float(pos):.1f}")
