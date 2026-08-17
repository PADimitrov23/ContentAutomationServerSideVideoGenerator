import os
import time
import logging
import requests
import random
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

GOOGGINS_KEYWORD_MAP = {
    "discipline": ["person running alone in rain", "alarm clock dark room", "person training gym alone"],
    "pain": ["hands gripping concrete", "person collapsed floor", "boxing gym heavy bag", "person exhausted workout"],
    "excuses": ["person lying bed covers head", "empty bottle ground", "person staring mirror"],
    "strength": ["person doing pull ups alone", "deadlift heavy weights", "back muscles training", "person lifting barbell"],
    "failure": ["person sitting alone dark room", "rain window", "empty parking lot night", "person head down bench"],
    "heart": ["person running marathon alone", "feet pavement close up", "heartbeat monitor", "person crossing finish line alone"],
    "darkness": ["single light dark tunnel", "person silhouette sunset", "city skyline 4am", "dark clouds storm"],
    "grind": ["alarm clock hand turning off", "person training alone gym", "dawn industrial area", "person sweat workout"],
    "war": ["military boots marching", "dog tags close up", "humvee desert road", "soldier silhouette sunset"],
    "nobody cares": ["empty stadium", "person sitting alone bench rain", "clock ticking", "empty street night"],
    "quit": ["person sitting stairs head hands", "door closing", "person walking away alone"],
    "weak": ["person collapsed ground", "heavy rain alone", "broken glass ground"],
    "tired": ["person running dark road", "feet concrete running", "alarm clock early morning"],
    "fear": ["dark hallway light end", "storm clouds forming", "person standing edge cliff"],
    "growth": ["plant growing timelapse", "sunrise over ocean", "person standing mountain top"],
    "success": ["person standing mountain", "city lights from above", "sunrise skyline"],
}

MOOD_BOOSTER = "dark moody cinematic"

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/arial.ttf",
]


class AssetManager:
    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv("PEXELS_API_KEY")
        if not self.api_key:
            raise RuntimeError("PEXELS_API_KEY is not set. Create a .env file or set the environment variable.")
        self.base_url = "https://api.pexels.com/videos/search"
        self.headers = {"Authorization": self.api_key}
        self.assets_dir = os.path.join(os.getcwd(), "assets", "video_clips")
        os.makedirs(self.assets_dir, exist_ok=True)
        self.max_retries = 3
        self.retry_delays = [2, 4, 8]

    def _enrich_query(self, query):
        query_lower = query.lower().strip()
        for key, alternatives in GOOGGINS_KEYWORD_MAP.items():
            if key in query_lower:
                enriched = random.choice(alternatives)
                logger.info(f"Keyword mapped: '{query}' -> '{enriched}'")
                return enriched
        return query

    def search_video(self, query, duration_min=4, depth=0):
        if depth > 2:
            logger.warning(f"Max search depth reached for: '{query}'")
            return None

        enriched_query = self._enrich_query(query)
        search_query = f"{enriched_query} {MOOD_BOOSTER}"

        for attempt in range(self.max_retries):
            try:
                logger.info(f"Searching Pexels (attempt {attempt + 1}): '{search_query}'")
                params = {
                    "query": search_query,
                    "per_page": 5,
                    "orientation": "portrait",
                    "size": "medium",
                }
                response = requests.get(self.base_url, headers=self.headers, params=params, timeout=10)

                if response.status_code == 429:
                    delay = self.retry_delays[min(attempt, len(self.retry_delays) - 1)]
                    logger.warning(f"Rate limited. Waiting {delay}s...")
                    time.sleep(delay)
                    continue

                if response.status_code != 200:
                    logger.warning(f"Pexels API error: {response.status_code}")
                    return None

                data = response.json()
                videos = data.get("videos", [])

                if not videos:
                    if " " in enriched_query:
                        simple_query = enriched_query.split()[-1]
                        logger.info(f"No results for '{enriched_query}'. Retrying with '{simple_query}'...")
                        return self.search_video(simple_query, duration_min, depth + 1)
                    return None

                valid_videos = [v for v in videos if v.get("duration", 0) >= duration_min]
                if not valid_videos:
                    valid_videos = videos

                selected = random.choice(valid_videos)
                video_files = selected.get("video_files", [])
                video_files.sort(key=lambda x: x.get("width", 0) * x.get("height", 0), reverse=True)

                best_file = video_files[0]
                width = best_file.get("width", 0)
                if width < 1080:
                    for vf in video_files:
                        if vf.get("width", 0) >= 1080:
                            best_file = vf
                            break

                logger.info(f"Selected: {best_file.get('width')}x{best_file.get('height')} from '{search_query}'")
                return best_file.get("link")

            except requests.exceptions.Timeout:
                delay = self.retry_delays[min(attempt, len(self.retry_delays) - 1)]
                logger.warning(f"Timeout on attempt {attempt + 1}. Retrying in {delay}s...")
                time.sleep(delay)
            except Exception as e:
                logger.error(f"Error searching Pexels: {e}")
                return None

        return None

    def download_video(self, url, filename):
        save_path = os.path.join(self.assets_dir, filename)

        if os.path.exists(save_path) and os.path.getsize(save_path) > 0:
            logger.info(f"Using cached: {filename}")
            return save_path

        for attempt in range(self.max_retries):
            try:
                logger.info(f"Downloading: {filename} (attempt {attempt + 1})")
                with requests.get(url, stream=True, timeout=15) as r:
                    r.raise_for_status()
                    with open(save_path, "wb") as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            f.write(chunk)
                logger.info(f"Downloaded: {filename}")
                return save_path
            except Exception as e:
                delay = self.retry_delays[min(attempt, len(self.retry_delays) - 1)]
                logger.warning(f"Download failed for {filename}: {e}. Retrying in {delay}s...")
                time.sleep(delay)
                if os.path.exists(save_path):
                    try:
                        os.remove(save_path)
                    except:
                        pass

        logger.error(f"Failed to download {filename} after {self.max_retries} attempts")
        return None

    def get_videos(self, script_data):
        logger.info("Starting video download...")
        video_pairs = []

        for scene in script_data:
            scene_id = scene["id"]
            query_a = scene.get("visual_1", "person running alone")
            query_b = scene.get("visual_2", "city skyline dark")

            url_a = self.search_video(query_a)
            path_a = self.download_video(url_a, f"scene_{scene_id}_a.mp4") if url_a else None

            url_b = self.search_video(query_b)
            path_b = self.download_video(url_b, f"scene_{scene_id}_b.mp4") if url_b else None

            if not path_a and path_b:
                path_a = path_b
                logger.warning(f"Scene {scene_id}: Clip A missing, using Clip B for both.")
            if not path_b and path_a:
                path_b = path_a
                logger.warning(f"Scene {scene_id}: Clip B missing, using Clip A for both.")

            if path_a and path_b:
                video_pairs.append((path_a, path_b))
                logger.info(f"Scene {scene_id}: Ready (A + B)")
            else:
                logger.error(f"Scene {scene_id}: No videos found")
                video_pairs.append(None)

        return video_pairs


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    manager = AssetManager()
    test_script = [
        {"id": 1, "visual_1": "discipline", "visual_2": "pain"},
    ]
    results = manager.get_videos(test_script)
    logger.info(f"Assets: {results}")
