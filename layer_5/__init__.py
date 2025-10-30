"""Layer 5: Adaptive visual style blending and final render.

Expose a small API:
 - load_style_profiles()
 - build_style_timeline(semantic_timeline, fps, duration_sec)
 - apply_styles_to_frames(base_frames, style_timeline, beat_curve, out_path, fps)

The implementation is intentionally lightweight and uses PIL/numpy. If moviepy is
installed it will write an MP4; otherwise it will write an animated GIF as fallback.
"""
from .style_profiles import STYLE_PROFILES, get_style_profile
from .style_applier import (
    build_style_timeline,
    apply_styles_to_frames,
    simple_motion_refinement,
)

__all__ = [
    "STYLE_PROFILES",
    "get_style_profile",
    "build_style_timeline",
    "apply_styles_to_frames",
    "simple_motion_refinement",
]
