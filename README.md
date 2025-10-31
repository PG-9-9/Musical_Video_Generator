# Musical Video Generator — README

Hi — I built this repo as a small, layered pipeline that turns short lyrics into a tiny lyric video. I write these notes as if I'm sitting next to you: casual, clear, and to-the-point. Below I explain each layer (L0–L6), how they connect, useful commands, and what to do when things go sideways.

## Quick summary

- The project is split into layers so each concern is isolated and testable.
- Layers L0..L5 are the media pipeline: audio, analysis, animation, styling, and composition.
- Layer 6 is a small FastAPI job server + dashboard that launches jobs and shows progress and outputs.
- I prefer `final_with_audio.mp4` as the canonical lyric-video output; the dashboard will show it when available.
- Generated audio clips are capped to 10 seconds by default to keep runs fast and predictable.

## Files and structure (high level)

Root files you care about:
- `main.py` — runs the whole pipeline (lyrics → video) end-to-end.
- `app.py`, `composer.py`, `music_gen.py`, `video_gen.py` — lower-level helpers and L0 implementations.
- `scripts/` — per-step runner scripts you can call directly:
  - `scripts/run_music_only.py`
  - `scripts/run_animation_only.py`
  - `scripts/run_style_only.py`
  - `scripts/generate_demo_assets.py`
- `layer_3/animator.py`, `layer_5/style_applier.py` — important L3/L5 modules.
- `layer_6/fastapi_server.py` — the job server and static dashboard.
- `layer_6/static/` and `layer_6/templates/` — dashboard HTML/CSS/JS.
- `outputs/` — where media, logs, and job metadata are written.

## The layers — what I mean by L0..L6 (and why)

I split the pipeline into layers because it makes debugging and iteration much easier.

- L0 — low-level media I/O and model hooking
  - This is where model wrappers and direct audio/video helpers live.
  - `music_gen.py` and `video_gen.py` live here: they abstract over different MusicGen/backends and MoviePy/FFmpeg quirks.
  - Nuance: different environments may have different audio libraries installed (torch, audiocraft, transformers). I try fallbacks and explicit `.wav` writes to avoid ambiguous tensor-handling errors.

- L1 — semantic timeline / lyric analysis
  - Converts lyrics into a timeline of events (phrases, verse/chorus markers) and a small Gemini analysis (`lyrics_analysis.json`) that suggests mood, BPM, color palette.
  - Nuance: this file drives both music prompts and video prompts, so any change in the timeline ripples through later layers.

- L2 — beat/tempo analysis
  - Produces `beat_analysis.json` containing beat positions and tempo estimates the animator uses to sync visuals to audio.
  - Nuance: if you feed in pre-generated audio, L2 will analyze it; when the MusicGen step runs, L2 runs after a music placeholder is created.

- L3 — animator (visual timeline → animated.mp4)
  - Uses the semantic timeline and beat analysis to render a frame sequence and a motion plan.
  - Nuance: I added the ability for per-segment color overrides (`_color_rgb_override`) and a high-level `config['style']` option mapped from the dashboard tokens.

- L4 — frame extraction & staging
  - Extracts frames from the raw animation and prepares them for styling. This helps decouple the styling step (which can be slow) from the animator.

- L5 — style applier (frame-by-frame stylistic transform)
  - Applies a style timeline (generated from the semantic timeline) to frames and recombines them into a `styled_final.mp4`.
  - Nuance: `build_style_timeline` supports `override_style` so the dashboard's simple tokens (e.g., `synthwave`) map to internal profiles.

- L6 — job server + dashboard (FastAPI)
  - Starts jobs (runs the per-step scripts or `main.py`), watches job progress, writes `outputs/jobs/{jobid}.json` and `{jobid}.log`.
  - Important behavior I added:
    - Runners accept a `jobid` argument and write `outputs/jobs/{jobid}.progress.json` with `pct` or `progress` and optional `stage` fields.
    - The server prefers per-job progress files, mirrors progress into the on-disk job metadata, and writes a short heartbeat if the runner is silent for >12s to keep the UI alive.
    - After a job completes, the server tries to extract audio from `final`-like MP4s into WAVs (prefers `ffmpeg` on PATH, falls back to MoviePy) so the dashboard can present a dedicated audio control.

## How the pieces connect (simple flow)

1. Start a job (the dashboard POSTs to `/start` or you run `python main.py`).
2. L1 produces `semantic_timeline.json` and `lyrics_analysis.json` (Gemini analysis).
3. L2 writes `beat_analysis.json`.
4. L3 writes `animated.mp4` (frame rendering).
5. L4 extracts frames and stages them for styling.
6. L5 applies styles and writes `styled_final.mp4`.
7. Composer step (orchestrator) mixes `music.wav` with the final video to produce `final_with_audio.mp4` (and the server will try to extract `final_with_audio.wav`).
8. `outputs/pipeline_outputs.json` contains a summary manifest.

## Running locally (Windows / cmd.exe examples)

I usually do development in a Conda environment. If you have a GPU-enabled env, start the server in that env so spawned runners inherit GPU access (MusicGen and model-based steps will then use CUDA).

Activate your env (example):

```cmd
conda activate musical_v_new
cd F:\Projects\Musical_Video_Generator
```

Start the FastAPI dashboard server (development):

```cmd
python -m uvicorn layer_6.fastapi_server:app --host 127.0.0.1 --port 8000 --reload
```

Open the dashboard: http://127.0.0.1:8000/dashboard

Start a full run from the dashboard or run a step directly from the repo if you prefer CLI:

```cmd
# run the full pipeline (same as pressing Full in dashboard)
python main.py

# or run a single stage (music only):
python scripts\run_music_only.py "{\"lyrics\":\"My short lyric\", \"duration\": 8}"

# run with jobid so server can track progress (example uses a real jobid when launched by the server)
python scripts\run_music_only.py "{\"lyrics\":\"Hi\"}" 1234-abcd-5678
```

Notes:
- Per-step scripts accept a JSON arg string followed by an optional `jobid`. When the `jobid` is provided, the runner writes `outputs/jobs/{jobid}.progress.json` so the server and UI can follow progress.
- Music generation requests longer than 10s are capped to 10s automatically.

## Outputs folder — what you'll see

`outputs/` typically contains:
- `music.wav`, `final_with_audio.mp4`, `final_with_audio.wav` (if the server extracted audio), `styled_final.mp4`, `animated.mp4`.
- `semantic_timeline.json`, `beat_analysis.json`, `pipeline_outputs.json`.
- `outputs/jobs/{jobid}.json`, `{jobid}.progress.json`, `{jobid}.log` for each run started by the server.

If you see zero-byte files in `outputs/`, delete them and re-run — zeros often come from failed or partial writes.

## Troubleshooting — common issues and how I usually debug

1. No audio in browser dashboard but audio exists on disk
   - The dashboard prefers `final_with_audio.mp4`. If playback seems muted, try opening `outputs/final_with_audio.mp4` directly in a new tab (I added a small button in the UI for earlier debugging).
   - The server now extracts a `final_with_audio.wav` companion file (using `ffmpeg` if available). If that `.wav` exists, the standalone audio player should work. If the browser still disables volume controls, try the direct-open link or download the file and play locally.

2. Progress stuck at some percent (e.g., 30)
   - Short answer: the runners should be writing `outputs/jobs/{jobid}.progress.json`; check that file and the runner log `outputs/jobs/{jobid}.log` for clues.
   - The server writes a gentle heartbeat if there is no progress update in ~12 seconds. If the runner is truly silent for a long time, it's likely doing heavy CPU work (MusicGen on CPU). Start the FastAPI server under the GPU-enabled Conda env to have child processes use CUDA.

3. MoviePy / FFmpeg complaints (e.g., "bytes wanted but 0 bytes read")
   - These often come from mismatched fps or truncated writes; MoviePy will still continue and usually produces usable MP4s. If you see repeated warnings, check available disk space and that no process is blocking the file.

4. Models running on CPU unexpectedly
   - Make sure you started the FastAPI server using the Conda environment that has CUDA-enabled PyTorch. Child processes inherit the Python executable used by the server. Example:

```cmd
conda activate musical_v_new
python -m uvicorn layer_6.fastapi_server:app --host 127.0.0.1 --port 8000
```

Then start jobs from that server's dashboard.

## Developer notes and nuances (things I learned while building this)

- Per-job progress is important — global progress files clash when multiple people or jobs run at once. I added `outputs/jobs/{jobid}.progress.json` and the server prefers those files.
- Browser audio controls can be finicky. I implemented a server-side audio extraction step (uses `ffmpeg` when present) so we have a simple WAV fallback for the UI.
- I cap music generation to 10s by default — it keeps iteration fast and reduces memory/load surprises.
- Style tokens in the dashboard map to internal profiles (synthwave -> an internal profile name). I added `override_style` hooks so a single dashboard token can be applied uniformly if you want.
- The animator supports per-segment color overrides via `_color_rgb_override` keys inside the semantic timeline; the style applier will respect those when present.

## Example workflows I use

- Quick demo generation
```cmd
python scripts\generate_demo_assets.py
# then start the server and open the dashboard to see demo media
```

- Full run via server (recommended for dashboard UX)
  - Start server in GPU env (if you have one)
  - Open http://127.0.0.1:8000/dashboard and press "Full"

- Run only the animation step (useful for fast visual iteration)
```cmd
python scripts\run_animation_only.py "{\"style\": \"synthwave\"}" my-jobid-123
```

## Extending and contributing

- If you want to add a new style or mapper, modify `layer_5/style_applier.py` and add the mapping for the dashboard token in `layer_6/static/dashboard.js` (the simple tokens map to internal names in that module).
- If you add heavy GPU work, favor starting the server in a GPU-enabled environment so child processes inherit the CUDA-visible devices.

## Quick debugging checklist (what I ask first when something fails)

1. Check `outputs/jobs/{jobid}.log` for the job.
2. Check `outputs/jobs/{jobid}.progress.json` — it should contain `pct` or `progress` and `stage`.
3. Confirm `final_with_audio.mp4` exists and is non-empty. If it does, the server should also extract `final_with_audio.wav`.
4. If models are slow, verify CUDA is visible to Python (run `python -c "import torch; print(torch.cuda.is_available(), torch.cuda.device_count())"` in the env used to start the server).

## Known limitations

- The UI is intentionally minimal. It polls server endpoints and relies on on-disk state. It is not hardened for multi-user concurrency beyond per-job files.
- Audio extraction requires `ffmpeg` in PATH for the cleanest results; otherwise MoviePy is attempted as a fallback.
- Some MoviePy warnings about frames/bytes may appear but often the output is still valid. If you see repeated issues, try running the pipeline with smaller sizes for debugging.

## Final notes — my goals for this repo

I built this as a small, practical system that demonstrates an end-to-end lyric → music → video flow, with an emphasis on debuggability and layered design. I like keeping short iteration cycles (hence the 10s cap) and explicit progress reporting so the UX is pleasant even when models take a while.

If you want, I can:
- Commit this README into the repo (I already wrote it as `README.md` in the project).
- Add icons to the dashboard call-to-actions.
- Add a small set of unit tests for the `outputs` selection logic and the per-job progress mirror.

Tell me which of those you'd like next.
