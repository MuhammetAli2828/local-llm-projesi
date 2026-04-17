"""
rule_service.py
===============
Staj başvuru formu kural tabanlı doğrulama.
Bölüm başkanı / sekreter mantığını taklit eder.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from services.form_service import REQUIRED_KEYS, normalize_date


def validate_form(data: Dict[str, Any]) -> Dict[str, List[str]]:
    """
    Döndürür:
      {
        "missing":  [...],   # Zorunlu eksik alanlar
        "errors":   [...],   # Mantıksal hatalar
        "warnings": [...],   # Uyarılar
      }
    """
    missing: List[str] = []
    errors: List[str] = []
    warnings: List[str] = []

    LABELS = {
        "ad_soyad":        "Ad Soyad",
        "ogrenci_no":      "Öğrenci No",
        "bolum":           "Bölüm/Program",
        "tc_kimlik_no":    "TC Kimlik No",
        "firma_adi":       "Firma Adı",
        "firma_adresi":    "Firma Adresi",
        "baslangic_tarihi":"Başlangıç Tarihi",
        "bitis_tarihi":    "Bitiş Tarihi",
        "staj_gun_sayisi": "Staj Gün Sayısı",
    }

    # 1) Zorunlu alanlar
    for key in REQUIRED_KEYS:
        val = data.get(key)
        if val is None or str(val).strip() in ("", "None", "null"):
            missing.append(LABELS.get(key, key))

    # 2) TC Kimlik No formatı
    tc = str(data.get("tc_kimlik_no") or "").strip()
    if tc and (not tc.isdigit() or len(tc) != 11):
        errors.append("TC Kimlik No 11 haneli rakam olmalıdır.")

    # 3) Tarih mantığı
    bd_raw = str(data.get("baslangic_tarihi") or "").strip()
    bt_raw = str(data.get("bitis_tarihi") or "").strip()
    bd = normalize_date(bd_raw)
    bt = normalize_date(bt_raw)

    if bd_raw and not bd:
        errors.append("Başlangıç tarihi geçersiz format (YYYY-MM-DD veya GG.AA.YYYY).")
    if bt_raw and not bt:
        errors.append("Bitiş tarihi geçersiz format.")

    if bd and bt:
        try:
            d_start = datetime.strptime(bd, "%Y-%m-%d")
            d_end = datetime.strptime(bt, "%Y-%m-%d")
            if d_end <= d_start:
                errors.append("Bitiş tarihi başlangıç tarihinden önce veya aynı olamaz.")

            # Staj gün sayısı tutarlılığı
            gun = data.get("staj_gun_sayisi")
            if gun:
                try:
                    gun_int = int(gun)
                    takvim_gun = (d_end - d_start).days
                    # İş günü yaklaşık = takvim_günü * 5/7
                    min_is = int(takvim_gun * 5 / 7) - 5
                    max_is = int(takvim_gun * 5 / 7) + 5
                    if gun_int < 1:
                        errors.append("Staj gün sayısı en az 1 olmalıdır.")
                    elif gun_int < min_is:
                        warnings.append(
                            f"Staj gün sayısı ({gun_int}) belirtilen tarih aralığına göre az görünüyor."
                        )
                except (ValueError, TypeError):
                    errors.append("Staj gün sayısı geçerli bir sayı olmalıdır.")

            # Geçmiş tarih uyarısı
            if d_start < datetime.now():
                warnings.append("Başlangıç tarihi geçmiş bir tarih.")

        except ValueError:
            pass

    # 4) Öğrenci No format kontrolü
    ono = str(data.get("ogrenci_no") or "").strip()
    if ono and len(ono) < 8:
        warnings.append("Öğrenci numarası çok kısa görünüyor.")

    # 5) Firma email format
    email = str(data.get("firma_eposta") or "").strip()
    if email and "@" not in email:
        warnings.append("Firma e-posta adresi geçersiz görünüyor.")

    # 6) Yönerge kuralı: staj min 20 iş günü (MYO için yaygın)
    gun = data.get("staj_gun_sayisi")
    if gun:
        try:
            gun_int = int(gun)
            if 0 < gun_int < 20:
                warnings.append(
                    f"Staj süresi {gun_int} gün. Bölümünüzün minimum staj süresini kontrol edin."
                )
        except (ValueError, TypeError):
            pass

    return {"missing": missing, "errors": errors, "warnings": warnings}