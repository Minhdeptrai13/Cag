/**
 * AOV Batch Pro Checker - Pure Monospace Stream Engine
 */

// Global State
let allResults = [];
let currentFilter = 'all';
let currentSearch = '';
let activeTaskId = null;
let pollInterval = null;

// DOM Elements
const statTotal = document.getElementById('statTotal');
const statHits = document.getElementById('statHits');
const statTrang = document.getElementById('statTrang');
const statSkinVIP = document.getElementById('statSkinVIP');

const countFilterAll = document.getElementById('countFilterAll');
const countFilterTrang = document.getElementById('countFilterTrang');
const countFilterVip = document.getElementById('countFilterVip');
const countFilterLive = document.getElementById('countFilterLive');

const threadInput = document.getElementById('threadInput');
const uploadZone = document.getElementById('uploadZone');
const fileInput = document.getElementById('fileInput');
const fileChosen = document.getElementById('fileChosen');
const batchText = document.getElementById('batchText');

const btnStartBatch = document.getElementById('btnStartBatch');
const btnClearBatch = document.getElementById('btnClearBatch');

const progressWrap = document.getElementById('progressWrap');
const progressStatus = document.getElementById('progressStatus');
const progressRatio = document.getElementById('progressRatio');
const progressBarFill = document.getElementById('progressBarFill');

const batchResultsList = document.getElementById('batchResultsList');
const filterSearch = document.getElementById('filterSearch');
const tabFilters = document.querySelectorAll('.tab-filter');

const btnCopyView = document.getElementById('btnCopyView');
const btnExportTrang = document.getElementById('btnExportTrang');
const btnExportAll = document.getElementById('btnExportAll');

const toast = document.getElementById('toast');

// ── Toast Helper ─────────────────────────────────────────────────────────────
function showToast(text, ms = 2500) {
  toast.textContent = text;
  toast.classList.add('show');
  setTimeout(() => toast.classList.remove('show'), ms);
}

window.copyFullAccount = function(btn) {
  const row = btn.closest('.acc-row');
  if (row) {
    const full = row.getAttribute('data-full') || '';
    if (full) {
      navigator.clipboard.writeText(full);
    }
  }
};

// ── File Drag & Drop ─────────────────────────────────────────────────────────
uploadZone.addEventListener('click', () => fileInput.click());

fileInput.addEventListener('change', (e) => {
  const file = e.target.files[0];
  if (file) handleFileLoaded(file);
});

uploadZone.addEventListener('dragover', (e) => {
  e.preventDefault();
  uploadZone.style.borderColor = 'var(--cyan)';
});
uploadZone.addEventListener('dragleave', () => {
  uploadZone.style.borderColor = 'var(--border-color)';
});
uploadZone.addEventListener('drop', (e) => {
  e.preventDefault();
  uploadZone.style.borderColor = 'var(--border-color)';
  const file = e.dataTransfer.files[0];
  if (file) handleFileLoaded(file);
});

function handleFileLoaded(file) {
  fileChosen.textContent = `[ ${file.name} - ${(file.size / 1024).toFixed(1)} KB ]`;
  const reader = new FileReader();
  reader.onload = (ev) => {
    batchText.value = ev.target.result;
    showToast(`DA NAP FILE: ${file.name}`);
  };
  reader.readAsText(file);
}

btnClearBatch.addEventListener('click', () => {
  batchText.value = '';
  fileChosen.textContent = '';
  fileInput.value = '';
  showToast('DA XOA TRANG');
});

// ── Start Batch Check ────────────────────────────────────────────────────────
btnStartBatch.addEventListener('click', async () => {
  const text = batchText.value.trim();
  if (!text) {
    showToast('VUI LONG DAN COMBO HOAC CHON FILE');
    return;
  }

  const lines = text.split('\n')
    .map(l => l.trim())
    .filter(l => l && !l.startsWith('#') && (/[:|;\t\s/]/.test(l)));

  if (lines.length === 0) {
    showToast('KHONG TIM THAY DONG ACC HOP LE');
    return;
  }

  const threads = parseInt(threadInput.value, 10) || 10;

  // Reset UI
  allResults = [];
  batchResultsList.innerHTML = '';
  updateCounters();

  document.getElementById('btnBatchText').style.display = 'none';
  document.getElementById('btnBatchLoader').style.display = 'inline-block';
  btnStartBatch.disabled = true;

  progressWrap.style.display = 'block';
  progressBarFill.style.width = '0%';
  progressStatus.textContent = 'Khoi dong luong...';
  progressRatio.textContent = `0/${lines.length} (0%)`;

  try {
    const resp = await fetch('/api/check-batch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ combos: lines, threads: threads })
    });

    const data = await resp.json();
    if (data.error) {
      showToast('LOI: ' + data.error);
      resetBatchUI();
      return;
    }

    activeTaskId = data.task_id;
    startTaskPolling(activeTaskId);
  } catch (err) {
    showToast('LOI KET NOI DEN SERVER');
    resetBatchUI();
  }
});

function resetBatchUI() {
  document.getElementById('btnBatchText').style.display = 'inline-block';
  document.getElementById('btnBatchLoader').style.display = 'none';
  btnStartBatch.disabled = false;
}

// ── Polling Background Task ──────────────────────────────────────────────────
function startTaskPolling(taskId) {
  if (pollInterval) clearInterval(pollInterval);

  pollInterval = setInterval(async () => {
    try {
      const resp = await fetch(`/api/task-status?task_id=${taskId}`);
      const data = await resp.json();

      if (data.error) {
        clearInterval(pollInterval);
        showToast('LOI TIEN TRINH: ' + data.error);
        resetBatchUI();
        return;
      }

      const total = data.total || 1;
      const done = data.done || 0;
      const pct = Math.floor((done / total) * 100);

      progressBarFill.style.width = pct + '%';
      progressStatus.textContent = data.status === 'DONE' ? 'HOAN THANH' : 'DANG CHECK...';
      progressRatio.textContent = `${done}/${total} (${pct}%)`;

      // Update new finished accounts
      const results = data.results || [];
      if (results.length > allResults.length) {
        const newItems = results.slice(allResults.length);
        allResults = results;
        renderNewItems(newItems);
        updateCounters();
      }

      if (data.status === 'DONE') {
        clearInterval(pollInterval);
        resetBatchUI();
        const hitCount = data.hits ?? data.hit ?? data.all_hits_count ?? 0;
        const trangCount = data.trang ?? 0;
        showToast(`HOÀN THÀNH CHECK: ${hitCount} LIVE / ${trangCount} TRẮNG`);
      }
    } catch (e) {
      console.error('Polling error:', e);
    }
  }, 800);
}

// ── Render Item Rows ─────────────────────────────────────────────────────────
function renderNewItems(items) {
  const empty = batchResultsList.querySelector('.empty-state');
  if (empty) empty.remove();

  const frag = document.createDocumentFragment();
  items.forEach(item => {
    if (matchesFilterAndSearch(item)) {
      const row = createRowElement(item);
      frag.appendChild(row);
    }
  });
  batchResultsList.prepend(frag);
}

function renderAllItems() {
  batchResultsList.innerHTML = '';
  const filtered = allResults.filter(matchesFilterAndSearch);

  if (filtered.length === 0) {
    batchResultsList.innerHTML = `<div class="empty-state">[ KHÔNG CÓ TÀI KHOẢN PHÙ HỢP BỘ LỌC ]</div>`;
    return;
  }

  const frag = document.createDocumentFragment();
  filtered.forEach(item => {
    frag.appendChild(createRowElement(item));
  });
  batchResultsList.appendChild(frag);
}

function createRowElement(item) {
  const isHit = item.status === 'HIT';
  const isTrang = Boolean(item.is_trang);
  const aov = item.aov || {};
  const sec = item.security || {};
  const creds = `${item.account}:${item.password}`;

  const row = document.createElement('div');
  row.className = `acc-row ${isTrang ? 'is-trang' : ''}`;

  let badgeHtml = '';
  if (isHit) {
    badgeHtml = isTrang 
      ? `<span class="badge-tag tag-trang">[ TRANG TTT ]</span>`
      : `<span class="badge-tag tag-dinh">[ CO TT: ${item.tinh_trang} ]</span>`;
  } else {
    badgeHtml = `<span class="badge-tag tag-fail">[ ${item.message || 'FAIL'} ]</span>`;
  }

  let skinsHtml = '';
  if (isHit) {
    const sss = aov.sss_list || [];
    const anime = aov.anime_list || [];
    const ss = aov.ss_list || [];

    if (sss.length || anime.length || ss.length) {
      skinsHtml = '<div class="row-skins">';
      if (sss.length) {
        skinsHtml += `<div class="skin-line-vip">SSS / THU NGUYEN (${sss.length}): ${sss.join(', ')}</div>`;
      }
      if (anime.length) {
        skinsHtml += `<div class="skin-line-anime">ANIME COLLAB (${anime.length}): ${anime.join(', ')}</div>`;
      }
      if (ss.length) {
        skinsHtml += `<div class="skin-line-ss">SS TUYET SAC (${ss.length}): ${ss.slice(0, 8).join(', ')}${ss.length > 8 ? '...' : ''}</div>`;
      }
      skinsHtml += '</div>';
    }
  }

  const fullText = formatItemFullText(item);

  // Parsed fields for fast visual summary
  const rank = aov.rank || 'Chưa rank';
  const stars = aov.stars || 0;
  const rankStr = stars > 0 ? `${rank} ${stars}*` : rank;

  const maskedEmail = (sec.masked_email || '').trim();
  const emailVerified = Boolean(sec.email_v);
  let emailStr = 'NO';
  if (maskedEmail && maskedEmail !== 'Trắng') {
    emailStr = emailVerified ? `${maskedEmail} (ĐÃ XT)` : `${maskedEmail} (CHƯA XT)`;
  }

  const maskedPhone = (sec.masked_phone || '').trim();
  const sdtStr = (!maskedPhone || maskedPhone === 'Trắng') ? 'NO' : maskedPhone;
  const cmndStr = sec.has_cccd ? 'YES' : 'NO';
  const authenStr = sec.auth_2fa ? 'YES' : 'NO';
  const fbStr = sec.fb_linked ? 'YES' : 'DIE';
  const lastLogin = item.last_login || 'Chưa rõ';

  row.innerHTML = `
    <div class="row-top">
      <div class="creds-box">
        <span class="creds-text">${creds}</span>
        <button class="btn-mini-copy" title="Copy User:Pass" onclick="navigator.clipboard.writeText('${creds}');showToast('ĐÃ COPY TK:MK');">TK:MK</button>
        <button class="btn-mini-copy btn-copy-full" title="Copy Toàn Bộ Thông Tin Acc" onclick="copyFullAccount(this);showToast('ĐÃ COPY TOÀN BỘ THÔNG TIN');">COPY FULL</button>
      </div>
      <div>${badgeHtml}</div>
    </div>
    ${isHit ? `
    <div class="row-data">
      <span>INGAME: <strong>${aov.name || 'Chưa đặt tên'}</strong></span>
      <span class="data-rank">RANK: <strong>${rankStr}</strong></span>
      <span class="data-champ">HERO: <strong>${aov.total_champs || 0}</strong></span>
      <span class="data-skin">SKIN: <strong>${aov.total_skins || 0}</strong></span>
      <span>SÒ: <strong>${item.shells || 0}</strong></span>
      <span>BAN: <strong>${aov.banned || 'KHÔNG'}</strong></span>
      <span>QG: <strong>${(item.country || 'VN').toUpperCase()}</strong></span>
    </div>
    <div class="row-sec">
      <span>MAIL: <strong>${emailStr}</strong></span>
      <span>SĐT: <strong>${sdtStr}</strong></span>
      <span>CMND: <strong>${cmndStr}</strong></span>
      <span>2FA: <strong>${authenStr}</strong></span>
      <span>FB: <strong>${fbStr}</strong></span>
      <span>LOGIN: <strong>${lastLogin}</strong></span>
    </div>
    ${skinsHtml}
    ` : ''}
  `;
  row.setAttribute('data-full', fullText);

  return row;
}

// ── Global Copy Helper ───────────────────────────────────────────────────────
window.copyFullAccount = function(btn) {
  const row = btn.closest('.acc-row');
  if (row) {
    const text = row.getAttribute('data-full') || '';
    if (text) {
      navigator.clipboard.writeText(text);
    }
  }
};


// ── Filter & Search Rules ────────────────────────────────────────────────────
function matchesFilterAndSearch(item) {
  // Filter tab
  if (currentFilter === 'trang' && !item.is_trang) return false;
  if (currentFilter === 'vip') {
    const sss = (item.aov && item.aov.sss_count) || 0;
    const ss = (item.aov && item.aov.ss_count) || 0;
    if (sss === 0 && ss === 0) return false;
  }
  if (currentFilter === 'live' && item.status !== 'HIT') return false;

  // Text search
  if (!currentSearch) return true;
  const q = currentSearch.toLowerCase();
  const acc = (item.account || '').toLowerCase();
  const name = ((item.aov && item.aov.name) || '').toLowerCase();
  const rank = ((item.aov && item.aov.rank) || '').toLowerCase();
  const sss = ((item.aov && item.aov.sss_list) || []).join(' ').toLowerCase();
  const anime = ((item.aov && item.aov.anime_list) || []).join(' ').toLowerCase();

  return acc.includes(q) || name.includes(q) || rank.includes(q) || sss.includes(q) || anime.includes(q);
}

// ── Counters Update ──────────────────────────────────────────────────────────
function updateCounters() {
  const total = allResults.length;
  const hits = allResults.filter(r => r.status === 'HIT');
  const trang = allResults.filter(r => r.is_trang);
  const vips = allResults.filter(r => (r.aov && ((r.aov.sss_count || 0) > 0 || (r.aov.ss_count || 0) > 0)));

  statTotal.textContent = total;
  statHits.textContent = hits.length;
  statTrang.textContent = trang.length;
  statSkinVIP.textContent = vips.length;

  countFilterAll.textContent = total;
  countFilterTrang.textContent = trang.length;
  countFilterVip.textContent = vips.length;
  countFilterLive.textContent = hits.length;
}

// ── Tab Filters Switcher ────────────────────────────────────────────────────
tabFilters.forEach(tab => {
  tab.addEventListener('click', () => {
    tabFilters.forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
    currentFilter = tab.getAttribute('data-filter');
    renderAllItems();
  });
});

filterSearch.addEventListener('input', (e) => {
  currentSearch = e.target.value.trim();
  renderAllItems();
});

// ── Helper to Format Full Account String (Exact Format) ──────────────────────
function formatItemFullText(item) {
  const isHit = item.status === 'HIT';
  const aov = item.aov || {};
  const sec = item.security || {};

  if (!isHit) {
    return `${item.account}:${item.password} | STATUS : ${item.status} | DETAIL : ${item.message || 'Thất bại'}`;
  }

  const name = aov.name || 'Chưa đặt tên';
  const stars = aov.stars || 0;
  const rank = aov.rank || 'Chưa Đấu Hạng';
  const rankStr = stars > 0 ? `${rank} ${stars} sao` : rank;
  const level = aov.level || 0;
  const hero = aov.total_champs || 0;
  const skin = aov.total_skins || 0;
  const ban = aov.banned || 'KHÔNG';

  // Email
  const maskedEmail = (sec.masked_email || '').trim();
  const emailVerified = Boolean(sec.email_v);
  let emailStr = 'NO [CHƯA LIÊN KẾT]';
  if (maskedEmail && maskedEmail !== 'Trắng') {
    emailStr = emailVerified ? `YES [${maskedEmail} - ĐÃ XÁC THỰC]` : `NO [${maskedEmail} - CHƯA XÁC THỰC]`;
  }

  // SDT
  const maskedPhone = (sec.masked_phone || '').trim();
  const sdtStr = (!maskedPhone || maskedPhone === 'Trắng') ? 'NO' : `YES [${maskedPhone}]`;

  // CMND / CCCD
  const cmndStr = sec.has_cccd ? 'YES' : 'NO';

  // AUTHEN 2FA
  const authenStr = sec.auth_2fa ? 'YES' : 'NO';

  // FB
  const fbStr = sec.fb_linked ? 'YES' : 'DIE';

  // SO
  const shells = item.shells || 0;

  // QUOC GIA
  const country = (item.country || 'VN').toUpperCase();

  // LOGIN LAN CUOI
  const lastLogin = item.last_login || 'Chưa ghi nhận';

  // SS
  const ssList = aov.ss_list || [];
  const ssStr = `${ssList.length} [${ssList.join(', ')}]`;

  // SSS
  const sssList = aov.sss_list || [];
  const sssStr = `${sssList.length} [${sssList.join(', ')}]`;

  // ANIME
  const animeList = aov.anime_list || [];
  const animeStr = `${animeList.length} [${animeList.join(', ')}]`;

  // OTHER
  const otherList = aov.other_list || [];
  const otherStr = `${otherList.length} [${otherList.slice(0, 10).join(', ')}${otherList.length > 10 ? '...' : ''}]`;

  // TRANG THAI
  const trangThai = (item.tinh_trang || 'CÓ THÔNG TIN').toUpperCase();

  return `${item.account}:${item.password} | NAME :${name} | RANK : ${rankStr} | LEVEL : ${level} | HERO : ${hero} | SKIN : ${skin} | BAN : ${ban} | EMAIL : ${emailStr} | SDT : ${sdtStr} | CMND : ${cmndStr} | AUTHEN : ${authenStr} | FB : ${fbStr} | SÒ : ${shells} | QUỐC GIA : ${country} | LOGIN LẦN CUỐI : ${lastLogin} | SS : ${ssStr} | SSS : ${sssStr} | ANIME : ${animeStr} | OTHER : ${otherStr} | TRẠNG THÁI : ${trangThai}`;
}

// ── Copy & Export File Operations ────────────────────────────────────────────
btnCopyView.addEventListener('click', () => {
  const activeItems = allResults.filter(matchesFilterAndSearch);
  if (activeItems.length === 0) {
    showToast('KHONG CO DU LIEU DE COPY');
    return;
  }

  const text = activeItems.map(formatItemFullText).join('\n');
  navigator.clipboard.writeText(text);
  showToast(`DA COPY DAY DU THONG TIN ${activeItems.length} ACC`);
});

btnExportTrang.addEventListener('click', () => {
  const trangItems = allResults.filter(r => r.is_trang);
  if (trangItems.length === 0) {
    showToast('CHUA CO ACC TRANG NAO');
    return;
  }

  const text = trangItems.map(formatItemFullText).join('\n');
  downloadFile('acc_trang_lienquan_full.txt', text);
  showToast(`DA TAI FILE ACC TRANG FULL INFO (${trangItems.length} ACC)`);
});

btnExportAll.addEventListener('click', () => {
  const hitItems = allResults.filter(r => r.status === 'HIT');
  if (hitItems.length === 0) {
    showToast('CHUA CO ACC LIVE NAO');
    return;
  }

  const text = hitItems.map(formatItemFullText).join('\n');
  downloadFile('hit_live_lienquan_full.txt', text);
  showToast(`DA TAI FILE HIT LIVE FULL INFO (${hitItems.length} ACC)`);
});

function downloadFile(filename, content) {
  const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
