## Musical Video Generator — README

I built this project to turn short lyrics into a compact, shareable lyric video — with music, a semantic timeline, animated frames, and a final styled video you can play in a browser. I’ll walk you through how the repo is organized, how each layer contributes to the final output, and the practical commands I use to run and troubleshoot the pipeline.


## Quick summary

- Input: a short lyric (text). I keep generated clips short (max ~10s by default).
- Output: a final MP4 (usually `final_with_audio.mp4` or `final.mp4`) plus helper files under `outputs/`.
- How it runs: a layered pipeline (L0..L5) performs music, beat analysis, animation, styling and composition. Layer 6 is a small FastAPI dashboard I use to start jobs and view outputs.

## Project layout

Top-level files:

- `main.py` — runs the full pipeline end-to-end.
- `app.py`, `composer.py`, `music_gen.py`, `video_gen.py`, `gemini_utils.py` — low-level helpers and model wrappers.
- `scripts/` — lightweight per-step runners I use when I want to run just one layer (examples: `run_music_only.py`, `run_animation_only.py`, `run_style_only.py`, `generate_demo_assets.py`).
- `layer_3/`, `layer_5/` (and similar) — code for animator and style applier.
- `layer_6/fastapi_server.py` and `layer_6/static/` — the job server and the small dashboard UI.
- `outputs/` — everything the pipeline writes: audio, video, progress files and job metadata.

## The layers 

I organized the pipeline in layers so each step is clear and testable. Here’s the role I gave each layer and what to watch for.

L0 — Media & Model helpers
- What I do here: wrap low-level model code and media I/O. This includes MusicGen/transformer model wrappers, safe audio write paths, and reads/writes for MoviePy or imageio.
- Why it matters: model libraries and media backends change often. I added defensive code so the repo works across environments and falls back when some features are missing.

L1 — Semantic timeline
- What I do here: analyze the lyrics and produce a short semantic timeline and prompts. This is where I call the Gemini/analysis utility to extract mood, color palette, tempo suggestions, and a short scene prompt.
- Output: `outputs/semantic_timeline.json` with segment events and text prompts.

L2 — Music & beat analysis
- What I do here: generate short audio clips and analyze tempo/beat so animation can sync to the music.
- Notes: I cap music duration to ~10 seconds inside the `run_music_only.py` runner. If you want longer clips, we can change the cap, but short clips are easier to iterate on.
- Output: `outputs/music.wav`, `outputs/beat_analysis.json`.

L3 — Animator
- What I do here: turn the semantic timeline and beat metadata into an animated sequence. The animator creates visual events (color changes, basic motion, scene transitions) and writes `outputs/animated.mp4`.
- Style hooks: the animator accepts a high-level `style` token (synthwave, lo-fi, acoustic, cinematic) and can apply per-segment palette overrides.

L4/L5 — Frame styling & composition
- What I do here: extract frames, build a style timeline based on the semantic timeline, then apply style transforms (filters, palettes). The result is `outputs/styled_final.mp4` or an intermediate `layer5_preview.mp4`.

L5 (orchestrator) — final composition
- What I do here: combine styled frames, the generated audio, and any overlays into a single final video. In many runs the final file is `outputs/final.mp4` and I also produce `outputs/final_with_audio.mp4`.

L6 — Dashboard and job server
- What I do here: I use a small FastAPI app as a job manager and lightweight dashboard. It launches the step scripts as subprocesses, monitors their progress files, and serves `outputs/` for playback.


## Important files produced during a run

- `outputs/semantic_timeline.json` — events the animator uses.
- `outputs/beat_analysis.json` — tempo and beat markers.
- `outputs/animated.mp4` — the raw animation before styling.
- `outputs/styled_final.mp4` — styled video composed from frames.
- `outputs/final_with_audio.mp4` — preferred final lyric video (video + audio muxed together).
- `outputs/final_with_audio.wav` — companion WAV extracted by the server for playback fallback (if ffmpeg is available or MoviePy fallback works).
- `outputs/jobs/{jobid}.json` and `.log` — job metadata and captured logs.

## How to run the server and a job (Windows / cmd.exe)


1) Activate the Conda environment that has GPU support (if you want model runs on CUDA):

```cmd
conda activate musical_v_new
cd F:\Projects\Musical_Video_Generator
```

2) Start the FastAPI server (I use uvicorn). I run it with the Python interpreter of the environment so child processes inherit CUDA availability:

```cmd
python -m uvicorn layer_6.fastapi_server:app --host 127.0.0.1 --port 8000
```

3) Open the dashboard: http://127.0.0.1:8000/dashboard 

4) Check the `outputs/` folder or the job page (GET `/jobs/{jobid}`) for progress and logs.

In the command line, to run a single step directly, for example:

```cmd
# run only music step and pass simple args (JSON string)
python scripts\run_music_only.py "{\"lyrics\": \"my short text\"}" my-job-id
```

Note: the scripts accept a JSON args string followed by the jobid so they can write a per-job progress file.

## Extending or modifying the pipeline

- To tweak max clip length: edit `scripts/run_music_only.py` which enforces a 10s cap by default.
- To add a new style token: implement the mapping in `layer_5/style_applier.py` and make sure `layer_3/animator.py` honors `config['style']`.
- To add new dashboard behavior: `layer_6/static/dashboard.js` is small and straightforward; `layer_6/templates/index.html` is the Jinja template.

## My recommended quick checks when something goes wrong

1. Check the job log: `outputs/jobs/{jobid}.log`.
2. Check the per-job progress: `outputs/jobs/{jobid}.progress.json` and `outputs/jobs/{jobid}.json`.
3. If audio isn't playing in-browser, open `outputs/final_with_audio.wav` directly in a new tab or local player.
4. Ensure FastAPI server was started from a Conda env that has GPU access if you expect fast model runs.

## Final notes :)

I kept the pipeline intentionally modular so you can run, inspect, and iterate on individual layers.

