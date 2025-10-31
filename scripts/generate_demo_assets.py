"""Create small demo assets under outputs/ so the dashboard can show a working demo without heavy model runs.
It creates:
 - outputs/demo_music.wav (sine wave, 6s)
 - outputs/semantic_timeline.json (simple segments)
 - outputs/beat_analysis.json (simple energy/beat times)
 - outputs/animated.mp4 (very small generated clip via moviepy when available)
 - outputs/styled_final.mp4 (copy of animated.mp4)
 - outputs/pipeline_outputs.json pointing to demo assets
"""
import os
import json
import math
import wave
import struct

OUT = 'outputs'
os.makedirs(OUT, exist_ok=True)

def write_sine_wav(path='outputs/demo_music.wav', duration=6.0, sr=22050, freq=440.0):
    n = int(duration * sr)
    amp = 0.4
    with wave.open(path, 'w') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        for i in range(n):
            t = i / sr
            v = int(32767 * amp * math.sin(2 * math.pi * freq * t))
            wf.writeframes(struct.pack('<h', v))


def write_demo_jsons():
    sem = {
        "duration_sec": 6.0,
        "segments": [
            {"start_sec": 0.0, "end_sec": 2.0, "emotion": "calm", "intensity": 0.2, "color_hex": "#1A0A33"},
            {"start_sec": 2.0, "end_sec": 4.0, "emotion": "hopeful", "intensity": 0.6, "color_hex": "#E03B8B"},
            {"start_sec": 4.0, "end_sec": 6.0, "emotion": "energetic", "intensity": 0.9, "color_hex": "#00E5FF"}
        ]
    }
    with open(os.path.join(OUT, 'semantic_timeline.json'), 'w', encoding='utf-8') as f:
        json.dump(sem, f, indent=2)

    beat = {
        "beat_times": [0.5, 1.5, 2.5, 3.5, 4.5, 5.5],
        "energy_curve": [0.1, 0.15, 0.2, 0.6, 0.8, 0.9],
        "per_segment_energy": [0.2, 0.6, 0.9]
    }
    with open(os.path.join(OUT, 'beat_analysis.json'), 'w', encoding='utf-8') as f:
        json.dump(beat, f, indent=2)


def make_small_video(path='outputs/animated.mp4'):
    try:
        from moviepy.editor import ImageSequenceClip
        import numpy as np
        frames = []
        for i in range(24):
            arr = np.zeros((180, 320, 3), dtype=np.uint8)
            arr[..., 0] = int(127 + 127 * math.sin(i * 0.3))
            arr[..., 1] = int(127 + 127 * math.sin(i * 0.2))
            arr[..., 2] = int(127 + 127 * math.sin(i * 0.1))
            frames.append(arr)
        clip = ImageSequenceClip(frames, fps=12)
        clip.write_videofile(path, codec='libx264', audio=False)
        clip.close()
        return True
    except Exception as e:
        print('Could not create demo video via moviepy:', e)
        return False


def main():
    print('Writing demo sine WAV...')
    write_sine_wav()
    print('Writing demo JSONs...')
    write_demo_jsons()
    print('Attempting to create small demo animated.mp4 (moviepy required)')
    ok = make_small_video()
    if ok:
        # copy animated to styled
        import shutil
        shutil.copyfile('outputs/animated.mp4', 'outputs/styled_final.mp4')
    else:
        # create placeholder text files so dashboard can show they exist
        with open('outputs/animated.mp4', 'wb') as f:
            f.write(b'')
        with open('outputs/styled_final.mp4', 'wb') as f:
            f.write(b'')

    pipeline = {
        "lyrics": "Demo lyrics",
        "semantic_timeline_path": "outputs/semantic_timeline.json",
        "beat_analysis_path": "outputs/beat_analysis.json",
        "music_path": "outputs/demo_music.wav",
        "video_path": "outputs/animated.mp4",
        "final_video_path": "outputs/final.mp4",
        "animated_path": "outputs/animated.mp4",
        "styled_video": "outputs/styled_final.mp4",
        "final_with_audio": "outputs/final_with_audio.mp4"
    }
    with open(os.path.join(OUT, 'pipeline_outputs.json'), 'w', encoding='utf-8') as f:
        json.dump(pipeline, f, indent=2)
    print('Demo assets written to outputs/')


if __name__ == '__main__':
    main()
