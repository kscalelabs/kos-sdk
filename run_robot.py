#!/usr/bin/env python3
"""
Convenience script for running different robots with standard planners
"""

import argparse
import subprocess
import sys
from robot_config import RobotType

def main():
    parser = argparse.ArgumentParser(description="Control different robots with ease")
    parser.add_argument(
        "robot", 
        choices=[r.value for r in RobotType], 
        help="Robot to control (alum1, white, default)"
    )
    parser.add_argument(
        "--planner", 
        default="zmp", 
        help="Planner to use (default: zmp)"
    )
    parser.add_argument(
        "--sim", 
        action="store_true", 
        help="Also run in simulation"
    )
    
    # Add any additional arguments you need
    args, unknown_args = parser.parse_known_args()
    
    # Build command to run the robot
    cmd = [sys.executable, "run.py", "--real", f"--robot={args.robot}", f"--planner={args.planner}"]
    
    # Add simulation if requested
    if args.sim:
        cmd.append("--sim")
    
    # Add any other arguments passed
    cmd.extend(unknown_args)
    
    print(f"Running command: {' '.join(cmd)}")
    subprocess.run(cmd)

if __name__ == "__main__":
    main()