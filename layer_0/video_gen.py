import os
from typing import List

try:
    # prefer the concrete ImageSequenceClip import path which exists in this env
    from moviepy.video.io.ImageSequenceClip import ImageSequenceClip
except Exception:
    # final fallback to moviepy.editor if available
    try:
        from moviepy.editor import ImageSequenceClip
    except Exception:
        ImageSequenceClip = None

from PIL import Image
import numpy as np


def generate_placeholder_video(prompt: str, duration_sec: int = 10, output_path: str = "outputs/video.mp4") -> str:
    """Generate a simple animated video (gradient frames) so pipeline is runnable.

    Uses moviepy ImageSequenceClip to write MP4. If moviepy is not available,
    writes an animated GIF instead.
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    fps = 24
    frames = []
    w, h = (720, 1280)
    n = int(fps * duration_sec)
    for i in range(n):
        t = i / max(1, n)
        r = int(20 + 200 * t) % 256
        g = int(10 + 120 * (1 - t)) % 256
        b = int(60 + 80 * t) % 256
        arr = np.zeros((w, h, 3), dtype=np.uint8)
        arr[..., 0] = r
        arr[..., 1] = g
        arr[..., 2] = b
        # transpose to HxW ordering for PIL
        img = Image.fromarray(arr.transpose(1, 0, 2))
        frames.append(img)

    if ImageSequenceClip is not None:
        clip = ImageSequenceClip([np.array(im) for im in frames], fps=fps)
        clip.write_videofile(output_path, fps=fps, codec='libx264', audio=False)
        return output_path
    else:
        gif_path = output_path.rsplit('.', 1)[0] + '.gif'
        frames[0].save(gif_path, save_all=True, append_images=frames[1:], duration=int(1000/fps), loop=0)
        return gif_path
