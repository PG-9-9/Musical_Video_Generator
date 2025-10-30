"""Probe moviepy installation and available import paths.
"""
import importlib, pkgutil, traceback
try:
    import moviepy
    print('moviepy', getattr(moviepy, '__version__', 'unknown'), 'at', moviepy.__file__)
    names = [m.name for m in pkgutil.iter_modules(moviepy.__path__)]
    print('submodules:', names)
except Exception:
    print('moviepy import failed:')
    traceback.print_exc()

paths_to_try = [
    'moviepy.editor',
    'moviepy.video.io.ImageSequenceClip',
    'moviepy.video.io.ImageSequenceClip',
    'moviepy.editor.VideoClip',
]

for p in paths_to_try:
    try:
        m = importlib.import_module(p)
        print('OK import', p, '->', getattr(m, '__file__', repr(m)))
    except Exception as e:
        print('FAIL import', p, type(e).__name__, str(e))

try:
    from moviepy.video.io.ImageSequenceClip import ImageSequenceClip
    print('Found ImageSequenceClip in moviepy.video.io.ImageSequenceClip')
except Exception:
    print('ImageSequenceClip not found at moviepy.video.io.ImageSequenceClip')
