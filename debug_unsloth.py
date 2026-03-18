import os
import sys
import builtins
import torch

print("Step 1: Vaccine Starting")
os.environ["UNSLOTH_USE_TRITON"] = "0"
os.environ["XFORMERS_FORCE_DISABLE_TRITON"] = "1"

for i in range(1, 129):
    if not hasattr(torch, f"int{i}"):
        setattr(torch, f"int{i}", torch.int8)
if not hasattr(builtins, "Unpack"):
    class UnpackStub: pass
    setattr(builtins, "Unpack", UnpackStub)

print("Step 2: Vaccine Applied")

try:
    print("Step 3: Importing unsloth.kernels.rms_layernorm")
    import unsloth.kernels.rms_layernorm
    print("Step 4: Importing unsloth.models.llama")
    import unsloth.models.llama
    print("Step 5: Importing SFTTrainer from trl")
    from trl import SFTTrainer
    print("Step 6: Importing FastLanguageModel from unsloth")
    from unsloth import FastLanguageModel
    print("Step 7: All core imports successful!")
except Exception as e:
    print(f"FAILED with error: {e}")
    import traceback
    traceback.print_exc()
