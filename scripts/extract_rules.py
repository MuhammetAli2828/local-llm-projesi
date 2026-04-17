from __future__ import annotations

import json
from pathlib import Path
from pypdf import PdfReader

BASE = Path(__file__).resolve().parent.parent
RAW = BASE / "data" / "raw"
PROCESSED = BASE / "data" / "processed"
PROCESSED.mkdir(parents=True, exist_ok=True)


def read_pdf(path: Path) -> str:
    reader = PdfReader(str(path))
    parts = []
    for page in reader.pages:
        parts.append(page.extract_text() or "")
    return "\n".join(parts)


def main():
    yonerge_path = RAW / "yonerge.pdf"
    takvim_path = RAW / "staj_takvimi.pdf"

    yonerge_text = read_pdf(yonerge_path) if yonerge_path.exists() else ""
    takvim_text = read_pdf(takvim_path) if takvim_path.exists() else ""

    rules = {
        "meta": {
            "institution": "Amasya Üniversitesi",
            "domain": "staj işlemleri",
            "version": "v1"
        },
        "rules": [
            {
                "id": "R001",
                "topic": "yaz_okulu_staj",
                "rule_text": "Yaz okuluna devam eden öğrenciler yaz okulu süresince staj yapamaz.",
                "answer_short": "Hayır. Yaz okuluna devam eden öğrenciler yaz okulu süresince staj yapamaz.",
                "keywords": [
                    "yaz okulu",
                    "staj",
                    "yaz okulunda staj",
                    "hem yaz okulu hem staj",
                    "yaz okulundan ders alıyorum"
                ],
                "source": "yonerge"
            },
            {
                "id": "R002",
                "topic": "yaz_staji_yaz_okulu",
                "rule_text": "Yaz stajı yapacak öğrenciler yaz okulundan ders alamaz.",
                "answer_short": "Hayır. Yaz stajı yapacak öğrenciler yaz okulundan ders alamaz.",
                "keywords": [
                    "yaz stajı",
                    "yaz okulundan ders",
                    "yaz stajında yaz okulu",
                    "staj yaparken ders"
                ],
                "source": "takvim"
            },
            {
                "id": "R003",
                "topic": "imza_kase",
                "rule_text": "Staj belgeleri imzalı ve kaşeli olmalıdır. Onaysız belgeler değerlendirmeye alınmaz.",
                "answer_short": "Hayır. Belgeler imzalı ve kaşeli olmalıdır, onaysız belgeler değerlendirmeye alınmaz.",
                "keywords": [
                    "imza",
                    "kaşe",
                    "onaysız belge",
                    "imzasız belge",
                    "kaşesiz belge"
                ],
                "source": "yonerge"
            },
            {
                "id": "R004",
                "topic": "staj_yeri_degistirme",
                "rule_text": "Öğrenci staj yerini kurul bilgisi ve onayı olmadan değiştiremez.",
                "answer_short": "Hayır. Öğrenci staj yerini kurul bilgisi ve onayı olmadan değiştiremez.",
                "keywords": [
                    "staj yeri değiştirme",
                    "staj yerimi değiştirebilir miyim",
                    "başka firmaya geçebilir miyim"
                ],
                "source": "yonerge"
            },
            {
                "id": "R005",
                "topic": "devamsizlik",
                "rule_text": "İzinsiz veya mazeretsiz devamsızlık toplam staj süresinin yüzde 10'una ulaşırsa staj sonlandırılır.",
                "answer_short": "İzinsiz veya mazeretsiz devamsızlık toplam staj süresinin yüzde 10'una ulaşırsa staj sonlandırılır.",
                "keywords": [
                    "devamsızlık",
                    "kaç gün gelmezsem",
                    "staj devamsızlık sınırı",
                    "devam zorunluluğu"
                ],
                "source": "yonerge"
            },
            {
                "id": "R006",
                "topic": "staj_tarihleri",
                "rule_text": "2024-2025 yaz dönemi için staj tarih aralığı 30.06.2025 - 06.09.2025 arasındadır.",
                "answer_short": "2024-2025 yaz dönemi için staj tarih aralığı 30.06.2025 ile 06.09.2025 arasındadır.",
                "keywords": [
                    "staj tarihleri",
                    "staj ne zaman",
                    "staj ne zaman başlıyor",
                    "staj aralığı"
                ],
                "source": "takvim"
            },
            {
                "id": "R007",
                "topic": "basvuru_tarihleri",
                "rule_text": "2024-2025 yaz dönemi için staj başvuruları 24.03.2025 - 16.06.2025 arasındadır.",
                "answer_short": "2024-2025 yaz dönemi için staj başvuruları 24.03.2025 ile 16.06.2025 arasındadır.",
                "keywords": [
                    "başvuru tarihleri",
                    "staja ne zaman başvurulur",
                    "başvurular ne zaman"
                ],
                "source": "takvim"
            },
            {
                "id": "R008",
                "topic": "belge_teslimi",
                "rule_text": "Staj sonunda belgeler ve işyeri değerlendirme formu müdürlüğe teslim edilmelidir.",
                "answer_short": "Staj sonunda gerekli belgeler ve işyeri değerlendirme formu müdürlüğe teslim edilmelidir.",
                "keywords": [
                    "belge teslimi",
                    "evrakları ne zaman teslim edeceğim",
                    "staj sonu belge"
                ],
                "source": "yonerge"
            },
            {
                "id": "R009",
                "topic": "basarisiz_staj",
                "rule_text": "Başarısız olan öğrencinin stajı yenilenir.",
                "answer_short": "Başarısız olan öğrencinin stajı yenilenir.",
                "keywords": [
                    "stajdan kalırsam",
                    "başarısız staj",
                    "staj tekrar edilir mi"
                ],
                "source": "yonerge"
            }
        ],
        "raw_preview": {
            "yonerge": yonerge_text[:5000],
            "takvim": takvim_text[:3000]
        }
    }

    out_path = PROCESSED / "rules.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(rules, f, ensure_ascii=False, indent=2)

    print(f"Kurallar yazıldı: {out_path}")


if __name__ == "__main__":
    main()