"""
app.py  —  Amasya MYO Staj Asistanı (Flask)
"""
from __future__ import annotations # selam

import json
import os
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path

from functools import wraps

from flask import (Flask, jsonify, redirect, render_template,
                   request, send_file, session, url_for)

app              = Flask(__name__)
app.secret_key   = "amasya-myo-staj-2025-gizli"
BASE    = Path(__file__).parent
DB_PATH = BASE / "staj.db"
UPLOAD  = BASE / "uploads" / "pdfs"
RAPORLAR = BASE / "uploads" / "raporlar"
YONERGE = BASE / "yonerge.pdf"
DOCS    = BASE / "docs"
MODEL          = "qwen2.5:latest"
FINETUNED_MODEL = "amasya-staj:latest"  # Modelfile ile üretilen LoRA modeli

def aktif_model() -> str:
    """Settings'ten model seçimini oku — fine-tuned veya base."""
    try:
        kullan = get_setting("use_finetuned") == "1"
        return FINETUNED_MODEL if kullan else MODEL
    except Exception:
        return MODEL

UPLOAD.mkdir(parents=True, exist_ok=True)
RAPORLAR.mkdir(parents=True, exist_ok=True)
DOCS.mkdir(parents=True, exist_ok=True)

def bildirim_ekle(tip: str, mesaj: str, link_id: int = None):
    with get_db() as c:
        c.execute("INSERT INTO bildirimler (tip,mesaj,link_id,tarih) VALUES (?,?,?,?)",
                  (tip, mesaj, link_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

# Kullanıcı adı → (şifre, rol)
USERS = {
    "ogrenci":  {"password": "ogrenci123",  "role": "ogrenci"},
    "sekreter": {"password": "sekreter123", "role": "sekreter"},
}

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "role" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

def sekreter_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get("role") != "sekreter":
            return jsonify({"ok": False, "hata": "Yetkisiz erişim"}), 403
        return f(*args, **kwargs)
    return decorated

# ─── DB ───────────────────────────────────────────────────────────────────────

def get_db():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    with get_db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS submissions (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            original_adi   TEXT,
            yukleme_tarihi TEXT,
            durum          TEXT DEFAULT 'beklemede',
            ai_karar       TEXT,
            ai_mesaj       TEXT,
            ai_rapor       TEXT,
            ai_guven       REAL,
            extracted_json TEXT,
            missing_json   TEXT
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS staj_raporlari (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            submission_id  INTEGER,
            dosya_adi      TEXT,
            dosya_yolu     TEXT,
            yukleme_tarihi TEXT,
            durum          TEXT DEFAULT 'beklemede',
            sekreter_notu  TEXT
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS bildirimler (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            tip     TEXT,
            mesaj   TEXT,
            link_id INTEGER,
            okundu  INTEGER DEFAULT 0,
            tarih   TEXT
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT
        )""")
        # 2025-2026 yaz ve ara dönem varsayılan değerleri
        defaults = {
            # Yaz dönemi
            "yaz_donem_adi":       "2025-2026 Yaz Dönemi",
            "yaz_staj_baslangic":  "2026-06-22",
            "yaz_staj_bitis":      "2026-09-18",
            "yaz_min_staj_gun":    "20",
            "yaz_basvuru_son_gun": "2026-06-13",
            # Ara dönem
            "ara_donem_adi":       "2025-2026 Ara Dönem",
            "ara_staj_baslangic":  "2026-01-19",
            "ara_staj_bitis":      "2026-02-13",
            "ara_min_staj_gun":    "20",
            "ara_basvuru_son_gun": "2026-01-09",
        }
        for k, v in defaults.items():
            c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?,?)", (k, v))

def get_setting(key: str) -> str:
    row = get_db().execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else ""

init_db()

# Eski DB'lere yeni kolonlar (migration)
def _migrate():
    with get_db() as c:
        for table, col, typ in [
            ("submissions",    "ai_detay_json", "TEXT"),
            ("staj_raporlari", "ai_analiz",     "TEXT"),
            ("staj_raporlari", "ai_skor",       "INTEGER"),
        ]:
            try:
                c.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")
            except sqlite3.OperationalError:
                pass

        # Eski "beklemede" başvuruları AI önerilerine göre karar bağla
        c.execute("""
            UPDATE submissions
               SET durum = CASE
                   WHEN ai_karar = 'KABUL' THEN 'onaylandi'
                   WHEN ai_karar = 'RED'   THEN 'reddedildi'
                   ELSE durum
                 END
             WHERE durum = 'beklemede'
               AND ai_karar IN ('KABUL','RED')
        """)
_migrate()

# ─── SERVİSLER ────────────────────────────────────────────────────────────────

_services = {}

def load_services():
    if _services:
        return _services["ol"], _services["rag"]
    from services.ollama_service import OllamaClient
    from services.pdf_service import extract_pdf_text
    from rag_index import TfidfRagIndex
    ol  = OllamaClient()
    rag = TfidfRagIndex(chunk_size=600, overlap=100)
    # Varsayılan yönerge
    if YONERGE.exists():
        rag.add_document("yonerge.pdf", extract_pdf_text(str(YONERGE)))
    # docs/ klasöründeki tüm PDF'ler
    for pdf in sorted(DOCS.glob("*.pdf")):
        text = extract_pdf_text(str(pdf))
        if text.strip():
            rag.add_document(pdf.name, text)
    _services["ol"]  = ol
    _services["rag"] = rag
    return ol, rag

def _llm_extract_form(pdf_text: str) -> dict:
    """PDF metninden form alanlarını LLM ile JSON olarak çıkar."""
    from services.form_service import extract_json_object, normalize_date
    if not pdf_text or len(pdf_text.strip()) < 30:
        return {}
    ol, _ = load_services()
    sistem = (
        "Sen bir form ayrıştırıcısın. Verilen PDF metninden staj başvuru alanlarını "
        "JSON olarak çıkaracaksın. SADECE JSON döndür, başka açıklama yazma. "
        "Bulamadığın alanları JSON'a dahil etme, tahmin etme."
    )
    kullanici = (
        "Şu alanları çıkar ve JSON objesi olarak döndür:\n"
        "ad_soyad, ogrenci_no, bolum, tc_kimlik_no, telefon_no, ikametgah_adresi, "
        "firma_adi, firma_adresi, firma_telefon, firma_eposta, hizmet_alani, "
        "baslangic_tarihi (YYYY-MM-DD), bitis_tarihi (YYYY-MM-DD), "
        "staj_gun_sayisi (sayı), haftalik_calisilan_gun (sayı).\n\n"
        f"PDF METNİ:\n{pdf_text[:3500]}\n\n"
        "JSON:"
    )
    try:
        model = ol.available_model(aktif_model())
        raw = ol.chat(
            model=model,
            messages=[{"role":"system","content":sistem},
                      {"role":"user","content":kullanici}],
            timeout=90, options={"temperature":0.0},
        )
        parsed = extract_json_object(raw) or {}
        # Tarih normalizasyonu
        for k in ("baslangic_tarihi","bitis_tarihi"):
            if parsed.get(k):
                nd = normalize_date(str(parsed[k]))
                if nd: parsed[k] = nd
        # Boş değerleri at
        return {k: v for k, v in parsed.items()
                if v and str(v).strip() and str(v).strip() not in ("null","None","-")}
    except Exception as e:
        print(f"[LLM Extract] {e}")
        return {}


def get_kurallar():
    """Geriye dönük uyumluluk için ham parça döndürür."""
    _, rag = load_services()
    queries = [
        "staj süresi minimum gün",
        "zorunlu belgeler başvuru",
        "başvuru şartları öğrenci",
        "değerlendirme onay kriterleri",
    ]
    seen, chunks = set(), []
    for q in queries:
        for hit in rag.search(q, top_k=2):
            if hit.chunk_text not in seen:
                seen.add(hit.chunk_text)
                chunks.append(hit.chunk_text[:260])
    return chunks


# Yapılandırılmış kural cache'i — LLM ile üretilir, in-memory tutulur
_KURALLAR_CACHE = {"data": None, "ts": 0}

def get_kurallar_yapilandirilmis():
    """Yönerge + sistem tarihlerine dayalı, kategorize teknik kural maddeleri.
    Anında döner (LLM bağımlılığı yok) — sistem tarihleri değişince otomatik güncellenir."""
    import time as _time
    global _KURALLAR_CACHE

    # Aktif dönem tarihleri
    yaz_b   = get_setting("yaz_staj_baslangic")
    yaz_s   = get_setting("yaz_staj_bitis")
    yaz_son = get_setting("yaz_basvuru_son_gun")
    yaz_min = get_setting("yaz_min_staj_gun") or "20"
    ara_b   = get_setting("ara_staj_baslangic")
    ara_s   = get_setting("ara_staj_bitis")
    ara_son = get_setting("ara_basvuru_son_gun")
    ara_min = get_setting("ara_min_staj_gun") or "20"

    # Cache anahtarı: tarihler değiştiyse cache geçersiz
    cache_key = f"{yaz_b}{yaz_s}{yaz_son}{yaz_min}{ara_b}{ara_s}{ara_son}{ara_min}"
    if _KURALLAR_CACHE.get("key") == cache_key and _KURALLAR_CACHE.get("data"):
        return _KURALLAR_CACHE["data"]

    def _tr_tarih(iso):
        """2026-06-22 → 22.06.2026"""
        if not iso or len(iso) < 10: return iso or "—"
        try:
            return f"{iso[8:10]}.{iso[5:7]}.{iso[0:4]}"
        except Exception:
            return iso

    kategoriler = [
        {"baslik": "Staj Süresi", "ikon": "⏱️", "maddeler": [
            f"Yaz dönemi penceresi: {_tr_tarih(yaz_b)} – {_tr_tarih(yaz_s)}",
            f"Ara dönem penceresi: {_tr_tarih(ara_b)} – {_tr_tarih(ara_s)}",
            f"Minimum staj: {yaz_min} iş günü",
            "Haftalık 5–6 iş günü çalışılmalı",
        ]},
        {"baslik": "Başvuru Süreci", "ikon": "📝", "maddeler": [
            f"Yaz son başvuru: {_tr_tarih(yaz_son)}",
            f"Ara son başvuru: {_tr_tarih(ara_son)}",
            "Form eksiksiz ve okunaklı doldurulmalı",
            "PDF formu sekretere iletilir",
        ]},
        {"baslik": "Zorunlu Bilgiler", "ikon": "📑", "maddeler": [
            "Ad-Soyad, TC Kimlik No, Öğrenci No",
            "Bölüm/Program ve iletişim",
            "Firma adı, adresi, telefonu",
            "Başlangıç ve bitiş tarihleri",
        ]},
        {"baslik": "Devam ve Disiplin", "ikon": "⚠️", "maddeler": [
            "Devamsızlık staj kabulünü etkiler",
            "Staj defteri düzenli tutulmalı",
            "Mazeretsiz devamsızlık → iptal",
        ]},
        {"baslik": "Karar Süreci", "ikon": "✅", "maddeler": [
            "Uygun başvurular AI ile onaylanır",
            "Eksik/hatalı başvurular reddedilir",
            "Sonuç anında öğrenciye bildirilir",
        ]},
    ]
    _KURALLAR_CACHE = {"data": kategoriler, "key": cache_key, "ts": _time.time()}
    return kategoriler

def agent_analiz(form_data: dict, pdf_text: str = "") -> dict:
    """Hızlı karar: sadece KABUL/RED + mesaj döndürür (30s timeout)."""
    from services.rule_service import validate_form
    from services.form_service import extract_json_object

    v        = validate_form(form_data)
    is_valid = not v["missing"] and not v["errors"]
    eksikler = v["missing"]

    donem_info = (
        f"Yaz: {get_setting('yaz_staj_baslangic')}–{get_setting('yaz_staj_bitis')} "
        f"| Ara: {get_setting('ara_staj_baslangic')}–{get_setting('ara_staj_bitis')}"
    )
    form_ozet = ", ".join(
        f"{k}={val}" for k, val in form_data.items()
        if val and str(val).strip() and k in (
            "ad_soyad","ogrenci_no","bolum","firma_adi",
            "baslangic_tarihi","bitis_tarihi","staj_gun_sayisi"
        )
    )

    prompt = (
        "Staj başvurusunu değerlendir. SADECE JSON döndür:\n"
        f"Dönemler: {donem_info}\n"
        f"Form: {form_ozet}\n"
        f"Eksik zorunlu alanlar: {eksikler if eksikler else 'YOK'}\n"
        f"Doğrulama: {'GEÇERSİZ' if not is_valid else 'GEÇERLİ'}\n\n"
        "Kural: Zorunlu alan yoksa KABUL, eksik alan varsa RED ver.\n"
        '{"karar":"KABUL","mesaj":"1 cümle gerekçe","guven":0.9}'
    )

    ol, _ = load_services()
    try:
        model = ol.available_model(aktif_model())
        raw   = ol.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            timeout=35, options={"temperature": 0.05},
        )
        parsed = extract_json_object(raw)
        if parsed and "karar" in parsed:
            karar = parsed["karar"] if parsed["karar"] in ("KABUL","RED") else ("KABUL" if is_valid else "RED")
            mesaj = parsed.get("mesaj", "")
            if isinstance(mesaj, dict): mesaj = str(mesaj)
            return {
                "karar": karar, "mesaj": mesaj,
                "guven": float(parsed.get("guven", 0.8)),
                "eksikler": eksikler, "rapor": raw, "ai_detay": {},
            }
    except Exception as e:
        print(f"[agent_analiz hızlı] {e}")

    # Fallback: kural tabanlı karar
    karar = "KABUL" if is_valid else "RED"
    mesaj = "Tüm zorunlu alanlar dolu." if is_valid else f"Eksik alanlar: {', '.join(eksikler)}"
    return {"karar": karar, "mesaj": mesaj, "guven": 0.7,
            "eksikler": eksikler, "rapor": "", "ai_detay": {}}


def _ai_zengin_analiz_arka_plan(sub_id: int, form_data: dict, pdf_text: str):
    """Arka planda çalışır: detaylı analiz (risk, firma, tarih, öneriler)."""
    from services.rule_service import validate_form
    from services.form_service import extract_json_object
    import threading

    def _calis():
        try:
            v = validate_form(form_data)
            form_ozet = json.dumps(
                {k: val for k, val in form_data.items() if val and str(val).strip()},
                ensure_ascii=False,
            )
            donem_info = (
                f"Yaz: {get_setting('yaz_donem_adi')} ({get_setting('yaz_staj_baslangic')}–{get_setting('yaz_staj_bitis')})\n"
                f"Ara: {get_setting('ara_donem_adi')} ({get_setting('ara_staj_baslangic')}–{get_setting('ara_staj_bitis')})"
            )
            prompt = (
                "Staj başvurusunu detaylı analiz et. SADECE JSON döndür:\n"
                f"Dönemler:\n{donem_info}\n"
                f"Form: {form_ozet}\n"
                f"Eksikler: {v['missing']}\nUyarılar: {v['warnings']}\n"
                + (f"PDF özet: {pdf_text[:600]}\n" if pdf_text else "")
                + '{\n"risk_skoru":0-100,\n"firma_analizi":"...",\n'
                  '"tarih_analizi":"...",\n"ogrenci_yorumu":"...",\n'
                  '"oneriler":["..."],\n"dikkat":["..."]\n}'
            )
            ol, _ = load_services()
            model = ol.available_model(aktif_model())
            raw   = ol.chat(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                timeout=90, options={"temperature": 0.1},
            )
            parsed = extract_json_object(raw)
            if parsed:
                ai_detay = {
                    "risk_skoru":     int(parsed.get("risk_skoru", 50)) if str(parsed.get("risk_skoru","50")).isdigit() else 50,
                    "firma_analizi":  str(parsed.get("firma_analizi", "")),
                    "tarih_analizi":  str(parsed.get("tarih_analizi", "")),
                    "ogrenci_yorumu": str(parsed.get("ogrenci_yorumu", "")),
                    "oneriler": parsed.get("oneriler",[]) if isinstance(parsed.get("oneriler"), list) else [],
                    "dikkat":   parsed.get("dikkat",[])   if isinstance(parsed.get("dikkat"),   list) else [],
                }
                with get_db() as c:
                    c.execute(
                        "UPDATE submissions SET ai_detay_json=?, ai_rapor=? WHERE id=?",
                        (json.dumps(ai_detay, ensure_ascii=False), raw[:1000], sub_id),
                    )
                print(f"[Zengin analiz] #{sub_id} tamamlandı")
        except Exception as e:
            print(f"[Zengin analiz] #{sub_id} hata: {e}")

    threading.Thread(target=_calis, daemon=True).start()

# ─── ROTALAR ──────────────────────────────────────────────────────────────────

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        user = USERS.get(username)
        if user and user["password"] == password:
            session["role"]     = user["role"]
            session["username"] = username
            return redirect(url_for("index"))
        error = "Kullanıcı adı veya şifre hatalı."
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def index():
    return render_template("index.html", role=session["role"])

@app.route("/api/kurallar")
def api_kurallar():
    try:
        kategoriler = get_kurallar_yapilandirilmis()
        return jsonify({"ok": True, "kategoriler": kategoriler})
    except Exception as e:
        return jsonify({"ok": False, "kategoriler": [], "hata": str(e)})

@app.route("/api/validate", methods=["POST"])
def api_validate():
    from services.rule_service import validate_form
    data = request.get_json(force=True) or {}
    v    = validate_form(data)
    msgs = []
    for m in v["missing"]:
        msgs.append({"t": "err",  "m": f"Zorunlu alan eksik: {m}"})
    for e in v["errors"]:
        msgs.append({"t": "err",  "m": e})
    for w in v["warnings"]:
        msgs.append({"t": "warn", "m": w})
    if not msgs:
        filled = sum(1 for k in ["ad_soyad","ogrenci_no","bolum","firma_adi",
                                  "baslangic_tarihi","bitis_tarihi","staj_gun_sayisi"]
                     if data.get(k) and str(data[k]).strip())
        if filled >= 7:
            msgs.append({"t": "ok",   "m": "Tüm zorunlu alanlar dolu ✓"})
        else:
            msgs.append({"t": "info", "m": "Formu doldurmaya devam edin…"})
    return jsonify({"msgs": msgs})

@app.route("/api/pdf", methods=["POST"])
def api_pdf():
    from services.pdf_service import fill_staj_pdf
    data = request.get_json(force=True) or {}
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        path = tmp.name
    try:
        fill_staj_pdf(data, path)
        return send_file(path, mimetype="application/pdf",
                         as_attachment=True,
                         download_name="staj_basvuru.pdf")
    except Exception as e:
        return jsonify({"ok": False, "hata": str(e)}), 500

@app.route("/api/yukle", methods=["POST"])
def api_yukle():
    from services.pdf_service import extract_pdf_text
    from services.form_service import extract_fields_from_pdf_text
    file = request.files.get("pdf")
    if not file:
        return jsonify({"ok": False, "hata": "Dosya yok"}), 400

    form_json = request.form.get("form_data", "")
    user_form = json.loads(form_json) if form_json else {}

    # PDF'i doğrudan UPLOAD klasörüne kaydet (tempfile Windows'ta sorunlu)
    import uuid
    UPLOAD.mkdir(parents=True, exist_ok=True)
    gecici_ad  = f"upload_{uuid.uuid4().hex}.pdf"
    gecici_yol = UPLOAD / gecici_ad
    file.save(str(gecici_yol))
    tmp_path   = str(gecici_yol)
    pdf_text   = extract_pdf_text(tmp_path)

    # 1) Regex ile çıkar
    extracted = extract_fields_from_pdf_text(pdf_text) if pdf_text.strip() else {}

    # 2) LLM ile zorunlu eksikleri tamamla
    required = ["ad_soyad","ogrenci_no","bolum","tc_kimlik_no",
                "firma_adi","firma_adresi","baslangic_tarihi",
                "bitis_tarihi","staj_gun_sayisi"]
    if pdf_text.strip() and any(k not in extracted for k in required):
        llm_extracted = _llm_extract_form(pdf_text)
        for k, v in llm_extracted.items():
            if k not in extracted and v:
                extracted[k] = v

    # 3) Kullanıcının manuel girdiği alanlar PDF üzerine yazar
    for k, v in user_form.items():
        if v and str(v).strip():
            extracted[k] = v

    form_data = extracted

    print(f"[YUKLE] form_data keys: {list(form_data.keys())}")
    print(f"[YUKLE] form_data: {json.dumps({k:v for k,v in form_data.items() if v}, ensure_ascii=False)}")
    result = agent_analiz(form_data, pdf_text)

    with get_db() as c:
        cur = c.execute(
            """INSERT INTO submissions
               (original_adi, yukleme_tarihi, durum,
                ai_karar, ai_mesaj, ai_rapor, ai_guven,
                extracted_json, missing_json, ai_detay_json)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                file.filename,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "onaylandi" if result["karar"] == "KABUL" else "reddedildi",
                result["karar"],
                result["mesaj"],
                result.get("rapor", ""),
                result.get("guven", 0.0),
                json.dumps(form_data, ensure_ascii=False),
                json.dumps(result.get("eksikler", []), ensure_ascii=False),
                json.dumps(result.get("ai_detay", {}), ensure_ascii=False),
            ),
        )
        sub_id = cur.lastrowid

    # Geçici PDF'i sub_id ile yeniden adlandır
    pdf_kalici = UPLOAD / f"{sub_id}.pdf"
    if pdf_kalici.exists():
        pdf_kalici.unlink()
    gecici_yol.rename(pdf_kalici)

    # Arka planda zengin analiz başlat
    _ai_zengin_analiz_arka_plan(sub_id, form_data, pdf_text)

    # Sekreter bildirimi
    ad = form_data.get("ad_soyad", file.filename)
    bildirim_ekle("basvuru", f"Yeni başvuru: {ad} — AI kararı: {result['karar']}", sub_id)

    tarih_bilgi = {
        "baslangic": form_data.get("baslangic_tarihi", ""),
        "bitis":     form_data.get("bitis_tarihi", ""),
        "staj_gun":  form_data.get("staj_gun_sayisi", ""),
    }
    return jsonify({"ok": True, "id": sub_id, "tarihler": tarih_bilgi,
                    "form_data": form_data, **result})

@app.route("/api/staj-donem", methods=["GET"])
def api_staj_donem_get():
    keys = [
        "yaz_donem_adi","yaz_staj_baslangic","yaz_staj_bitis",
        "yaz_min_staj_gun","yaz_basvuru_son_gun",
        "ara_donem_adi","ara_staj_baslangic","ara_staj_bitis",
        "ara_min_staj_gun","ara_basvuru_son_gun",
    ]
    return jsonify({k: get_setting(k) for k in keys})

@app.route("/api/staj-donem", methods=["POST"])
@sekreter_required
def api_staj_donem_set():
    data = request.get_json(force=True) or {}
    allowed = [
        "yaz_donem_adi","yaz_staj_baslangic","yaz_staj_bitis",
        "yaz_min_staj_gun","yaz_basvuru_son_gun",
        "ara_donem_adi","ara_staj_baslangic","ara_staj_bitis",
        "ara_min_staj_gun","ara_basvuru_son_gun",
        "use_finetuned",
    ]
    with get_db() as c:
        for k in allowed:
            if k in data:
                c.execute("INSERT OR REPLACE INTO settings (key,value) VALUES (?,?)",
                          (k, str(data[k])))
    return jsonify({"ok": True})

@app.route("/api/model-info")
def api_model_info():
    """Mevcut aktif model ve mevcut Ollama modelleri."""
    try:
        from services.ollama_service import OllamaClient
        info = OllamaClient().health()
        return jsonify({
            "ok": info.get("ok"),
            "aktif_model": aktif_model(),
            "mevcut_modeller": info.get("models", []),
            "use_finetuned": get_setting("use_finetuned") == "1",
            "finetuned_model": FINETUNED_MODEL,
            "base_model": MODEL,
        })
    except Exception as e:
        return jsonify({"ok": False, "hata": str(e)})

@app.route("/api/basvuru/pdf/<int:sub_id>")
@sekreter_required
def api_basvuru_pdf(sub_id):
    pdf_yol = UPLOAD / f"{sub_id}.pdf"
    if not pdf_yol.exists():
        return "PDF bulunamadı", 404
    return send_file(str(pdf_yol), mimetype="application/pdf")

@app.route("/api/basvurular")
@sekreter_required
def api_basvurular():
    rows = get_db().execute(
        "SELECT * FROM submissions ORDER BY id DESC"
    ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        # Sadece PDF'i kalıcı kaydedilmiş başvurular gösterilir
        if not (UPLOAD / f"{d['id']}.pdf").exists():
            continue
        d["pdf_var"] = True
        out.append(d)
    return jsonify(out)

@app.route("/api/karar", methods=["POST"])
@sekreter_required
def api_karar():
    data   = request.get_json(force=True) or {}
    sub_id = data.get("id")
    karar  = data.get("karar")
    durum  = "onaylandi" if karar == "KABUL" else "reddedildi"
    with get_db() as c:
        # Sadece durum güncellenir — ai_karar (AI önerisi) korunur
        c.execute("UPDATE submissions SET durum=? WHERE id=?", (durum, sub_id))
    return jsonify({"ok": True})

@app.route("/api/chat", methods=["POST"])
def api_chat():
    data    = request.get_json(force=True) or {}
    soru    = data.get("soru", "").strip()
    gecmis  = data.get("gecmis", [])   # [{role, content}, ...]
    if not soru:
        return jsonify({"yanit": "Soru boş."})

    ol, rag = load_services()
    # Yönergeden ilgili bölümleri RAG ile çek
    hits    = rag.search(soru, top_k=4)
    context = "\n\n".join(f"[Yönerge] {h.chunk_text[:700]}" for h in hits) if hits else ""

    # Staj dönemi bilgisini sisteme ekle
    donem_keys = [
        "yaz_donem_adi","yaz_staj_baslangic","yaz_staj_bitis","yaz_basvuru_son_gun","yaz_min_staj_gun",
        "ara_donem_adi","ara_staj_baslangic","ara_staj_bitis","ara_basvuru_son_gun","ara_min_staj_gun",
    ]
    d = {k: get_setting(k) for k in donem_keys}

    # Yaz dönemi gün hesabı (yaz tatili = staj penceresinin tüm günleri)
    def _gun_say(b, s):
        try:
            from datetime import date as _date
            ba = _date.fromisoformat(b); so = _date.fromisoformat(s)
            return (so - ba).days + 1
        except Exception:
            return None
    yaz_pencere_gun = _gun_say(d.get('yaz_staj_baslangic',''), d.get('yaz_staj_bitis',''))
    ara_pencere_gun = _gun_say(d.get('ara_staj_baslangic',''), d.get('ara_staj_bitis',''))

    donem_bilgi = (
        f"AKTİF STAJ DÖNEMLERİ (sistemde tanımlı resmi tarihler):\n"
        f"☀️ {d.get('yaz_donem_adi','Yaz Dönemi')}\n"
        f"   Staj penceresi: {d.get('yaz_staj_baslangic','')} → {d.get('yaz_staj_bitis','')}"
        f"{f' ({yaz_pencere_gun} takvim günü)' if yaz_pencere_gun else ''}\n"
        f"   Başvuru son tarihi: {d.get('yaz_basvuru_son_gun','')}\n"
        f"   Minimum staj gün sayısı: {d.get('yaz_min_staj_gun','20')} iş günü\n\n"
        f"❄️ {d.get('ara_donem_adi','Ara Dönem')} (Bahar/yarıyıl tatili)\n"
        f"   Staj penceresi: {d.get('ara_staj_baslangic','')} → {d.get('ara_staj_bitis','')}"
        f"{f' ({ara_pencere_gun} takvim günü)' if ara_pencere_gun else ''}\n"
        f"   Başvuru son tarihi: {d.get('ara_basvuru_son_gun','')}\n"
        f"   Minimum staj gün sayısı: {d.get('ara_min_staj_gun','20')} iş günü"
    )

    sistem = (
        "Sen Amasya MYO Staj Başvuru Asistanısın. Öğrencilerin staj süreci hakkındaki sorularını "
        "Türkçe, kısa ve net biçimde yanıtlarsın.\n\n"
        "ÖNEMLİ KURALLAR:\n"
        "1) Cevaplarını her zaman önce verilen YÖNERGE bölümlerine ve aktif STAJ DÖNEMİ bilgilerine dayandır.\n"
        "2) Tarih/staj süresi/dönem soruları → mutlaka aşağıdaki STAJ DÖNEMİ bilgisini kullan, başka tarih uydurma.\n"
        "3) Yönergede yoksa ya da bilmiyorsan 'Yönergede bu konuda kesin bilgi bulamadım' de — uydurma!\n"
        "4) Mümkünse yanıtlarken yönergedeki madde numarasını ya da bölümünü belirt.\n"
        "5) 'Yaz dönemi' (yaz tatili) ve 'Ara dönem' (bahar/yarıyıl tatili) ayırımına dikkat — kullanıcı hangisini sorduysa o döneme göre cevap ver.\n\n"
        f"{donem_bilgi}"
    )

    # Konuşma geçmişini hazırla (son 4 tur)
    messages = [{"role": "system", "content": sistem}]
    for m in gecmis[-4:]:
        if m.get("role") in ("user", "assistant") and m.get("content"):
            content = m["content"][:600]
            messages.append({"role": m["role"], "content": content})

    # RAG context'i son kullanıcı mesajına ekle
    if context:
        user_content = (
            f"=== YÖNERGEDEN İLGİLİ BÖLÜMLER ===\n{context}\n\n"
            f"=== KULLANICI SORUSU ===\n{soru}\n\n"
            f"Yukarıdaki yönerge bölümlerini ve sistem mesajındaki staj dönem tarihlerini kullanarak yanıtla."
        )
    else:
        user_content = soru
    messages.append({"role": "user", "content": user_content})

    chat_basarili = False
    try:
        model = ol.available_model(aktif_model())
        yanit = ol.chat(model=model, messages=messages, timeout=120,
                        options={"temperature": 0.3})
        chat_basarili = True
    except Exception as e:
        # Çift "Ollama hatası:" prefix'ini önle
        msg = str(e)
        if msg.lower().startswith("ollama"):
            yanit = msg
        else:
            yanit = f"Ollama hatası: {msg}"

    # Mesajda form alanı bilgisi VARSA çıkar — soru cümleleri için yapma
    form_data = {}
    soru_lc = soru.lower()

    import re as _re

    # Soru göstergeleri varsa extraction yapma
    SORU_KELIME = [
        '?', 'ne kadar', 'nasıl', 'kaç gün', 'kaç saat', 'kaç hafta',
        'ne zaman', 'hangi', 'kim', 'nedir', 'midir', 'mıdır', 'mıyım',
        'olur mu', 'gerekli mi', 'yapılır mı', 'yapılır', 'yapılabilir',
        'lazım mı', 'şart mı', 'açıklar mısın', 'anlatır mısın',
    ]
    is_soru = any(k in soru_lc for k in SORU_KELIME)

    # Açık veri sinyali (gerçek bir tarih, sayı, vs.) var mı?
    AY_ADLARI = r'(ocak|şubat|mart|nisan|mayıs|haziran|temmuz|ağustos|eylül|ekim|kasım|aralık)'
    has_date_pattern = bool(
        _re.search(r'\d{1,2}[/.\-]\d{1,2}', soru)               # 15/06, 15.06
        or _re.search(r'\d{4}-\d{2}-\d{2}', soru)                # 2026-06-22
        or _re.search(rf'\d{{1,2}}\s+{AY_ADLARI}', soru_lc)      # 15 Haziran
        or _re.search(rf'{AY_ADLARI}\s+\d{{1,2}}', soru_lc)      # Haziran 15
    )
    has_long_number = bool(_re.search(r'\b\d{6,}\b', soru))      # öğrenci/TC no
    has_data = has_date_pattern or has_long_number

    # Extraction sadece: chat başarılı + soru değil + gerçek veri sinyali var
    if chat_basarili and not is_soru and has_data:
        try:
            yil = datetime.now().year
            extract_prompt = (
                f"Aşağıdaki Türkçe mesajda EXPLICITLY yazılan staj formu alanlarını çıkar.\n"
                f"KURALLAR:\n"
                f"1) SADECE metinde YAZILMIŞ olan değerleri al, tahmin etme, hesaplama yapma.\n"
                f"2) Bulunmayan alanı JSON'a EKLEME (boş bile bırakma).\n"
                f"3) Tarih SADECE açıkça belirtilmişse (ör: '15 Haziran', '2026-06-22'). YOKSA EKLEME.\n"
                f"4) firma_adi = ŞİRKET ADI, firma_adresi = KONUM. Karıştırma!\n"
                f"5) Yıl yoksa {yil} varsay.\n\n"
                f"Mesaj: {soru}\n\n"
                f"Çıkarılabilecek alanlar:\n"
                f"baslangic_tarihi, bitis_tarihi (YYYY-MM-DD), staj_gun_sayisi,\n"
                f"firma_adi, firma_adresi, hizmet_alani, bolum,\n"
                f"ad_soyad, ogrenci_no, tc_kimlik_no\n\n"
                f"SADECE JSON döndür. Bulamazsan {{}}:\n"
            )
            raw_ext = ol.chat(
                model=model,
                messages=[{"role": "user", "content": extract_prompt}],
                timeout=20,
                options={"temperature": 0.0},
            )
            m = _re.search(r'\{.*?\}', raw_ext, _re.DOTALL)
            if m:
                parsed = json.loads(m.group())
                VALID_KEYS = {
                    'baslangic_tarihi','bitis_tarihi','staj_gun_sayisi',
                    'firma_adi','firma_adresi','hizmet_alani','bolum',
                    'ad_soyad','ogrenci_no','tc_kimlik_no',
                }
                # Tarih döndürüldüyse mesajda da tarih sinyali olmalı
                bugun_iso = datetime.now().strftime("%Y-%m-%d")
                form_data = {}
                for k, v in parsed.items():
                    if k not in VALID_KEYS: continue
                    val = str(v).strip()
                    if not val or val in ('', 'null', 'None', '0', 'false'):
                        continue
                    # Tarih hallüsinasyon kontrolü: bugünün tarihi ve mesajda tarih yoksa atla
                    if 'tarih' in k and not has_date_pattern:
                        continue
                    if 'tarih' in k and val == bugun_iso and bugun_iso not in soru:
                        continue
                    form_data[k] = val
        except Exception:
            form_data = {}

    return jsonify({"yanit": yanit, "form_data": form_data})

@app.route("/api/docs", methods=["GET"])
def api_docs_list():
    _, rag = load_services()
    docs = [{"name": name, "chunks": count} for name, count in rag.list_documents()]
    return jsonify({"ok": True, "docs": docs})


@app.route("/api/docs/upload", methods=["POST"])
def api_docs_upload():
    file = request.files.get("pdf")
    if not file or not file.filename:
        return jsonify({"ok": False, "hata": "Dosya seçilmedi"}), 400
    if not file.filename.lower().endswith(".pdf"):
        return jsonify({"ok": False, "hata": "Yalnızca PDF kabul edilir"}), 400

    save_path = DOCS / file.filename
    file.save(str(save_path))

    from services.pdf_service import extract_pdf_text
    text = extract_pdf_text(str(save_path))
    if not text.strip():
        save_path.unlink(missing_ok=True)
        return jsonify({"ok": False, "hata": "PDF'den metin okunamadı"}), 400

    _, rag = load_services()
    rag.add_document(file.filename, text)
    return jsonify({"ok": True, "dosya": file.filename})


@app.route("/api/docs/delete", methods=["POST"])
def api_docs_delete():
    data = request.get_json(force=True) or {}
    name = data.get("name", "")
    if not name or name == "yonerge.pdf":
        return jsonify({"ok": False, "hata": "Bu doküman silinemez"}), 400

    pdf_path = DOCS / name
    pdf_path.unlink(missing_ok=True)

    _, rag = load_services()
    rag.remove_document(name)
    return jsonify({"ok": True})


# ─── BİLDİRİMLER ──────────────────────────────────────────────────────────────

@app.route("/api/bildirimler")
@sekreter_required
def api_bildirimler():
    rows = get_db().execute(
        "SELECT * FROM bildirimler ORDER BY id DESC LIMIT 50"
    ).fetchall()
    return jsonify([dict(r) for r in rows])

@app.route("/api/bildirimler/okundu", methods=["POST"])
@sekreter_required
def api_bildirim_okundu():
    data = request.get_json(force=True) or {}
    bid  = data.get("id")
    with get_db() as c:
        if bid:
            c.execute("UPDATE bildirimler SET okundu=1 WHERE id=?", (bid,))
        else:
            c.execute("UPDATE bildirimler SET okundu=1")
    return jsonify({"ok": True})

@app.route("/api/bildirimler/sayi")
def api_bildirim_sayi():
    row = get_db().execute(
        "SELECT COUNT(*) as n FROM bildirimler WHERE okundu=0"
    ).fetchone()
    return jsonify({"sayi": row["n"]})

# ─── STAJ RAPORLARI ────────────────────────────────────────────────────────────

@app.route("/api/rapor/yukle", methods=["POST"])
@login_required
def api_rapor_yukle():
    file = request.files.get("rapor")
    sub_id = request.form.get("submission_id")
    if not file or not sub_id:
        return jsonify({"ok": False, "hata": "Dosya veya başvuru ID eksik"}), 400
    if not file.filename.lower().endswith(".pdf"):
        return jsonify({"ok": False, "hata": "Sadece PDF kabul edilir"}), 400

    fname    = f"rapor_{sub_id}_{file.filename}"
    savepath = RAPORLAR / fname
    file.save(str(savepath))

    with get_db() as c:
        cur = c.execute("""INSERT INTO staj_raporlari
                     (submission_id, dosya_adi, dosya_yolu, yukleme_tarihi)
                     VALUES (?,?,?,?)""",
                  (sub_id, file.filename, fname,
                   datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        rapor_id = cur.lastrowid

    bildirim_ekle("rapor", f"Staj raporu yüklendi — Başvuru #{sub_id}", int(sub_id))

    # Arka planda AI analiz başlat (öğrenci beklemeden cevap dönsün)
    import threading
    threading.Thread(target=_ai_rapor_arka_plan, args=(rapor_id,), daemon=True).start()

    return jsonify({"ok": True, "rapor_id": rapor_id})


def _ai_rapor_arka_plan(rapor_id: int):
    """Arka planda staj raporunu AI ile analiz et."""
    try:
        from services.pdf_service import extract_pdf_text
        from services.form_service import extract_json_object

        row = get_db().execute("SELECT * FROM staj_raporlari WHERE id=?", (rapor_id,)).fetchone()
        if not row: return
        pdf_path = RAPORLAR / row["dosya_yolu"]
        if not pdf_path.exists(): return
        text = extract_pdf_text(str(pdf_path))
        if not text.strip() or len(text) < 100: return

        sub = get_db().execute("SELECT * FROM submissions WHERE id=?", (row["submission_id"],)).fetchone()
        sub_info = ""
        if sub:
            try:
                ext = json.loads(sub["extracted_json"] or "{}")
                sub_info = f"Öğrenci: {ext.get('ad_soyad','?')}, Bölüm: {ext.get('bolum','?')}, Firma: {ext.get('firma_adi','?')}"
            except Exception:
                pass

        sistem = (
            "Sen staj raporu inceleme uzmanısın. JSON döndür:\n"
            "{\"kalite_skoru\":1-10,\"ozet\":\"...\",\"guclu_yonler\":[],\"eksikler\":[],"
            "\"oneriler\":[],\"uygunluk\":\"uygun|yetersiz|gözden_geçir\"}"
        )
        kullanici = f"BAŞVURU: {sub_info}\n\nRAPOR:\n{text[:6000]}"

        ol, _ = load_services()
        model = ol.available_model(aktif_model())
        raw = ol.chat(model=model,
                      messages=[{"role":"system","content":sistem},
                                {"role":"user","content":kullanici}],
                      timeout=180, options={"temperature":0.2})
        parsed = extract_json_object(raw) or {}
        skor = int(parsed.get("kalite_skoru",5)) if str(parsed.get("kalite_skoru","")).isdigit() else 5
        with get_db() as c:
            c.execute("UPDATE staj_raporlari SET ai_analiz=?, ai_skor=? WHERE id=?",
                      (json.dumps(parsed, ensure_ascii=False), skor, rapor_id))
        bildirim_ekle("rapor", f"🧠 AI rapor analizi tamamlandı — Skor: {skor}/10", row["submission_id"])
    except Exception as e:
        print(f"[AI Rapor Arka Plan] {e}")

@app.route("/api/rapor/liste")
@sekreter_required
def api_rapor_liste():
    rows = get_db().execute(
        "SELECT * FROM staj_raporlari ORDER BY id DESC"
    ).fetchall()
    return jsonify([dict(r) for r in rows])

@app.route("/api/rapor/indir/<int:rid>")
@sekreter_required
def api_rapor_indir(rid):
    row = get_db().execute(
        "SELECT * FROM staj_raporlari WHERE id=?", (rid,)
    ).fetchone()
    if not row:
        return jsonify({"ok": False}), 404
    path = RAPORLAR / row["dosya_yolu"]
    return send_file(str(path), as_attachment=True, download_name=row["dosya_adi"])

@app.route("/api/rapor/analiz/<int:rid>", methods=["POST"])
@sekreter_required
def api_rapor_analiz(rid):
    """Sekreter butonuna basınca staj raporunu LLM ile analiz et."""
    from services.pdf_service import extract_pdf_text
    from services.form_service import extract_json_object

    row = get_db().execute("SELECT * FROM staj_raporlari WHERE id=?", (rid,)).fetchone()
    if not row:
        return jsonify({"ok": False, "hata": "Rapor bulunamadı"}), 404

    pdf_path = RAPORLAR / row["dosya_yolu"]
    if not pdf_path.exists():
        return jsonify({"ok": False, "hata": "PDF bulunamadı"}), 404

    text = extract_pdf_text(str(pdf_path))
    if not text.strip():
        return jsonify({"ok": False, "hata": "PDF'den metin okunamadı"}), 400

    sub = get_db().execute("SELECT * FROM submissions WHERE id=?", (row["submission_id"],)).fetchone()
    sub_info = ""
    if sub:
        try:
            ext = json.loads(sub["extracted_json"] or "{}")
            sub_info = f"Öğrenci: {ext.get('ad_soyad','?')}, Bölüm: {ext.get('bolum','?')}, Firma: {ext.get('firma_adi','?')}, Süre: {ext.get('staj_gun_sayisi','?')} gün"
        except Exception:
            pass

    sistem = (
        "Sen bir staj raporu inceleme uzmanısın. Sana verilen staj raporunu detaylı analiz "
        "edip yapılandırılmış JSON döndür. Yanıtın MUTLAKA şu şemada olsun:\n"
        "{\n"
        '  "kalite_skoru": 1-10 arası tam sayı,\n'
        '  "ozet": "Raporun 2-3 cümlelik özeti",\n'
        '  "guclu_yonler": ["Madde 1","Madde 2"],\n'
        '  "eksikler": ["Madde 1","Madde 2"],\n'
        '  "bolumler": {"giris":true/false,"gunluk":true/false,"sonuc":true/false},\n'
        '  "oneriler": ["Geliştirme önerisi 1","..."],\n'
        '  "uygunluk": "uygun" veya "yetersiz" veya "gözden_geçir"\n'
        "}"
    )
    kullanici = (
        f"BAŞVURU BİLGİSİ:\n{sub_info}\n\n"
        f"STAJ RAPORU İÇERİĞİ:\n{text[:6000]}\n\n"
        "Bu staj raporunu yukarıdaki JSON formatında değerlendir."
    )

    ol, _ = load_services()
    try:
        model = ol.available_model(aktif_model())
        raw   = ol.chat(model=model,
                        messages=[{"role":"system","content":sistem},
                                  {"role":"user","content":kullanici}],
                        timeout=120, options={"temperature":0.2})
        parsed = extract_json_object(raw) or {}
        skor   = int(parsed.get("kalite_skoru", 5)) if str(parsed.get("kalite_skoru","")).isdigit() else 5
        with get_db() as c:
            c.execute("UPDATE staj_raporlari SET ai_analiz=?, ai_skor=? WHERE id=?",
                      (json.dumps(parsed, ensure_ascii=False), skor, rid))
        return jsonify({"ok": True, "analiz": parsed})
    except Exception as e:
        return jsonify({"ok": False, "hata": str(e)}), 500


@app.route("/api/ai-ozet", methods=["GET"])
@sekreter_required
def api_ai_ozet():
    """Sekreter için günlük özet — Python ile hesaplanır, LLM sadece kısa yorum."""
    # Sadece PDF'i olan başvurular
    rows = _filtrele_pdf_var(get_db().execute(
        "SELECT * FROM submissions ORDER BY id DESC"
    ).fetchall())

    if not rows:
        return jsonify({"ozet": "📭 Henüz başvuru yok."})

    # 1) Python ile istatistikleri hesapla (anında)
    toplam = len(rows)
    onayli = sum(1 for r in rows if r["durum"] == "onaylandi")
    reddi  = sum(1 for r in rows if r["durum"] == "reddedildi")
    bekle  = sum(1 for r in rows if r["durum"] == "beklemede")

    firmalar, bolumler = {}, {}
    for r in rows:
        try:
            ext = json.loads(r["extracted_json"] or "{}")
        except Exception:
            continue
        firma = (ext.get("firma_adi") or "").strip()
        bolum = (ext.get("bolum") or "").strip()
        if firma: firmalar[firma] = firmalar.get(firma, 0) + 1
        if bolum: bolumler[bolum] = bolumler.get(bolum, 0) + 1

    top_firma = sorted(firmalar.items(), key=lambda x: -x[1])[:5]
    top_bolum = sorted(bolumler.items(), key=lambda x: -x[1])[:5]

    # Bugün ve son 7 gün başvuru sayısı
    from datetime import date as _date, timedelta as _td
    bugun_str = _date.today().isoformat()
    son7 = (_date.today() - _td(days=7)).isoformat()
    bugun_say = sum(1 for r in rows if (r["yukleme_tarihi"] or "")[:10] == bugun_str)
    son7_say  = sum(1 for r in rows if (r["yukleme_tarihi"] or "")[:10] >= son7)

    # 2) Markdown özet metni oluştur (LLM'siz, anında)
    ozet = f"""## 📊 Genel İstatistik
- **Toplam başvuru:** {toplam}
- ✅ Kabul: **{onayli}** ({(onayli/toplam*100):.0f}%)
- ❌ Red: **{reddi}** ({(reddi/toplam*100):.0f}%)
- ⏳ Beklemede: **{bekle}**

## 📈 Aktivite
- Bugün gelen: **{bugun_say}** başvuru
- Son 7 gün: **{son7_say}** başvuru

## 🏢 En Çok Başvuru Gelen Firmalar
"""
    if top_firma:
        for i, (f, n) in enumerate(top_firma, 1):
            ozet += f"{i}. **{f}** — {n} başvuru\n"
    else:
        ozet += "_Veri yok._\n"

    ozet += "\n## 🎓 En Aktif Bölümler\n"
    if top_bolum:
        for i, (b, n) in enumerate(top_bolum, 1):
            ozet += f"{i}. **{b}** — {n} başvuru\n"
    else:
        ozet += "_Veri yok._\n"

    # 3) Kural tabanlı öneri (LLM yok — anında, asla timeout olmaz)
    oneriler = []
    if bekle > 0:
        oneriler.append(f"⚡ **{bekle} bekleyen başvuru** var. İncelemeniz öneriliyor.")
    if reddi > 0 and onayli > 0:
        kabul_pct = onayli / toplam * 100
        if kabul_pct < 50:
            oneriler.append(f"⚠️ Kabul oranı düşük (%{kabul_pct:.0f}). Yönerge bilgilendirmesi öğrencilere ulaştırılabilir.")
        else:
            oneriler.append(f"✅ Kabul oranı sağlıklı (%{kabul_pct:.0f}).")
    if bugun_say == 0 and son7_say > 0:
        oneriler.append("📅 Bugün yeni başvuru yok ama son 7 günde aktivite var.")
    elif bugun_say > 5:
        oneriler.append(f"🔥 Yoğun gün: bugün {bugun_say} yeni başvuru geldi.")

    # Aynı firma birden fazla başvuru varsa not düş
    coklu_firmalar = [f for f, n in firmalar.items() if n >= 2]
    if coklu_firmalar:
        oneriler.append(f"🏢 {len(coklu_firmalar)} firma birden fazla başvuru aldı — popüler staj alanları.")

    if not oneriler:
        oneriler.append("📋 Sistem sağlıklı, dikkat edilmesi gereken bir durum yok.")

    ozet += "\n## 💡 Öneriler\n"
    for o in oneriler:
        ozet += f"- {o}\n"

    return jsonify({"ozet": ozet})


@app.route("/api/rapor/karar", methods=["POST"])
@sekreter_required
def api_rapor_karar():
    data = request.get_json(force=True) or {}
    with get_db() as c:
        c.execute("UPDATE staj_raporlari SET durum=?, sekreter_notu=? WHERE id=?",
                  (data.get("durum",""), data.get("not",""), data.get("id")))
    return jsonify({"ok": True})


# ─── 🤖 AGENT (Tool Kullanan LLM) ─────────────────────────────────────────────

AGENT_TOOLS_DOC = """
KULLANABILECEĞİN ARAÇLAR (tool_calls içinde JSON ile çağırırsın):

- LIST_BASVURU  → Başvuru listele. input: {"filter": "hepsi|beklemede|kabul|red"}
- GET_BASVURU   → Tek başvuru detayı. input: {"id": <int>}
- ONAYLA        → Başvuruyu onayla. input: {"id": <int>, "sebep": "<metin>"}
- REDDET        → Başvuruyu reddet. input: {"id": <int>, "sebep": "<metin>"}
- ARA           → Başvurularda arama. input: {"anahtar": "<metin>"}
- ISTATISTIK    → İstatistik. input: {"tip": "ozet|firma|bolum|donem"}
- ONCELIK       → Bekleyenleri risk sırasına göre listele. input: {}
- CEVAP         → Sekretere mesaj/soru. input: {"metin": "<metin>"}
"""

AGENT_OTONOMUS_SISTEM = """Sen Amasya MYO Staj sisteminin TAM OTONOM AGENT'ısın.

KURALLAR:
- ASLA açıklayıcı metin yazma. ASLA markdown başlık (📋, 🔍 vs.) yazma.
- SADECE TEK BİR JSON objesi döndür. Başka hiçbir şey yok.
- JSON'un dışına tek karakter bile yazma.

PLAN: kısa teknik adımlar listesi (ör: ["liste_cek", "filtrele", "ozet_uret"]).
TOOL: gerekli tool çağrılarının listesi (her biri tool, input, reason içerir).
ANALİZ: başvuru analiz edilmediyse boş obje {}, edilmişse:
  gun_durumu (YETERLI/YETERSIZ/BILINMIYOR),
  tarih_durumu (GECERLI/GECERSIZ/BILINMIYOR),
  firma_durumu (UYGUN/RISKLI/UYGUN_DEGIL/BILINMIYOR),
  belge_durumu (TAM/EKSIK/BILINMIYOR),
  gecmis_durum (VAR/YOK/BILINMIYOR),
  tekrar_durumu (true/false),
  risk_skoru (0-100).
KARAR.sonuc: KABUL | RED | BEKLEME.
KARAR.nedenler: kısa neden listesi.
ACIKLAMA: 1-2 cümle Türkçe özet.

ÇIKTI ŞEMASI (sadece bu yapı, başka şey yok):
{"plan":[],"tool_calls":[{"tool":"","input":{},"reason":""}],"analiz":{},"karar":{"sonuc":"","nedenler":[]},"aciklama":""}

YASAKLAR: Halüsinasyon yapma, tarih uydurma, plansız işlem yapma.
""" + AGENT_TOOLS_DOC

def _gecerli_submission_ids():
    """Sadece PDF dosyası mevcut olan submission id'leri.
    Sekreter ekranı da bu filtreyi uyguluyor — agent da aynısını uygulamalı."""
    ids = set()
    if UPLOAD.exists():
        for f in UPLOAD.glob("*.pdf"):
            stem = f.stem
            if stem.isdigit():
                ids.add(int(stem))
    return ids

def _filtrele_pdf_var(rows):
    """sqlite3.Row listesini PDF'i olanlarla sınırla."""
    gecerli = _gecerli_submission_ids()
    return [r for r in rows if r["id"] in gecerli]


def _agent_tool_list(filter_="hepsi"):
    q = "SELECT id, original_adi, durum, ai_karar, yukleme_tarihi, extracted_json FROM submissions"
    args = []
    if filter_ == "beklemede":
        q += " WHERE durum='beklemede'"
    elif filter_ == "kabul":
        q += " WHERE ai_karar='KABUL'"
    elif filter_ == "red":
        q += " WHERE ai_karar='RED'"
    q += " ORDER BY id DESC"
    rows = _filtrele_pdf_var(get_db().execute(q, args).fetchall())[:30]
    out = []
    for r in rows:
        try:
            ext = json.loads(r["extracted_json"] or "{}")
        except: ext = {}
        out.append({
            "id": r["id"], "ad": ext.get("ad_soyad","?"),
            "bolum": ext.get("bolum","?"), "firma": ext.get("firma_adi","?"),
            "karar": r["ai_karar"], "durum": r["durum"], "tarih": r["yukleme_tarihi"],
        })
    return out

def _agent_tool_get(id_):
    # PDF yoksa erişilemez
    if id_ not in _gecerli_submission_ids():
        return {"hata": f"#{id_} bulunamadı veya PDF dosyası yok"}
    r = get_db().execute("SELECT * FROM submissions WHERE id=?", (id_,)).fetchone()
    if not r: return {"hata": f"#{id_} bulunamadı"}
    d = dict(r)
    try: d["form"] = json.loads(d.get("extracted_json") or "{}")
    except: d["form"] = {}
    d.pop("extracted_json", None); d.pop("ai_rapor", None); d.pop("ai_detay_json", None)
    return d

def _agent_tool_karar(id_, karar, sebep=""):
    if id_ not in _gecerli_submission_ids():
        return {"hata": f"#{id_} bulunamadı veya PDF yok"}
    durum = "onaylandi" if karar == "KABUL" else "reddedildi"
    with get_db() as c:
        cur = c.execute("UPDATE submissions SET durum=?, ai_karar=? WHERE id=?",
                        (durum, karar, id_))
        if cur.rowcount == 0:
            return {"hata": f"#{id_} bulunamadı"}
    return {"ok": True, "id": id_, "yeni_durum": durum, "sebep": sebep}

def _agent_tool_ara(anahtar):
    rows = _filtrele_pdf_var(get_db().execute(
        "SELECT id, original_adi, ai_karar, durum, extracted_json FROM submissions ORDER BY id DESC"
    ).fetchall())
    a = (anahtar or "").lower()
    bulunan = []
    for r in rows:
        try: ext = json.loads(r["extracted_json"] or "{}")
        except: ext = {}
        hay = " ".join(str(v) for v in ext.values()) + " " + (r["original_adi"] or "")
        if a in hay.lower():
            bulunan.append({"id": r["id"], "ad": ext.get("ad_soyad",""),
                            "firma": ext.get("firma_adi",""), "bolum": ext.get("bolum",""),
                            "karar": r["ai_karar"]})
    return bulunan[:20]

def _agent_tool_istatistik(tip):
    rows = _filtrele_pdf_var(get_db().execute("SELECT * FROM submissions").fetchall())
    if tip == "ozet":
        return {
            "toplam":     len(rows),
            "kabul":      sum(1 for r in rows if r["durum"] == "onaylandi"),
            "red":        sum(1 for r in rows if r["durum"] == "reddedildi"),
            "beklemede":  sum(1 for r in rows if r["durum"] == "beklemede"),
        }
    sayac = {}
    key = "firma_adi" if tip == "firma" else "bolum"
    for r in rows:
        try:    ext = json.loads(r["extracted_json"] or "{}")
        except: continue
        v = (ext.get(key) or "—").strip()
        if v: sayac[v] = sayac.get(v, 0) + 1
    sirali = sorted(sayac.items(), key=lambda x: -x[1])[:10]
    return {tip: [{"isim": k, "sayi": v} for k, v in sirali]}

def _agent_tool_oncelik():
    """Bekleyen başvuruları aciliyete göre sırala."""
    rows = _filtrele_pdf_var(get_db().execute(
        "SELECT * FROM submissions WHERE durum='beklemede' ORDER BY id DESC"
    ).fetchall())
    skorlu = []
    for r in rows:
        try: ext = json.loads(r["extracted_json"] or "{}")
        except: ext = {}
        try: detay = json.loads(r["ai_detay_json"] or "{}")
        except: detay = {}
        skor = 50
        if detay.get("risk_skoru"):
            skor = int(detay["risk_skoru"])
        # Eksik alan varsa öncelik artır
        try:
            eks = json.loads(r["missing_json"] or "[]")
            if eks: skor += min(len(eks)*5, 20)
        except: pass
        skorlu.append({
            "id": r["id"], "ad": ext.get("ad_soyad","?"),
            "firma": ext.get("firma_adi","?"), "bolum": ext.get("bolum","?"),
            "oncelik": skor,
            "seviye": "🔴 acil" if skor>=70 else ("🟡 normal" if skor>=40 else "🟢 düşük"),
        })
    return sorted(skorlu, key=lambda x: -x["oncelik"])

def _agent_parse_yanit(raw: str) -> dict:
    """LLM'in döndürdüğü metinden agent JSON yanıtını çıkar.
    plan/tool_calls/karar key'lerinden en az birini içeren en geniş JSON'u alır."""
    import re as _re
    # Tüm üst-seviye {...} bloklarını bul (basit dengeleme algoritması)
    candidates = []
    depth = 0; start = -1
    for i, ch in enumerate(raw):
        if ch == '{':
            if depth == 0: start = i
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0 and start >= 0:
                candidates.append(raw[start:i+1])
                start = -1
    # Her aday için parse + agent key kontrolü
    AGENT_KEYS = {'plan', 'tool_calls', 'karar', 'analiz', 'aciklama'}
    en_iyi = None; en_iyi_skor = -1
    for cand in candidates:
        try:
            obj = json.loads(cand)
            if not isinstance(obj, dict): continue
            skor = sum(1 for k in AGENT_KEYS if k in obj)
            if skor > en_iyi_skor:
                en_iyi_skor = skor
                en_iyi = obj
        except Exception:
            continue
    return en_iyi or {}


def _agent_tool_calistir(tool_name: str, inp: dict):
    """Tek bir tool'u güvenli şekilde çalıştır. (tool_name, sonuc) döndürür."""
    tn = (tool_name or "").upper()
    try:
        if   tn == "LIST_BASVURU": return tn, _agent_tool_list(inp.get("filter","hepsi"))
        elif tn == "GET_BASVURU":  return tn, _agent_tool_get(int(inp.get("id",0)))
        elif tn == "ONAYLA":       return tn, _agent_tool_karar(int(inp.get("id",0)), "KABUL", inp.get("sebep",""))
        elif tn == "REDDET":       return tn, _agent_tool_karar(int(inp.get("id",0)), "RED",   inp.get("sebep",""))
        elif tn == "ARA":          return tn, _agent_tool_ara(inp.get("anahtar",""))
        elif tn == "ISTATISTIK":   return tn, _agent_tool_istatistik(inp.get("tip","ozet"))
        elif tn in ("ONCELIK","ONCELIK_SIRALA"): return tn, _agent_tool_oncelik()
        elif tn == "CEVAP":        return tn, {"mesaj": inp.get("metin","")}
        else:                      return tn, {"hata": f"Bilinmeyen tool: {tn}"}
    except Exception as e:
        return tn, {"hata": str(e)}


@app.route("/api/agent/direct", methods=["POST"])
@sekreter_required
def api_agent_direct():
    """LLM bypass — tool'u doğrudan çağırır. Hızlı butonlar için."""
    data = request.get_json(force=True) or {}
    tool = (data.get("tool") or "").upper()
    inp  = data.get("input") or {}
    tn, sonuc = _agent_tool_calistir(tool, inp)
    return jsonify({
        "ok": True,
        "plan": [tn.lower()],
        "tool_calls": [{"tool": tn, "input": inp, "reason": "Hızlı buton", "sonuc": sonuc}],
        "analiz": {},
        "karar": {"sonuc": "BEKLEME", "nedenler": []},
        "aciklama": "",
    })


def _agent_kural_tabanli(komut: str):
    """Yaygın sorulara LLM'siz hızlı yanıt. Match yoksa None döner."""
    import re as _re
    k = komut.lower().strip()

    # "kaç başvuru / başvuru sayısı"
    if _re.search(r'(kaç|sayı|toplam).*başvuru', k) or 'durum özet' in k or 'istatistik' in k:
        # Bölüm filtresi var mı? "pc bölüm", "bilgisayar bölüm" gibi
        m = _re.search(r'(\w+)\s*böl[uü]m', k)
        if m:
            anahtar = m.group(1)
            _, sonuc = _agent_tool_calistir("ARA", {"anahtar": anahtar})
            sayi = len(sonuc) if isinstance(sonuc, list) else 0
            return {
                "plan": ["arama_yap", "say"],
                "tool_calls": [{"tool":"ARA","input":{"anahtar":anahtar},"reason":f"'{anahtar}' içeren başvuruları bul","sonuc":sonuc}],
                "analiz": {},
                "karar": {"sonuc":"BEKLEME","nedenler":[]},
                "aciklama": f"'{anahtar}' bölümünde {sayi} başvuru bulundu.",
            }
        _, sonuc = _agent_tool_calistir("ISTATISTIK", {"tip":"ozet"})
        return {
            "plan":["istatistik_cek"],
            "tool_calls":[{"tool":"ISTATISTIK","input":{"tip":"ozet"},"reason":"Genel istatistik","sonuc":sonuc}],
            "analiz":{},"karar":{"sonuc":"BEKLEME","nedenler":[]},"aciklama":"",
        }

    # "firma" kelimesi → firma istatistiği
    if 'firma' in k and ('top' in k or 'çok' in k or 'liste' in k or 'dağılım' in k):
        _, sonuc = _agent_tool_calistir("ISTATISTIK", {"tip":"firma"})
        return {"plan":["firma_dagilim"],"tool_calls":[{"tool":"ISTATISTIK","input":{"tip":"firma"},"reason":"Firma dağılımı","sonuc":sonuc}],
                "analiz":{},"karar":{"sonuc":"BEKLEME","nedenler":[]},"aciklama":""}

    # "bölüm" → bölüm istatistiği
    if 'bölüm' in k and ('dağılım' in k or 'liste' in k or 'çok' in k):
        _, sonuc = _agent_tool_calistir("ISTATISTIK", {"tip":"bolum"})
        return {"plan":["bolum_dagilim"],"tool_calls":[{"tool":"ISTATISTIK","input":{"tip":"bolum"},"reason":"Bölüm dağılımı","sonuc":sonuc}],
                "analiz":{},"karar":{"sonuc":"BEKLEME","nedenler":[]},"aciklama":""}

    # "öncelik" → ONCELIK
    if 'öncelik' in k or 'acil' in k:
        _, sonuc = _agent_tool_calistir("ONCELIK", {})
        return {"plan":["oncelik_sirala"],"tool_calls":[{"tool":"ONCELIK","input":{},"reason":"Öncelik sırası","sonuc":sonuc}],
                "analiz":{},"karar":{"sonuc":"BEKLEME","nedenler":[]},"aciklama":""}

    # "bekleyen başvuru"
    if 'bekleyen' in k or 'beklemede' in k:
        _, sonuc = _agent_tool_calistir("LIST_BASVURU", {"filter":"beklemede"})
        return {"plan":["liste_cek"],"tool_calls":[{"tool":"LIST_BASVURU","input":{"filter":"beklemede"},"reason":"Bekleyenleri listele","sonuc":sonuc}],
                "analiz":{},"karar":{"sonuc":"BEKLEME","nedenler":[]},"aciklama":""}

    # "ID 5" / "5 numaralı" / "#5" / "5. başvuru" → GET_BASVURU
    m = (_re.search(r'#\s*(\d+)', k)
         or _re.search(r'(?:^|\s)id\s*[:=]?\s*(\d+)', k)
         or _re.search(r'(\d+)\s*numara', k)
         or _re.search(r'numara\s*(\d+)', k)
         or _re.search(r'(\d+)\.?\s*(?:başvuru|basvuru)', k))
    if m:
        sid = int(m.group(1))
        _, sonuc = _agent_tool_calistir("GET_BASVURU", {"id":sid})
        return {"plan":["detay_cek"],"tool_calls":[{"tool":"GET_BASVURU","input":{"id":sid},"reason":f"#{sid} detay","sonuc":sonuc}],
                "analiz":{},"karar":{"sonuc":"BEKLEME","nedenler":[]},"aciklama":""}

    # "ara X" / "X ara" / "X bul" / "X firma/firmasını"
    m = (_re.search(r'(?:ara[mn]?|search|bul|getir)\s+([^\s]+)', k)
         or _re.search(r'([^\s]+)\s+(?:ara[mn]?|bul|firmas[ıi]?n[ıi]?\s*ara)', k)
         or _re.search(r'firma[sn]?[ıi]\s+([^\s]+)', k))
    if m:
        anahtar = m.group(1).strip('.,?!')
        if len(anahtar) >= 2 and not anahtar.isdigit():
            _, sonuc = _agent_tool_calistir("ARA", {"anahtar":anahtar})
            return {"plan":["arama_yap"],"tool_calls":[{"tool":"ARA","input":{"anahtar":anahtar},"reason":f"'{anahtar}' ara","sonuc":sonuc}],
                    "analiz":{},"karar":{"sonuc":"BEKLEME","nedenler":[]},"aciklama":""}

    return None


@app.route("/api/agent/komut", methods=["POST"])
@sekreter_required
def api_agent_komut():
    from services.form_service import extract_json_object
    data = request.get_json(force=True) or {}
    komut = (data.get("komut") or "").strip()
    if not komut:
        return jsonify({"ok": False, "yanit": "Komut boş."})

    # ÖNCE kural tabanlı hızlı yanıt dene
    hizli = _agent_kural_tabanli(komut)
    if hizli:
        sonuclar = []
        for tc in hizli["tool_calls"]:
            sonuclar.append({
                "tool": tc["tool"], "input": tc["input"],
                "reason": tc.get("reason",""), "sonuc": tc["sonuc"],
            })
        hizli["tool_calls"] = sonuclar
        hizli["ok"] = True
        hizli["tool"] = sonuclar[0]["tool"] if sonuclar else None
        hizli["yanit"] = hizli.get("aciklama","")
        return jsonify(hizli)

    # Kural eşleşmediyse LLM'e git
    ol, _ = load_services()
    try:
        model = ol.available_model(aktif_model())
        raw = ol.chat(
            model=model,
            messages=[
                {"role": "system", "content": AGENT_OTONOMUS_SISTEM},
                {"role": "user",   "content": f"KOMUT/OLAY: {komut}"},
            ],
            timeout=120, options={"temperature": 0.05},
        )
    except Exception as e:
        # LLM hatasında: en azından arama yapmayı dene
        _, sonuc = _agent_tool_calistir("ARA", {"anahtar": komut[:30]})
        if isinstance(sonuc, list) and sonuc:
            return jsonify({
                "ok": True, "plan":["fallback_arama"],
                "tool_calls":[{"tool":"ARA","input":{"anahtar":komut[:30]},"reason":"LLM timeout — arama fallback","sonuc":sonuc}],
                "analiz":{}, "karar":{"sonuc":"BEKLEME","nedenler":[]},
                "aciklama": f"LLM yanıt vermedi, '{komut[:30]}' için arama sonuçları gösteriliyor.",
            })
        return jsonify({"ok": False, "yanit": f"LLM hatası: {e}"})

    # Yeni gelişmiş parser — en uygun JSON'u seç
    parsed = _agent_parse_yanit(raw)
    if not parsed:
        parsed = extract_json_object(raw) or {}

    # Geriye dönük uyumluluk: eski format {tool, args} → yeni formata dönüştür
    if "tool" in parsed and "tool_calls" not in parsed:
        parsed = {
            "plan": [parsed.get("tool","").lower()],
            "tool_calls": [{
                "tool": parsed.get("tool",""),
                "input": parsed.get("args", {}),
                "reason": "Tek adımlı işlem",
            }],
            "analiz": {},
            "karar": {"sonuc": "BEKLEME", "nedenler": []},
            "aciklama": "",
        }

    plan       = parsed.get("plan") or []
    tool_calls = parsed.get("tool_calls") or []
    analiz     = parsed.get("analiz") or {}
    karar      = parsed.get("karar") or {"sonuc": "BEKLEME", "nedenler": []}
    aciklama   = parsed.get("aciklama") or ""

    # Tüm tool çağrılarını sırayla çalıştır
    sonuclar = []
    for tc in tool_calls[:5]:   # en fazla 5 tool çağrısı
        if not isinstance(tc, dict): continue
        tool_name = tc.get("tool","")
        inp       = tc.get("input") or tc.get("args") or {}
        reason    = tc.get("reason","")
        tn, sonuc = _agent_tool_calistir(tool_name, inp)
        sonuclar.append({"tool": tn, "input": inp, "reason": reason, "sonuc": sonuc})

    # Eğer hiç tool çağrılmadıysa ve karar BEKLEME değilse: sadece açıklama
    return jsonify({
        "ok": True,
        "plan": plan,
        "tool_calls": sonuclar,
        "analiz": analiz,
        "karar": karar,
        "aciklama": aciklama,
        # Geriye dönük: ilk tool sonucunu da gönder (frontend için)
        "tool": sonuclar[0]["tool"] if sonuclar else None,
        "yanit": aciklama or (sonuclar[0]["sonuc"].get("mesaj","") if sonuclar and isinstance(sonuclar[0].get("sonuc"), dict) else ""),
    })


if __name__ == "__main__":
    app.run(debug=True, port=5000)
