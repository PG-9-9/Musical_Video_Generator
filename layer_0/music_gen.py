import os
from typing import Optional

from pydub.generators import Sine
from pydub import AudioSegment
import logging

# Try to use MusicGen via the Transformers library first (if available),
# otherwise fall back to audiocraft MusicGen when available.
_TF_MUSICGEN_AVAILABLE = False
_TF_PIPELINE = None
try:
    # Prefer the transformers pipeline API if it exposes a text-to-audio task
    from transformers import pipeline as _hf_pipeline
    try:
        _TF_PIPELINE = _hf_pipeline("text-to-audio", model="facebook/musicgen-small")
        _TF_MUSICGEN_AVAILABLE = True
    except Exception:
        _TF_PIPELINE = None
        _TF_MUSICGEN_AVAILABLE = False
except Exception:
    _TF_MUSICGEN_AVAILABLE = False

# audiocraft (fallback) availability
_AUDIOCRAFT_AVAILABLE = False
_MUSICGEN = None
try:
    from audiocraft.models import MusicGen
    import torch
    _AUDIOCRAFT_AVAILABLE = True
    _MUSICGEN = MusicGen
except Exception:
    _AUDIOCRAFT_AVAILABLE = False


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
                               mubert_api_key: Optional[str] = None, semantic_timeline: Optional[object] = None) -> str:
    """
    Use Suno Bark (if available) to synthesize audio from a textual prompt. The code is
    defensive and tries multiple common Bark APIs to remain compatible across versions.
    If Bark is not available or generation fails, we fall back to a simple sine placeholder
    so the rest of the pipeline stays runnable.
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # If a semantic timeline object/path was provided, build a richer prompt
    def _build_prompt_from_timeline(prompt_base, timeline) -> str:
        parts = [prompt_base.strip() if prompt_base else ""]
        try:
            import json
            if isinstance(timeline, str):
                if os.path.exists(timeline):
                    with open(timeline, "r", encoding="utf-8") as fh:
                        timeline = json.load(fh)
                else:
                    # try parse as JSON string
                    timeline = json.loads(timeline)

            # timeline expected as list of segments
            if isinstance(timeline, dict) and "segments" in timeline:
                segs = timeline.get("segments", [])
            elif isinstance(timeline, list):
                segs = timeline
            else:
                segs = []

            for i, s in enumerate(segs[:6]):
                emo = s.get("emotion") if isinstance(s, dict) else None
                intensity = s.get("intensity") if isinstance(s, dict) else None
                keywords = s.get("keywords") if isinstance(s, dict) else None
                visual = s.get("visual_hint") if isinstance(s, dict) else None
                seg_desc = f"Segment {i+1}:"
                if emo:
                    seg_desc += f" emotion={emo}"
                if intensity:
                    seg_desc += f" intensity={intensity}"
                if keywords:
                    if isinstance(keywords, (list, tuple)):
                        seg_desc += " keywords=" + ",".join(map(str, keywords))
                    else:
                        seg_desc += f" keywords={keywords}"
                if visual:
                    seg_desc += f" visuals={visual}"
                parts.append(seg_desc)
        except Exception:
            # ignore timeline parsing errors and fall back to base prompt
            pass
        return " -- ".join([p for p in parts if p])

    full_prompt = music_prompt
    if semantic_timeline:
        full_prompt = _build_prompt_from_timeline(music_prompt or "", semantic_timeline)

    # Try transformers pipeline-based MusicGen first (if available)
    if _TF_MUSICGEN_AVAILABLE and _TF_PIPELINE is not None:
        try:
            logging.getLogger(__name__).info("Attempting generation via transformers MusicGen pipeline")
            res = _TF_PIPELINE(full_prompt, duration=duration_sec)
            audio_candidate = None
            # pipeline may return dict or array or path
            if isinstance(res, dict):
                audio_candidate = res.get("audio") or res.get("wav") or res.get("array") or res.get("samples")
            else:
                audio_candidate = res

            # If it returned a path
            if isinstance(audio_candidate, str) and os.path.exists(audio_candidate):
                try:
                    seg = AudioSegment.from_file(audio_candidate)
                    seg.export(output_path, format="wav")
                    return output_path
                except Exception:
                    pass

            # If it returned an array-like
            try:
                import numpy as _np
                import soundfile as sf
                if hasattr(audio_candidate, "dtype") or isinstance(audio_candidate, (list, tuple, _np.ndarray)):
                    sf.write(output_path, _np.asarray(audio_candidate), getattr(_TF_PIPELINE.model, "sample_rate", 32000))
                    return output_path
            except Exception:
                pass
        except Exception as e:
            logging.getLogger(__name__).warning("Transformers MusicGen pipeline failed: %s", e)

    # If Meta MusicGen (audiocraft) is available, use it.
    if _AUDIOCRAFT_AVAILABLE and _MUSICGEN is not None:
        try:
            # attempt to prefetch model weights (make this best-effort)
            try:
                from huggingface_hub import snapshot_download
                cache_dir = os.path.join(os.getcwd(), ".cache", "musicgen")
                os.makedirs(cache_dir, exist_ok=True)
                logging.getLogger(__name__).info("Ensuring MusicGen model cached; cache=%s", cache_dir)
                try:
                    snapshot_download(repo_id="facebook/musicgen-small", cache_dir=cache_dir)
                    os.environ["HF_HOME"] = cache_dir
                except Exception:
                    pass
            except Exception:
                pass

            model = _MUSICGEN.get_pretrained("small")
            device = "cuda" if torch.cuda.is_available() else "cpu"
            model.to(device)
            model.set_generation_params(duration=duration_sec)
            wavs = model.generate([full_prompt], device=device)
            audio = wavs[0]
            try:
                import torch as _torch
                if isinstance(audio, _torch.Tensor):
                    audio = audio.cpu().numpy()
            except Exception:
                pass
            sr = getattr(model, "sample_rate", 32000)
            try:
                import soundfile as sf
                sf.write(output_path, audio, sr)
            except Exception:
                # fallback: write via pydub if possible
                try:
                    import numpy as _np
                    seg = AudioSegment(
                        (audio * (2 ** 15 - 1)).astype('int16').tobytes(),
                        frame_rate=sr,
                        sample_width=2,
                        channels=1,
                    )
                    seg.export(output_path, format="wav")
                except Exception:
                    raise
            return output_path
        except Exception as e:
            logging.getLogger(__name__).warning("MusicGen generation failed, falling back: %s", e)

    # Fallback: make a simple placeholder audio so pipeline keeps running
    return generate_placeholder_music(duration_sec, output_path)
