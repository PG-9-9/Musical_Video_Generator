"""Quick test harness for Layer 5 style applier.

Creates a handful of base frames (solid gradients), constructs a fake
semantic_timeline and beat_curve, then runs the style applier and writes
outputs/layer5_preview.mp4 (or .gif fallback).
"""
import os
from PIL import Image
import json

from layer_5 import build_style_timeline, apply_styles_to_frames

OUT_DIR = "outputs"
os.makedirs(OUT_DIR, exist_ok=True)

def make_base_frames(w=480, h=270, frames=48):
    base = []
    for i in range(frames):
        t = i/frames
        r = int(30 + 120 * t)
        g = int(40 + 80 * (1 - t))
        b = int(80 + 40 * t)
        im = Image.new('RGB', (w,h), (r,g,b))
        base.append(im)
    return base


def fake_timeline(duration_sec=2.0):
    return {
        "segments": [
            {"start_sec":0.0, "end_sec":0.6, "emotion":"Calm", "intensity":0.2},
            {"start_sec":0.6, "end_sec":1.2, "emotion":"Energetic", "intensity":0.9},
            {"start_sec":1.2, "end_sec":2.0, "emotion":"Euphoric", "intensity":1.0},
        ]
    }


def fake_beat_curve(frames):
    # simple pulsing curve: low baseline with two peaks
    import math
    out = []
    for i in range(frames):
        t = i/frames
        val = 0.1 + 0.0 * math.sin(t*10)
        if 0.4 < t < 0.55:
            val += 0.9 * (1 - abs((t-0.475)/0.075))
        if 0.75 < t < 0.85:
            val += 0.7 * (1 - abs((t-0.8)/0.05))
        out.append(val)
    return out


def main():
    fps = 24
    duration = 2.0
    frames = int(fps*duration)
    base = make_base_frames(frames=frames)
    timeline = fake_timeline(duration)
    style_tl = build_style_timeline(timeline, fps=fps, duration_sec=duration)
    beat = fake_beat_curve(frames)
    out = os.path.join(OUT_DIR, "layer5_preview.mp4")
    print("Rendering preview to", out)
    out_written = apply_styles_to_frames(base, style_tl, beat, out, fps=fps)
    print("Wrote:", out_written)

if __name__ == '__main__':
    main()
