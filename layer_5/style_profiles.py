"""Define emotion -> style profile lookup table.

Each profile includes a simple representation of palette and tunables used by
the style applier. Keep the shapes small to make interpolation straightforward.
"""
from typing import Dict, Any, Tuple

def _hex_to_rgb(hexstr: str) -> Tuple[int,int,int]:
    h = hexstr.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

STYLE_PROFILES: Dict[str, Dict[str, Any]] = {
    "Calm": {
        "palette": ["#1E3A8A", "#60A5FA"],  # cool blue tones
        "contrast": 0.8,
        "motion_blur": 0.4,
        "texture": "film_grain",
    },
    "Hopeful": {
        "palette": ["#F59E0B", "#FDE68A"],  # golden hues
        "contrast": 1.0,
        "motion_blur": 0.6,
        "texture": "bokeh_glow",
    },
    "Energetic": {
        "palette": ["#EF4444", "#FB923C"],  # saturated reds/oranges
        "contrast": 1.4,
        "motion_blur": 0.2,
        "texture": "light_streaks",
    },
    "Euphoric": {
        "palette": ["#7C3AED", "#EC4899"],  # neon purples & pinks
        "contrast": 1.6,
        "motion_blur": 0.1,
        "texture": "particle_flare",
    },
    "Sad": {
        "palette": ["#4B5563", "#9CA3AF"],  # desaturated grays
        "contrast": 0.7,
        "motion_blur": 0.2,
        "texture": "vignette",
    },
    "Romantic": {
        "palette": ["#FCA5A5", "#FB7185"],  # warm rose tones
        "contrast": 1.0,
        "motion_blur": 0.4,
        "texture": "glow_halo",
    },
}

def get_style_profile(emotion: str) -> Dict[str, Any]:
    # fall back to Calm if unknown
    return STYLE_PROFILES.get(emotion, STYLE_PROFILES["Calm"])
