Layer 5 — Style applier & Frame styling

Purpose
- Build a per-frame style timeline, apply visual styles, and recompose the styled frames into a final video.

Key files
- `layer_5/style_applier.py` — builds style timeline and applies effects.
- `scripts/run_style_only.py` — runner that extracts frames and applies styles; it was rewritten to be robust and accept `runner_args['style']`.

Inputs & outputs
- Inputs: `outputs/animated.mp4`, `outputs/semantic_timeline.json`, optional `runner_args['style']` (UI token).
- Outputs: `outputs/styled_final.mp4`, `layer5_preview.mp4`/`.gif` and event files used for inspection.

Style mapping and override
- I added `override_style` support so a UI token like `synthwave` maps to an internal profile (e.g., `Euphoric`) and is applied uniformly or per-segment depending on the mapping.
- The style applier uses `dominant_emotion` and `emotion_intensity` as hints to bias palette selection and effect strength.

What I changed
- Rewrote `run_style_only.py` to extract frames via MoviePy or fallback methods, write progress updates (10/20/50/100), and honor the `style` override passed from the UI.

Practical notes
- Styling can be CPU-bound depending on the effects; previews (`layer5_preview.mp4`) are helpful before composing the full final MP4.
