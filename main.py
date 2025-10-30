import os
import json

from layer_0 import analyze_lyrics, load_config, generate_music_from_prompt, generate_placeholder_video, compose_video
from layer_1.semantic_timeline import generate_semantic_timeline
from layer_2.beat_analysis import analyze_beats
from layer_3 import generate_animation
from layer_5.style_profiles import STYLE_PROFILES
from layer_5.style_applier import build_style_timeline, apply_styles_to_frames
from layer_4.orchestrator import orchestrate_final
# Robust MoviePy imports to support multiple layouts
VideoFileClip = None
AudioFileClip = None
try:
    from moviepy.editor import VideoFileClip, AudioFileClip
except Exception:
    try:
        from moviepy import VideoFileClip, AudioFileClip
    except Exception:
        try:
            from moviepy.video.io.VideoFileClip import VideoFileClip
            from moviepy.audio.io.AudioFileClip import AudioFileClip
        except Exception:
            VideoFileClip = None
            AudioFileClip = None

from PIL import Image
import numpy as np


def main():
    lyrics = "In the midnight light, I’m chasing dreams through neon skies."
    config = load_config("config.json")

    print("[1/4] Analyzing lyrics with Gemini...")
    gemini_out = analyze_lyrics(lyrics, "config.json")
    print("Gemini output:", json.dumps(gemini_out, indent=2))

    music_prompt = gemini_out.get("music_prompt", "dreamy synthwave, neon city at night")
    video_prompt = gemini_out.get("video_prompt", "neon city animation")
    mubert_key = config.get("MUBERT_API_KEY")

    print("[2/6] Generating semantic timeline (Layer 1)...")
    sem = generate_semantic_timeline(lyrics, layer0_summary=gemini_out, output_path="outputs/semantic_timeline.json")
    print("Semantic timeline written to outputs/semantic_timeline.json")

    print("[3/6] Generating music placeholder...")
    # Build optional tempo/style hint from Gemini output if present
    tempo_hint = None
    try:
        bpm = gemini_out.get('recommended_bpm')
        if bpm:
            tempo_hint = f"{int(bpm)} BPM"
    except Exception:
        tempo_hint = None

    music_path = generate_music_from_prompt(music_prompt, duration_sec=10, output_path="outputs/music.wav",
                                            mubert_api_key=mubert_key, semantic_timeline="outputs/semantic_timeline.json",
                                            raw_lyrics=lyrics, global_mood=gemini_out.get('global_mood') or gemini_out.get('dominant_emotion'),
                                            optional_tempo_style=tempo_hint)

    print("[4/6] Running beat/tempo analysis (Layer 2)...")
    beats = analyze_beats(audio_path=music_path, semantic_timeline_path="outputs/semantic_timeline.json", output_path="outputs/beat_analysis.json")
    print("Beat analysis written to outputs/beat_analysis.json")

    print("[5/6] Generating video placeholder...")
    video_path = generate_placeholder_video(video_prompt, duration_sec=10, output_path="outputs/video.mp4")

    print("[6/6] Composing final video...")
    final_path = compose_video(video_path, music_path, lyrics, output_path="outputs/final.mp4")

    # Write a combined pipeline outputs file for convenience
    pipeline_out = {
        "lyrics": lyrics,
        "gemini": gemini_out,
        "semantic_timeline_path": "outputs/semantic_timeline.json",
        "beat_analysis_path": "outputs/beat_analysis.json",
        "music_path": music_path,
        "video_path": video_path,
        "final_video_path": final_path,
    }
    os.makedirs("outputs", exist_ok=True)
    with open("outputs/pipeline_outputs.json", "w", encoding="utf-8") as f:
        json.dump(pipeline_out, f, indent=2)

    print("Done. Final video at:", final_path)
    print("Pipeline metadata written to outputs/pipeline_outputs.json")

    # Run Layer 3 animator to produce animated.mp4 and events JSON.
    try:
        print("[7/9] Running Layer 3 animator to produce animated.mp4...")
        anim_cfg = {"resolution": [640, 360], "fps": 24, "crossfade_sec": 0.5, "style": "synthwave"}
        out = generate_animation("outputs/semantic_timeline.json", "outputs/beat_analysis.json", output_path="outputs/animated.mp4", events_path="outputs/layer3_events.json", config=anim_cfg)
        print("Layer 3 produced:", out)
        # update pipeline_out
        pipeline_out["animated_path"] = out.get("animated_path")
        pipeline_out["layer3_events"] = out.get("events_path")
        with open("outputs/pipeline_outputs.json", "w", encoding="utf-8") as f:
            json.dump(pipeline_out, f, indent=2)
        print("Animated video written to:", out.get("animated_path"))
    except Exception as e:
        print("Layer 3 animator failed:", e)
        return

    # ---- Layer 5: Adaptive styling ----
    try:
        print("[8/9] Building style timeline from semantic_timeline.json...")
        with open("outputs/semantic_timeline.json", 'r', encoding='utf-8') as f:
            sem = json.load(f)
        # duration estimate
        duration = sem.get('duration_sec', 10.0)
        fps = 24
        style_tl = build_style_timeline(sem, fps=fps, duration_sec=duration)

        print("[9/9] Extracting frames from animated.mp4 and applying styles (this may take a moment)...")
        clip = VideoFileClip(pipeline_out.get('animated_path', 'outputs/animated.mp4'))
        frames = []
        # sample at clip.fps or target fps
        target_fps = fps
        total_frames = int(min(clip.duration * target_fps, 240))  # cap to 240 frames for preview safety
        for i in range(total_frames):
            t = min(i / target_fps, clip.duration - 1e-3)
            frame = clip.get_frame(t)  # numpy array HxWx3
            pil = Image.fromarray(frame.astype('uint8'))
            frames.append(pil)

        # build a beat_curve from beat_analysis.json (energy_curve)
        with open("outputs/beat_analysis.json", 'r', encoding='utf-8') as f:
            beat = json.load(f)
        energy = beat.get('energy_curve', [])
        # normalize/upsample energy to frame count
        if len(energy) < total_frames and len(energy) > 0:
            # simple nearest upsample
            beat_curve = [energy[min(int((i/total_frames)*len(energy)), len(energy)-1)] for i in range(total_frames)]
        else:
            beat_curve = energy[:total_frames] if energy else [0.0]*total_frames

        styled_out = "outputs/styled_final.mp4"
        styled_path = apply_styles_to_frames(frames, style_tl, beat_curve, styled_out, fps=target_fps, lyrics=lyrics, semantic_timeline=sem)
        print("Styled video written to:", styled_path)
        pipeline_out['styled_video'] = styled_path
        with open("outputs/pipeline_outputs.json", "w", encoding="utf-8") as f:
            json.dump(pipeline_out, f, indent=2)

        # Layer 4: attach audio and finalize (try MoviePy -> ffmpeg -> orchestrator)
        muxed_path = "outputs/final_with_audio.mp4"
        attached = False
        # Try MoviePy attach first (we used MoviePy earlier for video writing)
        try:
            styled_clip = VideoFileClip(styled_path)
            audio_clip = AudioFileClip(music_path)
            try:
                if audio_clip.duration > styled_clip.duration:
                    audio_clip = audio_clip.subclip(0, styled_clip.duration)
                elif audio_clip.duration < styled_clip.duration:
                    try:
                        from moviepy.audio.fx.all import audio_loop
                        audio_clip = audio_clip.fx(audio_loop, duration=styled_clip.duration)
                    except Exception:
                        pass
            except Exception:
                pass
            final_clip = styled_clip.set_audio(audio_clip)
            final_clip.write_videofile(muxed_path, codec="libx264", audio_codec="aac")
            final_clip.close()
            try:
                styled_clip.close()
                audio_clip.close()
            except Exception:
                pass
            pipeline_out['final_with_audio'] = muxed_path
            attached = True
        except Exception:
            # MoviePy attach failed; try ffmpeg mux
            try:
                import shutil, subprocess
                ffmpeg = shutil.which('ffmpeg') or shutil.which('ffmpeg.exe')
                if not ffmpeg:
                    try:
                        import imageio_ffmpeg as _iioff
                        ffmpeg = _iioff.get_ffmpeg_exe()
                    except Exception:
                        ffmpeg = None
                if ffmpeg and os.path.exists(styled_path) and os.path.exists(music_path):
                    cmd = [ffmpeg, '-y', '-i', styled_path, '-i', music_path, '-c:v', 'copy', '-c:a', 'aac', '-shortest', muxed_path]
                    subprocess.run(cmd, check=True)
                    pipeline_out['final_with_audio'] = muxed_path
                    attached = True
            except Exception:
                # ffmpeg mux failed or not available; use orchestrator as last resort
                try:
                    out = orchestrate_final(styled_path, music_path, lyrics, "outputs/semantic_timeline.json", "outputs/beat_analysis.json", output_path=muxed_path)
                    pipeline_out['final_with_audio'] = out.get('output_path')
                    attached = True if out.get('output_path') else False
                except Exception as e:
                    print("Layer 4 orchestration failed:", e)

        # Finalize pipeline outputs metadata (ensure final_with_audio key is set to path or null)
        pipeline_out['final_with_audio'] = pipeline_out.get('final_with_audio') or None
        with open("outputs/pipeline_outputs.json", "w", encoding="utf-8") as f:
            json.dump(pipeline_out, f, indent=2)
        if attached:
            print("Final video with audio written to:", pipeline_out['final_with_audio'])
        else:
            print("Failed to attach audio; see logs for details. pipeline_outputs.json updated.")
    except Exception as e:
        print("Layer 5 styling failed:", e)
        import traceback
        traceback.print_exc()
        return


if __name__ == "__main__":
    main()
