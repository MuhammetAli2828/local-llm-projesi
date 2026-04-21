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


def extract_fields_from_pdf_text(pdf_text: str) -> Dict[str, Any]:
    """
    Amasya MYO staj başvuru formu PDF metninden regex ile alanları çıkarır.
    Döndürülen dict form şeması anahtarlarını kullanır.
    """
    if not pdf_text:
        return {}

    t = pdf_text.replace("\r", "\n")
    # Satır sonlarını normalize et
    lines = [ln.strip() for ln in t.split("\n") if ln.strip()]
    joined = " | ".join(lines)

    def find(patterns) -> str:
        """Verilen regex desenleri arasında ilk eşleşmeyi döner."""
        if isinstance(patterns, str):
            patterns = [patterns]
        for pat in patterns:
            m = re.search(pat, joined, re.IGNORECASE)
            if m:
                val = _clean(m.group(1))
                # "|" karakterine kadar al (satır ayracı)
                val = val.split(" | ")[0].split("  ")[0]
                if val and val not in (":", "-"):
                    return val
        return ""

    extracted: Dict[str, Any] = {}

    # Öğrenci
    extracted["ad_soyad"] = find([
        r"Ad[ıi]\s*Soyad[ıi]\s*[:：]?\s*([^|]{2,80})",
    ])
    extracted["ogrenci_no"] = find([
        r"[ÖOöo]ğ?renci\s*No\s*[:：]?\s*(\d{6,12})",
    ])
    extracted["bolum"] = find([
        r"B[öo]l[üu]m[üu]?\s*/?\s*(?:Program[ıi])?\s*[:：]\s*([^|:]{3,60}?)(?=\s{2,}|\s*TC\s|\s*T\.C|\s*\||\s*Ad[ıi]\s|$)",
        r"Program[ıi]\s*[:：]\s*([^|:]{3,60}?)(?=\s{2,}|\s*\||$)",
    ])
    extracted["tc_kimlik_no"] = find([
        r"TC\s*Kimlik\s*No\s*[:：]?\s*(\d{11})",
        r"T\.?C\.?\s*Kimlik\s*[:：]?\s*(\d{11})",
    ])
    extracted["telefon_no"] = find([
        r"(?:Telefon\s*No|Cep\s*Telefonu?)\s*[:：]?\s*(\+?\d[\d\s\-]{8,20})",
    ])
    extracted["ikametgah_adresi"] = find([
        r"[İI]kametg[âa]h?\s*Adresi\s*[:：]?\s*([^|]{5,200})",
    ])

    # Firma
    extracted["firma_adi"] = find([
        r"(?:STAJ YAPILAN YER[İI]N|STAJ YAPACA[ĞG]I YER).*?Ad[ıi]\s*[:：]?\s*([^|]{3,120})",
        r"Firma\s*Ad[ıi]\s*[:：]?\s*([^|]{3,120})",
        r"Kurum\s*Ad[ıi]\s*[:：]?\s*([^|]{3,120})",
    ])
    # Firma adresi: "STAJ YAPILAN" bölümünden sonra gelen "Adresi :" — ikametgah hariç
    m_fa = re.search(
        r"STAJ\s*YAPI?LAN[^|]*?Ad[ıi]\s*[:：][^|]*?\|\s*Adresi\s*[:：]\s*([^|]{5,200})",
        joined, re.IGNORECASE,
    )
    if m_fa:
        extracted["firma_adresi"] = _clean(m_fa.group(1)).split("  ")[0]
    else:
        # Fallback: "İkametgah" içermeyen ilk "Adresi :"
        for m in re.finditer(r"(?<!kametg[âa]h\s)Adresi\s*[:：]\s*([^|]{5,200})", joined, re.IGNORECASE):
            val = _clean(m.group(1)).split("  ")[0]
            if val:
                extracted["firma_adresi"] = val
                break

    extracted["hizmet_alani"] = find([
        r"Hizmet\s*Alan[ıi]\s*[:：]\s*([^|:]{3,80}?)(?=\s{2,}|\s*\||\s*Haftal[ıi]k|$)",
    ])
    extracted["haftalik_calisilan_gun"] = find([
        r"Haftal[ıi]k\s*(?:[ÇçCc]al[ıi][şs][ıi]lan\s*)?G[üu]n\s*[:：]?\s*(\d{1,2})",
    ])
    extracted["firma_telefon"] = find([
        r"(?:Firma\s*)?Telefon(?:\s*No)?\s*[:：]?\s*(\+?\d[\d\s\-()]{8,22})",
    ])
    extracted["firma_eposta"] = find([
        r"E[\-\s]?posta(?:\s*Adresi)?\s*[:：]?\s*([\w\.\-]+@[\w\.\-]+\.\w+)",
    ])
    extracted["firma_web"] = find([
        r"Web(?:\s*Adresi)?\s*[:：]?\s*((?:https?://)?[\w\.\-]+\.\w{2,}[\w/\.\-]*)",
    ])

    # Tarihler: dd.mm.yyyy veya dd/mm/yyyy biçiminde
    bas = find([
        r"(?:Staj[ıi]n)?\s*Ba[şs]lama\s*Tarihi\s*[:：]?\s*(\d{1,2}[./\-]\d{1,2}[./\-]\d{4})",
        r"Ba[şs]lang[ıi][çc]\s*Tarihi\s*[:：]?\s*(\d{1,2}[./\-]\d{1,2}[./\-]\d{4})",
    ])
    bit = find([
        r"(?:Staj[ıi]n)?\s*Biti[şs]\s*Tarihi\s*[:：]?\s*(\d{1,2}[./\-]\d{1,2}[./\-]\d{4})",
    ])
    if bas: extracted["baslangic_tarihi"] = normalize_date(bas) or bas
    if bit: extracted["bitis_tarihi"]     = normalize_date(bit) or bit

    extracted["staj_gun_sayisi"] = find([
        r"(\d{1,3})\s*i[şs]\s*g[üu]n[üu]",
        r"(?:Staj\s*)?G[üu]n\s*Say[ıi]s[ıi]\s*[:：]?\s*(\d{1,3})",
    ])

    # Boş değerleri temizle
    return {k: v for k, v in extracted.items() if v and str(v).strip()}