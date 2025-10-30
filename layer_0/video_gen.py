import os
from moviepy.editor import ColorClip, ImageClip, concatenate_videoclips


def generate_placeholder_video(prompt: str, duration_sec: int = 10, output_path: str = "outputs/video.mp4") -> str:
    """
    Generate a simple animated video (color -> color) so pipeline is runnable.
    For real usage, replace with Pika/Runway/Stable-Video-Diffusion API call.
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    clip1 = ColorClip(size=(720, 1280), color=(0, 0, 0), duration=duration_sec/2)
    clip2 = ColorClip(size=(720, 1280), color=(60, 0, 120), duration=duration_sec/2)

    final = concatenate_videoclips([clip1, clip2], method="compose")
    final.write_videofile(output_path, fps=24)
    return output_path
