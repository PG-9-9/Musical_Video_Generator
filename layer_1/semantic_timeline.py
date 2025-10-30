import json
import os
from typing import List, Dict, Any, Optional

from layer_0 import load_config
from layer_0 import gemini_utils as _gutils
from .emotion_classifier import classify_emotion

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



# Note: local fallback remains available via emotion_classifier when HF is not present.


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
    # to stray tokens the LLM may insert. If parsing fails, attempt up to two
    # gentle retries with stricter instructions before falling back to a
    # deterministic segmentation.
    def _extract_candidate(text: str) -> str:
        if "[" in text and "]" in text:
            start = text.find("[")
            end = text.rfind("]")
            return text[start:end+1]
        return text

    candidate = _extract_candidate(raw)

    segments = None
    # Try initial parse
    try:
        segments = json.loads(candidate)
    except Exception:
        segments = None

    # If initial parse failed, attempt up to two retries with a cleaner prompt
    # that forces JSON-only output. This often recovers from noisy model output.
    if segments is None:
        retry_prompt = _build_prompt(lyrics, layer0_summary) + "\n\nIMPORTANT: Return ONLY a single JSON array and nothing else. Do not include prose or markdown."
        for attempt in range(2):
            try:
                raw2 = _call_llm_for_segments(api_key, retry_prompt)
                raw2 = raw2.strip()
                if raw2.startswith("```"):
                    raw2 = raw2.strip('`\n \t').lstrip('json').strip()
                candidate2 = _extract_candidate(raw2)
                segments = json.loads(candidate2)
                break
            except Exception:
                segments = None

    # If we still couldn't parse, try a best-effort object-extraction, then
    # finally fall back to deterministic segmentation.
    if segments is None:
        import re
        objs = re.findall(r"\{[^}]*\}", raw, re.S)
        if objs:
            try:
                candidate2 = "[" + ",".join(objs) + "]"
                segments = json.loads(candidate2)
            except Exception:
                segments = None

        if not segments:
            print("Warning: LLM returned malformed JSON after retries; falling back to deterministic segmentation.")
            # determine desired segment count
            min_segments = 3
            max_segments = 5
            n = min_segments
            # try to choose n based on lyric length
            words = [w for w in lyrics.replace('\n', ' ').split() if w.strip()]
            if len(words) > 30:
                n = min(max_segments, max(min_segments, len(words) // 10))
            # split words into n buckets
            per = max(1, len(words) // n)
            segments = []
            for i in range(n):
                start = i * per
                end = None if i == n-1 else (i+1)*per
                seg_words = words[start:end]
                seg_text = " ".join(seg_words).strip()
                seg_emotion = classify_emotion(seg_text).get('label', 'neutral') if seg_text else 'neutral'
                seg_obj = {
                    "lines": [seg_text] if seg_text else [],
                    "emotion": seg_emotion,
                    "intensity": 0.5,
                    "color_hex": COLOR_EMOTION_MAP.get(seg_emotion, "#808080"),
                    "keywords": [w.strip('.,') for w in seg_words[:6]],
                    "visual_hint": "auto-generated segment"
                }
                segments.append(seg_obj)

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
            # use the classifier adapter (HF pipeline if present, otherwise keyword fallback)
            pred = classify_emotion(" ".join(lines_list))
            emotion = pred.get("label", "neutral")
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
        pred = classify_emotion(joined)
        predicted = pred.get("label", "neutral")
        score = float(pred.get("score", 0.0)) if pred else 0.0
        # If HF used and confidence is high, trust it. Otherwise only reduce intensity a bit.
        if predicted != s["emotion"]:
            s["verified"] = False
            # if classifier was confident, more strongly correct intensity
            if score >= 0.7:
                s["intensity"] = max(0.0, s["intensity"] - 0.35)
            else:
                s["intensity"] = max(0.0, s["intensity"] - 0.15)
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
    # If Layer 0 provided a color palette, use it to map segment colors (cyclically)
    if layer0_summary and isinstance(layer0_summary, dict) and layer0_summary.get("color_palette"):
        try:
            palette = [c for c in layer0_summary.get("color_palette") if isinstance(c, str) and c.strip()]
            if palette:
                for idx, s in enumerate(cleaned):
                    s["color_hex"] = palette[idx % len(palette)]
        except Exception:
            pass
    else:
        for s in cleaned:
            if not s.get("color_hex"):
                s["color_hex"] = COLOR_EMOTION_MAP.get(s.get("emotion", "neutral"), "#808080")

    # Final structure
    semantic_timeline = {"segments": cleaned, "duration_sec": total}

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(semantic_timeline, f, indent=2, ensure_ascii=False)

    return semantic_timeline
