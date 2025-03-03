# Robot side - handles recording and playback
import socket
import sounddevice as sd
import numpy as np
import time
import sys
import select
import tty
import termios

CHUNK = 1024
CHANNELS = 1  # This is for playback, recording will use channel 2
RATE = 44100
PLAY_DEVICE = 1  # Speaker device (cv182xa_dac)
REC_DEVICE = 0  # Microphone device (cv182xa_adc)


def is_data():
    """Check if there's input waiting"""
    return select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], [])


def record_audio(duration=None):
    """Record audio from microphone"""
    print("\nRecording... Press 'q' to stop.")
    print("Recording in progress: ", end="", flush=True)

    # Store original terminal settings
    old_settings = termios.tcgetattr(sys.stdin)
    try:
        # Set terminal to raw mode
        tty.setraw(sys.stdin.fileno())

        # Use the same parameters that work in audio_test.py
        channels = [2]  # Use channel 2 of the microphone
        buffer_duration = 1.0  # Record in 1-second chunks
        buffer_samples = int(RATE * buffer_duration)
        recorded_chunks = []
        seconds = 0

        while True:
            # Start recording this chunk
            chunk_recording = sd.rec(
                int(buffer_samples),
                samplerate=RATE,
                channels=len(channels),
                device=REC_DEVICE,
                dtype="float32",
                mapping=channels,
            )

            # Wait for recording to complete while checking for 'q'
            start_time = time.time()
            while time.time() - start_time < buffer_duration:
                if is_data() and sys.stdin.read(1) == "q":
                    sd.stop()
                    break
                time.sleep(0.1)

            sd.wait()  # Ensure the recording is complete

            # Add the chunk to our recording
            recorded_chunks.append(chunk_recording)
            seconds += 1
            print(".", end="", flush=True)

            # Check if we should stop
            if is_data() and sys.stdin.read(1) == "q":
                break

    finally:
        # Restore terminal settings
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
        print(f"\nRecording stopped after approximately {seconds} seconds")

    if not recorded_chunks:
        print("No audio was recorded!")
        return None

    # Combine all chunks
    audio_data = np.concatenate(recorded_chunks)

    # Convert float32 to int16 for sending
    audio_data = (audio_data * 32767).astype(np.int16)

    duration = len(audio_data) / RATE

    # Print some statistics to verify the recording
    print(f"Recorded {duration:.1f} seconds of audio")
    print(f"Max value: {np.max(np.abs(audio_data))}")
    print(f"Mean value: {np.mean(np.abs(audio_data))}")
    print(f"Shape: {audio_data.shape}")

    return audio_data


def play_audio(conn):
    """Play received audio"""
    try:
        # First receive the header
        header_bytes = b""
        while b"\n" not in header_bytes:
            chunk = conn.recv(1024)
            if not chunk:
                return
            header_bytes += chunk

        header_line, leftover = header_bytes.split(b"\n", 1)
        header_line = header_line.decode("utf-8").strip()
        print(f"Received header: {header_line}")

        # Create output stream
        stream = sd.OutputStream(
            samplerate=RATE, blocksize=CHUNK, device=PLAY_DEVICE, channels=CHANNELS, dtype=np.int16
        )

        with stream:
            stream.start()
            print("Playing received audio...")

            # Play any leftover data
            if leftover:
                audio_data = np.frombuffer(leftover, dtype=np.int16)
                stream.write(audio_data)

            # Receive and play audio
            while True:
                data = conn.recv(CHUNK * CHANNELS * 2)
                if not data:
                    break
                audio_data = np.frombuffer(data, dtype=np.int16)
                stream.write(audio_data)

            print("Finished playing audio.")

    except Exception as e:
        print(f"Error playing audio: {e}")


def send_audio_data(conn, audio_data):
    """Send audio data with proper flow control"""
    try:
        # Send header first
        header = f"RATE:{RATE},CHANNELS:{CHANNELS}\n".encode("utf-8")
        conn.sendall(header)

        # Send audio data in smaller chunks with flow control
        chunk_size = CHUNK * CHANNELS * 2  # 2 bytes per sample
        total_sent = 0
        total_size = len(audio_data)
        duration = len(audio_data) / RATE

        print(f"\nSending {duration:.1f} seconds of audio...")

        for i in range(0, total_size, chunk_size):
            chunk = audio_data[i : i + chunk_size].tobytes()
            conn.sendall(chunk)
            total_sent += len(chunk)

            # Show progress
            if (total_sent % (chunk_size * 10)) == 0:
                print(".", end="", flush=True)

            # Small delay to prevent buffer overflow
            time.sleep(0.001)

        print(f"\nSuccessfully sent {duration:.1f} seconds of audio")
        return True

    except Exception as e:
        print(f"\nError sending recording: {e}")
        return False


def main():
    HOST = "0.0.0.0"
    PORT = 4444

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server_socket.bind((HOST, PORT))
        server_socket.listen(1)
        print(f"Listening on {HOST}:{PORT}...")

        while True:
            conn, addr = server_socket.accept()
            print(f"Connection from {addr}")

            try:
                # Start recording when 'r' is pressed
                print("\nPress 'r' to start recording, or wait to receive audio...")

                # Set terminal to raw mode
                old_settings = termios.tcgetattr(sys.stdin)
                try:
                    tty.setraw(sys.stdin.fileno())

                    # Wait for either 'r' key or incoming data
                    while True:
                        if is_data():
                            c = sys.stdin.read(1)
                            if c == "r":
                                # Restore terminal settings before recording
                                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

                                # Record and send audio
                                print("\nStarting recording...")
                                audio_data = record_audio()

                                if audio_data is not None and len(audio_data) > 0:
                                    # Set socket to blocking mode for sending
                                    conn.setblocking(1)
                                    if not send_audio_data(conn, audio_data):
                                        print("Failed to send recording")
                                else:
                                    print("No audio data to send")
                                break

                        # Check for incoming data
                        conn.setblocking(0)
                        try:
                            data = conn.recv(1, socket.MSG_PEEK)
                            if data:
                                # Restore terminal settings before playback
                                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
                                conn.setblocking(1)
                                play_audio(conn)
                                break
                        except socket.error:
                            pass

                        time.sleep(0.1)

                finally:
                    # Ensure terminal settings are restored
                    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

            except Exception as e:
                print(f"Error: {e}")
            finally:
                conn.close()
                print("Connection closed")

    except KeyboardInterrupt:
        print("\nStopped by user")
    finally:
        server_socket.close()


if __name__ == "__main__":
    main()
