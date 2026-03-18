"""
TuminhAGI — QLoRA Finetuning Script
====================================
Finetunes a quantized LLM with LoRA adapters on custom datasets.
Includes Windows compatibility patches for Unsloth (Triton-free).

Usage:
    python train_qlora.py \
        --model "unsloth/Qwen2.5-Coder-3B-Instruct-bnb-4bit" \
        --data  "finetune/datasets/tuminh_swift_v1_final.jsonl" \
        --epochs 5 --batch-size 1 \
        --output "I:/TuminhAgi/finetune/checkpoint/agi_swift_v1"
"""

import os, sys, builtins, json, argparse
import torch

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
try:
    # Fix Windows console UnicodeEncodeError (e.g., Unsloth prints emojis).
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

if torch.cuda.is_available():
    torch.cuda.empty_cache()

# Lệnh phong ấn: giới hạn VRAM GPU 0 (tránh OOM / fragment).
# Lưu ý: API này chỉ hoạt động khi CUDA available.
if torch.cuda.is_available():
    # 0.92 dễ sát trần trên GPU 8GB khi backward loss dùng functorch.
    torch.cuda.set_per_process_memory_fraction(0.92, 0)

from unittest.mock import MagicMock
from importlib.machinery import ModuleSpec

# ╔══════════════════════════════════════════════════════════════════╗
# ║  SECTION 1: WINDOWS COMPATIBILITY — Triton Mock & Env Setup    ║
# ╚══════════════════════════════════════════════════════════════════╝

os.environ.update({
    "UNSLOTH_USE_TRITON":           "0",
    "XFORMERS_FORCE_DISABLE_TRITON":"1",
    "TORCHINDUCTOR_TRITON":         "0",
    "PYTORCH_CUDA_ALLOC_CONF":      "expandable_segments:True",
    # On Windows, avoid torch.compile -> Inductor -> Triton.
    "TORCHDYNAMO_DISABLE":          "1",
    "TORCHINDUCTOR_DISABLE":        "1",
})

# Mock Triton module hierarchy (not available on Windows)
for _name in [
    "triton", "triton.compiler", "triton.runtime", "triton.runtime.autotuner",
    "triton.runtime.jit", "triton.runtime.helper", "triton.language",
    "triton.language.extra", "triton.backends", "triton.backends.nvidia",
    "triton.backends.nvidia.driver", "triton.backends.nvidia.compiler",
]:
    _m = MagicMock(); _m.__path__ = []; _m.__name__ = _name
    _m.__spec__ = ModuleSpec(_name, None); sys.modules[_name] = _m
sys.modules["triton"].__version__ = "3.1.0"

try:
    import torch._inductor.config
    torch._inductor.config.triton.enabled = False
except Exception: pass

try:
    import torch._dynamo
    torch._dynamo.config.disable = True
    torch._dynamo.config.suppress_errors = True
except Exception:
    pass

# Patch missing dtypes & builtins
for _i in range(1, 129):
    if not hasattr(torch, f"int{_i}"): setattr(torch, f"int{_i}", torch.int8)
if not hasattr(builtins, "Unpack"):
    setattr(builtins, "Unpack", type("Unpack", (), {}))

# ╔══════════════════════════════════════════════════════════════════╗
# ║  SECTION 2: PYTORCH KERNEL OVERRIDES (Triton-free fallbacks)   ║
# ╚══════════════════════════════════════════════════════════════════╝

import unsloth.kernels.rms_layernorm
import unsloth.kernels.rope_embedding
import unsloth.kernels.cross_entropy_loss
import unsloth.kernels.utils
import unsloth.kernels.fast_lora
import unsloth.kernels
import unsloth.models.llama
try: import unsloth_zoo.fused_losses.cross_entropy_loss
except Exception: pass

def safe_rms_layernorm(layernorm, X, gemma=False):
    W   = layernorm.weight
    eps = getattr(layernorm, "variance_epsilon", getattr(layernorm, "eps", 1e-6))
    return torch.nn.functional.rms_norm(X, (X.shape[-1],), W, eps)

def safe_rope_embedding(Q, K, cos, sin, position_ids=None):
    def _rotate(x):
        h = x.shape[-1] // 2
        return torch.cat((-x[..., h:], x[..., :h]), dim=-1)
    if position_ids is not None:
        c = cos.squeeze(1).squeeze(0) if cos.ndim == 4 else cos
        s = sin.squeeze(1).squeeze(0) if sin.ndim == 4 else sin
        idx = position_ids.reshape(-1)
        c = c.index_select(0, idx).reshape(position_ids.shape + (cos.shape[-1],))
        s = s.index_select(0, idx).reshape(position_ids.shape + (sin.shape[-1],))
    else:
        sl = Q.shape[2]
        c, s = cos[:, :, :sl, :], sin[:, :, :sl, :]
    while c.ndim < Q.ndim: c, s = c.unsqueeze(1), s.unsqueeze(1)
    if c.shape[1] != 1 and Q.shape[2] == c.shape[1]:
        c, s = c.transpose(1, 2), s.transpose(1, 2)
    return (Q * c) + (_rotate(Q) * s), (K * c) + (_rotate(K) * s)

def safe_cross_entropy_loss(*args, **kwargs):
    """Universal CE loss — handles both fused (hidden_states+lm_head) and direct (logits) paths."""
    hs     = kwargs.get("hidden_states", args[0] if args else None)
    labels = kwargs.get("labels", args[1] if len(args) > 1 else None)
    n_items= kwargs.get("n_items")

    if hs is not None and "lm_head_weight" in kwargs:
        # Memory-safe CE: avoid materializing full logits (N x V).
        W = kwargs["lm_head_weight"]  # [V, H]
        b = kwargs.get("lm_head_bias")  # [V] or None

        if hs.ndim == 3:
            hs = hs.view(-1, hs.shape[-1])
            labels = labels.view(-1)

        # Filter valid labels
        valid = labels != -100
        if not torch.any(valid):
            return hs.new_zeros(())
        hs = hs[valid]
        labels = labels[valid]

        # Compute true-class logits: (hs * W[labels]).sum(-1) + b[label]
        W_y = W.index_select(0, labels).to(dtype=hs.dtype)  # [N, H]
        logit_y = (hs * W_y).sum(dim=-1).to(torch.float32)
        if b is not None:
            logit_y = logit_y + b.index_select(0, labels).to(torch.float32)

        # Chunked logsumexp over vocabulary to keep memory low.
        V = W.shape[0]
        chunk = int(kwargs.get("vocab_chunk_size", 4096))
        m = None
        s = None
        hs_f = hs.to(torch.float32)
        for start in range(0, V, chunk):
            end = min(start + chunk, V)
            Wc = W[start:end].to(torch.float32)  # [c, H]
            lc = hs_f @ Wc.t()                   # [N, c]
            if b is not None:
                lc = lc + b[start:end].to(torch.float32)
            # online logsumexp update
            lc_max = lc.max(dim=-1).values  # [N]
            if m is None:
                m = lc_max
                s = torch.exp(lc - m.unsqueeze(-1)).sum(dim=-1)
            else:
                m_new = torch.maximum(m, lc_max)
                s = s * torch.exp(m - m_new) + torch.exp(lc - m_new.unsqueeze(-1)).sum(dim=-1)
                m = m_new
            del Wc, lc
        logsumexp = m + torch.log(s)

        loss = (logsumexp - logit_y).sum()
        if n_items is None:
            n_items = max(labels.numel(), 1)
        return loss / n_items
    else:
        logits = kwargs.get("logits", hs)

    if logits is None or labels is None:
        raise RuntimeError(f"CE loss: missing logits/labels. keys={list(kwargs.keys())}")
    if logits.ndim == 3:
        logits = logits.view(-1, logits.shape[-1])
        labels = labels.view(-1)

    loss = torch.nn.functional.cross_entropy(logits.float(), labels, ignore_index=-100, reduction="sum")
    if n_items is None:
        n_items = max(torch.count_nonzero(labels != -100).item(), 1)
    return loss / n_items

def safe_matmul_lora(X, W, W_quant, A, B, s, out=None):
    """Dtype-safe LoRA matmul: base_out = X@W + s*(X@A)@B"""
    from unsloth.kernels.utils import fast_dequantize
    d    = X.dtype
    flat = X.dim() == 3
    if flat:
        b, sl, hd = X.shape; X = X.view(-1, hd)
    W_full  = fast_dequantize(W, W_quant, use_global_buffer=False) if W_quant is not None else W
    result  = torch.matmul(X, W_full.t().to(d))
    if A is not None:
        result += torch.matmul(torch.matmul(X, A.t().to(d)), B.t().to(d)) * s
    return result.view(b, sl, -1) if flat else result

def patched_matmul_lora(X, W, W_quant, A, B, s, out=None):
    """
    Patch Unsloth's matmul_lora dtype bug under autocast:
    - original uses dtype = X.dtype (often float32) but `out` is autocast to bf16/fp16
    - addmm_ then fails (out bf16, B float32).
    Fix: choose dtype = out.dtype AFTER base matmul.
    """
    from unsloth.kernels.utils import (
        Float8Tensor,
        fast_dequantize,
        torch_matmul,
        fp8_linear,
    )

    if X.dim() == 3:
        batch, seq_len, _d = X.shape
        X2 = X.view(-1, X.shape[-1])
        reshape = True
    else:
        X2 = X
        reshape = False

    if isinstance(W, Float8Tensor):
        assert W.ndim == 2
        if W.block_size[0] == W.shape[0] and W.block_size[1] == 1:
            W = W.dequantize()
        else:
            W = W.contiguous()
        out2 = torch_matmul(X2, W.t(), out=out)
    elif W.dtype == torch.float8_e4m3fn:
        out2 = fp8_linear(X2, W, W_quant)
    else:
        Wd = fast_dequantize(W, W_quant, use_global_buffer=True)
        out2 = torch_matmul(X2, Wd.t(), out=out)
        if W_quant is not None:
            del Wd

    dtype = out2.dtype
    if A is not None:
        A_t, B_t = A.t(), B.t()
        XA = torch_matmul(X2, A_t.to(dtype))
        out2.addmm_(XA, B_t.to(dtype), alpha=s)

    return out2.view(batch, seq_len, -1) if reshape else out2

# ╔══════════════════════════════════════════════════════════════════╗
# ║  SECTION 3: NAMESPACE PATCHING                                 ║
# ╚══════════════════════════════════════════════════════════════════╝

# Patch kernel functions in all relevant modules
_kernel_patches = {
    "fast_rms_layernorm":    safe_rms_layernorm,
    "fast_rope_embedding":   safe_rope_embedding,
}
_target_modules = [
    unsloth.kernels.rms_layernorm, unsloth.kernels.rope_embedding,
    unsloth.kernels.cross_entropy_loss, unsloth.kernels.utils,
    unsloth.kernels.fast_lora, unsloth.kernels, unsloth.models.llama,
]
try:
    import unsloth.models.qwen2
    _target_modules.append(unsloth.models.qwen2)
except Exception: pass

for _mod in _target_modules:
    for _attr, _fn in _kernel_patches.items():
        if hasattr(_mod, _attr): setattr(_mod, _attr, _fn)

# matmul_lora patch can OOM (forces full dequant + dtype cast).
# Only enable explicitly if you need it for debugging:
#   set TUMINH_FORCE_SAFE_MATMUL_LORA=1
if os.environ.get("TUMINH_FORCE_SAFE_MATMUL_LORA", "0") == "1":
    for _mod in _target_modules:
        if hasattr(_mod, "matmul_lora"):
            setattr(_mod, "matmul_lora", safe_matmul_lora)

# Always patch matmul_lora dtype under autocast (no full dequant copy).
for _mod in _target_modules:
    if hasattr(_mod, "matmul_lora"):
        setattr(_mod, "matmul_lora", patched_matmul_lora)

# Always use Safe CE (chunked) on 8GB Windows to avoid Functorch OOM spikes.
if True: # Always patch
    for _mod_name in [
        "unsloth_zoo.loss_utils", "unsloth_zoo.fused_losses.cross_entropy_loss",
        "unsloth.models._utils", "unsloth.models.llama", "unsloth.models.qwen2",
    ]:
        try:
            sys.modules[_mod_name].__dict__["unsloth_fused_ce_loss"] = safe_cross_entropy_loss
        except Exception:
            pass

# ╔══════════════════════════════════════════════════════════════════╗
# ║  SECTION 4: LORA BACKWARD-PASS DTYPE SURGERY                  ║
# ╚══════════════════════════════════════════════════════════════════╝

from unsloth.kernels.fast_lora import LoRA_MLP, LoRA_QKV, LoRA_W, torch_amp_custom_bwd
from unsloth.kernels.utils import fast_dequantize as _dequant
from unsloth.kernels.utils import matmul_lora as _unsloth_matmul_lora

def _safe_addmm(out, m1, m2, alpha=1, beta=0):
    """In-place dtype-safe addmm: out = beta*out + alpha*(m1 @ m2)"""
    d = out.dtype
    if beta:
        out.mul_(beta)
    else:
        out.zero_()
    out.addmm_(m1.to(d), m2.to(d), alpha=alpha)
    return out

@staticmethod
@torch_amp_custom_bwd
def _mlp_bwd(ctx, dY):
    gateW, gateW_q, gateS, upW, upW_q, upS, downW, downW_q, downS, bwd_fn = ctx.custom_saved_tensors
    gateA, gateB, upA, upB, downA, downB, X, e, g = ctx.saved_tensors
    B, S, H = X.shape
    # Use gradient dtype (autocast) to avoid Float vs Half/BF16 mismatches.
    d = dY.dtype
    dY, X, e, g = [t.view(-1, t.shape[-1]) for t in (dY, X, e, g)]
    gA, gB = gateA.to(d).t(), gateB.to(d).t()
    uA, uB = upA.to(d).t(),   upB.to(d).t()
    dA, dB = downA.to(d).t(), downB.to(d).t()
    # Use Unsloth's matmul_lora (global buffer) to reduce VRAM spikes.
    DW = _unsloth_matmul_lora(dY, downW.t(), downW_q, dB, dA, downS)
    h, df, de = bwd_fn(DW, e, g)
    dd_A, dd_B = torch.empty_like(dA), torch.empty_like(dB)
    dg_A, dg_B = torch.empty_like(gA), torch.empty_like(gB)
    du_A, du_B = torch.empty_like(uA), torch.empty_like(uB)
    _safe_addmm(dd_A, h.t(), dY @ dB.t(), alpha=downS)
    _safe_addmm(dd_B, dA.t() @ h.t(), dY, alpha=downS)
    _safe_addmm(du_A, X.t(), df @ uB.t(), alpha=upS)
    _safe_addmm(du_B, uA.t() @ X.t(), df, alpha=upS)
    _safe_addmm(dg_A, X.t(), de @ gB.t(), alpha=gateS)
    _safe_addmm(dg_B, gA.t() @ X.t(), de, alpha=gateS)
    W = _dequant(upW.t(), upW_q)
    w_dtype = W.dtype
    dX = torch.matmul(df.to(w_dtype), W.t()); del W
    _safe_addmm(dX, df @ uB.t(), uA.t(), alpha=upS, beta=1)
    W = _dequant(gateW.t(), gateW_q)
    w_dtype = W.dtype
    _safe_addmm(dX, de.to(w_dtype), W.t(), beta=1); del W
    _safe_addmm(dX, de @ gB.t(), gA.t(), alpha=gateS, beta=1)
    return (dX.view(B,S,H), None,None, dg_A.t(),dg_B.t(),None, None,None, du_A.t(),du_B.t(),None,
            None,None, dd_A.t(),dd_B.t(),None, None,None,None)

@staticmethod
@torch_amp_custom_bwd
def _qkv_bwd(ctx, dQ, dK, dV):
    QW,QW_q,QS, KW,KW_q,KS, VW,VW_q,VS = ctx.custom_saved_tensors
    X, QA,QB, KA,KB, VA,VB = ctx.saved_tensors
    B,S,H = X.shape
    d = dQ.dtype
    dQ = dQ.view(-1,dQ.shape[-1]); dK = dK.reshape(-1,dK.shape[-1])
    dV = dV.view(-1,dV.shape[-1]); X  = X.view(-1,X.shape[-1])
    qa,qb = QA.to(d).t(), QB.to(d).t(); ka,kb = KA.to(d).t(), KB.to(d).t()
    va,vb = VA.to(d).t(), VB.to(d).t()
    dqa,dqb = torch.empty_like(qa), torch.empty_like(qb)
    dka,dkb = torch.empty_like(ka), torch.empty_like(kb)
    dva,dvb = torch.empty_like(va), torch.empty_like(vb)
    for dd,da,db,dg,scl,a,b in [(dqa,dqb,dQ,X,QS,qa,qb),(dka,dkb,dK,X,KS,ka,kb),(dva,dvb,dV,X,VS,va,vb)]:
        _safe_addmm(dd, dg.t(), db @ b.t(), alpha=scl)
        _safe_addmm(da, a.t() @ dg.t(), db, alpha=scl)
    W = _dequant(QW.t(), QW_q)
    w_dtype = W.dtype
    dX = torch.matmul(dQ.to(w_dtype), W.t()); del W
    _safe_addmm(dX, dQ @ qb.t(), qa.t(), alpha=QS, beta=1)
    for dg, w, wq, a, b, scl in [(dK,KW,KW_q,ka,kb,KS),(dV,VW,VW_q,va,vb,VS)]:
        W = _dequant(w.t(), wq)
        w_dtype = W.dtype
        _safe_addmm(dX, dg.to(w_dtype), W.t(), beta=1); del W
        _safe_addmm(dX, dg @ b.t(), a.t(), alpha=scl, beta=1)
    return (dX.view(B,S,H), None,None,dqa.t(),dqb.t(),None, None,None,dka.t(),dkb.t(),None,
            None,None,dva.t(),dvb.t(),None, None)

@staticmethod
@torch_amp_custom_bwd
def _w_bwd(ctx, dY):
    W, W_q, scl = ctx.custom_saved_tensors
    A, B, X = ctx.saved_tensors
    B_,S,H = X.shape
    d = dY.dtype
    dY = dY.reshape(-1, dY.shape[-1]); X = X.reshape(-1, X.shape[-1])
    a, b = A.to(d).t(), B.to(d).t()
    da, db = torch.empty_like(a), torch.empty_like(b)
    _safe_addmm(da, X.t(), dY @ b.t(), alpha=scl)
    _safe_addmm(db, a.t() @ X.t(), dY, alpha=scl)
    Wd = _dequant(W.t(), W_q)
    w_dtype = Wd.dtype
    dX = dY.to(w_dtype) @ Wd.t(); del Wd
    _safe_addmm(dX, dY @ b.t(), a.t(), alpha=scl, beta=1)
    return dX.view(B_,S,H), None, None, da.t(), db.t(), None

# Always patch LoRA backward on Windows to avoid dtype mismatches (Float vs Half/BF16).
# Note: This may slightly increase VRAM usage but is required for stability.
if True: # Always patch
    LoRA_MLP.backward = _mlp_bwd
    LoRA_QKV.backward = _qkv_bwd
    LoRA_W.backward   = _w_bwd

print("[BOOT] Windows compatibility patches applied.")

# ╔══════════════════════════════════════════════════════════════════╗
# ║  SECTION 5: TRAINING CONFIG & LOGIC                            ║
# ╚══════════════════════════════════════════════════════════════════╝

from unsloth import FastLanguageModel
from trl import SFTTrainer, SFTConfig
from datasets import Dataset

# Set memory fraction for PyTorch CUDA allocator
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "max_split_size_mb:512,fraction:0.92"

CONFIG = {
    "base_model":     "unsloth/Qwen2.5-Coder-3B-Instruct-bnb-4bit",
    # 8GB VRAM (3060 Ti): start conservative, then scale up gradually.
    "max_seq_length": 128,
    "lora_r":         8,
    "lora_alpha":     16,
    "lora_dropout":   0,
    # Expand LoRA coverage for better learning.
    "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    "epochs":         5,
    "batch_size":     1,
    "grad_accum":     8,
    "learning_rate":  2e-4,
    "warmup_ratio":   0.1,
    "lr_scheduler":   "cosine",
    "output_dir":     "I:/TuminhAgi/finetune/checkpoint/agi_swift_v1",
    "logging_steps":  1,
}

PROMPT = """### Instruction:\n{instruction}\n\n### Input:\n{input}\n\n### Response:\n{output}"""


def load_data(path):
    print(f"[DATA] Loading: {path}")
    examples = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try: examples.append(json.loads(line))
                except Exception: continue
    texts = [PROMPT.format(
        instruction=ex.get("instruction", "Build SwiftUI view."),
        input=ex.get("input", ""),
        output=ex.get("output", ""),
    ) for ex in examples]
    ds = Dataset.from_dict({"text": texts}).train_test_split(test_size=0.05, seed=42)
    print(f"[DATA] {len(ds['train'])} train / {len(ds['test'])} eval examples.")
    return ds


def train(cfg, data_path):
    print(f"[MODEL] Loading: {cfg['base_model']}")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=cfg["base_model"],
        max_seq_length=cfg["max_seq_length"],
        dtype=None, load_in_4bit=True,
    )
    model = FastLanguageModel.get_peft_model(
        model, r=cfg["lora_r"],
        target_modules=cfg["target_modules"],
        lora_alpha=cfg["lora_alpha"],
        lora_dropout=cfg["lora_dropout"],
        bias="none", use_gradient_checkpointing="unsloth", random_state=3407,
    )

    # --- DTYPE ổn định trên Windows ---
    # Option: disable AMP entirely (use fp32) to avoid dtype/scaler edge cases.
    #   set TUMINH_NO_AMP=1
    no_amp = os.environ.get("TUMINH_NO_AMP", "0") == "1"

    # Giữ base model ở 4-bit, chỉ ép các tham số LoRA (requires_grad) sang dtype train.
    # BF16 chỉ dùng khi GPU hỗ trợ, nếu không thì fallback sang FP16.
    use_bf16 = False
    if not no_amp:
        # Enable BF16 explicitly if desired:
        #   set TUMINH_USE_BF16=1
        if os.environ.get("TUMINH_USE_BF16", "0") == "1" and torch.cuda.is_available():
            major, _minor = torch.cuda.get_device_capability()
            use_bf16 = (major >= 8) and torch.cuda.is_bf16_supported()

    train_dtype = torch.float32 if no_amp else (torch.bfloat16 if use_bf16 else torch.float16)

    for _name, param in model.named_parameters():
        if param.requires_grad:
            param.data = param.data.to(train_dtype)
            if param.grad is not None:
                param.grad.data = param.grad.data.to(train_dtype)

    model.config.torch_dtype = train_dtype

    if torch.cuda.is_available():
        torch.cuda.empty_cache() # Dọn dẹp cabin trước khi cất cánh
    ds = load_data(data_path)
    trainer = SFTTrainer(
        model=model, tokenizer=tokenizer,
        train_dataset=ds["train"], eval_dataset=ds["test"],
        dataset_text_field="text", max_seq_length=cfg["max_seq_length"],
        args=SFTConfig(
            per_device_train_batch_size=cfg["batch_size"],
            gradient_accumulation_steps=cfg["grad_accum"],
            warmup_ratio=cfg["warmup_ratio"],
            num_train_epochs=cfg["epochs"],
            learning_rate=cfg["learning_rate"],
            fp16=(not no_amp) and (not use_bf16),
            bf16=(not no_amp) and use_bf16,
            logging_steps=cfg["logging_steps"],
            optim="paged_adamw_8bit",
            weight_decay=0.01,
            lr_scheduler_type=cfg["lr_scheduler"],
            seed=42,
            output_dir=cfg["output_dir"],
            report_to="none",
            save_strategy="no",
        ),
    )

    print("\n[TRAIN] GO!\n")
    trainer.train()

    save_path = os.path.join(cfg["output_dir"], "lora_model")
    model.save_pretrained(save_path)
    tokenizer.save_pretrained(save_path)
    print(f"\n[DONE] Model saved to {save_path}")


def main():
    p = argparse.ArgumentParser(description="TuminhAGI QLoRA Finetuning")
    p.add_argument("--data",       default="finetune/datasets/tuminh_swift_v1_final.jsonl")
    p.add_argument("--model",      default=CONFIG["base_model"])
    p.add_argument("--epochs",     type=int, default=CONFIG["epochs"])
    p.add_argument("--batch-size", type=int, default=CONFIG["batch_size"])
    p.add_argument("--max-seq-length", type=int, default=CONFIG["max_seq_length"])
    p.add_argument("--output",     default=CONFIG["output_dir"])
    a = p.parse_args()
    cfg = {**CONFIG, "base_model": a.model, "epochs": a.epochs,
           "batch_size": a.batch_size, "max_seq_length": a.max_seq_length,
           "output_dir": a.output}
    train(cfg, a.data)


if __name__ == "__main__":
    main()