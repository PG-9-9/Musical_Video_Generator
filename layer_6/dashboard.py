import os
import json
import io
import streamlit as st
import plotly.graph_objects as go
import numpy as np
from pathlib import Path
import time

try:
    import librosa
except Exception:
    librosa = None


OUT_DIR = Path("outputs")


def load_json(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def load_audio(path: Path, sr=22050):
    if not path.exists() or librosa is None:
        return None, None
    y, sr = librosa.load(str(path), sr=sr, mono=True)
    return y, sr


def waveform_figure(y, sr, title="Waveform"):
    t = np.linspace(0, len(y) / sr, num=len(y))
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=t, y=y, mode="lines", line=dict(color="#1f77b4"), name="waveform"))
    fig.update_layout(title=title, xaxis_title="Time (s)", yaxis_title="Amplitude", height=250)
    return fig


def color_timeline_figure(segments, duration=10.0):
    fig = go.Figure()
    shapes = []
    for seg in segments:
        start = seg.get("start_sec", 0)
        end = seg.get("end_sec", start + 1)
        color = seg.get("color_hex") or seg.get("color") or "#777777"
        shapes.append(dict(type="rect", x0=start, x1=end, y0=0, y1=1, fillcolor=color, line=dict(width=0)))
    fig.update_layout(shapes=shapes, xaxis=dict(range=[0, duration], title="Time (s)"), yaxis=dict(visible=False), height=100)
    return fig


def simple_bar_keywords(timeline):
    # collect keywords across segments
    counts = {}
    for seg in timeline.get("segments", []):
        kws = seg.get("keywords") or seg.get("emotion_keywords") or []
        for k in kws:
            counts[k] = counts.get(k, 0) + 1
    items = sorted(counts.items(), key=lambda x: -x[1])[:30]
    if not items:
        return None
    labels, vals = zip(*items)
    fig = go.Figure([go.Bar(x=list(vals), y=list(labels), orientation="h")])
    fig.update_layout(title="Keyword counts (segments)", height=300)
    return fig


def draw_energy_curve(energy):
    if not energy:
        return None
    x = np.linspace(0, 10, num=len(energy))
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=energy, mode="lines+markers", name="energy", line=dict(color="#E03B8B")))
    fig.update_layout(title="Energy curve (RMS)", xaxis_title="Time (s)", height=250)
    return fig


def main():
    st.set_page_config(page_title="Layer 6 — Creative Studio", layout="wide")
    st.title("Layer 6 — AI Creative Studio Dashboard")

    # Sidebar controls
    st.sidebar.header("Controls")
    lyrics_input = st.sidebar.text_area("Lyrics (paste or type)", height=120)
    uploaded = st.sidebar.file_uploader("Or upload a .txt lyrics file", type=["txt"])
    if uploaded and not lyrics_input:
        try:
            lyrics_input = uploaded.read().decode("utf-8")
        except Exception:
            lyrics_input = None

    style_option = st.sidebar.selectbox("Style preset", ["synthwave", "lo-fi", "acoustic", "cinematic"], index=0)
    # allow 0 to mean 'unspecified' so default can be 0 while valid BPMs are 40-240
    bpm_hint = st.sidebar.number_input("BPM (optional)", min_value=0, max_value=240, value=0, step=1)

    st.sidebar.markdown("---")
    st.sidebar.markdown("Data files read from `outputs/` — re-run `main.py` to re-generate assets.")
    # Run pipeline controls (live streaming + per-layer runners)
    import subprocess, sys, time, shutil

    def stream_subprocess(cmd, log_area, file_watch=None):
        """Run cmd (list) and stream stdout/stderr into log_area (st.empty placeholder).
        Optionally pass file_watch: list of (path, callback) to call when file appears.
        """
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        except Exception as e:
            log_area.text_area("Pipeline output", f"Failed to start process: {e}")
            return 1
        buffer = []
        # non-blocking read loop
        while True:
            line = proc.stdout.readline()
            if line:
                buffer.append(line)
                # also echo to server console so cmd window sees progress
                try:
                    print(line, end='')
                except Exception:
                    pass
                # keep last ~2000 lines
                txt = "".join(buffer[-2000:])
                log_area.text_area("Pipeline output", txt, height=300)
            elif proc.poll() is not None:
                # process finished; drain remaining
                remaining = proc.stdout.read()
                if remaining:
                    buffer.append(remaining)
                txt = "".join(buffer[-2000:])
                log_area.text_area("Pipeline output", txt, height=300)
                break
            # check watched files
            if file_watch:
                for p, cb in list(file_watch):
                    try:
                        if os.path.exists(p):
                            cb(p)
                            file_watch.remove((p, cb))
                    except Exception:
                        pass
            time.sleep(0.05)
        return proc.returncode

    sidebar_log = st.sidebar.empty()
    # Buttons: full pipeline, per-layer, generate demo
    col_run_full = st.sidebar.button("Run full pipeline (may take minutes)")
    col_run_music = st.sidebar.button("Run music only (Layer 0)")
    col_run_anim = st.sidebar.button("Run animation only (Layer 3)")
    col_run_style = st.sidebar.button("Run style only (Layer 5)")
    col_gen_demo = st.sidebar.button("Generate demo assets")

    # small helpers to update UI when files appear
    def _mark_music(p):
        sidebar_log.text_area("Pipeline output", f"Music ready: {p}", height=300)
        try:
            st.experimental_rerun()
        except Exception:
            pass

    def _mark_anim(p):
        sidebar_log.text_area("Pipeline output", f"Animation ready: {p}", height=300)
        try:
            st.experimental_rerun()
        except Exception:
            pass

    def _mark_style(p):
        sidebar_log.text_area("Pipeline output", f"Styled video ready: {p}", height=300)
        try:
            st.experimental_rerun()
        except Exception:
            pass

    # Dispatch actions (use FastAPI job server if available)
    server_url = st.sidebar.text_input("Job server URL", value="http://127.0.0.1:8000")
    use_api = True
    try:
        import requests
    except Exception:
        use_api = False

    def start_job_via_api(job_name):
        try:
            resp = requests.post(f"{server_url}/start", json={"job": job_name}, timeout=5)
            if resp.status_code == 200:
                return resp.json().get('jobid')
            else:
                sidebar_log.text_area("Pipeline output", f"Server error: {resp.status_code} {resp.text}", height=300)
                return None
        except Exception as e:
            sidebar_log.text_area("Pipeline output", f"Failed to reach server: {e}", height=300)
            return None

    def poll_job_logs(jobid):
        try:
            while True:
                r = requests.get(f"{server_url}/jobs/{jobid}/logs", timeout=5)
                if r.status_code == 200:
                    data = r.json()
                    sidebar_log.text_area("Pipeline output", data.get('logs',''), height=300)
                    if data.get('status') in ('finished', 'error'):
                        return data.get('status')
                else:
                    sidebar_log.text_area("Pipeline output", f"Log fetch failed: {r.status_code}", height=300)
                    return 'error'
                time.sleep(0.5)
        except Exception as e:
            sidebar_log.text_area("Pipeline output", f"Polling failed: {e}", height=300)
            return 'error'

    if col_gen_demo:
        if use_api:
            st.sidebar.info("Requesting demo generation on job server...")
            jobid = start_job_via_api('demo')
            if jobid:
                status = poll_job_logs(jobid)
                if status == 'finished':
                    st.sidebar.success('Demo assets created')
                else:
                    st.sidebar.error('Demo job failed')
        else:
            st.sidebar.warning('requests not installed; cannot use job server')

    if col_run_music:
        if use_api:
            st.sidebar.info('Starting music-only job...')
            jobid = start_job_via_api('music')
            if jobid:
                status = poll_job_logs(jobid)
                if status == 'finished':
                    st.sidebar.success('Music job finished')
                else:
                    st.sidebar.error('Music job failed')
        else:
            st.sidebar.warning('requests not installed; cannot use job server')

    if col_run_anim:
        if use_api:
            st.sidebar.info('Starting animation job...')
            jobid = start_job_via_api('anim')
            if jobid:
                status = poll_job_logs(jobid)
                if status == 'finished':
                    st.sidebar.success('Animation job finished')
                else:
                    st.sidebar.error('Animation job failed')
        else:
            st.sidebar.warning('requests not installed; cannot use job server')

    if col_run_style:
        if use_api:
            st.sidebar.info('Starting style job...')
            jobid = start_job_via_api('style')
            if jobid:
                status = poll_job_logs(jobid)
                if status == 'finished':
                    st.sidebar.success('Style job finished')
                else:
                    st.sidebar.error('Style job failed')
        else:
            st.sidebar.warning('requests not installed; cannot use job server')

    tabs = st.tabs(["Layer 0 — Music", "Layer 1 — Semantic Timeline", "Layer 2 — Beats", "Layer 3 — Animation", "Layer 4 — Sync", "Layer 5 — Style", "Summary & Export"])

    # Load common artifacts
    lyrics_analysis = load_json(OUT_DIR / "lyrics_analysis.json")
    semantic_tl = load_json(OUT_DIR / "semantic_timeline.json")
    beat_analysis = load_json(OUT_DIR / "beat_analysis.json")
    pipeline = load_json(OUT_DIR / "pipeline_outputs.json") or {}

    # If user triggered run buttons above, refresh the artifact pointers so the UI below sees new files.
    if any([col_run_full, col_run_music, col_run_anim, col_run_style, col_gen_demo]):
        # small sleep to let file system settle
        time.sleep(0.2)
        lyrics_analysis = load_json(OUT_DIR / "lyrics_analysis.json")
        semantic_tl = load_json(OUT_DIR / "semantic_timeline.json")
        beat_analysis = load_json(OUT_DIR / "beat_analysis.json")
        pipeline = load_json(OUT_DIR / "pipeline_outputs.json") or {}

    # Layer 0 tab
    with tabs[0]:
        st.header("Layer 0 — Music Generation & Gemini")
        if lyrics_input:
            st.subheader("Input lyrics (preview)")
            st.text_area("lyrics_preview", value=lyrics_input, height=120)
        if lyrics_analysis:
            st.subheader("Gemini analysis")
            st.json(lyrics_analysis)
            st.markdown("**Music prompt**")
            st.code(lyrics_analysis.get("music_prompt", ""))
        music_path = OUT_DIR / pipeline.get("music_path", "music.wav")
        if music_path.exists():
            st.audio(str(music_path))
            if librosa is not None:
                y, sr = load_audio(music_path)
                if y is not None:
                    fig = waveform_figure(y, sr, title="Generated music waveform")
                    st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No music found in outputs/. Run the pipeline to generate audio.")

    # Layer 1 tab
    with tabs[1]:
        st.header("Layer 1 — Semantic & Emotional Timeline")
        if semantic_tl:
            duration = semantic_tl.get("duration_sec", 10.0)
            segs = semantic_tl.get("segments", [])
            st.plotly_chart(color_timeline_figure(segs, duration=duration), use_container_width=True)
            st.subheader("Timeline JSON")
            st.json(semantic_tl)
            kw_fig = simple_bar_keywords(semantic_tl)
            if kw_fig:
                st.plotly_chart(kw_fig, use_container_width=True)
            else:
                st.info("No keywords found in semantic timeline segments.")
        else:
            st.info("No semantic timeline found in outputs/semantic_timeline.json")

    # Layer 2 tab
    with tabs[2]:
        st.header("Layer 2 — Audio & Beat Analysis")
        if beat_analysis:
            st.subheader("Beat analysis JSON")
            st.json(beat_analysis)
            energy = beat_analysis.get("energy_curve") or beat_analysis.get("rms") or []
            energy_fig = draw_energy_curve(energy)
            if energy_fig:
                st.plotly_chart(energy_fig, use_container_width=True)
        else:
            st.info("No beat analysis found in outputs/beat_analysis.json")

    # Layer 3 tab
    with tabs[3]:
        st.header("Layer 3 — Procedural Visual Animation")
        anim_path = OUT_DIR / pipeline.get("animated_path", "animated.mp4")
        if anim_path.exists():
            st.video(str(anim_path))
            st.slider("Preview frame", 0, 100, 0)
        else:
            st.info("No animated video found (outputs/animated.mp4)")

    # Layer 4 tab
    with tabs[4]:
        st.header("Layer 4 — Synchronization")
        final_path = OUT_DIR / pipeline.get("final_video_path", "final.mp4")
        if final_path.exists():
            st.video(str(final_path))
        else:
            st.info("No final video found (outputs/final.mp4)")

    # Layer 5 tab
    with tabs[5]:
        st.header("Layer 5 — Style Mapper")
        styled = OUT_DIR / pipeline.get("styled_video", "styled_final.mp4")
        col1, col2 = st.columns(2)
        if styled.exists():
            with col1:
                st.subheader("Styled video")
                st.video(str(styled))
            with col2:
                st.subheader("Style report")
                style_report = load_json(OUT_DIR / "style_report.json")
                if style_report:
                    st.json(style_report)
                else:
                    st.info("No style_report.json found")
        else:
            st.info("No styled video found (outputs/styled_final.mp4)")

    # Summary & Export
    with tabs[6]:
        st.header("Summary & Export")
        st.markdown("### Download generated assets")
        files = [
            ("Music (wav)", OUT_DIR / pipeline.get("music_path", "music.wav")),
            ("Semantic timeline (json)", OUT_DIR / "semantic_timeline.json"),
            ("Beat analysis (json)", OUT_DIR / "beat_analysis.json"),
            ("Animated (mp4)", OUT_DIR / pipeline.get("animated_path", "animated.mp4")),
            ("Final (mp4)", OUT_DIR / pipeline.get("final_video_path", "final.mp4")),
            ("Styled (mp4)", OUT_DIR / pipeline.get("styled_video", "styled_final.mp4")),
        ]
        for label, p in files:
            if p.exists():
                with open(p, "rb") as fh:
                    st.download_button(label, data=fh, file_name=p.name)
            else:
                st.write(f"{label}: not found")

        st.markdown("---")
        if st.button("Export Project Report (zip) "):
            import zipfile, tempfile
            tf = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
            with zipfile.ZipFile(tf.name, "w") as z:
                for _, p in files:
                    if p.exists():
                        z.write(p, arcname=p.name)
            with open(tf.name, "rb") as fh:
                st.download_button("Download ZIP", data=fh, file_name="project_report.zip")


if __name__ == "__main__":
    main()
