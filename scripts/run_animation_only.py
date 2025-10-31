"""Run only Layer 3 animation using existing pipeline function.
Usage: F:\Conda\envs\musical_v\python.exe scripts\run_animation_only.py
"""
import os
import sys
import traceback
import json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from layer_3.animator import generate_animation


def main():
    try:
        print("Running Layer 3 animator...")
        # allow optional JSON arg
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

        semantic = runner_args.get('semantic', 'outputs/semantic_timeline.json')
        beat = runner_args.get('beat', 'outputs/beat_analysis.json')
        out_path = runner_args.get('output_path', 'outputs/animated.mp4')
        events_path = runner_args.get('events_path', 'outputs/layer3_events.json')
        cfg = runner_args.get('config', {"resolution": [640,360], "fps": 24, "crossfade_sec": 0.25})
        # allow top-level style token from dashboard (e.g., 'synthwave', 'lo-fi')
        if runner_args.get('style'):
            cfg['style'] = runner_args.get('style')

        try:
            os.makedirs('outputs', exist_ok=True)
            progress_path = os.path.join('outputs', 'jobs', f'{jobid}.progress.json') if jobid else 'outputs/progress_anim.json'
            os.makedirs(os.path.dirname(progress_path), exist_ok=True)
            with open(progress_path, 'w', encoding='utf-8') as pf:
                json.dump({'pct': 10, 'stage': 'starting'}, pf)
        except Exception:
            pass

        out = generate_animation(semantic, beat, output_path=out_path, events_path=events_path, config=cfg)
        print("Layer 3 done. Output:", out)
        try:
            progress_path = os.path.join('outputs', 'jobs', f'{jobid}.progress.json') if jobid else 'outputs/progress_anim.json'
            with open(progress_path, 'w', encoding='utf-8') as pf:
                json.dump({'pct': 100, 'stage': 'done'}, pf)
        except Exception:
            pass
    except Exception:
        print("Layer 3 failed:")
        traceback.print_exc()


if __name__ == '__main__':
    main()
