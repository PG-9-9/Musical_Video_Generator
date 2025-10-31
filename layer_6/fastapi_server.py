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


@app.get('/favicon.ico')
def favicon():
    # Return no-content for favicon requests to avoid 404 noise in logs
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
    _write_job(jobid, info)
    with open(log_path, 'w', encoding='utf-8') as lf:
        try:
            proc = subprocess.Popen(cmd, stdout=lf, stderr=subprocess.STDOUT, text=True)
            info['pid'] = proc.pid
            _write_job(jobid, info)
            # while running, also poll for a per-job progress file written by runners
            progress_path = os.path.join('outputs', f'progress_{info.get("job","unknown")}.json')
            while proc.poll() is None:
                # check for a progress file and update job info
                try:
                    if os.path.exists(progress_path):
                        with open(progress_path, 'r', encoding='utf-8') as pf:
                            try:
                                pj = json.load(pf)
                                # pj may contain {pct: int, stage: str}
                                if isinstance(pj, dict):
                                    info['progress'] = pj.get('pct')
                                    info['stage'] = pj.get('stage')
                                    _write_job(jobid, info)
                            except Exception:
                                pass
                except Exception:
                    pass
                time.sleep(0.5)
            info['returncode'] = proc.returncode
            info['status'] = 'finished' if proc.returncode == 0 else 'error'
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
    info = jobs.get(jobid)
    if not info:
        raise HTTPException(status_code=404, detail='Job not found')
    return info


@app.get('/jobs')
def list_jobs():
    return list(jobs.values())
