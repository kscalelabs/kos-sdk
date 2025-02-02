""" Record actions from the real robot and save it to a file. """
from skillit.play import FramePlayer
from skillit.record import SkillRecorder
from robot import RobotInterface

def record_skill(ip: str, skill_name: str) -> None:
    """Record a new skill.

    Args:
        ip: IP address of the robot
        skill_name: Name of the skill to record
    """
    # Initialize the recorder with robot IP and joint mapping
    recorder = SkillRecorder(
        ip=ip,
        joint_name_to_id=joint_name_to_id,
        frequency=20,  # Record at 20Hz
        countdown=3,  # 3 second countdown before recording
        skill_name=skill_name,  # Optional name for the skill
    )

    print("Starting recording session...")
    print("1. Robot joints will be set to passive mode")
    print("2. Move the robot to desired positions")
    print("3. Press Ctrl+C to start recording")
    print("4. Press Ctrl+C again to stop recording")

    # Start recording - this will block until Ctrl+C is pressed twice
    recorder.record()

def play_skill(ip: str, filename: str) -> None:
    """Play back a recorded skill.

    Args:
        ip: IP address of the robot
        filename: Path to the recorded skill JSON file
    """
    # Initialize the player with robot IP and joint mapping
    player = FramePlayer(ip=ip, joint_name_to_id=joint_name_to_id)

    # Configure actuators
    for _, joint_id in joint_name_to_id.items():
        player.ac.configure_actuator(actuator_id=joint_id, kp=100, kd=1, torque_enabled=True)

    # Play back the recorded movements
    print(f"Playing back skill from {filename}")
    player.play(filename)
