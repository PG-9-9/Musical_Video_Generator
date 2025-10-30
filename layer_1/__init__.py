"""Layer 1: semantic timeline API

Exports:
- generate_semantic_timeline(lyrics, layer0_summary=None)

This module implements the semantic segmentation step described in the project
spec: it asks the LLM to split the lyrics into 3-5 sequential segments and
produces a normalized timeline JSON saved to outputs/semantic_timeline.json.
"""
from .semantic_timeline import generate_semantic_timeline

__all__ = ["generate_semantic_timeline"]
