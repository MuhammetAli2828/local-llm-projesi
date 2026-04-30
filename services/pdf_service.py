"""
pdf_service.py  –  Amasya Üniversitesi Staj Formu PDF Doldurma
==============================================================
Yaklaşım: staj_belgesi.pdf şablonu üzerine sadece veri değerleri overlay edilir.
Şablon bulunamazsa sıfırdan PDF üretme (fallback) devreye girer.

A4 = 595 x 841 pt, orijin sol-alt (ReportLab standardı)
"""
from __future__ import annotations

import io
from pathlib import Path
from typing import Any, Dict

from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as rl_canvas

try:
    from pypdf import PdfReader, PdfWriter
except ImportError:
    from PyPDF2 import PdfReader, PdfWriter  # type: ignore

W, H = 595.0, 841.0
ML  = 42     # sol kenar
MR  = 553    # sağ kenar
MID = 300    # orta ayırıcı x

# Şablon PDF yolu (fill_staj_pdf içinde BASE_DIR ile birleştirilir)
_TEMPLATE_NAME = "staj_belgesi.pdf"


def _register_font() -> str:
    # Windows + Linux + macOS Türkçe destekli font yolları
    candidates = [
        # Windows
        r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\tahoma.ttf",
        r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\calibri.ttf",
        # Linux
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        # macOS
        "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for p in candidates:
        if Path(p).exists():
            try:
                pdfmetrics.registerFont(TTFont("TR", p))
                return "TR"
            except Exception:
                pass
    return "Helvetica"


FONT = _register_font()


# ── Yardımcılar ───────────────────────────────────────────────────────────────
def _val(c, x, y, text, size=9.0):
    if not text:
        return
    c.setFont(FONT, size)
    c.setFillGray(0)
    c.drawString(x, y, str(text))


def _chk(c, x, y, checked=False):
    """Sadece overlay: kutucuk değil, sadece işaret var ise X koy."""
    if checked:
        c.setFont(FONT, 7)
        c.setFillGray(0)
        c.drawString(x + 1, y + 1, "x")


def _wrap_val(c, text, x, y, max_w, size=8.5, lead=13) -> float:
    """Uzun metin satırlarını kaydırarak yaz."""
    if not text:
        return y
    words = text.split()
    lines, cur = [], []
    for w in words:
        test = " ".join(cur + [w])
        if c.stringWidth(test, FONT, size) > max_w and cur:
            lines.append(" ".join(cur))
            cur = [w]
        else:
            cur.append(w)
    if cur:
        lines.append(" ".join(cur))
    yp = y
    for ln in lines:
        c.setFont(FONT, size)
        c.setFillGray(0)
        c.drawString(x, yp, ln)
        yp -= lead
    return yp


# ── SAYFA 1 – Sadece değerler ─────────────────────────────────────────────────
# Koordinatlar yeni staj_belgesi.pdf (DOCX'ten üretilen) için pdfplumber ile kalibre edildi.
# ReportLab Y: sayfa altından yukarıya (0=alt, 841=üst)
def _p1_overlay(c, d):
    sv = lambda k: str(d.get(k) or "")

    # ── PARAGRAF: dönem, tarih/gün ──────────────────────────────────────────
    # Yeni şablon (rl_y baseline):
    #   "Güz/Bahar" prefix dots: rl_y=691.6, x=258.6 → "...." kısmı 258-285
    #   ".../.../202.. ile" baslangic: rl_y=670.9, x=496.4
    #   ".../.../202.." bitis:  rl_y=650.2, x=36.0
    #   "…… …… günü" gun:        rl_y=650.2, x=173.5 - 226
    donem = sv("donem")
    if donem:
        c.setFillColorRGB(1, 1, 1)
        c.rect(256, 689, 28, 11, fill=1, stroke=0)
        _val(c, 259, 692, donem, 8.5)
    bas = sv("baslangic_tarihi")
    bit = sv("bitis_tarihi")
    gun = sv("staj_gun_sayisi")
    if bas:
        c.setFillColorRGB(1, 1, 1)
        c.rect(493, 668, 50, 12, fill=1, stroke=0)
        _val(c, 496, 671, bas, 8.5)
    if bit:
        c.setFillColorRGB(1, 1, 1)
        c.rect(33, 647, 52, 12, fill=1, stroke=0)
        _val(c, 36, 650, bit, 8.5)
    if gun:
        c.setFillColorRGB(1, 1, 1)
        c.rect(170, 647, 42, 12, fill=1, stroke=0)
        _val(c, 173, 650, str(gun), 8.5)
    c.setFillGray(0)

    # ── ÖĞRENCİ ALANLARI ──────────────────────────────────────────────────────
    # Yeni şablon (rl_baseline):
    #   Bölümü/Programı: rl_y=585.1, ":" x=160, TC Kimlik ":" x≈438
    #   Adı Soyadı:     rl_y=561.8, ":" x=160
    #   Öğrenci No/Tel: rl_y=538.7, ":" x=160 / ":" x=390
    #   İkametgâh:      rl_y=515.5, ":" x=160
    Y_R1 = 587
    Y_R2 = 564
    Y_R3 = 540
    Y_R4 = 517

    _val(c, 170, Y_R1, sv("bolum"))
    _val(c, 446, Y_R1, sv("tc_kimlik_no"))
    _val(c, 170, Y_R2, sv("ad_soyad"))
    _val(c, 170, Y_R3, sv("ogrenci_no"))
    _val(c, 400, Y_R3, sv("telefon_no"))
    _wrap_val(c, sv("ikametgah_adresi"), 170, Y_R4, 370, size=8.5)

    # ── STAJ YERİ ALANLARI ────────────────────────────────────────────────────
    # Yeni şablon (rl_baseline):
    #   Adı:    rl_y=464.0, ":" x=158
    #   Adresi: rl_y=440.8
    #   Hizmet/Haftalık: rl_y=417.6, sağ kolon ":" x≈516
    #   Tel/Başlama:     rl_y=394.4, sağ kolon ":" x=484
    #   Eposta/Bitiş:    rl_y=371.2
    #   Web/Fax:         rl_y=347.9
    Y_S1 = 466
    Y_S2 = 443
    Y_S3 = 420
    Y_S4 = 397
    Y_S5 = 374
    Y_S6 = 350

    _val(c, 165, Y_S1, sv("firma_adi"))
    _wrap_val(c, sv("firma_adresi"), 165, Y_S2, 290, size=8.5)
    _val(c, 165, Y_S3, sv("hizmet_alani"))
    _val(c, 480, Y_S3, sv("haftalik_calisilan_gun"))
    _val(c, 165, Y_S4, sv("firma_telefon"))
    _val(c, 490, Y_S4, sv("baslangic_tarihi"))
    _val(c, 165, Y_S5, sv("firma_eposta"))
    _val(c, 490, Y_S5, sv("bitis_tarihi"))
    _val(c, 165, Y_S6, sv("firma_web"))
    _val(c, 490, Y_S6, sv("firma_fax"))

    # ── DEPARTMAN CHECK'LERİ ──────────────────────────────────────────────────
    # Yeni şablon (rl_baseline):
    #   ÜRETİM/...:      rl_y=280.6
    #   PAZARLAMA/...:   rl_y=259.0
    #   MUH./FİN./...:   rl_y=238.1
    #   diğer:           rl_y=217.6
    DROWS = [
        (281, "d_uretim",    "p_yonetici", "p_usta"),
        (259, "d_pazarlama", "p_muhendis",  "p_teknisyen"),
        (238, "d_muh",       "p_tekniker",  "p_isci"),
        (218, "d_diger1",    "p_diger1",    "p_diger2"),
    ]
    DROWS2 = [
        (281, "d_insan"),
        (259, "d_teknik"),
        (238, "d_buro"),
        (218, "d_diger2"),
    ]
    for y_, k1, k3, k4 in DROWS:
        _chk(c, 115, y_ + 1, bool(d.get(k1)))
        _val(c, 393, y_, sv(k3), 8)
        _val(c, 534, y_, sv(k4), 8)
    for y_, k2 in DROWS2:
        _chk(c, 250, y_ + 1, bool(d.get(k2)))

    # ── İMKANLAR CHECK'LERİ ───────────────────────────────────────────────────
    # Yeni şablon (rl_baseline):
    #   Ücret/Yemek/Fotoğraf/Nüfus: rl_y=148.7
    #   Servis/Savcılık:            rl_y=135.0
    Y_I1 = 149
    Y_I2 = 135

    _chk(c, 90,  Y_I1 + 1, bool(d.get("ucret")))
    _chk(c, 195, Y_I1 + 1, bool(d.get("yemek")))
    _chk(c, 415, Y_I1 + 1, bool(d.get("fotograf")))
    _chk(c, 535, Y_I1 + 1, bool(d.get("nufus_cuzdani")))
    _chk(c, 90,  Y_I2 + 1, bool(d.get("servis")))
    _chk(c, 415, Y_I2 + 1, bool(d.get("savcilik_belgesi")))


# ── SAYFA 2 – Sadece değerler ─────────────────────────────────────────────────
def _p2_overlay(c, d):
    sv = lambda k: str(d.get(k) or "")
    _val(c, 118, 729, sv("isveren_ad_soyad"))
    _val(c, 132, 711, sv("isveren_unvan"))


# ── SIFIRDAN PDF (fallback) ───────────────────────────────────────────────────
def _lbl(c, x, y, text, size=7.5):
    c.setFont(FONT, size); c.setFillGray(0.35)
    c.drawString(x, y, text); c.setFillGray(0)


def _hline(c, y, x1=ML, x2=MR, w=0.5):
    c.setLineWidth(w); c.setStrokeGray(0.35)
    c.line(x1, y, x2, y); c.setStrokeGray(0)


def _vline(c, x, y1, y2, w=0.5):
    c.setLineWidth(w); c.setStrokeGray(0.35)
    c.line(x, y1, x, y2); c.setStrokeGray(0)


def _chk_full(c, x, y, checked=False):
    c.setLineWidth(0.5); c.setStrokeGray(0.4)
    c.rect(x, y, 8, 8, fill=0); c.setStrokeGray(0)
    if checked:
        c.setFont(FONT, 7); c.drawString(x + 1, y + 1, "x")


def _sec(c, y, text):
    _hline(c, y + 14, w=1.2)
    _hline(c, y - 2,  w=0.5)
    c.setFont(FONT, 9); c.setFillGray(0)
    c.drawString(ML + 2, y + 3, text)


def _wrap(c, text, x, y, max_w, size=8.5, lead=13) -> float:
    words = text.split()
    lines, cur = [], []
    for w in words:
        test = " ".join(cur + [w])
        if c.stringWidth(test, FONT, size) > max_w and cur:
            lines.append(" ".join(cur)); cur = [w]
        else:
            cur.append(w)
    if cur:
        lines.append(" ".join(cur))
    yp = y
    for ln in lines:
        c.setFont(FONT, size); c.drawString(x, yp, ln); yp -= lead
    return yp


def _p1_full(c, d):
    """Sayfa 1 – şablon yokken sıfırdan üretme (fallback)."""
    sv = lambda k: str(d.get(k) or "")

    c.setLineWidth(0.8); c.setStrokeGray(0.3)
    c.rect(ML, 328, MR - ML, 487, fill=0); c.setStrokeGray(0)

    c.setFillColorRGB(0.55, 0, 0); c.rect(ML, 769, 58, 46, fill=1, stroke=0)
    c.setFillColorRGB(1, 1, 1); c.setFont(FONT, 6.5)
    c.drawCentredString(ML + 29, 800, "AMASYA")
    c.drawCentredString(ML + 29, 789, "ÜNİVERSİTESİ"); c.setFillGray(0)

    cx = (ML + 58 + MR) / 2
    c.setFont(FONT, 12); c.drawCentredString(cx, 802, "AMASYA ÜNİVERSİTESİ")
    c.setFont(FONT, 10); c.drawCentredString(cx, 787, "ZORUNLU STAJ BAŞVURU BİLGİ FORMU")
    c.setFont(FONT, 7);  c.drawRightString(MR, 775, "KYT-FRM-080/00")
    _hline(c, 771, w=0.8)

    bas = sv("baslangic_tarihi") or "../.../202.."
    bit = sv("bitis_tarihi")     or "../.../202.."
    gun = sv("staj_gun_sayisi")  or "......"
    para = (
        f"İlgili Makama,\n"
        f"Fakültemiz / Yüksekokulumuz öğrencilerinin Güz/Bahar eğitim-öğretim döneminde kuruluş ve "
        f"işletmelerde staj yapma zorunluluğu vardır. Aşağıda bilgileri yer alan öğrencimizin stajını "
        f"{bas} ile {bit} tarihleri arasında {gun} iş günü süreyle kuruluşunuzda yapmasında "
        f"göstereceğiniz ilgiye teşekkür eder, çalışmalarınızda başarılar dileriz."
    )
    c.setFillGray(0)
    yp = 755
    for blk in para.split("\n"):
        yp = _wrap(c, blk, ML, yp, MR - ML - 4, size=8.5, lead=13)
        yp -= 2

    Y_OH = 688; Y_R1 = 671; Y_R2 = 653; Y_R3 = 635; Y_R4 = 617
    _sec(c, Y_OH, "ÖĞRENCİNİN")
    _hline(c, Y_R1 - 4); _vline(c, MID, Y_R1 - 4, Y_OH - 2)
    _lbl(c, ML + 2, Y_R1, "Bölümü/Programı  :")
    _val(c, 165, Y_R1, sv("bolum"))
    _lbl(c, 302, Y_R1, "TC Kimlik No  :")
    _val(c, 400, Y_R1, sv("tc_kimlik_no"))
    _hline(c, Y_R2 - 4)
    _lbl(c, ML + 2, Y_R2, "Adı Soyadı  :")
    _val(c, 120, Y_R2, sv("ad_soyad"))
    _hline(c, Y_R3 - 4); _vline(c, MID, Y_R3 - 4, Y_R2 - 4)
    _lbl(c, ML + 2, Y_R3, "Öğrenci No  :")
    _val(c, 120, Y_R3, sv("ogrenci_no"))
    _lbl(c, 302, Y_R3, "Telefon No  :")
    _val(c, 390, Y_R3, sv("telefon_no"))
    _hline(c, Y_R4 - 4)
    _lbl(c, ML + 2, Y_R4, "İkametgâh Adresi  :")
    _val(c, 162, Y_R4, sv("ikametgah_adresi"))

    Y_SH = 598; Y_S1 = 581; Y_S2 = 563; Y_S3 = 545
    Y_S4 = 527; Y_S5 = 509; Y_S6 = 491
    _sec(c, Y_SH, "STAJ YAPILAN YERİN")
    _hline(c, Y_S1 - 4); _lbl(c, ML + 2, Y_S1, "Adı  :"); _val(c, 84, Y_S1, sv("firma_adi"))
    _hline(c, Y_S2 - 4); _lbl(c, ML + 2, Y_S2, "Adresi  :"); _val(c, 98, Y_S2, sv("firma_adresi"))
    _hline(c, Y_S3 - 4); _vline(c, MID, Y_S3 - 4, Y_S2 - 4)
    _lbl(c, ML + 2, Y_S3, "Hizmet Alanı  :"); _val(c, 128, Y_S3, sv("hizmet_alani"))
    _lbl(c, 302, Y_S3, "Haftalık Çalışılan Gün  :"); _val(c, 460, Y_S3, sv("haftalik_calisilan_gun"))
    _hline(c, Y_S4 - 4); _vline(c, MID, Y_S4 - 4, Y_S3 - 4)
    _lbl(c, ML + 2, Y_S4, "Telefon No  :"); _val(c, 118, Y_S4, sv("firma_telefon"))
    _lbl(c, 302, Y_S4, "Stajın Başlama Tarihi  :"); _val(c, 444, Y_S4, sv("baslangic_tarihi"))
    _hline(c, Y_S5 - 4); _vline(c, MID, Y_S5 - 4, Y_S4 - 4)
    _lbl(c, ML + 2, Y_S5, "E-posta Adresi  :"); _val(c, 148, Y_S5, sv("firma_eposta"))
    _lbl(c, 302, Y_S5, "Stajın Bitiş Tarihi  :"); _val(c, 434, Y_S5, sv("bitis_tarihi"))
    _hline(c, Y_S6 - 4); _vline(c, MID, Y_S6 - 4, Y_S5 - 4)
    _lbl(c, ML + 2, Y_S6, "Web Adresi  :"); _val(c, 118, Y_S6, sv("firma_web"))
    _lbl(c, 302, Y_S6, "Fax No  :"); _val(c, 360, Y_S6, sv("firma_fax"))

    Y_DH = 470; C1 = ML + 2; C2 = ML + 142; C3 = ML + 286
    _hline(c, Y_DH + 14, w=1.2); _hline(c, Y_DH - 2)
    c.setFont(FONT, 8)
    c.drawString(C1, Y_DH + 3, "FİRMADA BULUNAN DEPARTMANLAR")
    c.drawString(C3, Y_DH + 3, "DEPARTMANLARDA BULUNAN PERSONEL SAYISI")
    DROWS = [
        (453, "d_uretim",    "d_insan",   "İNSAN KAYNAKLARI", "p_yonetici", "YÖNETİCİ",  "p_usta",      "USTA"),
        (435, "d_pazarlama", "d_teknik",  "TEKNİK SERVİS",    "p_muhendis", "MÜHENDİS",  "p_teknisyen", "TEKNİSYEN"),
        (417, "d_muh",       "d_buro",    "BÜRO",             "p_tekniker", "TEKNİKER",  "p_isci",      "İŞÇİ"),
        (399, "d_diger1",    "d_diger2",  "...............",  "p_diger1",   "..........", "p_diger2",    ".........."),
    ]
    LABELS1 = ["ÜRETİM", "PAZARLAMA", "MUH./FİN.", ".........."]
    for (y_, k1, k2, l2, k3, l3, k4, l4), l1 in zip(DROWS, LABELS1):
        _hline(c, y_ - 4); _vline(c, C2 - 5, y_ - 4, y_ + 16); _vline(c, C3 - 5, y_ - 4, y_ + 16)
        _chk_full(c, C1, y_ + 1, bool(d.get(k1))); _lbl(c, C1 + 11, y_, l1, 7.5)
        _chk_full(c, C2, y_ + 1, bool(d.get(k2))); _lbl(c, C2 + 11, y_, l2, 7.5)
        _lbl(c, C3, y_, l3, 7); _val(c, C3 + 65, y_, sv(k3), 8)
        _lbl(c, C3 + 128, y_, l4, 7); _val(c, C3 + 192, y_, sv(k4), 8)

    Y_IH = 378; Y_I1 = 361; Y_I2 = 343; IM = ML + 260
    _hline(c, Y_IH + 14, w=1.2); _hline(c, Y_IH - 2)
    c.setFont(FONT, 8)
    c.drawCentredString((ML + IM) / 2, Y_IH + 3, "ÖĞRENCİYE SAĞLANABİLECEK İMKANLAR")
    c.drawCentredString((IM + MR) / 2, Y_IH + 3, "STAJ İÇİN ÖĞRENCİDEN İSTENEN BELGELER")
    _vline(c, IM, Y_I2 - 16, Y_IH - 2)
    _hline(c, Y_I1 - 4)
    _chk_full(c, ML + 2,  Y_I1 + 1, bool(d.get("ucret")));         _lbl(c, ML + 13,  Y_I1, "Ücret",             7.5)
    _chk_full(c, ML + 60, Y_I1 + 1, bool(d.get("yemek")));         _lbl(c, ML + 71,  Y_I1, "Yemek",             7.5)
    _chk_full(c, IM + 8,  Y_I1 + 1, bool(d.get("fotograf")));      _lbl(c, IM + 20,  Y_I1, "Fotoğraf",          7.5)
    _chk_full(c, IM + 78, Y_I1 + 1, bool(d.get("nufus_cuzdani"))); _lbl(c, IM + 90,  Y_I1, "Nüfus Cüzdan Sur.", 7.5)
    _hline(c, Y_I2 - 4)
    _chk_full(c, ML + 2,  Y_I2 + 1, bool(d.get("servis")));          _lbl(c, ML + 13, Y_I2, "Servis",           7.5)
    _chk_full(c, IM + 8,  Y_I2 + 1, bool(d.get("savcilik_belgesi"))); _lbl(c, IM + 20, Y_I2, "Savcılık Belgesi", 7.5)
    c.setFont(FONT, 7); c.drawString(ML, 320, "KYT-FRM-080/00")


def _p2_full(c, d):
    """Sayfa 2 – şablon yokken sıfırdan üretme (fallback)."""
    sv = lambda k: str(d.get(k) or "")
    c.setLineWidth(0.8); c.setStrokeGray(0.3)
    c.rect(ML, 105, MR - ML, 700, fill=0); c.setStrokeGray(0)
    c.setFont(FONT, 12); c.drawCentredString(W / 2, 800, "AMASYA ÜNİVERSİTESİ")
    c.setFont(FONT, 10); c.drawCentredString(W / 2, 785, "ZORUNLU STAJ BAŞVURU BİLGİ FORMU")
    c.setFont(FONT, 7);  c.drawRightString(MR, 773, "KYT-FRM-80/00")
    _hline(c, 769, w=0.8)
    _sec(c, 745, "İŞVEREN VEYA YETKİLİNİN")
    _hline(c, 725); _vline(c, MID, 725, 743)
    _lbl(c, ML + 2, 729, "Adı Soyadı  :")
    _val(c, 118, 729, sv("isveren_ad_soyad"))
    _lbl(c, MID + 5, 729, "İmza ve Resmi Kaşe")
    _hline(c, 707)
    _lbl(c, ML + 2, 711, "Görev ve Unvanı  :")
    _val(c, 132, 711, sv("isveren_unvan"))

    beyan = (
        "Beyanımın doğruluğunu, durumumda değişiklik olması durumunda değişikliği hemen "
        "bildireceğimi kabul eder, beyanımın hatalı veya eksik olmasından kaynaklanacak prim, "
        "idari para cezası, gecikme zammı ve gecikme faizinin tarafımca ödeneceğini taahhüt ederim."
    )
    _wrap(c, beyan, ML, 680, MR - ML - 4, size=8.5, lead=13)
    c.setFont(FONT, 8)
    c.drawRightString(MR, 620, "…./ ….. /20…..")
    c.drawRightString(MR, 607, "Öğrencinin İmzası")
    _hline(c, 588)
    _wrap(c, "Yukarıda belirtilen öğrencinin adı geçen firmada stajını yapması bölümümüzce uygun görülmüştür.",
          ML, 569, MR - ML - 4, size=8.5, lead=13)
    c.setFont(FONT, 8)
    c.drawCentredString(W / 2, 532, "…/…/20…..")
    c.drawCentredString(W / 2, 519, "Bölüm Başkanı")
    _hline(c, 494)
    c.setFont(FONT, 9); c.drawString(ML, 480, "ÖNEMLİ NOT:")
    notlar = [
        "Öğrencilerin Staj Dönemleri Süresince tabi olacakları iş kazası ve meslek hastalıkları sigorta primi üniversitemiz tarafından karşılanacaktır.",
        "Öğrencinin, Zorunlu Staj Başvuru Formunu, staj takvimine uyulacak şekilde ilgili birime teslim etmesi zorunludur. Teslim edilecek form 2 asıl nüsha olarak (fotokopi değil) hazırlanır.",
        "Bu formu, staj yapılacak iş yerine ve program staj yetkilisine onaylattıktan sonra, ilgili birime süresinde teslim etmeyen öğrenci staj yapamayacaktır.",
        "Stajla ilişiği kesilen ya da stajı bırakan öğrenci ile ilgili bilginin en geç 5 (beş) iş günü içinde öğrenci / iş yeri tarafından ilgili birime bildirilmesi gerekmektedir.",
    ]
    yn = 462
    for note in notlar:
        c.setFont(FONT, 8); c.drawString(ML + 4, yn, "•")
        yn = _wrap(c, note, ML + 14, yn, MR - ML - 18, size=8, lead=11)
        yn -= 6
    c.setFont(FONT, 7); c.drawString(ML, 113, "KYT-FRM-80/00")


# ── ANA FONKSİYON ─────────────────────────────────────────────────────────────
def fill_staj_pdf(form_data: Dict[str, Any], output_path: str,
                  template_path: str | None = None) -> None:
    """
    form_data → 2 sayfalık A4 staj formu PDF.
    Önce şablon üzerine overlay dener; şablon yoksa sıfırdan üretir.
    """
    # Şablon yolu belirleme
    if template_path is None:
        template_path = str(Path(__file__).resolve().parent.parent / _TEMPLATE_NAME)

    template_exists = Path(template_path).exists()

    if template_exists:
        # ── Overlay yaklaşımı ────────────────────────────────────────────────
        try:
            template_pdf = PdfReader(template_path)
            # Şablonun gerçek sayfa boyutunu oku (A4'ten farklı olabilir)
            mb = template_pdf.pages[0].mediabox
            t_w, t_h = float(mb.width), float(mb.height)

            buf = io.BytesIO()
            c = rl_canvas.Canvas(buf, pagesize=(t_w, t_h))
            _p1_overlay(c, form_data)
            c.showPage()
            _p2_overlay(c, form_data)
            c.showPage()
            c.save()
            buf.seek(0)

            overlay_pdf = PdfReader(buf)
            writer = PdfWriter()

            for i, tpage in enumerate(template_pdf.pages):
                if i < len(overlay_pdf.pages):
                    tpage.merge_page(overlay_pdf.pages[i])
                writer.add_page(tpage)

            with open(output_path, "wb") as f:
                writer.write(f)
            return
        except Exception as e:
            print(f"[PDF Overlay] Şablon merge başarısız ({e}), fallback kullanılıyor.")

    # ── Fallback: sıfırdan üretme ────────────────────────────────────────────
    c = rl_canvas.Canvas(output_path, pagesize=A4)
    c.setTitle("Amasya Üniversitesi – Staj Başvuru Formu")
    _p1_full(c, form_data)
    c.showPage()
    _p2_full(c, form_data)
    c.showPage()
    c.save()


def extract_pdf_text(pdf_path: str) -> str:
    try:
        reader = PdfReader(pdf_path)
        return "\n".join(p.extract_text() or "" for p in reader.pages)
    except Exception as e:
        print(f"[PDF Extract] {e}")
        return ""
