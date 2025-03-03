import socket
import time
import wave
import os
import numpy as np
import soundfile as sf
from datetime import datetime
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# OpenAI Configuration
client = OpenAI()  # It will automatically read from environment variable

if not os.getenv("OPENAI_API_KEY"):
    raise ValueError(
        "OPENAI_API_KEY environment variable is not set. Please create a .env file with your API key."
    )

# Audio Configuration
CHUNK = 8192
RATE = 44100
CHANNELS = 1
BUFFER_SIZE = 20


def maintain_connection(host, port, max_retries=5):
    """Establish and maintain a connection with retries"""
    for attempt in range(max_retries):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((host, port))
            return sock
        except socket.error as e:
            if attempt < max_retries - 1:
                print(
                    f"Connection attempt {attempt + 1} failed. Retrying in 2 seconds..."
                )
                time.sleep(2)
            else:
                raise ConnectionError(
                    f"Failed to connect after {max_retries} attempts: {e}"
                )
    return None


def receive_and_save_audio(sock):
    """Receive audio from robot and save to WAV file"""
    print("\nWaiting for audio from robot...")

    # First receive the header
    header_bytes = b""
    while b"\n" not in header_bytes:
        try:
            chunk = sock.recv(1024)
            if not chunk:
                return None
            header_bytes += chunk
        except socket.error:
            return None

    header_line, leftover = header_bytes.split(b"\n", 1)
    header_line = header_line.decode("utf-8").strip()
    print(f"Received header: {header_line}")

    # Initialize list for audio data
    received_audio = [np.frombuffer(leftover, dtype=np.int16)]

    # Receive audio data until connection is closed
    try:
        while True:
            data = sock.recv(CHUNK * 2)
            if not data:
                break
            audio_chunk = np.frombuffer(data, dtype=np.int16)
            received_audio.append(audio_chunk)
    except Exception as e:
        if len(received_audio) <= 1:  # If we didn't get meaningful audio
            return None

    # Combine all chunks
    audio_data = np.concatenate(received_audio)

    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"received_audio_{timestamp}.wav"

    # Save as WAV file
    sf.write(filename, audio_data, RATE)
    print(f"Saved recording to {filename}")

    return filename


def process_audio_and_get_response(audio_file):
    """Process audio through Whisper and GPT, return response as audio"""
    try:
        print("Converting audio to text...")
        with open(audio_file, "rb") as f:
            transcription = client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                response_format="text",
                temperature=0.0,
                language="en",
            )
        print(f"Transcribed text: {transcription}")

        response_text = ""
        stream = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant. Keep your responses concise and natural, as they will be spoken back to the user.",
                },
                {"role": "user", "content": transcription},
            ],
            stream=True,
            temperature=0.7,
            max_tokens=150,
        )

        for chunk in stream:
            if chunk.choices[0].delta.content is not None:
                response_text += chunk.choices[0].delta.content
        print(f"GPT response: {response_text}")

        print("Converting to speech...")
        response = client.audio.speech.create(
            model="tts-1",
            voice="alloy",
            input=response_text,
            response_format="wav",
            speed=1.1,
        )

        response_file = "response.wav"
        with open(response_file, "wb") as f:
            f.write(response.content)

        return response_file

    except Exception as e:
        print(f"Error processing audio: {e}")
        return None


def send_audio_file(sock, filename):
    """Send audio file to robot for playback"""
    try:
        # Read the audio file
        audio_data, orig_rate = sf.read(filename)

        # Convert to mono if stereo
        if len(audio_data.shape) > 1:
            audio_data = audio_data.mean(axis=1)

        # Resample if needed
        if orig_rate != RATE:
            duration = len(audio_data) / orig_rate
            time_old = np.linspace(0, duration, len(audio_data))
            time_new = np.linspace(0, duration, int(len(audio_data) * RATE / orig_rate))
            audio_data = np.interp(time_new, time_old, audio_data)

        # Convert to int16
        audio_data = (audio_data * 32767).astype(np.int16)

        # Send header
        header = f"RATE:{RATE},CHANNELS:{CHANNELS}\n".encode("utf-8")
        sock.sendall(header)

        # Send audio data in chunks
        chunk_size = CHUNK * CHANNELS * 2
        total_samples = len(audio_data)

        for i in range(0, total_samples, CHUNK):
            chunk = audio_data[i : i + CHUNK]
            if len(chunk) < CHUNK:
                chunk = np.pad(chunk, (0, CHUNK - len(chunk)), "constant")
            chunk_data = chunk.tobytes()
            sock.sendall(chunk_data)
            time.sleep(CHUNK / RATE)

        print("Response sent")
        return True

    except Exception as e:
        print(f"Error sending audio: {e}")
        return False


def cleanup_old_files():
    """Clean up old audio files"""
    try:
        # Remove all wav files older than 1 hour
        current_time = time.time()
        for file in Path(".").glob("*.wav"):
            if current_time - file.stat().st_mtime > 3600:  # 1 hour
                file.unlink()
    except Exception as e:
        print(f"Error cleaning up files: {e}")


def main():
    HOST = "10.33.11.231"  # IP of the robot
    PORT = 4444

    print(f"Starting continuous conversation mode with {HOST}:{PORT}")
    print("Press Ctrl+C to exit")

    while True:
        try:
            # Main connection for receiving audio
            with maintain_connection(HOST, PORT) as s:
                while True:
                    # Wait for and receive recording
                    audio_file = receive_and_save_audio(s)

                    if audio_file:
                        # Process audio and get response
                        response_file = process_audio_and_get_response(audio_file)

                        if response_file:
                            # Send response back to robot
                            with maintain_connection(HOST, PORT) as send_sock:
                                send_audio_file(send_sock, response_file)

                            # Clean up files
                            try:
                                os.remove(audio_file)
                                os.remove(response_file)
                            except:
                                pass

                    # Periodically clean up old files
                    cleanup_old_files()

        except KeyboardInterrupt:
            print("\nStopping by user request...")
            break
        except Exception as e:
            print(f"\nConnection error: {e}")
            print("Reconnecting in 5 seconds...")
            time.sleep(5)


if __name__ == "__main__":
    main()
