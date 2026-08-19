import os
import tempfile
import logging
import ffmpeg

logger = logging.getLogger(__name__)

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/arial.ttf",
]


def _find_font():
    for p in FONT_CANDIDATES:
        if os.path.exists(p):
            return p
    return None


class Composer:
    def __init__(self):
        self.temp_dir = os.path.join(os.getcwd(), "assets", "temp")
        self.final_dir = os.path.join(os.getcwd(), "assets", "final")
        self.font_path = _find_font()
        os.makedirs(self.temp_dir, exist_ok=True)
        os.makedirs(self.final_dir, exist_ok=True)
        self._textfiles = []

    def get_duration(self, filepath):
        try:
            probe = ffmpeg.probe(filepath)
            return float(probe["format"]["duration"])
        except:
            return 0.0

    def add_captions(self, video_stream, text, font_size=42):
        if not self.font_path or not text:
            return video_stream

        lines = []
        words = text.split()
        current = ""
        for word in words:
            if len(current + " " + word) > 35:
                lines.append(current)
                current = word
            else:
                current = (current + " " + word).strip()
        if current:
            lines.append(current)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("\n".join(lines[:2]))
            textfile = f.name
        self._textfiles.append(textfile)

        return video_stream.filter(
            "drawtext",
            textfile=textfile,
            fontfile=self.font_path,
            fontsize=font_size,
            fontcolor="white",
            borderw=3,
            bordercolor="black",
            x="(w-text_w)/2",
            y="h-text_h-100",
            enable="between(t,0,9999)",
        )

    def add_color_grade(self, video_stream):
        video_stream = video_stream.filter(
            "eq",
            saturation=0.75,
            contrast=1.15,
            brightness=-0.02,
        )
        video_stream = video_stream.filter("curves", master="0/0.02 0.5/0.48 1/0.95")
        return video_stream

    def process_scene(self, scene, video_pair):
        scene_id = scene["id"]
        audio_path = scene["audio_path"]
        total_duration = scene["duration"]
        output_path = os.path.join(self.temp_dir, f"scene_{scene_id}.mp4")
        scene_text = scene.get("text", "")

        try:
            input_audio = ffmpeg.input(audio_path)
            path_a, path_b = video_pair
            duration_a = total_duration / 2
            duration_b = (total_duration / 2) + 0.5

            stream_a = (
                ffmpeg.input(path_a, stream_loop=-1)
                .trim(duration=duration_a)
                .setpts("PTS-STARTPTS")
                .filter("scale", 1080, 1920)
                .filter("crop", 1080, 1920)
                .filter("fps", fps=30, round="up")
            )

            stream_b = (
                ffmpeg.input(path_b, stream_loop=-1)
                .trim(duration=duration_b)
                .setpts("PTS-STARTPTS")
                .filter("scale", 1080, 1920)
                .filter("crop", 1080, 1920)
                .filter("fps", fps=30, round="up")
            )

            video_stream = ffmpeg.concat(stream_a, stream_b, v=1, a=0)

            video_stream = self.add_color_grade(video_stream)
            video_stream = self.add_captions(video_stream, scene_text)

            runner = ffmpeg.output(
                video_stream,
                input_audio,
                output_path,
                vcodec="libx264",
                acodec="aac",
                pix_fmt="yuv420p",
                shortest=None,
            )
            runner.run(overwrite_output=True, quiet=True)
            logger.info(f"Scene {scene_id} rendered: {output_path}")
            return output_path

        except ffmpeg.Error as e:
            logger.error(f"Render failed scene {scene_id}: {e.stderr.decode('utf8') if e.stderr else str(e)}")
            return None

    def render_all_scenes(self, script_data, video_pairs):
        rendered_paths = []
        for i, scene in enumerate(script_data):
            current_pair = video_pairs[i]
            if current_pair is None:
                logger.warning(f"Skipping scene {scene['id']}: no video pair")
                continue
            output_path = self.process_scene(scene, current_pair)
            if output_path:
                rendered_paths.append(output_path)
        return rendered_paths

    def concatenate_with_transitions(self, video_paths, output_filename="final_short.mp4"):
        logger.info("Stitching final video...")
        output_path = os.path.join(self.final_dir, output_filename)

        if os.path.exists(output_path):
            try:
                os.remove(output_path)
            except:
                pass

        if not video_paths:
            return None

        input1 = ffmpeg.input(video_paths[0])
        v_stream = input1.video
        a_stream = input1.audio
        current_dur = self.get_duration(video_paths[0])

        for i in range(1, len(video_paths)):
            next_clip = ffmpeg.input(video_paths[i])
            next_dur = self.get_duration(video_paths[i])

            if i == len(video_paths) - 1:
                trans_dur = 0.08
            else:
                trans_dur = 0.0

            next_v = next_clip.video.filter("settb", "AVTB")
            next_a = next_clip.audio.filter("settb", "AVTB")

            if trans_dur > 0:
                offset = max(0, current_dur - trans_dur)
                v_stream = ffmpeg.filter(
                    [v_stream, next_v],
                    "xfade",
                    transition="fade",
                    duration=trans_dur,
                    offset=offset,
                )
                a_stream = ffmpeg.filter(
                    [a_stream, next_a],
                    "acrossfade",
                    d=trans_dur,
                )
                current_dur = (current_dur + next_dur) - trans_dur
            else:
                v_stream = ffmpeg.concat(v_stream, next_v, v=1, a=0)
                a_stream = ffmpeg.concat(a_stream, next_a, v=0, a=1)
                current_dur = current_dur + next_dur

        try:
            runner = ffmpeg.output(
                v_stream,
                a_stream,
                output_path,
                vcodec="libx264",
                acodec="aac",
                pix_fmt="yuv420p",
                movflags="faststart",
                preset="medium",
            )
            runner.run(overwrite_output=True, quiet=False)
            logger.info(f"Final video saved: {output_path}")
            return output_path

        except ffmpeg.Error as e:
            error_log = e.stderr.decode("utf8") if e.stderr else str(e)
            logger.error(f"Stitching error: {error_log}")
            return None
        finally:
            for f in self._textfiles:
                try:
                    os.unlink(f)
                except:
                    pass
            self._textfiles = []
