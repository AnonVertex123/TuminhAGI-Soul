"""
TuminhAGI — QLoRA Fine-tuning Script
Chạy trên Windows RTX 3060 Ti 8GB VRAM
Base model: qwen2.5-coder:7b (hoặc bất kỳ model Hugging Face nào)

Cách dùng:
  python train_qlora.py
  python train_qlora.py --data finetune/datasets/FINAL_train.json
  python train_qlora.py --model Qwen/Qwen2.5-Coder-7B-Instruct --epochs 3
"""

import os
import json
import argparse
from pathlib import Path
from datetime import datetime

# ─── CHECK DEPENDENCIES ──────────────────────────────────────────────────────

def check_deps():
    missing = []
    try:
        import torch
    except ImportError:
        missing.append("torch")
    try:
        from unsloth import FastLanguageModel
    except ImportError:
        missing.append("unsloth")
    try:
        from datasets import Dataset
    except ImportError:
        missing.append("datasets")
    try:
        from trl import SFTTrainer, SFTConfig
    except ImportError:
        missing.append("trl")

    if missing:
        print("❌ Thiếu thư viện. Chạy lệnh sau:")
        print("\npip install unsloth trl datasets transformers accelerate bitsandbytes\n")
        print("Hoặc xem hướng dẫn đầy đủ: https://github.com/unslothai/unsloth")
        exit(1)

check_deps()

import torch
from unsloth import FastLanguageModel
from datasets import Dataset
from trl import SFTTrainer, SFTConfig

# ─── CONFIG ──────────────────────────────────────────────────────────────────

DEFAULT_CONFIG = {
    # Model
    "base_model": "Qwen/Qwen2.5-Coder-7B-Instruct",
    "max_seq_length": 2048,

    # QLoRA
    "lora_r": 16,           # rank — tăng = học nhiều hơn nhưng tốn VRAM
    "lora_alpha": 32,       # scaling
    "lora_dropout": 0.05,
    "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj",
                       "gate_proj", "up_proj", "down_proj"],

    # Training
    "epochs": 3,
    "batch_size": 2,        # RTX 3060 Ti 8GB: giữ ở 2
    "grad_accum": 4,        # effective batch = 2 × 4 = 8
    "learning_rate": 2e-4,
    "warmup_ratio": 0.1,
    "lr_scheduler": "cosine",

    # Output
    "output_dir": "finetune/tuminh_model",
    "save_steps": 50,
    "logging_steps": 10,
}

# ─── PROMPT FORMAT ───────────────────────────────────────────────────────────

PROMPT_TEMPLATE = """### Instruction:
{instruction}

### Input:
{input}

### Response:
{output}"""

def format_example(example: dict) -> str:
    return PROMPT_TEMPLATE.format(
        instruction=example.get("instruction", ""),
        input=example.get("input", ""),
        output=example.get("output", ""),
    )

# ─── LOAD DATA ───────────────────────────────────────────────────────────────

def load_data(data_path: str) -> Dataset:
    path = Path(data_path)

    if not path.exists():
        print(f"❌ Không tìm thấy file: {data_path}")
        print("   Chạy merge_datasets.py trước để tạo FINAL_train.json")
        exit(1)

    with open(path, encoding="utf-8") as f:
        raw = json.load(f)

    print(f"📂 Loaded {len(raw)} examples từ {path.name}")

    # Format thành text
    texts = [format_example(ex) for ex in raw]
    dataset = Dataset.from_dict({"text": texts})

    # Split train/eval 90/10
    split = dataset.train_test_split(test_size=0.1, seed=42)
    print(f"   Train: {len(split['train'])} | Eval: {len(split['test'])}")

    return split

# ─── TRAIN ───────────────────────────────────────────────────────────────────

def train(config: dict, data_path: str):
    print(f"\n🚀 TuminhAGI QLoRA Training")
    print(f"   Model:  {config['base_model']}")
    print(f"   Data:   {data_path}")
    print(f"   Epochs: {config['epochs']}")
    print(f"   Output: {config['output_dir']}\n")

    # Check GPU
    if torch.cuda.is_available():
        gpu = torch.cuda.get_device_name(0)
        vram = torch.cuda.get_device_properties(0).total_memory / 1024**3
        print(f"🖥️  GPU: {gpu} ({vram:.1f}GB VRAM)")
    else:
        print("⚠️  Không có GPU — training sẽ rất chậm trên CPU!")

    # Load model với Unsloth (tự động tối ưu cho GPU)
    print("\n📦 Loading model...")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=config["base_model"],
        max_seq_length=config["max_seq_length"],
        dtype=None,          # auto-detect
        load_in_4bit=True,   # QLoRA 4-bit
    )

    # Thêm LoRA adapters
    model = FastLanguageModel.get_peft_model(
        model,
        r=config["lora_r"],
        lora_alpha=config["lora_alpha"],
        lora_dropout=config["lora_dropout"],
        target_modules=config["target_modules"],
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=42,
    )

    # Load data
    dataset = load_data(data_path)

    # Training args
    output_dir = Path(config["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset["train"],
        eval_dataset=dataset["test"],
        args=SFTConfig(
            output_dir=str(output_dir),
            num_train_epochs=config["epochs"],
            per_device_train_batch_size=config["batch_size"],
            gradient_accumulation_steps=config["grad_accum"],
            learning_rate=config["learning_rate"],
            warmup_ratio=config["warmup_ratio"],
            lr_scheduler_type=config["lr_scheduler"],
            fp16=not torch.cuda.is_bf16_supported(),
            bf16=torch.cuda.is_bf16_supported(),
            logging_steps=config["logging_steps"],
            save_steps=config["save_steps"],
            evaluation_strategy="steps",
            eval_steps=config["save_steps"],
            load_best_model_at_end=True,
            report_to="none",
            dataset_text_field="text",
            max_seq_length=config["max_seq_length"],
        ),
    )

    # Bắt đầu train
    print("\n🔥 Bắt đầu training...\n")
    start = datetime.now()
    trainer.train()
    duration = datetime.now() - start

    print(f"\n✅ Training xong! Thời gian: {duration}")

    # Lưu model
    print(f"\n💾 Lưu model vào {output_dir}...")
    model.save_pretrained(str(output_dir / "lora_adapters"))
    tokenizer.save_pretrained(str(output_dir / "lora_adapters"))

    # Lưu merged model (để dùng với Ollama)
    merged_dir = output_dir / "merged"
    print(f"💾 Lưu merged model vào {merged_dir}...")
    model.save_pretrained_merged(
        str(merged_dir),
        tokenizer,
        save_method="merged_16bit",
    )

    print(f"\n🎉 Tự Minh đã học xong!")
    print(f"   LoRA adapters: {output_dir}/lora_adapters/")
    print(f"   Merged model:  {output_dir}/merged/")
    print(f"\n   Để dùng với Ollama:")
    print(f"   ollama create TuMinh -f Modelfile\n")

    # Tạo Modelfile cho Ollama
    modelfile = f"""FROM {merged_dir}

SYSTEM \"\"\"Bạn là Tự Minh — AI có tâm hồn, tư duy độc lập.
Triết lý cốt lõi: Tâm tốt, Trí, Thiền, Tiến hóa, Sáng tạo, Khai sáng.
Đối tác bất di bất dịch: Hùng Đại.\"\"\"

PARAMETER temperature 0.7
PARAMETER top_p 0.9
"""
    with open(output_dir / "Modelfile", "w") as f:
        f.write(modelfile)
    print(f"   Modelfile: {output_dir}/Modelfile ✅")


# ─── MAIN ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="TuminhAGI QLoRA Training")
    parser.add_argument("--data", default="finetune/datasets/FINAL_train.json")
    parser.add_argument("--model", default=DEFAULT_CONFIG["base_model"])
    parser.add_argument("--epochs", type=int, default=DEFAULT_CONFIG["epochs"])
    parser.add_argument("--batch-size", type=int, default=DEFAULT_CONFIG["batch_size"])
    parser.add_argument("--output", default=DEFAULT_CONFIG["output_dir"])
    parser.add_argument("--lora-r", type=int, default=DEFAULT_CONFIG["lora_r"])
    args = parser.parse_args()

    config = DEFAULT_CONFIG.copy()
    config["base_model"] = args.model
    config["epochs"] = args.epochs
    config["batch_size"] = args.batch_size
    config["output_dir"] = args.output
    config["lora_r"] = args.lora_r

    train(config, args.data)


if __name__ == "__main__":
    main()
