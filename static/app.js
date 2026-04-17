/* ── TABS ─────────────────────────────────────────────────────────────────── */
document.querySelectorAll('.tab').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.panel').forEach(p => p.style.display = 'none');
    btn.classList.add('active');
    const id = 'tab-' + btn.dataset.tab;
    document.getElementById(id).style.display = 'block';
    if (btn.dataset.tab === 'sekreter') loadBasvurular();
  });
});

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
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
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
  try {
    const res  = await fetch('/api/kurallar');
    const data = await res.json();
    if (data.kurallar && data.kurallar.length) {
      list.innerHTML = data.kurallar.map(k =>
        `<div class="rule-item">${k}</div>`
      ).join('');
    } else {
      list.innerHTML = '<div class="fb-item info">ℹ️ Yönerge bulunamadı.</div>';
    }
  } catch {
    list.innerHTML = '<div class="fb-item warn">⚠️ Kurallar yüklenemedi.</div>';
  }
}

loadKurallar();

/* ── PDF OLUŞTUR ──────────────────────────────────────────────────────────── */
async function generatePDF() {
  const btn = document.getElementById('btn-pdf');
  btn.innerHTML = '<span class="spin">⏳</span> Oluşturuluyor…';
  btn.disabled = true;
  try {
    const res = await fetch('/api/pdf', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(getFormData()),
    });
    if (!res.ok) { showToast('❌ PDF oluşturulamadı.'); return; }
    const blob = await res.blob();
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href     = url;
    a.download = 'staj_basvuru.pdf';
    a.click();
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
const fileInput = document.getElementById('pdf-file');
const btnGonder = document.getElementById('btn-gonder');
const fileNameEl = document.getElementById('file-name');

fileInput.addEventListener('change', () => {
  const f = fileInput.files[0];
  if (f) {
    fileNameEl.textContent = f.name;
    btnGonder.disabled = false;
  }
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

    resultBox.style.display = 'block';
    const isKabul = data.karar === 'KABUL';
    resultBox.className = 'yukle-result ' + (isKabul ? 'kabul' : 'red');

    const eksikHtml = data.eksikler && data.eksikler.length
      ? `<br><strong>Eksik Alanlar:</strong> ${data.eksikler.join(', ')}`
      : '';

    resultBox.innerHTML =
      `<strong>${isKabul ? '✅ KABUL' : '❌ RED'}</strong> — Başvuru ID: #${data.id}<br>` +
      `${data.mesaj}${eksikHtml}`;

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

function appendMsg(text, role) {
  const div = document.createElement('div');
  div.className = `chat-msg ${role}`;
  div.textContent = text;
  chatMessages.appendChild(div);
  chatMessages.scrollTop = chatMessages.scrollHeight;
  return div;
}

async function sendChat() {
  const soru = chatInput.value.trim();
  if (!soru) return;
  chatInput.value = '';
  appendMsg(soru, 'user');

  const typing = appendMsg('⏳ Yanıt yazılıyor…', 'bot typing');
  chatSend.disabled = true;

  try {
    const res  = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ soru }),
    });
    const data = await res.json();
    typing.textContent = data.yanit;
    typing.classList.remove('typing');
  } catch {
    typing.textContent = '❌ Bağlantı hatası.';
  } finally {
    chatSend.disabled = false;
  }
}

chatSend.addEventListener('click', sendChat);
chatInput.addEventListener('keydown', e => { if (e.key === 'Enter') sendChat(); });

/* ── SEKRETER ─────────────────────────────────────────────────────────────── */
async function loadBasvurular() {
  const list = document.getElementById('basvuru-list');
  list.innerHTML = '<div class="empty-state">Yükleniyor…</div>';

  try {
    const res  = await fetch('/api/basvurular');
    const rows = await res.json();

    const t = rows.length;
    const k = rows.filter(r => r.ai_karar === 'KABUL').length;
    const rd = rows.filter(r => r.ai_karar === 'RED').length;
    const b = rows.filter(r => r.durum === 'beklemede').length;

    document.getElementById('m-toplam').textContent = t;
    document.getElementById('m-kabul').textContent  = k;
    document.getElementById('m-red').textContent    = rd;
    document.getElementById('m-bekle').textContent  = b;

    if (!rows.length) {
      list.innerHTML = '<div class="empty-state">📭 Henüz başvuru yok.</div>';
      return;
    }

    list.innerHTML = rows.map(r => {
      const karar = r.ai_karar || '—';
      const durum = r.durum    || 'beklemede';
      const badgeCls = karar === 'KABUL' ? 'kabul' : karar === 'RED' ? 'red' : 'bekle';
      const icon = karar === 'KABUL' ? '✅' : karar === 'RED' ? '❌' : '⏳';

      let extracted = {};
      try { extracted = JSON.parse(r.extracted_json || '{}'); } catch {}
      let eksikler = [];
      try { eksikler = JSON.parse(r.missing_json || '[]'); } catch {}

      const infoKeys = ['ad_soyad','ogrenci_no','bolum','firma_adi',
                        'baslangic_tarihi','bitis_tarihi','staj_gun_sayisi'];
      const infoHtml = infoKeys
        .filter(k => extracted[k])
        .map(k => `<div class="info-row"><strong>${k}:</strong> ${extracted[k]}</div>`)
        .join('');

      const eksikHtml = eksikler.length
        ? `<div class="eksik-list">⚠️ Eksik alanlar: ${eksikler.join(', ')}</div>` : '';

      const raporHtml = r.ai_rapor
        ? `<span class="rapor-toggle" onclick="toggleRapor(${r.id})">📄 AI Raporu Göster</span>
           <div id="rapor-${r.id}" class="rapor-text">${r.ai_rapor}</div>` : '';

      return `
      <div class="basvuru-card" id="card-${r.id}">
        <div class="basvuru-card-head" onclick="toggleCard(${r.id})">
          <div>
            <div class="basvuru-title">${icon} #${r.id} — ${r.original_adi || '—'}</div>
            <div class="basvuru-meta">${r.yukleme_tarihi || ''} &nbsp;|&nbsp; Durum: ${durum}
              &nbsp;|&nbsp; Güven: ${r.ai_guven ? Math.round(r.ai_guven*100)+'%' : '—'}
            </div>
          </div>
          <span class="badge ${badgeCls}">${karar}</span>
        </div>
        <div class="basvuru-body" id="body-${r.id}">
          <p style="font-size:.88rem;margin-bottom:12px;">${r.ai_mesaj || '—'}</p>
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

  } catch (e) {
    list.innerHTML = `<div class="empty-state">❌ Hata: ${e.message}</div>`;
  }
}

function toggleCard(id) {
  const body = document.getElementById('body-' + id);
  body.classList.toggle('open');
}

function toggleRapor(id) {
  const el = document.getElementById('rapor-' + id);
  el.style.display = el.style.display === 'block' ? 'none' : 'block';
}

async function manuelKarar(id, karar) {
  try {
    await fetch('/api/karar', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id, karar }),
    });
    showToast(karar === 'KABUL' ? '✅ Onaylandı!' : '❌ Reddedildi.');
    loadBasvurular();
  } catch (e) {
    showToast('❌ Hata: ' + e.message);
  }
}

/* ── TOAST ────────────────────────────────────────────────────────────────── */
let toastTimer = null;
function showToast(msg) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('show'), 3200);
}
