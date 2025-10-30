"""
Diagnostic script to probe the installed Transformers MusicGen pipeline / direct model API.

Usage: run under your Conda env (F:\Conda\envs\musical_v\python.exe) so installed packages are used.
The script will try to avoid downloading large model files. If model weights are not cached locally it will report that and exit.

It prints the returned object types/shapes for both the direct-model API (AutoProcessor+MusicgenForConditionalGeneration)
and the high-level "text-to-audio" pipeline if available.

Be patient: loading the model from cache can still take time and memory.
"""
import sys
import json
import traceback

try:
    from huggingface_hub import snapshot_download
except Exception:
    snapshot_download = None

MODEL_ID = "facebook/musicgen-small"
PROMPT = "A short, soft synth arpeggio with gentle pads, 4 seconds"

print("Diagnostic: checking if model is cached locally for:", MODEL_ID)
cached = False
if snapshot_download is not None:
    try:
        # try to locate files locally without downloading
        path = snapshot_download(repo_id=MODEL_ID, local_files_only=True)
        print("Found cached model at:", path)
        cached = True
    except Exception as e:
        print("Model not cached locally or snapshot_download not available:", str(e))
else:
    print("huggingface_hub.snapshot_download not available in this environment. Will attempt to load model but may download.")

print("\n--- Direct model API (AutoProcessor + MusicgenForConditionalGeneration) ---")
try:
    from transformers import AutoProcessor, MusicgenForConditionalGeneration
    print("transformers AutoProcessor and Musicgen model classes imported")
    if not cached:
        print("Model may not be cached locally. Loading might trigger a download. Aborting to avoid large download.")
    else:
        try:
            proc = AutoProcessor.from_pretrained(MODEL_ID, local_files_only=True)
            model = MusicgenForConditionalGeneration.from_pretrained(MODEL_ID, local_files_only=True)
            print("Loaded processor and model from cache")
            print("Building inputs...")
            inputs = proc(text=[PROMPT], padding=True, return_tensors="pt")
            print("Inputs keys:", list(inputs.keys()))
            print("Moving input tensors to cpu for safety")
            try:
                import torch
                device = "cuda" if torch.cuda.is_available() else "cpu"
                model.to(device)
                for k, v in list(inputs.items()):
                    try:
                        inputs[k] = v.to(device)
                    except Exception:
                        pass
            except Exception:
                pass
            print("Calling model.generate(...) (this may take a little while)")
            gen = model.generate(**inputs)
            print("model.generate returned type:", type(gen))
            try:
                import torch
                if hasattr(gen, 'shape'):
                    print("gen shape:", getattr(gen, 'shape', None))
                elif isinstance(gen, (list, tuple)):
                    print("gen length:", len(gen))
                    try:
                        first = gen[0]
                        print("first element type:", type(first))
                        if hasattr(first, 'shape'):
                            print("first shape:", first.shape)
                    except Exception:
                        pass
            except Exception:
                pass
            # try decoding via processor if available
            if hasattr(proc, 'decode'):
                try:
                    dec = proc.decode(gen[0])
                    print("proc.decode returned type:", type(dec))
                    # if it's a numpy array or list, print small stats
                    try:
                        import numpy as np
                        arr = np.asarray(dec)
                        print("decoded array shape:", arr.shape, "dtype:", arr.dtype)
                        print("sample slice:", arr.flatten()[:10])
                    except Exception:
                        print("proc.decode returned non-array type; repr:", repr(dec)[:200])
                except Exception:
                    print("proc.decode raised:")
                    traceback.print_exc()
            else:
                print("processor has no decode method; returned generation object should be inspected above")
        except Exception:
            print("Failed to load model from cache or run generation:")
            traceback.print_exc()
except Exception:
    print("Direct model API classes not importable in this environment:")
    traceback.print_exc()

print("\n--- High-level transformers pipeline('text-to-audio') ---")
try:
    from transformers import pipeline
    print("transformers.pipeline imported")
    try:
        # attempt to create pipeline but do not force download if not cached
        pipe = pipeline("text-to-audio", model=MODEL_ID)
        print("pipeline created. Calling pipeline with a short prompt (may download model if not cached)")
        res = pipe(PROMPT, duration=4)
        print("pipeline returned type:", type(res))
        # Inspect dict/list
        if isinstance(res, dict):
            print("dict keys:", list(res.keys()))
            for k, v in res.items():
                print(k, "-> type:", type(v))
                try:
                    import numpy as np
                    arr = np.asarray(v)
                    print("-> array shape", arr.shape, "dtype", arr.dtype)
                except Exception:
                    print("-> repr:", repr(v)[:200])
        elif isinstance(res, (list, tuple)):
            print("list length:", len(res))
            if res:
                print("first element type:", type(res[0]))
                try:
                    import numpy as np
                    arr = np.asarray(res[0])
                    print("first as array shape:", arr.shape)
                except Exception:
                    pass
        else:
            print("pipeline result repr:", repr(res)[:400])
    except Exception:
        print("Creating or calling the pipeline failed (may attempt to download model if not cached):")
        traceback.print_exc()
except Exception:
    print("transformers.pipeline is not importable in this environment:")
    traceback.print_exc()

print('\nDiagnostic complete.')
