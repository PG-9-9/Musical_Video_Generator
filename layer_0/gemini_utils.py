import json
import os
from typing import Dict, Any

from google import genai 


# --- Utility Functions ---

def load_config(path: str = "config.json") -> Dict[str, Any]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"{path} not found. Copy config.example.json to config.json and fill in keys.")
    with open(path, "r") as f:
        return json.load(f)


# --- Gemini Client & Analysis ---

def get_gemini_client(api_key: str):
    """
    Initializes the Generative Model using the standard modern SDK pattern.
    
    This pattern ensures the Client is configured correctly and the GenerativeModel
    class is used, which is the current required class name.
    """
    # 1. Initialize the Client with the API key.
    client = genai.Client(api_key=api_key)
    
    # Try several ways to obtain a model object (works across versions of the SDK):
    # Use a recent supported model by default. The runtime environment lists
    # newer Gemini models such as 'gemini-2.5-flash', so default to that.
    model_name = "gemini-2.5-flash"

    # 1) If client.models supports subscription (older code assumed dict-like access)
    try:
        return client.models[model_name]
    except Exception:
        pass

    # 2) If client.models exposes a get() helper
    try:
        models = getattr(client, "models", None)
        if models is not None and hasattr(models, "get"):
            m = models.get(model_name)
            if m is not None:
                return m
    except Exception:
        pass

    # 3) If the client itself exposes a get_model() helper
    if hasattr(client, "get_model"):
        try:
            return client.get_model(model_name)
        except Exception:
            pass

    # 4) If none of the above returned a model object, return a small adapter that
    #    will call the SDK's models.generate_content(...) method with the model name.
    class _ModelAdapter:
        def __init__(self, client, model_name):
            self._client = client
            self._model_name = model_name

        def generate_content(self, prompt):
            # Many newer SDKs expose generation at client.models.generate_content(...)
            if hasattr(self._client, "models") and hasattr(self._client.models, "generate_content"):
                # the SDK expects 'contents' not 'prompt'
                return self._client.models.generate_content(model=self._model_name, contents=prompt)
            # As a last resort, try client.generate (some SDKs accept model=..)
            if hasattr(self._client, "generate"):
                return self._client.generate(model=self._model_name, contents=prompt)
            raise RuntimeError("Gemini client does not support generate_content in this SDK version")

    return _ModelAdapter(client, model_name)


def analyze_lyrics(lyrics: str, config_path: str = "config.json") -> Dict[str, Any]:
    cfg = load_config(config_path)
    api_key = cfg.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY missing in config.json")
    
    model = get_gemini_client(api_key)

    prompt = f"""
You are an AI media composer.

Analyze the following lyrics and return JSON with these keys:
- global_mood (string)
- dominant_emotion (string)
- emotion_intensity (float 0-1)
- emotion_keywords (list of 3-5 words)
- recommended_bpm (integer)
- color_palette (list of 3 HEX codes)
- music_prompt (1-sentence music style description)
- video_prompt (1-sentence visual description)

{f"The target style is {'' if not lyrics else ''}." if False else ""}

Lyrics:
{lyrics}

Return ONLY valid JSON, no explanation.
"""
    # The SDK has changed shape between releases. Try multiple generate() helpers
    resp = None
    # If model has a generate_content method (original code path)
    if hasattr(model, "generate_content"):
        resp = model.generate_content(prompt)
    # Some SDK variants use generate() or generate_text()
    elif hasattr(model, "generate"):
        resp = model.generate(prompt)
    elif hasattr(model, "generate_text"):
        # Some clients expect model name passed in
        try:
            resp = model.generate_text(prompt)
        except TypeError:
            # maybe the object is the client and expects model=... param
            resp = model.generate_text(model=getattr(model, "_fallback_model_name", None) or "gemini-2.5-flash", prompt=prompt)
    else:
        # Perhaps get_gemini_client returned the raw client; try client.generate_text with model arg
        if hasattr(model, "generate_text"):
            resp = model.generate_text(model=getattr(model, "_fallback_model_name", "gemini-2.5-flash"), prompt=prompt)
        elif hasattr(model, "generate"):
            resp = model.generate(model=getattr(model, "_fallback_model_name", "gemini-2.5-flash"), prompt=prompt)
        else:
            raise RuntimeError("Unable to call generation on the Gemini client - unsupported SDK shape")

    # Extract the textual output in a robust way
    text = None
    if resp is None:
        raise RuntimeError("No response from Gemini model")

    # Common response shapes: resp.text, resp.output_text, resp.content, resp.result
    for attr in ("text", "output_text", "content", "result", "output"):
        if hasattr(resp, attr):
            text = getattr(resp, attr)
            break

    # If resp is a dict-like object
    if text is None:
        try:
            # some SDKs return a dict
            if isinstance(resp, dict):
                # try common keys
                for k in ("text", "output_text", "content", "result"):
                    if k in resp:
                        text = resp[k]
                        break
        except Exception:
            pass

    # Last resort: string conversion
    if text is None:
        text = str(resp)

    text = text.strip()

    # Clean output by removing potential markdown backticks (```json ... ```)
    if text.startswith("```"):
        text = text.lstrip("`").lstrip("json").strip()
    if text.endswith("```"):
        text = text.rstrip("`").strip()

    # ensure it's json
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        raise ValueError("Gemini output was not valid JSON: " + text)

    # persist a copy for downstream layers
    try:
        os.makedirs("outputs", exist_ok=True)
        with open("outputs/lyrics_analysis.json", "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
    except Exception:
        pass

    return data
