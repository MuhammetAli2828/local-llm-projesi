"""
streamlit_app.py
================
Amasya MYO Staj Asistanı — Streamlit arayüzü.
İki sekme: Öğrenci Paneli | Sekreter Paneli
"""
from __future__ import annotations

import json
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import streamlit as st

# ─── TEMEL YAPILANDIRMA ────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Amasya MYO Staj Asistanı",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="collapsed",
)

BASE_DIR = Path(__file__).parent
DB_PATH  = BASE_DIR / "staj_st.db"
YONERGE  = BASE_DIR / "yonerge.pdf"
MODEL    = "qwen2.5:latest"

# ─── VERİTABANI ───────────────────────────────────────────────────────────────

def init_db() -> None:
    with sqlite3.connect(DB_PATH) as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS submissions (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                original_adi     TEXT,
                dosya_adi        TEXT,
                yukleme_tarihi   TEXT,
                durum            TEXT DEFAULT 'beklemede',
                ai_karar         TEXT,
                ai_mesaj         TEXT,
                ai_rapor         TEXT,
                ai_guven         REAL,
                extracted_json   TEXT,
                missing_json     TEXT
            )
        """)

def save_submission(
    original_adi: str,
    dosya_adi: str,
    ai_karar: str,
    ai_mesaj: str,
    ai_rapor: str,
    ai_guven: float,
    extracted: dict,
    missing: list,
) -> int:
    durum = "onaylandi" if ai_karar == "KABUL" else "reddedildi"
    with sqlite3.connect(DB_PATH) as c:
        cur = c.execute(
            """INSERT INTO submissions
               (original_adi, dosya_adi, yukleme_tarihi, durum,
                ai_karar, ai_mesaj, ai_rapor, ai_guven,
                extracted_json, missing_json)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                original_adi, dosya_adi,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                durum, ai_karar, ai_mesaj, ai_rapor, ai_guven,
                json.dumps(extracted, ensure_ascii=False),
                json.dumps(missing, ensure_ascii=False),
            ),
        )
        return cur.lastrowid

def get_all_submissions() -> List[sqlite3.Row]:
    with sqlite3.connect(DB_PATH) as c:
        c.row_factory = sqlite3.Row
        return c.execute(
            "SELECT * FROM submissions ORDER BY id DESC"
        ).fetchall()

def update_submission(sub_id: int, durum: str, karar: str) -> None:
    with sqlite3.connect(DB_PATH) as c:
        c.execute(
            "UPDATE submissions SET durum=?, ai_karar=? WHERE id=?",
            (durum, karar, sub_id),
        )

# ─── SERVİSLER (CACHED) ───────────────────────────────────────────────────────

@st.cache_resource(show_spinner="Yönerge ve model yükleniyor…")
def load_services():
    from services.ollama_service import OllamaClient
    from services.pdf_service import extract_pdf_text
    from rag_index import TfidfRagIndex

    ol  = OllamaClient()
    rag = TfidfRagIndex(chunk_size=600, overlap=100)
    if YONERGE.exists():
        rag.build_from_text("yonerge.pdf", extract_pdf_text(str(YONERGE)))
    return ol, rag


@st.cache_data(show_spinner=False)
def get_kurum_kurallari() -> List[str]:
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
                chunks.append(hit.chunk_text[:280])
    return chunks

# ─── CANLI DOĞRULAMA (LLM YOK) ────────────────────────────────────────────────

def live_validate(fd: Dict[str, Any]) -> List[Dict[str, str]]:
    """Anlık kural tabanlı doğrulama. Her render'da çalışır."""
    from services.rule_service import validate_form

    msgs: List[Dict[str, str]] = []
    v = validate_form(fd)

    for m in v["missing"]:
        msgs.append({"t": "err", "m": f"Zorunlu alan eksik: {m}"})
    for e in v["errors"]:
        msgs.append({"t": "err", "m": e})
    for w in v["warnings"]:
        msgs.append({"t": "warn", "m": w})

    if not msgs:
        filled = sum(
            1 for key in ["ad_soyad", "ogrenci_no", "bolum", "firma_adi",
                          "baslangic_tarihi", "bitis_tarihi", "staj_gun_sayisi"]
            if fd.get(key) and str(fd[key]).strip()
        )
        if filled >= 7:
            msgs.append({"t": "ok", "m": "Tüm zorunlu alanlar dolu, form gönderime hazır."})
        else:
            msgs.append({"t": "info", "m": "Formu doldurmaya devam edin…"})
    return msgs

# ─── AJAN ANALİZİ ─────────────────────────────────────────────────────────────

def agent_analiz(form_data: dict, pdf_text: str = "") -> Dict[str, Any]:
    """LLM ile PDF/form değerlendirmesi. KABUL / RED karar verir."""
    from services.rule_service import validate_form

    v = validate_form(form_data)
    is_valid = not v["missing"] and not v["errors"]

    kurallar = get_kurum_kurallari()
    kural_text = "\n".join(f"- {k}" for k in kurallar[:5]) if kurallar else "—"

    form_ozet = json.dumps(
        {k: val for k, val in form_data.items() if val and str(val).strip()},
        ensure_ascii=False, indent=2
    )

    sistem = (
        "Sen Amasya MYO staj başvuru kontrol asistanısın. "
        "Yalnızca zorunlu alanlar (ad_soyad, ogrenci_no, bolum, tc_kimlik_no, "
        "firma_adi, firma_adresi, baslangic_tarihi, bitis_tarihi, staj_gun_sayisi) "
        "eksikse RED ver. Tarih geçmişte olması veya gün sayısı az görünmesi "
        "tek başına RED nedeni DEĞİLDİR — sadece WARNING sayılır. "
        "Yanıtını MUTLAKA şu JSON formatında ver:\n"
        '{"karar":"KABUL","mesaj":"…","guven":0.95,"eksikler":[]}'
    )

    kullanici = (
        f"Kurum staj yönergesi özeti:\n{kural_text}\n\n"
        f"Form verileri:\n{form_ozet}\n\n"
        f"Kural sonuçları:\n"
        f"  Eksik alanlar: {v['missing']}\n"
        f"  Hatalar: {v['errors']}\n"
        f"  Uyarılar: {v['warnings']}\n\n"
        + (f"PDF içeriğinden alınan ek bilgi:\n{pdf_text[:800]}\n\n" if pdf_text else "")
        + "Yukarıdaki bilgilere göre başvuruyu değerlendir ve JSON yanıtı ver."
    )

    ol, _ = load_services()
    try:
        model = ol.available_model(MODEL)
        raw = ol.chat(
            model=model,
            messages=[
                {"role": "system", "content": sistem},
                {"role": "user",   "content": kullanici},
            ],
            timeout=90,
            options={"temperature": 0.1},
        )
    except Exception as e:
        karar = "KABUL" if is_valid else "RED"
        return {
            "karar": karar,
            "mesaj": f"Ollama hatası — kural tabanlı karar: {e}",
            "guven": 0.7 if is_valid else 0.3,
            "eksikler": v["missing"],
            "rapor": raw if "raw" in dir() else "",
        }

    from services.form_service import extract_json_object
    parsed = extract_json_object(raw)
    if parsed:
        karar = "KABUL" if str(parsed.get("karar", "")).upper() == "KABUL" else "RED"
        if not is_valid:
            karar = "RED"
        return {
            "karar": karar,
            "mesaj": parsed.get("mesaj", raw[:300]),
            "guven": float(parsed.get("guven", 0.8)),
            "eksikler": parsed.get("eksikler", v["missing"]),
            "rapor": raw,
        }

    karar = "KABUL" if is_valid else "RED"
    return {
        "karar": karar,
        "mesaj": raw[:400],
        "guven": 0.7,
        "eksikler": v["missing"],
        "rapor": raw,
    }

# ─── YARDIMCI ─────────────────────────────────────────────────────────────────

def render_feedback(msgs: List[Dict[str, str]]) -> None:
    icons = {"ok": "✅", "warn": "⚠️", "err": "❌", "info": "ℹ️"}
    colors = {
        "ok":   "#d1fae5",
        "warn": "#fef9c3",
        "err":  "#fee2e2",
        "info": "#e0e7ff",
    }
    for m in msgs:
        t = m.get("t", "info")
        bg = colors.get(t, "#f1f5f9")
        st.markdown(
            f'<div style="background:{bg};border-radius:8px;'
            f'padding:8px 12px;margin:4px 0;font-size:0.87rem;">'
            f'{icons.get(t,"•")} {m["m"]}</div>',
            unsafe_allow_html=True,
        )

# ─── ANA UYGULAMA ─────────────────────────────────────────────────────────────

init_db()

tab_ogrenci, tab_sekreter = st.tabs(["🎓 Öğrenci Paneli", "🗂️ Sekreter Paneli"])

# ══════════════════════════════════════════════════════════════════════════════
# SEKME 1 — ÖĞRENCİ PANELİ
# ══════════════════════════════════════════════════════════════════════════════
with tab_ogrenci:
    st.markdown("## 🎓 Staj Başvuru Formu")
    left, right = st.columns([0.38, 0.62], gap="large")

    # ── SOL: Kurallar + Canlı Geri Bildirim + Chatbox ──────────────────────
    with left:
        st.markdown("### 📋 Kurum Kuralları")
        with st.spinner("Yönerge yükleniyor…"):
            kurallar = get_kurum_kurallari()
        if kurallar:
            for k in kurallar:
                st.markdown(
                    f'<div style="background:#f0f4ff;border-left:3px solid #4f46e5;'
                    f'padding:8px 12px;margin:4px 0;border-radius:0 6px 6px 0;'
                    f'font-size:0.82rem;">{k}</div>',
                    unsafe_allow_html=True,
                )
        else:
            st.info("Yönerge PDF bulunamadı.")

        st.divider()
        st.markdown("### 🔍 Canlı Form Kontrolü")
        feedback_slot = st.empty()

        st.divider()
        st.markdown("### 💬 Yönerge Chatbox")

        if "chat_history" not in st.session_state:
            st.session_state.chat_history = []

        chat_container = st.container(height=320)
        with chat_container:
            for msg in st.session_state.chat_history:
                with st.chat_message(msg["role"]):
                    st.write(msg["content"])

        soru = st.chat_input("Yönerge hakkında soru sor…")
        if soru:
            st.session_state.chat_history.append({"role": "user", "content": soru})
            with chat_container:
                with st.chat_message("user"):
                    st.write(soru)

            ol, rag = load_services()
            hits = rag.search(soru, top_k=3)
            context = "\n\n".join(h.chunk_text for h in hits) if hits else ""
            sistem_c = (
                "Sen Amasya MYO staj yönergesi konusunda uzman bir asistansın. "
                "Yalnızca yönerge içeriğine dayanarak yanıt ver. Türkçe yaz."
            )
            user_c = (
                f"Yönerge bağlamı:\n{context}\n\nSoru: {soru}"
                if context
                else f"Soru: {soru} (Yönerge bulunamadı, genel bilgiyle yanıt ver.)"
            )
            try:
                model = ol.available_model(MODEL)
                yanit = ol.chat(
                    model=model,
                    messages=[
                        {"role": "system", "content": sistem_c},
                        {"role": "user",   "content": user_c},
                    ],
                    timeout=60,
                )
            except Exception as e:
                yanit = f"Ollama bağlantı hatası: {e}"

            st.session_state.chat_history.append({"role": "assistant", "content": yanit})
            with chat_container:
                with st.chat_message("assistant"):
                    st.write(yanit)

    # ── SAĞ: FORM ──────────────────────────────────────────────────────────
    with right:
        form_data: Dict[str, Any] = {}

        with st.expander("👤 Öğrenci Bilgileri", expanded=True):
            c1, c2 = st.columns(2)
            form_data["ad_soyad"]        = c1.text_input("Ad Soyad *", key="ad_soyad")
            form_data["ogrenci_no"]      = c2.text_input("Öğrenci No *", key="ogrenci_no")
            form_data["bolum"]           = c1.text_input("Bölüm / Program *", key="bolum")
            form_data["tc_kimlik_no"]    = c2.text_input("TC Kimlik No *", key="tc_kimlik_no")
            form_data["donem"]           = c1.selectbox("Eğitim Dönemi", ["Güz", "Bahar"], key="donem")
            form_data["telefon_no"]      = c2.text_input("Telefon No", key="telefon_no")
            form_data["ikametgah_adresi"]= st.text_input("İkametgah Adresi", key="ikametgah_adresi")

        with st.expander("🏢 Staj Bilgileri", expanded=True):
            form_data["firma_adi"]    = st.text_input("Firma Adı *", key="firma_adi")
            form_data["firma_adresi"] = st.text_input("Firma Adresi *", key="firma_adresi")
            c1, c2 = st.columns(2)
            form_data["hizmet_alani"]   = c1.text_input("Hizmet Alanı", key="hizmet_alani")
            form_data["haftalik_calisilan_gun"] = c2.number_input(
                "Haftalık Çalışma Günü", min_value=0, max_value=7, value=5, key="hcg"
            )
            form_data["firma_telefon"] = c1.text_input("Firma Telefon", key="firma_telefon")
            form_data["firma_eposta"]  = c2.text_input("Firma E-posta", key="firma_eposta")
            form_data["firma_web"]     = c1.text_input("Firma Web", key="firma_web")
            form_data["firma_fax"]     = c2.text_input("Firma Fax", key="firma_fax")

            c1, c2, c3 = st.columns(3)
            bas = c1.date_input("Başlangıç Tarihi *", key="bas_tar", value=None)
            bit = c2.date_input("Bitiş Tarihi *", key="bit_tar", value=None)
            gun = c3.number_input("Staj Gün Sayısı *", min_value=0, value=0, key="staj_gun")

            form_data["baslangic_tarihi"] = str(bas) if bas else ""
            form_data["bitis_tarihi"]     = str(bit) if bit else ""
            form_data["staj_gun_sayisi"]  = gun if gun > 0 else ""

        with st.expander("🏭 Departman Bilgileri", expanded=False):
            c1, c2 = st.columns(2)
            form_data["departman_1"] = c1.text_input("Departman 1", key="dep1")
            form_data["departman_2"] = c2.text_input("Departman 2", key="dep2")
            form_data["departman_3"] = c1.text_input("Departman 3", key="dep3")
            form_data["departman_4"] = c2.text_input("Departman 4", key="dep4")
            st.markdown("**Personel Sayıları**")
            r1, r2, r3 = st.columns(3)
            form_data["personel_yonetici"]  = r1.number_input("Yönetici",  min_value=0, value=0, key="py")
            form_data["personel_muhendis"]  = r2.number_input("Mühendis",  min_value=0, value=0, key="pm")
            form_data["personel_tekniker"]  = r3.number_input("Tekniker",  min_value=0, value=0, key="ptk")
            form_data["personel_usta"]      = r1.number_input("Usta",      min_value=0, value=0, key="pu")
            form_data["personel_teknisyen"] = r2.number_input("Teknisyen", min_value=0, value=0, key="pts")
            form_data["personel_isci"]      = r3.number_input("İşçi",      min_value=0, value=0, key="pi")

        # Canlı geri bildirim
        msgs = live_validate(form_data)
        with feedback_slot:
            render_feedback(msgs)

        st.divider()
        st.markdown("#### 📄 PDF İşlemleri")

        # ── PDF OLUŞTUR & İNDİR ────────────────────────────────────────────
        col_dl, col_ul = st.columns(2)
        with col_dl:
            if st.button("📥 PDF Oluştur & İndir", use_container_width=True):
                from services.pdf_service import fill_staj_pdf
                with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                    tmp_path = tmp.name
                try:
                    fill_staj_pdf(form_data, tmp_path)
                    with open(tmp_path, "rb") as f:
                        st.session_state["pdf_bytes"] = f.read()
                    st.success("PDF hazır!")
                except Exception as e:
                    st.error(f"PDF oluşturulamadı: {e}")

        if st.session_state.get("pdf_bytes"):
            st.download_button(
                label="💾 PDF'i İndir",
                data=st.session_state["pdf_bytes"],
                file_name="staj_basvuru.pdf",
                mime="application/pdf",
                use_container_width=True,
            )

        # ── PDF YÜKLE & GÖNDER ────────────────────────────────────────────
        with col_ul:
            uploaded = st.file_uploader(
                "📤 PDF Yükle", type=["pdf"], key="pdf_upload", label_visibility="collapsed"
            )

        if uploaded:
            st.info(f"Yüklenen: **{uploaded.name}**")
            if st.button("🚀 Sekretere Gönder", use_container_width=True, type="primary"):
                with st.spinner("AI analiz yapıyor…"):
                    # Form verisi varsa kullan, yoksa PDF'ten çek
                    has_form = any(
                        form_data.get(k) and str(form_data[k]).strip()
                        for k in ["ad_soyad", "firma_adi", "baslangic_tarihi"]
                    )
                    if has_form:
                        analysis_data = form_data.copy()
                        pdf_text = ""
                    else:
                        from services.pdf_service import extract_pdf_text
                        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                            tmp.write(uploaded.read())
                            tmp_path = tmp.name
                        pdf_text = extract_pdf_text(tmp_path)
                        analysis_data = {}

                    result = agent_analiz(analysis_data, pdf_text)

                sub_id = save_submission(
                    original_adi=uploaded.name,
                    dosya_adi=uploaded.name,
                    ai_karar=result["karar"],
                    ai_mesaj=result["mesaj"],
                    ai_rapor=result.get("rapor", ""),
                    ai_guven=result.get("guven", 0.0),
                    extracted=analysis_data,
                    missing=result.get("eksikler", []),
                )

                karar = result["karar"]
                if karar == "KABUL":
                    st.success(f"✅ Başvuru sekretere iletildi (ID: {sub_id}) — AI Kararı: **KABUL**")
                else:
                    st.error(f"❌ Başvuru sekretere iletildi (ID: {sub_id}) — AI Kararı: **RED**")
                st.info(result["mesaj"])
                st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# SEKME 2 — SEKRETER PANELİ
# ══════════════════════════════════════════════════════════════════════════════
with tab_sekreter:
    st.markdown("## 🗂️ Sekreter Paneli")

    rows = get_all_submissions()
    total   = len(rows)
    kabul   = sum(1 for r in rows if r["ai_karar"] == "KABUL")
    red     = sum(1 for r in rows if r["ai_karar"] == "RED")
    bekleyen = sum(1 for r in rows if r["durum"] == "beklemede")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Toplam Başvuru", total)
    m2.metric("✅ Kabul",       kabul)
    m3.metric("❌ Red",         red)
    m4.metric("⏳ Beklemede",   bekleyen)

    st.divider()

    if not rows:
        st.info("Henüz başvuru yok.")
    else:
        for row in rows:
            karar = row["ai_karar"] or "—"
            durum = row["durum"]    or "beklemede"
            karar_icon = "✅" if karar == "KABUL" else ("❌" if karar == "RED" else "⏳")

            with st.expander(
                f"{karar_icon} #{row['id']} — {row['original_adi']}  |  "
                f"{row['yukleme_tarihi']}  |  Durum: **{durum}**",
                expanded=(durum == "beklemede"),
            ):
                col_info, col_action = st.columns([0.7, 0.3])

                with col_info:
                    st.markdown(f"**AI Kararı:** {karar}  |  **Güven:** {row['ai_guven']:.0%}")
                    st.markdown(f"**Mesaj:** {row['ai_mesaj']}")

                    eksikler = json.loads(row["missing_json"] or "[]")
                    if eksikler:
                        st.warning("Eksik alanlar: " + ", ".join(eksikler))

                    extracted = json.loads(row["extracted_json"] or "{}")
                    if extracted:
                        with st.container():
                            st.markdown("**Form Özeti:**")
                            disp_keys = [
                                "ad_soyad", "ogrenci_no", "bolum",
                                "firma_adi", "baslangic_tarihi",
                                "bitis_tarihi", "staj_gun_sayisi",
                            ]
                            for k in disp_keys:
                                v = extracted.get(k)
                                if v and str(v).strip():
                                    st.markdown(f"- **{k}:** {v}")

                with col_action:
                    if st.button("✅ Onayla", key=f"onayla_{row['id']}", use_container_width=True):
                        update_submission(row["id"], "onaylandi", "KABUL")
                        st.success("Onaylandı!")
                        st.rerun()
                    if st.button("❌ Reddet", key=f"reddet_{row['id']}", use_container_width=True):
                        update_submission(row["id"], "reddedildi", "RED")
                        st.error("Reddedildi.")
                        st.rerun()

                    if row["ai_rapor"]:
                        with st.expander("AI Raporu", expanded=False):
                            st.text(row["ai_rapor"][:800])
