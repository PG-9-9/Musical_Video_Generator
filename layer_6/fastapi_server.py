from fastapi import FastAPI, BackgroundTasks, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.responses import Response
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import subprocess
import uuid
import os
import threading
import time
import json
from typing import Dict
from fastapi.middleware.cors import CORSMiddleware
import shutil

app = FastAPI(title="MVG Job Server")

# Allow cross-origin requests from Streamlit/dev UI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get('/')
def read_root():
    return {"status": "ok", "endpoints": ["/start", "/jobs", "/jobs/{jobid}", "/jobs/{jobid}/logs"]}

# Mount static assets and outputs for easy browsing
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), 'templates'))
static_dir = os.path.join(os.path.dirname(__file__), 'static')
if os.path.isdir(static_dir):
    app.mount('/static', StaticFiles(directory=static_dir), name='static')

# serve outputs folder directly for playback/download
app.mount('/outputs', StaticFiles(directory='outputs'), name='outputs')


@app.get('/dashboard', response_class=HTMLResponse)
def dashboard_page(request: Request):
    return templates.TemplateResponse('index.html', {"request": request, "server_url": "http://127.0.0.1:8000"})


@app.get('/api/outputs')
def list_outputs():
    root = 'outputs'
    if not os.path.isdir(root):
        return JSONResponse({"files": []})
    # Only return media files that are useful for the dashboard (avoid logs, temp files, etc.)
    allowed_exts = {'.mp4', '.webm', '.wav', '.mp3', '.ogg'}
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        # skip job logs directory
        if os.path.abspath(dirpath).startswith(os.path.abspath(JOBS_DIR)):
            continue
        for fn in filenames:
            # include pipeline_outputs.json explicitly
            if fn == 'pipeline_outputs.json':
                rel = os.path.relpath(os.path.join(dirpath, fn), root)
                files.append(rel.replace('\\', '/'))
                continue
            _, ext = os.path.splitext(fn)
            if ext.lower() not in allowed_exts:
                continue
            full = os.path.join(dirpath, fn)
            try:
                size = os.path.getsize(full)
            except Exception:
                size = 0
            # ignore zero-sized/incomplete files so browser won't request bad ranges
            if size == 0:
                continue
            rel = os.path.relpath(full, root)
            files.append(rel.replace('\\', '/'))
    return JSONResponse({"files": sorted(files)})


from fastapi.responses import FileResponse


@app.get('/favicon.ico')
def favicon():
    # Serve the musical-note.png from the static folder as favicon if present
    p = os.path.join(static_dir, 'musical-note.png')
    if os.path.exists(p):
        return FileResponse(p, media_type='image/png')
    return Response(status_code=204)


@app.on_event('startup')
def ensure_demo_assets():
    """Ensure demo assets exist on server startup so dashboard shows playable demo by default."""
    # quick check for a few key demo files
    demo_needed = False
    wanted = [
        os.path.join('outputs', 'demo_music.wav'),
        os.path.join('outputs', 'semantic_timeline.json'),
        os.path.join('outputs', 'animated.mp4'),
        os.path.join('outputs', 'styled_final.mp4'),
    ]
    for p in wanted:
        if not os.path.exists(p) or os.path.getsize(p) == 0:
            demo_needed = True
            break
    if demo_needed:
        try:
            py = os.path.abspath(os.sys.executable)
            subprocess.run([py, os.path.join('scripts', 'generate_demo_assets.py')], check=True)
            print('Demo assets generated at startup.')
        except Exception as e:
            print('Failed to generate demo assets at startup:', e)

JOBS_DIR = os.path.join("outputs", "jobs")
os.makedirs(JOBS_DIR, exist_ok=True)

jobs: Dict[str, Dict] = {}


class StartRequest(BaseModel):
    job: str
    args: dict = {}


def _write_job(jobid, info):
    with open(os.path.join(JOBS_DIR, f"{jobid}.json"), "w", encoding="utf-8") as f:
        json.dump(info, f, indent=2)


def _tail_file(path, n=100):
    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
            return ''.join(lines[-n:])
    except Exception:
        return ''


def _run_process_and_watch(jobid, cmd):
    log_path = os.path.join(JOBS_DIR, f"{jobid}.log")
    info = jobs[jobid]
    info['status'] = 'running'
    info['pid'] = None
    # mark initial progress so UI sees an update immediately
    try:
        info['progress'] = 1
        info['stage'] = 'starting'
    except Exception:
        pass
    _write_job(jobid, info)
    with open(log_path, 'w', encoding='utf-8') as lf:
        try:
            proc = subprocess.Popen(cmd, stdout=lf, stderr=subprocess.STDOUT, text=True)
            info['pid'] = proc.pid
            _write_job(jobid, info)
            # while running, also poll for a per-job progress file written by runners
            job_progress_path = os.path.join('outputs', 'jobs', f'{jobid}.progress.json')
            legacy_progress_path = os.path.join('outputs', f'progress_{info.get("job","unknown")}.json')
            last_seen_pct = info.get('progress')
            last_seen_time = time.time()
            while proc.poll() is None:
                # prefer job-scoped progress file, fall back to legacy progress_{job}.json
                updated = False
                for progress_path in (job_progress_path, legacy_progress_path):
                    try:
                        if os.path.exists(progress_path):
                            with open(progress_path, 'r', encoding='utf-8') as pf:
                                try:
                                    pj = json.load(pf)
                                except Exception:
                                    pj = None
                            if isinstance(pj, dict):
                                # support either 'pct' or 'progress' as the numeric key
                                pct = pj.get('pct') if pj.get('pct') is not None else pj.get('progress')
                                try:
                                    if pct is not None:
                                        pct_int = int(pct)
                                        if pct_int != info.get('progress'):
                                            info['progress'] = pct_int
                                            last_seen_pct = pct_int
                                            last_seen_time = time.time()
                                            updated = True
                                except Exception:
                                    # leave progress unchanged if parsing fails
                                    pass
                                # stage/key may be present under various names
                                new_stage = pj.get('stage') or pj.get('status')
                                if new_stage:
                                    info['stage'] = new_stage
                                _write_job(jobid, info)
                                # once we've read the most-preferred file, break to sleep
                                break
                    except Exception:
                        # ignore file read issues and try next path
                        pass

                # if we haven't seen an update in 12s, emit a light heartbeat so UI shows activity
                if not updated and (time.time() - last_seen_time) > 12:
                    try:
                        cur = int(info.get('progress') or 0)
                        # gently nudge progress forward but never exceed 95 before finish
                        if cur < 95:
                            info['progress'] = min(95, cur + 1)
                            info['stage'] = (info.get('stage') or 'generating') + ' (heartbeat)'
                            _write_job(jobid, info)
                            last_seen_time = time.time()
                    except Exception:
                        pass

                time.sleep(0.5)
            info['returncode'] = proc.returncode
            info['status'] = 'finished' if proc.returncode == 0 else 'error'
            # ensure progress is set to 100 on process completion so UI finishes the bar
            try:
                info['progress'] = 100
            except Exception:
                pass
            # After the runner completes, attempt to ensure a companion audio (.wav) exists
            # for any final MP4s (so the dashboard can surface a dedicated audio player).
            try:
                # look for final-like files in outputs
                out_root = 'outputs'
                candidates = []
                for fn in os.listdir(out_root) if os.path.isdir(out_root) else []:
                    if fn.lower().endswith('.mp4') and ('final' in fn.lower() or 'with_audio' in fn.lower()):
                        candidates.append(os.path.join(out_root, fn))
                for mp4 in candidates:
                    try:
                        base = os.path.splitext(os.path.basename(mp4))[0]
                        wav_path = os.path.join(out_root, f"{base}.wav")
                        # if WAV already exists and non-empty, skip
                        if os.path.exists(wav_path) and os.path.getsize(wav_path) > 0:
                            continue
                        # prefer ffmpeg if available
                        ff = shutil.which('ffmpeg')
                        if ff:
                            # extract audio to WAV (PCM 16-bit) for broad browser support
                            subprocess.run([ff, '-y', '-i', mp4, '-vn', '-acodec', 'pcm_s16le', '-ar', '32000', '-ac', '1', wav_path], check=True)
                        else:
                            # fallback to moviepy if installed in environment
                            try:
                                from moviepy.editor import VideoFileClip
                                with VideoFileClip(mp4) as clip:
                                    if clip.audio:
                                        clip.audio.write_audiofile(wav_path, fps=32000)
                            except Exception:
                                # if this fails, just continue silently; dashboard will still try video element
                                pass
                    except Exception:
                        pass
            except Exception:
                pass
        except Exception as e:
            info['status'] = 'error'
            with open(log_path, 'a', encoding='utf-8') as lf2:
                lf2.write('\nException starting process:\n')
                lf2.write(str(e))
        finally:
            info['finished_at'] = time.time()
            _write_job(jobid, info)


@app.post('/start')
def start_job(req: StartRequest):
    job = req.job
    jobid = str(uuid.uuid4())
    log_path = os.path.join(JOBS_DIR, f"{jobid}.log")
    info = {
        'id': jobid,
        'job': job,
        'status': 'queued',
        'progress': 0,
        'stage': 'queued',
        'created_at': time.time(),
        'args': req.args,
        'log_path': log_path,
    }
    jobs[jobid] = info
    _write_job(jobid, info)

    # determine command
    py = os.path.abspath(os.sys.executable)
    if job == 'full':
        cmd = [py, 'main.py']
    elif job == 'music':
        cmd = [py, os.path.join('scripts', 'run_music_only.py')]
    elif job == 'anim':
        cmd = [py, os.path.join('scripts', 'run_animation_only.py')]
    elif job == 'style':
        cmd = [py, os.path.join('scripts', 'run_style_only.py')]
    elif job == 'demo':
        cmd = [py, os.path.join('scripts', 'generate_demo_assets.py')]
    else:
        raise HTTPException(status_code=400, detail=f"Unknown job type: {job}")

    # If the request included args, pass them as a single JSON string argument to the runner
    try:
        # Only pass runner args to the smaller per-step scripts; don't append to main.py (full pipeline)
        if req.args and job != 'full':
            cmd.append(json.dumps(req.args))
        # Also pass the jobid as the final argument so runners can write job-scoped progress
        if job != 'full':
            cmd.append(jobid)
    except Exception:
        pass

    # run in background thread
    t = threading.Thread(target=_run_process_and_watch, args=(jobid, cmd), daemon=True)
    t.start()
    return {'jobid': jobid}


@app.get('/start')
def start_job_get(job: str, args: str = None):
    """Convenience GET endpoint for quick testing from a browser.
    Use ?job=demo or ?job=music etc. For real usage prefer POST /start with JSON.
    """
    # Build a StartRequest and delegate to the POST handler
    try:
        parsed_args = json.loads(args) if args else {}
    except Exception:
        parsed_args = {}
    req = StartRequest(job=job, args=parsed_args)
    return start_job(req)


@app.get('/jobs/{jobid}/logs')
def get_logs(jobid: str, tail: int = 200):
    info = jobs.get(jobid)
    if not info:
        raise HTTPException(status_code=404, detail='Job not found')
    log_path = info.get('log_path')
    txt = _tail_file(log_path, n=tail)
    return {'jobid': jobid, 'logs': txt, 'status': info.get('status')}


@app.get('/jobs/{jobid}')
def get_job(jobid: str):
    # Prefer returning the on-disk job file which reflects the latest writes.
    job_file = os.path.join(JOBS_DIR, f"{jobid}.json")
    if os.path.exists(job_file):
        try:
            with open(job_file, 'r', encoding='utf-8') as jf:
                info = json.load(jf)
                return info
        except Exception:
            pass
    info = jobs.get(jobid)
    if not info:
        raise HTTPException(status_code=404, detail='Job not found')
    return info


@app.get('/jobs')
def list_jobs():
    return list(jobs.values())
