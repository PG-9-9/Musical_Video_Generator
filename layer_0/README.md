Layer 0 — Media & Model Helpers

Purpose
- This layer contains low-level helpers I use across the pipeline: model wrappers, audio I/O helpers, and robust media read/write code. 
- Top-level files used by L0: `music_gen.py`, `video_gen.py`, `composer.py`, `app.py`, `gemini_utils.py`.

What I expect this layer to provide
- Stable ways to write audio (explicit tensor → WAV conversions).
- Safe video read/write helpers (MoviePy or imageio), with fallbacks where features differ between library versions.
- Small wrappers that prefer GPU when available: 

Inputs & Outputs
- Inputs: model prompts, raw parameters (sample rate, duration), existing media files when requested.
- Outputs: WAV files, temporary media artifacts, helper objects (e.g., model wrappers) consumed by higher layers.
