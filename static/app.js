/* ── SAYFA YÜKLENDİĞİNDE ─────────────────────────────────────────────────── */
loadDonem();
loadKurallar();
if (document.getElementById('tab-sekreter')?.classList.contains('active')) {
  loadBasvurular();
}

/* ── COLLAPSIBLE ─────────────────────────────────────────────────────────── */
function toggleSection(head) {
  const body = head.nextElementSibling;
  const open = body.style.display !== 'none';
  body.style.display = open ? 'none' : 'grid';
  head.classList.toggle('open', !open);
}

/* ── FORM FIELDS → OBJECT ─────────────────────────────────────────────────── */
const FIELDS = [
  'ad_soyad','ogrenci_no','bolum','tc_kimlik_no','donem','telefon_no',
  'ikametgah_adresi','firma_adi','firma_adresi','hizmet_alani',
  'haftalik_calisilan_gun','firma_telefon','firma_eposta','firma_web',
  'firma_fax','baslangic_tarihi','bitis_tarihi','staj_gun_sayisi',
  'departman_1','departman_2','departman_3','departman_4',
  'personel_yonetici','personel_muhendis','personel_tekniker',
  'personel_usta','personel_teknisyen','personel_isci',
];

function getFormData() {
  const d = {};
  FIELDS.forEach(id => {
    const el = document.getElementById(id);
    if (el) d[id] = el.value;
  });
  return d;
}

/* ── STAJ DÖNEMİ ──────────────────────────────────────────────────────────── */
let _donem = {};

async function loadDonem() {
  try {
    const res = await fetch('/api/staj-donem');
    _donem    = await res.json();
    const set = (id, val) => { const el = document.getElementById(id); if (el) el.value = val || ''; };

    // Öğrenci banneri
    const banner = document.getElementById('donem-banner');
    if (banner) {
      const yaz = _donem.yaz_staj_baslangic
        ? `☀️ <strong>${_donem.yaz_donem_adi}</strong>: ${_donem.yaz_staj_baslangic} – ${_donem.yaz_staj_bitis} &nbsp;(Son: ${_donem.yaz_basvuru_son_gun || '—'}, Min: ${_donem.yaz_min_staj_gun} gün)`
        : '';
      const ara = _donem.ara_staj_baslangic
        ? `&nbsp;&nbsp;|&nbsp;&nbsp; ❄️ <strong>${_donem.ara_donem_adi}</strong>: ${_donem.ara_staj_baslangic} – ${_donem.ara_staj_bitis} &nbsp;(Son: ${_donem.ara_basvuru_son_gun || '—'}, Min: ${_donem.ara_min_staj_gun} gün)`
        : '';
      if (yaz || ara) { banner.style.display = 'block'; banner.innerHTML = `📅 ${yaz}${ara}`; }
    }

    // Sekreter dönem display
    const disp = document.getElementById('donem-display');
    if (disp) {
      disp.innerHTML =
        `<div class="sd-period-row">` +
          `<span class="sd-tag sd-yaz">☀️ ${_donem.yaz_donem_adi || '—'}</span>` +
          `<span class="sd-info">${_donem.yaz_staj_baslangic} – ${_donem.yaz_staj_bitis}</span>` +
          `<span class="sd-info">Son: ${_donem.yaz_basvuru_son_gun || '—'}</span>` +
          `<span class="sd-info">Min: ${_donem.yaz_min_staj_gun} gün</span>` +
        `</div>` +
        `<div class="sd-period-row" style="margin-top:6px">` +
          `<span class="sd-tag sd-ara">❄️ ${_donem.ara_donem_adi || '—'}</span>` +
          `<span class="sd-info">${_donem.ara_staj_baslangic} – ${_donem.ara_staj_bitis}</span>` +
          `<span class="sd-info">Son: ${_donem.ara_basvuru_son_gun || '—'}</span>` +
          `<span class="sd-info">Min: ${_donem.ara_min_staj_gun} gün</span>` +
        `</div>`;
    }

    set('sd-yaz-adi', _donem.yaz_donem_adi);
    set('sd-yaz-bas', _donem.yaz_staj_baslangic);
    set('sd-yaz-bit', _donem.yaz_staj_bitis);
    set('sd-yaz-son', _donem.yaz_basvuru_son_gun);
    set('sd-yaz-min', _donem.yaz_min_staj_gun);
    set('sd-ara-adi', _donem.ara_donem_adi);
    set('sd-ara-bas', _donem.ara_staj_baslangic);
    set('sd-ara-bit', _donem.ara_staj_bitis);
    set('sd-ara-son', _donem.ara_basvuru_son_gun);
    set('sd-ara-min', _donem.ara_min_staj_gun);
  } catch { /* sessiz hata */ }
}

function toggleDonemEdit() {
  const form = document.getElementById('donem-form');
  const disp = document.getElementById('donem-display');
  const show = form.style.display === 'none';
  form.style.display = show ? 'block' : 'none';
  disp.style.display = show ? 'none' : 'block';
}

async function saveDonem() {
  const get = id => document.getElementById(id)?.value || '';
  const payload = {
    yaz_donem_adi:       get('sd-yaz-adi'),
    yaz_staj_baslangic:  get('sd-yaz-bas'),
    yaz_staj_bitis:      get('sd-yaz-bit'),
    yaz_basvuru_son_gun: get('sd-yaz-son'),
    yaz_min_staj_gun:    get('sd-yaz-min'),
    ara_donem_adi:       get('sd-ara-adi'),
    ara_staj_baslangic:  get('sd-ara-bas'),
    ara_staj_bitis:      get('sd-ara-bit'),
    ara_basvuru_son_gun: get('sd-ara-son'),
    ara_min_staj_gun:    get('sd-ara-min'),
  };
  try {
    const res  = await fetch('/api/staj-donem', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (data.ok) { showToast('✅ Dönem bilgileri kaydedildi!'); toggleDonemEdit(); loadDonem(); }
  } catch (e) { showToast('❌ Kayıt hatası: ' + e.message); }
}

/* ── TARİH HESAP KUTUSU ───────────────────────────────────────────────────── */
function hesaplaTarih() {
  const box = document.getElementById('tarih-hesap');
  const bas = document.getElementById('baslangic_tarihi')?.value;
  const bit = document.getElementById('bitis_tarihi')?.value;
  if (!box) return;
  if (!bas || !bit) { box.style.display = 'none'; return; }
  const diff = Math.round((new Date(bit) - new Date(bas)) / 86400000);
  if (diff <= 0) { box.style.display = 'none'; return; }
  const isgunu = Math.round(diff * 5 / 7);
  const gun    = document.getElementById('staj_gun_sayisi');
  if (gun && !gun.value) gun.value = isgunu;
  const uyari = gun && gun.value && parseInt(gun.value) > isgunu + 5
    ? `<span style="color:#dc2626"> ⚠️ Girilen gün (${gun.value}) aralıktan fazla!</span>` : '';
  box.style.display = 'block';
  box.innerHTML = `📅 <strong>${bas}</strong> → <strong>${bit}</strong> &nbsp;=&nbsp; <strong>${diff}</strong> takvim günü &nbsp;|&nbsp; yaklaşık <strong>${isgunu}</strong> iş günü${uyari}`;
}

['baslangic_tarihi','bitis_tarihi','staj_gun_sayisi'].forEach(id => {
  const el = document.getElementById(id);
  if (el) { el.addEventListener('change', hesaplaTarih); el.addEventListener('input', hesaplaTarih); }
});

/* ── LIVE VALIDATE ────────────────────────────────────────────────────────── */
let validateTimer = null;

FIELDS.forEach(id => {
  const el = document.getElementById(id);
  if (el) el.addEventListener('input', () => {
    clearTimeout(validateTimer);
    validateTimer = setTimeout(runValidate, 400);
  });
});

async function runValidate() {
  const box = document.getElementById('feedback-box');
  try {
    const res = await fetch('/api/validate', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(getFormData()),
    });
    const { msgs } = await res.json();
    box.innerHTML = msgs.map(m => {
      const icons = { ok:'✅', warn:'⚠️', err:'❌', info:'ℹ️' };
      return `<div class="fb-item ${m.t}">${icons[m.t]||'•'} ${m.m}</div>`;
    }).join('');
  } catch {
    box.innerHTML = '<div class="fb-item info">ℹ️ Sunucuya ulaşılamıyor.</div>';
  }
}

/* ── KURALLAR ─────────────────────────────────────────────────────────────── */
async function loadKurallar() {
  const list = document.getElementById('kurallar-list');
  if (!list) return;
  try {
    const res  = await fetch('/api/kurallar');
    const data = await res.json();
    if (data.kurallar && data.kurallar.length) {
      list.innerHTML = data.kurallar.map(k => `<div class="rule-item">${k}</div>`).join('');
    } else {
      list.innerHTML = '<div class="fb-item info">ℹ️ Yönerge bulunamadı.</div>';
    }
  } catch {
    list.innerHTML = '<div class="fb-item warn">⚠️ Kurallar yüklenemedi.</div>';
  }
}

/* ── PDF OLUŞTUR ──────────────────────────────────────────────────────────── */
async function generatePDF() {
  const btn = document.getElementById('btn-pdf');
  btn.innerHTML = '<span class="spin">⏳</span> Oluşturuluyor…';
  btn.disabled = true;
  try {
    const res = await fetch('/api/pdf', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(getFormData()),
    });
    if (!res.ok) { showToast('❌ PDF oluşturulamadı.'); return; }
    const blob = await res.blob();
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href = url; a.download = 'staj_basvuru.pdf'; a.click();
    URL.revokeObjectURL(url);
    showToast('✅ PDF indirildi!');
  } catch (e) {
    showToast('❌ Hata: ' + e.message);
  } finally {
    btn.innerHTML = '<span>📥</span> PDF Oluştur & İndir';
    btn.disabled = false;
  }
}

/* ── PDF UPLOAD ───────────────────────────────────────────────────────────── */
const fileInput  = document.getElementById('pdf-file');
const btnGonder  = document.getElementById('btn-gonder');
const fileNameEl = document.getElementById('file-name');

if (fileInput) fileInput.addEventListener('change', () => {
  const f = fileInput.files[0];
  if (f) { fileNameEl.textContent = f.name; btnGonder.disabled = false; }
});

async function gonderPDF() {
  const file = fileInput.files[0];
  if (!file) return;
  btnGonder.innerHTML = '<span class="spin">⏳</span> Analiz ediliyor…';
  btnGonder.disabled = true;
  const fd = new FormData();
  fd.append('pdf', file);
  fd.append('form_data', JSON.stringify(getFormData()));
  const resultBox = document.getElementById('yukle-result');
  resultBox.style.display = 'none';
  try {
    const res  = await fetch('/api/yukle', { method: 'POST', body: fd });
    const data = await res.json();

    // PDF'den çıkarılan alanları boş form alanlarına doldur
    if (data.form_data) {
      FIELDS.forEach(id => {
        const el = document.getElementById(id);
        if (el && !el.value && data.form_data[id]) el.value = data.form_data[id];
      });
      hesaplaTarih();
      runValidate();
    }

    resultBox.style.display = 'block';
    const isKabul = data.karar === 'KABUL';
    resultBox.className = 'yukle-result ' + (isKabul ? 'kabul' : 'red');
    const eksikler = (data.eksikler || []).map(e =>
      typeof e === 'string' ? e : (e.alan || e.label || e.key || JSON.stringify(e))
    );
    const eksikHtml = eksikler.length ? `<br><strong>Eksik Alanlar:</strong> ${eksikler.join(', ')}` : '';
    const t = data.tarihler || {};
    const tarihHtml = (t.baslangic || t.bitis)
      ? `<br><span style="font-size:0.85em;opacity:.8">📅 ${t.baslangic||'?'} → ${t.bitis||'?'}${t.staj_gun ? ` | ${t.staj_gun} gün` : ''}</span>`
      : '';
    resultBox.innerHTML =
      `<strong>${isKabul ? '✅ KABUL' : '❌ RED'}</strong> — Başvuru ID: #${data.id}<br>` +
      `${data.mesaj}${eksikHtml}${tarihHtml}`;
    showToast(isKabul ? '✅ Başvuru kabul edildi!' : '❌ Başvuru reddedildi.');
  } catch (e) {
    resultBox.style.display = 'block';
    resultBox.className = 'yukle-result red';
    resultBox.innerHTML = '❌ Sunucu hatası: ' + e.message;
  } finally {
    btnGonder.innerHTML = '<span>🚀</span> Sekretere Gönder';
    btnGonder.disabled = false;
  }
}

/* ── CHAT ─────────────────────────────────────────────────────────────────── */
const chatMessages = document.getElementById('chat-messages');
const chatInput    = document.getElementById('chat-input');
const chatSend     = document.getElementById('chat-send');
let _chatHistory   = [];

function mdToHtml(text) {
  return text
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/^#{1,3}\s+(.+)$/gm, '<b>$1</b>')
    .replace(/^- (.+)$/gm, '• $1')
    .replace(/\n/g, '<br>');
}

function appendMsg(text, role, isHtml = false) {
  const div = document.createElement('div');
  div.className = `chat-msg ${role}`;
  if (isHtml) div.innerHTML = text; else div.textContent = text;
  chatMessages.appendChild(div);
  chatMessages.scrollTop = chatMessages.scrollHeight;
  return div;
}

const HIZLI_SORULAR = [
  'Staj ne zaman başlıyor?',
  'Minimum staj süresi kaç gün?',
  'Başvuru için hangi belgeler gerekli?',
  'Staj yeri nasıl onaylatılır?',
  'Devamsızlık sınırı nedir?',
];

function renderChips() {
  const chips = document.getElementById('chat-chips');
  if (!chips) return;
  chips.innerHTML = HIZLI_SORULAR.map(q =>
    `<button class="chat-chip" onclick="askChip(this,'${q}')">${q}</button>`
  ).join('');
}

function askChip(btn, soru) {
  btn.closest('#chat-chips').style.display = 'none';
  chatInput.value = soru;
  sendChat();
}

async function sendChat() {
  const soru = chatInput.value.trim();
  if (!soru) return;
  chatInput.value = '';
  const chips = document.getElementById('chat-chips');
  if (chips) chips.style.display = 'none';
  appendMsg(soru, 'user');
  _chatHistory.push({ role: 'user', content: soru });
  const typing = appendMsg('⏳ Yanıt yazılıyor…', 'bot typing');
  chatSend.disabled = true;
  try {
    const res  = await fetch('/api/chat', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ soru, gecmis: _chatHistory.slice(0,-1) }),
    });
    const data = await res.json();
    typing.innerHTML = mdToHtml(data.yanit);
    typing.classList.remove('typing');
    _chatHistory.push({ role: 'assistant', content: data.yanit });
    if (_chatHistory.length > 20) _chatHistory = _chatHistory.slice(-20);
  } catch {
    typing.textContent = '❌ Bağlantı hatası.';
  } finally {
    chatSend.disabled = false;
  }
}

function clearChat() {
  _chatHistory = [];
  chatMessages.innerHTML = '';
  renderChips();
  const chips = document.getElementById('chat-chips');
  if (chips) chips.style.display = 'flex';
}

if (chatSend) chatSend.addEventListener('click', sendChat);
if (chatInput) chatInput.addEventListener('keydown', e => { if (e.key === 'Enter') sendChat(); });
renderChips();

/* ── SEKRETER ─────────────────────────────────────────────────────────────── */
let _allRows = [];
let _activeFilter = 'hepsi';

async function loadBasvurular() {
  const list = document.getElementById('basvuru-list');
  if (!list) return;
  list.innerHTML = '<div class="empty-state">⏳ Yükleniyor…</div>';
  try {
    const res  = await fetch('/api/basvurular');
    _allRows   = await res.json();
    const t  = _allRows.length;
    const k  = _allRows.filter(r => r.ai_karar === 'KABUL').length;
    const rd = _allRows.filter(r => r.ai_karar === 'RED').length;
    const b  = _allRows.filter(r => r.durum === 'beklemede').length;
    document.getElementById('m-toplam').textContent = t;
    document.getElementById('m-kabul').textContent  = k;
    document.getElementById('m-red').textContent    = rd;
    document.getElementById('m-bekle').textContent  = b;
    renderList(_allRows);
  } catch (e) {
    list.innerHTML = `<div class="empty-state">❌ Hata: ${e.message}</div>`;
  }
}

function renderList(rows) {
  const list = document.getElementById('basvuru-list');
  if (!rows.length) { list.innerHTML = '<div class="empty-state">📭 Başvuru yok.</div>'; return; }
  list.innerHTML = rows.map(r => {
    const karar    = r.ai_karar || '—';
    const badgeCls = karar === 'KABUL' ? 'kabul' : karar === 'RED' ? 'red' : 'bekle';
    const cardCls  = karar === 'KABUL' ? 'kabul-card' : karar === 'RED' ? 'red-card' : 'bekle-card';
    const icon     = karar === 'KABUL' ? '✅' : karar === 'RED' ? '❌' : '⏳';
    let ext = {}; try { ext = JSON.parse(r.extracted_json || '{}'); } catch {}
    let eks = []; try { eks = JSON.parse(r.missing_json || '[]'); } catch {}
    const infoHtml = ['ad_soyad','ogrenci_no','bolum','firma_adi','baslangic_tarihi','bitis_tarihi','staj_gun_sayisi']
      .filter(k => ext[k]).map(k => `<div class="info-row"><strong>${k}:</strong> ${ext[k]}</div>`).join('');
    const eksikHtml = eks.length ? `<div class="eksik-list">⚠️ Eksik: ${eks.join(', ')}</div>` : '';
    const raporHtml = r.ai_rapor
      ? `<span class="rapor-toggle" onclick="toggleRapor(${r.id})">📄 AI Raporu</span><div id="rapor-${r.id}" class="rapor-text">${r.ai_rapor}</div>` : '';
    return `
    <div class="basvuru-card ${cardCls}" id="card-${r.id}">
      <div class="basvuru-head" onclick="toggleCard(${r.id})">
        <div>
          <div class="basvuru-title">${icon} #${r.id} — ${r.original_adi || '—'}</div>
          <div class="basvuru-meta">${r.yukleme_tarihi||''} · ${ext.firma_adi||''}</div>
        </div>
        <span class="badge ${badgeCls}">${karar}</span>
      </div>
      <div class="basvuru-body" id="body-${r.id}">
        <p style="font-size:.88rem;margin-bottom:12px;">${r.ai_mesaj||'—'}</p>
        ${eksikHtml}
        <div class="basvuru-info">${infoHtml}</div>
        ${raporHtml}
        <div class="basvuru-actions" style="margin-top:14px;">
          <button class="btn btn-success btn-sm" onclick="manuelKarar(${r.id},'KABUL')">✅ Onayla</button>
          <button class="btn btn-danger  btn-sm" onclick="manuelKarar(${r.id},'RED')">❌ Reddet</button>
        </div>
      </div>
    </div>`;
  }).join('');
}

function setFilter(btn, filter) {
  _activeFilter = filter;
  document.querySelectorAll('.sek-filter-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  filterBasvurular();
}

function filterBasvurular() {
  const q = (document.getElementById('sek-search')?.value || '').toLowerCase();
  let rows = _allRows;
  if (_activeFilter !== 'hepsi') {
    rows = rows.filter(r =>
      _activeFilter === 'beklemede' ? r.durum === 'beklemede' : r.ai_karar === _activeFilter
    );
  }
  if (q) {
    rows = rows.filter(r => {
      let ext = {}; try { ext = JSON.parse(r.extracted_json || '{}'); } catch {}
      return (r.original_adi||'').toLowerCase().includes(q)
          || (ext.ad_soyad||'').toLowerCase().includes(q)
          || (ext.ogrenci_no||'').toLowerCase().includes(q)
          || (ext.firma_adi||'').toLowerCase().includes(q);
    });
  }
  renderList(rows);
}

function toggleCard(id) {
  document.getElementById('body-' + id)?.classList.toggle('open');
}

function toggleRapor(id) {
  const el = document.getElementById('rapor-' + id);
  if (el) el.style.display = el.style.display === 'block' ? 'none' : 'block';
}

async function manuelKarar(id, karar) {
  try {
    await fetch('/api/karar', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id, karar }),
    });
    showToast(karar === 'KABUL' ? '✅ Onaylandı!' : '❌ Reddedildi.');
    loadBasvurular();
  } catch (e) { showToast('❌ Hata: ' + e.message); }
}

function exportCSV() {
  if (!_allRows.length) { showToast('⚠️ Dışa aktarılacak veri yok.'); return; }
  const headers = ['id','original_adi','yukleme_tarihi','durum','ai_karar','ai_guven',
                   'ad_soyad','ogrenci_no','bolum','firma_adi','baslangic_tarihi','bitis_tarihi','staj_gun_sayisi'];
  const rows = _allRows.map(r => {
    let ext = {}; try { ext = JSON.parse(r.extracted_json || '{}'); } catch {}
    return headers.map(h => {
      const v = ext[h] !== undefined ? ext[h] : (r[h] || '');
      return `"${String(v).replace(/"/g,'""')}"`;
    }).join(',');
  });
  const csv  = [headers.join(','), ...rows].join('\n');
  const blob = new Blob(['\ufeff'+csv], { type: 'text/csv;charset=utf-8;' });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a'); a.href = url;
  a.download = `basvurular_${new Date().toISOString().slice(0,10)}.csv`;
  a.click(); URL.revokeObjectURL(url);
  showToast('✅ CSV indirildi!');
}

/* ── TOAST ────────────────────────────────────────────────────────────────── */
let toastTimer = null;
function showToast(msg) {
  const el = document.getElementById('toast');
  el.textContent = msg; el.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('show'), 3200);
}
