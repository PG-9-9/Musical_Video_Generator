Layer 4 — Frame extraction & intermediate assets

Purpose
- Extracts per-frame image assets and timestamps from the raw animator output (`outputs/animated.mp4`) and writes small metadata files that downstream styling and composition layers rely on. 
- Splitting extraction from style application keeps the pipeline modular. Styling often happens frame-by-frame and can be CPU or GPU heavy; having a dedicated layer to prepare frames allows re-running styling (Layer 5) without re-rendering the base animation.

Inputs & outputs
- Inputs:
  - `outputs/animated.mp4` — produced by Layer 3 (Animator)
  - `outputs/layer3_events.json` or `outputs/semantic_timeline.json` — optional, used to map frames back to timeline segments

- Primary outputs (written under `outputs/`):
  - `outputs/frames/frame_0000.png`, `frame_0001.png`, ... — zero-padded PNGs, sequential frame files used by styling.
  - `outputs/frame_timestamps.json` — JSON list of timestamps (seconds) for each extracted frame in the same order, e.g. `[0.0, 0.0417, ...]`.
  - `outputs/frame_info.json` — optional per-frame metadata (which timeline segment index the frame belongs to, emotion label, palette hints).

Implementation Notes

- Extraction logic can be invoked from `scripts/run_animation_only.py` or a dedicated extractor in `video_gen.py` / `layer_4/extractor.py` if present. The pipeline uses MoviePy or imageio to open `animated.mp4` and write frames.
- I use padded names `frame_0000.png` with 4+ digits to make ordering and globbing robust across platforms.
- `frame_timestamps.json` is the single source of truth for mapping frame index → time. The JSON array length equals the number of frame PNGs.
- If `layer3_events.json` is available, the extractor computes for each frame which timeline segment it belongs to (by comparing timestamps). It writes that mapping into `frame_info.json` as `{ frames: [{idx:0, t:0.0, segment:0}, ...], fps:24 }`.
- This mapping is used by Layer 5 to apply segment-level styles deterministically.

