"""
Runner that executes only the music generation step using the existing pipeline function.
It will: load config, analyze lyrics via Gemini, then call generate_music_from_prompt and report the output path and any errors.
Run with the project's Conda Python to use the same environment:

F:\Conda\envs\musical_v\python.exe scripts\run_music_only.py
"""
import json
import os
import sys
import traceback

# Ensure project root is on sys.path so package imports work when running scripts
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from layer_0 import analyze_lyrics, load_config, generate_music_from_prompt

LYRICS = "In the midnight light, I’m chasing dreams through neon skies."


def _parse_args():
    # allow optional JSON arg to override lyrics, duration_sec, output_path, etc.
    import sys
    if len(sys.argv) > 1:
        try:
            a = json.loads(sys.argv[1])
            return a
        except Exception:
            print('Warning: could not parse runner arg as JSON:', sys.argv[1])
    return {}


def main():
    try:
        cfg = load_config("config.json")
    except Exception as e:
        print("Failed to load config.json:", e)
        return
    runner_args = _parse_args()
    try:
        # emit starting progress
        try:
            os.makedirs('outputs', exist_ok=True)
            with open('outputs/progress_music.json', 'w', encoding='utf-8') as pf:
                json.dump({'pct': 5, 'stage': 'starting'}, pf)
        except Exception:
            pass

        print("Analyzing lyrics with Gemini (layer_0.analyze_lyrics)...")
        lyrics = runner_args.get('lyrics', LYRICS)
        gem = analyze_lyrics(lyrics, "config.json")
        print("Gemini result summary:", json.dumps(gem, indent=2)[:1000])
        try:
            with open('outputs/progress_music.json', 'w', encoding='utf-8') as pf:
                json.dump({'pct': 15, 'stage': 'analyzed'}, pf)
        except Exception:
            pass
    except Exception as e:
        print("Gemini analysis failed:")
        traceback.print_exc()
        return

    music_prompt = gem.get('music_prompt') or "dreamy synthwave, neon city at night"
    tempo_hint = None
    try:
        bpm = gem.get('recommended_bpm')
        if bpm:
            tempo_hint = f"{int(bpm)} BPM"
    except Exception:
        tempo_hint = None

    out_path = runner_args.get('output_path', 'outputs/music_gen_test.wav')
    duration = runner_args.get('duration_sec', 6)
    try:
        print("Calling generate_music_from_prompt(...) with prompt:\n", music_prompt)
        try:
            with open('outputs/progress_music.json', 'w', encoding='utf-8') as pf:
                json.dump({'pct': 30, 'stage': 'generating'}, pf)
        except Exception:
            pass
        music = generate_music_from_prompt(
            music_prompt,
            duration_sec=duration,
            output_path=out_path,
            mubert_api_key=cfg.get('MUBERT_API_KEY'),
            semantic_timeline=runner_args.get('semantic_timeline', "outputs/semantic_timeline.json"),
            raw_lyrics=lyrics,
            global_mood=gem.get('global_mood') or gem.get('dominant_emotion'),
            optional_tempo_style=tempo_hint)
        print("Music generation returned:", music)
        if os.path.exists(music):
            print("SUCCESS: music file written to:", music)
            try:
                with open('outputs/progress_music.json', 'w', encoding='utf-8') as pf:
                    json.dump({'pct': 100, 'stage': 'done'}, pf)
            except Exception:
                pass
        else:
            print("Warning: generate_music_from_prompt did not return a file path that exists.")
    except Exception as e:
        print("Music generation failed:")
        traceback.print_exc()


if __name__ == '__main__':
    main()
