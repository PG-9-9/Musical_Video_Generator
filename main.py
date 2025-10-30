import os
import json

from layer_0 import analyze_lyrics, load_config, generate_music_from_prompt, generate_placeholder_video, compose_video
from layer_1.semantic_timeline import generate_semantic_timeline
from layer_2.beat_analysis import analyze_beats
import json
import os


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
    music_path = generate_music_from_prompt(music_prompt, duration_sec=10, output_path="outputs/music.wav",
                                            mubert_api_key=mubert_key)

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


if __name__ == "__main__":
    main()
