Layer 6 — FastAPI job server and Dashboard

Purpose
- A small job manager and static dashboard that launches per-step scripts, captures logs, watches per-job progress, and serves final outputs for preview.

Key files
- `layer_6/fastapi_server.py` — job server and watcher.
- `layer_6/templates/index.html` — simple Jinja2 template for the dashboard.
- `layer_6/static/dashboard.js` and `styles.css` — frontend logic and styling.

How jobs run
- HTTP `POST /start` with body `{ job: 'full'|'music'|'anim'|'style'|'demo', args: {...} }` returns a `jobid`.
- The server launches the appropriate script as a subprocess and writes `outputs/jobs/{jobid}.log` and mirrors progress into `outputs/jobs/{jobid}.json`.

Progress contract
- Runners should accept a JSON args string and a final `jobid` CLI arg. When provided, runners write `outputs/jobs/{jobid}.progress.json` with `{'pct': <int>, 'stage': <str>}` updates.
- The server prefers that per-job progress path and mirrors `pct`/`progress` into the job JSON so the dashboard displays accurate, job-scoped progress.

Robustness & niceties I implemented
- Initial progress set to 1 when job is queued so UI shows immediate activity.
- Heartbeat nudger: if no progress update for 12s the server gently increments progress (up to 95) so the UI doesn't look frozen during long model runs.
- On completion the server sets `progress=100` and attempts to extract a companion WAV (e.g., `final_with_audio.wav`) from final MP4s using `ffmpeg` or a MoviePy fallback; this helps browser playback and diagnostics.
- The dashboard JS prefers `final_with_audio.mp4` when picking the final video to display.

Endpoints
- `GET /api/outputs` — returns a list of media files under `outputs/` for the dashboard to consume.
- `GET /jobs/{jobid}` — returns mirrored job metadata (reads on-disk file to show fresh updates).
- `GET /jobs/{jobid}/logs` — return last N log lines.

Developer notes
- Start the server with the Python interpreter from your desired Conda env (so spawned runners inherit CUDA):
```cmd
conda activate musical_v_new
python -m uvicorn layer_6.fastapi_server:app --host 127.0.0.1 --port 8000
```
- If a runner is silent but the job is active (e.g., model generating), the heartbeat will nudge progress shown in the UI; real runner progress should still be written by the runners for correctness.
