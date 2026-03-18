import os
import sys
import argparse

# Keep Windows console stable
os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import torch
from peft import PeftModel
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig


def main():
    p = argparse.ArgumentParser(description="Export LoRA model to GGUF using Unsloth saver.")
    p.add_argument("--base", default="Qwen/Qwen2.5-Coder-3B-Instruct")
    p.add_argument("--adapter", default=r"I:\TuminhAgi\_tmp_out\lora_model")
    p.add_argument("--out", default=r"I:\TuminhAgi\_tmp_out\gguf")
    p.add_argument("--quant", default="q4_k_m", help="GGUF quantization method, e.g. q4_k_m")
    p.add_argument("--max-seq-length", type=int, default=2048)
    p.add_argument("--no-4bit", action="store_true", help="Disable 4-bit loading (uses fp16/bf16).")
    a = p.parse_args()

    os.makedirs(a.out, exist_ok=True)

    use_cuda = torch.cuda.is_available()
    compute_dtype = torch.bfloat16 if (use_cuda and torch.cuda.get_device_capability(0)[0] >= 8) else torch.float16

    quant_config = None
    if not a.no_4bit:
        quant_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_use_double_quant=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=compute_dtype,
        )

    # Tokenizer is loaded from adapter directory (contains tokenizer files saved by training)
    tokenizer = AutoTokenizer.from_pretrained(a.adapter, use_fast=True)

    # Load base model + attach LoRA adapter
    model = AutoModelForCausalLM.from_pretrained(
        a.base,
        dtype=compute_dtype,
        device_map="auto" if use_cuda else None,
        quantization_config=quant_config,
        low_cpu_mem_usage=True,
        trust_remote_code=True,
    )
    model = PeftModel.from_pretrained(model, a.adapter, is_trainable=False)
    model.eval()

    # Patch Unsloth saving methods onto the model, then export to GGUF.
    from unsloth.save import patch_saving_functions

    # Work around a Windows mismatch where Unsloth tries to introspect the upstream
    # converter script and fails on newer MODEL_ARCH enums (e.g. MISTRAL4).
    # We already provide a working llama.cpp binary + convert_hf_to_gguf.py, so we
    # can skip introspection and just run conversion.
    try:
        import unsloth_zoo.llama_cpp as _llama_cpp

        def _no_introspect_download_convert_hf_to_gguf():
            llama_cpp_folder = _llama_cpp.LLAMA_CPP_DEFAULT_DIR
            converter = os.path.join(llama_cpp_folder, "convert_hf_to_gguf.py")
            if not os.path.exists(converter):
                converter = os.path.join(llama_cpp_folder, "convert-hf-to-gguf.py")
            return converter, set(), set()

        # Patch in both modules, since unsloth.save may have imported the symbol directly.
        _llama_cpp._download_convert_hf_to_gguf = _no_introspect_download_convert_hf_to_gguf
        import unsloth.save as _uns_save
        _uns_save._download_convert_hf_to_gguf = _no_introspect_download_convert_hf_to_gguf

        # Fix Windows subprocess decoding (cp1252) when capturing converter output.
        _orig_run = _llama_cpp.subprocess.run

        def _run_utf8(*args, **kwargs):
            if kwargs.get("text") or kwargs.get("universal_newlines"):
                kwargs.setdefault("encoding", "utf-8")
                kwargs.setdefault("errors", "replace")
            return _orig_run(*args, **kwargs)

        _llama_cpp.subprocess.run = _run_utf8
    except Exception:
        pass

    model = patch_saving_functions(model, vision=False)
    result = model.save_pretrained_gguf(
        a.out,
        tokenizer=tokenizer,
        quantization_method=a.quant,
    )

    print("GGUF export done.")
    if isinstance(result, dict) and "gguf_files" in result:
        for f in result["gguf_files"]:
            print(f)


if __name__ == "__main__":
    main()