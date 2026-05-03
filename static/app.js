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
function _esc(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

async function loadKurallar() {
  const list = document.getElementById('kurallar-list');
  if (!list) return;
  try {
    const res  = await fetch('/api/kurallar');
    const data = await res.json();
    const kats = data.kategoriler;
    if (kats && kats.length) {
      list.innerHTML = kats.map(k => {
        const maddeler = (k.maddeler || []).map(m =>
          `<li class="kural-madde">${_esc(m)}</li>`
        ).join('');
        return `
          <div class="kural-kategori">
            <div class="kural-kategori-head">
              <span class="kural-ikon">${_esc(k.ikon||'•')}</span>
              <span class="kural-baslik">${_esc(k.baslik||'')}</span>
            </div>
            <ul class="kural-maddeler">${maddeler}</ul>
          </div>`;
      }).join('');
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
    const eksikler = (data.eksikler || []).map(e =>
      typeof e === 'string' ? e : (e.alan || e.label || e.key || JSON.stringify(e))
    );
    const t = data.tarihler || {};
    const tarihHtml = (t.baslangic || t.bitis)
      ? `<div class="gonderme-tarih">📅 ${t.baslangic||'?'} → ${t.bitis||'?'}${t.staj_gun ? ` · ${t.staj_gun} gün` : ''}</div>`
      : '';
    const isKabul = data.karar === 'KABUL';
    const eksikHtml = eksikler.length
      ? `<div class="gonderme-eksik">⚠️ Eksik alanlar: ${eksikler.join(', ')}</div>` : '';
    resultBox.className = 'yukle-result ' + (isKabul ? 'kabul' : 'red');
    resultBox.innerHTML =
      `<div class="gonderme-baslik">${isKabul ? '✅ Başvurunuz Onaylandı' : '❌ Başvurunuz Reddedildi'} — #${data.id}</div>` +
      `<div class="gonderme-aciklama">${data.mesaj || ''}</div>` +
      `${tarihHtml}${eksikHtml}` +
      `<div class="gonderme-bilgi">${isKabul
        ? '🎉 Tebrikler! Başvurunuz AI değerlendirmesinde uygun bulundu. Sekreter ek bir gözden geçirme yapabilir.'
        : 'ℹ️ Lütfen eksikleri tamamlayıp yeniden başvurun.'}</div>`;
    showToast(isKabul ? '✅ Başvurunuz onaylandı!' : '❌ Başvurunuz reddedildi.');
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
  if (!text) return '';
  // 1) HTML escape
  let h = String(text)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  // 2) Code inline `kod`
  h = h.replace(/`([^`]+)`/g, '<code>$1</code>');
  // 3) Bold/italic
  h = h.replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>');
  h = h.replace(/(?<![*\w])\*([^*\n]+)\*(?!\w)/g, '<em>$1</em>');
  // 4) Headings ##/### → kalın küçük başlık
  h = h.replace(/^###?\s+(.+)$/gm, '<div class="md-h">$1</div>');
  // 5) Numaralı liste 1. ... → <li>
  h = h.replace(/^\s*\d+\.\s+(.+)$/gm, '<li class="md-ol">$1</li>');
  // 6) Madde işaretli liste - veya • → <li>
  h = h.replace(/^\s*[-•]\s+(.+)$/gm, '<li class="md-ul">$1</li>');
  // 7) Ardışık <li>'leri grupla
  h = h.replace(/(<li class="md-ol">.*?<\/li>(?:\s*<li class="md-ol">.*?<\/li>)+)/gs,
                m => '<ol class="md-list">' + m.replace(/ class="md-ol"/g,'') + '</ol>');
  h = h.replace(/(<li class="md-ul">.*?<\/li>(?:\s*<li class="md-ul">.*?<\/li>)+)/gs,
                m => '<ul class="md-list">' + m.replace(/ class="md-ul"/g,'') + '</ul>');
  // Tek <li>'leri de sar
  h = h.replace(/<li class="md-ol">(.+?)<\/li>/g, '<ol class="md-list"><li>$1</li></ol>');
  h = h.replace(/<li class="md-ul">(.+?)<\/li>/g, '<ul class="md-list"><li>$1</li></ul>');
  // 8) Paragraflar — boş satırlar paragraf ayırır
  const paragraflar = h.split(/\n\n+/);
  h = paragraflar.map(p => {
    p = p.trim();
    if (!p) return '';
    // Zaten blok eleman varsa <p> ekleme
    if (/^<(ol|ul|div|blockquote)/.test(p)) return p;
    return '<p>' + p.replace(/\n/g, '<br>') + '</p>';
  }).join('');
  return h;
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
  const typing = appendMsg('▌', 'bot typing');
  chatSend.disabled = true;

  // 1) Streaming ile token-by-token yanıt
  let tamYanit = '';
  try {
    const res = await fetch('/api/chat-stream', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ soru, gecmis: _chatHistory.slice(0,-1) }),
    });
    if (!res.ok || !res.body) throw new Error('stream-yok');
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split('\n\n');
      buffer = parts.pop() || '';
      for (const p of parts) {
        const line = p.trim();
        if (!line.startsWith('data:')) continue;
        const payload = line.slice(5).trim();
        if (payload === '[DONE]') break;
        try {
          const obj = JSON.parse(payload);
          if (obj.t) {
            tamYanit += obj.t;
            typing.innerHTML = mdToHtml(tamYanit) + '<span class="cursor-blink">▌</span>';
            chatMessages.scrollTop = chatMessages.scrollHeight;
          } else if (obj.err) {
            tamYanit = 'Ollama hatası: ' + obj.err;
          }
        } catch {}
      }
    }
    typing.innerHTML = mdToHtml(tamYanit);
    typing.classList.remove('typing');
  } catch (e) {
    // Fallback: eski non-stream endpoint
    try {
      const res = await fetch('/api/chat', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ soru, gecmis: _chatHistory.slice(0,-1) }),
      });
      const d = await res.json();
      tamYanit = d.yanit || '';
      typing.innerHTML = mdToHtml(tamYanit);
      typing.classList.remove('typing');
    } catch {
      typing.textContent = '❌ Bağlantı hatası.';
      tamYanit = '';
    }
  }

  // Hata mı?
  const isHata = tamYanit.toLowerCase().startsWith('ollama hatası') || tamYanit.startsWith('❌');
  if (isHata) typing.classList.add('chat-msg-error');

  // 2) History'e ekle
  if (!isHata && tamYanit) _chatHistory.push({ role:'assistant', content: tamYanit });
  if (_chatHistory.length > 20) _chatHistory = _chatHistory.slice(-20);

  // 3) Form extraction — sadece soruda gerçek veri sinyali varsa (arka planda)
  const data = { yanit: tamYanit, form_data: {} };
  const SIGNAL = /\d{1,2}[\/.\-]\d{1,2}|\d{4}-\d{2}-\d{2}|ocak|şubat|mart|nisan|mayıs|haziran|temmuz|ağustos|eylül|ekim|kasım|aralık|firma|adres/i;
  if (!isHata && SIGNAL.test(soru)) {
    try {
      const r2 = await fetch('/api/chat', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ soru, gecmis: [] }),
      });
      const d2 = await r2.json();
      if (d2.form_data) data.form_data = d2.form_data;
    } catch {}
  }

  // Form alanı verisi geldiyse otomatik doldur (chat başarısız olduysa atlanır)
  if (!isHata && data.form_data && Object.keys(data.form_data).length > 0) {
    const ALAN_ADLARI = {
      baslangic_tarihi: 'Başlangıç',
      bitis_tarihi:     'Bitiş',
      staj_gun_sayisi:  'Staj Günü',
      firma_adi:        'Firma Adı',
      firma_adresi:     'Firma Adresi',
      hizmet_alani:     'Hizmet Alanı',
      bolum:            'Bölüm',
      ad_soyad:         'Ad Soyad',
      ogrenci_no:       'Öğrenci No',
      tc_kimlik_no:     'TC Kimlik',
    };
    const satirlar = [];
    Object.entries(data.form_data).forEach(([key, val]) => {
      const el = document.getElementById(key);
      if (el) {
        el.value = val;
        // Yeşil highlight animasyonu
        el.classList.add('autofill-flash');
        setTimeout(() => el.classList.remove('autofill-flash'), 2000);
        const etiket = ALAN_ADLARI[key] || key;
        const gosterim = key.includes('tarih') ? val.split('-').reverse().join('.') : val;
        satirlar.push(`<span class="autofill-row"><span class="autofill-key">${etiket}:</span> <span class="autofill-val">${gosterim}</span></span>`);
      }
    });
    if (satirlar.length) {
      hesaplaTarih();
      runValidate();
      const bilgi = document.createElement('div');
      bilgi.className = 'chat-msg bot autofill-msg';
      bilgi.innerHTML = `<div class="autofill-head">🤖 Form otomatik dolduruldu</div>${satirlar.join('')}`;
      chatMessages.appendChild(bilgi);
      chatMessages.scrollTop = chatMessages.scrollHeight;
    }
  }

  chatSend.disabled = false;
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
  const list = document.getElementById('tab-basvurular');
  if (!list) return;
  list.innerHTML = '<div class="empty-state">⏳ Yükleniyor…</div>';
  try {
    const res  = await fetch('/api/basvurular');
    _allRows   = await res.json();
    const t  = _allRows.length;
    const k  = _allRows.filter(r => r.durum === 'onaylandi').length;
    const rd = _allRows.filter(r => r.durum === 'reddedildi').length;
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
  const list = document.getElementById('tab-basvurular');
  if (!rows.length) { list.innerHTML = '<div class="empty-state">📭 Başvuru yok.</div>'; return; }
  list.innerHTML = rows.map(r => {
    // Gerçek karar: durum (sekreter kararı) — AI önerisi: ai_karar
    const durum    = r.durum || 'beklemede';
    const aiOneri  = r.ai_karar || '—';
    const bekleyen = durum === 'beklemede';
    const cardCls  = durum === 'onaylandi' ? 'kabul-card' : durum === 'reddedildi' ? 'red-card' : 'bekle-card';
    const durumIcon = durum === 'onaylandi' ? '✅' : durum === 'reddedildi' ? '❌' : '⏳';
    const durumLabel = durum === 'onaylandi' ? 'Onaylandı' : durum === 'reddedildi' ? 'Reddedildi' : 'Beklemede';
    const durumBadgeCls = durum === 'onaylandi' ? 'kabul' : durum === 'reddedildi' ? 'red' : 'bekle';

    let ext = {}; try { ext = JSON.parse(r.extracted_json || '{}'); } catch {}
    let eks = []; try { eks = JSON.parse(r.missing_json || '[]'); } catch {}
    let aiD = {}; try { aiD = JSON.parse(r.ai_detay_json || '{}'); } catch {}

    const infoHtml = [
      ['Ad Soyad','ad_soyad'],['Öğrenci No','ogrenci_no'],['Bölüm','bolum'],
      ['Firma','firma_adi'],['Başlangıç','baslangic_tarihi'],['Bitiş','bitis_tarihi'],['Gün','staj_gun_sayisi']
    ].filter(([,k]) => ext[k])
     .map(([lbl,k]) => `<div class="info-row"><strong>${lbl}:</strong> ${ext[k]}</div>`).join('');

    const eksikHtml = eks.length ? `<div class="eksik-list">⚠️ Eksik: ${eks.join(', ')}</div>` : '';

    // AI önerisi — sekreter için bilgi amaçlı
    const aiOneriCls  = aiOneri === 'KABUL' ? 'ai-oneri-kabul' : aiOneri === 'RED' ? 'ai-oneri-red' : '';
    const aiOneriHtml = aiOneri !== '—'
      ? `<div class="ai-oneri-badge ${aiOneriCls}">🤖 AI Öneri: ${aiOneri === 'KABUL' ? 'Uygun görünüyor' : 'Dikkat edilmesi gereken noktalar var'}</div>`
      : '';

    // AI Detay paneli
    let aiDetayHtml = '';
    if (aiD && (aiD.firma_analizi || aiD.tarih_analizi || aiD.oneriler?.length)) {
      const risk = aiD.risk_skoru || 0;
      const riskRenk = risk < 30 ? '#059669' : risk < 60 ? '#d97706' : '#dc2626';
      aiDetayHtml = `
        <div class="ai-detay-panel">
          <div class="ai-detay-head">🧠 AI Değerlendirmesi</div>
          <div class="ai-risk-bar">
            <span>Risk:</span>
            <div class="ai-risk-track"><div class="ai-risk-fill" style="width:${risk}%;background:${riskRenk}"></div></div>
            <strong style="color:${riskRenk}">${risk}/100</strong>
          </div>
          ${aiD.firma_analizi  ? `<div class="ai-detay-row">🏢 <strong>Firma:</strong> ${aiD.firma_analizi}</div>` : ''}
          ${aiD.tarih_analizi  ? `<div class="ai-detay-row">📅 <strong>Tarih:</strong> ${aiD.tarih_analizi}</div>` : ''}
          ${aiD.ogrenci_yorumu ? `<div class="ai-detay-row">👤 <strong>Öğrenci:</strong> ${aiD.ogrenci_yorumu}</div>` : ''}
          ${aiD.oneriler?.length ? `<div class="ai-detay-row">💡 <strong>Öneriler:</strong><ul>${aiD.oneriler.map(o=>`<li>${o}</li>`).join('')}</ul></div>` : ''}
          ${aiD.dikkat?.length   ? `<div class="ai-detay-row ai-uyari">⚠️ <strong>Dikkat:</strong><ul>${aiD.dikkat.map(o=>`<li>${o}</li>`).join('')}</ul></div>` : ''}
        </div>`;
    }

    const raporHtml = r.ai_rapor
      ? `<span class="rapor-toggle" onclick="toggleRapor(${r.id})">📄 AI Ham Yanıtı</span><div id="rapor-${r.id}" class="rapor-text">${r.ai_rapor}</div>` : '';

    // Aksiyon satırı: AI kararı finaldir, sekreter override edebilir
    const karsiKarar = durum === 'onaylandi' ? 'RED' : 'KABUL';
    const karsiLabel = durum === 'onaylandi' ? '❌ Reddet' : '✅ Onayla';
    const aksiyonHtml = `
      <div class="karar-verildi">
        ${durum === 'onaylandi'
          ? '<span style="color:#065f46;font-weight:700;">✅ AI tarafından onaylandı</span>'
          : durum === 'reddedildi'
          ? '<span style="color:#991b1b;font-weight:700;">❌ AI tarafından reddedildi</span>'
          : '<span style="color:#92400e;font-weight:700;">⏳ İşleniyor…</span>'}
        <button class="btn btn-outline btn-sm" onclick="manuelKarar(${r.id},'${karsiKarar}')">${karsiLabel} (Override)</button>
      </div>`;

    return `
    <div class="basvuru-card ${cardCls}" id="card-${r.id}">
      <div class="basvuru-head" onclick="toggleCard(${r.id})">
        <div>
          <div class="basvuru-title">${durumIcon} #${r.id} — ${ext.ad_soyad || r.original_adi || '—'}</div>
          <div class="basvuru-meta">${r.yukleme_tarihi||''} · ${ext.firma_adi||''} ${ext.bolum ? '· '+ext.bolum : ''}</div>
        </div>
        <div style="display:flex;align-items:center;gap:8px;flex-shrink:0;flex-wrap:wrap">
          ${aiOneriHtml}
          <span class="badge ${durumBadgeCls}">${durumLabel}</span>
          <a href="/api/basvuru/pdf/${r.id}" target="_blank" class="btn btn-outline btn-sm pdf-goruntule-btn" onclick="event.stopPropagation()">📄 PDF</a>
        </div>
      </div>
      <div class="basvuru-body" id="body-${r.id}">
        <p style="font-size:.88rem;margin-bottom:12px;color:var(--gray-600)">${r.ai_mesaj||'—'}</p>
        ${eksikHtml}
        <div class="basvuru-info">${infoHtml}</div>
        ${aiDetayHtml}
        ${raporHtml}
        ${aksiyonHtml}
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
    rows = rows.filter(r => {
      if (_activeFilter === 'beklemede') return r.durum === 'beklemede';
      if (_activeFilter === 'KABUL')     return r.durum === 'onaylandi';
      if (_activeFilter === 'RED')       return r.durum === 'reddedildi';
      return true;
    });
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

/* ── 🤖 AGENT ─────────────────────────────────────────────────────────────── */
function _renderToolSonuc(tool, sonuc) {
  /* Tool sonucunu kullanıcı dostu formatta göster (sayılar, listeler vs.) */
  if (!sonuc || sonuc.hata) {
    return `<div class="agent-hata">❌ ${_esc(sonuc?.hata || 'Sonuç yok')}</div>`;
  }

  const t = (tool || '').toUpperCase();

  // ISTATISTIK ozet → 4 metrik kartı
  if (t === 'ISTATISTIK' && 'toplam' in sonuc) {
    return `<div class="agent-stats">
      <div class="agent-stat-card stat-toplam"><div class="stat-num">${sonuc.toplam}</div><div class="stat-lbl">Toplam</div></div>
      <div class="agent-stat-card stat-kabul"><div class="stat-num">${sonuc.kabul||0}</div><div class="stat-lbl">Kabul</div></div>
      <div class="agent-stat-card stat-red"><div class="stat-num">${sonuc.red||0}</div><div class="stat-lbl">Red</div></div>
      <div class="agent-stat-card stat-bekle"><div class="stat-num">${sonuc.beklemede||0}</div><div class="stat-lbl">Beklemede</div></div>
    </div>`;
  }

  // ISTATISTIK firma/bolum → bar chart benzeri liste
  if (t === 'ISTATISTIK' && (sonuc.firma || sonuc.bolum)) {
    const liste = sonuc.firma || sonuc.bolum;
    const baslik = sonuc.firma ? '🏢 Firmalara Göre Dağılım' : '🎓 Bölümlere Göre Dağılım';
    const max = Math.max(...liste.map(x => x.sayi), 1);
    let h = `<div class="agent-rank-baslik">${baslik}</div><div class="agent-rank-list">`;
    liste.forEach((it, i) => {
      const pct = (it.sayi / max) * 100;
      h += `<div class="agent-rank-row">
        <span class="agent-rank-num">#${i+1}</span>
        <span class="agent-rank-isim">${_esc(it.isim)}</span>
        <div class="agent-rank-bar"><div class="agent-rank-fill" style="width:${pct}%"></div></div>
        <span class="agent-rank-sayi">${it.sayi}</span>
      </div>`;
    });
    h += '</div>';
    return h;
  }

  // LIST_BASVURU / ARA / ONCELIK → başvuru listesi tablosu
  if ((t === 'LIST_BASVURU' || t === 'ARA' || t === 'ONCELIK' || t === 'ONCELIK_SIRALA') && Array.isArray(sonuc)) {
    if (sonuc.length === 0) return '<div class="agent-bos">📭 Sonuç bulunamadı.</div>';
    let h = `<div class="agent-list-baslik">📋 ${sonuc.length} başvuru</div>`;
    h += '<div class="agent-basvuru-list">';
    sonuc.forEach(b => {
      const kararCls = b.durum === 'onaylandi' ? 'kabul' : b.durum === 'reddedildi' ? 'red' : 'bekle';
      const icon = b.durum === 'onaylandi' ? '✅' : b.durum === 'reddedildi' ? '❌' : '⏳';
      h += `<div class="agent-basvuru-item ${kararCls}">
        <span class="agent-basvuru-id">#${b.id}</span>
        <div class="agent-basvuru-info">
          <div class="agent-basvuru-ad">${_esc(b.ad || '?')}</div>
          <div class="agent-basvuru-meta">${_esc(b.firma || '—')} · ${_esc(b.bolum || '—')}</div>
        </div>
        <span class="agent-basvuru-badge badge-${kararCls}">${icon} ${_esc(b.karar || b.durum || '—')}</span>
      </div>`;
    });
    h += '</div>';
    return h;
  }

  // GET_BASVURU → tek başvuru detayı
  if (t === 'GET_BASVURU' && sonuc.id) {
    const f = sonuc.form || {};
    const kararCls = sonuc.durum === 'onaylandi' ? 'kabul' : sonuc.durum === 'reddedildi' ? 'red' : 'bekle';
    let h = `<div class="agent-detay">
      <div class="agent-detay-baslik">📄 #${sonuc.id} — ${_esc(f.ad_soyad || sonuc.original_adi || '?')}
        <span class="agent-basvuru-badge badge-${kararCls}">${_esc(sonuc.durum || '—')}</span>
      </div>
      <div class="agent-detay-grid">`;
    [['Bölüm','bolum'],['Öğrenci No','ogrenci_no'],['Firma','firma_adi'],
     ['Başlangıç','baslangic_tarihi'],['Bitiş','bitis_tarihi'],['Gün','staj_gun_sayisi']
    ].forEach(([lbl,k])=>{
      if (f[k]) h += `<div><span class="lbl">${lbl}:</span> ${_esc(f[k])}</div>`;
    });
    h += '</div>';
    if (sonuc.ai_mesaj) h += `<div class="agent-detay-msg">💬 ${_esc(sonuc.ai_mesaj)}</div>`;
    h += '</div>';
    return h;
  }

  // ONAYLA / REDDET sonuç
  if ((t === 'ONAYLA' || t === 'REDDET') && sonuc.ok) {
    const ic = t === 'ONAYLA' ? '✅' : '❌';
    return `<div class="agent-islem ${t.toLowerCase()}">
      ${ic} #${sonuc.id} → <strong>${_esc(sonuc.yeni_durum)}</strong>
      ${sonuc.sebep ? `<div class="agent-sebep">${_esc(sonuc.sebep)}</div>` : ''}
    </div>`;
  }

  // CEVAP — düz mesaj
  if (t === 'CEVAP' && sonuc.mesaj) {
    return `<div class="agent-cevap">${mdToHtml(sonuc.mesaj)}</div>`;
  }

  // Bilinmeyen → JSON pretty
  return `<pre class="agent-raw">${_esc(JSON.stringify(sonuc, null, 2).slice(0, 800))}</pre>`;
}

let _agentBusy = false;
async function agentGonder(directKomut) {
  if (_agentBusy) return;   // Çift tıklamayı engelle
  _agentBusy = true;

  const input  = document.getElementById('agent-input');
  const result = document.getElementById('agent-result');
  const komut  = directKomut || (input?.value.trim()) || '';
  if (!komut) { _agentBusy = false; return; }

  // Tüm Sor / agent butonlarını disable et
  document.querySelectorAll('.agent-soru-row button, .agent-action-btn').forEach(b => b.disabled = true);

  // Eski içeriği temizle (üst üste birikmesin)
  result.style.display = 'block';
  result.innerHTML =
    `<div class="agent-msg agent-msg-user">👤 ${_esc(komut)}</div>` +
    `<div class="agent-msg agent-loading">⏳ Asistan çalışıyor…</div>`;

  try {
    const res  = await fetch('/api/agent/komut', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ komut }),
    });
    const data = await res.json();
    const loadEl = result.querySelector('.agent-loading');
    if (loadEl) loadEl.remove();

    if (!data.ok) {
      result.insertAdjacentHTML('beforeend',
        `<div class="agent-msg agent-hata">❌ ${_esc(data.yanit || 'Hata')}</div>`);
      return;
    }

    let html = '<div class="agent-msg agent-msg-bot agent-rich">';

    // 1. ÖZET (en üstte) — açıklama + karar varsa onlar
    if (data.aciklama) {
      html += `<div class="agent-ozet">${mdToHtml(data.aciklama)}</div>`;
    }

    // 2. KARAR (varsa, KABUL/RED/BEKLEME)
    if (data.karar && data.karar.sonuc && data.karar.sonuc !== 'BEKLEME') {
      const sonuc = data.karar.sonuc;
      const kararCls = sonuc === 'KABUL' ? 'kabul' : 'red';
      const kararIcon = sonuc === 'KABUL' ? '✅' : '❌';
      html += `<div class="agent-karar agent-karar-${kararCls}">${kararIcon} <strong>${sonuc}</strong></div>`;
      if (data.karar.nedenler && data.karar.nedenler.length) {
        html += '<ul class="agent-nedenler">';
        data.karar.nedenler.forEach(n => html += `<li>${_esc(n)}</li>`);
        html += '</ul>';
      }
    }

    // 3. SONUÇLAR (asıl önemli kısım — tool çıktıları)
    if (data.tool_calls && data.tool_calls.length) {
      data.tool_calls.forEach(tc => {
        html += _renderToolSonuc(tc.tool, tc.sonuc);
      });
    }

    // 4. ANALİZ (varsa, başvuru analiz edildiyse)
    const a = data.analiz || {};
    if (a.risk_skoru !== undefined && a.gun_durumu) {
      const risk = parseInt(a.risk_skoru || 0);
      const riskRenk = risk < 30 ? '#059669' : risk < 60 ? '#d97706' : '#dc2626';
      html += '<div class="agent-analiz-mini">';
      html += `<span class="agent-mini-baslik">🔍 Analiz:</span>`;
      ['gun_durumu','tarih_durumu','firma_durumu','belge_durumu'].forEach(k => {
        if (a[k] && a[k] !== 'BILINMIYOR')
          html += `<span class="agent-analiz-tag">${k.split('_')[0]}: ${_esc(a[k])}</span>`;
      });
      html += `<span class="agent-analiz-tag" style="background:${riskRenk}20;color:${riskRenk}">Risk: ${risk}/100</span>`;
      html += '</div>';
    }

    // 5. TEKNİK DETAY (collapsible — debug bilgisi)
    if (data.plan?.length || data.tool_calls?.length) {
      html += '<details class="agent-detay-toggle"><summary>🛠️ Teknik detay</summary>';
      if (data.plan?.length) {
        html += '<div class="agent-mini-blok"><b>Plan:</b> ' + data.plan.map(p=>`<code>${_esc(p)}</code>`).join(' → ') + '</div>';
      }
      if (data.tool_calls?.length) {
        html += '<div class="agent-mini-blok"><b>Tool çağrıları:</b><ul>';
        data.tool_calls.forEach(tc => {
          html += `<li><code>${_esc(tc.tool)}(${_esc(JSON.stringify(tc.input||{}))})</code>`;
          if (tc.reason) html += ` <span class="agent-mini-reason">— ${_esc(tc.reason)}</span>`;
          html += '</li>';
        });
        html += '</ul></div>';
      }
      html += '</details>';
    }

    html += '</div>';
    result.insertAdjacentHTML('beforeend', html);

    // ONAYLA/REDDET varsa listeyi yenile
    const islemYapildi = (data.tool_calls || []).some(tc =>
      ['ONAYLA','REDDET'].includes((tc.tool||'').toUpperCase()));
    if (islemYapildi) {
      loadBasvurular();
      showToast('✅ Agent işlem yaptı!');
    }
    if (input) input.value = '';
  } catch (e) {
    const loadEl = result.querySelector('.agent-loading');
    if (loadEl) loadEl.innerHTML = '❌ Hata: ' + e.message;
  } finally {
    _agentBusy = false;
    document.querySelectorAll('.agent-soru-row button, .agent-action-btn').forEach(b => b.disabled = false);
  }
  result.scrollTop = result.scrollHeight;
}

function agentHizli(komut) {
  const input = document.getElementById('agent-input');
  if (input) input.value = komut;
  agentGonder(komut);
}

/* Doğrudan tool çağrısı — LLM bypass, anında sonuç */
async function agentDirect(tool, input, baslik) {
  const result = document.getElementById('agent-result');
  result.style.display = 'block';
  result.innerHTML =
    `<div class="agent-msg agent-msg-user">👤 ${_esc(baslik)}</div>` +
    `<div class="agent-msg agent-loading">⏳ Veriler getiriliyor…</div>`;
  try {
    const res = await fetch('/api/agent/direct', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({tool, input}),
    });
    const data = await res.json();
    const loadEl = result.querySelector('.agent-loading');
    if (loadEl) loadEl.remove();
    let html = '<div class="agent-msg agent-msg-bot agent-rich">';
    (data.tool_calls || []).forEach(tc => {
      html += _renderToolSonuc(tc.tool, tc.sonuc);
    });
    html += '</div>';
    result.insertAdjacentHTML('beforeend', html);
  } catch (e) {
    const loadEl = result.querySelector('.agent-loading');
    if (loadEl) loadEl.innerHTML = '❌ Hata: ' + e.message;
  }
  result.scrollTop = result.scrollHeight;
}

/* Çoklu tool çağrısı sırayla */
async function agentDirectMulti(calls, baslik) {
  const result = document.getElementById('agent-result');
  result.style.display = 'block';
  result.innerHTML =
    `<div class="agent-msg agent-msg-user">👤 ${_esc(baslik)}</div>` +
    `<div class="agent-msg agent-loading">⏳ Veriler getiriliyor…</div>`;
  try {
    const sonuclar = await Promise.all(calls.map(c =>
      fetch('/api/agent/direct', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify(c),
      }).then(r => r.json())
    ));
    const loadEl = result.querySelector('.agent-loading');
    if (loadEl) loadEl.remove();
    let html = '<div class="agent-msg agent-msg-bot agent-rich">';
    sonuclar.forEach(d => {
      (d.tool_calls || []).forEach(tc => {
        html += _renderToolSonuc(tc.tool, tc.sonuc);
      });
    });
    html += '</div>';
    result.insertAdjacentHTML('beforeend', html);
  } catch (e) {
    const loadEl = result.querySelector('.agent-loading');
    if (loadEl) loadEl.innerHTML = '❌ Hata: ' + e.message;
  }
  result.scrollTop = result.scrollHeight;
}

function agentSoru() {
  const row = document.getElementById('agent-soru-row');
  if (!row) return;
  const visible = row.style.display !== 'none';
  row.style.display = visible ? 'none' : 'flex';
  if (!visible) document.getElementById('agent-input')?.focus();
}

/* ── AI ÖZET ──────────────────────────────────────────────────────────────── */
async function aiOzet() {
  const card = document.getElementById('ai-ozet-card');
  const body = document.getElementById('ai-ozet-body');
  card.style.display = 'block';
  body.innerHTML = '<div style="padding:20px;text-align:center;color:#64748b;">⏳ AI özet hazırlanıyor… (bu 30 saniye sürebilir)</div>';
  try {
    const res  = await fetch('/api/ai-ozet');
    const data = await res.json();
    body.innerHTML = mdToHtml(data.ozet || '—');
  } catch (e) {
    body.innerHTML = `<div style="color:#dc2626;padding:14px;">❌ ${e.message}</div>`;
  }
}

/* ── SEKRETER SEKMELERİ ───────────────────────────────────────────────────── */
function sekmeAc(btn, sekme) {
  document.querySelectorAll('.sek-tab').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById('tab-basvurular').style.display = sekme === 'basvurular' ? 'flex' : 'none';
  document.getElementById('tab-raporlar').style.display   = sekme === 'raporlar'   ? 'flex' : 'none';
  const dokTab = document.getElementById('tab-dokumanlar');
  if (dokTab) dokTab.style.display = sekme === 'dokumanlar' ? 'flex' : 'none';
  if (sekme === 'raporlar')   loadRaporlar();
  if (sekme === 'dokumanlar') loadDokumanlar();
}

/* ── DÖKÜMAN YÖNETİMİ ─────────────────────────────────────────────────────── */
async function loadDokumanlar() {
  const list = document.getElementById('dok-list');
  const yonergeBadge = document.getElementById('dok-yonerge-badge');
  const yonergeMeta  = document.getElementById('yonerge-mevcut-meta');
  if (!list) return;
  list.innerHTML = '⏳ Yükleniyor…';
  try {
    const res = await fetch('/api/docs');
    const data = await res.json();
    const docs = data.docs || [];
    const yonerge = docs.find(d => d.is_yonerge);
    if (yonerge) {
      if (yonergeBadge) yonergeBadge.textContent = `${yonerge.chunks} chunk · ${yonerge.size_kb} KB`;
      if (yonergeMeta) {
        yonergeMeta.innerHTML =
          `<strong>${yonerge.size_kb} KB</strong> · ` +
          `<strong>${yonerge.chunks}</strong> chunk` +
          (yonerge.guncel ? ` · son güncelleme: <strong>${yonerge.guncel}</strong>` : '');
      }
    }
    const ekler = docs.filter(d => !d.is_yonerge);
    if (ekler.length === 0) {
      list.innerHTML = '<div class="dok-empty">📭 Henüz ek doküman yok.</div>';
      return;
    }
    list.innerHTML = ekler.map(d => `
      <div class="dok-row">
        <div class="dok-info">
          <span class="dok-icon">📄</span>
          <div>
            <div class="dok-name">${_esc(d.name)}</div>
            <div class="dok-meta">${d.chunks} chunk · ${d.size_kb} KB${d.guncel ? ' · ' + d.guncel : ''}</div>
          </div>
        </div>
        <div class="dok-actions">
          <a href="/api/docs/view/${encodeURIComponent(d.name)}" target="_blank" class="btn btn-outline btn-sm" title="Görüntüle">👁️</a>
          <a href="/api/docs/view/${encodeURIComponent(d.name)}?indir=1" class="btn btn-outline btn-sm" title="İndir">⬇️</a>
          <button class="btn btn-danger btn-sm" onclick="dokSil('${_esc(d.name)}')" title="Sil">🗑️</button>
        </div>
      </div>
    `).join('');
  } catch (e) {
    list.innerHTML = '<div class="dok-empty">❌ Yüklenemedi: ' + e.message + '</div>';
  }
}

const yonergeFile = document.getElementById('yonerge-file');
if (yonergeFile) {
  yonergeFile.addEventListener('change', () => {
    const f = yonergeFile.files[0];
    document.getElementById('yonerge-file-name').textContent = f ? f.name : 'Dosya seçilmedi';
    document.getElementById('btn-yonerge-update').disabled = !f;
  });
}

async function yonergeGuncelle() {
  const f = document.getElementById('yonerge-file').files[0];
  if (!f) return;
  const result = document.getElementById('yonerge-result');
  const btn = document.getElementById('btn-yonerge-update');
  btn.disabled = true; btn.innerHTML = '<span class="spin">⏳</span> Güncelleniyor…';
  result.style.display = 'block';
  result.className = 'yonerge-result info';
  result.textContent = '⏳ Yönerge yükleniyor ve indeksleniyor…';
  const fd = new FormData();
  fd.append('pdf', f);
  try {
    const res = await fetch('/api/docs/yonerge-update', { method: 'POST', body: fd });
    const data = await res.json();
    if (data.ok) {
      result.className = 'yonerge-result success';
      result.innerHTML = `✅ <strong>${data.mesaj}</strong><br>Boyut: ${data.boyut_kb} KB · ${data.karakter} karakter`;
      showToast('✅ Yönerge güncellendi!');
      loadDokumanlar();
      // Yönerge değiştiyse kuralları da yenile
      if (typeof loadKurallar === 'function') loadKurallar();
    } else {
      result.className = 'yonerge-result error';
      result.textContent = '❌ ' + (data.hata || 'Hata');
    }
  } catch (e) {
    result.className = 'yonerge-result error';
    result.textContent = '❌ Bağlantı hatası: ' + e.message;
  } finally {
    btn.disabled = false; btn.innerHTML = '⬆️ Yönergeyi Güncelle';
    document.getElementById('yonerge-file-name').textContent = 'Dosya seçilmedi';
    document.getElementById('yonerge-file').value = '';
  }
}

async function dokYukle(input) {
  const f = input.files[0];
  if (!f) return;
  const fd = new FormData();
  fd.append('pdf', f);
  showToast('⏳ Doküman yükleniyor…');
  try {
    const res = await fetch('/api/docs/upload', { method: 'POST', body: fd });
    const data = await res.json();
    if (data.ok) {
      showToast(`✅ ${data.dosya} eklendi`);
      loadDokumanlar();
    } else {
      showToast('❌ ' + (data.hata || 'Hata'));
    }
  } catch (e) { showToast('❌ ' + e.message); }
  input.value = '';
}

/* PDF görüntüle — yeni pencerede aç (Simple Browser dışına çıkmayı zorla) */
function dokGoruntule(url) {
  // window.open ile yeni pencere — VS Code Simple Browser bunu çoğunlukla
  // dışarı (gerçek tarayıcıya) yönlendirir
  const win = window.open(url, '_blank', 'noopener,noreferrer');
  if (!win) {
    // Popup engellendiyse: link kopyala
    navigator.clipboard?.writeText(window.location.origin + url);
    showToast('🔗 Link panoya kopyalandı, tarayıcıya yapıştır');
  }
}

/* PDF indir — Blob olarak fetch edip <a download> ile indirme tetikle */
async function dokIndir(url, dosyaAdi) {
  showToast('⏳ İndiriliyor…');
  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error('Dosya bulunamadı');
    const blob = await res.blob();
    const blobUrl = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = blobUrl;
    a.download = dosyaAdi || 'dokuman.pdf';
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(blobUrl), 1000);
    showToast('✅ İndirildi: ' + (dosyaAdi || 'dokuman.pdf'));
  } catch (e) {
    showToast('❌ İndirme hatası: ' + e.message);
  }
}

async function dokSil(name) {
  if (!confirm(`"${name}" dosyasını silmek istediğinize emin misiniz?`)) return;
  try {
    const res = await fetch('/api/docs/delete', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({name}),
    });
    const data = await res.json();
    if (data.ok) {
      showToast('🗑️ Silindi');
      loadDokumanlar();
    } else {
      showToast('❌ ' + (data.hata || 'Hata'));
    }
  } catch (e) { showToast('❌ ' + e.message); }
}

/* ── BİLDİRİMLER ──────────────────────────────────────────────────────────── */
let _bildirimAcik = false;

async function loadBildirimSayisi() {
  try {
    const res  = await fetch('/api/bildirimler/sayi');
    const data = await res.json();
    const badge = document.getElementById('notif-badge');
    if (!badge) return;
    if (data.sayi > 0) {
      badge.textContent = data.sayi > 99 ? '99+' : data.sayi;
      badge.style.display = 'flex';
    } else {
      badge.style.display = 'none';
    }
  } catch { /* sessiz */ }
}

async function toggleBildirimler() {
  const dd = document.getElementById('notif-dropdown');
  _bildirimAcik = !_bildirimAcik;
  dd.style.display = _bildirimAcik ? 'block' : 'none';
  if (_bildirimAcik) await loadBildirimler();
}

async function loadBildirimler() {
  const list = document.getElementById('notif-list');
  try {
    const res  = await fetch('/api/bildirimler');
    const rows = await res.json();
    if (!rows.length) { list.innerHTML = '<div class="notif-empty">Bildirim yok</div>'; return; }
    list.innerHTML = rows.map(r => `
      <div class="notif-item ${r.okundu ? 'okundu' : 'yeni'}" onclick="bildirimTikla(${r.id},${r.link_id||0},'${r.tip}')">
        <span class="notif-icon">${r.tip === 'rapor' ? '📝' : '📋'}</span>
        <div class="notif-body">
          <div class="notif-mesaj">${r.mesaj}</div>
          <div class="notif-tarih">${r.tarih}</div>
        </div>
        ${!r.okundu ? '<span class="notif-dot"></span>' : ''}
      </div>`).join('');
  } catch { list.innerHTML = '<div class="notif-empty">Yüklenemedi</div>'; }
}

async function bildirimTikla(id, linkId, tip) {
  await fetch('/api/bildirimler/okundu', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id }),
  });
  loadBildirimSayisi();
  loadBildirimler();
  if (tip === 'rapor') { sekmeAc(document.querySelectorAll('.sek-tab')[1], 'raporlar'); }
  else                 { loadBasvurular(); }
  _bildirimAcik = false;
  document.getElementById('notif-dropdown').style.display = 'none';
}

async function tumunuOku(e) {
  e.stopPropagation();
  await fetch('/api/bildirimler/okundu', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  });
  loadBildirimSayisi();
  loadBildirimler();
}

// Sekreter ise periyodik kontrol
if (document.getElementById('notif-badge')) {
  loadBildirimSayisi();
  setInterval(loadBildirimSayisi, 30000);
}

// Dropdown dışına tıklanınca kapat
document.addEventListener('click', e => {
  const wrap = document.querySelector('.notif-wrap');
  if (wrap && !wrap.contains(e.target)) {
    document.getElementById('notif-dropdown').style.display = 'none';
    _bildirimAcik = false;
  }
});

/* ── RAPOR YÜKLEME (öğrenci) ─────────────────────────────────────────────── */
const raporFile = document.getElementById('rapor-file');
if (raporFile) {
  raporFile.addEventListener('change', () => {
    const f = raporFile.files[0];
    document.getElementById('rapor-file-name').textContent = f ? f.name : 'Dosya seçilmedi';
    document.getElementById('btn-rapor-yukle').disabled = !f;
  });
}

async function raporYukle() {
  const file  = document.getElementById('rapor-file')?.files[0];
  const subId = document.getElementById('rapor-sub-id')?.value;
  const result = document.getElementById('rapor-result');
  if (!file || !subId) { showToast('⚠️ Başvuru ID ve rapor dosyası seçin.'); return; }
  const btn = document.getElementById('btn-rapor-yukle');
  btn.disabled = true; btn.innerHTML = '<span class="spin">⏳</span> Yükleniyor…';
  const fd = new FormData();
  fd.append('rapor', file);
  fd.append('submission_id', subId);
  try {
    const res  = await fetch('/api/rapor/yukle', { method: 'POST', body: fd });
    const data = await res.json();
    result.style.display = 'block';
    result.style.cssText = 'display:block;padding:8px 12px;border-radius:8px;font-size:.85rem;' +
      (data.ok ? 'background:#d1fae5;color:#065f46;' : 'background:#fee2e2;color:#991b1b;');
    result.textContent = data.ok ? '✅ Rapor başarıyla yüklendi!' : '❌ ' + (data.hata || 'Hata');
    if (data.ok) showToast('✅ Staj raporu gönderildi!');
  } catch (e) {
    result.style.display = 'block';
    result.textContent = '❌ Bağlantı hatası';
  } finally {
    btn.disabled = false; btn.innerHTML = '<span>📤</span> Yükle';
  }
}

/* ── RAPOR LİSTESİ (sekreter) ────────────────────────────────────────────── */
async function loadRaporlar() {
  const list = document.getElementById('tab-raporlar');
  list.innerHTML = '<div class="empty-state">⏳ Yükleniyor…</div>';
  try {
    const res  = await fetch('/api/rapor/liste');
    const rows = await res.json();
    if (!rows.length) { list.innerHTML = '<div class="empty-state">📭 Rapor yok.</div>'; return; }
    const durumRenk = { beklemede:'#fef3c7', incelendi:'#d1fae5', reddedildi:'#fee2e2' };
    list.innerHTML = rows.map(r => {
      let analiz = null;
      try { analiz = r.ai_analiz ? JSON.parse(r.ai_analiz) : null; } catch {}
      const skor = r.ai_skor || 0;
      const skorRenk = skor >= 7 ? '#059669' : skor >= 4 ? '#d97706' : '#dc2626';
      const aiBadge = analiz
        ? `<span class="ai-badge" style="background:${skorRenk}20;color:${skorRenk}">🧠 AI: ${skor}/10</span>`
        : `<span class="ai-badge" style="background:#fef3c7;color:#92400e">⏳ AI bekliyor</span>`;
      const analizHtml = analiz ? `
        <div class="ai-detay-panel" style="margin-top:10px">
          <div class="ai-detay-head">🧠 AI Rapor Analizi <span style="float:right;color:${skorRenk}">Kalite: ${skor}/10</span></div>
          ${analiz.ozet ? `<div class="ai-detay-row">📝 <strong>Özet:</strong> ${analiz.ozet}</div>` : ''}
          ${analiz.guclu_yonler?.length ? `<div class="ai-detay-row">✅ <strong>Güçlü:</strong><ul>${analiz.guclu_yonler.map(x=>`<li>${x}</li>`).join('')}</ul></div>` : ''}
          ${analiz.eksikler?.length ? `<div class="ai-detay-row ai-uyari">⚠️ <strong>Eksik:</strong><ul>${analiz.eksikler.map(x=>`<li>${x}</li>`).join('')}</ul></div>` : ''}
          ${analiz.oneriler?.length ? `<div class="ai-detay-row">💡 <strong>Öneri:</strong><ul>${analiz.oneriler.map(x=>`<li>${x}</li>`).join('')}</ul></div>` : ''}
        </div>` : '';
      return `
      <div class="basvuru-card" style="border-left:4px solid #4f46e5;padding:14px 18px;">
        <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
          <div>
            <strong>📝 Başvuru #${r.submission_id}</strong> — ${r.dosya_adi} ${aiBadge}
            <div style="font-size:.78rem;color:var(--gray-400);margin-top:2px;">${r.yukleme_tarihi}</div>
          </div>
          <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
            <span style="background:${durumRenk[r.durum]||'#f1f5f9'};padding:3px 10px;border-radius:20px;font-size:.8rem;font-weight:600;">${r.durum}</span>
            <a href="/api/rapor/indir/${r.id}" class="btn btn-outline btn-sm">⬇️ İndir</a>
            <button class="btn btn-primary btn-sm" onclick="aiAnaliz(${r.id})">🧠 AI Analiz</button>
            <button class="btn btn-success btn-sm" onclick="raporKarar(${r.id},'incelendi')">✅ İncelendi</button>
            <button class="btn btn-danger  btn-sm" onclick="raporKarar(${r.id},'reddedildi')">❌ Reddet</button>
          </div>
        </div>
        ${r.sekreter_notu ? `<div style="margin-top:8px;font-size:.83rem;color:var(--gray-600);">Not: ${r.sekreter_notu}</div>` : ''}
        ${analizHtml}
      </div>`;
    }).join('');
  } catch (e) { list.innerHTML = `<div class="empty-state">❌ ${e.message}</div>`; }
}

async function aiAnaliz(id) {
  showToast('🧠 AI rapor analizi başladı… (30-60 sn)');
  try {
    const res  = await fetch(`/api/rapor/analiz/${id}`, { method: 'POST' });
    const data = await res.json();
    if (data.ok) { showToast('✅ AI analiz tamamlandı!'); loadRaporlar(); }
    else         { showToast('❌ ' + (data.hata || 'Hata')); }
  } catch (e) { showToast('❌ ' + e.message); }
}

async function raporKarar(id, durum) {
  await fetch('/api/rapor/karar', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id, durum }),
  });
  showToast(durum === 'incelendi' ? '✅ Rapor incelendi.' : '❌ Rapor reddedildi.');
  loadRaporlar();
}

/* ── TOAST ────────────────────────────────────────────────────────────────── */
let toastTimer = null;
function showToast(msg) {
  const el = document.getElementById('toast');
  el.textContent = msg; el.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('show'), 3200);
}
