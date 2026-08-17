import os
import asyncio
import logging
import edge_tts
from mutagen.mp3 import MP3

logger = logging.getLogger(__name__)


class AudioEngine:
    def __init__(self, voice="en-US-GuyNeural"):
        self.voice = voice
        self.output_dir = os.path.join(os.getcwd(), "assets", "audio_clips")
        os.makedirs(self.output_dir, exist_ok=True)

    async def generate_audio(self, text, output_filename, retries=3):
        output_path = os.path.join(self.output_dir, output_filename)

        for attempt in range(retries):
            try:
                communicate = edge_tts.Communicate(text, self.voice, rate="+15%")
                await communicate.save(output_path)
                return output_path
            except Exception as e:
                delay = 2 * (attempt + 1)
                logger.warning(f"Audio error (attempt {attempt + 1}/{retries}): {e}. Retrying in {delay}s...")
                if attempt < retries - 1:
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Failed to generate audio after {retries} attempts.")
                    raise e

    def get_audio_duration(self, file_path):
        try:
            audio = MP3(file_path)
            return audio.info.length
        except Exception as e:
            logger.error(f"Error reading audio length: {e}")
            return 0.0

    async def process_script(self, script_data):
        logger.info(f"Generating audio for {len(script_data)} scenes...")

        for scene in script_data:
            scene_id = scene["id"]
            text = scene["text"]
            filename = f"voice_{scene_id}.mp3"

            try:
                file_path = await self.generate_audio(text, filename)
                duration = self.get_audio_duration(file_path)
                scene["audio_path"] = file_path
                scene["duration"] = duration
                logger.info(f"Scene {scene_id}: {duration:.2f}s")
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Skipping scene {scene_id}: {e}")
                continue

        return script_data
