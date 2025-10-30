"""Simple runner to create a semantic_timeline from sample lyrics."""
from layer_1 import generate_semantic_timeline


SAMPLE_LYRICS = "In the midnight light, I’m chasing dreams through neon skies.\nThe city hums and my heart races on.\nI remember whispers of a softer day,\nBut I push forward, hopeful for the dawn."  # short sample


def run():
    out = generate_semantic_timeline(SAMPLE_LYRICS)
    print("Wrote semantic timeline with", len(out["segments"]), "segments")


if __name__ == '__main__':
    run()
