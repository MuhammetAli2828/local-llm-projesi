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