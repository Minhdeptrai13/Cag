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
const authView = document.getElementById('authView');
const toast = document.getElementById('toast');

// Landing Elements
const btnLandingLogin = document.getElementById('btnLandingLogin');
const btnLandingDocs = document.getElementById('btnLandingDocs');
const btnHeroOpenStudio = document.getElementById('btnHeroOpenStudio');
const btnHeroRegister = document.getElementById('btnHeroRegister');

// Auth View Elements
const btnBackToLanding = document.getElementById('btnBackToLanding');
const tabLoginBtn = document.getElementById('tabLoginBtn');
const tabRegisterBtn = document.getElementById('tabRegisterBtn');
const loginForm = document.getElementById('loginForm');
const registerForm = document.getElementById('registerForm');
const loginError = document.getElementById('loginError');
const regError = document.getElementById('regError');
const linkSwitchToRegister = document.getElementById('linkSwitchToRegister');
const linkSwitchToLogin = document.getElementById('linkSwitchToLogin');

// Studio Header
const studioUsername = document.getElementById('studioUsername');
const studioUserRole = document.getElementById('studioUserRole');
const studioCredits = document.getElementById('studioCredits');
const studioUserAvatar = document.getElementById('studioUserAvatar');
const btnStudioLogout = document.getElementById('btnStudioLogout');

// Sidebar Nav
const navItems = document.querySelectorAll('.nav-item');
const tabPanes = document.querySelectorAll('.tab-pane');

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
  if (authView) authView.style.display = 'none';
  if (studioView) studioView.style.display = 'none';
}

function showAuthView(mode = 'login') {
  if (landingView) landingView.style.display = 'none';
  if (studioView) studioView.style.display = 'none';
  if (authView) authView.style.display = 'flex';

  if (loginError) loginError.style.display = 'none';
  if (regError) regError.style.display = 'none';

  if (mode === 'register') {
    if (tabRegisterBtn) tabRegisterBtn.classList.add('active');
    if (tabLoginBtn) tabLoginBtn.classList.remove('active');
    if (loginForm) loginForm.style.display = 'none';
    if (registerForm) registerForm.style.display = 'flex';
    initSliderCaptcha();
  } else {
    if (tabLoginBtn) tabLoginBtn.classList.add('active');
    if (tabRegisterBtn) tabRegisterBtn.classList.remove('active');
    if (loginForm) loginForm.style.display = 'flex';
    if (registerForm) registerForm.style.display = 'none';
  }
}

function showStudioView() {
  if (landingView) landingView.style.display = 'none';
  if (authView) authView.style.display = 'none';
  if (studioView) studioView.style.display = 'flex';
  renderUserHeader();
  loadUserApiKeys();
  updateCodeSnippets();
  checkAdminPrivileges();
}

function renderUserHeader() {
  if (!currentUser) return;
  if (studioUsername) studioUsername.textContent = currentUser.username || 'User';
  if (studioUserRole) studioUserRole.textContent = (currentUser.role || 'FREE').toUpperCase();
  if (studioCredits) studioCredits.textContent = (currentUser.credits !== undefined && currentUser.credits !== null ? currentUser.credits : 0);
  if (studioUserAvatar) studioUserAvatar.textContent = (currentUser.username || 'U')[0].toUpperCase();
  if (quotaBigNumber) quotaBigNumber.textContent = (currentUser.credits !== undefined && currentUser.credits !== null ? currentUser.credits : 0);
  if (quotaTierLabel) quotaTierLabel.textContent = (currentUser.role || 'FREE').toUpperCase() + ' PLAN';
  checkAdminPrivileges();
}

function checkAdminPrivileges() {
  const tabNavAdmin = document.getElementById('tabNavAdmin');
  if (tabNavAdmin) {
    if (currentUser && (currentUser.role === 'owner' || currentUser.role === 'admin')) {
      tabNavAdmin.style.display = 'flex';
    } else {
      tabNavAdmin.style.display = 'none';
    }
  }
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

// ── Safe Event Helper ────────────────────────────────────────────────────────
function on(el, event, handler) {
  if (el && typeof el.addEventListener === 'function') {
    el.addEventListener(event, handler);
  }
}

// Navigation & Auth Buttons
on(btnLandingLogin, 'click', (e) => {
  e.preventDefault();
  showAuthView('login');
});

on(btnHeroOpenStudio, 'click', (e) => {
  e.preventDefault();
  if (currentUser) showStudioView();
  else showAuthView('login');
});

on(btnHeroRegister, 'click', (e) => {
  e.preventDefault();
  showAuthView('register');
});

on(btnLandingDocs, 'click', (e) => {
  e.preventDefault();
  if (currentUser) {
    showStudioView();
    switchTab('api');
  } else {
    showAuthView('login');
  }
});

on(btnBackToLanding, 'click', (e) => {
  e.preventDefault();
  showLandingView();
});

on(tabLoginBtn, 'click', () => {
  showAuthView('login');
});

on(tabRegisterBtn, 'click', () => {
  showAuthView('register');
});

on(linkSwitchToRegister, 'click', (e) => {
  e.preventDefault();
  showAuthView('register');
});

on(linkSwitchToLogin, 'click', (e) => {
  e.preventDefault();
  showAuthView('login');
});

// Login Submit
on(loginForm, 'submit', async (e) => {
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

// Register Submit with Internal Slider Captcha
on(registerForm, 'submit', async (e) => {
  e.preventDefault();
  if (regError) regError.style.display = 'none';
  const username = document.getElementById('regUser').value.trim();
  const password = document.getElementById('regPass').value;

  if (!captchaVerifiedData) {
    if (regError) {
      regError.textContent = 'Vui lòng kéo thanh trượt để xác thực bảo mật trước khi đăng ký!';
      regError.style.display = 'block';
    }
    return;
  }

  try {
    const res = await fetch('/api/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        username,
        password,
        captcha_token: captchaVerifiedData.token,
        slider_x: captchaVerifiedData.user_x,
        track_width: captchaVerifiedData.track_width
      })
    });
    const data = await res.json();
    if (data.success || data.status === 'ok') {
      currentUser = data.user;
      currentApiKey = data.user ? (data.user.api_key || data.user.key) : data.api_key;
      localStorage.setItem('aov_user', JSON.stringify(currentUser));
      showStudioView();
      showToast('TẠO TÀI KHOẢN THÀNH CÔNG! BẠN ĐƯỢC TẶNG 50 CREDITS');
    } else {
      if (regError) {
        regError.textContent = data.error || data.message || 'Đăng ký thất bại!';
        regError.style.display = 'block';
      }
      initSliderCaptcha(); // Reset captcha on failure
    }
  } catch (err) {
    if (regError) {
      regError.textContent = 'Lỗi kết nối đến máy chủ';
      regError.style.display = 'block';
    }
    initSliderCaptcha();
  }
});

on(btnStudioLogout, 'click', () => {
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
  } else if (tabName === 'admin') {
    loadAdminDashboard();
  }
}

navItems.forEach(btn => {
  btn.addEventListener('click', () => {
    const t = btn.getAttribute('data-tab');
    switchTab(t);
  });
});

// ── Mode Switcher (Batch Stream vs Single Quick Test) ───────────────────────
on(btnModeBatch, 'click', () => {
  btnModeBatch.classList.add('active');
  btnModeSingle.classList.remove('active');
  batchStreamPane.style.display = 'grid';
  singleTestPane.style.display = 'none';
});

on(btnModeSingle, 'click', () => {
  btnModeSingle.classList.add('active');
  btnModeBatch.classList.remove('active');
  batchStreamPane.style.display = 'none';
  singleTestPane.style.display = 'block';
});

// ── Single Quick Test ───────────────────────────────────────────────────────
on(btnRunSingle, 'click', async () => {
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
      const sec = data.security || {};
      const hasPhone = Boolean(
        data.has_phone ||
        sec.has_phone ||
        data.mobile_bound ||
        sec.mobile_bound ||
        (data.masked_phone && data.masked_phone !== 'Trắng' && data.masked_phone !== 'NO') ||
        (sec.masked_phone && sec.masked_phone !== 'Trắng' && sec.masked_phone !== 'NO')
      );
      const phone = (data.masked_phone || sec.masked_phone || '').trim();
      const phoneDisplay = (phone && phone !== 'Trắng' && phone !== 'NO') ? phone : (hasPhone ? 'ĐÃ LIÊN KẾT' : '');

      const email = (data.masked_email || sec.masked_email || '').trim();
      const hasEmail = Boolean(email && email !== 'Trắng');
      const emailV = Boolean(data.email_v !== undefined ? data.email_v : sec.email_v);

      const hasCccd = Boolean(data.has_cccd !== undefined ? data.has_cccd : sec.has_cccd);
      const hasAuthen = Boolean(data.auth_2fa !== undefined ? data.auth_2fa : sec.auth_2fa);
      const hasFb = Boolean(data.fb_linked !== undefined ? data.fb_linked : sec.fb_linked);

      const isTrang = Boolean(data.is_trang) && !hasPhone;
      const tinhTrang = data.tt_info || data.tinh_trang || (isTrang ? 'ACC TRẮNG' : (hasPhone ? 'Acc Dính SĐT' : 'CÓ THÔNG TIN'));

      let phoneHtml = hasPhone ? `<span class="sec-val yes">YES [${escapeHtml(phoneDisplay)}]</span>` : `<span class="sec-val no">NO</span>`;
      let emailHtml = hasEmail ? (emailV ? `<span class="sec-val yes">YES [${escapeHtml(email)} - ĐÃ XT]</span>` : `<span class="sec-val warn">NO [${escapeHtml(email)} - CHƯA XT]</span>`) : `<span class="sec-val no">NO</span>`;
      let cccdHtml = hasCccd ? `<span class="sec-val yes">YES</span>` : `<span class="sec-val no">NO</span>`;
      let authenHtml = hasAuthen ? `<span class="sec-val yes">YES</span>` : `<span class="sec-val no">NO</span>`;
      let fbHtml = hasFb ? `<span class="sec-val yes">YES</span>` : `<span class="sec-val no">DIE</span>`;

      singleStatusTag.textContent = isTrang ? 'HIT LIVE (ACC TRẮNG)' : `HIT LIVE (${tinhTrang.toUpperCase()})`;

      singleBody.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
          <div><strong>INGAME:</strong> ${escapeHtml(data.ingame || aov.name || 'None')}</div>
          <button type="button" class="btn-acc-copy" id="btnCopySingleFull">COPY CHI TIẾT</button>
        </div>
        <div><strong>RANK:</strong> <span style="color:var(--gold)">${escapeHtml(data.rank || aov.rank || 'Unranked')}</span></div>
        <div><strong>TƯỚNG:</strong> ${data.heroes_count || aov.total_champs || 0} | <strong>SKIN:</strong> ${data.skins_count || aov.total_skins || 0}</div>
        <div class="acc-sec-line" style="margin: 8px 0;">
          <span class="sec-pill"><strong>SĐT:</strong> ${phoneHtml}</span>
          <span class="sec-pill"><strong>EMAIL:</strong> ${emailHtml}</span>
          <span class="sec-pill"><strong>CCCD:</strong> ${cccdHtml}</span>
          <span class="sec-pill"><strong>2FA:</strong> ${authenHtml}</span>
          <span class="sec-pill"><strong>FB:</strong> ${fbHtml}</span>
          <span class="sec-pill"><strong>TRẠNG THÁI:</strong> <span class="sec-val ${data.is_trang ? 'status-trang' : 'warn'}">${escapeHtml(tinhTrang)}</span></span>
        </div>
        ${skinDetails}
      `;

      const btnCopySingle = document.getElementById('btnCopySingleFull');
      if (btnCopySingle) {
        btnCopySingle.addEventListener('click', () => {
          navigator.clipboard.writeText(formatItemFullText(data));
          showToast(`ĐÃ COPY CHI TIẾT ACC [${acc}]!`);
        });
      }
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
const btnSelectFile = document.getElementById('btnSelectFile');
on(btnSelectFile, 'click', (e) => {
  e.preventDefault();
  e.stopPropagation();
  if (fileInput) fileInput.click();
});

on(fileInput, 'change', (e) => {
  const file = e.target.files[0];
  if (file) handleLoadedFile(file);
});

on(uploadZone, 'dragover', (e) => {
  e.preventDefault();
  uploadZone.classList.add('dragover');
});
on(uploadZone, 'dragleave', () => {
  uploadZone.classList.remove('dragover');
});
on(uploadZone, 'drop', (e) => {
  e.preventDefault();
  uploadZone.classList.remove('dragover');
  const file = e.dataTransfer.files[0];
  if (file) handleLoadedFile(file);
});

let selectedLargeFile = null;
let currentResultsOffset = 0;

function formatFileSize(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
  return (bytes / (1024 * 1024 * 1024)).toFixed(2) + ' GB';
}

function handleLoadedFile(file) {
  selectedLargeFile = file;
  const sizeStr = formatFileSize(file.size);
  if (fileChosen) fileChosen.textContent = `[ ${file.name} - ${sizeStr} ]`;

  // If file is > 5 MB, do NOT load into textarea to prevent browser freeze
  if (file.size > 5 * 1024 * 1024) {
    batchText.value = `[FILE LỚN ĐƯỢC CHỌN: ${file.name} (${sizeStr})]\n-> File sẽ được truyền stream siêu tốc trực tiếp lên server không làm đơ trình duyệt. Nhấn 'BẮT ĐẦU QUÉT' để chạy ngay!`;
    batchText.disabled = true;
    showToast(`ĐÃ SẴN SÀNG STREAM FILE LỚN (${sizeStr})`);
  } else {
    batchText.disabled = false;
    const reader = new FileReader();
    reader.onload = (ev) => {
      batchText.value = ev.target.result;
      showToast(`ĐÃ NẠP FILE: ${file.name} (${sizeStr})`);
    };
    reader.readAsText(file);
  }
}

on(btnClearBatch, 'click', () => {
  batchText.value = '';
  batchText.disabled = false;
  selectedLargeFile = null;
  if (fileChosen) fileChosen.textContent = '';
  if (fileInput) fileInput.value = '';
  showToast('ĐÃ XÓA TRẮNG');
});

async function uploadLargeFileInChunks(file) {
  const chunkSize = 2 * 1024 * 1024; // 2MB per chunk
  const totalChunks = Math.ceil(file.size / chunkSize);
  let uploadId = '';

  progressWrap.style.display = 'block';
  progressBarFill.style.width = '0%';
  progressStatus.textContent = `Đang tải stream file lên server (0/${totalChunks})...`;

  for (let i = 0; i < totalChunks; i++) {
    const start = i * chunkSize;
    const end = Math.min(file.size, start + chunkSize);
    const blob = file.slice(start, end);
    const textChunk = await blob.text();
    const isLast = (i === totalChunks - 1);

    const resp = await fetch('/api/upload-chunk', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        upload_id: uploadId,
        chunk: textChunk,
        is_last: isLast
      })
    });

    const resJson = await resp.json();
    if (!resJson.success) {
      throw new Error(resJson.error || 'Lỗi truyền chunk file');
    }

    uploadId = resJson.upload_id;
    const uploadPct = Math.round(((i + 1) / totalChunks) * 100);
    progressBarFill.style.width = `${uploadPct}%`;
    progressRatio.textContent = `${uploadPct}%`;
    progressStatus.textContent = `Đang tải stream file (${i + 1}/${totalChunks} chunks - ${uploadPct}%)...`;

    if (isLast) {
      return { uploadId, totalValid: resJson.total_valid };
    }
  }
}

on(btnStartBatch, 'click', async () => {
  const threads = Math.min(500, Math.max(1, parseInt(threadInput.value, 10) || 50));

  // Reset Console
  allResults = [];
  currentResultsOffset = 0;
  batchResultsList.innerHTML = '';
  updateCounters();

  document.getElementById('btnBatchText').style.display = 'none';
  document.getElementById('btnBatchLoader').style.display = 'inline-block';
  btnStartBatch.disabled = true;

  // Case 1: Large File Streaming (> 5 MB)
  if (selectedLargeFile && selectedLargeFile.size > 5 * 1024 * 1024) {
    try {
      const { uploadId, totalValid } = await uploadLargeFileInChunks(selectedLargeFile);
      progressStatus.textContent = `Khởi động ${threads} luồng quét cho ${totalValid} tài khoản...`;
      progressBarFill.style.width = '0%';
      progressRatio.textContent = `0/${totalValid} (0%)`;

      const resp = await fetch('/api/check-uploaded-file', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          upload_id: uploadId,
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
      return;
    } catch (err) {
      showToast('LỖI TẢI FILE LỚN: ' + err.message);
      resetBatchUI();
      return;
    }
  }

  // Case 2: Standard Textarea Combo List
  const text = batchText.value.trim();
  if (!text) {
    showToast('VUI LÒNG DÁN COMBO HOẶC CHỌN FILE .TXT');
    resetBatchUI();
    return;
  }

  const lines = text.split('\n')
    .map(l => l.trim())
    .filter(l => l && !l.startsWith('#') && (/[:|;\t\s/]/.test(l)));

  if (lines.length === 0) {
    showToast('KHÔNG TÌM THẤY DÒNG COMBO HỢP LỆ');
    resetBatchUI();
    return;
  }

  progressWrap.style.display = 'block';
  progressBarFill.style.width = '0%';
  progressStatus.textContent = `Khởi động ${threads} luồng...`;
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
  currentResultsOffset = 0;

  pollInterval = setInterval(async () => {
    try {
      const resp = await fetch(`/api/task-status?task_id=${taskId}&offset=${currentResultsOffset}`);
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
      progressStatus.textContent = data.is_running ? `Đang quét (${done}/${total} - ${pct}%)...` : 'Hoàn thành!';

      const newItems = data.results || [];
      if (newItems.length > 0) {
        allResults = allResults.concat(newItems);
        currentResultsOffset = (data.next_offset !== undefined) ? data.next_offset : allResults.length;
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
  }, 600);
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

function formatItemFullText(r) {
  if (!r) return '';
  if (r.full_info) return r.full_info;

  const acc = r.account || '';
  const pwd = r.password || '';
  const status = r.status || 'FAIL';
  if (status !== 'HIT') {
    return `${acc}:${pwd} | STATUS : ${status} | DETAIL : ${r.message || 'Thất bại'}`;
  }

  const aov = r.aov || {};
  const sec = r.security || {};

  const name = r.ingame || aov.name || 'NoName';
  const rank = r.rank || aov.rank || 'None';
  const stars = aov.stars || 0;
  const rankStr = stars > 0 ? `${rank} ${stars} sao` : rank;
  const level = aov.level || 0;
  const hero = r.heroes_count !== undefined ? r.heroes_count : (aov.total_champs || 0);
  const skin = r.skins_count !== undefined ? r.skins_count : (aov.total_skins || 0);
  const ban = aov.banned || 'KHÔNG';

  const maskedEmail = (sec.masked_email || '').trim();
  let emailStr = 'NO [CHƯA LIÊN KẾT]';
  if (maskedEmail && maskedEmail !== 'Trắng') {
    emailStr = sec.email_v ? `YES [${maskedEmail} - ĐÃ XÁC THỰC]` : `NO [${maskedEmail} - CHƯA XÁC THỰC]`;
  }

  const hasPhone = Boolean(
    r.has_phone ||
    sec.has_phone ||
    r.mobile_bound ||
    sec.mobile_bound ||
    (r.masked_phone && r.masked_phone !== 'Trắng' && r.masked_phone !== 'NO') ||
    (sec.masked_phone && sec.masked_phone !== 'Trắng' && sec.masked_phone !== 'NO')
  );
  const maskedPhone = (r.masked_phone || sec.masked_phone || '').trim();
  let sdtStr = 'NO';
  if (maskedPhone && maskedPhone !== 'Trắng' && maskedPhone !== 'NO') {
    sdtStr = `YES [${maskedPhone}]`;
  } else if (hasPhone) {
    sdtStr = 'YES [ĐÃ LIÊN KẾT]';
  }

  const cmndStr = (r.has_cccd || sec.has_cccd) ? 'YES' : 'NO';
  const authenStr = (r.auth_2fa || sec.auth_2fa) ? 'YES' : 'NO';
  const fbStr = (r.fb_linked || sec.fb_linked) ? 'YES' : 'DIE';
  const shells = r.shells || 0;
  const country = (r.country || 'VN').toUpperCase();
  const lastLogin = r.last_login || 'Chưa ghi nhận';

  const ssList = r.ss_list || aov.ss_list || [];
  const sssList = r.sss_list || aov.sss_list || [];
  const animeList = r.anime_list || aov.anime_list || [];
  const splusList = r.other_list || r.splus_list || aov.other_list || [];

  const ssStr = `${ssList.length} [${ssList.join(', ')}]`;
  const sssStr = `${sssList.length} [${sssList.join(', ')}]`;
  const animeStr = `${animeList.length} [${animeList.join(', ')}]`;
  const splusStr = `${splusList.length} [${splusList.join(', ')}]`;
  const isTrangAcc = Boolean(r.is_trang || (r.aov && r.aov.is_trang)) && !hasPhone;
  const trangThai = (r.tt_info || r.tinh_trang || (isTrangAcc ? 'ACC TRẮNG' : 'CÓ THÔNG TIN')).toUpperCase();

  return `${acc}:${pwd} | NAME :${name} | RANK : ${rankStr} | LEVEL : ${level} | HERO : ${hero} | SKIN : ${skin} | BAN : ${ban} | EMAIL : ${emailStr} | SDT : ${sdtStr} | CMND : ${cmndStr} | AUTHEN : ${authenStr} | FB : ${fbStr} | SÒ : ${shells} | QUỐC GIA : ${country} | LOGIN LẦN CUỐI : ${lastLogin} | SS : ${ssStr} | SSS : ${sssStr} | ANIME : ${animeStr} | S+ : ${splusStr} | TRẠNG THÁI : ${trangThai}`;
}

function createRowElement(item) {
  const div = document.createElement('div');
  const isHit = item.status === 'HIT';
  const sec = item.security || {};

  const hasPhone = Boolean(
    item.has_phone ||
    sec.has_phone ||
    item.mobile_bound ||
    sec.mobile_bound ||
    (item.masked_phone && item.masked_phone !== 'Trắng' && item.masked_phone !== 'NO') ||
    (sec.masked_phone && sec.masked_phone !== 'Trắng' && sec.masked_phone !== 'NO')
  );

  const tinhTrangRaw = item.tt_info || item.tinh_trang || '';
  const isTrang = Boolean(item.is_trang || (item.aov && item.aov.is_trang)) && !hasPhone && (!tinhTrangRaw || tinhTrangRaw.toLowerCase() === 'acc trắng');

  let cls = 'acc-row ';
  if (isHit) cls += isTrang ? 'row-trang' : 'row-hit';
  else cls += 'row-invalid';
  div.className = cls;

  const accStr = `${item.account}:${item.password}`;
  if (isHit) {
    const aov = item.aov || {};
    const sssList = item.sss_list || aov.sss_list || [];
    const animeList = item.anime_list || aov.anime_list || [];
    const ssList = item.ss_list || aov.ss_list || [];
    const splusList = item.other_list || item.splus_list || aov.other_list || [];

    let skinBlocksHtml = '';
    if (sssList.length > 0) {
      skinBlocksHtml += `
        <div class="skin-badge-line">
          <span class="skin-tag sss">SSS (${sssList.length})</span>
          <span class="skin-items-text">${escapeHtml(sssList.join(', '))}</span>
        </div>`;
    }
    if (animeList.length > 0) {
      skinBlocksHtml += `
        <div class="skin-badge-line">
          <span class="skin-tag anime">ANIME (${animeList.length})</span>
          <span class="skin-items-text">${escapeHtml(animeList.join(', '))}</span>
        </div>`;
    }
    if (ssList.length > 0) {
      skinBlocksHtml += `
        <div class="skin-badge-line">
          <span class="skin-tag ss">SS (${ssList.length})</span>
          <span class="skin-items-text">${escapeHtml(ssList.join(', '))}</span>
        </div>`;
    }
    if (splusList.length > 0) {
      skinBlocksHtml += `
        <div class="skin-badge-line">
          <span class="skin-tag splus">S+ / HỮU HẠN (${splusList.length})</span>
          <span class="skin-items-text">${escapeHtml(splusList.join(', '))}</span>
        </div>`;
    }
    if (!skinBlocksHtml && item.skins_vip) {
      skinBlocksHtml = `<div class="acc-skins-line">★ VIP: ${escapeHtml(item.skins_vip)}</div>`;
    }

    const phone = (item.masked_phone || sec.masked_phone || '').trim();
    const phoneDisplay = (phone && phone !== 'Trắng' && phone !== 'NO') ? phone : (hasPhone ? 'ĐÃ LIÊN KẾT' : '');

    const email = (item.masked_email || sec.masked_email || '').trim();
    const hasEmail = Boolean(email && email !== 'Trắng');
    const emailV = Boolean(item.email_v !== undefined ? item.email_v : sec.email_v);

    const hasCccd = Boolean(item.has_cccd !== undefined ? item.has_cccd : sec.has_cccd);
    const hasAuthen = Boolean(item.auth_2fa !== undefined ? item.auth_2fa : sec.auth_2fa);
    const hasFb = Boolean(item.fb_linked !== undefined ? item.fb_linked : sec.fb_linked);

    const tinhTrang = tinhTrangRaw || (isTrang ? 'ACC TRẮNG' : (hasPhone ? 'Acc Dính SĐT' : 'CÓ THÔNG TIN'));

    let phoneHtml = hasPhone ? `<span class="sec-val yes">YES [${escapeHtml(phoneDisplay)}]</span>` : `<span class="sec-val no">NO</span>`;
    let emailHtml = hasEmail ? (emailV ? `<span class="sec-val yes">YES [${escapeHtml(email)} - ĐÃ XT]</span>` : `<span class="sec-val warn">NO [${escapeHtml(email)} - CHƯA XT]</span>`) : `<span class="sec-val no">NO</span>`;
    let cccdHtml = hasCccd ? `<span class="sec-val yes">YES</span>` : `<span class="sec-val no">NO</span>`;
    let authenHtml = hasAuthen ? `<span class="sec-val yes">YES</span>` : `<span class="sec-val no">NO</span>`;
    let fbHtml = hasFb ? `<span class="sec-val yes">YES</span>` : `<span class="sec-val no">DIE</span>`;

    const tagText = isTrang ? 'ACC TRẮNG' : (tinhTrang ? tinhTrang.toUpperCase() : 'DÍNH THÔNG TIN');

    div.innerHTML = `
      <div class="row-head">
        <div style="display:flex;align-items:center;gap:8px;">
          <span class="acc-tag ${isTrang ? 'trang' : 'dinh'}">${escapeHtml(tagText)}</span>
          <code>${escapeHtml(accStr)}</code>
        </div>
        <div class="acc-actions">
          <button type="button" class="btn-acc-copy" title="Copy toàn bộ thông tin chi tiết của tài khoản này">COPY CHI TIẾT</button>
        </div>
      </div>
      <div class="acc-info-line">
        [ ${escapeHtml(item.ingame || aov.name || 'NoName')} ] | RANK: <span style="color:var(--gold)">${escapeHtml(item.rank || aov.rank || 'None')}</span> | TƯỚNG: ${item.heroes_count !== undefined ? item.heroes_count : (aov.total_champs || 0)} | SKIN: ${item.skins_count !== undefined ? item.skins_count : (aov.total_skins || 0)}
      </div>
      <div class="acc-sec-line">
        <span class="sec-pill"><strong>SĐT:</strong> ${phoneHtml}</span>
        <span class="sec-pill"><strong>EMAIL:</strong> ${emailHtml}</span>
        <span class="sec-pill"><strong>CCCD:</strong> ${cccdHtml}</span>
        <span class="sec-pill"><strong>2FA:</strong> ${authenHtml}</span>
        <span class="sec-pill"><strong>FB:</strong> ${fbHtml}</span>
        <span class="sec-pill"><strong>TRẠNG THÁI:</strong> <span class="sec-val ${isTrang ? 'status-trang' : 'warn'}">${escapeHtml(tinhTrang)}</span></span>
      </div>
      ${skinBlocksHtml ? `<div class="acc-skins-block">${skinBlocksHtml}</div>` : ''}
    `;

    const copyBtn = div.querySelector('.btn-acc-copy');
    if (copyBtn) {
      copyBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        const fullText = formatItemFullText(item);
        navigator.clipboard.writeText(fullText);
        showToast(`ĐÃ COPY CHI TIẾT ACC [${item.account}]!`);
      });
    }
  } else {
    div.innerHTML = `
      <div class="row-head">
        <div style="display:flex;align-items:center;gap:8px;">
          <span class="acc-tag invalid">${escapeHtml(item.status || 'FAIL')}</span>
          <code>${escapeHtml(accStr)}</code>
        </div>
        <div class="acc-actions">
          <button type="button" class="btn-acc-copy">COPY</button>
        </div>
      </div>
      <div style="color:var(--text-muted);font-size:11px;">${escapeHtml(item.message || 'FAIL')}</div>
    `;
    const copyBtn = div.querySelector('.btn-acc-copy');
    if (copyBtn) {
      copyBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        navigator.clipboard.writeText(`${item.account}:${item.password} | STATUS: ${item.status || 'FAIL'} | LÝ DO: ${item.message || '-'}`);
        showToast(`ĐÃ COPY ACC [${item.account}]!`);
      });
    }
  }
  return div;
}

function matchesFilter(item) {
  const isHit = item.status === 'HIT';
  const sec = item.security || {};
  const hasPhone = Boolean(
    item.has_phone ||
    sec.has_phone ||
    item.mobile_bound ||
    sec.mobile_bound ||
    (item.masked_phone && item.masked_phone !== 'Trắng' && item.masked_phone !== 'NO') ||
    (sec.masked_phone && sec.masked_phone !== 'Trắng' && sec.masked_phone !== 'NO')
  );
  const tinhTrang = (item.tt_info || item.tinh_trang || '').toLowerCase();
  const isTrang = Boolean(item.is_trang || (item.aov && item.aov.is_trang)) && !hasPhone && (!tinhTrang || tinhTrang === 'acc trắng');

  const hasVip = Boolean(
    item.skins_vip ||
    (item.sss_list && item.sss_list.length > 0) ||
    (item.anime_list && item.anime_list.length > 0) ||
    (item.ss_list && item.ss_list.length > 0) ||
    (item.aov && (
      (item.aov.sss_list && item.aov.sss_list.length > 0) ||
      (item.aov.anime_list && item.aov.anime_list.length > 0) ||
      (item.aov.ss_list && item.aov.ss_list.length > 0)
    ))
  );

  if (currentFilter === 'trang' && (!isHit || !isTrang || hasPhone)) return false;
  if (currentFilter === 'vip' && (!isHit || !hasVip)) return false;
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
      const sec = r.security || {};
      const hasPhone = Boolean(
        r.has_phone ||
        sec.has_phone ||
        r.mobile_bound ||
        sec.mobile_bound ||
        (r.masked_phone && r.masked_phone !== 'Trắng' && r.masked_phone !== 'NO') ||
        (sec.masked_phone && sec.masked_phone !== 'Trắng' && sec.masked_phone !== 'NO')
      );
      const tinhTrang = (r.tt_info || r.tinh_trang || '').toLowerCase();
      const isTrangAcc = Boolean(r.is_trang || (r.aov && r.aov.is_trang)) && !hasPhone && (!tinhTrang || tinhTrang === 'acc trắng');
      if (isTrangAcc) trang++;

      const hasVip = Boolean(
        r.skins_vip ||
        (r.sss_list && r.sss_list.length > 0) ||
        (r.anime_list && r.anime_list.length > 0) ||
        (r.ss_list && r.ss_list.length > 0) ||
        (r.aov && (
          (r.aov.sss_list && r.aov.sss_list.length > 0) ||
          (r.aov.anime_list && r.aov.anime_list.length > 0) ||
          (r.aov.ss_list && r.aov.ss_list.length > 0)
        ))
      );
      if (hasVip) vip++;
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

on(filterSearch, 'input', (e) => {
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

on(btnExportAll, 'click', () => {
  if (!allResults || allResults.length === 0) {
    showToast('CHƯA CÓ KẾT QUẢ CHECK NÀO ĐỂ XUẤT');
    return;
  }
  const hits = allResults.filter(r => r.status === 'HIT');
  let txt = '';
  let filename = '';

  if (hits.length > 0) {
    txt = '=== DANH SÁCH ACC AOV HIT LIVE (FULL CHI TIẾT) ===\n\n';
    hits.forEach(r => {
      txt += formatItemFullText(r) + '\n';
    });
    filename = `aov_hits_full_${Date.now()}.txt`;
    downloadFile(filename, txt);
    showToast(`ĐÃ XUẤT ${hits.length} TÀI KHOẢN HIT LIVE`);
  } else {
    txt = '=== TOÀN BỘ KẾT QUẢ QUÉT TÀI KHOẢN ===\n\n';
    allResults.forEach(r => {
      txt += formatItemFullText(r) + '\n';
    });
    filename = `aov_all_checked_${Date.now()}.txt`;
    downloadFile(filename, txt);
    showToast(`ĐÃ XUẤT TOÀN BỘ ${allResults.length} TÀI KHOẢN ĐÃ QUÉT`);
  }
});

on(btnExportTrang, 'click', () => {
  if (!allResults || allResults.length === 0) {
    showToast('CHƯA CÓ KẾT QUẢ CHECK NÀO ĐỂ XUẤT');
    return;
  }
  const trangs = allResults.filter(r => {
    if (r.status !== 'HIT') return false;
    const sec = r.security || {};
    const hasPhone = Boolean(
      r.has_phone ||
      sec.has_phone ||
      r.mobile_bound ||
      sec.mobile_bound ||
      (r.masked_phone && r.masked_phone !== 'Trắng' && r.masked_phone !== 'NO') ||
      (sec.masked_phone && sec.masked_phone !== 'Trắng' && sec.masked_phone !== 'NO')
    );
    const tinhTrang = (r.tt_info || r.tinh_trang || '').toLowerCase();
    return Boolean(r.is_trang || (r.aov && r.aov.is_trang)) && !hasPhone && (!tinhTrang || tinhTrang === 'acc trắng');
  });

  if (trangs.length === 0) {
    showToast('KHÔNG CÓ TÀI KHOẢN NÀO TRẮNG THÔNG TIN TRONG KẾT QUẢ');
    return;
  }
  let txt = '=== DANH SÁCH ACC AOV TRẮNG THÔNG TIN (FULL CHI TIẾT) ===\n\n';
  trangs.forEach(r => {
    txt += formatItemFullText(r) + '\n';
  });
  downloadFile(`aov_acc_trang_full_${Date.now()}.txt`, txt);
  showToast(`ĐÃ XUẤT ${trangs.length} ACC TRẮNG THÔNG TIN`);
});

on(btnCopyView, 'click', () => {
  let list = allResults.filter(matchesFilter);
  if (list.length === 0 && allResults.length > 0) {
    list = allResults;
  }
  if (list.length === 0) {
    showToast('KHÔNG CÓ TÀI KHOẢN ĐỂ SAO CHÉP');
    return;
  }
  const lines = list.map(r => formatItemFullText(r));
  navigator.clipboard.writeText(lines.join('\n'));
  showToast(`ĐÃ COPY TOÀN BỘ CHI TIẾT ${lines.length} TÀI KHOẢN!`);
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

on(btnCopyApiKey, 'click', () => {
  if (displayApiKey && displayApiKey.value) {
    navigator.clipboard.writeText(displayApiKey.value);
    showToast('ĐÃ COPY API KEY!');
  }
});

on(btnGenNewApiKey, 'click', async () => {
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
on(btnSendTestApi, 'click', async () => {
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

on(btnCopySnippet, 'click', () => {
  if (snippetCode) {
    navigator.clipboard.writeText(snippetCode.textContent);
    showToast('ĐÃ COPY CODE MẪU!');
  }
});

// ── Check History Logs ──────────────────────────────────────────────────────
histFilterBtns.forEach(btn => {
  on(btn, 'click', () => {
    histFilterBtns.forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    currentHistFilter = btn.getAttribute('data-hist-filter') || 'all';
    loadCheckHistory(currentHistFilter);
  });
});

on(btnRefreshHistory, 'click', () => loadCheckHistory(currentHistFilter));

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

on(btnExportHistory, 'click', async () => {
  if (!currentUser) {
    showToast('VUI LÒNG ĐĂNG NHẬP ĐỂ XUẤT LỊCH SỬ');
    return;
  }
  
  // Nếu chưa có cache lịch sử, tự động tải về từ máy chủ
  if (!currentHistoryList || currentHistoryList.length === 0) {
    try {
      const res = await fetch(`/api/user/history?user_id=${currentUser.id}&status=all&limit=500`);
      const data = await res.json();
      if (data.success || data.status === 'ok') {
        currentHistoryList = data.history || [];
      }
    } catch (e) {
      console.error('Error fetching history:', e);
    }
  }

  if (!currentHistoryList || currentHistoryList.length === 0) {
    showToast('BẠN CHƯA CÓ DỮ LIỆU LỊCH SỬ NÀO TRÊN HỆ THỐNG');
    return;
  }

  let content = '=== LỊCH SỬ TÀI KHOẢN AOV ĐÃ CHECK ===\n\n';
  currentHistoryList.forEach(it => {
    const isHit = it.status === 'HIT';
    const isTrang = Boolean(it.is_trang);
    const detailObj = it.detail_parsed || {};
    const rank = it.rank || detailObj.rank || 'None';
    const heroes = it.hero_count !== undefined ? it.hero_count : (detailObj.heroes_count || 0);
    const skins = it.skin_count !== undefined ? it.skin_count : (detailObj.skins_count || 0);
    const timeStr = it.created_at ? new Date(it.created_at * 1000).toLocaleString('vi-VN') : '-';

    content += `${it.account} | STATUS: ${it.status} | RANK: ${rank} | TƯỚNG: ${heroes} | SKIN: ${skins} | TRẮNG TTT: ${isTrang ? 'YES' : 'NO'} | THỜI GIAN: ${timeStr}\n`;
  });

  downloadFile(`aov_history_export_${Date.now()}.txt`, content);
  showToast(`ĐÃ XUẤT ${currentHistoryList.length} DÒNG LỊCH SỬ`);
});

on(btnClearHistory, 'click', async () => {
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

// ── Slider Captcha Engine ──────────────────────────────────────────────────
let captchaVerifiedData = null;
let currentChallenge = null;

async function initSliderCaptcha() {
  const captchaBox = document.getElementById('captchaBox');
  const sliderTrack = document.getElementById('sliderTrack');
  const sliderThumb = document.getElementById('sliderThumb');
  const sliderFill = document.getElementById('sliderFill');
  const sliderTargetNotch = document.getElementById('sliderTargetNotch');
  const captchaStatusText = document.getElementById('captchaStatusText');
  const btnSubmitRegister = document.getElementById('btnSubmitRegister');

  if (!captchaBox || !sliderTrack || !sliderThumb) return;

  captchaVerifiedData = null;
  if (btnSubmitRegister) btnSubmitRegister.disabled = true;
  if (sliderTargetNotch) sliderTargetNotch.classList.remove('matched');
  if (captchaStatusText) {
    captchaStatusText.textContent = 'Đang tạo thử thách...';
    captchaStatusText.classList.remove('verified');
  }

  // Reset positions
  sliderThumb.style.left = '4px';
  if (sliderFill) sliderFill.style.width = '0px';

  try {
    const res = await fetch('/api/captcha/new');
    const data = await res.json();
    if (data.status === 'ok') {
      currentChallenge = data;
      // Position target notch based on target_ratio
      const trackWidth = sliderTrack.clientWidth || 320;
      const notchX = Math.round(data.target_ratio * (trackWidth - 40));
      if (sliderTargetNotch) {
        sliderTargetNotch.style.left = `${notchX}px`;
        sliderTargetNotch.style.display = 'block';
      }
      if (captchaStatusText) {
        captchaStatusText.textContent = 'Kéo hình tròn đến tâm điểm vàng';
      }
    }
  } catch (err) {
    console.error('Captcha fetch error:', err);
    if (captchaStatusText) captchaStatusText.textContent = 'Lỗi tải mã bảo mật';
  }

  // Bind drag events
  let isDragging = false;
  let startMouseX = 0;
  let currentThumbX = 4;

  const onStart = (e) => {
    if (!currentChallenge || captchaVerifiedData) return;
    isDragging = true;
    startMouseX = e.type.startsWith('touch') ? e.touches[0].clientX : e.clientX;
    document.addEventListener('mousemove', onMove);
    document.addEventListener('touchmove', onMove, { passive: false });
    document.addEventListener('mouseup', onEnd);
    document.addEventListener('touchend', onEnd);
  };

  const onMove = (e) => {
    if (!isDragging) return;
    if (e.cancelable && e.type.startsWith('touch')) e.preventDefault();
    const clientX = e.type.startsWith('touch') ? e.touches[0].clientX : e.clientX;
    const deltaX = clientX - startMouseX;
    const trackWidth = sliderTrack.clientWidth || 320;
    const maxLeft = trackWidth - 36;
    let newLeft = Math.max(4, Math.min(4 + deltaX, maxLeft));

    sliderThumb.style.left = `${newLeft}px`;
    if (sliderFill) sliderFill.style.width = `${newLeft}px`;
    currentThumbX = newLeft;

    // Check proximity to notch
    const targetX = currentChallenge.target_ratio * (trackWidth - 40);
    if (Math.abs(newLeft - targetX) <= 15) {
      if (sliderTargetNotch) sliderTargetNotch.classList.add('matched');
    } else {
      if (sliderTargetNotch) sliderTargetNotch.classList.remove('matched');
    }
  };

  const onEnd = () => {
    if (!isDragging) return;
    isDragging = false;
    document.removeEventListener('mousemove', onMove);
    document.removeEventListener('touchmove', onMove);
    document.removeEventListener('mouseup', onEnd);
    document.removeEventListener('touchend', onEnd);

    const trackWidth = sliderTrack.clientWidth || 320;
    const targetX = currentChallenge.target_ratio * (trackWidth - 40);

    if (Math.abs(currentThumbX - targetX) <= 16) {
      // Verified!
      captchaVerifiedData = {
        token: currentChallenge.token,
        user_x: currentThumbX,
        track_width: trackWidth
      };
      if (captchaStatusText) {
        captchaStatusText.textContent = '✓ ĐÃ XÁC THỰC THÀNH CÔNG';
        captchaStatusText.classList.add('verified');
      }
      if (sliderTargetNotch) sliderTargetNotch.classList.add('matched');
      if (btnSubmitRegister) btnSubmitRegister.disabled = false;
      showToast('XÁC THỰC BẢO MẬT THÀNH CÔNG!');
    } else {
      // Failed, spring back
      sliderThumb.style.transition = 'left 0.2s ease';
      sliderThumb.style.left = '4px';
      if (sliderFill) {
        sliderFill.style.transition = 'width 0.2s ease';
        sliderFill.style.width = '0px';
      }
      setTimeout(() => {
        sliderThumb.style.transition = '';
        if (sliderFill) sliderFill.style.transition = '';
      }, 250);
      if (captchaStatusText) captchaStatusText.textContent = 'Chưa khớp, vui lòng thử lại';
    }
  };

  sliderThumb.onmousedown = onStart;
  sliderThumb.ontouchstart = onStart;
}

// ── Theme & Language Engine ────────────────────────────────────────────────
let currentTheme = localStorage.getItem('aov_theme') || 'dark';
let currentLang = localStorage.getItem('aov_lang') || 'vi';

const translations = {
  vi: {
    landing_api_docs: 'API DOCS',
    landing_auth_btn: 'ĐĂNG NHẬP / ĐĂNG KÝ',
    logout_btn: 'ĐĂNG XUẤT',
    nav_checker: 'Checker Studio',
    nav_api: 'API Playground',
    nav_history: 'History Logs',
    nav_billing: 'Quota & Giftcode',
    nav_admin: 'Admin Master'
  },
  en: {
    landing_api_docs: 'REST API DOCS',
    landing_auth_btn: 'SIGN IN / REGISTER',
    logout_btn: 'SIGN OUT',
    nav_checker: 'Checker Studio',
    nav_api: 'API Playground',
    nav_history: 'Audit Logs',
    nav_billing: 'Credits & Billing',
    nav_admin: 'Master Admin'
  }
};

function applyTheme(theme) {
  currentTheme = theme;
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem('aov_theme', theme);

  const darkIcons = document.querySelectorAll('.theme-icon-dark');
  const lightIcons = document.querySelectorAll('.theme-icon-light');

  if (theme === 'light') {
    darkIcons.forEach(el => el.style.display = 'none');
    lightIcons.forEach(el => el.style.display = 'inline');
  } else {
    darkIcons.forEach(el => el.style.display = 'inline');
    lightIcons.forEach(el => el.style.display = 'none');
  }
}

function applyLanguage(lang) {
  currentLang = lang;
  localStorage.setItem('aov_lang', lang);

  const langPills = document.querySelectorAll('.lang-text');
  langPills.forEach(el => el.textContent = lang.toUpperCase());

  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n');
    if (translations[lang] && translations[lang][key]) {
      el.textContent = translations[lang][key];
    }
  });
}

// Bind Theme / Lang switches
const btnToggleTheme = document.getElementById('btnToggleTheme');
const btnStudioTheme = document.getElementById('btnStudioTheme');
const btnToggleLang = document.getElementById('btnToggleLang');
const btnStudioLang = document.getElementById('btnStudioLang');

if (btnToggleTheme) btnToggleTheme.addEventListener('click', () => applyTheme(currentTheme === 'dark' ? 'light' : 'dark'));
if (btnStudioTheme) btnStudioTheme.addEventListener('click', () => applyTheme(currentTheme === 'dark' ? 'light' : 'dark'));
if (btnToggleLang) btnToggleLang.addEventListener('click', () => applyLanguage(currentLang === 'vi' ? 'en' : 'vi'));
if (btnStudioLang) btnStudioLang.addEventListener('click', () => applyLanguage(currentLang === 'vi' ? 'en' : 'vi'));

// ── AI Studio Copilot RAG Drawer Engine ─────────────────────────────────────
const aiCopilotDrawer = document.getElementById('aiCopilotDrawer');
const btnOpenAICopilot = document.getElementById('btnOpenAICopilot');
const btnCloseAICopilot = document.getElementById('btnCloseAICopilot');
const aiChatForm = document.getElementById('aiChatForm');
const aiChatInput = document.getElementById('aiChatInput');
const aiChatBody = document.getElementById('aiChatBody');
const aiPromptChips = document.querySelectorAll('.ai-prompt-chip');

function toggleAICopilot(open = true) {
  if (!aiCopilotDrawer) return;
  if (open) {
    aiCopilotDrawer.classList.add('open');
    if (aiChatInput) aiChatInput.focus();
  } else {
    aiCopilotDrawer.classList.remove('open');
  }
}

if (btnOpenAICopilot) btnOpenAICopilot.addEventListener('click', () => toggleAICopilot(true));
if (btnCloseAICopilot) btnCloseAICopilot.addEventListener('click', () => toggleAICopilot(false));

aiPromptChips.forEach(chip => {
  chip.addEventListener('click', () => {
    const query = chip.getAttribute('data-query');
    if (query && aiChatInput) {
      aiChatInput.value = query;
      sendAIMessage(query);
    }
  });
});

async function sendAIMessage(prompt) {
  if (!prompt || !prompt.trim()) return;
  appendChatMessage('user', prompt);
  if (aiChatInput) aiChatInput.value = '';

  const typingMsg = appendChatMessage('assistant', 'Đang suy nghĩ và đối soát dữ liệu RAG...', true);

  try {
    const res = await fetch('/api/ai/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        prompt: prompt,
        task_id: activeTaskId || ''
      })
    });
    const data = await res.json();
    if (typingMsg) typingMsg.remove();

    if (data.status === 'ok') {
      appendChatMessage('assistant', data.response);
    } else {
      appendChatMessage('assistant', data.error || 'Trợ lý AI gặp sự cố kết nối.');
    }
  } catch (err) {
    if (typingMsg) typingMsg.remove();
    appendChatMessage('assistant', 'Lỗi kết nối tới AI Copilot.');
  }
}

function appendChatMessage(role, text, isTyping = false) {
  if (!aiChatBody) return null;
  const msgEl = document.createElement('div');
  msgEl.className = `ai-message ${role}`;
  if (isTyping) msgEl.classList.add('typing-indicator');

  const avatar = document.createElement('div');
  avatar.className = 'msg-avatar';
  avatar.textContent = role === 'user' ? 'U' : '🤖';

  const bubble = document.createElement('div');
  bubble.className = 'msg-bubble';
  bubble.innerHTML = text.replace(/\n/g, '<br/>');

  msgEl.appendChild(avatar);
  msgEl.appendChild(bubble);
  aiChatBody.appendChild(msgEl);
  aiChatBody.scrollTop = aiChatBody.scrollHeight;
  return msgEl;
}

if (aiChatForm) {
  aiChatForm.addEventListener('submit', (e) => {
    e.preventDefault();
    const val = aiChatInput.value.trim();
    if (val) sendAIMessage(val);
  });
}

// ── Admin Master Dashboard Engine ──────────────────────────────────────────
const adminUsersTbody = document.getElementById('adminUsersTbody');
const adminGiftcodesTbody = document.getElementById('adminGiftcodesTbody');
const adminUserCount = document.getElementById('adminUserCount');
const btnRefreshAdminData = document.getElementById('btnRefreshAdminData');
const adminCreateGiftcodeForm = document.getElementById('adminCreateGiftcodeForm');
const modalAdminCredits = document.getElementById('modalAdminCredits');
const modalTargetUsername = document.getElementById('modalTargetUsername');
const modalCreditsDelta = document.getElementById('modalCreditsDelta');
const formAdminAdjustCredits = document.getElementById('formAdminAdjustCredits');
const btnCloseModalCredits = document.getElementById('btnCloseModalCredits');
const btnCancelModalCredits = document.getElementById('btnCancelModalCredits');
let adminSelectedUser = null;

async function loadAdminDashboard() {
  if (!currentUser) return;
  await Promise.all([loadAdminUsers(), loadAdminGiftcodes()]);
}

async function loadAdminUsers() {
  if (!adminUsersTbody) return;
  try {
    const res = await fetch(`/api/admin/users?admin_id=${currentUser.id}`);
    const data = await res.json();
    if (data.status === 'ok') {
      const users = data.users || [];
      if (adminUserCount) adminUserCount.textContent = `${users.length} Người dùng`;
      adminUsersTbody.innerHTML = '';

      users.forEach(u => {
        const tr = document.createElement('tr');
        const roleBadgeClass = u.role === 'owner' ? 'badge-role-owner' : (u.role === 'admin' ? 'badge-role-admin' : 'badge-role-user');

        let actionsHtml = `<div class="action-btn-group">
          <button class="btn btn-sm btn-ghost btn-adj-cr" data-username="${u.username}">+ CR</button>`;

        if (currentUser.role === 'owner' && u.role !== 'owner') {
          if (u.role === 'admin') {
            actionsHtml += `<button class="btn btn-sm btn-ghost btn-demote" data-uid="${u.id}">Hạ User</button>`;
          } else {
            actionsHtml += `<button class="btn btn-sm btn-ghost btn-promote" data-uid="${u.id}">Lên Admin</button>`;
          }
        }
        actionsHtml += `</div>`;

        tr.innerHTML = `
          <td>#${u.id}</td>
          <td><strong>${escapeHtml(u.username)}</strong></td>
          <td><span class="${roleBadgeClass}">${(u.role || 'user').toUpperCase()}</span></td>
          <td><code>${u.credits.toLocaleString()} CR</code></td>
          <td><code style="font-size:11px;">${escapeHtml(u.api_key || '-')}</code></td>
          <td>${actionsHtml}</td>
        `;
        adminUsersTbody.appendChild(tr);
      });

      // Bind dynamic actions
      adminUsersTbody.querySelectorAll('.btn-adj-cr').forEach(btn => {
        btn.addEventListener('click', () => {
          const uname = btn.getAttribute('data-username');
          openAdjustCreditsModal(uname);
        });
      });

      adminUsersTbody.querySelectorAll('.btn-promote').forEach(btn => {
        btn.addEventListener('click', async () => {
          const uid = btn.getAttribute('data-uid');
          await updateAdminRole(uid, 'admin');
        });
      });

      adminUsersTbody.querySelectorAll('.btn-demote').forEach(btn => {
        btn.addEventListener('click', async () => {
          const uid = btn.getAttribute('data-uid');
          await updateAdminRole(uid, 'user');
        });
      });
    }
  } catch (e) {
    console.error('Load admin users error:', e);
  }
}

async function updateAdminRole(targetUserId, newRole) {
  if (!confirm(`Xác nhận đổi quyền người dùng #${targetUserId} thành ${newRole.toUpperCase()}?`)) return;
  try {
    const res = await fetch('/api/admin/update-role', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        admin_id: currentUser.id,
        target_user_id: targetUserId,
        new_role: newRole
      })
    });
    const data = await res.json();
    if (data.status === 'ok') {
      showToast('ĐÃ CẬP NHẬT PHÂN QUYỀN!');
      loadAdminUsers();
    } else {
      showToast(data.error || 'Thao tác thất bại');
    }
  } catch (err) {
    showToast('Lỗi máy chủ');
  }
}

function openAdjustCreditsModal(username) {
  adminSelectedUser = username;
  if (modalTargetUsername) modalTargetUsername.value = username;
  if (modalCreditsDelta) modalCreditsDelta.value = '100';
  if (modalAdminCredits) modalAdminCredits.style.display = 'flex';
}

function closeAdjustCreditsModal() {
  if (modalAdminCredits) modalAdminCredits.style.display = 'none';
}

if (btnCloseModalCredits) btnCloseModalCredits.addEventListener('click', closeAdjustCreditsModal);
if (btnCancelModalCredits) btnCancelModalCredits.addEventListener('click', closeAdjustCreditsModal);

if (formAdminAdjustCredits) {
  formAdminAdjustCredits.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!adminSelectedUser || !currentUser) return;
    const delta = parseInt(modalCreditsDelta.value, 10);
    try {
      const res = await fetch('/api/admin/adjust-credits', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          admin_id: currentUser.id,
          target_username: adminSelectedUser,
          credits_delta: delta
        })
      });
      const data = await res.json();
      if (data.status === 'ok') {
        showToast(`ĐÃ CẬP NHẬT CREDITS CHO ${adminSelectedUser}!`);
        closeAdjustCreditsModal();
        loadAdminUsers();
        refreshUserMeta();
      } else {
        showToast(data.error || 'Cập nhật thất bại');
      }
    } catch (err) {
      showToast('Lỗi kết nối máy chủ');
    }
  });
}

async function loadAdminGiftcodes() {
  if (!adminGiftcodesTbody) return;
  try {
    const res = await fetch(`/api/admin/giftcodes?admin_id=${currentUser.id}`);
    const data = await res.json();
    if (data.status === 'ok') {
      const codes = data.giftcodes || [];
      adminGiftcodesTbody.innerHTML = '';
      codes.forEach(c => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td><code>${escapeHtml(c.code)}</code></td>
          <td><strong style="color:var(--green);">+${c.credits} CR</strong></td>
          <td>${c.used_count || 0} / ${c.max_uses}</td>
          <td>
            <button class="btn btn-sm btn-ghost btn-del-giftcode" data-code="${escapeHtml(c.code)}" style="color:var(--red);">Xóa</button>
          </td>
        `;
        adminGiftcodesTbody.appendChild(tr);
      });

      adminGiftcodesTbody.querySelectorAll('.btn-del-giftcode').forEach(btn => {
        btn.addEventListener('click', async () => {
          const code = btn.getAttribute('data-code');
          if (!confirm(`Xóa giftcode ${code}?`)) return;
          try {
            const res = await fetch('/api/admin/delete-giftcode', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ admin_id: currentUser.id, code })
            });
            const d = await res.json();
            if (d.status === 'ok') {
              showToast(`ĐÃ XÓA MÃ ${code}`);
              loadAdminGiftcodes();
            } else {
              showToast(d.error || 'Xóa thất bại');
            }
          } catch (e) {
            showToast('Lỗi máy chủ');
          }
        });
      });
    }
  } catch (e) {
    console.error('Load giftcodes error:', e);
  }
}

if (adminCreateGiftcodeForm) {
  adminCreateGiftcodeForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!currentUser) return;
    const code = document.getElementById('newGiftcodeCode').value.trim().toUpperCase();
    const credits = parseInt(document.getElementById('newGiftcodeCredits').value, 10);
    const maxUses = parseInt(document.getElementById('newGiftcodeMaxUses').value, 10);

    try {
      const res = await fetch('/api/admin/create-giftcode', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          admin_id: currentUser.id,
          code,
          credits,
          max_uses: maxUses
        })
      });
      const data = await res.json();
      if (data.status === 'ok') {
        showToast(`TẠO MÃ ${code} THÀNH CÔNG!`);
        document.getElementById('newGiftcodeCode').value = '';
        loadAdminGiftcodes();
      } else {
        showToast(data.error || 'Tạo mã thất bại');
      }
    } catch (err) {
      showToast('Lỗi máy chủ');
    }
  });
}

if (btnRefreshAdminData) {
  btnRefreshAdminData.addEventListener('click', () => {
    loadAdminDashboard();
    showToast('ĐÃ LÀM MỚI DỮ LIỆU ADMIN');
  });
}

// Init theme & language on startup
applyTheme(currentTheme);
applyLanguage(currentLang);

// Bootstrap
initApp();
