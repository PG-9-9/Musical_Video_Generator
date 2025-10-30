import os
from typing import Optional

from pydub.generators import Sine
from pydub import AudioSegment


def generate_placeholder_music(duration_sec: int = 10, output_path: str = "outputs/music.wav") -> str:
    """Generate a simple sine-wave placeholder music so pipeline is runnable without external API."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    base = Sine(440).to_audio_segment(duration=duration_sec * 1000).apply_gain(-5)
    # add a second tone to make it less boring
    overlay = Sine(660).to_audio_segment(duration=duration_sec * 1000).apply_gain(-12)
    final = base.overlay(overlay)
    final.export(output_path, format="wav")
    return output_path


def generate_music_from_prompt(music_prompt: str, duration_sec: int = 10, output_path: str = "outputs/music.wav",
                               mubert_api_key: Optional[str] = None) -> str:
    """
    If mubert_api_key is provided, call the service (left as TODO); otherwise fallback to placeholder.
    """
    if mubert_api_key is None:
        return generate_placeholder_music(duration_sec, output_path)
    # TODO: implement actual Mubert call
    return generate_placeholder_music(duration_sec, output_path)
