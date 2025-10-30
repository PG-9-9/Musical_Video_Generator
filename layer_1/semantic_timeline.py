import json
import os
from typing import List, Dict, Any, Optional

from layer_0 import load_config
from layer_0 import gemini_utils as _gutils

# Controlled vocabulary for emotions
CONTROLLED_EMOTIONS = ["calm", "sad", "dark", "romantic", "hopeful", "energetic", "euphoric", "neutral"]

# Default mapping from emotion to representative HEX color
COLOR_EMOTION_MAP = {
    "calm": "#6CC0FF",
    "sad": "#2B3A67",
    "dark": "#0B0B0B",
    "romantic": "#FF6FA3",
    "hopeful": "#FFD166",
    "energetic": "#FF7F11",
    "euphoric": "#9B5DE5",
    "neutral": "#808080",
}


def _local_emotion_classifier(text: str) -> str:
    """Lightweight keyword-based emotion classifier used for verification.

    This is intentionally small and local for stability; in production this
    should be replaced with a DistilBERT-Emotion or similar classifier.
    """
    t = text.lower()
    if any(w in t for w in ["love", "romance", "heart"]):
        return "romantic"
    if any(w in t for w in ["hope", "dream", "aspir"]):
        return "hopeful"
    if any(w in t for w in ["dance", "run", "drive", "energy", "rush"]):
        return "energetic"
    if any(w in t for w in ["happy", "joy", "euphor"]):
        return "euphoric"
    if any(w in t for w in ["sad", "tears", "cry", "lonely", "melanch"]):
        return "sad"
    if any(w in t for w in ["dark", "shadow", "nightmare"]):
        return "dark"
    if any(w in t for w in ["calm", "quiet", "gentle", "soft"]):
        return "calm"
    return "neutral"


def _call_llm_for_segments(api_key: str, prompt: str) -> str:
    """Call the installed Gemini SDK via layer_0.gemini_utils.get_gemini_client
    and return the textual output.
    """
    client_or_model = _gutils.get_gemini_client(api_key)

    # Attempt the same robust extraction logic used in layer_0
    resp = None
    if hasattr(client_or_model, "generate_content"):
        try:
            resp = client_or_model.generate_content(prompt)
        except TypeError:
            # fallback to client.models.generate_content
            client_obj = getattr(client_or_model, "_client", None) or getattr(client_or_model, "client", None) or client_or_model
            model_name = getattr(client_or_model, "_model_name", getattr(client_or_model, "_fallback_model_name", "gemini-2.5-flash"))
            resp = client_obj.models.generate_content(model=model_name, contents=prompt)
    elif hasattr(client_or_model, "generate"):
        try:
            resp = client_or_model.generate(prompt)
        except TypeError:
            client_obj = getattr(client_or_model, "_client", None) or getattr(client_or_model, "client", None) or client_or_model
            model_name = getattr(client_or_model, "_model_name", getattr(client_or_model, "_fallback_model_name", "gemini-2.5-flash"))
            resp = client_obj.models.generate_content(model=model_name, contents=prompt)
    else:
        client_obj = client_or_model
        model_name = getattr(client_or_model, "_fallback_model_name", "gemini-2.5-flash")
        resp = client_obj.models.generate_content(model=model_name, contents=prompt)

    # Extract text
    text = None
    for attr in ("text", "output_text", "content", "result", "output"):
        if hasattr(resp, attr):
            text = getattr(resp, attr)
            break
    if text is None and isinstance(resp, dict):
        for k in ("text", "output_text", "content", "result"):
            if k in resp:
                text = resp[k]
                break
    if text is None:
        text = str(resp)
    return text.strip()


def _build_prompt(lyrics: str, layer0_summary: Optional[Dict[str, Any]] = None, min_segments: int = 3, max_segments: int = 5) -> str:
    vocab = ", ".join(CONTROLLED_EMOTIONS)
    ctx = "" if layer0_summary is None else json.dumps(layer0_summary, indent=2)
    prompt = f"""
You are a semantic analyst that converts song lyrics into a temporal emotional blueprint.

Controlled emotion labels: {vocab}

Input lyrics (do not invent lines):
{lyrics}

Context from Layer 0 (may be empty):
{ctx}

TASK:
- Split the lyrics into BETWEEN {min_segments} and {max_segments} ordered segments where tone, imagery, or energy changes.
- For each segment, output a JSON object with these fields:
  - lines: an array of the exact lyric lines (strings) belonging to this segment
  - emotion: one of the controlled emotion labels
  - intensity: float between 0.0 and 1.0 indicating how intense that emotion is
  - color_hex: representative color in 6-digit HEX (e.g., #RRGGBB) or null
  - keywords: array of 3-6 single-word imagery/theme keywords
  - visual_hint: concise 3-7 word hint describing animation style

ADDITIONAL RULES:
- Cover the entire lyrics with no gaps and no overlapping lines.
- Return ONLY a single JSON array (no explanation, no extraneous text).
- The order of array elements must reflect the timeline order from start to end.
"""
    return prompt


def generate_semantic_timeline(lyrics: str, layer0_summary: Optional[Dict[str, Any]] = None, output_path: str = "outputs/semantic_timeline.json") -> Dict[str, Any]:
    """Main entrypoint: ask the LLM for segments, verify/blend emotions locally, normalize time and save JSON.

    Returns the final semantic timeline dict.
    """
    cfg = load_config("config.json")
    api_key = cfg.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY missing in config.json")

    prompt = _build_prompt(lyrics, layer0_summary)
    raw = _call_llm_for_segments(api_key, prompt)

    # Remove common markdown fences if present
    if raw.startswith("```"):
        raw = raw.strip("`\n \t").lstrip("json").strip()

    # Try to extract the first JSON array-looking substring ([ ... ]) to be robust
    # to stray tokens the LLM may insert.
    if "[" in raw and "]" in raw:
        start = raw.find("[")
        end = raw.rfind("]")
        candidate = raw[start:end+1]
    else:
        candidate = raw

    try:
        segments = json.loads(candidate)
    except Exception as e:
        # If that fails, surface the raw output for debugging
        raise ValueError("LLM did not return valid JSON array: " + str(e) + "\nRaw output:\n" + raw)

    if not isinstance(segments, list):
        raise ValueError("Expected JSON array of segments")

    n = len(segments)
    if n < 3 or n > 5:
        raise ValueError(f"LLM returned {n} segments; expected between 3 and 5")

    # Normalize and validate fields
    cleaned: List[Dict[str, Any]] = []
    for seg in segments:
        s = {}
        # lines: accept string or list
        lines = seg.get("lines") or seg.get("text") or seg.get("lyrics")
        if isinstance(lines, str):
            # split by line breaks if present
            lines_list = [ln.strip() for ln in lines.splitlines() if ln.strip()]
        elif isinstance(lines, list):
            lines_list = [str(x).strip() for x in lines if str(x).strip()]
        else:
            lines_list = []
        s["lines"] = lines_list

        emotion = str(seg.get("emotion", "neutral")).lower()
        if emotion not in CONTROLLED_EMOTIONS:
            # try to map loosely
            emotion = _local_emotion_classifier(" ".join(lines_list))
        s["emotion"] = emotion

        intensity = seg.get("intensity", seg.get("emotional_intensity", 0.5))
        try:
            intensity = float(intensity)
        except Exception:
            intensity = 0.5
        intensity = max(0.0, min(1.0, intensity))
        s["intensity"] = intensity

        color = seg.get("color_hex") or seg.get("color") or None
        if not color:
            color = COLOR_EMOTION_MAP.get(emotion, "#808080")
        s["color_hex"] = color

        keywords = seg.get("keywords") or seg.get("tags") or []
        if isinstance(keywords, str):
            keywords = [k.strip() for k in keywords.split(",") if k.strip()]
        s["keywords"] = keywords[:6]

        visual_hint = seg.get("visual_hint") or seg.get("visual") or ""
        s["visual_hint"] = str(visual_hint).strip()

        cleaned.append(s)

    # Emotion verification & blending
    for s in cleaned:
        joined = " ".join(s.get("lines", []))
        predicted = _local_emotion_classifier(joined)
        if predicted != s["emotion"]:
            # favor LLM label but reduce intensity due to classifier uncertainty
            s["verified"] = False
            s["intensity"] = max(0.0, s["intensity"] - 0.2)
        else:
            s["verified"] = True

    # Temporal normalization: assign equal-duration contiguous segments across 10 seconds
    total = 10.0
    for i, s in enumerate(cleaned):
        start = round(i * (total / n), 6)
        end = round((i + 1) * (total / n), 6)
        s["start_sec"] = start
        s["end_sec"] = end

    # Smooth extreme intensity jumps: if neighbor delta > 0.4 average them
    for i in range(1, n):
        prev = cleaned[i - 1]["intensity"]
        cur = cleaned[i]["intensity"]
        if abs(prev - cur) > 0.4:
            avg = round((prev + cur) / 2.0, 3)
            cleaned[i - 1]["intensity"] = avg
            cleaned[i]["intensity"] = avg

    # Ensure colors present
    for s in cleaned:
        if not s.get("color_hex"):
            s["color_hex"] = COLOR_EMOTION_MAP.get(s.get("emotion", "neutral"), "#808080")

    # Final structure
    semantic_timeline = {"segments": cleaned, "duration_sec": total}

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(semantic_timeline, f, indent=2, ensure_ascii=False)

    return semantic_timeline
