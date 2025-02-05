import os
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv
from playsound import playsound
from loguru import logger
import traceback

# Load environment variables (ensure your .env file contains your API credentials)
load_dotenv()

# Create an OpenAI client using your environment variables
client = OpenAI(
    api_key=os.getenv("ALI_OPENAI_API_KEY"),
    organization=os.getenv("ALI_OPENAI_ORG_ID"),
    project=os.getenv("ALI_OPENAI_PROJECT_ID")
)

# Define the input text for TTS
input_text = "Today is a wonderful day to build something people love!"

# Define the output file path for the generated speech
speech_file_path = Path("speech.mp3")

logger.info("Generating speech audio...")

try:
    # Generate speech audio from the input text
    response = client.audio.speech.create(
        model="tts-1",   # You can experiment with "tts-1-hd" for higher quality if desired
        voice="alloy",   # Options include alloy, ash, coral, echo, fable, onyx, nova, sage, and shimmer
        input=input_text
    )

    # Stream the generated audio to a file
    response.stream_to_file(speech_file_path)

    logger.info(f"Speech audio saved to {speech_file_path}")

    # Play the generated audio
    logger.info("Playing audio...")
    playsound(str(speech_file_path))

except Exception as e:
    logger.error(f"Error in text-to-speech process: {str(e)}")
    logger.error(f"Full traceback:\n{''.join(traceback.format_tb(e.__traceback__))}")
