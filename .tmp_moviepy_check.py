"""Small script to verify moviepy + ffmpeg can write an MP4 and print errors.
"""
import sys
import traceback
from PIL import Image
import numpy as np

try:
    import moviepy
    from moviepy.editor import ImageSequenceClip
    print('moviepy version:', moviepy.__version__)
    # create two frames
    arr1 = np.zeros((120, 160, 3), dtype=np.uint8)
    arr1[..., 0] = 255
    arr2 = np.zeros((120, 160, 3), dtype=np.uint8)
    arr2[..., 2] = 255
    clip = ImageSequenceClip([arr1, arr2], fps=2)
    out = 'outputs/moviepy_check.mp4'
    print('Writing', out)
    clip.write_videofile(out, codec='libx264', audio=False)
    print('Wrote', out)
except Exception as e:
    print('Exception while testing moviepy:')
    traceback.print_exc()
    sys.exit(2)
