import os
import sounddevice as sd
from scipy.io.wavfile import write
from openai import OpenAI
from dotenv import load_dotenv
import numpy as np
from loguru import logger
import traceback

# Load environment variables (make sure your .env file contains your API keys)
load_dotenv()

# Create an OpenAI client using your environment variables
client = OpenAI(
    api_key=os.getenv("ALI_OPENAI_API_KEY"),
    organization=os.getenv("ALI_OPENAI_ORG_ID"),
    project=os.getenv("ALI_OPENAI_PROJECT_ID")
)

def record_audio():
    # Audio recording parameters
    sample_rate = 16000  # Sample rate in Hz (Whisper works fine with 16 kHz)
    filename = "recorded_audio.wav"
    
    logger.info("Press Enter to start recording...")
    input()  # Wait for Enter key
    logger.info("Recording... Press Ctrl+C to stop")
    
    # Initialize an empty list to store audio chunks
    audio_chunks = []
    
    try:
        # Start recording
        with sd.InputStream(samplerate=sample_rate, channels=1, dtype='int16') as stream:
            try:
                while True:
                    # Record in chunks
                    audio_chunk, overflowed = stream.read(sample_rate)
                    audio_chunks.append(audio_chunk)
            except KeyboardInterrupt:  # User presses Ctrl+C
                pass
        
        # Combine all audio chunks
        recording = np.concatenate(audio_chunks)
        
        # Save the recording to a WAV file
        write(filename, sample_rate, recording)
        logger.info(f"Recording complete. Saved to {filename}")
        return filename
    except Exception as e:
        logger.error(f"Error during audio recording: {str(e)}")
        logger.error(f"Full traceback:\n{''.join(traceback.format_tb(e.__traceback__))}")
        raise

def main():
    try:
        # Record the audio
        filename = record_audio()
        
        # Open the recorded file and send it for transcription
        with open(filename, "rb") as audio_file:
            transcription = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="text"
            )

        logger.info("Transcription:")
        logger.info(transcription)

    except Exception as e:
        logger.error(f"Error in speech-to-text process: {str(e)}")
        logger.error(f"Full traceback:\n{''.join(traceback.format_tb(e.__traceback__))}")

if __name__ == "__main__":
    main()
