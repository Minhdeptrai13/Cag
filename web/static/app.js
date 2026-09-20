/**
 * AOV Studio Playground - Master Frontend Engine
 * Handles Landing View, Studio Workspace, Interactive API Tester,
 * Multi-thread Batch Checker, Check History, and Billing/Giftcodes.
 */

// ── Global App State ────────────────────────────────────────────────────────
let currentUser = null;
let currentApiKey = null;
let activeTaskId = null;
let pollInterval = null;
let allResults = [];
let currentFilter = 'all';
let currentSearch = '';
let currentHistoryList = [];
let currentHistFilter = 'all';
let currentSnippetLang = 'python';

// ── DOM References ──────────────────────────────────────────────────────────
const landingView = document.getElementById('landingView');
const studioView = document.getElementById('studioView');
const authModal = document.getElementById('authModal');
const toast = document.getElementById('toast');

// Landing Elements
const btnLandingLogin = document.getElementById('btnLandingLogin');
const btnLandingDocs = document.getElementById('btnLandingDocs');
const btnHeroOpenStudio = document.getElementById('btnHeroOpenStudio');
const btnHeroRegister = document.getElementById('btnHeroRegister');

// Studio Header
const studioUsername = document.getElementById('studioUsername');
const studioUserRole = document.getElementById('studioUserRole');
const studioCredits = document.getElementById('studioCredits');
const studioUserAvatar = document.getElementById('studioUserAvatar');
const btnStudioLogout = document.getElementById('btnStudioLogout');

// Sidebar Nav
const navItems = document.querySelectorAll('.nav-item');
const tabPanes = document.querySelectorAll('.tab-pane');

// Auth Form
const btnCloseAuthModal = document.getElementById('btnCloseAuthModal');
const tabLoginBtn = document.getElementById('tabLoginBtn');
const tabRegisterBtn = document.getElementById('tabRegisterBtn');
const loginForm = document.getElementById('loginForm');
const registerForm = document.getElementById('registerForm');
const loginError = document.getElementById('loginError');
const regError = document.getElementById('regError');

// Checker Studio DOM
const btnModeBatch = document.getElementById('btnModeBatch');
const btnModeSingle = document.getElementById('btnModeSingle');
const batchStreamPane = document.getElementById('batchStreamPane');
const singleTestPane = document.getElementById('singleTestPane');

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
const countFilterAll = document.getElementById('countFilterAll');
const countFilterTrang = document.getElementById('countFilterTrang');
const countFilterVip = document.getElementById('countFilterVip');
const countFilterLive = document.getElementById('countFilterLive');
const btnCopyView = document.getElementById('btnCopyView');
const btnExportTrang = document.getElementById('btnExportTrang');
const btnExportAll = document.getElementById('btnExportAll');

// Single Quick Test DOM
const singleAcc = document.getElementById('singleAcc');
const singlePass = document.getElementById('singlePass');
const btnRunSingle = document.getElementById('btnRunSingle');
const singleResultBox = document.getElementById('singleResultBox');
const singleHeader = document.getElementById('singleHeader');
const singleStatusTag = document.getElementById('singleStatusTag');
const singleAccLabel = document.getElementById('singleAccLabel');
const singleBody = document.getElementById('singleBody');

// API Playground DOM
const displayApiKey = document.getElementById('displayApiKey');
const btnCopyApiKey = document.getElementById('btnCopyApiKey');
const btnGenNewApiKey = document.getElementById('btnGenNewApiKey');
const testComboInput = document.getElementById('testComboInput');
const btnSendTestApi = document.getElementById('btnSendTestApi');
const testResponseWrap = document.getElementById('testResponseWrap');
const testResponseCode = document.getElementById('testResponseCode');
const testLatency = document.getElementById('testLatency');
const codeTabs = document.querySelectorAll('.code-tab');
const snippetCode = document.getElementById('snippetCode');
const btnCopySnippet = document.getElementById('btnCopySnippet');

// History DOM
const histCount = document.getElementById('histCount');
const btnRefreshHistory = document.getElementById('btnRefreshHistory');
const btnExportHistory = document.getElementById('btnExportHistory');
const btnClearHistory = document.getElementById('btnClearHistory');
const histFilterBtns = document.querySelectorAll('[data-hist-filter]');
const historyTableBody = document.getElementById('historyTableBody');

// Billing DOM
const quotaBigNumber = document.getElementById('quotaBigNumber');
const quotaTierLabel = document.getElementById('quotaTierLabel');
const redeemStudioForm = document.getElementById('redeemStudioForm');
const redeemStudioInput = document.getElementById('redeemStudioInput');
const redeemStudioError = document.getElementById('redeemStudioError');

// ── Toast System ────────────────────────────────────────────────────────────
function showToast(msg, duration = 2500) {
  if (!toast) return;
  toast.textContent = msg;
  toast.classList.add('show');
  setTimeout(() => toast.classList.remove('show'), duration);
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

// ── Auth & View Switcher ────────────────────────────────────────────────────
function initApp() {
  const saved = localStorage.getItem('aov_user');
  if (saved) {
    try {
      currentUser = JSON.parse(saved);
      showStudioView();
      refreshUserMeta();
    } catch (e) {
      localStorage.removeItem('aov_user');
      showLandingView();
    }
  } else {
    showLandingView();
  }
}

function showLandingView() {
  if (landingView) landingView.style.display = 'block';
  if (studioView) studioView.style.display = 'none';
}

function showStudioView() {
  if (landingView) landingView.style.display = 'none';
  if (studioView) studioView.style.display = 'flex';
  renderUserHeader();
  loadUserApiKeys();
  updateCodeSnippets();
}

function renderUserHeader() {
  if (!currentUser) return;
  if (studioUsername) studioUsername.textContent = currentUser.username || 'User';
  if (studioUserRole) studioUserRole.textContent = (currentUser.role || 'FREE').toUpperCase();
  if (studioCredits) studioCredits.textContent = (currentUser.credits !== undefined && currentUser.credits !== null ? currentUser.credits : 0);
  if (studioUserAvatar) studioUserAvatar.textContent = (currentUser.username || 'U')[0].toUpperCase();
  if (quotaBigNumber) quotaBigNumber.textContent = (currentUser.credits !== undefined && currentUser.credits !== null ? currentUser.credits : 0);
  if (quotaTierLabel) quotaTierLabel.textContent = (currentUser.role || 'FREE').toUpperCase() + ' PLAN';
}

async function refreshUserMeta() {
  if (!currentUser) return;
  try {
    const res = await fetch(`/api/v1/user/me?user_id=${currentUser.id}`);
    const data = await res.json();
    if (data.success || data.status === 'ok') {
      const u = data.user || {};
      currentUser.credits = (u.credits !== undefined && u.credits !== null ? u.credits : currentUser.credits);
      currentUser.role = (u.role !== undefined && u.role !== null ? u.role : currentUser.role);
      if (u.api_key) currentApiKey = u.api_key;
      localStorage.setItem('aov_user', JSON.stringify(currentUser));
      renderUserHeader();
      updateCodeSnippets();
      if (displayApiKey && currentApiKey) displayApiKey.value = currentApiKey;
    }
  } catch (e) {
    console.error('Refresh user error:', e);
  }
}

// Open Auth Modal
function openAuthModal(isRegister = false) {
  if (loginError) loginError.style.display = 'none';
  if (regError) regError.style.display = 'none';
  if (isRegister) {
    (tabRegisterBtn && tabRegisterBtn.click)();
  } else {
    (tabLoginBtn && tabLoginBtn.click)();
  }
  if (authModal) authModal.style.display = 'flex';
}

(btnLandingLogin && btnLandingLogin.addEventListener)('click', () => openAuthModal(false));
(btnHeroOpenStudio && btnHeroOpenStudio.addEventListener)('click', () => {
  if (currentUser) showStudioView();
  else openAuthModal(false);
});
(btnHeroRegister && btnHeroRegister.addEventListener)('click', () => openAuthModal(true));
(btnLandingDocs && btnLandingDocs.addEventListener)('click', () => {
  if (currentUser) {
    showStudioView();
    switchTab('api');
  } else {
    openAuthModal(false);
  }
});

(btnCloseAuthModal && btnCloseAuthModal.addEventListener)('click', () => {
  if (authModal) authModal.style.display = 'none';
});

(tabLoginBtn && tabLoginBtn.addEventListener)('click', () => {
  tabLoginBtn.classList.add('active');
  tabRegisterBtn.classList.remove('active');
  loginForm.style.display = 'flex';
  registerForm.style.display = 'none';
});

(tabRegisterBtn && tabRegisterBtn.addEventListener)('click', () => {
  tabRegisterBtn.classList.add('active');
  tabLoginBtn.classList.remove('active');
  loginForm.style.display = 'none';
  registerForm.style.display = 'flex';
});

// Login Submit
(loginForm && loginForm.addEventListener)('submit', async (e) => {
  e.preventDefault();
  if (loginError) loginError.style.display = 'none';
  const username = document.getElementById('loginUser').value.trim();
  const password = document.getElementById('loginPass').value;

  try {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password })
    });
    const data = await res.json();
    if (data.success || data.status === 'ok') {
      currentUser = data.user;
      currentApiKey = data.user.api_key || data.user.key;
      localStorage.setItem('aov_user', JSON.stringify(currentUser));
      if (authModal) authModal.style.display = 'none';
      showStudioView();
      showToast(`XIN CHÀO ${currentUser.username.toUpperCase()}!`);
    } else {
      if (loginError) {
        loginError.textContent = data.error || data.message || 'Đăng nhập thất bại!';
        loginError.style.display = 'block';
      }
    }
  } catch (err) {
    if (loginError) {
      loginError.textContent = 'Lỗi kết nối đến máy chủ';
      loginError.style.display = 'block';
    }
  }
});

// Register Submit
(registerForm && registerForm.addEventListener)('submit', async (e) => {
  e.preventDefault();
  if (regError) regError.style.display = 'none';
  const username = document.getElementById('regUser').value.trim();
  const password = document.getElementById('regPass').value;

  try {
    const res = await fetch('/api/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password })
    });
    const data = await res.json();
    if (data.success || data.status === 'ok') {
      currentUser = data.user;
      currentApiKey = data.user ? (data.user.api_key || data.user.key) : data.api_key;
      localStorage.setItem('aov_user', JSON.stringify(currentUser));
      if (authModal) authModal.style.display = 'none';
      showStudioView();
      showToast('TẠO TÀI KHOẢN THÀNH CÔNG! BẠN ĐƯỢC TẶNG 50 CREDITS');
    } else {
      if (regError) {
        regError.textContent = data.error || data.message || 'Đăng ký thất bại!';
        regError.style.display = 'block';
      }
    }
  } catch (err) {
    if (regError) {
      regError.textContent = 'Lỗi kết nối đến máy chủ';
      regError.style.display = 'block';
    }
  }
});

(btnStudioLogout && btnStudioLogout.addEventListener)('click', () => {
  currentUser = null;
  currentApiKey = null;
  localStorage.removeItem('aov_user');
  showLandingView();
  showToast('ĐÃ ĐĂNG XUẤT');
});

// ── Sidebar Tabs Switcher ───────────────────────────────────────────────────
function switchTab(tabName) {
  navItems.forEach(btn => {
    if (btn.getAttribute('data-tab') === tabName) btn.classList.add('active');
    else btn.classList.remove('active');
  });

  tabPanes.forEach(pane => {
    if (pane.id === `tab${tabName.charAt(0).toUpperCase() + tabName.slice(1)}`) {
      pane.classList.add('active');
    } else {
      pane.classList.remove('active');
    }
  });

  if (tabName === 'history') {
    loadCheckHistory(currentHistFilter);
  } else if (tabName === 'api') {
    loadUserApiKeys();
  }
}

navItems.forEach(btn => {
  btn.addEventListener('click', () => {
    const t = btn.getAttribute('data-tab');
    switchTab(t);
  });
});

// ── Mode Switcher (Batch Stream vs Single Quick Test) ───────────────────────
(btnModeBatch && btnModeBatch.addEventListener)('click', () => {
  btnModeBatch.classList.add('active');
  btnModeSingle.classList.remove('active');
  batchStreamPane.style.display = 'grid';
  singleTestPane.style.display = 'none';
});

(btnModeSingle && btnModeSingle.addEventListener)('click', () => {
  btnModeSingle.classList.add('active');
  btnModeBatch.classList.remove('active');
  batchStreamPane.style.display = 'none';
  singleTestPane.style.display = 'block';
});

// ── Single Quick Test ───────────────────────────────────────────────────────
(btnRunSingle && btnRunSingle.addEventListener)('click', async () => {
  const acc = singleAcc.value.trim();
  const pwd = singlePass.value.trim();
  if (!acc || !pwd) {
    showToast('VUI LÒNG NHẬP TÀI KHOẢN VÀ MẬT KHẨU');
    return;
  }

  const btnText = document.getElementById('singleBtnText');
  const btnLoader = document.getElementById('singleBtnLoader');
  btnText.style.display = 'none';
  btnLoader.style.display = 'inline';
  btnRunSingle.disabled = true;

  try {
    const res = await fetch('/api/check-single', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ account: acc, password: pwd, user_id: currentUser ? currentUser.id : null })
    });
    const data = await res.json();
    singleResultBox.style.display = 'block';
    singleAccLabel.textContent = `${acc}:${pwd}`;

    if (data.status === 'HIT') {
      singleStatusTag.className = 'status-tag hit';
      singleStatusTag.textContent = data.is_trang ? 'HIT LIVE (TRẮNG TTT)' : 'HIT LIVE (CÓ TTT)';
      singleBody.innerHTML = `
        <div><strong>INGAME:</strong> ${escapeHtml(data.ingame || 'None')}</div>
        <div><strong>RANK:</strong> <span style="color:var(--gold)">${escapeHtml(data.rank || 'Unranked')}</span></div>
        <div><strong>TƯỚNG:</strong> ${data.heroes_count || 0} | <strong>SKIN:</strong> ${data.skins_count || 0}</div>
        <div><strong>SKIN VIP/SSS:</strong> <span style="color:var(--gold)">${escapeHtml(data.skins_vip || 'Không có')}</span></div>
        <div><strong>THÔNG TIN:</strong> ${escapeHtml(data.tt_info || '')}</div>
      `;
    } else {
      singleStatusTag.className = 'status-tag invalid';
      singleStatusTag.textContent = data.status || 'FAIL';
      singleBody.innerHTML = `<div style="color:var(--red)">${escapeHtml(data.message || 'Kiểm tra thất bại')}</div>`;
    }

    refreshUserMeta();
  } catch (e) {
    showToast('LỖI KẾT NỐI SERVER');
  } finally {
    btnText.style.display = 'inline';
    btnLoader.style.display = 'none';
    btnRunSingle.disabled = false;
  }
});

// ── Batch Stream Checker ────────────────────────────────────────────────────
(uploadZone && uploadZone.addEventListener)('click', () => fileInput.click());
(fileInput && fileInput.addEventListener)('change', (e) => {
  const file = e.target.files[0];
  if (file) handleLoadedFile(file);
});

(uploadZone && uploadZone.addEventListener)('dragover', (e) => {
  e.preventDefault();
  uploadZone.style.borderColor = 'var(--cyan)';
});
(uploadZone && uploadZone.addEventListener)('dragleave', () => {
  uploadZone.style.borderColor = 'var(--glass-border)';
});
(uploadZone && uploadZone.addEventListener)('drop', (e) => {
  e.preventDefault();
  uploadZone.style.borderColor = 'var(--glass-border)';
  const file = e.dataTransfer.files[0];
  if (file) handleLoadedFile(file);
});

function handleLoadedFile(file) {
  if (fileChosen) fileChosen.textContent = `[ ${file.name} - ${(file.size / 1024).toFixed(1)} KB ]`;
  const reader = new FileReader();
  reader.onload = (ev) => {
    batchText.value = ev.target.result;
    showToast(`ĐÃ NẠP FILE: ${file.name}`);
  };
  reader.readAsText(file);
}

(btnClearBatch && btnClearBatch.addEventListener)('click', () => {
  batchText.value = '';
  if (fileChosen) fileChosen.textContent = '';
  if (fileInput) fileInput.value = '';
  showToast('ĐÃ XÓA TRẮNG');
});

(btnStartBatch && btnStartBatch.addEventListener)('click', async () => {
  const text = batchText.value.trim();
  if (!text) {
    showToast('VUI LÒNG DÁN COMBO HOẶC CHỌN FILE .TXT');
    return;
  }

  const lines = text.split('\n')
    .map(l => l.trim())
    .filter(l => l && !l.startsWith('#') && (/[:|;\t\s/]/.test(l)));

  if (lines.length === 0) {
    showToast('KHÔNG TÌM THẤY DÒNG COMBO HỢP LỆ');
    return;
  }

  const threads = parseInt(threadInput.value, 10) || 10;

  // Reset Console
  allResults = [];
  batchResultsList.innerHTML = '';
  updateCounters();

  document.getElementById('btnBatchText').style.display = 'none';
  document.getElementById('btnBatchLoader').style.display = 'inline-block';
  btnStartBatch.disabled = true;

  progressWrap.style.display = 'block';
  progressBarFill.style.width = '0%';
  progressStatus.textContent = 'Khởi động luồng...';
  progressRatio.textContent = `0/${lines.length} (0%)`;

  try {
    const resp = await fetch('/api/check-batch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        combos: lines,
        threads: threads,
        user_id: currentUser ? currentUser.id : null
      })
    });

    const data = await resp.json();
    if (data.error) {
      showToast('LỖI: ' + data.error);
      resetBatchUI();
      return;
    }

    activeTaskId = data.task_id;
    startTaskPolling(activeTaskId);
  } catch (err) {
    showToast('LỖI KẾT NỐI ĐẾN SERVER');
    resetBatchUI();
  }
});

function resetBatchUI() {
  document.getElementById('btnBatchText').style.display = 'inline-block';
  document.getElementById('btnBatchLoader').style.display = 'none';
  btnStartBatch.disabled = false;
}

function startTaskPolling(taskId) {
  if (pollInterval) clearInterval(pollInterval);

  pollInterval = setInterval(async () => {
    try {
      const resp = await fetch(`/api/task-status?task_id=${taskId}`);
      const data = await resp.json();

      if (data.error) {
        clearInterval(pollInterval);
        showToast('LỖI TIẾN TRÌNH: ' + data.error);
        resetBatchUI();
        return;
      }

      const total = data.total || 1;
      const done = data.done || 0;
      const pct = Math.min(100, Math.round((done / total) * 100));

      progressBarFill.style.width = `${pct}%`;
      progressRatio.textContent = `${done}/${total} (${pct}%)`;
      progressStatus.textContent = data.is_running ? `Đang quét (${done}/${total})...` : 'Hoàn thành!';

      const results = data.results || [];
      if (results.length > allResults.length) {
        const newItems = results.slice(allResults.length);
        allResults = results;
        renderNewBatchItems(newItems);
        updateCounters();
      }

      if (data.status === 'DONE') {
        clearInterval(pollInterval);
        resetBatchUI();
        const hitCount = (data.hits !== undefined && data.hits !== null ? data.hits : 0);
        const trangCount = (data.trang !== undefined && data.trang !== null ? data.trang : 0);
        showToast(`HOÀN THÀNH BATCH: ${hitCount} SỐNG / ${trangCount} TRẮNG TTT`);
        refreshUserMeta();
      }
    } catch (e) {
      console.error('Polling error:', e);
    }
  }, 700);
}

function renderNewBatchItems(items) {
  const empty = batchResultsList.querySelector('.empty-state');
  if (empty) empty.remove();

  const frag = document.createDocumentFragment();
  items.forEach(it => {
    if (matchesFilter(it)) {
      frag.appendChild(createRowElement(it));
    }
  });
  batchResultsList.prepend(frag);
}

function createRowElement(item) {
  const div = document.createElement('div');
  const isHit = item.status === 'HIT';
  const isTrang = Boolean(item.is_trang);

  let cls = 'acc-row ';
  if (isHit) cls += isTrang ? 'row-trang' : 'row-hit';
  else cls += 'row-invalid';
  div.className = cls;

  const accStr = `${item.account}:${item.password}`;
  if (isHit) {
    div.innerHTML = `
      <div class="row-head">
        <span class="acc-tag ${isTrang ? 'trang' : 'hit'}">${isTrang ? 'TRẮNG TTT' : 'HIT LIVE'}</span>
        <code>${escapeHtml(accStr)}</code>
      </div>
      <div class="acc-info-line">
        [ ${escapeHtml(item.ingame || 'NoName')} ] | RANK: ${escapeHtml(item.rank || 'None')} | TƯỚNG: ${item.heroes_count || 0} | SKIN: ${item.skins_count || 0}
      </div>
      ${item.skins_vip ? `<div class="acc-skins-line">★ VIP: ${escapeHtml(item.skins_vip)}</div>` : ''}
    `;
  } else {
    div.innerHTML = `
      <div class="row-head">
        <span class="acc-tag invalid">${escapeHtml(item.status)}</span>
        <code>${escapeHtml(accStr)}</code>
      </div>
      <div style="color:var(--text-muted);font-size:11px;">${escapeHtml(item.message || 'FAIL')}</div>
    `;
  }
  return div;
}

function matchesFilter(item) {
  const isHit = item.status === 'HIT';
  const isTrang = Boolean(item.is_trang);
  const isVip = Boolean(item.skins_vip);

  if (currentFilter === 'trang' && (!isHit || !isTrang)) return false;
  if (currentFilter === 'vip' && (!isHit || !isVip)) return false;
  if (currentFilter === 'live' && !isHit) return false;

  if (currentSearch) {
    const full = JSON.stringify(item).toLowerCase();
    if (!full.includes(currentSearch)) return false;
  }
  return true;
}

function updateCounters() {
  const total = allResults.length;
  let hits = 0, trang = 0, vip = 0;
  allResults.forEach(r => {
    if (r.status === 'HIT') {
      hits++;
      if (r.is_trang) trang++;
      if (r.skins_vip) vip++;
    }
  });

  if (countFilterAll) countFilterAll.textContent = total;
  if (countFilterTrang) countFilterTrang.textContent = trang;
  if (countFilterVip) countFilterVip.textContent = vip;
  if (countFilterLive) countFilterLive.textContent = hits;
}

tabFilters.forEach(btn => {
  btn.addEventListener('click', () => {
    tabFilters.forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    currentFilter = btn.getAttribute('data-filter');
    renderFilteredBatchList();
  });
});

(filterSearch && filterSearch.addEventListener)('input', (e) => {
  currentSearch = e.target.value.toLowerCase().trim();
  renderFilteredBatchList();
});

function renderFilteredBatchList() {
  batchResultsList.innerHTML = '';
  const filtered = allResults.filter(matchesFilter);
  if (filtered.length === 0) {
    batchResultsList.innerHTML = `<div class="empty-state">[ KHÔNG CÓ TÀI KHOẢN PHÙ HỢP BỘ LỌC ]</div>`;
    return;
  }
  const frag = document.createDocumentFragment();
  filtered.forEach(it => frag.appendChild(createRowElement(it)));
  batchResultsList.appendChild(frag);
}

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

(btnExportAll && btnExportAll.addEventListener)('click', () => {
  const hits = allResults.filter(r => r.status === 'HIT');
  if (hits.length === 0) {
    showToast('CHƯA CÓ HIT NÀO ĐỂ LƯU');
    return;
  }
  let txt = '=== DANH SÁCH ACC AOV HIT LIVE ===\n\n';
  hits.forEach(r => {
    txt += `${r.account}:${r.password} | RANK: ${r.rank || 'None'} | TƯỚNG: ${r.heroes_count} | SKIN: ${r.skins_count} | TRẮNG TTT: ${r.is_trang ? 'YES' : 'NO'}\n`;
  });
  downloadFile(`aov_all_hits_${Date.now()}.txt`, txt);
  showToast(`ĐÃ LƯU ${hits.length} HIT LIVE`);
});

(btnExportTrang && btnExportTrang.addEventListener)('click', () => {
  const trangs = allResults.filter(r => r.status === 'HIT' && r.is_trang);
  if (trangs.length === 0) {
    showToast('CHƯA CÓ ACC TRẮNG NÀO ĐỂ LƯU');
    return;
  }
  let txt = '=== DANH SÁCH ACC AOV TRẮNG TTT ===\n\n';
  trangs.forEach(r => {
    txt += `${r.account}:${r.password} | RANK: ${r.rank || 'None'} | TƯỚNG: ${r.heroes_count} | SKIN: ${r.skins_count}\n`;
  });
  downloadFile(`aov_acc_trang_${Date.now()}.txt`, txt);
  showToast(`ĐÃ LƯU ${trangs.length} ACC TRẮNG`);
});

(btnCopyView && btnCopyView.addEventListener)('click', () => {
  const filtered = allResults.filter(matchesFilter);
  if (filtered.length === 0) {
    showToast('KHÔNG CÓ TÀI KHOẢN ĐỂ COPY');
    return;
  }
  const lines = filtered.map(r => `${r.account}:${r.password}`);
  navigator.clipboard.writeText(lines.join('\n'));
  showToast(`ĐÃ COPY ${filtered.length} COMBO ĐANG XEM`);
});

// ── API Keys & Code Playground ──────────────────────────────────────────────
async function loadUserApiKeys() {
  if (!currentUser) return;
  try {
    const res = await fetch(`/api/user/keys?user_id=${currentUser.id}`);
    const data = await res.json();
    if (data.success || data.status === 'ok') {
      const keys = data.keys || [];
      if (keys.length > 0) {
        currentApiKey = keys[0].api_key || keys[0].key;
      } else {
        currentApiKey = 'Chưa có API Key';
      }
      if (displayApiKey) displayApiKey.value = currentApiKey;
      updateCodeSnippets();
    }
  } catch (e) {
    console.error('Error load keys:', e);
  }
}

(btnCopyApiKey && btnCopyApiKey.addEventListener)('click', () => {
  if (displayApiKey && displayApiKey.value) {
    navigator.clipboard.writeText(displayApiKey.value);
    showToast('ĐÃ COPY API KEY!');
  }
});

(btnGenNewApiKey && btnGenNewApiKey.addEventListener)('click', async () => {
  if (!currentUser) return;
  if (!confirm('Bạn có chắc chắn muốn tạo API Key mới không?')) return;
  try {
    const res = await fetch('/api/keys/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: currentUser.id })
    });
    const data = await res.json();
    if (data.success || data.status === 'ok') {
      currentApiKey = data.api_key || data.key;
      if (displayApiKey) displayApiKey.value = currentApiKey;
      updateCodeSnippets();
      showToast('ĐÃ TẠO API KEY MỚI THÀNH CÔNG!');
    }
  } catch (e) {
    showToast('Lỗi khi tạo API key mới');
  }
});

// Interactive API Tester
(btnSendTestApi && btnSendTestApi.addEventListener)('click', async () => {
  const combo = testComboInput.value.trim();
  if (!combo) {
    showToast('HÃY NHẬP TÀI KHOẢN TEST (user:pass)');
    return;
  }

  const btnText = document.getElementById('testApiBtnText');
  const btnLoader = document.getElementById('testApiBtnLoader');
  btnText.style.display = 'none';
  btnLoader.style.display = 'inline';
  btnSendTestApi.disabled = true;

  const startTime = performance.now();

  try {
    const res = await fetch('/api/v1/check', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${currentApiKey || ''}`
      },
      body: JSON.stringify({ account: combo })
    });
    const elapsed = Math.round(performance.now() - startTime);
    const jsonRes = await res.json();

    testResponseWrap.style.display = 'block';
    testLatency.textContent = `${elapsed} ms`;
    testResponseCode.textContent = JSON.stringify(jsonRes, null, 2);

    refreshUserMeta();
    showToast('ĐÃ NHẬN RESPONSE TỪ API!');
  } catch (e) {
    showToast('LỖI GỌI API TEST');
  } finally {
    btnText.style.display = 'inline';
    btnLoader.style.display = 'none';
    btnSendTestApi.disabled = false;
  }
});

// Code Snippets Generators
codeTabs.forEach(tab => {
  tab.addEventListener('click', () => {
    codeTabs.forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
    currentSnippetLang = tab.getAttribute('data-lang');
    updateCodeSnippets();
  });
});

function updateCodeSnippets() {
  const domain = window.location.origin;
  const key = currentApiKey || 'YOUR_API_KEY';
  let code = '';

  if (currentSnippetLang === 'python') {
    code = `import requests

url = "${domain}/api/v1/check"
headers = {
    "Authorization": "Bearer ${key}",
    "Content-Type": "application/json"
}
payload = {
    "account": "user123:password456"
}

response = requests.post(url, headers=headers, json=payload)
data = response.json()

print("Status:", data.get("status"))
print("Formatted:", data.get("formatted"))
print("Data:", data.get("data"))`;
  } else if (currentSnippetLang === 'curl') {
    code = `curl -X POST ${domain}/api/v1/check \\
  -H "Authorization: Bearer ${key}" \\
  -H "Content-Type: application/json" \\
  -d '{"account":"user123:password456"}'`;
  } else if (currentSnippetLang === 'nodejs') {
    code = `const axios = require('axios');

async function checkAccount() {
  try {
    const res = await axios.post('${domain}/api/v1/check', {
      account: 'user123:password456'
    }, {
      headers: {
        'Authorization': 'Bearer ${key}',
        'Content-Type': 'application/json'
      }
    });
    console.log(res.data);
  } catch (err) {
    console.error(err.response ? err.response.data : err.message);
  }
}

checkAccount();`;
  } else if (currentSnippetLang === 'golang') {
    code = `package main

import (
	"bytes"
	"fmt"
	"io"
	"net/http"
)

func main() {
	url := "${domain}/api/v1/check"
	payload := []byte(\`{"account":"user123:password456"}\`)

	req, _ := http.NewRequest("POST", url, bytes.NewBuffer(payload))
	req.Header.Set("Authorization", "Bearer ${key}")
	req.Header.Set("Content-Type", "application/json")

	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		panic(err)
	}
	defer resp.Body.Close()

	body, _ := io.ReadAll(resp.Body)
	fmt.Println(string(body))
}`;
  } else if (currentSnippetLang === 'php') {
    code = `<?php
$curl = curl_init();

curl_setopt_array($curl, array(
  CURLOPT_URL => '${domain}/api/v1/check',
  CURLOPT_RETURNTRANSFER => true,
  CURLOPT_CUSTOMREQUEST => 'POST',
  CURLOPT_POSTFIELDS => json_encode(['account' => 'user123:password456']),
  CURLOPT_HTTPHEADER => array(
    'Authorization: Bearer ${key}',
    'Content-Type: application/json'
  ),
));

$response = curl_exec($curl);
curl_close($curl);
echo $response;
?>`;
  }

  if (snippetCode) snippetCode.textContent = code;
}

(btnCopySnippet && btnCopySnippet.addEventListener)('click', () => {
  if (snippetCode) {
    navigator.clipboard.writeText(snippetCode.textContent);
    showToast('ĐÃ COPY CODE MẪU!');
  }
});

// ── Check History Logs ──────────────────────────────────────────────────────
histFilterBtns.forEach(btn => {
  btn.addEventListener('click', () => {
    histFilterBtns.forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    currentHistFilter = btn.getAttribute('data-hist-filter') || 'all';
    loadCheckHistory(currentHistFilter);
  });
});

(btnRefreshHistory && btnRefreshHistory.addEventListener)('click', () => loadCheckHistory(currentHistFilter));

async function loadCheckHistory(filter = 'all') {
  if (!currentUser) return;
  historyTableBody.innerHTML = '<tr><td colspan="7" class="text-center">[ ĐANG TẢI DỮ LIỆU LỊCH SỬ... ]</td></tr>';
  try {
    const res = await fetch(`/api/user/history?user_id=${currentUser.id}&status=${filter}`);
    const data = await res.json();
    if (data.success || data.status === 'ok') {
      currentHistoryList = data.history || [];
      if (histCount) histCount.textContent = currentHistoryList.length;
      renderHistoryTable(currentHistoryList);
    }
  } catch (e) {
    historyTableBody.innerHTML = '<tr><td colspan="7" class="text-center">[ LỖI KẾT NỐI TẢI LỊCH SỬ ]</td></tr>';
  }
}

function renderHistoryTable(items) {
  if (items.length === 0) {
    historyTableBody.innerHTML = '<tr><td colspan="7" class="text-center">[ CHƯA CÓ LỊCH SỬ CHECK NÀO ]</td></tr>';
    return;
  }
  let html = '';
  items.forEach(it => {
    const isHit = it.status === 'HIT';
    const isTrang = Boolean(it.is_trang);
    const statusColor = isHit ? (isTrang ? 'var(--cyan)' : 'var(--green)') : 'var(--red)';
    const timeStr = it.created_at ? new Date(it.created_at * 1000).toLocaleString('vi-VN') : '-';
    const trangStr = isTrang ? '<strong style="color:var(--cyan)">TRẮNG</strong>' : 'ĐÃ ĐK';

    html += `
      <tr>
        <td><code>${escapeHtml(it.account)}</code></td>
        <td style="color:${statusColor};font-weight:700;">${it.status}</td>
        <td>${escapeHtml(it.rank || '-')}</td>
        <td>${it.hero_count || 0}</td>
        <td>${it.skin_count || 0}</td>
        <td>${trangStr}</td>
        <td><small style="color:var(--text-muted)">${timeStr}</small></td>
      </tr>
    `;
  });
  historyTableBody.innerHTML = html;
}

(btnExportHistory && btnExportHistory.addEventListener)('click', () => {
  if (!currentHistoryList || currentHistoryList.length === 0) {
    showToast('KHÔNG CÓ DỮ LIỆU LỊCH SỬ ĐỂ XUẤT');
    return;
  }
  let content = '=== LỊCH SỬ TÀI KHOẢN AOV ĐÃ CHECK ===\n\n';
  currentHistoryList.forEach(it => {
    content += `${it.account} | STATUS: ${it.status} | RANK: ${it.rank || 'None'} | TƯỚNG: ${it.hero_count} | SKIN: ${it.skin_count} | TRẮNG: ${it.is_trang ? 'YES' : 'NO'}\n`;
  });
  downloadFile(`aov_history_export_${Date.now()}.txt`, content);
  showToast(`ĐÃ XUẤT ${currentHistoryList.length} DÒNG LỊCH SỬ`);
});

(btnClearHistory && btnClearHistory.addEventListener)('click', async () => {
  if (!currentUser) return;
  if (!confirm('Bạn có chắc chắn muốn xóa toàn bộ lịch sử check của mình?')) return;
  try {
    const res = await fetch('/api/user/history/clear', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: currentUser.id })
    });
    const data = await res.json();
    if (data.success) {
      showToast('ĐÃ XÓA SẠCH LỊCH SỬ');
      loadCheckHistory('all');
    }
  } catch (e) {
    showToast('Lỗi khi xóa lịch sử');
  }
});

// ── Quota & Giftcode Redeem ─────────────────────────────────────────────────
window.fillCode = function(code) {
  if (redeemStudioInput) {
    redeemStudioInput.value = code;
    redeemStudioInput.focus();
  }
};

(redeemStudioForm && redeemStudioForm.addEventListener)('submit', async (e) => {
  e.preventDefault();
  if (!currentUser) return;
  if (redeemStudioError) redeemStudioError.style.display = 'none';
  const code = redeemStudioInput.value.trim();

  try {
    const res = await fetch('/api/user/redeem', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: currentUser.id, code })
    });
    const data = await res.json();
    if (data.success || data.status === 'ok') {
      currentUser.credits = (data.new_credits !== undefined && data.new_credits !== null ? data.new_credits : (currentUser.credits + data.credits_added));
      localStorage.setItem('aov_user', JSON.stringify(currentUser));
      renderUserHeader();
      redeemStudioInput.value = '';
      showToast(data.message || `KÍCH HOẠT THÀNH CÔNG +${data.credits_added} CREDITS!`);
    } else {
      if (redeemStudioError) {
        redeemStudioError.textContent = data.error || data.message || 'Mã Giftcode không hợp lệ!';
        redeemStudioError.style.display = 'block';
      }
    }
  } catch (err) {
    if (redeemStudioError) {
      redeemStudioError.textContent = 'Lỗi kết nối máy chủ';
      redeemStudioError.style.display = 'block';
    }
  }
});

// Close overlay on outside click
window.addEventListener('click', (e) => {
  if (e.target === authModal) authModal.style.display = 'none';
});

// Bootstrap
initApp();
