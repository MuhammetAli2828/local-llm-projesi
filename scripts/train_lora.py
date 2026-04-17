from __future__ import annotations

import os
import torch

from datasets import load_dataset
from peft import LoraConfig
from transformers import AutoModelForCausalLM, AutoTokenizer
from trl import SFTConfig, SFTTrainer

MODEL_NAME = "Qwen/Qwen2.5-3B-Instruct"
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRAIN_FILE = os.path.join(BASE_DIR, "data", "processed", "train_data_split.jsonl")
VAL_FILE = os.path.join(BASE_DIR, "data", "processed", "val_data.jsonl")
OUTPUT_DIR = os.path.join(BASE_DIR, "data", "outputs", "qwen25_amasya_staj_lora")


def main():
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, trust_remote_code=True)

    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # Tek cihaz seç
    if torch.cuda.is_available():
        torch_dtype = torch.float16
        model = AutoModelForCausalLM.from_pretrained(
            MODEL_NAME,
            trust_remote_code=True,
            torch_dtype=torch_dtype,
        )
        model = model.to("cuda")
    else:
        torch_dtype = torch.float32
        model = AutoModelForCausalLM.from_pretrained(
            MODEL_NAME,
            trust_remote_code=True,
            torch_dtype=torch_dtype,
        )
        model = model.to("cpu")

    model.config.use_cache = False
    model.gradient_checkpointing_enable()

    dataset = load_dataset(
        "json",
        data_files={
            "train": TRAIN_FILE,
            "validation": VAL_FILE,
        }
    )

    peft_config = LoraConfig(
        r=16,
        lora_alpha=32,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=[
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",                           
            "up_proj",
            "down_proj",
            "gate_proj",
        ],
    )

    args = SFTConfig(
        output_dir=OUTPUT_DIR,
        per_device_train_batch_size=1,
        per_device_eval_batch_size=1,
        gradient_accumulation_steps=8,
        learning_rate=2e-4,
        num_train_epochs=4,
        logging_steps=10,
        eval_strategy="steps",
        eval_steps=25,
        save_steps=25,
        save_total_limit=2,
        bf16=False,
        fp16=torch.cuda.is_available(),
        max_length=1024,
        packing=False,
        report_to="none",
    )

    trainer = SFTTrainer(
        model=model,
        args=args,
        train_dataset=dataset["train"],
        eval_dataset=dataset["validation"],
        processing_class=tokenizer,
        peft_config=peft_config,
    )

    trainer.train()
    trainer.model.save_pretrained(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)

    print("Eğitim tamamlandı.")
    print("Çıktı klasörü:", OUTPUT_DIR)


if __name__ == "__main__":
    main()
