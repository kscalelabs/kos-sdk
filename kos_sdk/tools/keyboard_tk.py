"""Defines an actor robot model that allows for keyboard control."""

import tkinter as tk
from tkinter import ttk
from typing import Dict, Union

from ks_digital_twin.actor.base import ActorRobot
from unit_types import Degree


class KeyboardActor(ActorRobot):
    """Actor robot model that allows for keyboard control."""

    def __init__(self, joint_names: list[str], parent_frame: ttk.Frame) -> None:
        """Initialize the keyboard control interface.

        Args:
            joint_names: List of joint names to control
            parent_frame: Parent tkinter frame to add controls to
        """
        self.joint_names = joint_names
        self.current_joint_angles = {name: 0.0 for name in joint_names}

        # Create main frame
        main_frame = ttk.Frame(parent_frame, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title label
        title_label = ttk.Label(main_frame, text="Joint Control", font=("Helvetica", 16, "bold"))
        title_label.pack(pady=10)

        # Create joint control frames
        self.joint_controls: Dict[str, Dict] = {}

        for joint_name in joint_names:
            frame = ttk.LabelFrame(main_frame, text=joint_name, padding="5")
            frame.pack(fill=tk.X, pady=5)

            # Value label
            value_var = tk.StringVar(value="0.0")
            value_label = ttk.Label(frame, textvariable=value_var)
            value_label.pack(side=tk.LEFT, padx=5)

            # Control buttons
            btn_frame = ttk.Frame(frame)
            btn_frame.pack(side=tk.RIGHT)

            decrease_btn = ttk.Button(
                btn_frame, text="-5°", command=lambda n=joint_name: self._update_angle(n, -5.0)
            )
            decrease_btn.pack(side=tk.LEFT, padx=2)

            fine_decrease_btn = ttk.Button(
                btn_frame, text="-1°", command=lambda n=joint_name: self._update_angle(n, -1.0)
            )
            fine_decrease_btn.pack(side=tk.LEFT, padx=2)

            fine_increase_btn = ttk.Button(
                btn_frame, text="+1°", command=lambda n=joint_name: self._update_angle(n, 1.0)
            )
            fine_increase_btn.pack(side=tk.LEFT, padx=2)

            increase_btn = ttk.Button(
                btn_frame, text="+5°", command=lambda n=joint_name: self._update_angle(n, 5.0)
            )
            increase_btn.pack(side=tk.LEFT, padx=2)

            # Store controls
            self.joint_controls[joint_name] = {
                "value_var": value_var,
                "frame": frame,
                "buttons": [decrease_btn, fine_decrease_btn, fine_increase_btn, increase_btn],
            }

        # Add keyboard bindings to parent window
        parent_frame.bind("<Left>", lambda e: self._update_angle(self.joint_names[0], -1.0))
        parent_frame.bind("<Right>", lambda e: self._update_angle(self.joint_names[0], 1.0))
        parent_frame.bind("<Up>", lambda e: self._update_angle(self.joint_names[0], 5.0))
        parent_frame.bind("<Down>", lambda e: self._update_angle(self.joint_names[0], -5.0))
        parent_frame.bind("<Tab>", self._cycle_focus)

    def _update_angle(self, joint_name: str, delta: float) -> None:
        """Update the angle of the specified joint.

        Args:
            joint_name: Name of the joint to update
            delta: Amount to change the angle by (in degrees)
        """
        self.current_joint_angles[joint_name] += delta
        self.joint_controls[joint_name]["value_var"].set(
            f"{self.current_joint_angles[joint_name]:.1f}°"
        )

    def _cycle_focus(self, event=None) -> None:
        """Cycle keyboard focus through the joints."""
        focused = self.parent_frame.focus_get()
        for i, joint_name in enumerate(self.joint_names):
            if focused in self.joint_controls[joint_name]["buttons"]:
                next_joint = self.joint_names[(i + 1) % len(self.joint_names)]
                self.joint_controls[next_joint]["buttons"][0].focus_set()
                return
        # If no joint focused, focus first joint
        self.joint_controls[self.joint_names[0]]["buttons"][0].focus_set()

    def get_joint_angles(self) -> Dict[str, Union[int, Degree]]:
        """Return the current joint angles.

        Returns:
            Dictionary mapping joint names to their current angles
        """
        return self.current_joint_angles.copy()
