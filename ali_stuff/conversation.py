import asyncio
import os
from dotenv import load_dotenv
from loguru import logger
import numpy as np
from datetime import datetime
import re

# Import the ElevenLabs API (assumes ELEVENLABS_API_KEY is in env)
from elevenlabs.client import ElevenLabs
from elevenlabs import play

# Import robot interface (your existing module)
from demos.robot import RobotInterface

# Load environment variables (ELEVENLABS_API_KEY, OPENAI_API_KEY, etc.)
load_dotenv()

# ------------------------
# Robot Speaker Definition
# ------------------------
class RobotSpeaker:
    def __init__(self, ip="10.33.11.231", voice_id="JBFqnCBsd6RMkjVDRZzb"):
        self.robot = RobotInterface(ip=ip)
        self.eleven = ElevenLabs()
        self.voice_id = voice_id

    async def connect(self):
        """Connect to the robot."""
        await self.robot.__aenter__()
        logger.info("Connected to robot")

    async def close(self):
        """Clean shutdown: turn off display and disconnect."""
        try:
            # Turn off display by writing a blank buffer
            info = await self.robot.kos.led_matrix.get_matrix_info()
            buffer_size = info.width * info.height // 8
            off_buffer = bytes([0x00] * buffer_size)
            await self.robot.kos.led_matrix.write_buffer(off_buffer)
            logger.info("Display turned off")
        finally:
            await self.robot.__aexit__(None, None, None)

    async def speak_and_display(self, text: str, voice_id="JBFqnCBsd6RMkjVDRZzb"):
        """Convert text to speech (via ElevenLabs) and display on the robot's LED matrix."""
        try:
            logger.info(f"Converting text to speech and displaying: {text}")

            # Get display dimensions and create an image
            info = await self.robot.kos.led_matrix.get_matrix_info()
            from PIL import Image, ImageDraw, ImageFont
            image = Image.new('L', (info.width, info.height), 0)
            draw = ImageDraw.Draw(image)

            # Fit text to the display by decreasing font size if needed.
            font_size = info.height
            text_width = info.width + 1
            while text_width > info.width and font_size > 1:
                try:
                    font = ImageFont.load_default()  # Using default font for simplicity
                    bbox = draw.textbbox((0, 0), text, font=font)
                    text_width = bbox[2] - bbox[0]
                    text_height = bbox[3] - bbox[1]
                    font_size -= 1
                except Exception:
                    font = ImageFont.load_default()
                    break

            # Center the text on the display
            x = (info.width - text_width) // 2
            y = (info.height - text_height) // 2
            draw.text((x, y), text, font=font, fill=255)

            # Convert image to a binary (1-bit) format and pack the bits
            binary = image.point(lambda x: 0 if x < 128 else 1, '1')
            arr = np.array(binary, dtype=np.uint8)
            packed = np.packbits(arr)
            buffer = bytes(packed)
            await self.robot.kos.led_matrix.write_buffer(buffer)

            # Generate and play audio (text-to-speech)
            audio = self.eleven.text_to_speech.convert(
                text=text,
                voice_id=voice_id,
                model_id="eleven_multilingual_v2",
                output_format="mp3_44100_128",
            )
            play(audio)
            logger.info("Finished speaking")

        except Exception as e:
            logger.error(f"Error speaking: {e}", exc_info=True)

# ------------------------
# Helper Functions
# ------------------------

def record_audio(duration: int = 5, filename: str = "temp_audio.wav",
                 samplerate: int = 44100, channels: int = 1) -> str:
    """
    Record audio from the default microphone for the given duration (in seconds)
    and save it to a WAV file.
    """
    import sounddevice as sd
    import soundfile as sf

    print(f"Recording audio for {duration} seconds...")
    recording = sd.rec(int(duration * samplerate), samplerate=samplerate, channels=channels)
    sd.wait()  # Wait until recording is finished
    sf.write(filename, recording, samplerate)
    print(f"Recording saved to {filename}")
    return filename

def transcribe_audio(file_path: str) -> str:
    """
    Transcribe the audio file using OpenAI's Whisper API.
    """
    from openai import OpenAI
    # Create an OpenAI client using our environment variables.
    client = OpenAI(
        api_key=os.getenv("ALI_OPENAI_API_KEY"),
        organization=os.getenv("ALI_OPENAI_ORG_ID"),
        project=os.getenv("ALI_OPENAI_PROJECT_ID")
    )
    with open(file_path, "rb") as audio_file:
        transcription = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            response_format="text"
        )

    logger.info(f"Transcription: {transcription}")
    return transcription  # Remove .text since transcription is already a string

def generate_gpt_response(user_text: str) -> str:
    """
    Generate a GPT-4-based response given the user's input text.
    """
    from openai import OpenAI
    client = OpenAI(
        api_key=os.getenv("ALI_OPENAI_API_KEY"),
        organization=os.getenv("ALI_OPENAI_ORG_ID"),
        project=os.getenv("ALI_OPENAI_PROJECT_ID")
    )
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": user_text}
        ],
        timeout=10
    )
    return completion.choices[0].message.content

def create_conversation_folder():
    """Create a timestamped folder for the conversation"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder_path = os.path.join("saved_conversations", timestamp)
    os.makedirs(folder_path, exist_ok=True)
    logger.info(f"Created conversation folder: {os.path.abspath(folder_path)}")
    return folder_path

def get_first_n_words(text: str, n: int = 5) -> str:
    """Get first n words from text and format for filename"""
    words = re.sub(r'[^\w\s]', '', text).split()[:n]
    return '_'.join(words).lower()

def save_conversation_item(folder_path: str, speaker: str, turn: int, text: str, 
                         audio_data=None, original_audio_file=None):
    """Save text and audio files for a conversation turn"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    first_words = get_first_n_words(text)
    base_filename = f"{speaker}_{turn}_{first_words}_{timestamp}"
    
    # Save text
    text_path = os.path.join(folder_path, f"{base_filename}.txt")
    with open(text_path, "w") as f:
        f.write(text)
    logger.info(f"Saved text file: {os.path.abspath(text_path)}")
    
    # Save audio if provided
    if audio_data is not None:
        audio_path = os.path.join(folder_path, f"{base_filename}.mp3")
        with open(audio_path, "wb") as f:
            # Convert generator to bytes if needed
            if hasattr(audio_data, '__iter__'):
                audio_bytes = b"".join(audio_data)
            else:
                audio_bytes = audio_data
            f.write(audio_bytes)
        logger.info(f"Saved audio file (MP3): {os.path.abspath(audio_path)}")
    elif original_audio_file is not None:
        # Copy original wav file
        wav_path = os.path.join(folder_path, f"{base_filename}.wav")
        import shutil
        shutil.copy2(original_audio_file, wav_path)
        logger.info(f"Saved audio file (WAV): {os.path.abspath(wav_path)}")
        
        # Also create an MP3 copy
        from pydub import AudioSegment
        mp3_path = os.path.join(folder_path, f"{base_filename}.mp3")
        audio = AudioSegment.from_wav(wav_path)
        audio.export(mp3_path, format="mp3")
        logger.info(f"Saved audio file (MP3 copy): {os.path.abspath(mp3_path)}")

async def conversation_loop(speaker: RobotSpeaker):
    """
    Main loop: record audio from mic, transcribe it, generate a GPT response,
    and then speak & display that response. Exits when user says "bye".
    """
    try:
        # Create conversation folder
        conversation_folder = create_conversation_folder()
        turn_counter = 1

        while True:
            print("\n=== New Interaction ===")
            # Record from the microphone
            audio_file = await asyncio.to_thread(record_audio, 5)
            print("Transcribing audio...")
            transcription = await asyncio.to_thread(transcribe_audio, audio_file)
            print(f"You said: {transcription}")

            # Save user's turn
            save_conversation_item(
                conversation_folder, 
                "user", 
                turn_counter, 
                transcription,
                original_audio_file=audio_file
            )

            # Check if user said bye
            if "bye" in transcription.lower():
                print("Generating goodbye response...")
                response_text = await asyncio.to_thread(generate_gpt_response, 
                    "The user said goodbye. Give a friendly goodbye response in 10 words or less.")
                print(f"GPT-4 response: {response_text}")
                
                # Generate and save assistant's goodbye response
                audio = speaker.eleven.text_to_speech.convert(
                    text=response_text,
                    voice_id=speaker.voice_id,
                    model_id="eleven_multilingual_v2",
                    output_format="mp3_44100_128",
                )
                save_conversation_item(
                    conversation_folder,
                    "assistant",
                    turn_counter,
                    response_text,
                    audio_data=audio
                )
                
                await speaker.speak_and_display(response_text)
                logger.info("Conversation ended by user saying goodbye")
                break

            # Generate a response using GPT-4
            print("Generating response...")
            response_text = await asyncio.to_thread(generate_gpt_response, transcription)
            print(f"GPT-4 response: {response_text}")

            # Generate audio and save assistant's response
            audio = speaker.eleven.text_to_speech.convert(
                text=response_text,
                voice_id=speaker.voice_id,
                model_id="eleven_multilingual_v2",
                output_format="mp3_44100_128",
            )
            save_conversation_item(
                conversation_folder,
                "assistant",
                turn_counter,
                response_text,
                audio_data=audio
            )

            # Use the robot speaker to speak and display the response
            await speaker.speak_and_display(response_text)
            
            turn_counter += 1

    except KeyboardInterrupt:
        logger.info("Conversation interrupted by user.")

# ------------------------
# Main Execution
# ------------------------
async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Robot conversation: speak & respond.")
    parser.add_argument("--ip", default="10.33.11.231", help="Robot IP address")
    parser.add_argument("--voice", default="uh5qBlKfjqFl7XXhFnJi", help="ElevenLabs voice ID")
    parser.add_argument("--duration", type=int, default=5, help="Recording duration in seconds")
    args = parser.parse_args()

    speaker = RobotSpeaker(ip=args.ip)
    try:
        await speaker.connect()
        print("Ready for conversation. Press Ctrl+C to exit.")
        await conversation_loop(speaker)
    finally:
        await speaker.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Program terminated by user.")
