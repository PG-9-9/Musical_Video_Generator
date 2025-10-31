Layer 1 — Semantic timeline & Emotion classifier

Purpose
- Turn lyric text into a structured semantic timeline and run an emotion classification step that informs visuals and music.

Key pieces
- `layer_1/emotion_classifier.py` — an adapter that tries a DistilBERT-based Hugging Face pipeline and falls back to a keyword classifier if transformers or model weights aren't available.
- `gemini_utils.py` (top-level helper) — used to run Gemini/LLM analysis that produces mood, color palette, music/video prompts and recommended BPM.
- Timeline writer — code in `main.py` or a small `semantic_timeline` helper writes `outputs/semantic_timeline.json`.

Emotion classifier details
- The classifier uses a controlled vocabulary: `['calm','sad','dark','romantic','hopeful','energetic','euphoric','neutral']`.
- If `transformers` and the DistilBERT models are present, the module loads a HF pipeline (tries `mrm8488/tiny-distilbert-finetuned-emotion` first, then `j-hartmann/emotion-english-distilbert`).
- If Hugging Face pipelines fail or aren't installed, the module falls back to a simple keyword-based classifier with deterministic labels and moderate default scores (0.6).

Data flow and outputs
- Inputs: lyric text string (from UI or `main.py`).
- Output: a small dict `{'label': <emotion_label>, 'score': <0..1>, 'backend': 'hf'|'fallback'}` returned by `classify_emotion(text)`.
- The timeline builder consumes this output and expands it into segment-level fields written to `outputs/semantic_timeline.json` (fields: `prompt`, `dominant_emotion`, `emotion_intensity`, `color_palette`, `recommended_bpm`).

Implementation notes 
- I normalize HF labels to the project's controlled vocabulary via a small mapping (joy -> euphoric, love -> romantic, sadness -> sad, anger/fear -> dark, etc.). If HF emits an unfamiliar label the code falls back to `neutral`.
- The `dominant_emotion` and `emotion_intensity` fields influence palette selection and effect strength in the animator and style applier.
