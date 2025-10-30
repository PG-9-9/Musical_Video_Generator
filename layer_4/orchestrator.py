"""Layer 4 orchestrator: compose animated visuals + audio + subtitles + beat overlays into final.mp4

Inputs:
 - outputs/animated.mp4 (Layer 3)
 - outputs/music.wav (Layer 0)
 - outputs/semantic_timeline.json (Layer 1)
 - outputs/beat_analysis.json (Layer 2)
 - lyrics.txt (optional raw lyrics)

Outputs:
 - outputs/final.mp4
 - outputs/layer4_events.json
"""
import json
import os
from typing import Dict, Any, List

from moviepy.editor import VideoFileClip, AudioFileClip, CompositeVideoClip, ColorClip, ImageClip, VideoClip
import numpy as np
from PIL import Image, ImageDraw, ImageFont
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


def _make_text_image(text: str, width: int, fontsize: int = 36, color: str = 'white'):
    # Create a transparent image with centered text using Pillow
    try:
        font = ImageFont.truetype("arialbd.ttf", fontsize)
    except Exception:
        try:
            font = ImageFont.truetype("Arial.ttf", fontsize)
        except Exception:
            font = ImageFont.load_default()

    # measure text
    dummy = Image.new("RGBA", (10, 10))
    draw = ImageDraw.Draw(dummy)
    try:
        w, h = draw.textsize(text, font=font)
    except Exception:
        bbox = draw.textbbox((0, 0), text, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]

    img_w = width
    img_h = h + 16
    img = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    x = (img_w - w) // 2
    y = (img_h - h) // 2
    draw.text((x, y), text, font=font, fill=color)
    return img


def build_line_timing_from_semantic(semantic: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return list of lines with start and duration: {text, start, duration}.

    For each segment, distribute time evenly across its lines.
    """
    lines_out = []
    for seg in semantic.get('segments', []):
        start = float(seg.get('start_sec', 0.0))
        end = float(seg.get('end_sec', start + 1.0))
        lines = seg.get('lines', []) or []
        if isinstance(lines, str):
            lines = [l for l in lines.splitlines() if l.strip()]
        if not lines:
            continue
        per = (end - start) / max(1, len(lines))
        for i, line in enumerate(lines):
            lines_out.append({"text": line, "start": round(start + i * per, 6), "duration": round(per, 6)})
    return lines_out


def make_line_subtitle_clip(line_text: str, start: float, duration: float, video_w: int, video_h: int, fontsize: int = 36, color: str = 'white', highlight_color: str = '#FFD166') -> VideoClip:
    """Create a VideoClip that renders a subtitle line with karaoke-style highlight.

    The highlight grows proportionally across the duration.
    """
    # precompute text size
    try:
        font = ImageFont.truetype("arialbd.ttf", fontsize)
    except Exception:
        try:
            font = ImageFont.truetype("Arial.ttf", fontsize)
        except Exception:
            font = ImageFont.load_default()

    dummy = Image.new("RGBA", (10, 10))
    draw = ImageDraw.Draw(dummy)
    try:
        text_w, text_h = draw.textsize(line_text, font=font)
    except Exception:
        bbox = draw.textbbox((0, 0), line_text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

    padding_y = 12
    box_h = text_h + padding_y

    def make_frame(t):
        # t is relative to clip start
        img = Image.new("RGBA", (video_w, box_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        # background semi-transparent rounded box
        bg_color = (0, 0, 0, 150)
        draw.rectangle([(0, 0), (video_w, box_h)], fill=bg_color)

        # compute highlight width based on progress
        progress = max(0.0, min(1.0, t / max(1e-6, duration)))
        highlight_w = int(progress * text_w)

        # compute text position
        x = (video_w - text_w) // 2
        y = (box_h - text_h) // 2

        # draw highlight rect behind text portion
        if highlight_w > 0:
            hx0 = x
            hx1 = x + highlight_w
            # parse highlight color
            hc = tuple(int(_hex_to_rgb01(highlight_color)[i] * 255) for i in range(3)) + (200,)
            draw.rectangle([(hx0, y), (hx1, y + text_h)], fill=hc)

        # draw full text in white
        draw.text((x, y), line_text, font=font, fill=color)

        # convert RGBA to RGB array (composite against black) to avoid alpha channel issues
        rgb = img.convert('RGB')
        return np.array(rgb)

    clip = VideoClip(make_frame, duration=duration).set_start(start).set_position(('center', 'bottom'))
    return clip


def make_beat_overlay_clip(beat_time: float, video_w: int, video_h: int, duration: float = 0.9, color_hex: str = '#FFFFFF') -> VideoClip:
    """Return a short VideoClip that renders an expanding ring pulse at the beat time using Layer 3 effect.

    We reuse `effects.expanding_ring_pulse` for a consistent visual style.
    """
    state = {
        "color_rgb": _hex_to_rgb01(color_hex),
        "energy": 1.0,
        "beats": [0.0],
    }

    def make_frame(t):
        # t relative to clip start
        # pass t to effect which will compute rings relative to beats=[0]
        frame = effects.expanding_ring_pulse(state, t, video_w, video_h)
        return (np.clip(frame * 255.0, 0, 255)).astype('uint8')

    clip = VideoClip(make_frame, duration=duration).set_start(max(0.0, beat_time - 0.0)).set_opacity(1.0)
    return clip


def build_word_timing_from_semantic(semantic: Dict[str, Any], lyrics_text: str = None) -> List[Dict[str, Any]]:
    """Generate per-word timings by splitting segment lines and distributing time within segment.
    Returns list of {word, start, duration} covering the whole timeline.
    """
    words_timed = []
    segments = semantic.get('segments', [])
    for seg in segments:
        start = float(seg.get('start_sec', 0.0))
        end = float(seg.get('end_sec', start + 1.0))
        lines = seg.get('lines', [])
        text = ' '.join(lines) if isinstance(lines, list) else str(lines)
        ws = [w for w in text.split() if w.strip()]
        if not ws:
            continue
        per = (end - start) / len(ws)
        for i, w in enumerate(ws):
            words_timed.append({"word": w, "start": round(start + i * per, 6), "duration": round(per, 6)})
    return words_timed


def make_beat_overlays(beats: List[float], video_w: int, video_h: int, energy_curve: List[float], fps: int = 24):
    """Create short ImageClips for beat overlays. Intensity scales with local energy if possible."""
    clips = []
    for b in beats:
        # pick energy as 1.0 default; advanced mapping can sample energy_curve
        intensity = 1.0
        duration = 0.10
        # white flash with alpha proportional to intensity
        arr = np.ones((video_h, video_w, 3), dtype=np.uint8) * 255
        clip = ImageClip(arr).set_start(max(0, float(b) - duration/2)).set_duration(duration).set_opacity(0.12 * intensity)
        clips.append(clip)
    return clips


def compose_final(animated_path: str = "outputs/animated.mp4", music_path: str = "outputs/music.wav", semantic_path: str = "outputs/semantic_timeline.json", beat_path: str = "outputs/beat_analysis.json", lyrics_path: str = "lyrics.txt", output_path: str = "outputs/final.mp4", events_path: str = "outputs/layer4_events.json", config: Dict[str, Any] = None):
    if config is None:
        config = {"subtitle_fontsize": 36, "subtitle_color": "white", "crossfade_sec": 0.3}

    # load inputs
    if not os.path.exists(animated_path):
        raise FileNotFoundError(animated_path)
    video = VideoFileClip(animated_path)
    video_w, video_h = int(video.w), int(video.h)

    if not os.path.exists(music_path):
        raise FileNotFoundError(music_path)
    audio = AudioFileClip(music_path)

    with open(semantic_path, 'r', encoding='utf-8') as f:
        semantic = json.load(f)
    with open(beat_path, 'r', encoding='utf-8') as f:
        beat = json.load(f)

    beats = beat.get('beat_times', []) or []
    energy_curve = beat.get('energy_curve', []) or []

    # Build word timings
    lyrics_text = None
    if lyrics_path and os.path.exists(lyrics_path):
        with open(lyrics_path, 'r', encoding='utf-8') as f:
            lyrics_text = f.read()

    # Build per-line subtitles (with karaoke-like highlighting)
    lines = build_line_timing_from_semantic(semantic)
    subtitle_clips = [make_line_subtitle_clip(l['text'], l['start'], l['duration'], video_w, video_h, fontsize=config.get('subtitle_fontsize', 36), color=config.get('subtitle_color', 'white'), highlight_color=config.get('subtitle_highlight', '#FFD166')) for l in lines]

    # Beat overlays using expanding ring pulses
    beat_clips = [make_beat_overlay_clip(b, video_w, video_h, duration=0.9, color_hex='#FFFFFF') for b in beats]

    # Scene tints: semi-transparent color overlay per segment, fading at boundaries
    tint_clips = []
    for seg in semantic.get('segments', []):
        st = float(seg.get('start_sec', 0.0))
        en = float(seg.get('end_sec', st + 1.0))
        color = _hex_to_rgb01(seg.get('color_hex'))
        # ColorClip takes color as tuple 0-255
        col = tuple([int(c * 255) for c in color.tolist()])
        tint = ColorClip(size=(video_w, video_h), color=col).set_start(st).set_duration(en - st).set_opacity(0.08)
        tint_clips.append(tint)

    # Compose everything
    layers = [video] + tint_clips + beat_clips + subtitle_clips
    final = CompositeVideoClip(layers).set_audio(audio)

    # write events file: merged timeline events
    events = []
    # scene events
    for s in semantic.get('segments', []):
        events.append({"type": "scene", "t": s.get('start_sec'), "emotion": s.get('emotion')})
    # beat events
    for b in beats:
        events.append({"type": "beat", "t": b})
    # word events: generate per-word timing from lines for more granular events
    words = []
    for l in lines:
        text = l.get('text', '')
        start = float(l.get('start', 0.0))
        dur = float(l.get('duration', 1.0))
        ws = [w for w in text.split() if w.strip()]
        if not ws:
            continue
        per = dur / len(ws)
        for i, w in enumerate(ws):
            words.append({"word": w, "start": round(start + i * per, 6), "duration": round(per, 6)})

    for w in words:
        events.append({"type": "word", "t": w['start'], "word": w['word']})

    events = sorted(events, key=lambda x: x['t'])

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    final.write_videofile(output_path, fps=video.fps)

    os.makedirs(os.path.dirname(events_path), exist_ok=True)
    with open(events_path, 'w', encoding='utf-8') as f:
        json.dump({"events": events}, f, indent=2)

    return {"final_path": output_path, "events_path": events_path}
