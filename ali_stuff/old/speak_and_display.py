import asyncio
import re
import os
import json
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from dotenv import load_dotenv
from loguru import logger
from demos.robot import RobotInterface
from elevenlabs.client import ElevenLabs
from elevenlabs import play
import openai
from openai import OpenAI

# Load environment variables (including OPENAI_API_KEY)
load_dotenv()
openai.api_key = os.getenv("ALI_OPENAI_API_KEY")
openai.organization = os.getenv("ALI_OPENAI_ORG_ID")
OPENAI_PROJECT_ID = os.getenv("ALI_OPENAI_PROJECT_ID")

class RobotSpeaker:
    def __init__(self, ip="10.33.11.231"):
        self.robot = RobotInterface(ip=ip)
        self.eleven = ElevenLabs()

    async def connect(self):
        """Connect to robot"""
        await self.robot.__aenter__()
        logger.info("Connected to robot")

    async def close(self):
        """Clean shutdown"""
        try:
            # Turn off display
            info = await self.robot.kos.led_matrix.get_matrix_info()
            buffer_size = info.width * info.height // 8
            off_buffer = bytes([0x00] * buffer_size)
            await self.robot.kos.led_matrix.write_buffer(off_buffer)
            logger.info("Display turned off")
        finally:
            await self.robot.__aexit__(None, None, None)

    async def display_text(self, text: str):
        """
        Draws the given text (in our case a single emoji) onto the robot's LED matrix.
        """
        try:
            info = await self.robot.kos.led_matrix.get_matrix_info()
            image = Image.new('L', (info.width, info.height), 0)
            draw = ImageDraw.Draw(image)

            # Start with a font size equal to the height of the display.
            font_size = info.height
            font = ImageFont.load_default()
            text_width = info.width + 1  # initialize to force loop

            # Try to find a font size that fits the emoji
            while text_width > info.width and font_size > 1:
                try:
                    # For simplicity, we use the default font.
                    # (For full emoji support you might need a TTF that supports emojis.)
                    font = ImageFont.load_default()
                    bbox = draw.textbbox((0, 0), text, font=font)
                    text_width = bbox[2] - bbox[0]
                    text_height = bbox[3] - bbox[1]
                    font_size -= 1
                except Exception:
                    font = ImageFont.load_default()
                    break

            # Center the text
            x = (info.width - text_width) // 2
            y = (info.height - text_height) // 2

            draw.text((x, y), text, font=font, fill=255)

            # Convert image to binary for the LED matrix
            binary = image.point(lambda x: 0 if x < 128 else 1, '1')
            arr = np.array(binary, dtype=np.uint8)
            packed = np.packbits(arr)
            buffer = bytes(packed)

            await self.robot.kos.led_matrix.write_buffer(buffer)
        except Exception as e:
            logger.error(f"Error in display_text: {e}", exc_info=True)

    def get_emojis_for_text(self, text: str) -> list:
        """
        Uses GPT-4-o-mini (via OpenAI's structured outputs) to select one emoji per sentence.
        The prompt instructs the model to output a JSON object with a single key "emojis" that is
        an array of single-character strings.
        """
        logger.info("Entering get_emojis_for_text")
        try:
            # Instantiate the new client from the new OpenAI interface.
            logger.info("Creating OpenAI client")
            client = OpenAI(
                api_key=os.getenv("ALI_OPENAI_API_KEY"),
                organization=os.getenv("ALI_OPENAI_ORG_ID"),
                project=os.getenv("ALI_OPENAI_PROJECT_ID")
            )
            
            logger.info("Making API call to OpenAI...")
            logger.info(f"Using API key: {os.getenv('ALI_OPENAI_API_KEY')[:5]}...")
            logger.info(f"Using project ID: {os.getenv('ALI_OPENAI_PROJECT_ID')}")

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an emoji selector. For each sentence in the provided text, "
                            "select one emoji that best represents the emotion or tone of the sentence. "
                            "Return a JSON object with a key 'emojis' which is an array of strings, "
                            "where each string is a single emoji corresponding to each sentence in order. "
                            "Provide no additional text."
                        )
                    },
                    {"role": "user", "content": text},
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "emoji_selection",
                        "schema": {
                            "type": "object",
                            "properties": {
                                "emojis": {
                                    "type": "array",
                                    "items": {"type": "string"}
                                }
                            },
                            "required": ["emojis"],
                            "additionalProperties": False
                        },
                        "strict": True
                    }
                },
                timeout=10
            )
            
            content = response.choices[0].message.content
            logger.info(f"Raw content from OpenAI: {content}")
            
            parsed = json.loads(content)
            logger.info(f"Successfully parsed JSON response")
            
            return parsed.get("emojis", [])
        except Exception as e:
            logger.error(f"Error in get_emojis_for_text: {str(e)}", exc_info=True)
            return ["😕"]  # Return a default emoji on error

    async def display_emojis(self, emojis: list, sentences: list):
        """
        For each sentence, display the corresponding emoji on the robot display
        and print to terminal. The display remains for an estimated duration based on
        the sentence length.
        """
        for sentence, emoji in zip(sentences, emojis):
            await self.display_text(emoji)
            logger.info(f"Sentence: {sentence} -> Emoji: {emoji}")
            print(f"Sentence: {sentence} -> Emoji: {emoji}")
            # Estimate duration: assume an average speaking rate of ~150 wpm (~2.5 words/sec)
            word_count = len(sentence.split())
            duration = word_count / 2.5
            # Ensure a minimum display time (e.g. 2 seconds)
            duration = max(duration, 2)
            await asyncio.sleep(duration)

    async def speak_and_display(self, text: str, voice_id="JBFqnCBsd6RMkjVDRZzb"):
        """
        Gets the audio for the full text using ElevenLabs and concurrently displays emoji expressions.
        """
        try:
            logger.info(f"Converting text to speech and displaying emojis for: {text}")

            # Generate speech audio via ElevenLabs.
            logger.info("Generating speech audio via ElevenLabs...")
            audio = self.eleven.text_to_speech.convert(
                text=text,
                voice_id=voice_id,
                model_id="eleven_multilingual_v2",
                output_format="mp3_44100_128",
            )
            logger.info("Successfully generated audio")

            # Start playing the audio in a background thread.
            logger.info("Starting audio playback...")
            play_audio_task = asyncio.create_task(asyncio.to_thread(play, audio))
            logger.info("Audio playback task created")

            # Get the emojis from GPT-4-o-mini.
            logger.info("Getting emojis from GPT-4-o-mini...")
            emojis = self.get_emojis_for_text(text)
            logger.info(f"Got emojis: {emojis}")

            # Split the text into sentences using a simple regex.
            logger.info("Splitting text into sentences...")
            sentences = re.split(r'(?<=[.!?])\s+', text.strip())
            if not sentences or sentences == ['']:
                sentences = [text.strip()]
            logger.info(f"Split into {len(sentences)} sentences: {sentences}")

            # Adjust the emoji list to match the number of sentences.
            logger.info("Adjusting emoji list length...")
            if len(emojis) != len(sentences):
                if len(emojis) == 0:
                    emojis = ["❓"] * len(sentences)
                elif len(emojis) == 1:
                    emojis = emojis * len(sentences)
                else:
                    if len(emojis) < len(sentences):
                        emojis += [emojis[-1]] * (len(sentences) - len(emojis))
                    else:
                        emojis = emojis[:len(sentences)]
            logger.info(f"Adjusted emojis: {emojis}")

            # Start displaying emojis concurrently with the audio playback.
            logger.info("Starting emoji display task...")
            display_task = asyncio.create_task(self.display_emojis(emojis, sentences))
            logger.info("Emoji display task created")

            # Wait for both tasks to complete.
            logger.info("Waiting for audio and display tasks to complete...")
            await asyncio.gather(play_audio_task, display_task)
            logger.info("Finished speaking and displaying emojis")
        except Exception as e:
            logger.error(f"Error in speak_and_display: {e}", exc_info=True)


async def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("text", help="Text to speak and display")
    parser.add_argument("--ip", default="10.33.11.231", help="Robot IP address")
    parser.add_argument("--voice", default="JBFqnCBsd6RMkjVDRZzb", help="ElevenLabs voice ID")
    args = parser.parse_args()

    speaker = RobotSpeaker(ip=args.ip)
    try:
        await speaker.connect()
        await speaker.speak_and_display(args.text, args.voice)

        # Keep display on until interrupted.
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Display interrupted by user")
    finally:
        await speaker.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Program terminated by user")