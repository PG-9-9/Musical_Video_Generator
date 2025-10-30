"""Runner for layer_2: analyze the outputs/music.wav and optional semantic timeline."""
from layer_2.beat_analysis import analyze_beats
import json


def run():
    out = analyze_beats(audio_path="outputs/music.wav", semantic_timeline_path="outputs/semantic_timeline.json")
    print("Wrote beat analysis. tempo:", out.get("tempo_bpm"), "BPM. beats:", len(out.get("beat_times", [])))
    # print a small summary
    print(json.dumps({
        "tempo_bpm": out.get("tempo_bpm"),
        "n_beats": len(out.get("beat_times", [])),
        "n_onsets": len(out.get("onset_times", [])),
        "duration_sec": out.get("duration_sec")
    }, indent=2))


if __name__ == '__main__':
    run()
