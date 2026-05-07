# -*- coding: utf-8 -*-
import requests, json, sys, os
from pathlib import Path

os.chdir(Path(__file__).parent)
BASE = 'http://127.0.0.1:5000'

def ok(step, status, extra=""):
    print(f"[{step}] HTTP {status} {extra}")

# ── 1. Ogrenci girisi ────────────────────────────────────────────────────────
s_ogr = requests.Session()
r = s_ogr.post(f'{BASE}/login',
               data={'username':'ogrenci','password':'ogrenci123'},
               allow_redirects=True)
ok(1, r.status_code, "ogrenci girisi -> " + r.url)

# ── 2. Test PDF olustur ──────────────────────────────────────────────────────
from services.pdf_service import fill_staj_pdf
test_data = {
    'ad_soyad': 'Ahmet Yilmaz', 'ogrenci_no': '2021001',
    'bolum': 'Bilgisayar Programciligi',
    'tc_kimlik_no': '12345678901', 'donem': '2025-2026 Yaz',
    'telefon_no': '05001234567',
    'ikametgah_adresi': 'Test Mah. No:1 Amasya',
    'firma_adi': 'Test Yazilim A.S.',
    'firma_adresi': 'Organize San. Bolgesi Amasya',
    'hizmet_alani': 'Yazilim Gelistirme',
    'haftalik_calisilan_gun': '5',
    'firma_telefon': '03581234567', 'firma_eposta': 'info@test.com',
    'firma_web': 'www.test.com', 'firma_fax': '',
    'baslangic_tarihi': '2025-07-01', 'bitis_tarihi': '2025-08-29',
    'staj_gun_sayisi': '40',
    'departman_1': 'Yazilim', 'departman_2': '', 'departman_3': '', 'departman_4': '',
    'personel_yonetici': '2', 'personel_muhendis': '5', 'personel_tekniker': '3',
    'personel_usta': '0', 'personel_teknisyen': '1', 'personel_isci': '10',
}
pdf_path = Path('test_upload.pdf')
fill_staj_pdf(test_data, str(pdf_path))
print(f"[2] Test PDF olusturuldu: {pdf_path.stat().st_size} bytes")

# ── 3. PDF yukle ─────────────────────────────────────────────────────────────
with open(pdf_path, 'rb') as f:
    r3 = s_ogr.post(f'{BASE}/api/yukle',
                    files={'pdf': (pdf_path.name, f, 'application/pdf')})
d3 = r3.json()
ok(3, r3.status_code, "yukle -> " + json.dumps(d3, ensure_ascii=False)[:200])

sub_id = d3.get('id')
ai_karar = d3.get('karar') or d3.get('ai_karar', '')
print(f"   Basvuru ID: {sub_id}  |  AI Karar: {ai_karar}")

if not sub_id:
    print("HATA: ID alinamadi, duruyor.")
    sys.exit(1)

# ── 4. BB girisi ─────────────────────────────────────────────────────────────
s_bb = requests.Session()
r = s_bb.post(f'{BASE}/login',
              data={'username':'bolum_baskani','password':'bb2025'},
              allow_redirects=True)
ok(4, r.status_code, "BB girisi -> " + r.url)

# ── 5. BB bekleyenler ────────────────────────────────────────────────────────
r5 = s_bb.get(f'{BASE}/api/bb/bekleyenler')
d5 = r5.json()
ok(5, r5.status_code, f"BB bekleyenler: {len(d5)} kayit")
print(f"   Bekleyenler: {[x['id'] for x in d5]}")

# ── 6. BB onayla ─────────────────────────────────────────────────────────────
r6 = s_bb.post(f'{BASE}/api/bb/onayla',
               json={'id': sub_id, 'ad': 'Prof. Dr. Ali Veli'},
               headers={'Content-Type': 'application/json'})
d6 = r6.json()
ok(6, r6.status_code, "BB onayla -> " + json.dumps(d6, ensure_ascii=False)[:200])

# ── 7. Ogrenci: sekretere ilet ───────────────────────────────────────────────
r7 = s_ogr.post(f'{BASE}/api/sekreter-ilet/{sub_id}')
d7 = r7.json()
ok(7, r7.status_code, "Sekretere ilet -> " + json.dumps(d7, ensure_ascii=False)[:200])

# ── 8. Sekreter girisi ───────────────────────────────────────────────────────
s_sek = requests.Session()
r = s_sek.post(f'{BASE}/login',
               data={'username':'sekreter','password':'sekreter123'},
               allow_redirects=True)
ok(8, r.status_code, "Sekreter girisi -> " + r.url)

# ── 9. Basvurulari listele ───────────────────────────────────────────────────
r9 = s_sek.get(f'{BASE}/api/basvurular')
d9 = r9.json()
ok(9, r9.status_code, f"Sekreter basvurular: {len(d9)} kayit")
print(f"   Kayitlar: {[(x['id'], x['durum']) for x in d9]}")

# ── 10. Sekreter onayla (AI + e-imza kontrollu) ──────────────────────────────
r10 = s_sek.post(f'{BASE}/api/karar',
                 json={'id': sub_id, 'karar': 'KABUL'},
                 headers={'Content-Type': 'application/json'})
d10 = r10.json()
ok(10, r10.status_code, "Sekreter onayla (AI kontrollu)")
print(f"   onaylandi: {d10.get('onaylandi')}")
k = d10.get('kontroller', {})
for ad, c in k.items():
    icon = 'OK' if c.get('ok') else 'FAIL'
    print(f"   [{icon}] {ad}: {c.get('mesaj','')}")
    if c.get('uyarilar'):
        for u in c['uyarilar']:
            print(f"         Uyari: {u}")

# Sonuc
import sqlite3
conn = sqlite3.connect('staj.db')
row = conn.execute("SELECT durum, bb_durum, bb_ad, bb_tarih FROM submissions WHERE id=?", (sub_id,)).fetchone()
conn.close()
print(f"\n=== SONUC === id={sub_id}")
print(f"  durum    : {row[0]}")
print(f"  bb_durum : {row[1]}")
print(f"  bb_ad    : {row[2]}")
print(f"  bb_tarih : {row[3]}")
