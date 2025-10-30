"""Run Layer 3 demo: read existing L1+L2 outputs and produce an animated.mp4."""
from layer_3 import generate_animation

def main():
    cfg = {"resolution": [640, 360], "fps": 24, "style": "demo"}
    out = generate_animation("outputs/semantic_timeline.json", "outputs/beat_analysis.json", output_path="outputs/animated.mp4", events_path="outputs/layer3_events.json", config=cfg)
    print("Wrote animated video:", out)

if __name__ == '__main__':
    main()
