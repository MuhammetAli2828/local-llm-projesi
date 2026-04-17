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

from flask import Flask, jsonify, render_template, request, send_file

app     = Flask(__name__)
BASE    = Path(__file__).parent
DB_PATH = BASE / "staj.db"
UPLOAD  = BASE / "uploads" / "pdfs"
YONERGE = BASE / "yonerge.pdf"
MODEL   = "qwen2.5:latest"

UPLOAD.mkdir(parents=True, exist_ok=True)

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
    if YONERGE.exists():
        rag.build_from_text("yonerge.pdf", extract_pdf_text(str(YONERGE)))
    _services["ol"]  = ol
    _services["rag"] = rag
    return ol, rag

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
        karar = "KABUL" if str(parsed.get("karar","")).upper() == "KABUL" else "RED"
        if not is_valid:
            karar = "RED"
        return {
            "karar":    karar,
            "mesaj":    parsed.get("mesaj", raw[:300]),
            "guven":    float(parsed.get("guven", 0.8)),
            "eksikler": parsed.get("eksikler", v["missing"]),
            "rapor":    raw,
        }
    karar = "KABUL" if is_valid else "RED"
    return {"karar": karar, "mesaj": raw[:400], "guven": 0.7,
            "eksikler": v["missing"], "rapor": raw}

# ─── ROTALAR ──────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")

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
    file = request.files.get("pdf")
    if not file:
        return jsonify({"ok": False, "hata": "Dosya yok"}), 400

    form_json = request.form.get("form_data", "")
    form_data = json.loads(form_json) if form_json else {}
    pdf_text  = ""

    if not any(form_data.get(k) and str(form_data[k]).strip()
               for k in ["ad_soyad", "firma_adi", "baslangic_tarihi"]):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            file.save(tmp.name)
            pdf_text  = extract_pdf_text(tmp.name)
            form_data = {}

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

    return jsonify({"ok": True, "id": sub_id, **result})

@app.route("/api/basvurular")
def api_basvurular():
    rows = get_db().execute(
        "SELECT * FROM submissions ORDER BY id DESC"
    ).fetchall()
    return jsonify([dict(r) for r in rows])

@app.route("/api/karar", methods=["POST"])
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
    data  = request.get_json(force=True) or {}
    soru  = data.get("soru", "").strip()
    if not soru:
        return jsonify({"yanit": "Soru boş."})
    ol, rag = load_services()
    hits    = rag.search(soru, top_k=3)
    context = "\n\n".join(h.chunk_text for h in hits) if hits else ""
    sistem  = ("Sen Amasya MYO staj yönergesi uzmanısın. "
               "Yalnızca yönerge içeriğine göre Türkçe yanıt ver.")
    user_c  = (f"Yönerge:\n{context}\n\nSoru: {soru}" if context
               else f"Soru: {soru}")
    try:
        model = ol.available_model(MODEL)
        yanit = ol.chat(model=model,
                        messages=[{"role":"system","content":sistem},
                                  {"role":"user","content":user_c}],
                        timeout=60)
    except Exception as e:
        yanit = f"Ollama hatası: {e}"
    return jsonify({"yanit": yanit})

if __name__ == "__main__":
    app.run(debug=True, port=5000)
