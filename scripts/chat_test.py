from __future__ import annotations

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

BASE_MODEL = "Qwen/Qwen2.5-3B-Instruct"
ADAPTER_PATH = "data/outputs/qwen25_amasya_staj_lora"


def main():
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, trust_remote_code=True)
    base_model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        trust_remote_code=True,
        device_map="auto",
    )
    model = PeftModel.from_pretrained(base_model, ADAPTER_PATH)

    print("Model hazır. Çıkmak için q yaz.")

    while True:
        question = input("\nSen: ").strip()
        if question.lower() in {"q", "quit", "exit"}:
            break

        messages = [
            {
                "role": "system",
                "content": "Sen Amasya Üniversitesi staj asistanısın. Yürürlükteki staj yönergesine göre kısa, net ve doğru cevap ver."
            },
            {"role": "user", "content": question},
        ]

        prompt = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )
        inputs = tokenizer(prompt, return_tensors="pt").to(model.device)

        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=120,
                temperature=0.2,
                do_sample=True,
            )

        answer = tokenizer.decode(outputs[0], skip_special_tokens=True)
        print("\nModel:", answer)


if __name__ == "__main__":
    main()