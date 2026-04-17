from __future__ import annotations

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

BASE_MODEL = "Qwen/Qwen2.5-3B-Instruct"
ADAPTER_PATH = "data/outputs/qwen25_amasya_staj_lora"

TEST_QUESTIONS = [
    "yaz oklu staj aynı anda olur mu",
    "Yaz stajı yaparken yaz okulundan ders alabilir miyim?",
    "İmzasız belge teslim etsem olur mu?",
    "Staj yerimi onaysız değiştirebilir miyim?",
    "Devamsızlık sınırı nedir?",
    "Başvurular ne zaman?",
    "Staj tarihleri ne zaman?",
]

def build_model():
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, trust_remote_code=True)

    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    if torch.cuda.is_available():
        dtype = torch.float16
        base_model = AutoModelForCausalLM.from_pretrained(
            BASE_MODEL,
            trust_remote_code=True,
            torch_dtype=dtype,
        ).to("cuda")
    else:
        dtype = torch.float32
        base_model = AutoModelForCausalLM.from_pretrained(
            BASE_MODEL,
            trust_remote_code=True,
            torch_dtype=dtype,
        ).to("cpu")

    model = PeftModel.from_pretrained(base_model, ADAPTER_PATH)
    model.eval()

    return model, tokenizer


def ask_model(model, tokenizer, question: str) -> str:
    messages = [
        {
            "role": "system",
            "content": "Sen Amasya Üniversitesi staj asistanısın. Yürürlükteki staj kurallarına göre kısa, net ve doğru cevap ver."
        },
        {"role": "user", "content": question},
    ]

    prompt = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )

    inputs = tokenizer(prompt, return_tensors="pt", padding=True)

    if torch.cuda.is_available():
        inputs = {k: v.to("cuda") for k, v in inputs.items()}
    else:
        inputs = {k: v.to("cpu") for k, v in inputs.items()}

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=120,
            temperature=0.2,
            do_sample=True,
            pad_token_id=tokenizer.eos_token_id,
        )

    full_text = tokenizer.decode(outputs[0], skip_special_tokens=True)

    # Sadece model cevabını ayırmaya çalış
    if question in full_text:
        answer = full_text.split(question, 1)[-1].strip()
    else:
        answer = full_text.strip()

    return answer


def main():
    model, tokenizer = build_model()

    for q in TEST_QUESTIONS:
        print("=" * 80)
        print("SORU:", q)
        print("CEVAP:", ask_model(model, tokenizer, q))
        print()


if __name__ == "__main__":
    main()