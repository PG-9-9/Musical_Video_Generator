Layer 0 — Media & Model Helpers

Purpose
- This layer contains low-level helpers I use across the pipeline: model wrappers, audio I/O helpers, and robust media read/write code. I keep the code here defensive so higher layers can assume consistent behavior.

Where the code lives
- Top-level files used by L0: `music_gen.py`, `video_gen.py`, `composer.py`, `app.py`, `gemini_utils.py`.

What I expect this layer to provide
- Stable ways to write audio (explicit tensor → WAV conversions).
- Safe video read/write helpers (MoviePy or imageio), with fallbacks where features differ between library versions.
- Small wrappers that prefer GPU when available: code checks that the FastAPI server (or runner) was started under a CUDA-capable Python interpreter and uses that device for model inference.

Inputs & Outputs
- Inputs: model prompts, raw parameters (sample rate, duration), existing media files when requested.
- Outputs: WAV files, temporary media artifacts, helper objects (e.g., model wrappers) consumed by higher layers.

Notes on reliability
- If ffmpeg is missing from PATH, some MoviePy operations fall back to slower or less robust implementations — I added checks to ignore zero-sized files to avoid browser range errors.
- Always start the FastAPI server with the environment that has CUDA if you want GPU inference: e.g. `conda activate musical_v_new` then start the server so spawned runners inherit the same interpreter.

Developer checklist
- If you add a new model wrapper here, export a small clear function (synchronous) that takes inputs and writes a deterministic file path (so callers don't need to handle device setup).
