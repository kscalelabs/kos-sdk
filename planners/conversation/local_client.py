# test.py - handles recording from robot and playback
import socket
import time
import wave
import os
import numpy as np
import soundfile as sf
from datetime import datetime
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv  # Add this import

# Load environment variables from .env file
load_dotenv()

# OpenAI Configuration
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Audio Configuration
CHUNK = 8192        # Larger chunk size for stability
RATE = 44100       # Standard sample rate
CHANNELS = 1       # Mono audio
BUFFER_SIZE = 20   # For receiving

def receive_and_save_audio(sock):
    """Receive audio from robot and save to WAV file"""
    print("Waiting for audio from robot...")
    
    # First receive the header
    header_bytes = b""
    while b"\n" not in header_bytes:
        chunk = sock.recv(1024)
        if not chunk:
            return None
        header_bytes += chunk
    
    header_line, leftover = header_bytes.split(b"\n", 1)
    header_line = header_line.decode('utf-8').strip()
    print(f"Received header: {header_line}")
    
    # Initialize list for audio data
    received_audio = [np.frombuffer(leftover, dtype=np.int16)]
    
    # Receive audio data until connection is closed
    try:
        while True:
            data = sock.recv(CHUNK * 2)  # 2 bytes per sample
            if not data:
                break
            audio_chunk = np.frombuffer(data, dtype=np.int16)
            received_audio.append(audio_chunk)
    except Exception as e:
        print(f"Error receiving audio: {e}")
    
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
    print("Converting audio to text...")
    with open(audio_file, "rb") as f:
        transcription = client.audio.transcriptions.create(
            model="whisper-1", 
            file=f,
            response_format="text",
            temperature=0.0,  # More deterministic for faster processing
            language="en"
        )
    print(f"Transcribed text: {transcription}")
    
    print("Getting GPT response...")
    response_text = ""
    # Stream the chat completion
    stream = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful assistant. Keep your responses concise and natural, as they will be spoken back to the user."},
            {"role": "user", "content": transcription}
        ],
        stream=True,  # Enable streaming
        temperature=0.7,
        max_tokens=150  # Limit response length for faster processing
    )
    
    print("Streaming response: ", end='', flush=True)
    for chunk in stream:
        if chunk.choices[0].delta.content is not None:
            response_text += chunk.choices[0].delta.content
            print(".", end='', flush=True)
    print(f"\nGPT response: {response_text}")
    
    print("Converting response to speech...")
    response = client.audio.speech.create(
        model="tts-1",  # Using tts-1 for faster generation
        voice="alloy",
        input=response_text,
        response_format="wav",
        speed=1.1  # Slightly faster speech
    )
    
    # Save the response audio
    response_file = "response.wav"
    with open(response_file, "wb") as f:
        f.write(response.content)
    print(f"Response audio saved to {response_file}")
    
    return response_file

def send_audio_file(sock, filename):
    """Send audio file to robot for playback"""
    print(f"Sending {filename} to robot...")
    
    try:
        # Read the audio file and get its properties
        audio_data, orig_rate = sf.read(filename)
        
        # Convert to mono if stereo
        if len(audio_data.shape) > 1:
            audio_data = audio_data.mean(axis=1)
        
        # Resample if needed
        if orig_rate != RATE:
            print(f"Resampling from {orig_rate}Hz to {RATE}Hz")
            duration = len(audio_data) / orig_rate
            time_old = np.linspace(0, duration, len(audio_data))
            time_new = np.linspace(0, duration, int(len(audio_data) * RATE / orig_rate))
            audio_data = np.interp(time_new, time_old, audio_data)
        
        # Convert to int16 with proper scaling
        audio_data = (audio_data * 32767).astype(np.int16)
        
        # Send header
        header = f"RATE:{RATE},CHANNELS:{CHANNELS}\n".encode('utf-8')
        sock.sendall(header)
        print(f"Sent header: {header.decode().strip()}")
        
        # Stream the audio data in chunks with proper timing
        chunk_size = CHUNK * CHANNELS * 2  # 2 bytes per sample
        total_samples = len(audio_data)
        
        print(f"Streaming audio file... ({total_samples/RATE:.1f} seconds)")
        
        for i in range(0, total_samples, CHUNK):
            # Get chunk of samples
            chunk = audio_data[i:i + CHUNK]
            
            # Pad the last chunk if needed
            if len(chunk) < CHUNK:
                chunk = np.pad(chunk, (0, CHUNK - len(chunk)), 'constant')
            
            # Send the chunk
            chunk_data = chunk.tobytes()
            sock.sendall(chunk_data)
            
            # Control playback speed precisely
            time.sleep(CHUNK / RATE)  # Wait exactly one chunk duration
            
            # Show progress
            if (i % (CHUNK * 10)) == 0:
                print(".", end='', flush=True)
        
        print("\nFinished streaming audio file.")
        
    except Exception as e:
        print(f"Error sending audio: {e}")
        raise

def main():
    HOST = '10.33.12.0'  # IP of the robot
    PORT = 4444
    
    while True:
        try:
            # Create a new connection for each operation
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((HOST, PORT))
                print(f"Connected to {HOST}:{PORT}")
                
                # Wait for and receive recording
                audio_file = receive_and_save_audio(s)
                
                if audio_file:
                    # Process audio and get response
                    response_file = process_audio_and_get_response(audio_file)
                    
                    # Send response back to robot
                    print("\nSending response back to robot...")
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as send_sock:
                        send_sock.connect((HOST, PORT))
                        send_audio_file(send_sock, response_file)
                
                # Ask if user wants to continue
                response = input("\nDo you want to continue? (y/n): ")
                if response.lower() != 'y':
                    break
                    
        except KeyboardInterrupt:
            print("\nStopped by user")
            break
        except Exception as e:
            print(f"Error: {e}")
            response = input("\nDo you want to try again? (y/n): ")
            if response.lower() != 'y':
                break

if __name__ == '__main__':
    main()