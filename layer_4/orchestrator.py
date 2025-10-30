import os
import json
from typing import Optional, Dict

# Robust moviepy imports: different installs expose different submodules.
VideoFileClip = None
AudioFileClip = None
concatenate_videoclips = None
CompositeVideoClip = None
ColorClip = None
ImageClip = None
VideoClip = None
try:
    # preferred modern import
    from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips, CompositeVideoClip, ColorClip, ImageClip, VideoClip
except Exception:
    try:
        # fallback to submodule imports
        from moviepy.video.io.VideoFileClip import VideoFileClip
        from moviepy.audio.io.AudioFileClip import AudioFileClip
        from moviepy.video.compositing.concatenate import concatenate_videoclips
        from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip
        from moviepy.video.fx.all import *
        from moviepy.video.VideoClip import ColorClip, ImageClip, VideoClip
    except Exception:
        # Leave names as None; callers will get a clearer error later.
        VideoFileClip = None
        AudioFileClip = None
        concatenate_videoclips = None
        CompositeVideoClip = None
        ColorClip = None
        ImageClip = None
        VideoClip = None


def orchestrate_final(styled_video_path: str = None, music_path: str = None, lyrics: str = None,
                      semantic_timeline_path: str = None, beat_analysis_path: str = None,
                      output_path: str = "outputs/final_with_audio.mp4",
                      video_clip=None, audio_clip=None) -> Dict[str, str]:
    """Attach audio to the styled video, ensure lengths match, and write final MP4.

    Returns a dict with keys: output_path, duration, notes
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # If caller passed clip objects, prefer them and skip import checks
    if video_clip is not None and audio_clip is not None:
        clip = video_clip
        audio = audio_clip
    else:
        # Defensive checks: some environments expose moviepy under different layouts.
        global VideoFileClip, AudioFileClip, concatenate_videoclips
        if not callable(VideoFileClip) or not callable(AudioFileClip):
            try:
                import moviepy.editor as _mpy
                VideoFileClip = getattr(_mpy, 'VideoFileClip', VideoFileClip)
                AudioFileClip = getattr(_mpy, 'AudioFileClip', AudioFileClip)
                concatenate_videoclips = getattr(_mpy, 'concatenate_videoclips', concatenate_videoclips)
            except Exception:
                pass

        if not callable(VideoFileClip) or not callable(AudioFileClip):
            # Can't perform orchestration without moviepy; fallback to copying styled video
            try:
                # attempt a safe copy
                import shutil
                if styled_video_path:
                    shutil.copyfile(styled_video_path, output_path)
                    return {"output_path": output_path, "duration": None, "notes": "moviepy not available; copied styled video"}
                else:
                    raise RuntimeError("moviepy not importable and no styled_video_path provided")
            except Exception as e:
                raise RuntimeError("MoviePy not importable in this environment: cannot attach audio") from e

        # Prefer clip objects passed in by caller to avoid re-import surprises
        clip = video_clip if video_clip is not None else VideoFileClip(styled_video_path)
        audio = audio_clip if audio_clip is not None else AudioFileClip(music_path)

        # If the provided audio object doesn't support moviepy operations (subclip/duration),
        # attempt a fast ffmpeg-based mux of the styled video + audio file (avoids moviepy callables).
        try:
            if not hasattr(audio, 'subclip') or not hasattr(audio, 'duration'):
                import shutil, subprocess
                ffmpeg = shutil.which('ffmpeg') or shutil.which('ffmpeg.exe')
                if ffmpeg and styled_video_path and music_path and os.path.exists(styled_video_path) and os.path.exists(music_path):
                    cmd = [ffmpeg, '-y', '-i', styled_video_path, '-i', music_path, '-c:v', 'copy', '-c:a', 'aac', '-shortest', output_path]
                    try:
                        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        return {"output_path": output_path, "duration": clip.duration if 'clip' in locals() and hasattr(clip, 'duration') else None, "notes": "orchestrated_via_ffmpeg"}
                    except Exception:
                        # if ffmpeg muxing fails, fall back to attempting moviepy coercion below
                        pass
                # try to coerce to a moviepy AudioFileClip using local imports as a fallback
                try:
                    import moviepy.editor as _mpy
                    audio = _mpy.AudioFileClip(music_path)
                except Exception:
                    try:
                        from moviepy import AudioFileClip as _AFP
                        audio = _AFP(music_path)
                    except Exception:
                        # leave original audio; downstream code will handle length checks
                        pass
        except Exception:
            pass

    # If audio is longer than video, trim; if shorter, loop to fit video length
    if audio.duration > clip.duration:
        audio = audio.subclip(0, clip.duration)
    elif audio.duration < clip.duration:
        # Try to loop audio to match video duration. Prefer moviepy's audio_loop fx
        try:
            # audio.fx(audio_loop, duration) is preferred when available
            from moviepy.audio.fx.all import audio_loop
            audio = audio.fx(audio_loop, duration=clip.duration)
        except Exception:
            # Fallback: concatenate repeated subclips and try concatenate_audioclips
            parts = []
            rem = clip.duration
            while rem > 0:
                take = min(rem, audio.duration)
                parts.append(audio.subclip(0, take))
                rem -= take
            if parts:
                try:
                    from moviepy.audio.fx.all import audio_loop as _al
                    audio = audio.fx(_al, duration=clip.duration)
                except Exception:
                    try:
                        from moviepy.editor import concatenate_audioclips
                        audio = concatenate_audioclips(parts)
                    except Exception:
                        # last resort: use the first part and let it repeat implicitly
                        audio = parts[0]

    final = clip.set_audio(audio)

    # Write final file
    final.write_videofile(output_path, codec="libx264", audio_codec="aac")

    # Write a small events JSON for debugging
    events = {
        "styled_video": styled_video_path,
        "music": music_path,
        "output": output_path,
        "video_duration": clip.duration,
        "audio_duration": audio.duration,
    }
    try:
        with open("outputs/final_events.json", "w", encoding="utf-8") as f:
            json.dump(events, f, indent=2)
    except Exception:
        pass

    return {"output_path": output_path, "duration": clip.duration, "notes": "orchestrated"}
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

# moviepy imports handled at top of file (robust import attempts)
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


def compose_final(animated_path: str = "outputs/animated.mp4", music_path: str = "outputs/music.wav", semantic_path: str = "outputs/semantic_timeline.json", beat_path: str = "outputs/beat_analysis.json", lyrics_path: str = "lyrics.txt", output_path: str = "outputs/final.mp4", events_path: str = "outputs/layer4_events.json", config: Dict[str, Any] = None, video_clip=None, audio_clip=None):
    if config is None:
        config = {"subtitle_fontsize": 36, "subtitle_color": "white", "crossfade_sec": 0.3}

    # load inputs
    if video_clip is None:
        if not os.path.exists(animated_path):
            raise FileNotFoundError(animated_path)
        video = VideoFileClip(animated_path)
    else:
        video = video_clip
    video_w, video_h = int(video.w), int(video.h)

    if audio_clip is None:
        if not os.path.exists(music_path):
            raise FileNotFoundError(music_path)
        audio = AudioFileClip(music_path)
    else:
        audio = audio_clip

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
