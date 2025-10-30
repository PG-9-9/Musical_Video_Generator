"""Layer 4 demo runner"""
from layer_4.orchestrator import compose_final


def main():
    out = compose_final(animated_path="outputs/animated.mp4", music_path="outputs/music.wav", semantic_path="outputs/semantic_timeline.json", beat_path="outputs/beat_analysis.json", lyrics_path="lyrics.txt", output_path="outputs/final.mp4", events_path="outputs/layer4_events.json")
    print("Wrote final:", out)


if __name__ == '__main__':
    main()
