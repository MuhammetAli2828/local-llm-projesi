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


def _get_donem():
    """DB'den aktif staj dönemi bilgisini çeker."""
    try:
        import sqlite3, pathlib
        db = sqlite3.connect(pathlib.Path(__file__).parent.parent / "staj.db")
        db.row_factory = sqlite3.Row
        rows = db.execute("SELECT key, value FROM settings").fetchall()
        db.close()
        return {r["key"]: r["value"] for r in rows}
    except Exception:
        return {}


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
                    elif gun_int < min_is and takvim_gun < 90:
                        warnings.append(
                            f"Staj gün sayısı ({gun_int}) belirtilen tarih aralığına göre az görünüyor."
                        )
                except (ValueError, TypeError):
                    errors.append("Staj gün sayısı geçerli bir sayı olmalıdır.")

            # Geçmiş tarih uyarısı — yalnızca bitiş de geçmişte ise
            if d_end < datetime.now():
                warnings.append("Staj tarihleri geçmişte kalmış; arşiv kaydı olabilir.")

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

    # 6) DB'den staj dönemi ayarları — yaz ve ara dönem
    donem = _get_donem()

    # Her iki dönemin verilerini al
    periods = [
        {
            "adi":     donem.get("yaz_donem_adi", "Yaz Dönemi"),
            "bas":     donem.get("yaz_staj_baslangic", ""),
            "bit":     donem.get("yaz_staj_bitis", ""),
            "min":     int(donem.get("yaz_min_staj_gun", 20) or 20),
            "son_bas": donem.get("yaz_basvuru_son_gun", ""),
        },
        {
            "adi":     donem.get("ara_donem_adi", "Ara Dönem"),
            "bas":     donem.get("ara_staj_baslangic", ""),
            "bit":     donem.get("ara_staj_bitis", ""),
            "min":     int(donem.get("ara_min_staj_gun", 20) or 20),
            "son_bas": donem.get("ara_basvuru_son_gun", ""),
        },
    ]

    # Staj gün sayısı kontrolü — hangi dönemdeyse ona göre min kontrol
    gun = data.get("staj_gun_sayisi")
    if gun and bd and bt:
        try:
            gun_int = int(gun)
            d_b = datetime.strptime(bd, "%Y-%m-%d")
            d_e = datetime.strptime(bt, "%Y-%m-%d")
            matched_min = None
            for p in periods:
                if p["bas"] and p["bit"]:
                    try:
                        pb = datetime.strptime(p["bas"], "%Y-%m-%d")
                        pe = datetime.strptime(p["bit"], "%Y-%m-%d")
                        if pb <= d_b and d_e <= pe:
                            matched_min = p["min"]
                            break
                    except ValueError:
                        pass
            min_gun_db = matched_min if matched_min is not None else 20
            if 0 < gun_int < min_gun_db:
                warnings.append(
                    f"Staj süresi {gun_int} gün. Bu dönem için minimum {min_gun_db} iş günü gerekiyor."
                )
        except (ValueError, TypeError):
            pass

    # Tarihler her iki dönemin de dışındaysa uyarı ver
    if bd and bt:
        try:
            d_b = datetime.strptime(bd, "%Y-%m-%d")
            d_e = datetime.strptime(bt, "%Y-%m-%d")
            in_any = False
            for p in periods:
                if p["bas"] and p["bit"]:
                    try:
                        pb = datetime.strptime(p["bas"], "%Y-%m-%d")
                        pe = datetime.strptime(p["bit"], "%Y-%m-%d")
                        if pb <= d_b and d_e <= pe:
                            in_any = True
                            break
                    except ValueError:
                        pass
            if not in_any:
                donem_str = "  |  ".join(
                    f"{p['adi']}: {p['bas']}–{p['bit']}"
                    for p in periods if p["bas"]
                )
                warnings.append(f"Tarihler tanımlı dönemler dışında. ({donem_str})")
        except ValueError:
            pass

    # Başvuru son gün kontrolü — her iki dönem için
    for p in periods:
        if p["son_bas"] and bd:
            try:
                son = datetime.strptime(p["son_bas"], "%Y-%m-%d")
                pb  = datetime.strptime(p["bas"], "%Y-%m-%d") if p["bas"] else None
                d_b = datetime.strptime(bd, "%Y-%m-%d")
                # Sadece bu döneme ait başvurular için kontrol et
                if pb and d_b >= pb and datetime.now() > son:
                    warnings.append(f"{p['adi']} başvuru son tarihi ({p['son_bas']}) geçmiş.")
            except ValueError:
                pass

    return {"missing": missing, "errors": errors, "warnings": warnings}