"""Emotion classifier adapter: tries Hugging Face DistilBERT-based model and falls back
to a lightweight keyword classifier if transformers or model weights are unavailable.

This module exposes `classify_emotion(text: str) -> Dict[str, Any]` returning
{'label': <emotion_label>, 'score': <0-1 float>, 'backend': 'hf'|'fallback'}.
"""
from typing import Dict, Any
import logging

# Controlled set used by the project
CONTROLLED_EMOTIONS = ["calm", "sad", "dark", "romantic", "hopeful", "energetic", "euphoric", "neutral"]

_HF_AVAILABLE = False
_PIPELINE = None

try:
    from transformers import pipeline
    # Use a small emotion model when available; this will download weights on first run.
    try:
        _PIPELINE = pipeline("text-classification", model="mrm8488/tiny-distilbert-finetuned-emotion", top_k=1)
        _HF_AVAILABLE = True
    except Exception:
        # If that model isn't available or download fails, try the generic distilbert emotion model
        try:
            _PIPELINE = pipeline("text-classification", model="j-hartmann/emotion-english-distilbert", top_k=1)
            _HF_AVAILABLE = True
        except Exception:
            _PIPELINE = None
            _HF_AVAILABLE = False
except Exception:
    _HF_AVAILABLE = False
    _PIPELINE = None

def _fallback_keyword_emotion(text: str) -> Dict[str, Any]:
    t = text.lower()
    if any(w in t for w in ["love", "romance", "heart"]):
        return {"label": "romantic", "score": 0.6, "backend": "fallback"}
    if any(w in t for w in ["hope", "dream", "aspir"]):
        return {"label": "hopeful", "score": 0.6, "backend": "fallback"}
    if any(w in t for w in ["dance", "run", "drive", "energy", "rush"]):
        return {"label": "energetic", "score": 0.6, "backend": "fallback"}
    if any(w in t for w in ["happy", "joy", "euphor"]):
        return {"label": "euphoric", "score": 0.6, "backend": "fallback"}
    if any(w in t for w in ["sad", "tears", "cry", "lonely", "melanch"]):
        return {"label": "sad", "score": 0.6, "backend": "fallback"}
    if any(w in t for w in ["dark", "shadow", "nightmare"]):
        return {"label": "dark", "score": 0.6, "backend": "fallback"}
    if any(w in t for w in ["calm", "quiet", "gentle", "soft"]):
        return {"label": "calm", "score": 0.6, "backend": "fallback"}
    return {"label": "neutral", "score": 0.5, "backend": "fallback"}

def classify_emotion(text: str) -> Dict[str, Any]:
    """Return a dict {label, score, backend}. Uses HF pipeline when available, otherwise fallback.

    label will be normalized to the project's CONTROLLED_EMOTIONS if possible; otherwise 'neutral'.
    """
    if not text or not text.strip():
        return {"label": "neutral", "score": 0.0, "backend": "none"}

    # Lazy-init HF pipeline if transformers just became available in the env
    global _HF_AVAILABLE, _PIPELINE
    if not _HF_AVAILABLE and _PIPELINE is None:
        try:
            from transformers import pipeline
            try:
                _PIPELINE = pipeline("text-classification", model="mrm8488/tiny-distilbert-finetuned-emotion", top_k=1)
                _HF_AVAILABLE = True
            except Exception:
                try:
                    _PIPELINE = pipeline("text-classification", model="j-hartmann/emotion-english-distilbert", top_k=1)
                    _HF_AVAILABLE = True
                except Exception:
                    _PIPELINE = None
                    _HF_AVAILABLE = False
        except Exception:
            _HF_AVAILABLE = False

    if _HF_AVAILABLE and _PIPELINE is not None:
        try:
            out = _PIPELINE(text)
            if out and isinstance(out, list):
                best = out[0]
                lab = best.get("label", "neutral").lower()
                score = float(best.get("score", 0.0))
                # Map common HF labels to controlled vocabulary if possible
                lab_map = {
                    "joy": "euphoric",
                    "love": "romantic",
                    "sadness": "sad",
                    "anger": "dark",
                    "surprise": "energetic",
                    "fear": "dark",
                    "neutral": "neutral",
                    "happiness": "euphoric",
                }
                normalized = lab_map.get(lab, lab)
                if normalized not in CONTROLLED_EMOTIONS:
                    normalized = "neutral"
                return {"label": normalized, "score": score, "backend": "hf"}
        except Exception as e:
            # If HF fails at runtime, fall back to keyword method
            logging.getLogger(__name__).warning("HF emotion pipeline failed: %s", e)

    # fallback
    return _fallback_keyword_emotion(text)
