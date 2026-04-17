from __future__ import annotations

import json
import random
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
PROCESSED = BASE / "data" / "processed"

SYSTEM_QA = "Sen Amasya Üniversitesi staj asistanısın. Yürürlükteki staj yönergesi ve staj takvimine göre kısa, net ve doğru cevap ver."
SYSTEM_FORM = "Sen Amasya Üniversitesi staj formu doldurma asistanısın. Kullanıcının verdiği bilgileri toparla, eksik bilgileri kısa sorularla iste."
SYSTEM_SECRETARY = "Sen Amasya Üniversitesi staj sekreter yardımcısısın. Başvuruyu kurallara göre değerlendir, eksikleri ve hataları açıkça belirt."

QUESTION_TEMPLATES = [
    "{base}?",
    "Kanka {base}?",
    "{base} olur mu?",
    "{base} mümkün mü?",
    "{base} yapabilir miyim?",
    "Bir şey soracağım, {base}?",
    "{base} hakkında bilgi verir misin?",
]

PARAPHRASES = {
    "yaz_okulu_staj": [
        "staj yaparken yaz okulu yapabilir miyim",
        "yaz okulunda ders alıyorum staj yapabilir miyim",
        "hem yaz okulu hem staj olur mu",
        "yaz okulu sürecinde staj yapılır mı",
        "yaz okuluna gidip aynı anda staj yapabilir miyim",
    ],
    "yaz_staji_yaz_okulu": [
        "yaz stajı yaparken yaz okulundan ders alabilir miyim",
        "yaz stajında iken yaz okuluna yazılabilir miyim",
        "yaz stajı ile yaz okulu birlikte olur mu",
        "yaz stajı yaparsam yaz okuluna kayıt olabilir miyim",
    ],
    "imza_kase": [
        "belgeleri imzasız versem olur mu",
        "kaşe olmadan belge kabul edilir mi",
        "imzayı sonradan atsam olur mu",
        "onaysız evrak teslim edebilir miyim",
        "imza ve kaşe şart mı",
    ],
    "staj_yeri_degistirme": [
        "staj yerimi kendim değiştirebilir miyim",
        "onay almadan işyerini değiştirsem olur mu",
        "başka firmaya geçmek istiyorum direkt geçebilir miyim",
        "kurula sormadan staj yeri değişir mi",
    ],
    "devamsizlik": [
        "kaç gün devamsızlık hakkım var",
        "gelmezsem ne olur",
        "stajda devamsızlık sınırı nedir",
        "stajda yok yazılırsam ne olur",
    ],
    "staj_tarihleri": [
        "staj ne zaman başlıyor",
        "staj tarihleri ne",
        "yaz stajı hangi tarihler arasında",
        "staj başlangıç ve bitiş tarihleri nedir",
    ],
    "basvuru_tarihleri": [
        "başvurular ne zaman",
        "staja ne zaman başvurulur",
        "başvuru tarih aralığı nedir",
        "staj başvurusu için son gün ne zaman",
    ],
    "belge_teslimi": [
        "evrakları ne zaman teslim etmem lazım",
        "staj bitince belgeleri kime veriyorum",
        "işyeri değerlendirme formunu nereye teslim ederim",
        "staj dosyası ne zaman teslim edilir",
    ],
    "basarisiz_staj": [
        "stajdan kalırsam ne olur",
        "başarısız staj tekrar edilir mi",
        "stajı geçemezsem yeniden yapar mıyım",
    ],
}

FORM_SCENARIOS = [
    (
        "Adım Zeynep Yılmaz, öğrenci numaram 2212345678, bölümüm Bilgisayar Programcılığı.",
        "Bilgilerini aldım: ad soyadın Zeynep Yılmaz, öğrenci numaran 2212345678 ve bölümün Bilgisayar Programcılığı. Şimdi telefon numaranı, staj yapacağın işyerinin adını ve staj tarihlerini yazar mısın?"
    ),
    (
        "Ben Ahmet Kaya. Öğrenci no 2111122233. ABC Teknoloji'de 01.07.2025 ile 30.07.2025 arasında staj yapacağım.",
        "Tamam. Ad soyadın Ahmet Kaya, öğrenci numaran 2111122233, işyerin ABC Teknoloji ve staj tarihlerin 01.07.2025 - 30.07.2025 olarak görünüyor. Şimdi bölüm/program, telefon numarası ve işyeri adresini de yazar mısın?"
    ),
    (
        "Adım Elif Demir, telefon numaram 05551234567, staj yerim Nova Yazılım.",
        "Bilgilerinin bir kısmını aldım: ad soyadın Elif Demir, telefon numaran 05551234567 ve işyerin Nova Yazılım. Şimdi öğrenci numaranı, bölüm/programını ve staj tarihlerini de yazar mısın?"
    ),
]

SECRETARY_SCENARIOS = [
    (
        "Öğrenci yaz okulundan ders alıyor ve aynı dönemde yaz stajı yapmak istiyor. Uygun mu?",
        "Uygun değil. Yaz okuluna devam eden öğrenci yaz okulu süresince staj yapamaz. Yaz stajı yapacak öğrenci de yaz okulundan ders alamaz."
    ),
    (
        "Başvuru formunda imza ve kaşe yok. Kabul edilir mi?",
        "Eksik belge var. İmza ve kaşe olmadan onaysız belge kabul edilmez."
    ),
    (
        "Öğrenci kurul onayı almadan staj yerini değiştirmiş. Bu uygun mu?",
        "Uygun değil. Öğrenci staj yerini kurul bilgisi ve onayı olmadan değiştiremez."
    ),
]


def make_chat_row(system: str, user: str, assistant: str):
    return {
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
            {"role": "assistant", "content": assistant},
        ]
    }


def build_rule_rows(rules):
    rows = []
    for rule in rules:
        topic = rule["topic"]
        answer = rule["answer_short"]
        paraphrases = PARAPHRASES.get(topic, [])

        for phr in paraphrases:
            for tpl in QUESTION_TEMPLATES:
                user_q = tpl.format(base=phr)
                rows.append(make_chat_row(SYSTEM_QA, user_q, answer))

        rows.append(make_chat_row(
            SYSTEM_QA,
            f"{topic} hakkında bilgi verir misin?",
            answer
        ))

    return rows


def build_form_rows():
    rows = []
    for user, assistant in FORM_SCENARIOS:
        rows.append(make_chat_row(SYSTEM_FORM, user, assistant))
    return rows


def build_secretary_rows():
    rows = []
    for user, assistant in SECRETARY_SCENARIOS:
        rows.append(make_chat_row(SYSTEM_SECRETARY, user, assistant))
    return rows


def build_negative_rows():
    rows = [
        make_chat_row(
            SYSTEM_QA,
            "Staj yaparken aynı anda yaz okulunda ders de alırım diye düşünüyorum, sorun olur mu?",
            "Evet, sorun olur. Yaz okuluna devam eden öğrenci yaz okulu süresince staj yapamaz."
        ),
        make_chat_row(
            SYSTEM_QA,
            "İmzayı daha sonra atarım, önce belgeyi teslim etsem olur mu?",
            "Hayır. Belgeler imzalı ve kaşeli olmalıdır. Onaysız belgeler değerlendirmeye alınmaz."
        ),
        make_chat_row(
            SYSTEM_QA,
            "Staj yerimi kimseye sormadan değiştirdim, yine de geçerli olur mu?",
            "Hayır. Öğrenci staj yerini kurul bilgisi ve onayı olmadan değiştiremez."
        ),
    ]
    return rows


def main():
    rules_path = PROCESSED / "rules.json"
    with rules_path.open("r", encoding="utf-8") as f:
        rules_data = json.load(f)

    rows = []
    rows.extend(build_rule_rows(rules_data["rules"]))
    rows.extend(build_form_rows())
    rows.extend(build_secretary_rows())
    rows.extend(build_negative_rows())

    random.shuffle(rows)

    out_path = PROCESSED / "train_data.jsonl"
    with out_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"Toplam örnek sayısı: {len(rows)}")
    print(f"Yazıldı: {out_path}")


if __name__ == "__main__":
    main()