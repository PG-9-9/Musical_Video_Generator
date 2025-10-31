Layer 5 — Style applier & Frame styling

Purpose
- Build a per-frame style timeline, apply visual styles, and recompose the styled frames into a final video.

Key files
- `layer_5/style_applier.py` — builds style timeline and applies effects.
- `scripts/run_style_only.py` — runner that extracts frames and applies styles; it was rewritten to be robust and accept `runner_args['style']`.

Inputs & outputs
- Primary inputs (produced by Layer 3 / Layer 4):
	- `outputs/frames/frame_0000.png`, `frame_0001.png`, ... — produced by Layer 4 extractor (preferred).
	- `outputs/frame_timestamps.json` — the canonical frame → time mapping from Layer 4.
	- `outputs/semantic_timeline.json` — to map segments to frames.
	- optional `runner_args['style']` (UI token).
- Outputs: `outputs/styled_final.mp4`, `layer5_preview.mp4`/`.gif` and event files used for inspection.

Style mapping and override
- I added `override_style` support so a UI token like `synthwave` maps to an internal profile (e.g., `Euphoric`) and is applied uniformly or per-segment depending on the mapping.
- The style applier uses `dominant_emotion` and `emotion_intensity` as hints to bias palette selection and effect strength.
- Rewrote `run_style_only.py` to prefer reading extracted frames from `outputs/frames/` (Layer 4). If frames are absent, the runner falls back to extracting frames from `outputs/animated.mp4` itself.

