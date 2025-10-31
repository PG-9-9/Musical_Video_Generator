Layer 2 — Music generation & Beat analysis

Purpose
- Generate the short music track (MusicGen or fallback) and analyze tempo/beat positions so visuals can sync to the audio.

Key files
- `scripts/run_music_only.py` — runner that calls the music generation code and writes progress. It caps duration to 10 seconds by default.
- `music_gen.py` — model wrapper that tries to use MusicGen/transformers
- `beat_analysis.py` — analyzes WAV files to produce beat times and a tempo estimate.

Inputs & outputs
- Inputs: `semantic_timeline.json` (suggested BPM and prompts), optional `args` from UI (lyrics, desired duration).
- Outputs:
  - `outputs/music.wav` (the generated audio)
  - `outputs/beat_analysis.json` (tempo, beat timestamps)

Implementation notes
- `run_music_only.py` accepts a JSON args string and a jobid; when jobid is passed it writes per-job progress to `outputs/jobs/{jobid}.progress.json` so the server can mirror progress.
- Music generation will prefer GPU if code runs under a CUDA-enabled interpreter. If GPU is absent, generation falls back to CPU (much slower).
- If generation is very slow, ensure the FastAPI server and runners are started from a GPU-enabled Conda env 
