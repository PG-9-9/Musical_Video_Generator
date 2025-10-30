# 10s Animated Musical Video Generator (with Gemini)

This project shows an end-to-end pipeline that:

1. Takes **lyrics** as input
2. Uses **Gemini** to analyze mood, BPM, and produce **music + video prompts**
3. Generates **placeholder music** (pydub) and **placeholder video** (moviepy)
4. Adds **word-by-word subtitles** on top of the video
5. Exports a final **MP4**

> You can replace the placeholder generators with real services (Mubert, Pika, RunwayML, AnimateDiff, SVD).

## Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Then create a `config.json`:

```json
{
  "GEMINI_API_KEY": "YOUR_GEMINI_API_KEY",
  "MUBERT_API_KEY": "",
  "VIDEO_API_ENDPOINT": ""
}
```

## Run CLI

```bash
python main.py
```

Output will be in `outputs/final.mp4`.

## Run UI

```bash
streamlit run app.py
```
