"""Visual effect implementations for Layer 3.

Each effect exposes a function(effect_state, t, w, h) -> RGB frame (H,W,3) float32 0-1.
effect_state contains precomputed parameters like color, intensity scale, beat times, etc.
"""
from typing import Dict, Any, List
import numpy as np


def _norm01(x):
    x = np.asarray(x, dtype=np.float32)
    x = np.clip(x, 0.0, 1.0)
    return x


def gradient_wave(state: Dict[str, Any], t: float, w: int, h: int) -> np.ndarray:
    # slow horizontal wave that shifts hue; color provided as hex in state['color']
    color = state.get("color_rgb", np.array([0.4, 0.6, 1.0], dtype=np.float32))
    speed = state.get("speed", 0.1)
    energy = state.get("energy", 1.0)
    x = np.linspace(0, 2 * np.pi, w)[None, :]
    y = np.linspace(0, 1, h)[:, None]
    phase = np.sin(x * 2 + t * speed) * 0.5 + 0.5
    base = y * 0.6 + phase * 0.4
    frame = base[:, :, None] * color[None, None, :] * energy
    return _norm01(frame)


def soft_particle_drift(state: Dict[str, Any], t: float, w: int, h: int) -> np.ndarray:
    # falling mist: many soft translucent circles drifting downward
    rng = state.get("rng")
    if rng is None:
        rng = np.random.RandomState(42)
        state["rng"] = rng
    n = state.get("count", 80)
    energy = state.get("energy", 1.0)
    bg = np.zeros((h, w, 3), dtype=np.float32)
    for i in range(n):
        px = state.get("px", rng.rand(n))
    xs = state.setdefault("px", rng.rand(n))
    ys = state.setdefault("py", rng.rand(n))
    sizes = state.setdefault("ps", 0.01 + 0.06 * rng.rand(n))
    speeds = state.setdefault("pv", 0.05 + 0.25 * rng.rand(n))
    for i in range(n):
        cx = int((xs[i] + (t * speeds[i]) * 0.05) % 1.0 * w)
        cy = int(((ys[i] + t * speeds[i]) % 1.0) * h)
        r = int(sizes[i] * min(w, h))
        rr = np.arange(max(0, cy - r), min(h, cy + r))
        cc = np.arange(max(0, cx - r), min(w, cx + r))
        if rr.size == 0 or cc.size == 0:
            continue
        yy, xx = np.meshgrid(rr, cc, indexing="ij")
        d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
        mask = np.exp(- (d / (r + 1e-6)) ** 2)
        col = np.array(state.get("color_rgb", [0.2, 0.4, 0.6])) * 0.6
        bg[rr[:, None], cc[None, :], :] += mask[:, :, None] * col[None, None, :] * (0.02 * energy)
    return _norm01(bg)


def expanding_ring_pulse(state: Dict[str, Any], t: float, w: int, h: int) -> np.ndarray:
    # concentric rings expanding at beat times
    center = (w // 2, h // 2)
    frame = np.zeros((h, w, 3), dtype=np.float32)
    color = state.get("color_rgb", np.array([1.0, 0.8, 0.5], dtype=np.float32))
    beats = state.get("beats", [])
    energy = state.get("energy", 1.0)
    for b in beats:
        dt = t - b
        if dt < 0 or dt > 1.2:
            continue
        rr = dt * max(w, h) * 0.6
        yy, xx = np.meshgrid(np.arange(h), np.arange(w), indexing="ij")
        d = np.sqrt((xx - center[0]) ** 2 + (yy - center[1]) ** 2)
        ring = np.exp(-((d - rr) ** 2) / (max(1.0, rr * 0.12)))
        frame += ring[:, :, None] * color[None, None, :] * (0.6 * (1.0 - dt) * energy)
    return _norm01(frame)


def beat_flash(state: Dict[str, Any], t: float, w: int, h: int) -> np.ndarray:
    # full-frame flash on beat, decays between beats
    color = state.get("color_rgb", np.array([1.0, 1.0, 1.0], dtype=np.float32))
    beats = state.get("beats", [])
    energy = state.get("energy", 1.0)
    val = 0.0
    for b in beats:
        dt = t - b
        if dt >= 0 and dt < 0.35:
            val = max(val, (0.35 - dt) / 0.35)
    frame = np.ones((h, w, 3), dtype=np.float32) * (color[None, None, :] * val * energy)
    return _norm01(frame)


def particle_explosion(state: Dict[str, Any], t: float, w: int, h: int) -> np.ndarray:
    rng = state.get("rng")
    if rng is None:
        rng = np.random.RandomState(1)
        state["rng"] = rng
    n = state.get("count", 200)
    center = (w // 2, h // 2)
    frame = np.zeros((h, w, 3), dtype=np.float32)
    for i in range(n):
        ang = state.setdefault("angles", rng.rand(n) * 2 * np.pi)[i]
        speed = state.setdefault("speeds", 0.2 + 0.8 * rng.rand(n))[i]
        r = (t * speed) * min(w, h)
        cx = int(center[0] + np.cos(ang) * r)
        cy = int(center[1] + np.sin(ang) * r)
        if cx < 0 or cy < 0 or cx >= w or cy >= h:
            continue
        frame[cy, cx, :] += np.array(state.get("color_rgb", [1.0, 0.5, 0.9])) * 0.8
    # small blur-like spread
    frame = np.clip(frame, 0.0, 1.0)
    return frame


def smooth_orbit(state: Dict[str, Any], t: float, w: int, h: int) -> np.ndarray:
    frame = np.zeros((h, w, 3), dtype=np.float32)
    color = state.get("color_rgb", np.array([1.0, 0.6, 0.7], dtype=np.float32))
    # draw a few rotating lines
    center = (w // 2, h // 2)
    for i in range(3):
        ang = t * (0.2 + 0.1 * i) + i
        x = int(center[0] + np.cos(ang) * w * 0.25)
        y = int(center[1] + np.sin(ang) * h * 0.25)
        # draw a simple pixel at (x,y)
        if 0 <= x < w and 0 <= y < h:
            frame[y, x, :] = color
    return _norm01(frame * state.get("energy", 1.0))


def noise_fog(state: Dict[str, Any], t: float, w: int, h: int) -> np.ndarray:
    rng = state.get("rng")
    if rng is None:
        rng = np.random.RandomState(123)
        state["rng"] = rng
    base = rng.rand(h, w, 1).astype(np.float32)
    color = np.array(state.get("color_rgb", [0.02, 0.02, 0.02]), dtype=np.float32)
    frame = base * color[None, None, :] * state.get("energy", 1.0)
    return _norm01(frame)
