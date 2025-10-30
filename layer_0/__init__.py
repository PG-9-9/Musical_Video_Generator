"""Public surface for layer_0 package: re-export main pipeline functions."""
from .gemini_utils import analyze_lyrics, load_config
from .music_gen import generate_music_from_prompt, generate_placeholder_music
from .video_gen import generate_placeholder_video
from .composer import compose_video

__all__ = [
    "analyze_lyrics",
    "load_config",
    "generate_music_from_prompt",
    "generate_placeholder_music",
    "generate_placeholder_video",
    "compose_video",
]
