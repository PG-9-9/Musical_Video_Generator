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


def main():
    try:
        cfg = load_config("config.json")
    except Exception as e:
        print("Failed to load config.json:", e)
        return
    try:
        print("Analyzing lyrics with Gemini (layer_0.analyze_lyrics)...")
        gem = analyze_lyrics(LYRICS, "config.json")
        print("Gemini result summary:", json.dumps(gem, indent=2)[:1000])
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

    out_path = "outputs/music_gen_test.wav"
    try:
        print("Calling generate_music_from_prompt(...) with prompt:\n", music_prompt)
        music = generate_music_from_prompt(music_prompt, duration_sec=6, output_path=out_path,
                                           mubert_api_key=cfg.get('MUBERT_API_KEY'),
                                           semantic_timeline="outputs/semantic_timeline.json",
                                           raw_lyrics=LYRICS,
                                           global_mood=gem.get('global_mood') or gem.get('dominant_emotion'),
                                           optional_tempo_style=tempo_hint)
        print("Music generation returned:", music)
        if os.path.exists(music):
            print("SUCCESS: music file written to:", music)
        else:
            print("Warning: generate_music_from_prompt did not return a file path that exists.")
    except Exception as e:
        print("Music generation failed:")
        traceback.print_exc()


if __name__ == '__main__':
    main()
