import os
import numpy as np
import sounddevice as sd
from scipy.io.wavfile import write
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv
import pygame  # Add this import at the top
from loguru import logger
import traceback
import time  # Add this import

# Load environment variables (ensure your .env file contains your API credentials)
load_dotenv()

# Create an OpenAI client using your environment variables
client = OpenAI(
    api_key=os.getenv("ALI_OPENAI_API_KEY"),
    organization=os.getenv("ALI_OPENAI_ORG_ID"),
    project=os.getenv("ALI_OPENAI_PROJECT_ID")
)

# Initialize pygame mixer at the start
pygame.mixer.init()

def record_audio():
    """
    Records audio until Ctrl+C is pressed.
    The recording is saved to 'recorded_audio.wav' and the filename is returned.
    """
    sample_rate = 16000  # in Hz
    filename = "recorded_audio.wav"
    logger.info("Recording... Press Ctrl+C to stop.")

    audio_chunks = []
    try:
        with sd.InputStream(samplerate=sample_rate, channels=1, dtype='int16') as stream:
            try:
                while True:
                    # Read approximately 1 second of audio at a time
                    audio_chunk, overflowed = stream.read(sample_rate)
                    audio_chunks.append(audio_chunk)
            except KeyboardInterrupt:
                # When Ctrl+C is pressed, exit the recording loop
                pass

        # Combine all recorded chunks and write to WAV file
        recording = np.concatenate(audio_chunks)
        write(filename, sample_rate, recording)
        logger.info(f"Recording complete. Saved to {filename}")
        return filename

    except Exception as e:
        logger.error("Error during audio recording: {}", e)
        logger.error("Full traceback:\n{}", ''.join(traceback.format_tb(e.__traceback__)))
        raise

def transcribe_audio(filename):
    """
    Sends the recorded audio file to the Whisper API for transcription.
    Returns the transcribed text.
    """
    start_time = time.time()
    try:
        with open(filename, "rb") as audio_file:
            transcription = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="text"
            )
        duration = time.time() - start_time
        logger.info("Transcription took {:.1f} seconds", duration)
        logger.info("Transcription: {}", transcription)
        return transcription

    except Exception as e:
        logger.error("Error in transcription: {}", e)
        logger.error("Full traceback:\n{}", ''.join(traceback.format_tb(e.__traceback__)))
        raise

def generate_response(user_text):
    """
    Sends the user input text to the GPT-4o mini chat API with a system prompt
    defining Zbot, and returns the bot's response text.
    """
    start_time = time.time()
    try:
        messages = [
            {"role": "system", "content": (
                "You are Zbot. A helpful 40 cm tall humanoid robot that is open source. "
                "You give short answers to questions, and are curious and love helping people learn about robotics, computer science, and AI. You have a fun and charming personality."
            )},
            {"role": "user", "content": user_text}
        ]
        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            timeout=10
        )
        bot_response = completion.choices[0].message.content
        duration = time.time() - start_time
        logger.info("Response generation took {:.1f} seconds", duration)
        logger.info("Zbot Response: {}", bot_response)
        return bot_response

    except Exception as e:
        logger.error("Error generating response: {}", e)
        logger.error("Full traceback:\n{}", ''.join(traceback.format_tb(e.__traceback__)))
        raise

def generate_and_play_speech(text):
    """
    Converts the provided text to speech using the TTS API,
    saves the audio as 'speech.mp3', and plays it.
    Can be interrupted with Ctrl+C during playback.
    """
    speech_file_path = Path("speech.mp3")
    start_time = time.time()
    try:
        logger.info("Generating speech audio...")
        response = client.audio.speech.create(
            model="tts-1",
            voice="alloy",
            input=text
        )
        response.stream_to_file(speech_file_path)
        generation_duration = time.time() - start_time
        logger.info("Speech generation took {:.1f} seconds", generation_duration)
        
        logger.info(f"Speech audio saved to {speech_file_path}")
        logger.info("Playing audio... (Press Ctrl+C to skip)")
        
        playback_start = time.time()
        try:
            pygame.mixer.music.load(str(speech_file_path))
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
            playback_duration = time.time() - playback_start
            logger.info("Audio playback took {:.1f} seconds", playback_duration)
        except KeyboardInterrupt:
            playback_duration = time.time() - playback_start
            logger.info("Playback interrupted after {:.1f} seconds", playback_duration)
            pygame.mixer.music.stop()
            
    except Exception as e:
        logger.error("Error in text-to-speech: {}", e)
        logger.error("Full traceback:\n{}", ''.join(traceback.format_tb(e.__traceback__)))
        raise

def main():
    """
    Main conversation loop:
      1. Records user speech (stopped with Ctrl+C).
      2. Transcribes the audio to text.
      3. Sends the text to the AI (Zbot) for a response.
      4. Converts the response to speech and plays it.
      5. Repeats indefinitely.
    """
    logger.info("Starting conversation. Speak now; press Ctrl+C during recording to send your message. To exit the conversation, press Ctrl+C when not recording.")

    try:
        while True:
            # Record user speech until Ctrl+C is pressed
            audio_filename = record_audio()

            # Convert recorded audio to text
            user_text = transcribe_audio(audio_filename)
            if not user_text.strip():
                logger.info("No speech detected. Starting a new recording...")
                continue  # Skip to the next loop iteration if transcription is empty
            
            if "bye" in user_text.lower():
                logger.info("User said: {}", user_text)
                logger.info("Exiting conversation. Goodbye!")
                break

            logger.info("User said: {}", user_text)

            # Generate AI (Zbot) response based on the transcribed text
            bot_response = generate_response(user_text)

            # Convert the AI response to speech and play it
            generate_and_play_speech(bot_response)

    except KeyboardInterrupt:
        logger.info("Exiting conversation. Goodbye!")

if __name__ == "__main__":
    main()
