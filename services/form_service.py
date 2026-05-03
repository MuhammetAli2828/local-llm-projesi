"""
form_service.py
===============
Form şeması ve yardımcı fonksiyonlar.
"""
from __future__ import annotations
import json
import re
from typing import Any, Dict

# ─── FORM ŞEMASI ──────────────────────────────────────────────────────────────
FORM_SCHEMA = {
    "ogrenci": {
        "label": "Öğrenci Bilgileri",
        "fields": [
            {"key": "ad_soyad",          "label": "Ad Soyad",           "type": "text",   "required": True},
            {"key": "ogrenci_no",         "label": "Öğrenci No",         "type": "text",   "required": True},
            {"key": "bolum",              "label": "Bölüm / Program",    "type": "text",   "required": True},
            {"key": "tc_kimlik_no",       "label": "TC Kimlik No",       "type": "text",   "required": True},
            {"key": "donem",              "label": "Eğitim Dönemi",      "type": "select",
             "options": ["Güz", "Bahar"],                                                  "required": False},
            {"key": "telefon_no",         "label": "Telefon No",         "type": "text",   "required": False},
            {"key": "ikametgah_adresi",   "label": "İkametgah Adresi",   "type": "text",   "required": False},
        ],
    },
    "staj": {
        "label": "Staj Bilgileri",
        "fields": [
            {"key": "firma_adi",          "label": "Firma Adı",          "type": "text",   "required": True},
            {"key": "firma_adresi",       "label": "Firma Adresi",       "type": "text",   "required": True},
            {"key": "hizmet_alani",       "label": "Hizmet Alanı",       "type": "text",   "required": False},
            {"key": "haftalik_calisilan_gun", "label": "Haftalık Gün",   "type": "number", "required": False},
            {"key": "firma_telefon",      "label": "Firma Telefon",      "type": "text",   "required": False},
            {"key": "firma_eposta",       "label": "Firma E-posta",      "type": "text",   "required": False},
            {"key": "firma_web",          "label": "Firma Web",          "type": "text",   "required": False},
            {"key": "firma_fax",          "label": "Firma Fax",          "type": "text",   "required": False},
            {"key": "baslangic_tarihi",   "label": "Başlangıç Tarihi",   "type": "date",   "required": True},
            {"key": "bitis_tarihi",       "label": "Bitiş Tarihi",       "type": "date",   "required": True},
            {"key": "staj_gun_sayisi",    "label": "Staj Gün Sayısı",    "type": "number", "required": True},
        ],
    },
    "departman": {
        "label": "Departman Bilgileri",
        "fields": [
            {"key": "departman_1", "label": "Departman 1", "type": "text", "required": False},
            {"key": "departman_2", "label": "Departman 2", "type": "text", "required": False},
            {"key": "departman_3", "label": "Departman 3", "type": "text", "required": False},
            {"key": "departman_4", "label": "Departman 4", "type": "text", "required": False},
            {"key": "personel_yonetici",  "label": "Yönetici Sayısı",    "type": "number", "required": False},
            {"key": "personel_muhendis",  "label": "Mühendis Sayısı",    "type": "number", "required": False},
            {"key": "personel_tekniker",  "label": "Tekniker Sayısı",    "type": "number", "required": False},
            {"key": "personel_usta",      "label": "Usta Sayısı",        "type": "number", "required": False},
            {"key": "personel_teknisyen", "label": "Teknisyen Sayısı",   "type": "number", "required": False},
            {"key": "personel_isci",      "label": "İşçi Sayısı",        "type": "number", "required": False},
        ],
    },
}

FIELD_KEYS: set[str] = {
    f["key"]
    for group in FORM_SCHEMA.values()
    for f in group["fields"]
}

REQUIRED_KEYS: set[str] = {
    f["key"]
    for group in FORM_SCHEMA.values()
    for f in group["fields"]
    if f.get("required")
}


def extract_json_object(text: str) -> Dict[str, Any] | None:
    """Metin içinden ilk JSON objesini çeker."""
    if not text:
        return None
    # ```json ... ``` bloğunu temizle
    text = re.sub(r"```json\s*", "", text)
    text = re.sub(r"```\s*", "", text)
    text = text.strip()

    # Doğrudan JSON denemesi
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass

    # İçinden JSON çek
    match = re.search(r"\{.*?\}", text, re.DOTALL)
    if match:
        try:
            obj = json.loads(match.group())
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass
    return None


def normalize_date(value: Any) -> str | None:
    """Tarihi YYYY-MM-DD formatına çevirir."""
    if not isinstance(value, str):
        return None
    v = value.strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
        return v
    m = re.fullmatch(r"(\d{1,2})[./-](\d{1,2})[./-](\d{4})", v)
    if m:
        d, mo, y = map(int, m.groups())
        return f"{y:04d}-{mo:02d}-{d:02d}"
    return None


# ─── PDF'DEN FORM ALANI ÇIKARIMI ──────────────────────────────────────────────
def _clean(s: str) -> str:
    """Label ardındaki boşluk, nokta, tire temizle."""
    return re.sub(r"\s+", " ", (s or "").strip(" :.-·—_\t"))


_LABEL_RE = re.compile(
    r"(B[öo]l[üu]m|Program|Ad[ıı]\s*Soyad|[ÖO][ğg]renci|"
    r"[İI]kametg|STAJ\s*YAPILAN|Adresi|Hizmet\s*Alan|Haftal[ıı]k|"
    r"Telefon|E-posta|Web\s*Adresi|Fax|TC\s*Kimlik|Ba[şs]lama|Biti[şs]|"
    r"Staj[ıı]n|Departman|Personel|[İI]mkan|Belge|[İI][şs]veren|"
    r"Beyan[ıı]m|[ÖO]nemli|AMASYA|ZORUNLU|KYT|[İI]lgili\s*Makama|"
    r"Fak[üu]ltemiz|[Öö]ğrencimizin|[Üü]cret|Yemek|Servis|Foto[ğg]raf|"
    r"N[üu]fus|Savc[ıı]l[ıı]k|[Üü]retim|Pazarlama|Muh|B[üu]ro|"
    r"Teknik|[İI]nsan|Staj[ıı]|tarih|aras[ıı]nda)",
    re.IGNORECASE,
)

def extract_fields_from_pdf_text(pdf_text: str) -> Dict[str, Any]:
    """
    Amasya MYO staj başvuru formu PDF metninden alanları çıkarır.
    Strateji: değerler PDF'in alt kısmında ayrı satırlar halinde gruplanmış olur.
    """
    if not pdf_text:
        return {}

    lines = [ln.strip() for ln in pdf_text.replace("\r", "\n").split("\n") if ln.strip()]
    joined = " | ".join(lines)

    extracted: Dict[str, Any] = {}

    # ── 1. Kesin kalıplarla al (tip tabanlı) ──────────────────────────────────

    # TC Kimlik: tam 11 rakam
    m = re.search(r'\b(\d{11})\b', joined)
    if m:
        extracted["tc_kimlik_no"] = m.group(1)

    # E-posta
    m = re.search(r'\b([\w.\-]+@[\w.\-]+\.\w+)\b', joined)
    if m:
        extracted["firma_eposta"] = m.group(1)

    # ISO tarihler (YYYY-MM-DD), ilk 2 farklı tanesini al
    dates: list = []
    for m in re.finditer(r'\b(\d{4}-\d{2}-\d{2})\b', joined):
        if m.group(1) not in dates:
            dates.append(m.group(1))
        if len(dates) == 2:
            break
    # dd.mm.yyyy veya dd/mm/yyyy
    for m in re.finditer(r'\b(\d{1,2}[./]\d{1,2}[./]\d{4})\b', joined):
        nd = normalize_date(m.group(1))
        if nd and nd not in dates:
            dates.append(nd)
        if len(dates) == 2:
            break
    if dates:
        extracted["baslangic_tarihi"] = dates[0]
    if len(dates) > 1:
        extracted["bitis_tarihi"] = dates[1]

    # Telefon numaraları: 0 ile başlayan 11 hane
    phones: list = []
    for m in re.finditer(r'\b(0\d{3}[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2})\b', joined):
        clean = re.sub(r'[\s\-]', '', m.group(1))
        if clean not in phones:
            phones.append(clean)
    if phones:
        extracted["telefon_no"] = phones[0]
    if len(phones) > 1:
        extracted["firma_telefon"] = phones[1]

    # ── 2. "Değer satırları" bloğunu bul ve sıralı parse et ───────────────────
    # Bu PDF'te değerler form etiketleri bittikten sonra ayrı satırlar halinde gelir.
    # Etiket olmayan, kısa veya anlamlı satırlar değer satırıdır.

    def is_label_line(line: str) -> bool:
        """Satır template etiketi mi?"""
        return bool(_LABEL_RE.search(line)) or line.endswith(':') or (
            ':' in line and len(line) < 120 and not re.search(r'@', line)
        )

    # Template bitiş satırını bul: "Savcılık Belgesi" satırı (sayfa 1 son checkbox)
    template_end_idx = 0
    for i, line in enumerate(lines):
        if re.search(r'Savc[ıı]l[ıı]k\s*Belge', line, re.IGNORECASE):
            template_end_idx = i + 1
            break
    # Fallback: "Ücret Yemek" satırının 2 sonrası
    if not template_end_idx:
        for i, line in enumerate(lines):
            if re.search(r'[Üü]cret.{1,20}Yemek|[Üü]cret.{1,5}Foto', line, re.IGNORECASE):
                template_end_idx = i + 2
                break

    val_lines = []
    for line in lines[template_end_idx:]:
        # Sayfa 2 başladığında dur
        if re.search(r'[İI][şs]veren|YETK[İI]L[İI]', line, re.IGNORECASE):
            break
        # Güz/Bahar dönem seçimi
        if re.match(r'^(G[üu]z|Bahar)$', line, re.IGNORECASE):
            extracted["donem"] = line
            continue
        # Etiket satırı değilse değer olarak al
        if not is_label_line(line) and len(line) >= 2:
            val_lines.append(line)

    # Değer satırlarını sırayla ata
    # Bilinen tipler: 11-digit (TC), 6-10 digit (öğrenci no), telefon, tarih, email zaten alındı
    # Geri kalanlar metin alanları — sıra: bölüm, ad_soyad(?), öğrenci no, tel, ikametgah,
    #   firma_adi, firma_adresi, hizmet_alani, haftalık_gün, firma_tel
    text_queue = []
    tc_val = extracted.get("tc_kimlik_no", "")

    for line in val_lines:
        # Zaten alınanları atla
        if line == tc_val:
            continue
        if re.match(r'^\d{4}-\d{2}-\d{2}$', line):
            continue
        if re.match(r'^(G[üu]z|Bahar)$', line, re.IGNORECASE):
            continue
        if re.match(r'^[\w.\-]+@[\w.\-]+\.\w+$', line):
            continue

        # Sadece rakam
        if re.match(r'^\d+$', line):
            n = len(line)
            val = line
            if n == 11 and val == tc_val:
                continue
            if n == 11:  # başka 11-digit: muhtemelen öğrenci tel tekrar
                continue
            if 6 <= n <= 10 and not extracted.get("ogrenci_no"):
                extracted["ogrenci_no"] = val
                continue
            if 1 <= n <= 3 and not extracted.get("staj_gun_sayisi"):
                extracted["staj_gun_sayisi"] = val
                continue
            if n == 1 and not extracted.get("haftalik_calisilan_gun"):
                extracted["haftalik_calisilan_gun"] = val
                continue
            continue

        # Metin değeri
        text_queue.append(line)

    # Sıra: bölüm → (ad_soyad eğer varsa) → ikametgah → firma_adi → firma_adresi → hizmet_alani
    text_fields = ["bolum", "ikametgah_adresi", "firma_adi", "firma_adresi", "hizmet_alani"]
    tf_idx = 0
    for val in text_queue:
        if tf_idx >= len(text_fields):
            break
        field = text_fields[tf_idx]
        extracted[field] = val
        tf_idx += 1

    # ── 3. Satır içi etiket:değer (fallback, bazı PDF'lerde değer etiketle birlikte) ──
    def inline(patterns) -> str:
        for pat in patterns:
            m = re.search(pat, joined, re.IGNORECASE)
            if m:
                val = _clean(m.group(1)).split(" | ")[0].split("  ")[0]
                if val and len(val.strip()) > 1:
                    return val
        return ""

    if not extracted.get("ad_soyad"):
        # Sayfa 1: "Adı Soyadı :" satırından sonraki satır, sayfa 2'ye bakmadan
        p1 = joined.split("STAJ")[0] if "STAJ" in joined else joined
        m = re.search(r"Ad[ıı]\s*Soyad[ıı]\s*[:：]\s*([^|]{2,80})", p1, re.IGNORECASE)
        if m:
            val = _clean(m.group(1)).split("  ")[0]
            if val and len(val) > 1:
                extracted["ad_soyad"] = val

    if not extracted.get("firma_adi"):
        extracted["firma_adi"] = inline([
            r"STAJ\s*YAPILAN\s*YER[İI]N[^|]*\|\s*Ad[ıı]\s*[:：]\s*([^|]{3,120})",
        ])

    if not extracted.get("hizmet_alani"):
        extracted["hizmet_alani"] = inline([
            r"Hizmet\s*Alan[ıı]\s*[:：]\s*([^|:]{3,80}?)(?=\s{2,}|\s*\||\s*Haftal|$)",
        ])

    if not extracted.get("haftalik_calisilan_gun"):
        extracted["haftalik_calisilan_gun"] = inline([
            r"Haftal[ıı]k[^|:]*[:：]\s*(\d{1,2})",
        ])

    # Boş değerleri temizle
    return {k: v for k, v in extracted.items() if v and str(v).strip()}