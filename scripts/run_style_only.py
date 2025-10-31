"""Run only Layer 5 style applier using existing pipeline functions.
Usage: F:\Conda\envs\musical_v\python.exe scripts\run_style_only.py
"""
import os
import sys
import traceback
import json
import glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from PIL import Image

from layer_5.style_applier import build_style_timeline, apply_styles_to_frames


def main():
    try:
        print("Loading animated video frames...")
        runner_args = {}
        jobid = None
        if len(sys.argv) > 1:
            try:
                runner_args = json.loads(sys.argv[1])
            except Exception:
                print('Could not parse runner JSON arg:', sys.argv[1])
        try:
            if len(sys.argv) > 2:
                jobid = sys.argv[2]
        except Exception:
            jobid = None

        # determine progress path (job-scoped when jobid provided)
        progress_path = os.path.join('outputs', 'jobs', f'{jobid}.progress.json') if jobid else 'outputs/progress_style.json'
        try:
            os.makedirs(os.path.dirname(progress_path), exist_ok=True)
            with open(progress_path, 'w', encoding='utf-8') as pf:
                json.dump({'pct': 10, 'stage': 'starting'}, pf)
        except Exception:
            pass

        frames = []
        # try moviepy extraction first
        try:
            from moviepy.editor import VideoFileClip
            clip = VideoFileClip('outputs/animated.mp4')
            fps = int(clip.fps or 24)
            duration = clip.duration or 10.0
            total_frames = min(int(fps * duration), 240)
            for i in range(total_frames):
                t = min(i / fps, clip.duration - 1e-3)
                frame = clip.get_frame(t)
                frames.append(Image.fromarray(frame.astype('uint8')))
            clip.close()
        except Exception:
            # fallback: load frame_*.png from outputs
            files = sorted(glob.glob(os.path.join('outputs', 'frame_*.png')))
            for p in files:
                try:
                    frames.append(Image.open(p).convert('RGB'))
                except Exception:
                    pass

        if not frames:
            print('No frames available to style. Aborting.')
            return

        semantic = {}
        try:
            with open('outputs/semantic_timeline.json', 'r', encoding='utf-8') as f:
                semantic = json.load(f)
        except Exception:
            print('No semantic_timeline.json; using defaults')

        fps = runner_args.get('fps', 24)
        duration = semantic.get('duration_sec', len(frames)/fps if frames else 10.0)

        # build style timeline; allow override from dashboard style token
        override_style = runner_args.get('style')
        try:
            with open(progress_path, 'w', encoding='utf-8') as pf:
                json.dump({'pct': 20, 'stage': 'building_style_timeline'}, pf)
        except Exception:
            pass

        style_tl = build_style_timeline(semantic, fps=fps, duration_sec=duration, override_style=override_style)

        beat = []
        try:
            with open('outputs/beat_analysis.json', 'r', encoding='utf-8') as f:
                ba = json.load(f)
                beat = ba.get('energy_curve', [])
        except Exception:
            beat = [0.0] * len(frames)

        out = runner_args.get('output_path', 'outputs/styled_final.mp4')
        print('Applying styles to frames; writing', out)
        try:
            with open(progress_path, 'w', encoding='utf-8') as pf:
                json.dump({'pct': 50, 'stage': 'stylizing'}, pf)
        except Exception:
            pass

        res = apply_styles_to_frames(frames, style_tl, beat, out, fps=fps, lyrics=runner_args.get('lyrics', None), semantic_timeline=semantic)
        print('Layer 5 done. Output:', res)
        try:
            with open(progress_path, 'w', encoding='utf-8') as pf:
                json.dump({'pct': 100, 'stage': 'done'}, pf)
        except Exception:
            pass
    except Exception:
        print('Layer 5 failed:')
        traceback.print_exc()


if __name__ == '__main__':
    main()
