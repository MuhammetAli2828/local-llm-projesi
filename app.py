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
YONERGE = BASE / "yonerge.pdf"
DOCS    = BASE / "docs"
MODEL   = "qwen2.5:latest"

UPLOAD.mkdir(parents=True, exist_ok=True)
DOCS.mkdir(parents=True, exist_ok=True)

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
        model = ol.available_model(MODEL)
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
    from services.rule_service import validate_form
    from services.form_service import extract_json_object

    v        = validate_form(form_data)
    is_valid = not v["missing"] and not v["errors"]
    kurallar = get_kurallar()
    kural_text = "\n".join(f"- {k}" for k in kurallar[:5]) or "—"

    form_ozet = json.dumps(
        {k: val for k, val in form_data.items() if val and str(val).strip()},
        ensure_ascii=False, indent=2,
    )

    sistem = (
        "Sen Amasya MYO staj başvuru kontrol asistanısın. "
        "Yalnızca zorunlu alanlar eksikse RED ver. Tarih geçmişte veya "
        "gün sayısı az olması tek başına RED nedeni değildir. "
        "Yanıtını MUTLAKA şu JSON formatında ver:\n"
        '{"karar":"KABUL","mesaj":"...","guven":0.95,"eksikler":[]}'
    )
    kullanici = (
        f"Yönerge özeti:\n{kural_text}\n\n"
        f"Form:\n{form_ozet}\n\n"
        f"Eksik: {v['missing']}\nHata: {v['errors']}\nUyarı: {v['warnings']}\n\n"
        + (f"PDF içeriği:\n{pdf_text[:800]}\n\n" if pdf_text else "")
        + "Başvuruyu değerlendir."
    )

    ol, _ = load_services()
    try:
        model = ol.available_model(MODEL)
        raw   = ol.chat(
            model=model,
            messages=[
                {"role": "system", "content": sistem},
                {"role": "user",   "content": kullanici},
            ],
            timeout=90, options={"temperature": 0.1},
        )
    except Exception as e:
        karar = "KABUL" if is_valid else "RED"
        return {"karar": karar, "mesaj": str(e), "guven": 0.5,
                "eksikler": v["missing"], "rapor": ""}

    parsed = extract_json_object(raw)
    if parsed:
        llm_karar = str(parsed.get("karar","")).upper()
        if not is_valid:
            karar = "RED"
        else:
            # Kural doğrulaması geçtiyse LLM RED dese bile KABUL
            karar = "KABUL"
        mesaj = parsed.get("mesaj", raw[:300])
        if isinstance(mesaj, dict):
            mesaj = str(mesaj)
        return {
            "karar":    karar,
            "mesaj":    mesaj,
            "guven":    float(parsed.get("guven", 0.8)),
            "eksikler": v["missing"],   # Her zaman kural tabanlı eksik listesi
            "rapor":    raw,
        }
    karar = "KABUL" if is_valid else "RED"
    return {"karar": karar, "mesaj": raw[:400], "guven": 0.7,
            "eksikler": v["missing"], "rapor": raw}

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

    # Her zaman PDF'den çıkar
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        file.save(tmp.name)
        tmp_path = tmp.name
    pdf_text = extract_pdf_text(tmp_path)

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
                extracted_json, missing_json)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                file.filename,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "onaylandi" if result["karar"] == "KABUL" else "reddedildi",
                result["karar"], result["mesaj"], result.get("rapor",""),
                result.get("guven", 0.0),
                json.dumps(form_data, ensure_ascii=False),
                json.dumps(result.get("eksikler",[]), ensure_ascii=False),
            ),
        )
        sub_id = cur.lastrowid

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
    ]
    with get_db() as c:
        for k in allowed:
            if k in data:
                c.execute("INSERT OR REPLACE INTO settings (key,value) VALUES (?,?)",
                          (k, str(data[k])))
    return jsonify({"ok": True})

@app.route("/api/basvurular")
@sekreter_required
def api_basvurular():
    rows = get_db().execute(
        "SELECT * FROM submissions ORDER BY id DESC"
    ).fetchall()
    return jsonify([dict(r) for r in rows])

@app.route("/api/karar", methods=["POST"])
@sekreter_required
def api_karar():
    data   = request.get_json(force=True) or {}
    sub_id = data.get("id")
    karar  = data.get("karar")
    durum  = "onaylandi" if karar == "KABUL" else "reddedildi"
    with get_db() as c:
        c.execute("UPDATE submissions SET durum=?, ai_karar=? WHERE id=?",
                  (durum, karar, sub_id))
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
        model = ol.available_model(MODEL)
        yanit = ol.chat(model=model, messages=messages, timeout=90,
                        options={"temperature": 0.3})
    except Exception as e:
        yanit = f"Ollama hatası: {e}"
    return jsonify({"yanit": yanit})

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


if __name__ == "__main__":
    app.run(debug=True, port=5000)
