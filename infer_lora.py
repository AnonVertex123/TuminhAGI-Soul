import os
import sys
import argparse
import builtins
os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
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
from transformers.utils import logging as _tf_logging

try:
    from huggingface_hub.utils import logging as _hub_logging
except Exception:
    _hub_logging = None

_tf_logging.set_verbosity_error()
if _hub_logging is not None:
    _hub_logging.set_verbosity_error()


PROMPT = "### Instruction:\n{instruction}\n\n### Input:\n{input}\n\n### Response:\n"
CODE_ONLY_SUFFIX = "\n\nChỉ trả về duy nhất 1 khối code Markdown dạng ```swift ... ``` và không giải thích."


def main():
    p = argparse.ArgumentParser(description="Run inference with base model + LoRA adapter")
    p.add_argument("--base", default="Qwen/Qwen2.5-Coder-3B-Instruct")
    p.add_argument("--adapter", default=r"I:\TuminhAgi\_tmp_out\lora_model")
    p.add_argument("--instruction", default="Build SwiftUI view.")
    p.add_argument("--instruction-file", default="", help="Path to UTF-8 text file for instruction (overrides --instruction).")
    p.add_argument("--input", default="")
    p.add_argument("--input-file", default="", help="Path to UTF-8 text file for input (overrides --input).")
    p.add_argument("--max-seq-length", type=int, default=256)
    p.add_argument("--max-new-tokens", type=int, default=256)
    p.add_argument("--temperature", type=float, default=0.7)
    p.add_argument("--top-p", type=float, default=0.95)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--no-4bit", action="store_true", help="Disable 4-bit loading (uses fp16/bf16).")
    p.add_argument(
        "--extract",
        choices=["response", "code", "full"],
        default="code",
        help="How to print output: only response, code block, or full prompt+response.",
    )
    a = p.parse_args()

    torch.manual_seed(a.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(a.seed)

    tokenizer = AutoTokenizer.from_pretrained(a.adapter, use_fast=True)

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

    def _read_text(path: str) -> str:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()

    instruction = _read_text(a.instruction_file) if a.instruction_file else a.instruction
    user_input = _read_text(a.input_file) if a.input_file else a.input
    if a.extract == "code":
        instruction = instruction.rstrip() + CODE_ONLY_SUFFIX
    prompt = PROMPT.format(instruction=instruction, input=user_input)
    inputs = tokenizer(prompt, return_tensors="pt")
    if use_cuda:
        inputs = {k: v.to(model.device) for k, v in inputs.items()}

    with torch.inference_mode():
        out = model.generate(
            **inputs,
            max_new_tokens=a.max_new_tokens,
            do_sample=a.temperature > 0,
            temperature=a.temperature,
            top_p=a.top_p,
            pad_token_id=tokenizer.eos_token_id,
        )

    text = tokenizer.decode(out[0], skip_special_tokens=True)
    marker = "### Response:"
    if a.extract != "full" and marker in text:
        text = text.split(marker, 1)[1].strip()

    if a.extract == "code":
        if "```" in text:
            parts = text.split("```")
            # Common patterns:
            # 1) ```lang\n<code>\n```  -> parts[1] starts with lang
            # 2) ```\n<code>\n```      -> parts[1] starts with newline
            if len(parts) >= 3:
                body = parts[1]
                if "\n" in body:
                    first, rest = body.split("\n", 1)
                    if first.strip().isalpha() and len(first.strip()) <= 16:
                        body = rest
                text = body.strip()
            else:
                text = parts[0].strip()
        else:
            # Heuristic fallback: if model returned code without fences.
            idx = text.find("func ")
            if idx == -1:
                idx = text.find("import ")
            if idx != -1:
                text = text[idx:].strip()

    print(text)


if __name__ == "__main__":
    main()

