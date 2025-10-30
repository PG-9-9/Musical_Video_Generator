"""Functions to interpolate style parameters over frames and apply them to images.

This module is intentionally lightweight. It uses PIL for simple color/contrast
adjustments and basic numpy for pixel shifts. For production optical-flow or
motion-blur you can replace the simple primitives with OpenCV or a dedicated
flow implementation.
"""
from typing import List, Dict, Any, Tuple
import math
import os
import json

from PIL import Image, ImageEnhance, ImageFilter
import numpy as np

from .style_profiles import STYLE_PROFILES, get_style_profile


def build_style_timeline(semantic_timeline: Dict[str, Any], fps: int, duration_sec: float) -> List[Dict[str, Any]]:
    """Return a list of per-frame style parameter dicts for `int(fps*duration_sec)` frames.

    semantic_timeline is expected to be a dict with a 'segments' list where each segment
    has at least: start_sec, end_sec, emotion, intensity (0..1), keywords(optional).
    """
    frame_count = max(1, int(round(fps * duration_sec)))
    frames = [None] * frame_count

    segments = semantic_timeline.get("segments", []) if semantic_timeline else []
    if not segments:
        # default single calm segment
        segments = [{"start_sec": 0.0, "end_sec": duration_sec, "emotion": "Calm", "intensity": 0.2}]

    # Build arrays of times and associated style vectors for interpolation
    times = []
    style_vectors = []
    for seg in segments:
        t = seg.get("start_sec", 0.0)
        times.append(t)
        profile = get_style_profile(seg.get("emotion", "Calm"))
        # style vector: palette color (rgb tuple of first color), contrast, motion_blur, intensity
        rgb = _hex_to_rgb(profile["palette"][0])
        contrast = float(profile.get("contrast", 1.0))
        motion_blur = float(profile.get("motion_blur", 0.3))
        intensity = float(seg.get("intensity", 0.5))
        style_vectors.append((rgb, contrast, motion_blur, intensity))

    # ensure final time equals duration_sec (append last segment end)
    last_end = segments[-1].get("end_sec", duration_sec)
    if last_end < duration_sec:
        times.append(duration_sec)
        style_vectors.append(style_vectors[-1])

    # For each frame, find interpolation between nearest times
    for i in range(frame_count):
        t = (i / fps)
        # find segment interval
        for k in range(len(times)-1):
            t0, t1 = times[k], times[k+1]
            if t0 <= t <= t1:
                alpha = 0.0 if t1==t0 else ((t - t0) / max(1e-6, (t1 - t0)))
                v0, v1 = style_vectors[k], style_vectors[k+1]
                rgb = tuple(int(_lerp(v0[0][j], v1[0][j], alpha)) for j in range(3))
                contrast = _lerp(v0[1], v1[1], alpha)
                motion_blur = _lerp(v0[2], v1[2], alpha)
                intensity = _lerp(v0[3], v1[3], alpha)
                frames[i] = {
                    "time": t,
                    "palette_color": rgb,
                    "contrast": contrast,
                    "motion_blur": motion_blur,
                    "intensity": intensity,
                }
                break
        else:
            # t beyond last defined; use last vector
            v = style_vectors[-1]
            frames[i] = {"time": t, "palette_color": tuple(v[0]), "contrast": v[1], "motion_blur": v[2], "intensity": v[3]}

    return frames


def apply_styles_to_frames(base_frames: List[Image.Image], style_timeline: List[Dict[str, Any]], beat_curve: List[float], out_path: str, fps: int=24):
    """Apply per-frame style to a list of PIL Image frames and write a preview output.

    - base_frames: list of PIL Images (mode RGB)
    - style_timeline: per-frame style dicts from build_style_timeline
    - beat_curve: list of floats length == frame_count or shorter; values modulate bloom/contrast
    - out_path: output path for MP4 or GIF
    """
    frame_count = len(base_frames)
    styled = []
    for i, img in enumerate(base_frames):
        params = style_timeline[min(i, len(style_timeline)-1)]
        img2 = _apply_color_grade(img, params)
        # add texture: simple vignette or grain
        img2 = _apply_texture(img2, params.get("intensity", 0.5), params)
        # energy modulation
        energy = beat_curve[i] if (beat_curve and i < len(beat_curve)) else 0.0
        img2 = _apply_energy_bloom(img2, energy, params)
        styled.append(img2)

    # optional motion refinement (simple micro drift using beat curve)
    styled = simple_motion_refinement(styled, beat_curve)

    # write output using moviepy if available, else animated GIF via PIL
    # Attempt to write MP4 using moviepy. If it fails, print full traceback and re-raise
    try:
        try:
            from moviepy.video.io.ImageSequenceClip import ImageSequenceClip
        except Exception:
            from moviepy import ImageSequenceClip

        clip = ImageSequenceClip([np.array(im) for im in styled], fps=fps)
        try:
            # preferred: omit custom logger/verbose to avoid compatibility issues
            clip.write_videofile(out_path, codec="libx264", audio=False)
        except Exception:
            import traceback
            print("moviepy.write_videofile raised an exception:")
            traceback.print_exc()
            raise
    except Exception:
        # Do not silently fallback to GIF when MP4 is required — re-raise for diagnosis
        raise

    return out_path


def simple_motion_refinement(frames: List[Image.Image], beat_curve: List[float], max_drift_px: int = 3) -> List[Image.Image]:
    """Add micro camera drift per-frame. Drift magnitude modulated by recent beat energy.

    This is a lightweight replacement for optical-flow-based micro camera drifts.
    """
    out = []
    frame_count = len(frames)
    # compute a smoothed beat envelope
    envelope = _smooth_array(beat_curve or [0.0]*frame_count, window=5, length=frame_count)
    for i, im in enumerate(frames):
        env = envelope[i] if i < len(envelope) else 0.0
        # create a small sinusoidal offset based on time and envelope
        dx = int(round((math.sin(i * 0.1) * 0.5 + 0.5) * max_drift_px * env))
        dy = int(round((math.cos(i * 0.07) * 0.5 + 0.5) * max_drift_px * env))
        out.append(_translate_image(im, dx, dy))
    return out


# ----- helpers -----
def _hex_to_rgb(hexstr: str) -> Tuple[int,int,int]:
    h = hexstr.lstrip('#')
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def _lerp(a, b, alpha):
    return a + (b - a) * alpha


def _apply_color_grade(img: Image.Image, params: Dict[str, Any]) -> Image.Image:
    # adjust contrast
    contrast = params.get("contrast", 1.0)
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(contrast)
    # tint toward palette color by blending
    palette_color = params.get("palette_color", (40, 90, 200))
    tint = Image.new("RGB", img.size, palette_color)
    # blend amount based on intensity
    amount = float(params.get("intensity", 0.5)) * 0.35
    img = Image.blend(img, tint, amount)
    return img


def _apply_texture(img: Image.Image, intensity: float, params: Dict[str, Any]) -> Image.Image:
    tex = params.get("texture", "")
    if tex == "film_grain":
        # apply a small gaussian noise via PIL point transform
        arr = np.array(img).astype(np.float32)
        grain = (np.random.randn(*arr.shape) * (6.0 * intensity)).astype(np.float32)
        arr = np.clip(arr + grain, 0, 255).astype(np.uint8)
        return Image.fromarray(arr)
    elif tex == "vignette":
        w, h = img.size
        vign = Image.new('L', (w, h), 0)
        for y in range(h):
            for x in range(w):
                # distance to center
                dx = (x - w/2) / (w/2)
                dy = (y - h/2) / (h/2)
                d = math.sqrt(dx*dx + dy*dy)
                val = int(255 * (1 - min(1, d**1.5) * intensity))
                vign.putpixel((x,y), val)
        return Image.composite(img, Image.new('RGB', img.size, (0,0,0)), vign)
    else:
        # small blur for other textures
        if intensity > 0.6:
            return img.filter(ImageFilter.GaussianBlur(radius=1.0 * intensity))
        return img


def _apply_energy_bloom(img: Image.Image, energy: float, params: Dict[str, Any]) -> Image.Image:
    # When energy peaks, increase saturation/brightness slightly
    if energy <= 0:
        return img
    # simple bloom: overlay a brightened, blurred copy scaled by energy
    bright = ImageEnhance.Brightness(img).enhance(1.0 + energy*0.6)
    blur = bright.filter(ImageFilter.GaussianBlur(radius=3 * energy))
    return Image.blend(img, blur, 0.25 * energy)


def _translate_image(img: Image.Image, dx: int, dy: int) -> Image.Image:
    if dx == 0 and dy == 0:
        return img
    w, h = img.size
    bg = Image.new('RGB', (w, h), (0,0,0))
    bg.paste(img, (dx, dy))
    return bg


def _smooth_array(arr: List[float], window: int = 3, length: int = None) -> List[float]:
    if length is None:
        length = len(arr)
    out = [0.0] * length
    for i in range(length):
        s = 0.0
        c = 0
        for j in range(max(0, i-window), min(length, i+window+1)):
            val = arr[j] if j < len(arr) else 0.0
            s += val
            c += 1
        out[i] = s / max(1, c)
    return out
