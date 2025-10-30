"""Write a short mp4 using the moviepy import path that exists in this env.
"""
import numpy as np
import traceback
try:
    from moviepy.video.io.ImageSequenceClip import ImageSequenceClip
    print('Using moviepy.video.io.ImageSequenceClip')
except Exception:
    try:
        from moviepy.editor import ImageSequenceClip
        print('Using moviepy.editor.ImageSequenceClip')
    except Exception:
        print('No usable ImageSequenceClip import')
        raise

arr1 = np.zeros((120, 160, 3), dtype=np.uint8)
arr1[..., 0] = 255
arr2 = np.zeros((120, 160, 3), dtype=np.uint8)
arr2[..., 2] = 255
clip = ImageSequenceClip([arr1, arr2], fps=2)
out = 'outputs/moviepy_check2.mp4'
print('Writing', out)
clip.write_videofile(out, codec='libx264', audio=False)
print('Wrote', out)
