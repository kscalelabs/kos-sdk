"""Script to demonstrate walking sequence with Wesley's tuned parameters."""

import asyncio
import math
import time
import os
from PIL import Image
from pykos import KOS
from walkingsequence import BipedController, joint_to_actuator_id, angles_to_pykos_commands
from openai import OpenAI
from dotenv import load_dotenv
import sounddevice as sd
import soundfile as sf

# LED Matrix Configuration
GRID_WIDTH = 32
GRID_HEIGHT = 16

# Different face patterns
PATTERNS = {
    "happy": """
00000000000000000000000000000000
00000000000000000000000000000000
00000000000000000000000000000000
00000111100000000000000111100000
00001111110000000000001111110000
00011111111000000000011111111000
00011111111111111111111111111000
00011111111111111111111111111000
00011111111000000000011111111000
00001111110000000000001111110000
00000111100000000000000111100000
00000000000000000000000000000000
00000000000000000000000000000000
00000000000000000000000000000000
00000000000000000000000000000000
00000000000000000000000000000000
""".strip(),
    "sleepy": """
00000000000000000000000000000000
00000000000000000000000000000000
00000000000000000000000000000000
00000111100000000000001111000000
00001111110000000000011111100000
00011111111000000000111111110000
00000000000000000000000000000000
00000000000000000000000000000000
00000000000000011110000000000000
00000000000001111111100000000000
00000000000011111111110000000000
00000000000000011110000000000000
00000000000000000000000000000000
00000000000000000000000000000000
00000000000000000000000000000000
00000000000000000000000000000000
""".strip(),
    "focused": """
00000000000000000000000000000000
00000000000000000000000000000000
00000000000000000000000000000000
00000111100000000000000111100000
00001111110000000000001111110000
00011111111000000000011111111000
00011111111000000000011111111000
00011111111000000000011111111000
00011111111000000000011111111000
00001111110000000000001111110000
00000111100000000000000111100000
00000000000000000000000000000000
00000000000000000000000000000000
00000000000000000000000000000000
00000000000000000000000000000000
00000000000000000000000000000000
""".strip(),
    "surprised": """
00000000000000000000000000000000
00000000000000000000000000000000
00000111100000000000000111100000
00001111110000000000001111110000
00011111111000000000011111111000
00011111111111111111111111111000
00011111111111111111111111111000
00011111111111111111111111111000
00011111111111111111111111111000
00011111111000000000011111111000
00001111110000000000001111110000
00000111100000000000000111100000
00000000000000000000000000000000
00000000000000000000000000000000
00000000000000000000000000000000
00000000000000000000000000000000
""".strip(),
    "happy_planet": """
00000000000000000000000000000000
00000000000000000000000000000000
00000000000000011100000000000000
00000111100000111110000111100000
00001111110001111111001111110000
00011111111011111111111111111000
00011111111111111111111111111000
00011111111111111111111111111000
00011111111011111111011111111000
00001111110001111111001111110000
00000111100000111110000111100000
00000000000000011100000000000000
00000000000000000000000000000000
00000000000000000000000000000000
00000000000000000000000000000000
00000000000000000000000000000000
""".strip(),
    "blink": """
00000000000000000000000000000000
00000000000000000000000000000000
00000000000000000000000000000000
00000000000000000000000000000000
00000111100000000000000111100000
00001111110000000000001111110000
00001111110000000000001111110000
00001111110000000000001111110000
00000111100000000000000111100000
00000000000000000000000000000000
00000000000000000000000000000000
00000000000000000000000000000000
00000000000000000000000000000000
00000000000000000000000000000000
00000000000000000000000000000000
00000000000000000000000000000000
""".strip(),
}

# Load environment variables from .env file
load_dotenv()

# OpenAI Configuration
client = OpenAI()  # It will automatically read from environment variable

if not os.getenv("OPENAI_API_KEY"):
    raise ValueError("OPENAI_API_KEY environment variable is not set. Please create a .env file with your API key.")

# Audio Configuration
PLAY_DEVICE = 1  # Speaker device (cv182xa_dac)
RATE = 44100  # Standard sample rate
CHANNELS = 1  # Mono audio


async def set_led_matrix(kos: KOS, pattern_name: str):
    """Set LED matrix pattern."""
    if pattern_name not in PATTERNS:
        return

    # Create image from pattern
    MATRIX = [list(row) for row in PATTERNS[pattern_name].split("\n")]
    image = Image.new("1", (GRID_WIDTH, GRID_HEIGHT), "black")
    for y in range(GRID_HEIGHT):
        for x in range(GRID_WIDTH):
            if MATRIX[y][x] == "1":
                image.putpixel((x, y), 1)

    # Send to LED matrix
    bitmap_data = image.tobytes()
    await kos.led_matrix.write_buffer(bitmap_data)


async def set_led_expression(kos: KOS, expression: str):
    """Set LED expression on the robot's face.

    Available expressions:
    - "happy": Wide awake and happy with planet
    - "focused": Concentrated expression
    - "sleepy": Tired/closing eyes
    - "surprised": Wide open eyes
    - "blink": Quick blink animation
    """
    # Map expressions to LED matrix patterns
    matrix_patterns = {
        "happy": "happy_planet",  # Use pattern with planet
        "focused": "focused",
        "sleepy": "sleepy",
        "surprised": "surprised",
        "blink": "blink",
    }

    if expression in matrix_patterns:
        await set_led_matrix(kos, matrix_patterns[expression])
        if expression == "blink":
            await asyncio.sleep(0.1)  # Quick blink
            await set_led_matrix(kos, matrix_patterns["focused"])  # Return to focused


async def play_audio_file(filename: str):
    """Play an audio file through the robot's speaker."""
    try:
        # Read the audio file
        audio_data, samplerate = sf.read(filename)

        # Convert to mono if stereo
        if len(audio_data.shape) > 1:
            audio_data = audio_data.mean(axis=1)

        # Play the audio
        sd.play(audio_data, samplerate, device=PLAY_DEVICE)
        sd.wait()  # Wait until audio is finished playing
    except Exception as e:
        print(f"Error playing audio: {e}")


async def say_text(kos: KOS, text: str, expression: str = "happy"):
    """Make the robot speak text and show an expression."""
    print(f"Robot saying: {text}")

    # Set expression while speaking
    await set_led_expression(kos, expression)

    # Convert text to speech using OpenAI's API
    response = client.audio.speech.create(
        model="tts-1",
        voice="alloy",
        input=text,
        response_format="wav",
        speed=1.1,
    )

    # Save the audio temporarily
    temp_file = "temp_speech.wav"
    with open(temp_file, "wb") as f:
        f.write(response.content)

    # Play the audio
    await play_audio_file(temp_file)

    # Clean up
    os.remove(temp_file)

    # Return to previous expression
    await set_led_expression(kos, "focused")


async def run_walk_sequence(ip: str, arm_mode: str = "disabled", sim_only: bool = False):
    """Run a walking sequence on the robot.

    Args:
        ip: IP address of the robot
        arm_mode: One of ["disabled", "coordinated", "fixed"]
            - disabled: Arms are not controlled
            - coordinated: Arms swing naturally with leg movement
            - fixed: Arms held in a fixed position
        sim_only: Whether to run in simulation only mode
    """
    dt = 0.001
    async with KOS(ip=ip) as kos:
        # Reset simulation if in sim mode
        if sim_only:
            print("Resetting simulation...")
            await kos.sim.reset()

        # Start with sleepy expression
        await set_led_expression(kos, "sleepy")
        await say_text(kos, "I'm feeling sleepy...", "sleepy")
        await asyncio.sleep(1)

        # Separate actuator lists for better control
        leg_actuators = [
            31,
            32,
            33,
            34,
            35,  # Left leg
            41,
            42,
            43,
            44,
            45,  # Right leg
        ]
        arm_actuators = [
            11,
            12,
            13,
            14,  # Left arm
            21,
            22,
            23,
            24,  # Right arm
        ]

        # Configure leg actuators with appropriate gains for sim/real
        for actuator_id in leg_actuators:
            print(f"Enabling torque for leg actuator {actuator_id}")
            if sim_only:
                # Higher gains for simulation
                await kos.actuator.configure_actuator(
                    actuator_id=actuator_id,
                    kp=150,
                    kd=15,
                    max_torque=100,
                    torque_enabled=True,
                )
            else:
                # Lower gains for real robot
                await kos.actuator.configure_actuator(
                    actuator_id=actuator_id,
                    kp=32,
                    kd=32,
                    max_torque=100,
                    torque_enabled=True,
                )

        # Configure arm actuators if not disabled
        if arm_mode != "disabled":
            for actuator_id in arm_actuators:
                print(f"Enabling torque for arm actuator {actuator_id}")
                if sim_only:
                    # Higher gains for simulation
                    await kos.actuator.configure_actuator(
                        actuator_id=actuator_id,
                        kp=50,
                        kd=5,
                        max_torque=50,
                        torque_enabled=True,
                    )
                else:
                    # Lower gains for real robot
                    await kos.actuator.configure_actuator(
                        actuator_id=actuator_id,
                        kp=20,
                        kd=2,
                        max_torque=50,
                        torque_enabled=True,
                    )

        try:
            # Wake up animation with speech
            print("Waking up...")
            await set_led_expression(kos, "surprised")
            await say_text(kos, "Oh! Time to wake up!", "surprised")
            await asyncio.sleep(0.5)
            await set_led_expression(kos, "blink")
            await asyncio.sleep(0.5)
            await set_led_expression(kos, "focused")
            await say_text(kos, "Let's get walking!", "happy")

            # Get pre-walk stance first
            walker = BipedController(lateral_movement_enabled=False)
            walker.hip_pitch_offset = math.radians(27)  # Initial lean
            walker.control_foot_position(
                -walker.hip_forward_offset,
                0.0,
                walker.nominal_leg_height,
                0,
            )
            walker.control_foot_position(
                -walker.hip_forward_offset,
                0.0,
                walker.nominal_leg_height,
                1,
            )
            pre_walk_angles = walker.get_joint_angles()

            # Convert to commands based on arm mode
            pre_walk_commands = []
            for joint_name, angle_radians in pre_walk_angles.items():
                if joint_name in joint_to_actuator_id:
                    actuator_id = joint_to_actuator_id[joint_name]
                    # Include arm commands only if not disabled
                    if actuator_id in leg_actuators or (arm_mode != "disabled" and actuator_id in arm_actuators):
                        angle_degrees = math.degrees(angle_radians)
                        if actuator_id in [32]:  # Special case for left hip roll
                            angle_degrees = -angle_degrees
                        pre_walk_commands.append(
                            {
                                "actuator_id": actuator_id,
                                "position": angle_degrees,
                            }
                        )

            # Hold the pre-walk stance for 3 seconds
            print("Holding pre-walk stance...")
            hold_start = time.time()
            while time.time() - hold_start < 3.0:
                await kos.actuator.command_actuators(pre_walk_commands)
                await asyncio.sleep(dt)

            # Walking sequence
            print("Starting walk...")
            # Happy expression for walking
            await set_led_expression(kos, "happy")

            walker.hip_pitch_offset = math.radians(27)  # Walking pitch
            walker.gait_phase = 20  # Skip the initial ramping phase
            start_time = time.time()
            last_blink = start_time

            while time.time() - start_time < 10.0:
                current_time = time.time()

                # Occasional blink during walking
                if current_time - last_blink > 3.0:
                    await set_led_expression(kos, "blink")
                    last_blink = current_time

                walker.step_length = 11.0
                walker.step_cycle_length = 20
                walker.update_gait()
                angles_dict = walker.get_joint_angles()

                commands = []
                for joint_name, angle_radians in angles_dict.items():
                    if joint_name in joint_to_actuator_id:
                        actuator_id = joint_to_actuator_id[joint_name]
                        # Process leg actuators
                        if actuator_id in leg_actuators:
                            angle_degrees = math.degrees(angle_radians)
                            if actuator_id in [32]:
                                angle_degrees = -angle_degrees
                            commands.append(
                                {
                                    "actuator_id": actuator_id,
                                    "position": angle_degrees,
                                }
                            )
                        # Process arm actuators based on mode
                        elif actuator_id in arm_actuators and arm_mode != "disabled":
                            if arm_mode == "coordinated":
                                # Coordinate arm swing with opposite leg
                                # When left leg forward, right arm forward and vice versa
                                phase = walker.step_cycle_counter / walker.step_cycle_length
                                arm_swing = 20 * math.sin(2 * math.pi * phase)  # 20 degree swing

                                if "left" in joint_name:
                                    # Left arm moves opposite to right leg
                                    if walker.stance_foot_index == 1:  # Right leg is stance
                                        angle_degrees = arm_swing
                                    else:
                                        angle_degrees = -arm_swing
                                else:
                                    # Right arm moves opposite to left leg
                                    if walker.stance_foot_index == 0:  # Left leg is stance
                                        angle_degrees = arm_swing
                                    else:
                                        angle_degrees = -arm_swing

                                if "_shoulder_pitch" in joint_name:
                                    commands.append(
                                        {
                                            "actuator_id": actuator_id,
                                            "position": angle_degrees,
                                        }
                                    )
                            else:  # fixed mode
                                commands.append(
                                    {
                                        "actuator_id": actuator_id,
                                        "position": 0,  # Keep arms in neutral position
                                    }
                                )

                if commands:
                    await kos.actuator.command_actuators(commands)
                await asyncio.sleep(dt)

            # End with stable stance
            print("Ending sequence...")
            # Tired expression after walking
            await set_led_expression(kos, "sleepy")

            walker.hip_pitch_offset = math.radians(27)  # Final stance
            walker.control_foot_position(
                -walker.hip_forward_offset,
                0.0,
                walker.nominal_leg_height,
                0,
            )
            walker.control_foot_position(
                -walker.hip_forward_offset,
                0.0,
                walker.nominal_leg_height,
                1,
            )
            final_angles = walker.get_joint_angles()

            final_commands = []
            for joint_name, angle_radians in final_angles.items():
                if joint_name in joint_to_actuator_id:
                    actuator_id = joint_to_actuator_id[joint_name]
                    if actuator_id in leg_actuators or (arm_mode != "disabled" and actuator_id in arm_actuators):
                        angle_degrees = math.degrees(angle_radians)
                        if actuator_id in [32]:
                            angle_degrees = -angle_degrees
                        final_commands.append(
                            {
                                "actuator_id": actuator_id,
                                "position": angle_degrees,
                            }
                        )

            # Hold final position
            start_time = time.time()
            transition_duration = 1.0
            while time.time() - start_time < transition_duration:
                await kos.actuator.command_actuators(final_commands)
                await asyncio.sleep(dt)

            print("Sequence complete!")

        except KeyboardInterrupt:
            print("\nStopping sequence...")
            # Set neutral expression when stopping
            await set_led_expression(kos, "focused")
            return


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Run a walking sequence with Wesley's parameters")
    parser.add_argument(
        "--ip",
        type=str,
        default="localhost",  # Changed default to localhost for simulation
        help="IP for the KOS device",
    )
    parser.add_argument(
        "--no-lateral",
        action="store_true",
        help="Disable lateral movements",
        default=True,
    )
    parser.add_argument(
        "--arm-mode",
        type=str,
        choices=["disabled", "coordinated", "fixed"],
        default="disabled",
        help="How to control the arms during walking",
    )
    parser.add_argument(
        "--sim-only",
        action="store_true",
        help="Run in simulation only mode",
    )
    args = parser.parse_args()

    await run_walk_sequence(ip=args.ip, arm_mode=args.arm_mode, sim_only=args.sim_only)


if __name__ == "__main__":
    asyncio.run(main())
