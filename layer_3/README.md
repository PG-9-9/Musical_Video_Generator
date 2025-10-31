Layer 3 — Animator (semantic timeline → animated frames/video)

Purpose
- Turn a semantic timeline into a moving sequence. The animator interprets segment prompts, palettes and beat positions and emits an animated video (`outputs/animated.mp4`) plus an events file used for debugging.

Key files
- `layer_3/animator.py` — main animator code invoked by `scripts/run_animation_only.py`.
- `scripts/run_animation_only.py` — lightweight runner that accepts JSON args and a jobid so it can write progress.

Inputs & outputs
- Inputs: `outputs/semantic_timeline.json`, `outputs/beat_analysis.json`, optional `style` token.
- Outputs: `outputs/animated.mp4`, `outputs/layer3_events.json`.

Style integration
- Animator honors `config['style']` when present and supports a per-segment `_color_rgb_override` key. This allows the style applier to force palettes and guarantees deterministic visuals for given inputs.

Implementation notes
- The animator uses MoviePy (or imageio as available) to compose frames. It reports per-frame progress via MoviePy's own progress output and the runner writes job progress files.
- I added handling for `_color_rgb_override` to make palette application deterministic and to respond directly to the emotion-derived palette from the timeline.

Debug tips
- If you see frame warnings from MoviePy, inspect `outputs/animated.mp4` and `outputs/layer3_events.json` — the events file helps map frames to timeline segments.
- To test style overrides, run `python scripts/run_animation_only.py "{\"style\":\"synthwave\"}" <jobid>` and check that segment palettes change.
