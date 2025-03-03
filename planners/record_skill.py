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
import math
import signal
import sys

# Import joint mapping
from robot import JOINT_TO_ID

IS_MACOS = platform.system() == "Darwin"

# Global flag for stopping continuous recording
STOP_RECORDING = False


# Signal handler for keyboard interrupt
def signal_handler(sig, frame):
    global STOP_RECORDING
    if STOP_RECORDING:  # If already stopping, force exit
        sys.exit(0)
    logger.info("Stopping recording (press Ctrl+C again to force exit)...")
    STOP_RECORDING = True


# Register the signal handler
signal.signal(signal.SIGINT, signal_handler)


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
                ("record", robot.get_joint_angles(), float(delay_var.get()))
            ),
        )
        record_btn.pack(pady=10)

        # Manual positioning checkbox
        manual_var = tk.BooleanVar(value=False)
        manual_check = ttk.Checkbutton(
            record_frame,
            text="Manual Positioning (Disable Torque)",
            variable=manual_var,
            command=lambda: self.command_queue.put(("manual_mode", manual_var.get())),
        )
        manual_check.pack(pady=10)

        # Save button
        save_btn = ttk.Button(
            record_frame,
            text="Save and Exit",
            command=lambda: self.command_queue.put(("quit",)),
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
        self.manual_mode = False
        self.continuous_mode = False
        self.last_recorded_positions = None
        self.min_position_change = (
            0.02  # Reduced from 0.05 to capture more subtle movements
        )
        self.last_record_time = time.time()

        # Check if we should use GUI or continuous mode
        if skill_name.startswith("continuous_"):
            self.continuous_mode = True
            self.skill_name = skill_name.replace("continuous_", "")
            # Use a higher frequency for recording (50Hz) to capture more natural movements
            self.continuous_frequency = 50.0  # 50Hz for recording
            self.record_interval = 1.0 / self.continuous_frequency
            logger.info(
                f"Starting continuous recording for skill: {self.skill_name} at {self.continuous_frequency}Hz"
            )
        else:
            # For GUI mode, use the specified frequency
            self.record_interval = 1.0 / frequency
            # Create queues for process communication
            self.command_queue = Queue()
            self.position_queue = Queue()

            # Start GUI process
            self.gui_process = GUIProcess(
                skill_name, self.command_queue, self.position_queue
            )
            self.gui_process.start()

            logger.info(f"Started GUI recording for skill: {skill_name}")
            self.current_positions_queue = self.gui_process.current_positions_queue

    def update(
        self, feedback_state: Union[Dict[str, Union[int, Degree]], None]
    ) -> None:
        """Process commands from GUI or record continuously."""
        global STOP_RECORDING

        # Check if we should stop recording
        if STOP_RECORDING and self.continuous_mode:
            logger.info("Stopping continuous recording and saving skill...")
            self.save_and_exit()
            # Reset the flag
            STOP_RECORDING = False
            return

        if feedback_state is None:
            self.is_sim = True
            # For continuous mode in simulation, create some dummy positions if needed
            if self.continuous_mode and not self.last_positions:
                # Create default positions for all joints
                self.last_positions = {joint: 0.0 for joint in JOINT_TO_ID.keys()}

            # For continuous mode in simulation, simulate joint movements
            if self.continuous_mode:
                self._simulate_joint_movements()
            return

        self.last_positions = feedback_state

        if self.continuous_mode:
            # Continuous recording mode
            current_time = time.time()
            time_since_last_record = current_time - self.last_record_time

            # Check if it's time to record based on our frequency
            if time_since_last_record >= self.record_interval:
                # Check if positions have changed enough to record
                if self._should_record_new_frame(feedback_state):
                    self.last_recorded_positions = feedback_state.copy()

                    # Calculate the actual delay based on time since last frame
                    # This ensures playback timing matches recording timing
                    actual_delay = max(time_since_last_record, self.record_interval)

                    frame = Frame(joint_positions=feedback_state, delay=actual_delay)
                    self.frames.append(frame)

                    # Log recording frequency periodically (every 10 frames)
                    if len(self.frames) % 10 == 0:
                        actual_frequency = 1.0 / time_since_last_record
                        logger.info(
                            f"Recording at {actual_frequency:.2f}Hz (target: {self.continuous_frequency:.2f}Hz)"
                        )
                    else:
                        logger.info(f"Continuously recorded frame {len(self.frames)}")

                self.last_record_time = current_time
        elif self.recording:
            # GUI recording mode
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
                        logger.info(
                            f"Recorded keyframe {len(self.frames)} with {delay}s delay"
                        )
                    elif cmd[0] == "manual_mode":
                        self.manual_mode = cmd[1]
                        logger.info(
                            f"Manual mode {'enabled' if self.manual_mode else 'disabled'}"
                        )
                    elif cmd[0] == "quit":
                        self.save_and_exit()
            except queue.Empty:
                pass

    def _should_record_new_frame(
        self, current_positions: Dict[str, Union[int, Degree]]
    ) -> bool:
        """Determine if we should record a new frame based on position changes."""
        if self.last_recorded_positions is None:
            return True

        # Important joints that we want to be more sensitive to
        important_joints = [
            "left_shoulder_pitch",
            "right_shoulder_pitch",
            "left_elbow",
            "right_elbow",
            "left_elbow_yaw",
            "right_elbow_yaw",
            "left_hip_pitch",
            "right_hip_pitch",
            "left_knee",
            "right_knee",
        ]

        # Time-based recording - ensure we record at least every 0.5 seconds
        # even if there's little movement
        current_time = time.time()
        if current_time - self.last_record_time >= 0.5:
            return True

        # Check for significant changes in any joint position
        for joint, position in current_positions.items():
            if joint not in self.last_recorded_positions:
                continue

            # Get the threshold for this joint
            threshold = (
                self.min_position_change * 0.5
                if joint in important_joints
                else self.min_position_change
            )

            # Check if position has changed enough
            if abs(position - self.last_recorded_positions[joint]) > threshold:
                return True

        return False

    def get_command_positions(self) -> Dict[str, Union[int, Degree]]:
        """Return the current joint positions."""
        if not self.is_sim:
            return self.last_positions
        if self.continuous_mode:
            return self.last_positions or {}
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
        if not self.continuous_mode:
            self.position_queue.put(("quit",))
            self.gui_process.join(timeout=1.0)
            if self.gui_process.is_alive():
                self.gui_process.terminate()

    def save(self) -> None:
        """Save the recorded skill to a file."""
        if not self.frames:
            logger.warning("No frames to save!")
            return

        # Post-process frames for continuous recording
        if self.continuous_mode and len(self.frames) > 10:
            logger.info(
                f"Post-processing {len(self.frames)} frames for optimal playback..."
            )

            # Calculate average delay between frames
            total_delay = sum(frame.delay for frame in self.frames)
            avg_delay = total_delay / len(self.frames)

            # Smooth out delays to make playback more consistent
            for frame in self.frames:
                # Adjust delays to be closer to the average (smoothing)
                if frame.delay > avg_delay * 2:
                    frame.delay = avg_delay * 1.5
                elif frame.delay < avg_delay * 0.5:
                    frame.delay = avg_delay * 0.75

            # Downsample if we have too many frames (more than 200)
            if len(self.frames) > 200:
                logger.info(
                    f"Downsampling from {len(self.frames)} to approximately 200 frames..."
                )

                # Calculate downsample factor
                downsample_factor = len(self.frames) / 200

                # Keep only every nth frame
                downsampled_frames = []
                for i in range(0, len(self.frames), int(downsample_factor)):
                    if i < len(self.frames):
                        # Adjust delay to account for skipped frames
                        if i + int(downsample_factor) < len(self.frames):
                            total_skipped_delay = sum(
                                frame.delay
                                for frame in self.frames[
                                    i + 1 : i + int(downsample_factor)
                                ]
                            )
                            self.frames[i].delay += total_skipped_delay
                        downsampled_frames.append(self.frames[i])

                self.frames = downsampled_frames
                logger.info(f"Downsampled to {len(self.frames)} frames")

        # Create skill data
        skill_data = SkillData(name=self.skill_name, frames=self.frames)

        # Save to file
        self.save_to_file(self.skill_name)

        # Log information about the saved skill
        total_duration = sum(frame.delay for frame in self.frames)
        logger.info(f"Saved skill '{self.skill_name}' with {len(self.frames)} frames")
        logger.info(f"Total playback duration: {total_duration:.2f} seconds")
        logger.info(
            f"Average frame delay: {total_duration/len(self.frames):.3f} seconds"
        )

    def save_to_file(self, filename: str) -> None:
        """Save the recorded skill to a specific JSON file."""
        if not self.frames:
            logger.warning("No frames recorded, skipping save")
            return

        base_path = os.path.join(os.path.dirname(__file__), "recorded_skills")
        os.makedirs(base_path, exist_ok=True)

        # If filename doesn't end with .json, add it
        if not filename.endswith(".json"):
            filename = f"{filename}.json"

        skill_data = SkillData(name=filename[:-5], frames=self.frames)
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
            if not self.continuous_mode and hasattr(self, "gui_process"):
                self.gui_process.join(timeout=1.0)
                if self.gui_process.is_alive():
                    self.gui_process.terminate()

    def should_toggle_torque(self) -> bool:
        """Check if torque should be toggled based on manual mode or continuous mode."""
        return self.manual_mode or self.continuous_mode

    def _simulate_joint_movements(self):
        """Simulate joint movements for testing in simulation mode."""
        if not hasattr(self, "sim_time"):
            self.sim_time = 0.0

        # Update simulation time
        self.sim_time += self.record_interval

        # Create simulated joint positions with sinusoidal movements
        simulated_positions = {}
        for joint in JOINT_TO_ID.keys():
            if "shoulder" in joint or "elbow" in joint:
                # Arms move in a sinusoidal pattern
                simulated_positions[joint] = 45.0 * math.sin(self.sim_time)
            elif "hip" in joint or "knee" in joint or "ankle" in joint:
                # Legs move in a different pattern
                simulated_positions[joint] = 20.0 * math.sin(self.sim_time * 0.5)
            else:
                # Other joints move slightly
                simulated_positions[joint] = 10.0 * math.sin(self.sim_time * 0.2)

        # Record the simulated frame
        if self._should_record_new_frame(simulated_positions):
            self.last_recorded_positions = simulated_positions.copy()
            frame = Frame(
                joint_positions=simulated_positions, delay=self.record_interval
            )
            self.frames.append(frame)
            logger.info(f"Recorded simulated frame {len(self.frames)}")

        # Update last positions
        self.last_positions = simulated_positions

    def handle_command(self, command: str, args: List[str]) -> None:
        """Handle a command from the user."""
        if command == "manual_mode":
            self.manual_mode = not self.manual_mode
            self.torque_state_changed = True
            logger.info(f"Manual mode {'enabled' if self.manual_mode else 'disabled'}")
        elif command == "save":
            if len(args) > 0:
                filename = args[0]
                self.save_to_file(filename)
            else:
                self.save()
            logger.info("Recording saved")
        else:
            logger.warning(f"Unknown command: {command}")
