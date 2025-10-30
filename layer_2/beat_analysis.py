import json
import os
from typing import Dict, Any, Optional, List

import numpy as np
import math

try:
    import librosa
except Exception:
    librosa = None


def _safe_load_audio(path: str):
    if librosa is None:
        raise RuntimeError("librosa is not installed in the current environment")
    y, sr = librosa.load(path, sr=None, mono=True)
    return y, sr


def _normalize_curve(x: np.ndarray) -> List[float]:
    if x.size == 0:
        return []
    x = np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)
    mn = float(np.min(x))
    mx = float(np.max(x))
    if math.isclose(mx, mn):
        return [0.0 for _ in x.tolist()]
    norm = (x - mn) / (mx - mn)
    return norm.tolist()


def analyze_beats(audio_path: str = "outputs/music.wav", semantic_timeline_path: Optional[str] = "outputs/semantic_timeline.json", output_path: str = "outputs/beat_analysis.json") -> Dict[str, Any]:
    """Analyze audio to find tempo, beats, energy curve, onsets, and per-segment energies.

    Returns a dictionary and writes JSON to output_path.
    """
    if not os.path.exists(audio_path):
        raise FileNotFoundError(audio_path + " not found")

    y, sr = _safe_load_audio(audio_path)

    # Tempo and beat tracking (primary attempt)
    hop_length = 512
    frame_length = 1024
    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr, hop_length=hop_length, start_bpm=90)
    beat_times = librosa.frames_to_time(beat_frames, sr=sr, hop_length=hop_length).tolist()

    # If tempo detection failed or returned unrealistic value, try stronger fallbacks
    def _estimate_tempo_autocorr(onset_env: np.ndarray, sr: int, hop_length: int, bpm_min=50, bpm_max=200):
        """Estimate tempo (BPM) from the onset envelope using autocorrelation.

        Returns BPM or 0.0 if estimation fails.
        """
        if onset_env is None or len(onset_env) < 4:
            return 0.0
        # remove mean and small eps
        x = onset_env - np.mean(onset_env)
        if np.allclose(x, 0):
            return 0.0
        ac = np.correlate(x, x, mode="full")
        ac = ac[len(ac)//2:]
        # Ignore lag 0
        ac[0] = 0
        # Convert BPM range to lag range
        hop_sec = float(hop_length) / float(sr)
        # Convert bpm to lag in frames: lag = 60 / (bpm * hop_sec)
        max_lag = int(np.ceil(60.0 / (bpm_min * hop_sec))) if bpm_min > 0 else len(ac)-1
        min_lag = int(np.floor(60.0 / (bpm_max * hop_sec))) if bpm_max > 0 else 1
        min_lag = max(1, min_lag)
        max_lag = min(len(ac)-1, max_lag)
        if max_lag <= min_lag:
            return 0.0
        segment = ac[min_lag:max_lag+1]
        if segment.size == 0:
            return 0.0
        lag = np.argmax(segment) + min_lag
        if lag <= 0:
            return 0.0
        bpm = 60.0 / (lag * hop_sec)
        if math.isfinite(bpm) and bpm_min <= bpm <= bpm_max:
            return float(bpm)
        return 0.0

    def _try_percussive_beat_track(y, sr, hop_length, frame_length):
        try:
            # Use harmonic-percussive separation to emphasize transients
            harmonic, percussive = librosa.effects.hpss(y)
            t_bpm, t_beats = librosa.beat.beat_track(y=percussive, sr=sr, hop_length=hop_length)
            t_times = librosa.frames_to_time(t_beats, sr=sr, hop_length=hop_length).tolist()
            return float(t_bpm), t_times
        except Exception:
            return 0.0, []

    # Compute onset envelope for fallback strategies
    onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop_length)

    # Fallback 1: if tempo=0 or not reasonable, attempt percussive beat track
    if not (60 <= tempo <= 180):
        try_bpm, try_beats = _try_percussive_beat_track(y, sr, hop_length, frame_length)
        if 60 <= try_bpm <= 180 and len(try_beats) > 0:
            tempo = try_bpm
            beat_times = try_beats
        else:
            # Fallback 2: autocorrelation on onset envelope
            ac_bpm = _estimate_tempo_autocorr(onset_env, sr, hop_length, bpm_min=50, bpm_max=200)
            if ac_bpm and 50 <= ac_bpm <= 200:
                tempo = ac_bpm
                # attempt to re-run beat tracking using estimated tempo as start_bpm
                try:
                    t_bpm2, t_beats2 = librosa.beat.beat_track(y=y, sr=sr, hop_length=hop_length, start_bpm=int(round(ac_bpm)))
                    if t_beats2 is not None and len(t_beats2) > 0:
                        beat_times = librosa.frames_to_time(t_beats2, sr=sr, hop_length=hop_length).tolist()
                except Exception:
                    # ignore and continue; we have tempo at least
                    pass

        # If beat timestamps are empty but we have a tempo estimate, synthesize beat grid
        if (not beat_times or len(beat_times) == 0) and tempo and tempo > 0.0:
            try:
                period = 60.0 / float(tempo)
                hop_sec = float(hop_length) / float(sr)
                # step in frames between candidate beats
                step = max(1, int(round(period / hop_sec)))
                if step >= 1 and onset_env is not None and len(onset_env) > 0:
                    # find best phase (shift) in range 0..step-1 that maximizes aligned onset energy
                    best_shift = 0
                    best_score = -1.0
                    for shift in range(0, step):
                        idxs = np.arange(shift, len(onset_env), step)
                        if idxs.size == 0:
                            continue
                        score = float(np.sum(onset_env[idxs]))
                        if score > best_score:
                            best_score = score
                            best_shift = shift

                    # synthesize beat frame indices and convert to times
                    beat_idxs = np.arange(best_shift, len(onset_env), step)
                    synth_times = (beat_idxs * hop_sec).tolist()
                    # Filter to clip duration
                    duration = librosa.get_duration(y=y, sr=sr)
                    synth_times = [float(t) for t in synth_times if t >= 0.0 and t <= duration]
                    if len(synth_times) > 0:
                        beat_times = synth_times
            except Exception:
                # if synthesis fails, keep beat_times as-is
                pass

    # Onsets
    onset_frames = librosa.onset.onset_detect(y=y, sr=sr)
    onset_times = librosa.frames_to_time(onset_frames, sr=sr).tolist()

    # RMS energy curve (frame-based)
    hop_length = 512
    frame_length = 1024
    rms = librosa.feature.rms(y=y, frame_length=frame_length, hop_length=hop_length)[0]
    times = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=hop_length, n_fft=frame_length).tolist()
    energy_curve = _normalize_curve(rms)

    # Per-segment average energy using semantic timeline if provided
    per_segment_energy = []
    if semantic_timeline_path and os.path.exists(semantic_timeline_path):
        with open(semantic_timeline_path, "r", encoding="utf-8") as f:
            sem = json.load(f)
        segments = sem.get("segments", [])
        for seg in segments:
            start = float(seg.get("start_sec", 0.0))
            end = float(seg.get("end_sec", 0.0))
            # average rms values between start and end
            idxs = [i for i, t in enumerate(times) if t >= start and t < end]
            if not idxs:
                avg = 0.0
            else:
                vals = [rms[i] for i in idxs]
                avg = float(np.mean(np.nan_to_num(vals)))
            per_segment_energy.append(avg)
        # normalize per-segment energies to 0-1
        per_segment_energy = _normalize_curve(np.array(per_segment_energy))

    # Validation checks
    # tempo realistic
    tempo_valid = 60 <= tempo <= 180
    # beat timestamps cover most of the clip
    duration = librosa.get_duration(y=y, sr=sr)
    beats_cover = (len(beat_times) > 0 and beat_times[0] <= 0.5 and beat_times[-1] >= max(0.9 * duration, duration - 0.5))

    result = {
        "audio_path": audio_path,
        "tempo_bpm": float(tempo),
        "beat_times": beat_times,
        "onset_times": onset_times,
        "energy_curve": energy_curve,
        "energy_curve_times": times,
        "per_segment_energy": per_segment_energy,
        "duration_sec": duration,
        "tempo_valid": bool(tempo_valid),
        "beats_cover": bool(beats_cover),
    }

    # ensure no NaN/inf in result
    def _clean(obj):
        if isinstance(obj, list):
            return [_clean(x) for x in obj]
        if isinstance(obj, float):
            if math.isfinite(obj):
                return obj
            return 0.0
        return obj

    result = {k: _clean(v) for k, v in result.items()}

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    return result
