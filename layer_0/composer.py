import os
from typing import List, Tuple

from moviepy.editor import VideoFileClip, AudioFileClip, ImageClip, CompositeVideoClip
from PIL import Image, ImageDraw, ImageFont
import numpy as np


def make_subtitle_clips(lyrics: str, duration_sec: int = 10, fontsize: int = 48, color: str = "white", video_width: int = 1280) -> List[ImageClip]:
    """Create simple subtitle clips using Pillow -> ImageClip so ImageMagick is not required.

    This renders each word to a transparent PNG and returns ImageClips positioned at bottom center.
    """
    words = lyrics.split()
    if not words:
        return []
    per_word = duration_sec / len(words)
    clips = []
    t = 0.0
    for w in words:
        # load a bold font if available, otherwise fallback to default
        try:
            # Windows common name for Arial Bold
            font = ImageFont.truetype("arialbd.ttf", fontsize)
        except Exception:
            try:
                font = ImageFont.truetype("Arial.ttf", fontsize)
            except Exception:
                font = ImageFont.load_default()

        # measure text size using font (getsize is broadly supported)
        try:
            w_w, w_h = font.getsize(w)
        except Exception:
            dummy = Image.new("RGBA", (1, 1))
            draw = ImageDraw.Draw(dummy)
            # fallback (older/newer Pillow versions)
            bbox = draw.textbbox((0, 0), w, font=font)
            w_w = bbox[2] - bbox[0]
            w_h = bbox[3] - bbox[1]

        img_w = video_width
        img_h = int(w_h * 1.6)  # add some padding

        img = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Draw text centered
        x = (img_w - w_w) // 2
        y = (img_h - w_h) // 2
        draw.text((x, y), w, font=font, fill=color)

        arr = np.array(img)
        img_clip = ImageClip(arr).set_position(("center", "bottom")).set_start(t).set_duration(per_word)
        clips.append(img_clip)
        t += per_word
    return clips


def compose_video(video_path: str, audio_path: str, lyrics: str, output_path: str = "outputs/final.mp4") -> str:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    video = VideoFileClip(video_path).subclip(0, 10)
    audio = AudioFileClip(audio_path).subclip(0, 10)

    # give subtitles the video width so rendered text centers correctly
    subtitles = make_subtitle_clips(lyrics, duration_sec=10, video_width=video.w)
    layers = [video] + subtitles
    final = CompositeVideoClip(layers)
    final = final.set_audio(audio)
    final.write_videofile(output_path, fps=24)
    return output_path
