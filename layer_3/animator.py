"""Layer 3 animator: produce animated.mp4 from semantic timeline + beat analysis.

Writes an events JSON summary for debugging.
"""
import json
import os
from typing import Dict, Any, List, Callable

import numpy as np
from moviepy import VideoClip, concatenate_videoclips

from layer_3.visuals import effects


def _hex_to_rgb01(hexstr: str):
    if not hexstr or not isinstance(hexstr, str):
        return np.array([0.5, 0.5, 0.5], dtype=np.float32)
    s = hexstr.strip().lstrip('#')
    if len(s) == 3:
        s = ''.join([c*2 for c in s])
    try:
        r = int(s[0:2], 16) / 255.0
        g = int(s[2:4], 16) / 255.0
        b = int(s[4:6], 16) / 255.0
        return np.array([r, g, b], dtype=np.float32)
    except Exception:
        return np.array([0.5, 0.5, 0.5], dtype=np.float32)


EMOTION_TO_EFFECT: Dict[str, Callable[[Dict[str, Any], float, int, int], np.ndarray]] = {
    "calm": effects.gradient_wave,
    "sad": effects.soft_particle_drift,
    "hopeful": effects.expanding_ring_pulse,
    "energetic": effects.beat_flash,
    "euphoric": effects.particle_explosion,
    "romantic": effects.smooth_orbit,
    "dark": effects.noise_fog,
    "neutral": effects.gradient_wave,
}


def render_segment_clip(seg: Dict[str, Any], beats: List[float], energy_curve: List[float], fps: int, resolution=(1280, 720)):
    w, h = resolution
    start = float(seg.get("start_sec", 0.0))
    end = float(seg.get("end_sec", start + 1.0))
    duration = max(0.01, end - start)
    emotion = seg.get("emotion", "neutral")
    intensity = float(seg.get("intensity", 0.5))
    color = seg.get("color_hex")
    visual_hint = seg.get("visual_hint", "")

    effect_fn = EMOTION_TO_EFFECT.get(emotion, effects.gradient_wave)
    state = {
        # allow upstream override via '_color_rgb_override'
        "color_rgb": seg.get('_color_rgb_override') if seg.get('_color_rgb_override') is not None else _hex_to_rgb01(color),
        "energy": intensity,
        "beats": [b - start for b in beats if b >= start and b < end],
    }

    # make_frame uses local t starting at 0
    def make_frame(t):
        frame = effect_fn(state, t, w, h)
        # apply a global vignette based on energy
        vign = np.linspace(1.0, 0.6, h)[:, None]
        frame = frame * vign[:, :, None]
        frame = np.clip(frame * 255.0, 0, 255).astype('uint8')
        return frame

    # use with_fps on newer moviepy
    clip = VideoClip(make_frame, duration=duration).with_fps(fps)
    return clip


def generate_animation(semantic_path: str = "outputs/semantic_timeline.json", beat_path: str = "outputs/beat_analysis.json", output_path: str = "outputs/animated.mp4", events_path: str = "outputs/layer3_events.json", config: Dict[str, Any] = None):
    if config is None:
        config = {"resolution": [1280, 720], "fps": 24, "style": "default"}

    with open(semantic_path, 'r', encoding='utf-8') as f:
        sem = json.load(f)
    with open(beat_path, 'r', encoding='utf-8') as f:
        beat = json.load(f)

    segments = sem.get('segments', [])
    beats = beat.get('beat_times', []) or []
    energy_curve = beat.get('energy_curve', []) or []

    fps = int(config.get('fps', 24))
    w, h = tuple(config.get('resolution', [1280, 720]))

    clips = []
    events = []

    # synthwave palette and per-emotion tuning
    synthwave_palette = {
        "neon_pink": _hex_to_rgb01("#FF6FA3"),
        "electric_blue": _hex_to_rgb01("#6CC0FF"),
        "magenta": _hex_to_rgb01("#9B5DE5"),
        "orange": _hex_to_rgb01("#FF7F11"),
        "cyan": _hex_to_rgb01("#00FFFF"),
        "navy": _hex_to_rgb01("#0B0B0B"),
    }

    emotion_color_override = {
        "calm": synthwave_palette["electric_blue"],
        "sad": synthwave_palette["navy"],
        "hopeful": synthwave_palette["neon_pink"],
        "energetic": synthwave_palette["orange"],
        "euphoric": synthwave_palette["magenta"],
        "romantic": synthwave_palette["neon_pink"],
        "dark": synthwave_palette["navy"],
        "neutral": synthwave_palette["cyan"],
    }

    # high-level style override for palettes
    style_override = (config.get('style') or '').lower()
    if style_override == 'synthwave':
        # already using synthwave defaults
        pass
    elif style_override == 'lo-fi' or style_override == 'lofi':
        # muted, warm tones
        emotion_color_override = {
            "calm": _hex_to_rgb01("#6B7280"),
            "sad": _hex_to_rgb01("#4B5563"),
            "hopeful": _hex_to_rgb01("#D6A65A"),
            "energetic": _hex_to_rgb01("#C2410C"),
            "euphoric": _hex_to_rgb01("#9F7AEA"),
            "romantic": _hex_to_rgb01("#FCA5A5"),
            "dark": _hex_to_rgb01("#111827"),
            "neutral": _hex_to_rgb01("#9CA3AF"),
        }
    elif style_override == 'acoustic':
        emotion_color_override = {
            "calm": _hex_to_rgb01("#7C3E19"),
            "sad": _hex_to_rgb01("#5B5B5B"),
            "hopeful": _hex_to_rgb01("#F59E0B"),
            "energetic": _hex_to_rgb01("#D97706"),
            "euphoric": _hex_to_rgb01("#F472B6"),
            "romantic": _hex_to_rgb01("#FB7185"),
            "dark": _hex_to_rgb01("#2D2D2D"),
            "neutral": _hex_to_rgb01("#D1BFA7"),
        }
    elif style_override == 'cinematic':
        emotion_color_override = {
            "calm": _hex_to_rgb01("#1F2937"),
            "sad": _hex_to_rgb01("#0F172A"),
            "hopeful": _hex_to_rgb01("#F59E0B"),
            "energetic": _hex_to_rgb01("#EF4444"),
            "euphoric": _hex_to_rgb01("#7C3AED"),
            "romantic": _hex_to_rgb01("#B91C1C"),
            "dark": _hex_to_rgb01("#000000"),
            "neutral": _hex_to_rgb01("#4B5563"),
        }

    # per-segment energy if present
    per_segment_energy = beat.get("per_segment_energy") or []

    for idx, seg in enumerate(segments):
    # tune state for segment
        seg_energy = 1.0
        if idx < len(per_segment_energy):
            try:
                seg_energy = float(per_segment_energy[idx])
            except Exception:
                seg_energy = 1.0

        # inject color override when color_hex missing
        emo_key = (seg.get('emotion') or 'neutral').lower()
        if not seg.get('color_hex') and emotion_color_override.get(emo_key) is not None:
            seg['_color_rgb_override'] = emotion_color_override.get(emo_key)

        clip = render_segment_clip(seg, beats, energy_curve, fps, resolution=(w, h))
    # attach metadata for debugging/events
        clip._layer3_meta = {
            "emotion": seg.get('emotion'),
            "start": seg.get('start_sec'),
            "end": seg.get('end_sec'),
            "energy": seg_energy,
        }
        clips.append(clip)
        events.append({"segment": seg.get('emotion'), "start": seg.get('start_sec'), "end": seg.get('end_sec')})

    # compute per-frame events (beats/triggers) for debugging
    fps_int = fps
    frame_events = []
    beat_tolerance = 0.045
    total_duration = sem.get('duration_sec', sum([c.duration for c in clips]) if clips else 0)
    n_frames = int(total_duration * fps_int)
    for fidx in range(n_frames):
        t = fidx / fps_int
        # which segment
        seg_idx = None
        for i, s in enumerate(segments):
            st = float(s.get('start_sec', 0.0))
            en = float(s.get('end_sec', st + 1.0))
            if t >= st and t < en:
                seg_idx = i
                break
        nearby_beats = [b for b in beats if abs(b - t) <= beat_tolerance]
        if nearby_beats:
            frame_events.append({"time": round(t, 4), "type": "beat", "segment": seg_idx, "beats": nearby_beats})

    # apply crossfade transitions
    crossfade_sec = float(config.get('crossfade_sec', 0.5))
    # apply crossfade if supported, else concatenate
    if crossfade_sec > 0 and len(clips) > 1:
        # try to use crossfadein where available
        try:
            adjusted_clips = [clips[0]] + [c.crossfadein(crossfade_sec) for c in clips[1:]]
        except Exception:
            adjusted_clips = clips
    else:
        adjusted_clips = clips

    final = concatenate_videoclips(adjusted_clips, method="compose")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    final.write_videofile(output_path, fps=fps)

    # write events (segments + per-frame events summary)
    os.makedirs(os.path.dirname(events_path), exist_ok=True)
    with open(events_path, 'w', encoding='utf-8') as f:
        json.dump({"segments": events, "beat_count": len(beats), "frame_events": frame_events}, f, indent=2)

    return {"animated_path": output_path, "events_path": events_path}
