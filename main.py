import asyncio
import json
import os
import shutil
import sys
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from modules.asset_manager import AssetManager
from modules.audio import AudioEngine
from modules.composer import Composer

app = FastAPI(title="YouTube Shorts Generator")

def clean_cache():
    folders_to_clean = [
        os.path.join(os.getcwd(), "assets", "audio_clips"),
        os.path.join(os.getcwd(), "assets", "video_clips"),
        os.path.join(os.getcwd(), "assets", "temp")
    ]
    for folder in folders_to_clean:
        if not os.path.exists(folder):
            continue
        if "assets" not in folder:
            continue
        for filename in os.listdir(folder):
            file_path = os.path.join(folder, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception:
                pass

async def generate_video(script):
    print(f"Processing {len(script)} scenes...")
    audio_engine = AudioEngine()
    script = await audio_engine.process_script(script)
    asset_manager = AssetManager()
    assets_map = asset_manager.get_videos(script)
    composer = Composer()
    final_scene_paths = composer.render_all_scenes(script, assets_map)
    if not final_scene_paths:
        return None
    output_path = composer.concatenate_with_transitions(final_scene_paths)
    clean_cache()
    return output_path

@app.post("/generate")
async def generate(request: Request):
    body = await request.json()
    if isinstance(body, list):
        script = body
    elif isinstance(body, dict):
        script = body.get("script", body.get("scenes", body.get("output")))
        if script is None:
            return {"status": "error", "message": "No script array found in request body"}
    else:
        return {"status": "error", "message": "Invalid request body"}
    output_path = await generate_video(script)
    if output_path:
        return FileResponse(output_path, media_type="video/mp4", filename="final_short.mp4")
    return {"status": "error", "message": "Video generation failed"}

async def main():
    if len(sys.argv) >= 2:
        if sys.argv[1] == "server":
            port = int(sys.argv[2]) if len(sys.argv) > 2 else 8000
            print(f"Starting server on port {port}...")
            config = uvicorn.Config(app, host="0.0.0.0", port=port)
            server = uvicorn.Server(config)
            await server.serve()
            return
        if sys.argv[1] == "-":
            script = json.loads(sys.stdin.read())
        else:
            with open(sys.argv[1], "r") as f:
                script = json.load(f)
        output_path = await generate_video(script)
        if output_path:
            print(f"\nOUTPUT_PATH:{output_path}")
        else:
            print("Failed to generate video.")
            sys.exit(1)
    else:
        print("Usage:")
        print("  python main.py server [port]     Start HTTP server")
        print("  python main.py <script.json>     Generate from file")
        print("  cat script.json | python main.py -   Generate from stdin")

if __name__ == "__main__":
    asyncio.run(main())
