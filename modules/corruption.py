import json
import os
import shutil
import subprocess

STATE_FILE = os.path.join(os.getcwd(), "assets", "corruption.json")

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "C:/Windows/Fonts/arial.ttf",
]

CORRUPTION_TEXT = {
    5: "CALIBRATING",
    6: "SIGNAL LOST",
    7: "DO NOT LOOK",
    8: "IT KNOWS YOU",
    9: "I AM STILL HERE",
    10: "THERE IS NO MIRROR",
    11: "YOU ARE BEING MANIFESTED",
}


def load_state():
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {"level": 0}


def get_corruption_level():
    return load_state().get("level", 0)


def increment_corruption():
    state = load_state()
    state["level"] = state.get("level", 0) + 1
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)
    return state["level"]


def _font_path():
    for p in FONT_CANDIDATES:
        if os.path.exists(p):
            return p
    return None


def video_filters(level):
    f = []

    grain = {1: 4, 2: 6, 3: 8, 4: 11, 5: 14, 6: 18, 7: 22, 8: 26}.get(level, 30)
    if level >= 1:
        f.append(f"noise=alls={grain}:allf=t")

    if level >= 1:
        f.append("eq=saturation=0.9")
    if level >= 2:
        f.append("eq=saturation=0.78:brightness=-0.02:contrast=1.05")
    if level >= 3:
        f.append("eq=saturation=0.62:brightness=-0.03:contrast=1.08")

    if level >= 2:
        f.append("vignette=angle=PI/4")
    if level >= 6:
        f.append("vignette=angle=PI/3.2")

    if level >= 3:
        f.append("rgbashift=rh=2:bh=-2")
    if level >= 5:
        f.append("rgbashift=rh=4:bh=-3")
    if level >= 8:
        f.append("rgbashift=rh=6:bh=-5")

    if level >= 3:
        f.append("curves=master='0/0.03 1/0.94'")

    if level >= 4:
        f.append("hue=h=5")
    if level >= 7:
        f.append("hue=h=10")

    if level >= 4:
        f.append("eq=brightness='0.02*sin(2*PI*t*0.4)'")
    if level >= 8:
        f.append("eq=brightness='0.03*sin(2*PI*t*0.9)'")

    if level >= 7:
        f.append("colorbalance=bm=0.08")
    if level >= 9:
        f.append("colorbalance=bs=0.15")

    if level >= 6:
        f.append("drawgrid=w=iw:h=3:t=1:c=black@0.22")
    if level >= 9:
        f.append("drawgrid=w=iw:h=2:t=1:c=black@0.3")

    if level >= 7:
        f.append("crop=iw-24:ih-24:x='12+3*sin(t*50)':y='12+3*cos(t*43)'")
        f.append("scale=1080:1920")

    font = _font_path()
    if font and level in CORRUPTION_TEXT:
        text = CORRUPTION_TEXT[level]
        enable = {
            5: "lt(mod(t,6),0.15)",
            6: "lt(mod(t,7),0.2)",
            7: "lt(mod(t,9),0.2)",
            8: "lt(mod(t,11),0.25)",
            9: "lt(mod(t,13),0.25)",
        }.get(level, "lt(mod(t,13),0.3)")
        f.append(
            f"drawtext=fontfile='{font}':text='{text}':fontsize=60:"
            f"fontcolor='white@0.85':box=1:boxcolor='black@0.6':boxborderw=14:"
            f"x=(w-text_w)/2:y=(h-th)/2:enable='{enable}'"
        )

    return f


def audio_filters(level):
    f = []
    if level >= 1:
        f.append("lowpass=f=9000")
    if level >= 3:
        f.append("lowpass=f=7000")
    if level >= 5:
        f.append("lowpass=f=5000")
    if level >= 7:
        f.append("lowpass=f=4000")

    if level >= 3:
        f.append("aecho=0.7:0.4:60|110:0.3|0.2")
    if level >= 5:
        f.append("aecho=0.6:0.4:80|150:0.35|0.25")

    if level >= 7:
        f.append("vibrato=f=3.5:d=0.6")
    if level >= 9:
        f.append("tremolo=f=2:d=0.6")

    if level >= 6:
        f.append("asetrate=0.96*44100")
        f.append("aresample=44100")
    if level >= 9:
        f.append("asetrate=0.92*44100")
        f.append("aresample=44100")

    return f


def corrupt_video(input_path, level, work_dir):
    if level < 1:
        return input_path

    vf = ",".join(video_filters(level))
    af = ",".join(audio_filters(level))

    os.makedirs(work_dir, exist_ok=True)
    output_path = os.path.join(work_dir, f"corrupted_{level}.mp4")

    cmd = ["ffmpeg", "-y", "-i", input_path]
    if vf:
        cmd += ["-vf", vf]
    if af:
        cmd += ["-af", af]
    cmd += [
        "-c:v", "libx264",
        "-c:a", "aac",
        "-pix_fmt", "yuv420p",
        "-preset", "medium",
        "-movflags", "faststart",
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg corruption pass failed: {result.stderr[-500:]}")

    os.replace(output_path, input_path)
    return input_path
