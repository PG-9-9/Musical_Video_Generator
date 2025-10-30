"""Layer 2: rhythmic analysis package

Exports:
- analyze_beats(audio_path, semantic_timeline_path=None)

"""
from .beat_analysis import analyze_beats

__all__ = ["analyze_beats"]
