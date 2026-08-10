import asyncio
import json
import os
import shutil
import sys
import uvicorn
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse

LOG_FILE = os.path.join(os.getcwd(), "assets", "history.json")

def append_log(entry):
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w") as f:
            json.dump([], f)
    try:
        with open(LOG_FILE, "r") as f:
            logs = json.load(f)
    except:
        logs = []
    logs.insert(0, entry)
    with open(LOG_FILE, "w") as f:
        json.dump(logs, f, indent=2)
from modules.asset_manager import AssetManager
from modules.audio import AudioEngine
from modules.composer import Composer
from modules.notify import send_alert
from modules.youtube_uploader import TokenExpiredError, get_token_expiry, is_token_valid
from datetime import timedelta

app = FastAPI(title="YouTube Shorts Generator")

def check_token_warning():
    expiry = get_token_expiry()
    if expiry is None:
        return
    now = datetime.now(expiry.tzinfo)
    remaining = expiry - now
    if remaining < timedelta(hours=48):
        msg = f"YouTube token expires in {int(remaining.total_seconds() // 3600)}h. Re-auth: python setup_youtube.py"
        print(f"⚠️ {msg}")
        send_alert("token_expiring_soon", msg)

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

@app.get("/logs", response_class=HTMLResponse)
async def view_logs():
    if not os.path.exists(LOG_FILE):
        return "<h2>No history yet</h2>"
    try:
        with open(LOG_FILE, "r") as f:
            logs = json.load(f)
    except:
        return "<h2>No history yet</h2>"
    rows = "".join(
        f"<tr><td>{l['date'][:19]}</td><td>{l['title']}</td><td><a href='{l['url']}' target='_blank'>{l['url']}</a></td><td>{l['status']}</td></tr>"
        for l in logs if l['url']
    )
    return f"""<!DOCTYPE html>
<html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Video History</title>
<style>body{{font-family:sans-serif;padding:20px;background:#111;color:#fff}}table{{width:100%;border-collapse:collapse}}
th,td{{padding:10px;text-align:left;border-bottom:1px solid #333}}th{{color:#888}}
a{{color:#4fc3f7}}tr:hover{{background:#222}}</style></head>
<body><h2>Video History</h2><table><tr><th>Date</th><th>Title</th><th>URL</th><th>Status</th></tr>{rows}</table></body></html>"""

@app.get("/token-status")
async def token_status():
    expiry = get_token_expiry()
    if expiry is None:
        return {"status": "not_configured", "message": "No token yet. Run: python setup_youtube.py"}
    now = datetime.now(expiry.tzinfo)
    valid = is_token_valid()
    remaining_hours = int((expiry - now).total_seconds() // 3600)
    return {
        "status": "valid" if valid else "expired",
        "expires": expiry.isoformat(),
        "valid_for_hours": remaining_hours
    }

@app.post("/debug")
async def debug(request: Request):
    body = await request.json()
    print(f"DEBUG received: {type(body)} -> {str(body)[:500]}")
    return {"received_type": str(type(body)), "body_preview": str(body)[:300]}

@app.post("/generate")
async def generate(request: Request):
    body = await request.json()
    if isinstance(body, list):
        script = body
        title = "YouTube Short"
        upload_to_youtube = True
    elif isinstance(body, dict):
        script = body.get("script", body.get("scenes", body.get("output")))
        title = body.get("title", "YouTube Short")
        upload_to_youtube = body.get("youtube", False)
        if script is None:
            return {"status": "error", "message": "No script array found in request body"}
    else:
        return {"status": "error", "message": "Invalid request body"}

    try:
        output_path = await generate_video(script)
    except Exception as e:
        result = {"status": "error", "message": f"Video generation failed: {e}"}
        append_log({"date": datetime.now().isoformat(), "title": title, "url": "", "status": result["status"]})
        send_alert("video_generation_failed", f"Content automation video generation failed: {e}", title=title)
        return result

    result = {"status": "error", "message": "Video generation failed"}
    if output_path:
        if upload_to_youtube:
            try:
                from modules.youtube_uploader import upload_video
                video_id = upload_video(output_path, title=title)
                result = {"status": "uploaded", "video_id": video_id, "url": f"https://youtu.be/{video_id}", "title": title}
            except TokenExpiredError as e:
                result = {"status": "token_expired", "message": str(e), "title": title}
                send_alert("token_expired", str(e), title=title)
            except Exception as e:
                result = {"status": "upload_failed", "video_path": output_path, "error": str(e), "title": title}
                send_alert("upload_failed", f"Content automation video upload failed: {e}", title=title)
        else:
            return FileResponse(output_path, media_type="video/mp4", filename="final_short.mp4")
    entry = {"date": datetime.now().isoformat(), "title": result.get("title", ""), "url": result.get("url", ""), "status": result.get("status", "")}
    append_log(entry)
    return result

async def main():
    if len(sys.argv) >= 2:
        if sys.argv[1] == "server":
            port = int(sys.argv[2]) if len(sys.argv) > 2 else 8000
            print(f"Starting server on port {port}...")
            check_token_warning()
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
