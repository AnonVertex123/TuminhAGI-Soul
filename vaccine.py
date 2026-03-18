import sys
import torch
import typing
import builtins

# --- Vaccine Tự Minh: Mocking dtypes and Unpack for Windows ---
# Fixes NameError: name 'Unpack' is not defined in unsloth_zoo
# Bypasses environment-specific typing limitations on Windows

for i in range(1, 129):
    if not hasattr(torch, f"int{i}"):
        setattr(torch, f"int{i}", torch.int8)

# Injected into builtins to solve global NameError in 3rd party libs
if not hasattr(builtins, "Unpack"):
    class UnpackStub: pass
    setattr(builtins, "Unpack", UnpackStub)

if not hasattr(typing, "Unpack"):
    try:
        from typing_extensions import Unpack
        typing.Unpack = Unpack
    except ImportError:
        class UnpackStub: pass
        typing.Unpack = UnpackStub

# --- Kết thúc Vaccine ---
