"""
app.py  —  Amasya MYO Staj Asistanı (Flask)
"""
from __future__ import annotations

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
        return jsonify({"ok": True, "kurallar": get_kurallar()})
    except Exception as e:
        return jsonify({"ok": False, "kurallar": [], "hata": str(e)})

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
    hits    = rag.search(soru, top_k=5)
    context = "\n\n".join(h.chunk_text for h in hits) if hits else ""

    # Staj dönemi bilgisini sisteme ekle
    donem_keys = [
        "yaz_donem_adi","yaz_staj_baslangic","yaz_staj_bitis","yaz_basvuru_son_gun","yaz_min_staj_gun",
        "ara_donem_adi","ara_staj_baslangic","ara_staj_bitis","ara_basvuru_son_gun","ara_min_staj_gun",
    ]
    d = {k: get_setting(k) for k in donem_keys}
    donem_bilgi = (
        f"Aktif Staj Dönemleri:\n"
        f"- {d.get('yaz_donem_adi','Yaz')}: {d.get('yaz_staj_baslangic','')} – {d.get('yaz_staj_bitis','')} "
        f"(Son başvuru: {d.get('yaz_basvuru_son_gun','')}, Min: {d.get('yaz_min_staj_gun','20')} gün)\n"
        f"- {d.get('ara_donem_adi','Ara')}: {d.get('ara_staj_baslangic','')} – {d.get('ara_staj_bitis','')} "
        f"(Son başvuru: {d.get('ara_basvuru_son_gun','')}, Min: {d.get('ara_min_staj_gun','20')} gün)"
    )

    sistem = (
        "Sen Amasya MYO Staj Başvuru Asistanısın. "
        "Öğrencilerin staj süreci hakkındaki sorularını Türkçe, kısa ve net biçimde yanıtlarsın. "
        "Yönerge bilgisi ve dönem bilgisi verildiğinde bunları kullan. "
        "Bilmediğin bir şeyi kesinlikle uydurama. Madde numaralarını doğru ver.\n\n"
        f"{donem_bilgi}"
    )

    # Konuşma geçmişini hazırla (son 6 tur)
    messages = [{"role": "system", "content": sistem}]
    for m in gecmis[-6:]:
        if m.get("role") in ("user", "assistant") and m.get("content"):
            messages.append({"role": m["role"], "content": m["content"]})

    # RAG context'i son kullanıcı mesajına ekle
    if context:
        user_content = f"İlgili yönerge bölümleri:\n{context}\n\nSoru: {soru}"
    else:
        user_content = soru
    messages.append({"role": "user", "content": user_content})

    try:
        model = ol.available_model(aktif_model())
        yanit = ol.chat(model=model, messages=messages, timeout=90,
                        options={"temperature": 0.3})
    except Exception as e:
        yanit = f"Ollama hatası: {e}"

    # Mesajda form alanı bilgisi varsa çıkar
    form_data = {}
    FORM_KEYWORDS = [
        'tarih','haziran','temmuz','ağustos','eylül','ekim','kasım','aralık',
        'ocak','şubat','mart','nisan','mayıs','arası','arasında','başlıyorum',
        'yapacağım','staj yapıcam','firma','şirketi','bölüm','program','adres',
        'gün','hafta','tc','kimlik','öğrenci no','numara','ad soyad','adım',
    ]
    if any(k in soru.lower() for k in FORM_KEYWORDS):
        try:
            import re as _re
            bugun = datetime.now().strftime("%Y-%m-%d")
            yil   = datetime.now().year
            # Hem kullanıcı mesajı hem asistanın özeti kullanılarak daha doğru çıkarım
            extract_prompt = (
                f"Aşağıdaki Türkçe metinden staj başvuru formu alanlarını çıkar. "
                f"SADECE geçerli JSON döndür, başka hiçbir şey yazma. Bulamazsan {{}} döndür.\n\n"
                f"Bugün: {bugun}  (yıl belirtilmemişse {yil} kullan)\n\n"
                f"=== KULLANICI MESAJI ===\n{soru}\n\n"
                f"=== ASİSTAN ÖZETİ ===\n{yanit[:500]}\n\n"
                f"=== ÖNEMLİ KURALLAR ===\n"
                f"firma_adi   → Şirketin/firmanın SADECE İSMİ (ör: 'Metropolitcard', 'ABC A.Ş.'). Adres yazmak YASAK!\n"
                f"firma_adresi → Şirketin ADRES ya da KONUMU (ör: 'Üsküdar', 'Kadıköy/İstanbul'). İsim yazmak YASAK!\n"
                f"baslangic_tarihi / bitis_tarihi → YYYY-MM-DD formatında (ör: '{yil}-06-22')\n"
                f"ad_soyad → Öğrencinin adı ve soyadı\n"
                f"ogrenci_no → Öğrenci numarası (sadece rakamlar)\n"
                f"tc_kimlik_no → 11 haneli TC kimlik numarası\n"
                f"staj_gun_sayisi → Sadece rakam (ör: 30)\n"
                f"bolum → Öğrencinin bölümü/programı\n"
                f"hizmet_alani → Staj yapılacak sektör/alan\n\n"
                f"Sadece bulunan alanları JSON'a ekle:\n"
                f"JSON:"
            )
            raw_ext = ol.chat(
                model=model,
                messages=[{"role": "user", "content": extract_prompt}],
                timeout=25,
                options={"temperature": 0.05},
            )
            m = _re.search(r'\{.*?\}', raw_ext, _re.DOTALL)
            if m:
                parsed = json.loads(m.group())
                VALID_KEYS = {
                    'baslangic_tarihi','bitis_tarihi','staj_gun_sayisi',
                    'firma_adi','firma_adresi','hizmet_alani','bolum',
                    'ad_soyad','ogrenci_no','tc_kimlik_no',
                }
                form_data = {
                    k: str(v).strip()
                    for k, v in parsed.items()
                    if k in VALID_KEYS and v and str(v).strip() not in ('', 'null', 'None', '0')
                }
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
    """Sekreter için tüm bekleyen başvuruların AI özeti."""
    rows = get_db().execute(
        "SELECT * FROM submissions ORDER BY id DESC LIMIT 20"
    ).fetchall()
    if not rows:
        return jsonify({"ozet": "Henüz başvuru yok."})

    items = []
    for r in rows:
        try:
            ext = json.loads(r["extracted_json"] or "{}")
            items.append(
                f"#{r['id']} {ext.get('ad_soyad','?')} | "
                f"{ext.get('bolum','?')} | {ext.get('firma_adi','?')} | "
                f"{r['ai_karar']} | Tarih: {r['yukleme_tarihi']}"
            )
        except Exception:
            continue

    sistem = (
        "Sen bir staj başvuruları analiz uzmanısın. Sekretere kısa, net, "
        "vurgulu Türkçe özet sunarsın. Maddeler halinde ve emojilerle."
    )
    kullanici = (
        "Aşağıda son 20 staj başvurusu var. Bu başvuruları analiz et:\n\n"
        + "\n".join(items)
        + "\n\nÖzetinde şunları yer ver:\n"
        "1. 📊 Genel istatistik (kaç KABUL, kaç RED)\n"
        "2. 🏢 En çok başvuru gelen firmalar\n"
        "3. 🎓 En aktif bölümler\n"
        "4. ⚠️ Dikkat edilmesi gereken (acil/şüpheli) başvurular\n"
        "5. 💡 Sekretere öneriler"
    )

    ol, _ = load_services()
    try:
        model = ol.available_model(aktif_model())
        ozet  = ol.chat(model=model,
                        messages=[{"role":"system","content":sistem},
                                  {"role":"user","content":kullanici}],
                        timeout=90, options={"temperature":0.3})
        return jsonify({"ozet": ozet})
    except Exception as e:
        return jsonify({"ozet": f"Hata: {e}"}), 500


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
KULLANABILECEĞİN ARAÇLAR (sadece JSON ile çağırırsın):

1. LIST_BASVURU(filter)   → Başvuru listele.
   filter: "hepsi" | "beklemede" | "kabul" | "red"
   Örnek: {"tool":"LIST_BASVURU","args":{"filter":"beklemede"}}

2. GET_BASVURU(id)        → Tek bir başvuru detayı.
   Örnek: {"tool":"GET_BASVURU","args":{"id":5}}

3. ONAYLA(id, sebep)      → Başvuruyu onayla.
   Örnek: {"tool":"ONAYLA","args":{"id":3,"sebep":"Tüm kriterler uygun"}}

4. REDDET(id, sebep)      → Başvuruyu reddet.
   Örnek: {"tool":"REDDET","args":{"id":3,"sebep":"Tarihler dönem dışı"}}

5. ARA(anahtar)           → Başvurularda metin ara (ad, firma, bölüm).
   Örnek: {"tool":"ARA","args":{"anahtar":"yazılım"}}

6. ISTATISTIK(tip)        → İstatistik üret.
   tip: "ozet" | "firma" | "bolum" | "donem"
   Örnek: {"tool":"ISTATISTIK","args":{"tip":"firma"}}

7. ONCELIK_SIRALA()       → Bekleyen başvuruları aciliyete göre sırala.

8. CEVAP(metin)           → İşlem gerektirmeyen direkt yanıt.
   Örnek: {"tool":"CEVAP","args":{"metin":"Merhaba!"}}

KURALLAR:
- SADECE JSON döndür, başka açıklama yazma.
- Birden fazla işlem gerekirse en kritik olanı seç.
- ID belirtilmemişse önce LIST_BASVURU veya ARA kullan.
- ONAYLA/REDDET için mutlaka ID gerekir; yoksa CEVAP ile sor.
"""

def _agent_tool_list(filter_="hepsi"):
    q = "SELECT id, original_adi, durum, ai_karar, yukleme_tarihi, extracted_json FROM submissions"
    args = []
    if filter_ == "beklemede":
        q += " WHERE durum='beklemede'"
    elif filter_ == "kabul":
        q += " WHERE ai_karar='KABUL'"
    elif filter_ == "red":
        q += " WHERE ai_karar='RED'"
    q += " ORDER BY id DESC LIMIT 30"
    rows = get_db().execute(q, args).fetchall()
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
    r = get_db().execute("SELECT * FROM submissions WHERE id=?", (id_,)).fetchone()
    if not r: return {"hata": f"#{id_} bulunamadı"}
    d = dict(r)
    try: d["form"] = json.loads(d.get("extracted_json") or "{}")
    except: d["form"] = {}
    d.pop("extracted_json", None); d.pop("ai_rapor", None); d.pop("ai_detay_json", None)
    return d

def _agent_tool_karar(id_, karar, sebep=""):
    durum = "onaylandi" if karar == "KABUL" else "reddedildi"
    with get_db() as c:
        cur = c.execute("UPDATE submissions SET durum=?, ai_karar=? WHERE id=?",
                        (durum, karar, id_))
        if cur.rowcount == 0:
            return {"hata": f"#{id_} bulunamadı"}
    return {"ok": True, "id": id_, "yeni_durum": durum, "sebep": sebep}

def _agent_tool_ara(anahtar):
    rows = get_db().execute(
        "SELECT id, original_adi, ai_karar, durum, extracted_json FROM submissions ORDER BY id DESC"
    ).fetchall()
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
    rows = get_db().execute("SELECT * FROM submissions").fetchall()
    if tip == "ozet":
        return {
            "toplam":     len(rows),
            "kabul":      sum(1 for r in rows if r["ai_karar"] == "KABUL"),
            "red":        sum(1 for r in rows if r["ai_karar"] == "RED"),
            "beklemede":  sum(1 for r in rows if r["durum"]    == "beklemede"),
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
    rows = get_db().execute(
        "SELECT * FROM submissions WHERE durum='beklemede' ORDER BY id DESC"
    ).fetchall()
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

@app.route("/api/agent/komut", methods=["POST"])
@sekreter_required
def api_agent_komut():
    from services.form_service import extract_json_object
    data = request.get_json(force=True) or {}
    komut = (data.get("komut") or "").strip()
    if not komut:
        return jsonify({"ok": False, "yanit": "Komut boş."})

    sistem = (
        "Sen Amasya MYO staj başvuru sisteminin agent'ısın. "
        "Sekreterin doğal dildeki komutlarını analiz edip uygun aracı çağırırsın.\n\n"
        + AGENT_TOOLS_DOC
    )
    ol, _ = load_services()
    try:
        model = ol.available_model(aktif_model())
        raw = ol.chat(
            model=model,
            messages=[{"role":"system","content":sistem},
                      {"role":"user","content":f"Komut: {komut}"}],
            timeout=60, options={"temperature":0.0},
        )
    except Exception as e:
        return jsonify({"ok": False, "yanit": f"LLM hatası: {e}"})

    parsed = extract_json_object(raw) or {}
    tool   = (parsed.get("tool") or "").upper()
    args   = parsed.get("args") or {}

    sonuc = None
    try:
        if   tool == "LIST_BASVURU":  sonuc = _agent_tool_list(args.get("filter","hepsi"))
        elif tool == "GET_BASVURU":   sonuc = _agent_tool_get(int(args.get("id",0)))
        elif tool == "ONAYLA":        sonuc = _agent_tool_karar(int(args.get("id",0)), "KABUL", args.get("sebep",""))
        elif tool == "REDDET":        sonuc = _agent_tool_karar(int(args.get("id",0)), "RED",   args.get("sebep",""))
        elif tool == "ARA":           sonuc = _agent_tool_ara(args.get("anahtar",""))
        elif tool == "ISTATISTIK":    sonuc = _agent_tool_istatistik(args.get("tip","ozet"))
        elif tool == "ONCELIK_SIRALA": sonuc = _agent_tool_oncelik()
        elif tool == "CEVAP":         sonuc = {"mesaj": args.get("metin","")}
        else:
            return jsonify({"ok": False, "yanit": f"Anlaşılamadı: {raw[:200]}"})
    except Exception as e:
        return jsonify({"ok": False, "yanit": f"Araç hatası: {e}"})

    # Sonucu doğal dile çevir
    try:
        sentez_sistem = (
            "Sen agent'sın. Bir araç çalıştırdın ve sonuç geldi. "
            "Sekretere KISA, NET, Türkçe, emojili bir özet sun. Maddeler kullan."
        )
        sentez_user = (
            f"KOMUT: {komut}\n"
            f"ÇALIŞTIRILAN ARAÇ: {tool}\n"
            f"SONUÇ:\n{json.dumps(sonuc, ensure_ascii=False)[:3000]}"
        )
        cevap = ol.chat(model=model,
                        messages=[{"role":"system","content":sentez_sistem},
                                  {"role":"user","content":sentez_user}],
                        timeout=60, options={"temperature":0.3})
    except Exception:
        cevap = json.dumps(sonuc, ensure_ascii=False, indent=2)

    return jsonify({"ok": True, "tool": tool, "args": args, "sonuc": sonuc, "yanit": cevap})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
