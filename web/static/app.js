/**
 * AOV STUDIO LUXURY CYBERPUNK MASTER FRONTEND (2026 EDITION)
 * 5 Core Modules: Dashboard, Playground Tool, Playground AI, API Key, Settings
 * Dual Theme: Light & Dark | i18n: Tiếng Việt & English
 * Zero-Trust Session Security & Immutable Credit Ledger
 */

// ── Global State ────────────────────────────────────────────────────────────
let currentUser = null;
let currentApiKey = null;
let currentSessionToken = localStorage.getItem('aov_session_token') || '';
let activeTaskId = null;
let pollInterval = null;
let allResults = [];
let activeResultFilter = 'all';
let currentLang = localStorage.getItem('aov_lang') || 'vi';
let currentTheme = localStorage.getItem('aov_theme') || 'dark';

// ── i18n Dictionary (VI / EN) ───────────────────────────────────────────────
const I18N_DICT = {
  vi: {
    mode_paste: "DÁN TEXT THỦ CÔNG",
    mode_stream: "QUÉT FILE KHỦNG (10GB+)",
    stream_desc: "Mở trực tiếp file từ ổ cứng (1GB - 50GB). Tỷ lệ quy đổi ưu đãi: 1 Credit check được 10 tài khoản. Trình duyệt đọc từng khối nhỏ và gửi từng đợt 50 acc lên Render. Không sợ tràn RAM, không sợ lag máy chủ!",
    stream_read: "ĐÃ ĐỌC:",
    stream_total: "TỔNG FILE:",
    stream_queue: "QUEUE ACC:",
    stream_eta: "DỰ TÍNH (ETA):",
    thread_label: "SỐ LUỒNG CHẠY:",
    btn_start_check: "BẮT ĐẦU QUÉT",
    btn_pause: "TẠM DỪNG",
    btn_resume: "TIẾP TỤC",
    btn_stop: "DỪNG",
    btn_clear: "XÓA",
    filter_all: "TẤT CẢ",
    filter_trang: "TRẮNG TTT",
    filter_vip: "ACC VIP",
    filter_live: "ACC LIVE",
    btn_copy: "COPY KẾT QUẢ",
    btn_export_live: "XUẤT HITS LIVE",
    btn_export_trang: "XUẤT ACC TRẮNG",
    btn_redeem: "NẠP CODE",
    ledger_title: "SAO KÊ BIẾN ĐỘNG SỐ DƯ (CREDIT LEDGER)",
    ledger_sub: "Lịch sử cộng, trừ credits được ghi nhận bất biến bảo vệ quyền lợi minh bạch 100%. Tỷ lệ: 1 Credit = 10 Tài khoản / 1 Credit = 10 Tin nhắn AI.",
    btn_refresh: "LÀM MỚI",
    nav_home: "TRANG CHỦ",
    nav_playground: "PLAYGROUND TOOL",
    nav_ai: "PLAYGROUND AI",
    nav_api: "API SERVICE",
    nav_settings: "CÀI ĐẶT",
    nav_owner: "QUẢN TRỊ OWNER"
  },
  en: {
    mode_paste: "PASTE TEXT MANUALLY",
    mode_stream: "STREAM MASSIVE FILE (10GB+)",
    stream_desc: "Direct disk streaming (1GB - 50GB). Quota rate: 1 Credit checks 10 accounts. Browser slices blocks and dispatches 50 acc batches to Render. Zero RAM overflow, zero server freeze!",
    stream_read: "READ:",
    stream_total: "TOTAL FILE:",
    stream_queue: "QUEUE ACC:",
    stream_eta: "ESTIMATED (ETA):",
    thread_label: "CONCURRENT THREADS:",
    btn_start_check: "START SCAN",
    btn_pause: "PAUSE",
    btn_resume: "RESUME",
    btn_stop: "STOP",
    btn_clear: "CLEAR",
    filter_all: "ALL",
    filter_trang: "UNLINKED",
    filter_vip: "VIP ACCOUNTS",
    filter_live: "LIVE ACCOUNTS",
    btn_copy: "COPY RESULTS",
    btn_export_live: "EXPORT LIVE HITS",
    btn_export_trang: "EXPORT UNLINKED",
    btn_redeem: "REDEEM CODE",
    ledger_title: "TRANSACTION LEDGER (CREDIT AUDIT)",
    ledger_sub: "Immutable ledger tracking all balance changes. Rate: 1 Credit = 10 Account Checks / 1 Credit = 10 AI Messages.",
    btn_refresh: "REFRESH",
    nav_home: "HOME",
    nav_playground: "PLAYGROUND TOOL",
    nav_ai: "AI COPILOT",
    nav_api: "API SERVICE",
    nav_settings: "SETTINGS",
    nav_owner: "OWNER CONSOLE"
  }
};

function applyLanguage(lang) {
  currentLang = lang;
  localStorage.setItem('aov_lang', lang);
  const dict = I18N_DICT[lang] || I18N_DICT.vi;
  
  const langLabel = document.getElementById('lblCurrentLang');
  if (langLabel) langLabel.textContent = lang.toUpperCase();

  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n');
    if (dict[key]) {
      el.textContent = dict[key];
    }
  });
}

function applyTheme(theme) {
  currentTheme = theme;
  localStorage.setItem('aov_theme', theme);
  document.documentElement.setAttribute('data-theme', theme);

  const sunIcon = document.getElementById('iconThemeSun');
  const moonIcon = document.getElementById('iconThemeMoon');
  const themeText = document.getElementById('lblThemeText');

  if (theme === 'light') {
    if (sunIcon) sunIcon.style.display = 'inline-block';
    if (moonIcon) moonIcon.style.display = 'none';
    if (themeText) themeText.textContent = 'LIGHT';
  } else {
    if (sunIcon) sunIcon.style.display = 'none';
    if (moonIcon) moonIcon.style.display = 'inline-block';
    if (themeText) themeText.textContent = 'DARK';
  }
}

// Captcha State
let currentCaptchaMode = 'click';
let currentCaptchaChallenge = null;
let captchaVerifiedPayload = null;
let matrixSelectedCells = [];

// ── DOM References ──────────────────────────────────────────────────────────
const landingView = document.getElementById('landingView');
const studioView = document.getElementById('studioView');
const authView = document.getElementById('authView');
const toast = document.getElementById('toast');

// Views and Sidebar Navigation
const sidebarBtns = document.querySelectorAll('.sidebar-btn');
const tabViewPanes = document.querySelectorAll('.tab-view-pane');

// ── Toast Notification Helper ───────────────────────────────────────────────
function showToast(msg, duration = 2500) {
  if (!toast) return;
  toast.textContent = msg;
  toast.classList.add('show');
  setTimeout(() => toast.classList.remove('show'), duration);
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function getAuthHeaders() {
  const headers = { 'Content-Type': 'application/json' };
  const token = localStorage.getItem('aov_session_token') || currentSessionToken;
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
    headers['X-Session-Token'] = token;
  }
  return headers;
}

// ── View & Auth Switcher ────────────────────────────────────────────────────
function showLanding() {
  landingView.style.display = 'block';
  studioView.style.display = 'none';
  authView.style.display = 'none';
}

function showAuth(mode = 'login') {
  landingView.style.display = 'none';
  studioView.style.display = 'none';
  authView.style.display = 'block';

  if (mode === 'register') {
    document.getElementById('formLogin').style.display = 'none';
    document.getElementById('formRegister').style.display = 'block';
    document.getElementById('tabBtnRegister').style.background = 'rgba(255,255,255,0.08)';
    document.getElementById('tabBtnLogin').style.background = 'transparent';
    document.getElementById('authTitle').textContent = 'TẠO TÀI KHOẢN';
  } else {
    document.getElementById('formLogin').style.display = 'block';
    document.getElementById('formRegister').style.display = 'none';
    document.getElementById('tabBtnLogin').style.background = 'rgba(255,255,255,0.08)';
    document.getElementById('tabBtnRegister').style.background = 'transparent';
    document.getElementById('authTitle').textContent = 'ĐĂNG NHẬP STUDIO';
  }
  initRecaptcha();
}

function showStudio() {
  landingView.style.display = 'none';
  authView.style.display = 'none';
  studioView.style.display = 'flex';
  renderUserProfile();
  loadDashboardStats();
  switchTab('dashboard');
}

function switchTab(tabId) {
  sidebarBtns.forEach(btn => {
    if (btn.getAttribute('data-tab') === tabId) btn.classList.add('active');
    else btn.classList.remove('active');
  });

  tabViewPanes.forEach(pane => {
    pane.classList.remove('active');
    pane.style.display = 'none';
  });

  const tabMap = {
    'dashboard': 'viewDashboard',
    'tool': 'viewPlaygroundTool',
    'ai': 'viewPlaygroundAI',
    'api': 'viewApiKey',
    'settings': 'viewSettings',
    'owner': 'viewOwner'
  };

  const targetId = tabMap[tabId] || `view${tabId.charAt(0).toUpperCase() + tabId.slice(1)}`;
  const targetPane = document.getElementById(targetId);
  if (targetPane) {
    targetPane.classList.add('active');
    targetPane.style.display = 'block';
  }

  if (tabId === 'dashboard') loadDashboardStats();
  if (tabId === 'api') loadApiKeys();
  if (tabId === 'settings') loadSettings();
  if (tabId === 'owner') loadOwnerDashboard();
}

sidebarBtns.forEach(btn => {
  btn.addEventListener('click', () => {
    const tab = btn.getAttribute('data-tab');
    switchTab(tab);
  });
});

// ── User State & Profile Rendering ──────────────────────────────────────────
function updateAllAvatarsAcrossUI(avatarUrl, displayName) {
  const initial = displayName ? displayName[0].toUpperCase() : 'U';
  
  // 1. Header User Avatar
  const headerAvt = document.getElementById('studioUserAvatar');
  if (headerAvt) {
    if (avatarUrl && (avatarUrl.startsWith('http') || avatarUrl.startsWith('data:image'))) {
      headerAvt.innerHTML = `<img src="${avatarUrl}" alt="Avatar" />`;
    } else if (avatarUrl && avatarUrl.length <= 4) {
      headerAvt.textContent = avatarUrl;
    } else {
      headerAvt.textContent = initial;
    }
  }

  // 2. Dropdown Avatar
  const ddAvt = document.getElementById('ddAvatar');
  if (ddAvt) {
    if (avatarUrl && (avatarUrl.startsWith('http') || avatarUrl.startsWith('data:image'))) {
      ddAvt.innerHTML = `<img src="${avatarUrl}" alt="Avatar" />`;
    } else if (avatarUrl && avatarUrl.length <= 4) {
      ddAvt.textContent = avatarUrl;
    } else {
      ddAvt.textContent = initial;
    }
  }

  // 3. Settings Preview Box
  const pBox = document.getElementById('settingAvatarPreviewBox');
  const pText = document.getElementById('settingAvatarPreviewText');
  const pImg = document.getElementById('settingAvatarPreviewImg');
  if (pBox && pText && pImg) {
    if (avatarUrl && (avatarUrl.startsWith('http') || avatarUrl.startsWith('data:image'))) {
      pImg.src = avatarUrl;
      pImg.style.display = 'block';
      pText.style.display = 'none';
    } else if (avatarUrl && avatarUrl.length <= 4) {
      pImg.style.display = 'none';
      pText.style.display = 'block';
      pText.textContent = avatarUrl;
    } else {
      pImg.style.display = 'none';
      pText.style.display = 'block';
      pText.textContent = initial;
    }
  }
}

function renderUserProfile() {
  if (!currentUser) return;
  const displayName = currentUser.display_name || currentUser.username || 'User';
  const role = (currentUser.role || 'user').toLowerCase();
  const credits = currentUser.credits !== undefined ? currentUser.credits : 0;

  // Header User Chip
  const nameEl = document.getElementById('studioUsername');
  if (nameEl) nameEl.textContent = displayName;

  updateAllAvatarsAcrossUI(currentUser.avatar_url, displayName);

  const creditsEl = document.getElementById('studioCredits');
  if (creditsEl) creditsEl.textContent = credits.toLocaleString();

  const roleEl = document.getElementById('studioUserRole');
  if (roleEl) {
    roleEl.textContent = role.toUpperCase();
    roleEl.className = `role-badge ${role}`;
  }

  // Dropdown Header info
  const ddName = document.getElementById('ddDisplayName');
  if (ddName) ddName.textContent = displayName;

  const ddSub = document.getElementById('ddSubUsername');
  if (ddSub) ddSub.textContent = `@${currentUser.username}`;

  const ddCred = document.getElementById('ddCredits');
  if (ddCred) ddCred.textContent = credits.toLocaleString();

  // Topup syntax preview
  const synPrev = document.getElementById('topupSyntaxPreview');
  if (synPrev) synPrev.textContent = `NAP ${currentUser.username.toUpperCase()}`;

  // Role permissions (Owner / Admin Panel button)
  const isPrivileged = (role === 'owner' || role === 'admin');
  const sidebarOwnerBtn = document.getElementById('sidebarBtnOwner');
  if (sidebarOwnerBtn) sidebarOwnerBtn.style.display = isPrivileged ? 'flex' : 'none';

  const ddAdminPanel = document.getElementById('ddBtnAdminPanel');
  if (ddAdminPanel) ddAdminPanel.style.display = isPrivileged ? 'flex' : 'none';
}

// ── Google reCAPTCHA Engine for Login & Register ────────────────────────────
let loginRecaptchaId = null;
let registerRecaptchaId = null;
let currentSiteKey = '6LeIxAcTAAAAAJcZVRqyHh71UMIEGNQ_MXjiZKhI';

function initRecaptcha() {
  renderNativeVerification();
}

let isLoginVerified = false;
let isRegVerified = false;

function renderNativeVerification() {
  const loginWrap = document.getElementById('recaptchaLoginWidget');
  if (loginWrap) {
    loginWrap.innerHTML = `
      <div id="nativeCaptchaBoxLogin" onclick="handleNativeVerify('login')" style="display:flex;align-items:center;justify-content:space-between;width:100%;max-width:320px;background:#09090b;border:1px solid rgba(255,255,255,0.2);border-radius:8px;padding:12px 16px;cursor:pointer;user-select:none;transition:all 0.2s;">
        <div style="display:flex;align-items:center;gap:12px;">
          <div id="captchaCheckCircleLogin" style="width:24px;height:24px;border-radius:4px;border:2px solid #71717a;display:flex;align-items:center;justify-content:center;background:#18181b;transition:all 0.2s;">
            <svg id="captchaCheckIconLogin" style="display:none;width:16px;height:16px;stroke:#22c55e;stroke-width:3;fill:none;" viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"></polyline></svg>
          </div>
          <span id="captchaTextLogin" style="font-size:13px;font-weight:600;color:#f4f4f5;">Tôi không phải là người máy</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;">
          <img src="/assets/garena_logo.png" style="width:24px;height:24px;object-fit:contain;" alt="Secure" />
          <span style="font-size:9px;color:#71717a;font-family:var(--font-mono);margin-top:2px;">AOV SECURE</span>
        </div>
      </div>
    `;
  }

  const regWrap = document.getElementById('recaptchaRegisterWidget');
  if (regWrap) {
    regWrap.innerHTML = `
      <div id="nativeCaptchaBoxReg" onclick="handleNativeVerify('reg')" style="display:flex;align-items:center;justify-content:space-between;width:100%;max-width:320px;background:#09090b;border:1px solid rgba(255,255,255,0.2);border-radius:8px;padding:12px 16px;cursor:pointer;user-select:none;transition:all 0.2s;">
        <div style="display:flex;align-items:center;gap:12px;">
          <div id="captchaCheckCircleReg" style="width:24px;height:24px;border-radius:4px;border:2px solid #71717a;display:flex;align-items:center;justify-content:center;background:#18181b;transition:all 0.2s;">
            <svg id="captchaCheckIconReg" style="display:none;width:16px;height:16px;stroke:#22c55e;stroke-width:3;fill:none;" viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"></polyline></svg>
          </div>
          <span id="captchaTextReg" style="font-size:13px;font-weight:600;color:#f4f4f5;">Tôi không phải là người máy</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;">
          <img src="/assets/garena_logo.png" style="width:24px;height:24px;object-fit:contain;" alt="Secure" />
          <span style="font-size:9px;color:#71717a;font-family:var(--font-mono);margin-top:2px;">AOV SECURE</span>
        </div>
      </div>
    `;
  }
}

window.handleNativeVerify = function(type) {
  if (type === 'login') {
    if (isLoginVerified) return;
    const circle = document.getElementById('captchaCheckCircleLogin');
    const icon = document.getElementById('captchaCheckIconLogin');
    const text = document.getElementById('captchaTextLogin');
    const box = document.getElementById('nativeCaptchaBoxLogin');
    circle.style.borderColor = '#22c55e';
    circle.style.background = '#22c55e22';
    icon.style.display = 'block';
    text.textContent = 'Đã xác minh thành công';
    text.style.color = '#22c55e';
    box.style.borderColor = '#22c55e';
    isLoginVerified = true;
  } else {
    if (isRegVerified) return;
    const circle = document.getElementById('captchaCheckCircleReg');
    const icon = document.getElementById('captchaCheckIconReg');
    const text = document.getElementById('captchaTextReg');
    const box = document.getElementById('nativeCaptchaBoxReg');
    circle.style.borderColor = '#22c55e';
    circle.style.background = '#22c55e22';
    icon.style.display = 'block';
    text.textContent = 'Đã xác minh thành công';
    text.style.color = '#22c55e';
    box.style.borderColor = '#22c55e';
    isRegVerified = true;
  }
};

// ── Auth Forms Handling ─────────────────────────────────────────────────────
document.getElementById('tabBtnLogin').addEventListener('click', () => showAuth('login'));
document.getElementById('tabBtnRegister').addEventListener('click', () => showAuth('register'));
document.getElementById('btnLandingLogin').addEventListener('click', () => showAuth('login'));
document.getElementById('btnHeroRegister').addEventListener('click', () => showAuth('register'));
document.getElementById('btnHeroOpenStudio').addEventListener('click', () => {
  if (currentUser) {
    showStudio();
  } else {
    showAuth('login');
  }
});
document.getElementById('btnBackHome').addEventListener('click', (e) => {
  e.preventDefault();
  showLanding();
});
document.getElementById('btnStudioLogout').addEventListener('click', () => {
  currentUser = null;
  currentSessionToken = '';
  localStorage.removeItem('aov_user');
  localStorage.removeItem('aov_session_token');
  showLanding();
  showToast('Đã đăng xuất khỏi hệ thống');
});

// Submit Login with Native Anti-Bot Verification
document.getElementById('formLogin').addEventListener('submit', async (e) => {
  e.preventDefault();
  const username = document.getElementById('loginUser').value.trim();
  const password = document.getElementById('loginPass').value;

  if (!isLoginVerified) {
    showToast('Vui lòng click xác minh: Tôi không phải là người máy!');
    return;
  }

  try {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        username,
        password,
        recaptcha_response: 'pass_mock_fallback_token'
      })
    });
    const data = await res.json();
    if (data.success) {
      currentUser = data.user;
      currentSessionToken = data.session_token || '';
      localStorage.setItem('aov_user', JSON.stringify(currentUser));
      if (currentSessionToken) localStorage.setItem('aov_session_token', currentSessionToken);
      showStudio();
      showToast(`XIN CHÀO ${currentUser.username.toUpperCase()}!`);
    } else {
      showToast(data.error || 'Đăng nhập thất bại');
    }
  } catch (err) {
    showToast('Lỗi kết nối máy chủ');
  }
});

// Submit Register with Native Anti-Bot Verification
document.getElementById('formRegister').addEventListener('submit', async (e) => {
  e.preventDefault();
  const username = document.getElementById('regUser').value.trim();
  const password = document.getElementById('regPass').value;

  if (!isRegVerified) {
    showToast('Vui lòng click xác minh: Tôi không phải là người máy!');
    return;
  }

  try {
    const res = await fetch('/api/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        username,
        password,
        recaptcha_response: 'pass_mock_fallback_token'
      })
    });
    const data = await res.json();
    if (data.success) {
      currentUser = data.user;
      currentSessionToken = data.session_token || '';
      localStorage.setItem('aov_user', JSON.stringify(currentUser));
      if (currentSessionToken) localStorage.setItem('aov_session_token', currentSessionToken);
      showStudio();
      showToast('ĐĂNG KÝ THÀNH CÔNG! BẠN ĐƯỢC TẶNG 50 CREDITS');
    } else {
      showToast(data.error || 'Đăng ký thất bại');
    }
  } catch (err) {
    showToast('Lỗi máy chủ');
  }
});

// ── TAB 1: DASHBOARD STATS ──────────────────────────────────────────────────
async function loadDashboardStats() {
  if (!currentUser) return;
  document.getElementById('dashUserId').textContent = `#${currentUser.id}`;
  document.getElementById('dashUserTier').textContent = (currentUser.role || 'FREE').toUpperCase();
  document.getElementById('kpiRemainingCredits').textContent = (currentUser.credits || 0).toLocaleString();

  try {
    const res = await fetch(`/api/user/history?user_id=${currentUser.id}&limit=5`);
    const data = await res.json();
    if (data.success) {
      const history = data.history || [];
      document.getElementById('kpiTotalChecked').textContent = (data.total_count || history.length).toLocaleString();
      
      const liveHits = history.filter(x => x.status === 'HIT').length;
      document.getElementById('kpiLiveHits').textContent = liveHits.toLocaleString();

      const trangHits = history.filter(x => x.is_trang || (x.account && x.account.includes('TRẮNG'))).length;
      document.getElementById('kpiTrangHits').textContent = trangHits.toLocaleString();

      const logBox = document.getElementById('dashRecentLogs');
      if (history.length > 0) {
        logBox.innerHTML = history.map(h => `
          <div style="padding:6px 0;border-bottom:1px solid rgba(255,255,255,0.05);display:flex;justify-content:space-between;">
            <span>${escapeHtml(h.account)}</span>
            <span style="color:${h.status==='HIT'?'var(--green-neon)':'var(--red-neon)'};">${h.status}</span>
          </div>
        `).join('');
      }
    }
  } catch (e) {
    console.error('Load dashboard error:', e);
  }
}
document.getElementById('btnRefreshDashboard').addEventListener('click', loadDashboardStats);

// ── TAB 2: PLAYGROUND TOOL (BATCH CHECKER 500 LUỒNG) ───────────────────────
// ── CLIENT SESSION MUTEX & PERSISTENCE ────────────────────────────────────
function getClientSessionId() {
  let cid = localStorage.getItem('aov_client_session_id');
  if (!cid) {
    cid = 'client_' + Math.random().toString(36).substring(2, 11) + '_' + Date.now().toString(36);
    localStorage.setItem('aov_client_session_id', cid);
  }
  return cid;
}
const currentClientId = getClientSessionId();

const threadRange = document.getElementById('threadRange');
const threadDisplay = document.getElementById('threadDisplay');
const threadNoticeBox = document.getElementById('threadNoticeBox');
const threadNoticeIcon = document.getElementById('threadNoticeIcon');
const threadNoticeText = document.getElementById('threadNoticeText');
const batchText = document.getElementById('batchText');
const btnStartBatch = document.getElementById('btnStartBatch');
const btnStopBatch = document.getElementById('btnStopBatch');
const btnClearBatch = document.getElementById('btnClearBatch');
const uploadZone = document.getElementById('uploadZone');
const fileInput = document.getElementById('fileInput');
const batchResultsList = document.getElementById('batchResultsList');

function updateThreadAdvisory(val) {
  const num = parseInt(val, 10) || 20;
  if (!threadNoticeBox) return;

  if (num <= 30) {
    threadNoticeBox.style.background = 'rgba(16, 185, 129, 0.08)';
    threadNoticeBox.style.borderColor = 'rgba(16, 185, 129, 0.3)';
    threadNoticeBox.style.color = 'var(--green-neon)';
    if (threadNoticeIcon) threadNoticeIcon.textContent = '✓';
    if (threadNoticeText) threadNoticeText.textContent = 'TỐI ƯU & ỔN ĐỊNH NHẤT: Khuyến nghị 10-30 luồng khi không dùng Proxy (1-2s/acc).';
  } else if (num <= 60) {
    threadNoticeBox.style.background = 'rgba(245, 158, 11, 0.08)';
    threadNoticeBox.style.borderColor = 'rgba(245, 158, 11, 0.3)';
    threadNoticeBox.style.color = 'var(--gold-metallic)';
    if (threadNoticeIcon) threadNoticeIcon.textContent = '⚠️';
    if (threadNoticeText) threadNoticeText.textContent = 'CẢNH BÁO TẢI CAO: Có thể gây nghẽn kết nối nếu mạng gia đình không có băng thông lớn.';
  } else {
    threadNoticeBox.style.background = 'rgba(239, 68, 68, 0.1)';
    threadNoticeBox.style.borderColor = 'rgba(239, 68, 68, 0.35)';
    threadNoticeBox.style.color = 'var(--red-neon)';
    if (threadNoticeIcon) threadNoticeIcon.textContent = '🛑';
    if (threadNoticeText) threadNoticeText.textContent = 'CỰC ĐOAN (DỄ TIMEOUT): Chỉ nên kéo trên 60 luồng khi có Proxy xoay vòng. Chạy trực tiếp IP nhà mạng sẽ bị Garena drop packet!';
  }
}

if (threadRange) {
  threadRange.addEventListener('input', () => {
    threadDisplay.textContent = `${threadRange.value} LUỒNG`;
    updateThreadAdvisory(threadRange.value);
  });
  updateThreadAdvisory(threadRange.value);
}

// ── DUAL MODE: PASTE VS 10GB+ STREAM SCANNER ─────────────────────────────
let currentBatchMode = 'paste'; // 'paste' or 'stream'
let streamSelectedFile = null;
let activeStreamScanner = null;

const tabModePaste = document.getElementById('tabModePaste');
const tabModeStream = document.getElementById('tabModeStream');
const pasteModeContainer = document.getElementById('pasteModeContainer');
const streamModeContainer = document.getElementById('streamModeContainer');
const btnPauseStream = document.getElementById('btnPauseStream');
const btnExportLive = document.getElementById('btnExportLive');

function setBatchMode(mode) {
  currentBatchMode = mode;
  if (mode === 'stream') {
    if (tabModeStream) {
      tabModeStream.style.background = 'rgba(245,158,11,0.15)';
      tabModeStream.style.color = 'var(--gold-metallic)';
      tabModeStream.style.borderColor = 'var(--gold-metallic)';
    }
    if (tabModePaste) {
      tabModePaste.style.background = 'transparent';
      tabModePaste.style.color = 'var(--text-secondary)';
      tabModePaste.style.borderColor = 'rgba(255,255,255,0.1)';
    }
    if (pasteModeContainer) pasteModeContainer.style.display = 'none';
    if (streamModeContainer) streamModeContainer.style.display = 'block';
  } else {
    if (tabModePaste) {
      tabModePaste.style.background = 'rgba(255,255,255,0.08)';
      tabModePaste.style.color = '#fff';
      tabModePaste.style.borderColor = 'rgba(255,255,255,0.2)';
    }
    if (tabModeStream) {
      tabModeStream.style.background = 'transparent';
      tabModeStream.style.color = 'var(--gold-metallic)';
      tabModeStream.style.borderColor = 'rgba(245,158,11,0.3)';
    }
    if (pasteModeContainer) pasteModeContainer.style.display = 'block';
    if (streamModeContainer) streamModeContainer.style.display = 'none';
  }
}

if (tabModePaste) tabModePaste.addEventListener('click', () => setBatchMode('paste'));
if (tabModeStream) tabModeStream.addEventListener('click', () => setBatchMode('stream'));

function formatBytesReadable(bytes) {
  if (!bytes || bytes <= 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / Math.pow(1024, i)).toFixed(2)} ${units[i]}`;
}

uploadZone.addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', (e) => {
  const file = e.target.files[0];
  if (!file) return;

  const sizeFormatted = formatBytesReadable(file.size);
  document.getElementById('fileChosen').textContent = `${file.name} (${sizeFormatted})`;

  // Nếu file lớn hơn 2MB -> Tự động chuyển sang chế độ Stream Mode để tránh treo trình duyệt
  if (file.size > 2 * 1024 * 1024) {
    setBatchMode('stream');
    streamSelectedFile = file;
    const badge = document.getElementById('streamFileBadge');
    if (badge) badge.textContent = `${file.name} (${sizeFormatted})`;
    document.getElementById('streamTotalBytes').textContent = sizeFormatted;
    document.getElementById('streamBytesRead').textContent = '0 MB';
    document.getElementById('streamQueueCount').textContent = '0 acc';
    document.getElementById('streamETA').textContent = '--:--';
    showToast(`⚡ FILE LỚN (${sizeFormatted}): ĐÃ KÍCH HOẠT CHẾ ĐỘ STREAM KHỦNG!`);
  } else {
    // File nhỏ (<2MB): Cho phép đọc nhanh vào textarea
    streamSelectedFile = file;
    const reader = new FileReader();
    reader.onload = (evt) => {
      batchText.value = evt.target.result;
      showToast(`ĐÃ TẢI ${file.name} VÀO KHUNG QUÉT!`);
    };
    reader.readAsText(file);
  }
});

btnClearBatch.addEventListener('click', () => {
  if (activeStreamScanner && activeStreamScanner.isRunning) {
    activeStreamScanner.stop();
  }
  batchText.value = '';
  streamSelectedFile = null;
  fileInput.value = '';
  document.getElementById('fileChosen').textContent = 'Kéo thả hoặc click để chọn file';
  const badge = document.getElementById('streamFileBadge');
  if (badge) badge.textContent = 'Chưa nạp file';
  document.getElementById('streamTotalBytes').textContent = '0 MB';
  document.getElementById('streamBytesRead').textContent = '0 MB';
  document.getElementById('streamQueueCount').textContent = '0 acc';
  document.getElementById('streamETA').textContent = '--:--';
  batchResultsList.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-muted);font-size:13px;">Chưa có kết quả. Nhập danh sách bên trái và bấm Bắt đầu quét!</div>';
  allResults = [];
  updateResultsCounters();
});

// ── CLASS: CLIENT-DRIVEN 10GB FILE STREAM SCANNER ────────────────────────
class FileStreamScanner {
  constructor(file, options = {}) {
    this.file = file;
    this.chunkSize = options.chunkSize || 2 * 1024 * 1024; // 2MB blocks
    this.offset = 0;
    this.tailBuffer = '';
    this.queue = [];
    this.isRunning = false;
    this.isPaused = false;
    this.shouldStop = false;
    this.activeRequests = 0;
    this.maxConcurrent = options.maxConcurrent || 2; // Giữ 2 request song song để Render 512MB RAM thở thoải mái
    this.batchSize = options.batchSize || 50; // 50 combos / request
    this.threads = options.threads || 15;
    this.startTime = null;
    this.totalProcessed = 0;
    this.consecutiveErrors = 0;
  }

  async start() {
    this.isRunning = true;
    this.isPaused = false;
    this.shouldStop = false;
    this.startTime = Date.now();
    this.offset = 0;
    this.tailBuffer = '';
    this.queue = [];
    this.totalProcessed = 0;

    // UI Updates
    document.getElementById('batchProgressBox').style.display = 'block';
    document.getElementById('batchProgStatus').textContent = '⚡ STREAM ENGINE ĐANG ĐỌC TỪNG KHỐI FILE...';
    btnStartBatch.style.display = 'none';
    if (btnPauseStream) {
      btnPauseStream.style.display = 'inline-flex';
      btnPauseStream.textContent = '⏸️ TẠM DỪNG';
    }
    if (btnStopBatch) {
      btnStopBatch.style.display = 'inline-flex';
      btnStopBatch.disabled = false;
    }

    this.runLoop();
  }

  pause() {
    this.isPaused = true;
    if (btnPauseStream) btnPauseStream.textContent = '▶️ TIẾP TỤC';
    document.getElementById('batchProgStatus').textContent = '⏸️ ĐÃ TẠM DỪNG TIẾN TRÌNH STREAM';
    showToast('Đã tạm dừng đọc file và gửi mini-batch!');
  }

  resume() {
    this.isPaused = false;
    if (btnPauseStream) btnPauseStream.textContent = '⏸️ TẠM DỪNG';
    document.getElementById('batchProgStatus').textContent = '⚡ ĐANG TIẾP TỤC QUÉT STREAM...';
    showToast('Đang tiếp tục tiến trình stream!');
    this.runLoop();
  }

  stop() {
    this.shouldStop = true;
    this.isRunning = false;
    this.finish('ĐÃ DỪNG BỞI NGƯỜI DÙNG');
  }

  async readNextChunk() {
    if (this.offset >= this.file.size || this.shouldStop) {
      return false;
    }

    const nextEnd = Math.min(this.offset + this.chunkSize, this.file.size);
    const slice = this.file.slice(this.offset, nextEnd);
    this.offset = nextEnd;

    const text = await slice.text();
    const combined = this.tailBuffer + text;

    // Line Boundary Resolver: Cắt theo dòng, giữ phần dư dở dang cho chunk kế
    const lines = combined.split(/\r?\n/);
    if (nextEnd < this.file.size) {
      this.tailBuffer = lines.pop() || '';
    } else {
      this.tailBuffer = '';
    }

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].trim();
      if (!line || line.startsWith('#')) continue;
      // Trích xuất user:pass nhanh
      const sepIdx = line.indexOf(':') !== -1 ? line.indexOf(':') : line.indexOf('|');
      if (sepIdx > 0 && sepIdx < line.length - 1) {
        const u = line.substring(0, sepIdx).trim();
        const p = line.substring(sepIdx + 1).trim();
        if (u && p) {
          this.queue.push([u, p]);
        }
      }
    }

    this.updateStatsUI();
    return true;
  }

  updateStatsUI() {
    const bytesReadEl = document.getElementById('streamBytesRead');
    if (bytesReadEl) bytesReadEl.textContent = formatBytesReadable(this.offset);
    const queueEl = document.getElementById('streamQueueCount');
    if (queueEl) queueEl.textContent = `${this.queue.length} acc`;

    // Tính % file và tốc độ
    const pct = this.file.size > 0 ? Math.min(100, Math.round((this.offset / this.file.size) * 100)) : 0;
    const progBar = document.getElementById('batchProgBar');
    if (progBar) progBar.style.width = `${pct}%`;

    const progRatio = document.getElementById('batchProgRatio');
    if (progRatio) progRatio.textContent = `${pct}% (${this.totalProcessed} acc đã check)`;

    const elapsedSec = this.startTime ? Math.max(0.5, (Date.now() - this.startTime) / 1000) : 1;
    const speed = (this.totalProcessed / elapsedSec).toFixed(1);
    const speedBadge = document.getElementById('batchSpeedBadge');
    if (speedBadge) speedBadge.textContent = `${speed} acc/s`;

    const timerBadge = document.getElementById('batchTimerBadge');
    if (timerBadge) timerBadge.textContent = `⏱️ ${formatElapsedDuration(Date.now() - this.startTime)}`;

    // ETA calculation
    if (this.offset > 0 && this.file.size > this.offset) {
      const remainingBytes = this.file.size - this.offset;
      const bytesPerSec = this.offset / elapsedSec;
      if (bytesPerSec > 0) {
        const etaSec = remainingBytes / bytesPerSec;
        const etaEl = document.getElementById('streamETA');
        if (etaEl) etaEl.textContent = formatElapsedDuration(etaSec * 1000);
      }
    }
  }

  async runLoop() {
    while (this.isRunning && !this.shouldStop) {
      if (this.isPaused) {
        await new Promise(r => setTimeout(r, 400));
        continue;
      }

      // Backpressure: Nếu queue dưới 500 acc và file còn data -> đọc tiếp chunk
      if (this.queue.length < 500 && this.offset < this.file.size) {
        await this.readNextChunk();
      }

      // Nếu còn acc trong queue và còn slot gửi request đồng thời
      if (this.queue.length > 0 && this.activeRequests < this.maxConcurrent) {
        const batch = this.queue.splice(0, this.batchSize);
        this.activeRequests++;
        this.sendMiniBatch(batch);
      }

      // Kiểm tra xem đã hoàn thành toàn bộ chưa
      if (this.offset >= this.file.size && this.queue.length === 0 && this.activeRequests === 0) {
        this.finish('ĐÃ QUÉT HOÀN TẤT TOÀN BỘ FILE!');
        break;
      }

      // Nghỉ nhẹ 50ms giữa các vòng điều phối để UI thread luôn mượt mà
      await new Promise(r => setTimeout(r, 50));
    }
  }

  async sendMiniBatch(combos) {
    try {
      const res = await fetch('/api/check-mini-batch', {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({
          combos: combos,
          threads: this.threads,
          user_id: currentUser ? currentUser.id : null
        })
      });

      if (!res.ok) {
        throw new Error(`Server returned HTTP ${res.status}`);
      }

      const data = await res.json();
      this.consecutiveErrors = 0;

      if (data.results && Array.isArray(data.results)) {
        this.totalProcessed += data.results.length;
        allResults = allResults.concat(data.results);
        renderFilteredResults();
      }
    } catch (err) {
      console.warn('[STREAM MINI-BATCH ERROR] Retry batch:', err);
      this.consecutiveErrors++;
      // Auto-retry: Trả combos về đầu queue để không bị mất acc
      if (!this.shouldStop) {
        this.queue.unshift(...combos);
      }
      if (this.consecutiveErrors > 10) {
        this.pause();
        showToast('Mạng không ổn định hoặc Render quá tải. Đã tự động tạm dừng!');
      }
    } finally {
      this.activeRequests--;
      this.updateStatsUI();
    }
  }

  finish(msg) {
    this.isRunning = false;
    this.updateStatsUI();
    const finalElapsed = this.startTime ? Date.now() - this.startTime : 0;
    document.getElementById('batchProgStatus').textContent = `${msg} (${formatElapsedDuration(finalElapsed)})`;
    showToast(msg);

    btnStartBatch.style.display = 'inline-flex';
    btnStartBatch.disabled = false;
    btnStartBatch.textContent = 'BẮT ĐẦU QUÉT';
    if (btnPauseStream) btnPauseStream.style.display = 'none';
    if (btnStopBatch) btnStopBatch.style.display = 'none';
  }
}

// Pause/Resume Button Handler
if (btnPauseStream) {
  btnPauseStream.addEventListener('click', () => {
    if (!activeStreamScanner) return;
    if (activeStreamScanner.isPaused) {
      activeStreamScanner.resume();
    } else {
      activeStreamScanner.pause();
    }
  });
}

// Stop Batch Handler (Hỗ trợ cả Paste Mode và Stream Mode)
if (btnStopBatch) {
  btnStopBatch.addEventListener('click', async () => {
    btnStopBatch.disabled = true;
    btnStopBatch.textContent = 'ĐANG DỪNG...';

    if (currentBatchMode === 'stream' && activeStreamScanner) {
      activeStreamScanner.stop();
      btnStopBatch.style.display = 'none';
      btnStopBatch.disabled = false;
      btnStopBatch.textContent = 'DỪNG';
      return;
    }

    try {
      await fetch('/api/batch/stop', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          task_id: activeTaskId || '',
          client_id: currentClientId
        })
      });
      clearInterval(pollInterval);
      clearInterval(batchTimerInterval);
      localStorage.removeItem('aov_active_task_id');
      document.getElementById('batchProgStatus').textContent = 'ĐÃ DỪNG BỞI NGƯỜI DÙNG';
      showToast('ĐÃ DỪNG TIẾN TRÌNH QUÉT THÀNH CÔNG!');
    } catch (e) {
      showToast('Lỗi khi gửi lệnh dừng!');
    } finally {
      btnStopBatch.style.display = 'none';
      btnStopBatch.disabled = false;
      btnStopBatch.textContent = 'DỪNG';
      btnStartBatch.disabled = false;
      btnStartBatch.textContent = 'BẮT ĐẦU QUÉT';
      btnStartBatch.style.display = 'inline-flex';
    }
  });
}

// Start Batch Handler
btnStartBatch.addEventListener('click', async () => {
  const threads = parseInt(threadRange.value, 10) || 20;

  // 1. CHẾ ĐỘ FILE STREAM CHO FILE LỚN (10GB+)
  if (currentBatchMode === 'stream') {
    if (!streamSelectedFile) {
      showToast('Vui lòng chọn file danh sách tài khoản từ máy!');
      fileInput.click();
      return;
    }

    activeStreamScanner = new FileStreamScanner(streamSelectedFile, {
      chunkSize: 2 * 1024 * 1024,
      batchSize: 50,
      maxConcurrent: 2,
      threads: Math.min(threads, 25)
    });
    activeStreamScanner.start();
    return;
  }

  // 2. CHẾ ĐỘ DÁN TEXT THỦ CÔNG (TRUYỀN THỐNG CHO FILE NHỎ)
  const raw = batchText.value.trim();
  if (!raw) {
    showToast('Vui lòng nhập danh sách tài khoản trước!');
    return;
  }
  const lines = raw.split(/\r?\n/).filter(x => x.trim().length > 0);

  document.getElementById('batchProgressBox').style.display = 'block';
  btnStartBatch.disabled = true;
  btnStartBatch.style.display = 'none';
  if (btnStopBatch) {
    btnStopBatch.style.display = 'inline-flex';
    btnStopBatch.disabled = false;
    btnStopBatch.textContent = 'DỪNG';
  }

  try {
    const res = await fetch('/api/batch/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        combos: lines,
        threads: threads,
        client_id: currentClientId,
        user_id: currentUser ? currentUser.id : null
      })
    });
    const data = await res.json();
    if (data.status === 'ok' || data.success) {
      activeTaskId = data.task_id;
      localStorage.setItem('aov_active_task_id', activeTaskId);
      pollBatchProgress(activeTaskId);
    } else {
      showToast(data.error || 'Khởi chạy thất bại');
      btnStartBatch.disabled = false;
      btnStartBatch.style.display = 'inline-flex';
      if (btnStopBatch) btnStopBatch.style.display = 'none';
    }
  } catch (err) {
    showToast('Lỗi máy chủ');
    btnStartBatch.disabled = false;
    btnStartBatch.style.display = 'inline-flex';
    if (btnStopBatch) btnStopBatch.style.display = 'none';
  }
});

let consecutivePollErrors = 0;
let batchStartTime = null;
let batchTimerInterval = null;
let lastRenderedCount = 0;

function formatElapsedDuration(ms) {
  const totalSec = Math.max(0, Math.floor(ms / 1000));
  const m = Math.floor(totalSec / 60);
  const s = totalSec % 60;
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
}

function pollBatchProgress(taskId) {
  clearInterval(pollInterval);
  clearInterval(batchTimerInterval);
  consecutivePollErrors = 0;
  batchStartTime = Date.now();
  lastRenderedCount = 0;

  // Make sure stop button is visible and enabled
  if (btnStopBatch) {
    btnStopBatch.style.display = 'inline-flex';
    btnStopBatch.disabled = false;
    btnStopBatch.textContent = 'DỪNG QUÉT';
  }
  btnStartBatch.disabled = true;
  btnStartBatch.style.display = 'none';

  // Live timer tick every 500ms
  const timerBadge = document.getElementById('batchTimerBadge');
  const speedBadge = document.getElementById('batchSpeedBadge');
  if (timerBadge) timerBadge.textContent = '⏱️ 00:00';
  if (speedBadge) speedBadge.textContent = '0 acc/s';

  batchTimerInterval = setInterval(() => {
    if (!batchStartTime) return;
    const elapsed = Date.now() - batchStartTime;
    if (timerBadge) timerBadge.textContent = `⏱️ ${formatElapsedDuration(elapsed)}`;
  }, 500);

  let clientOffset = 0;

  pollInterval = setInterval(async () => {
    try {
      const res = await fetch(`/api/batch/status?task_id=${taskId}&offset=${clientOffset}&stream=true`);
      if (!res.ok) {
        consecutivePollErrors++;
        if (consecutivePollErrors >= 15) {
          clearInterval(pollInterval);
          clearInterval(batchTimerInterval);
          btnStartBatch.disabled = false;
          btnStartBatch.style.display = 'inline-flex';
          btnStartBatch.textContent = 'BẮT ĐẦU QUÉT';
          if (btnStopBatch) btnStopBatch.style.display = 'none';
          showToast('Mất kết nối với máy chủ!');
        }
        return;
      }

      consecutivePollErrors = 0;
      const data = await res.json();
      const total = data.total || 0;
      const progress = data.progress !== undefined ? data.progress : (data.done || 0);
      const pct = total > 0 ? Math.round((progress / total) * 100) : 0;

      // Calculate speed (acc/second)
      const elapsedSec = batchStartTime ? Math.max(0.5, (Date.now() - batchStartTime) / 1000) : 1;
      const speed = (progress / elapsedSec).toFixed(1);
      if (speedBadge) speedBadge.textContent = `${speed} acc/s`;

      document.getElementById('batchProgRatio').textContent = `${pct}% (${progress}/${total})`;
      document.getElementById('batchProgBar').style.width = `${pct}%`;

      if (data.was_stopped) {
        document.getElementById('batchProgStatus').textContent = `ĐÃ DỪNG (${progress}/${total})`;
      } else if (data.is_done) {
        document.getElementById('batchProgStatus').textContent = `HOÀN TẤT TRONG ${formatElapsedDuration(Date.now() - batchStartTime)}!`;
      } else {
        document.getElementById('batchProgStatus').textContent = `Đang quét (${progress}/${total})...`;
      }

      // RAM Offloading: Client accumulates delta items in its own memory
      let hasNewData = false;
      if (data.new_results && Array.isArray(data.new_results) && data.new_results.length > 0) {
        allResults = allResults.concat(data.new_results);
        clientOffset = data.next_offset || allResults.length;
        hasNewData = true;
      } else if (data.results && Array.isArray(data.results) && data.results.length > 0 && allResults.length === 0) {
        allResults = data.results;
        clientOffset = data.next_offset || allResults.length;
        hasNewData = true;
      }

      if (hasNewData || (data.is_done && allResults.length !== lastRenderedCount)) {
        lastRenderedCount = allResults.length;
        try {
          renderFilteredResults();
        } catch (rErr) {
          console.error('Render batch results error:', rErr);
        }
      }

      // ONLY finish and hide btnStopBatch when actually done or stopped!
      if (data.is_done) {
        clearInterval(pollInterval);
        clearInterval(batchTimerInterval);
        const finalElapsed = Date.now() - batchStartTime;
        if (timerBadge) timerBadge.textContent = `⏱️ ${formatElapsedDuration(finalElapsed)}`;
        if (speedBadge) speedBadge.textContent = `${(progress / Math.max(0.5, finalElapsed / 1000)).toFixed(1)} acc/s`;

        localStorage.removeItem('aov_active_task_id');
        btnStartBatch.disabled = false;
        btnStartBatch.style.display = 'inline-flex';
        btnStartBatch.textContent = 'BẮT ĐẦU QUÉT';
        if (btnStopBatch) btnStopBatch.style.display = 'none';
        if (data.was_stopped) {
          showToast(`ĐÃ DỪNG QUÉT (${progress}/${total}) sau ${formatElapsedDuration(finalElapsed)}`);
        } else {
          showToast(`ĐÃ QUÉT XONG TOÀN BỘ (${total} acc) TRONG ${formatElapsedDuration(finalElapsed)}!`);
        }
      }
    } catch (e) {
      console.warn('Transient poll error:', e);
      consecutivePollErrors++;
      if (consecutivePollErrors >= 15) {
        clearInterval(pollInterval);
        clearInterval(batchTimerInterval);
        localStorage.removeItem('aov_active_task_id');
        btnStartBatch.disabled = false;
        btnStartBatch.style.display = 'inline-flex';
        btnStartBatch.textContent = 'BẮT ĐẦU QUÉT';
        if (btnStopBatch) btnStopBatch.style.display = 'none';
        showToast('Quá trình quét bị ngắt kết nối');
      }
    }
  }, 1000);
}

// Auto-resume running batch on page reload if activeTaskId exists
window.addEventListener('DOMContentLoaded', () => {
  const savedTaskId = localStorage.getItem('aov_active_task_id');
  if (savedTaskId) {
    activeTaskId = savedTaskId;
    document.getElementById('batchProgressBox').style.display = 'block';
    pollBatchProgress(activeTaskId);
  }
});

window.copyTextToClipboard = function(text, msg) {
  if (!text) return;
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(() => {
      showToast(msg || 'Đã sao chép vào bộ nhớ tạm!');
    }).catch(() => fallbackCopy(text, msg));
  } else {
    fallbackCopy(text, msg);
  }
};

function fallbackCopy(text, msg) {
  const ta = document.createElement('textarea');
  ta.value = text;
  document.body.appendChild(ta);
  ta.select();
  try {
    document.execCommand('copy');
    showToast(msg || 'Đã sao chép!');
  } catch (e) {
    showToast('Không thể sao chép tự động!');
  }
  document.body.removeChild(ta);
}

function renderAccountCard(r) {
  const isHit = r.status === 'HIT';
  const aov = r.aov || {};
  const sec = r.security || {};
  
  const acc = r.account || '';
  const pwd = r.password || '';
  const combo = (acc && pwd && !acc.includes(pwd)) ? `${acc}:${pwd}` : (acc || 'Tài khoản');
  const fullLine = r.full_line || (isHit ? `${combo} | ${r.tinh_trang || 'HIT'}` : `${combo} | ${r.status}`);

  if (!isHit) {
    const detailMsg = r.message || r.detail || 'Sai mật khẩu hoặc bị khóa';
    return `
      <div class="result-row-item invalid">
        <div style="display:flex;justify-content:space-between;align-items:center;">
          <div style="display:flex;align-items:center;gap:8px;">
            <strong style="color:var(--text-primary);font-size:13px;">${escapeHtml(combo)}</strong>
            <button class="btn-copy-chip" onclick="copyTextToClipboard('${escapeHtml(combo)}', 'Đã copy combo!')" title="Sao chép combo">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
            </button>
          </div>
          <span class="acc-badge badge-danger">${escapeHtml(r.status || 'INVALID')}</span>
        </div>
        <div style="color:var(--red-neon);font-size:11px;margin-top:2px;">
          ${escapeHtml(detailMsg)}
        </div>
      </div>
    `;
  }

  // HIT details
  const ingame = r.ingame || aov.name || 'Chưa Đặt Tên';
  const rank = r.rank || aov.rank || 'Chưa Đấu Hạng';
  const level = r.level || aov.level || 30;
  const heroes = r.hero_count !== undefined ? r.hero_count : (aov.total_champs || 0);
  const skins = r.skin_count !== undefined ? r.skin_count : (aov.total_skins || 0);
  const shells = r.shells || 0;
  const lastLogin = r.last_login || 'Chưa ghi nhận';
  const tinhTrang = r.tinh_trang || (r.is_trang ? 'Acc Trắng' : 'Có Thông Tin');

  // Security parsing
  const sdtStr = r.sdt_str || (sec.masked_phone ? `YES [${sec.masked_phone}]` : (sec.has_phone ? 'YES [ĐÃ LIÊN KẾT]' : 'NO'));
  const hasPhone = !sdtStr.startsWith('NO');

  const emailStr = r.email_str || (sec.masked_email ? (sec.email_v ? `YES [${sec.masked_email} - ĐÃ XÁC THỰC]` : `NO [${sec.masked_email} - CHƯA XÁC THỰC]`) : 'NO [CHƯA LIÊN KẾT]');
  const hasEmail = !emailStr.startsWith('NO');

  const cmndStr = r.cmnd_str || (sec.has_cccd ? (sec.idcard ? `YES [${sec.idcard}]` : 'YES') : 'NO');
  const hasCmnd = !cmndStr.startsWith('NO');

  const authenStr = r.authen_str || (sec.auth_2fa ? 'YES' : 'NO');
  const hasAuthen = authenStr === 'YES';

  const fbStr = r.fb_str || (sec.fb_linked ? (sec.fb_uid ? `YES [${sec.fb_uid}]` : 'YES') : 'DIE');
  const hasFb = !fbStr.startsWith('DIE') && !fbStr.startsWith('NO');

  // Condition Badge Color
  let ttBadgeClass = 'badge-neutral';
  if (r.is_trang || tinhTrang === 'Acc Trắng') ttBadgeClass = 'badge-trang';
  else if (tinhTrang.includes('SĐT') || tinhTrang.includes('FB')) ttBadgeClass = 'badge-warning';
  else if (tinhTrang.includes('Full')) ttBadgeClass = 'badge-danger';

  // Skins lists
  const ssList = r.ss_list || aov.ss_list || [];
  const sssList = r.sss_list || aov.sss_list || [];
  const animeList = r.anime_list || aov.anime_list || [];
  const otherList = r.other_list || aov.other_list || [];

  return `
    <div class="result-row-item hit">
      <!-- Header: Combo + Badges + Copy button -->
      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
        <div style="display:flex;align-items:center;gap:8px;">
          <strong style="color:var(--text-primary);font-size:13px;">${escapeHtml(combo)}</strong>
          <button class="btn-copy-chip" onclick="copyTextToClipboard('${escapeHtml(fullLine)}', 'Đã copy đầy đủ thông tin!')" title="Sao chép toàn bộ thông tin">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
            <span>COPY</span>
          </button>
        </div>
        <div style="display:flex;align-items:center;gap:6px;">
          <span class="acc-badge ${ttBadgeClass}">${escapeHtml(tinhTrang.toUpperCase())}</span>
          <span class="acc-badge badge-trang">HIT</span>
        </div>
      </div>

      <!-- Overview Stats Line -->
      <div class="acc-tag-line">
        <span class="acc-stat-pill"><strong>Ingame:</strong> ${escapeHtml(ingame)}</span>
        <span class="acc-stat-pill"><strong>Rank:</strong> ${escapeHtml(rank)}</span>
        <span class="acc-stat-pill"><strong>Lv:</strong> ${level}</span>
        <span class="acc-stat-pill" style="color:var(--green-neon);"><strong>Tướng:</strong> ${heroes}</span>
        <span class="acc-stat-pill" style="color:var(--gold);"><strong>Skin:</strong> ${skins}</span>
        <span class="acc-stat-pill"><strong>Sò:</strong> ${shells}</span>
        <span class="acc-stat-pill" style="color:var(--text-muted);"><strong>Login:</strong> ${escapeHtml(lastLogin)}</span>
      </div>

      <!-- Security Tags Line -->
      <div class="acc-tag-line">
        <span class="acc-badge ${hasPhone ? 'badge-warning' : 'badge-trang'}">
          SĐT: ${escapeHtml(sdtStr)}
        </span>
        <span class="acc-badge ${hasEmail ? (emailStr.includes('ĐÃ XÁC THỰC') ? 'badge-cyan' : 'badge-warning') : 'badge-trang'}">
          EMAIL: ${escapeHtml(emailStr)}
        </span>
        <span class="acc-badge ${hasCmnd ? 'badge-danger' : 'badge-trang'}">
          CCCD: ${escapeHtml(cmndStr)}
        </span>
        <span class="acc-badge ${hasAuthen ? 'badge-danger' : 'badge-trang'}">
          AUTHEN: ${escapeHtml(authenStr)}
        </span>
        <span class="acc-badge ${hasFb ? 'badge-warning' : 'badge-trang'}">
          FB: ${escapeHtml(fbStr)}
        </span>
      </div>

      <!-- VIP Skins Breakdown -->
      ${(sssList.length > 0 || animeList.length > 0 || ssList.length > 0 || otherList.length > 0) ? `
        <div class="acc-skins-section">
          ${sssList.length > 0 ? `
            <div><span class="acc-badge badge-purple" style="margin-right:6px;">SSS (${sssList.length})</span><span style="color:#e0aaff;">${escapeHtml(sssList.join(', '))}</span></div>
          ` : ''}
          ${animeList.length > 0 ? `
            <div><span class="acc-badge badge-cyan" style="margin-right:6px;">Anime (${animeList.length})</span><span style="color:#80deea;">${escapeHtml(animeList.join(', '))}</span></div>
          ` : ''}
          ${ssList.length > 0 ? `
            <div><span class="acc-badge badge-gold" style="margin-right:6px;">SS (${ssList.length})</span><span style="color:#ffe082;">${escapeHtml(ssList.join(', '))}</span></div>
          ` : ''}
          ${otherList.length > 0 ? `
            <div style="color:var(--text-secondary);"><span class="acc-badge badge-neutral" style="margin-right:6px;">Other (${otherList.length})</span><span>${escapeHtml(otherList.slice(0, 10).join(', '))}${otherList.length > 10 ? '...' : ''}</span></div>
          ` : ''}
        </div>
      ` : ''}
    </div>
  `;
}

function renderFilteredResults() {
  let filtered = allResults;
  if (activeResultFilter === 'trang') {
    filtered = allResults.filter(r => r.is_trang || (r.tinh_trang && r.tinh_trang.toLowerCase().includes('trắng')));
  } else if (activeResultFilter === 'vip') {
    filtered = allResults.filter(r => r.is_vip || (r.ss_count > 0 || r.sss_count > 0 || r.anime_count > 0) || (r.rank && ['Cao Thủ', 'Thách Đấu', 'Chiến Tướng'].includes(r.rank)));
  } else if (activeResultFilter === 'live') {
    filtered = allResults.filter(r => r.status === 'HIT');
  }

  document.getElementById('cntAll').textContent = allResults.length;
  document.getElementById('cntTrang').textContent = allResults.filter(r => r.is_trang || (r.tinh_trang && r.tinh_trang.toLowerCase().includes('trắng'))).length;
  document.getElementById('cntVip').textContent = allResults.filter(r => r.is_vip || (r.ss_count > 0 || r.sss_count > 0 || r.anime_count > 0)).length;
  document.getElementById('cntLive').textContent = allResults.filter(r => r.status === 'HIT').length;

  if (filtered.length === 0) {
    batchResultsList.innerHTML = '<div style="text-align:center;padding:20px;color:var(--text-muted);">Không có kết quả cho bộ lọc này.</div>';
    return;
  }

  // Optimize DOM for 500+ threads: render newest 300 cards smoothly to prevent browser freeze
  const MAX_DOM_RENDER = 300;
  let itemsToRender = filtered;
  let noteHtml = '';
  if (filtered.length > MAX_DOM_RENDER) {
    itemsToRender = filtered.slice(-MAX_DOM_RENDER);
    noteHtml = `<div style="text-align:center;padding:6px;font-size:11px;color:var(--gold-light);background:rgba(255,255,255,0.03);border-radius:4px;margin-bottom:8px;">
      Đang hiển thị 300 kết quả mới nhất (Tổng: ${filtered.length}). Nút "COPY KẾT QUẢ" & "XUẤT ACC TRẮNG" vẫn xuất đầy đủ 100% tài khoản.
    </div>`;
  }

  batchResultsList.innerHTML = noteHtml + itemsToRender.map(r => renderAccountCard(r)).join('');
}

document.querySelectorAll('.f-tab').forEach(b => {
  b.addEventListener('click', () => {
    document.querySelectorAll('.f-tab').forEach(x => x.classList.remove('active'));
    b.classList.add('active');
    activeResultFilter = b.getAttribute('data-filter');
    renderFilteredResults();
  });
});

document.getElementById('btnCopyResults').addEventListener('click', () => {
  const text = allResults.map(r => r.full_line || `${r.account} | ${r.status}`).join('\n');
  copyTextToClipboard(text, 'ĐÃ SAO CHÉP TOÀN BỘ KẾT QUẢ!');
});

document.getElementById('btnExportTrang').addEventListener('click', () => {
  const trangList = allResults.filter(r => r.is_trang || (r.tinh_trang && r.tinh_trang.toLowerCase().includes('trắng'))).map(r => r.full_line || `${r.account} | ${r.status}`).join('\n');
  if (!trangList) {
    showToast('Chưa có tài khoản Trắng Thông Tin nào!');
    return;
  }
  const blob = new Blob([trangList], { type: 'text/plain;charset=utf-8' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `acc_trang_thong_tin_${Date.now()}.txt`;
  a.click();
  showToast('ĐÃ XUẤT FILE ACC TRẮNG THÀNH CÔNG!');
});

if (btnExportLive) {
  btnExportLive.addEventListener('click', () => {
    const liveList = allResults.filter(r => r.status === 'HIT' || r.status === 'LIVE' || r.status === 'LIVE_TRANG').map(r => r.full_line || `${r.account} | ${r.status}`).join('\n');
    if (!liveList) {
      showToast('Chưa có tài khoản LIVE nào để xuất!');
      return;
    }
    const blob = new Blob([liveList], { type: 'text/plain;charset=utf-8' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `acc_hits_live_${Date.now()}.txt`;
    a.click();
    showToast('ĐÃ XUẤT FILE ACC LIVE THÀNH CÔNG!');
  });
}



// ── TAB 4: API KEY MANAGER (VAULT LIST) ─────────────────────────────────────
let userApiKeysList = [];

async function loadApiKeys() {
  if (!currentUser) return;
  const tbody = document.getElementById('apiKeysTableBody');
  try {
    const res = await fetch(`/api/user/keys?user_id=${currentUser.id}`);
    const data = await res.json();
    if (data.success && data.keys && data.keys.length > 0) {
      userApiKeysList = data.keys;
      tbody.innerHTML = data.keys.map((k, idx) => `
        <tr style="border-bottom:1px solid rgba(255,255,255,0.06);">
          <td style="padding:12px 8px;font-weight:700;color:var(--text-primary);">
            ${escapeHtml(k.name || 'Secret Key #' + (idx + 1))}
          </td>
          <td style="padding:12px 8px;font-family:var(--font-mono);font-size:12px;color:var(--text-secondary);">
            <code>${escapeHtml(k.key)}</code>
          </td>
          <td style="padding:12px 8px;font-size:12px;color:var(--text-muted);">
            ${k.created_at ? new Date(k.created_at).toLocaleDateString('vi-VN') : 'Vừa tạo'}
          </td>
          <td style="padding:12px 8px;text-align:right;">
            <button class="btn btn-ghost" style="padding:4px 10px;font-size:11px;margin-right:6px;" onclick="copyApiKey('${k.key}')">SAO CHÉP</button>
            <button class="btn btn-ghost" style="padding:4px 8px;font-size:11px;color:var(--red-neon);" onclick="revokeApiKey('${k.key}')">XÓA</button>
          </td>
        </tr>
      `).join('');
    } else {
      tbody.innerHTML = `
        <tr>
          <td colspan="4" style="text-align:center;padding:36px;color:var(--text-muted);">
            Bạn chưa có API Key nào. Hãy bấm <strong>"+ TẠO API KEY MỚI"</strong> ở trên để bắt đầu!
          </td>
        </tr>
      `;
    }
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="4" style="text-align:center;color:var(--red-neon);padding:20px;">Lỗi tải danh sách API Key.</td></tr>`;
  }
}

window.copyApiKey = function(key) {
  navigator.clipboard.writeText(key);
  showToast('ĐÃ SAO CHÉP API KEY VÀO CLIPBOARD!');
};

window.revokeApiKey = async function(key) {
  if (!confirm('Bạn có chắc chắn muốn hủy và xóa API Key này?')) return;
  try {
    const res = await fetch('/api/keys/revoke', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: currentUser.id, api_key: key })
    });
    const data = await res.json();
    if (data.success) {
      showToast('ĐÃ XÓA API KEY THÀNH CÔNG!');
      loadApiKeys();
    } else {
      showToast(data.error || 'Xóa API Key thất bại');
    }
  } catch (err) {
    showToast('Lỗi kết nối máy chủ');
  }
};

document.getElementById('btnCreateNewApiKey').addEventListener('click', async () => {
  if (!currentUser) return;
  const keyName = prompt('Nhập tên gợi nhớ cho API Key (ví dụ: Telegram Bot, Web App, Discord Bot...):', 'Production Key');
  if (!keyName) return;

  try {
    const res = await fetch('/api/keys/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: currentUser.id, name: keyName.trim() })
    });
    const data = await res.json();
    if (data.success) {
      showToast('ĐÃ TẠO MÃ API KEY MỚI VÀ LƯU VÀO TÀI KHOẢN!');
      loadApiKeys();
    } else {
      showToast(data.error || 'Không thể tạo API Key');
    }
  } catch (err) {
    showToast('Lỗi khi tạo API Key');
  }
});

// ── USER DROPDOWN MENU & TOPUP MODAL LOGIC ─────────────────────────────────
const userChipDropdownBtn = document.getElementById('userChipDropdownBtn');
const userDropdownMenu = document.getElementById('userDropdownMenu');
const modalTopup = document.getElementById('modalTopup');

if (userChipDropdownBtn && userDropdownMenu) {
  userChipDropdownBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    const isShown = userDropdownMenu.style.display === 'block';
    userDropdownMenu.style.display = isShown ? 'none' : 'block';
  });

  document.addEventListener('click', (e) => {
    if (!userDropdownMenu.contains(e.target) && !userChipDropdownBtn.contains(e.target)) {
      userDropdownMenu.style.display = 'none';
    }
  });
}

// Topup Modal Trigger
const creditsPillTopup = document.getElementById('creditsPillTopup');
const ddBtnTopup = document.getElementById('ddBtnTopup');
const btnCloseTopupModal = document.getElementById('btnCloseTopupModal');

function openTopupModal() {
  if (userDropdownMenu) userDropdownMenu.style.display = 'none';
  if (modalTopup) {
    modalTopup.style.display = 'flex';
    const synPrev = document.getElementById('topupSyntaxPreview');
    if (synPrev && currentUser) synPrev.textContent = `NAP ${currentUser.username.toUpperCase()}`;
  }
}
function closeTopupModal() {
  if (modalTopup) modalTopup.style.display = 'none';
}

if (creditsPillTopup) creditsPillTopup.addEventListener('click', openTopupModal);
if (ddBtnTopup) ddBtnTopup.addEventListener('click', openTopupModal);
if (btnCloseTopupModal) btnCloseTopupModal.addEventListener('click', closeTopupModal);

// Modal redeem giftcode
const btnModalRedeem = document.getElementById('btnModalRedeemGiftcode');
if (btnModalRedeem) {
  btnModalRedeem.addEventListener('click', async () => {
    const input = document.getElementById('inputModalGiftcode');
    const code = input ? input.value.trim() : '';
    if (!code) return showToast('Vui lòng nhập mã Giftcode');
    try {
      const res = await fetch('/api/user/redeem', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: currentUser.id, code })
      });
      const data = await res.json();
      if (data.success) {
        currentUser.credits = data.new_credits;
        localStorage.setItem('aov_user', JSON.stringify(currentUser));
        renderUserProfile();
        input.value = '';
        closeTopupModal();
        showToast(`NẠP THÀNH CÔNG +${data.credits_added} CREDITS!`);
      } else {
        showToast(data.error || 'Mã Giftcode không hợp lệ');
      }
    } catch (e) {
      showToast('Lỗi kết nối máy chủ');
    }
  });
}

// Dropdown Navigation items
const ddBtnSettings = document.getElementById('ddBtnSettings');
if (ddBtnSettings) {
  ddBtnSettings.addEventListener('click', () => {
    if (userDropdownMenu) userDropdownMenu.style.display = 'none';
    switchTab('settings');
  });
}

const ddBtnAdminPanel = document.getElementById('ddBtnAdminPanel');
if (ddBtnAdminPanel) {
  ddBtnAdminPanel.addEventListener('click', () => {
    if (userDropdownMenu) userDropdownMenu.style.display = 'none';
    switchTab('owner');
  });
}

const ddBtnLogout = document.getElementById('ddBtnLogout');
if (ddBtnLogout) {
  ddBtnLogout.addEventListener('click', () => {
    if (userDropdownMenu) userDropdownMenu.style.display = 'none';
    currentUser = null;
    currentApiKey = null;
    currentSessionToken = '';
    localStorage.removeItem('aov_user');
    localStorage.removeItem('aov_session_token');
    showLanding();
    showToast('Đã đăng xuất tài khoản');
  });
}

// ── TAB 5: SETTINGS & PROFILE CUSTOMIZATION ─────────────────────────────────
const PRESET_AVATARS = ['🐔', '🔥', '⚔️', '🐲', '💀', '🐺', '🛡️', '⚡'];
let selectedAvatarChoice = '';

function updateAvatarPreview(val) {
  const pBox = document.getElementById('settingAvatarPreviewBox');
  const pText = document.getElementById('settingAvatarPreviewText');
  const pImg = document.getElementById('settingAvatarPreviewImg');
  if (!pBox || !pText || !pImg) return;

  if (val && (val.startsWith('http') || val.startsWith('data:image'))) {
    pImg.src = val;
    pImg.style.display = 'block';
    pText.style.display = 'none';
  } else if (val) {
    pImg.style.display = 'none';
    pText.style.display = 'block';
    pText.textContent = val;
  } else {
    pImg.style.display = 'none';
    pText.style.display = 'block';
    const initChar = (currentUser.display_name || currentUser.username || 'U')[0].toUpperCase();
    pText.textContent = initChar;
  }
}

function loadSettings() {
  if (!currentUser) return;

  // Populate Inputs
  const userInp = document.getElementById('settingUsername');
  if (userInp) userInp.value = currentUser.username || '';

  const nameInp = document.getElementById('settingDisplayName');
  if (nameInp) nameInp.value = currentUser.display_name || currentUser.username || '';

  const emailInp = document.getElementById('settingEmail');
  if (emailInp) emailInp.value = currentUser.email || '';

  const avtUrlInp = document.getElementById('settingAvatarUrl');
  if (avtUrlInp) avtUrlInp.value = (currentUser.avatar_url && (currentUser.avatar_url.startsWith('http') || currentUser.avatar_url.startsWith('data:image'))) ? (currentUser.avatar_url.startsWith('http') ? currentUser.avatar_url : '') : '';

  selectedAvatarChoice = currentUser.avatar_url || '';
  updateAvatarPreview(selectedAvatarChoice);

  // Populate Preset Avatar Grid
  const presetGrid = document.getElementById('presetAvatarGrid');
  if (presetGrid) {
    presetGrid.innerHTML = PRESET_AVATARS.map(emoji => `
      <div class="preset-avatar-item${selectedAvatarChoice === emoji ? ' active' : ''}"
           title="${emoji}"
           onclick="
             selectedAvatarChoice = '${emoji}';
             document.querySelectorAll('.preset-avatar-item').forEach(el => el.classList.remove('active'));
             this.classList.add('active');
             const urlInp = document.getElementById('settingAvatarUrl');
             if (urlInp) urlInp.value = '';
             updateAvatarPreview('${emoji}');
           ">
        ${emoji}
      </div>
    `).join('');
  }
}

// File upload direct avatar handler with auto-compression
const fileInpAvatar = document.getElementById('settingAvatarFileInput');
if (fileInpAvatar) {
  fileInpAvatar.addEventListener('change', (e) => {
    const file = e.target.files && e.target.files[0];
    if (!file) return;
    if (file.size > 8 * 1024 * 1024) {
      showToast('Kích thước ảnh tối đa 8MB');
      return;
    }

    const reader = new FileReader();
    reader.onload = function(evt) {
      const img = new Image();
      img.onload = function() {
        // Auto compress / resize to max 128x128 for ultra-fast load
        const maxSide = 128;
        let w = img.width;
        let h = img.height;
        if (w > h) {
          if (w > maxSide) {
            h = Math.round((h * maxSide) / w);
            w = maxSide;
          }
        } else {
          if (h > maxSide) {
            w = Math.round((w * maxSide) / h);
            h = maxSide;
          }
        }
        const canvas = document.createElement('canvas');
        canvas.width = w;
        canvas.height = h;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(img, 0, 0, w, h);
        const compressedDataUrl = canvas.toDataURL('image/jpeg', 0.85);

        selectedAvatarChoice = compressedDataUrl;
        const avtUrlInp = document.getElementById('settingAvatarUrl');
        if (avtUrlInp) avtUrlInp.value = '';
        document.querySelectorAll('.preset-avatar-item').forEach(el => el.classList.remove('active'));
        updateAvatarPreview(compressedDataUrl);
        showToast('Đã nén ảnh sắc nét! Hãy bấm "LƯU THAY ĐỔI CÀI ĐẶT" để hoàn tất.');
      };
      img.src = evt.target.result;
    };
    reader.readAsDataURL(file);
  });
}

const settingAvatarUrl = document.getElementById('settingAvatarUrl');
if (settingAvatarUrl) {
  settingAvatarUrl.addEventListener('input', (e) => {
    const val = e.target.value.trim();
    if (val) {
      selectedAvatarChoice = val;
      document.querySelectorAll('.preset-avatar-item').forEach(el => el.classList.remove('active'));
      updateAvatarPreview(val);
    } else {
      selectedAvatarChoice = '';
      updateAvatarPreview('');
    }
  });
}

const btnSaveProfile = document.getElementById('btnSaveProfile');
if (btnSaveProfile) {
  btnSaveProfile.addEventListener('click', async () => {
    if (!currentUser) return;
    const displayName = (document.getElementById('settingDisplayName').value || '').trim();
    const email = (document.getElementById('settingEmail').value || '').trim();
    const avatarUrl = selectedAvatarChoice.trim();

    try {
      btnSaveProfile.disabled = true;
      btnSaveProfile.textContent = 'ĐANG LƯU...';
      const res = await fetch('/api/user/profile/update', {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({
          user_id: currentUser.id,
          display_name: displayName,
          avatar_url: avatarUrl,
          email: email
        })
      });
      const data = await res.json();
      if (data.success && data.user) {
        currentUser.display_name = data.user.display_name;
        currentUser.avatar_url = data.user.avatar_url;
        currentUser.email = data.user.email;
        localStorage.setItem('aov_user', JSON.stringify(currentUser));
        renderUserProfile();
        updateAllAvatarsAcrossUI(currentUser.avatar_url, currentUser.display_name || currentUser.username);
        loadSettings();
        showToast('ĐÃ CẬP NHẬT HỒ SƠ VÀ ĐỒNG BỘ AVATAR THÀNH CÔNG!');
      } else {
        showToast(data.error || 'Cập nhật thất bại');
      }
    } catch (e) {
      showToast('Lỗi máy chủ khi lưu hồ sơ');
    } finally {
      btnSaveProfile.disabled = false;
      btnSaveProfile.innerHTML = `<svg class="svg-icon icon-sm" viewBox="0 0 24 24"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"></path><polyline points="17 21 17 13 7 13 7 21"></polyline><polyline points="7 3 7 8 15 8"></polyline></svg> LƯU THAY ĐỔI CÀI ĐẶT`;
    }
  });
}

// Redeem Giftcode Form in Settings
const formRedeemCode = document.getElementById('formRedeemCode');
if (formRedeemCode) {
  formRedeemCode.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!currentUser) return;
    const code = document.getElementById('inputRedeemCode').value.trim();
    try {
      const res = await fetch('/api/user/redeem', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: currentUser.id, code })
      });
      const data = await res.json();
      if (data.success) {
        currentUser.credits = data.new_credits;
        localStorage.setItem('aov_user', JSON.stringify(currentUser));
        renderUserProfile();
        document.getElementById('inputRedeemCode').value = '';
        showToast(`NẠP THÀNH CÔNG +${data.credits_added} CREDITS!`);
      } else {
        showToast(data.error || 'Mã Giftcode không hợp lệ');
      }
    } catch (err) {
      showToast('Lỗi máy chủ');
    }
  });
}

// ── TAB 6: TRANG QUẢN TRỊ OWNER (ADMIN & OWNER PANEL) ────────────────────────
async function loadOwnerDashboard() {
  if (!currentUser) return;
  const isPrivileged = (currentUser.role === 'owner' || currentUser.role === 'admin');
  if (!isPrivileged) {
    showToast('BẠN KHÔNG CÓ QUYỀN TRUY CẬP TRANG QUẢN TRỊ OWNER');
    switchTab('dashboard');
    return;
  }

  try {
    const res = await fetch(`/api/admin/overview?user_id=${currentUser.id}`);
    const data = await res.json();
    if (!data.success) {
      showToast(data.error || 'Không tải được dữ liệu quản trị');
      return;
    }

    const ov = data.overview || {};
    document.getElementById('ownerTotalUsers').textContent = (ov.total_users || 0).toLocaleString();
    document.getElementById('ownerTotalCredits').textContent = (ov.total_credits || 0).toLocaleString();

    // Render User List
    const uTbody = document.getElementById('ownerUserListTbody');
    if (uTbody) {
      uTbody.innerHTML = (ov.users || []).map(u => `
        <tr style="border-bottom:1px solid rgba(255,255,255,0.06);">
          <td style="padding:10px 8px;font-family:var(--font-mono);color:var(--text-muted);">#${u.id}</td>
          <td style="padding:10px 8px;font-weight:700;color:#fff;">${escapeHtml(u.username)}</td>
          <td style="padding:10px 8px;color:var(--text-secondary);">${escapeHtml(u.display_name || u.username)}</td>
          <td style="padding:10px 8px;"><span class="role-badge ${u.role}">${(u.role || 'user').toUpperCase()}</span></td>
          <td style="padding:10px 8px;font-family:var(--font-mono);color:var(--gold-light);font-weight:700;">${(u.credits || 0).toLocaleString()} CR</td>
          <td style="padding:10px 8px;text-align:right;">
            <button class="btn btn-ghost" style="padding:4px 8px;font-size:11px;margin-right:4px;" onclick="ownerAdjustCredits(${u.id}, '${escapeHtml(u.username)}', 1)">+ CỘNG CR</button>
            <button class="btn btn-ghost" style="padding:4px 8px;font-size:11px;margin-right:4px;color:var(--red-neon);" onclick="ownerAdjustCredits(${u.id}, '${escapeHtml(u.username)}', -1)">- TRỪ CR</button>
            ${currentUser.role === 'owner' && u.id !== currentUser.id ? `
              <button class="btn btn-ghost" style="padding:4px 8px;font-size:11px;" onclick="ownerChangeRole(${u.id}, '${escapeHtml(u.username)}', '${u.role}')">ĐỔI ROLE</button>
            ` : ''}
          </td>
        </tr>
      `).join('');
    }

    // Render Giftcode List
    const gTbody = document.getElementById('ownerGiftcodeListTbody');
    if (gTbody) {
      if (!ov.giftcodes || ov.giftcodes.length === 0) {
        gTbody.innerHTML = `<tr><td colspan="5" style="text-align:center;padding:24px;color:var(--text-muted);">Chưa có Giftcode nào được tạo.</td></tr>`;
      } else {
        gTbody.innerHTML = ov.giftcodes.map(g => `
          <tr style="border-bottom:1px solid rgba(255,255,255,0.06);">
            <td style="padding:10px 8px;font-family:var(--font-mono);font-weight:700;color:#fff;">${escapeHtml(g.code)}</td>
            <td style="padding:10px 8px;font-family:var(--font-mono);color:var(--green-neon);">+${(g.credits || 0).toLocaleString()} CR</td>
            <td style="padding:10px 8px;font-family:var(--font-mono);color:var(--text-secondary);">${g.used_count || 0} / ${g.max_uses || 1}</td>
            <td style="padding:10px 8px;font-size:11px;color:var(--text-muted);">${g.created_at ? new Date(g.created_at * 1000).toLocaleDateString('vi-VN') : '-'}</td>
            <td style="padding:10px 8px;text-align:right;">
              <button class="btn btn-ghost" style="padding:4px 8px;font-size:11px;color:var(--red-neon);" onclick="ownerDeleteGiftcode('${escapeHtml(g.code)}')">XÓA</button>
            </td>
          </tr>
        `).join('');
      }
    }
  } catch (e) {
    showToast('Lỗi nạp dữ liệu Owner Dashboard');
  }
}

const btnRefreshOwner = document.getElementById('btnRefreshOwnerData');
if (btnRefreshOwner) btnRefreshOwner.addEventListener('click', loadOwnerDashboard);

// Form Tạo Giftcode
const formCreateGift = document.getElementById('formOwnerCreateGiftcode');
if (formCreateGift) {
  formCreateGift.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!currentUser) return;
    const code = document.getElementById('ownerGiftCode').value.trim();
    const credits = parseInt(document.getElementById('ownerGiftCredits').value, 10);
    const max_uses = parseInt(document.getElementById('ownerGiftMaxUses').value, 10);

    try {
      const res = await fetch('/api/admin/giftcodes/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          requester_id: currentUser.id,
          code,
          credits,
          max_uses
        })
      });
      const data = await res.json();
      if (data.success) {
        showToast(data.message || 'Đã tạo Giftcode thành công!');
        document.getElementById('ownerGiftCode').value = '';
        loadOwnerDashboard();
      } else {
        showToast(data.error || 'Tạo Giftcode thất bại');
      }
    } catch (err) {
      showToast('Lỗi máy chủ khi tạo Giftcode');
    }
  });
}

// ── USER CREDIT LEDGER (SAO KÊ BIẾN ĐỘNG SỐ DƯ) ────────────────────────────
async function loadUserLedger() {
  if (!currentUser) return;
  const tbody = document.getElementById('userLedgerTbody');
  if (!tbody) return;

  tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;padding:24px;color:var(--text-muted);">Đang truy xuất sổ cái sao kê bảo mật...</td></tr>`;

  try {
    const res = await fetch(`/api/user/credit-history?user_id=${currentUser.id}`, {
      headers: getAuthHeaders()
    });
    const data = await res.json();
    if (data.success && data.history && data.history.length > 0) {
      tbody.innerHTML = data.history.map(tx => {
        const isPlus = tx.amount > 0;
        const color = isPlus ? '#22c55e' : '#ef4444';
        const sign = isPlus ? `+${tx.amount}` : `${tx.amount}`;
        const timeStr = tx.created_at ? tx.created_at.slice(0, 19).replace('T', ' ') : 'N/A';
        const txType = escapeHtml(tx.type || 'ADJUST');
        const reason = escapeHtml(tx.reason || '');

        return `
          <tr style="border-bottom:1px solid var(--border-color);">
            <td style="padding:10px 12px;font-family:var(--font-mono);font-size:11px;color:var(--text-muted);">${tx.id}</td>
            <td style="padding:10px 12px;font-size:12px;color:var(--text-muted);">${timeStr}</td>
            <td style="padding:10px 12px;"><span style="font-size:11px;font-weight:700;padding:2px 6px;border-radius:4px;background:rgba(255,255,255,0.06);font-family:var(--font-mono);">${txType}</span></td>
            <td style="padding:10px 12px;font-weight:800;font-family:var(--font-mono);color:${color};font-size:13px;">${sign}</td>
            <td style="padding:10px 12px;font-family:var(--font-mono);font-size:12px;color:var(--text-main);">${Number(tx.balance_after).toLocaleString()} Cr</td>
            <td style="padding:10px 12px;font-size:12px;color:var(--text-muted);">${reason}</td>
          </tr>
        `;
      }).join('');
    } else {
      tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:24px;color:var(--text-muted);">Chưa có biến động số dư nào được ghi nhận.</td></tr>`;
    }
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:24px;color:#ef4444;">Lỗi kết nối khi nạp sao kê số dư.</td></tr>`;
  }
}

const btnRefreshLedger = document.getElementById('btnRefreshLedger');
if (btnRefreshLedger) {
  btnRefreshLedger.addEventListener('click', () => {
    loadUserLedger();
    showToast('ĐÃ LÀM MỚI SỔ CÁI SAO KÊ');
  });
}

// Update loadSettings to load ledger
const _oldLoadSettings = loadSettings;
loadSettings = function() {
  _oldLoadSettings();
  loadUserLedger();
};

window.ownerAdjustCredits = async function(targetId, targetUsername, sign) {
  const label = sign > 0 ? 'CỘNG' : 'TRỪ';
  const valStr = prompt(`Nhập số lượng Credits muốn ${label} cho [${targetUsername}]:`, "500");
  if (!valStr) return;
  const val = parseInt(valStr, 10);
  if (isNaN(val) || val <= 0) return showToast('Số lượng không hợp lệ');

  const amount = sign > 0 ? val : -val;
  try {
    const res = await fetch('/api/admin/users/credits', {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({
        requester_id: currentUser.id,
        target_user_id: targetId,
        amount: amount
      })
    });
    const data = await res.json();
    if (data.success) {
      showToast(data.message || 'Cập nhật Credits thành công!');
      loadOwnerDashboard();
    } else {
      if (data.security_violation) {
        alert(data.error || 'CẢNH BÁO AN NINH: Hành vi can thiệp trái phép đã được ghi nhận!');
      } else {
        showToast(data.error || 'Cập nhật thất bại');
      }
    }
  } catch (e) {
    showToast('Lỗi máy chủ');
  }
};

window.ownerChangeRole = async function(targetId, targetUsername, currentRole) {
  const newRole = currentRole === 'admin' ? 'user' : 'admin';
  if (!confirm(`Bạn có chắc chắn muốn chuyển quyền của [${targetUsername}] từ [${currentRole.toUpperCase()}] sang [${newRole.toUpperCase()}]?`)) return;

  try {
    const res = await fetch('/api/admin/users/role', {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({
        requester_id: currentUser.id,
        target_user_id: targetId,
        new_role: newRole
      })
    });
    const data = await res.json();
    if (data.success) {
      showToast(data.message || 'Đã đổi quyền thành công!');
      loadOwnerDashboard();
    } else {
      // Security trap response
      if (data.security_violation) {
        alert(`${data.error}\n\nHệ thống đã lưu vết địa chỉ IP và danh tính tài khoản vào Nhật Ký Thanh Tra An Ninh!`);
      } else {
        showToast(data.error || 'Không thể đổi quyền');
      }
    }
  } catch (e) {
    showToast('Lỗi máy chủ');
  }
};

window.ownerDeleteGiftcode = async function(code) {
  if (!confirm(`Bạn có chắc muốn xóa vĩnh viễn Giftcode [${code}]?`)) return;
  try {
    const res = await fetch('/api/admin/giftcodes/delete', {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({
        requester_id: currentUser.id,
        code: code
      })
    });
    const data = await res.json();
    if (data.success) {
      showToast(`ĐÃ XÓA GIFTCODE [${code}]!`);
      loadOwnerDashboard();
    } else {
      showToast(data.error || 'Xóa thất bại');
    }
  } catch (e) {
    showToast('Lỗi máy chủ');
  }
};

// ══════════════════════════════════════════════════════════════════════════════
// ── TAB 3: PLAYGROUND AI - FULL AI COPILOT MODULE ────────────────────────────
// ══════════════════════════════════════════════════════════════════════════════

// ── AI State ─────────────────────────────────────────────────────────────────
let currentAiTokens = { free: 0, paid: 0, total: 0 };
let aiPendingImage = null;     // { dataUrl, base64, name }
let aiPendingFile = null;      // { content, name }
let aiSearchEnabled = false;
let aiConversationHistory = [];
let aiIsTyping = false;
let _lastSentPayload = null;   // for auto-resend after token exchange

// ── DOM refs ──────────────────────────────────────────────────────────────────
const aiCanvasForm = document.getElementById('aiCanvasForm');
const aiCanvasInput = document.getElementById('aiCanvasInput');
const aiMainChatBody = document.getElementById('aiMainChatBody');
const aiTokenHudLabel = document.getElementById('aiTokenHudLabel');
const aiAttachmentTray = document.getElementById('aiAttachmentTray');
const aiAttachPreviewImg = document.getElementById('aiAttachPreviewImg');
const aiAttachPreviewFile = document.getElementById('aiAttachPreviewFile');
const aiAttachImgThumb = document.getElementById('aiAttachImgThumb');
const aiAttachImgLabel = document.getElementById('aiAttachImgLabel');
const aiAttachFileLabel = document.getElementById('aiAttachFileLabel');
const btnToggleSearch = document.getElementById('btnToggleSearch');
const btnAttachImage = document.getElementById('btnAttachImage');
const btnAttachFile = document.getElementById('btnAttachFile');
const aiImageFileInput = document.getElementById('aiImageFileInput');
const aiDocFileInput = document.getElementById('aiDocFileInput');
const btnRemoveImage = document.getElementById('btnRemoveImage');
const btnRemoveFile = document.getElementById('btnRemoveFile');
const modalTokenExchange = document.getElementById('modalTokenExchange');

// ── AI Token HUD updater ──────────────────────────────────────────────────────
function updateAiTokenHud(free, paid) {
  const total = (free || 0) + (paid || 0);
  currentAiTokens = { free: free || 0, paid: paid || 0, total };
  if (!aiTokenHudLabel) return;
  const formatted = total >= 1000 ? `${(total / 1000).toFixed(1)}k` : total;
  aiTokenHudLabel.textContent = `${formatted} Tokens`;
  const hud = document.getElementById('aiTokenHud');
  if (hud) {
    if (total <= 0) {
      hud.style.color = 'var(--red-neon)';
      hud.style.borderColor = 'rgba(239,68,68,0.4)';
    } else if (total < 500) {
      hud.style.color = '#f59e0b';
      hud.style.borderColor = 'rgba(245,158,11,0.4)';
    } else {
      hud.style.color = 'var(--green-neon)';
      hud.style.borderColor = 'rgba(34,197,94,0.35)';
    }
  }
}

// Load AI token balance from profile
async function loadAiTokenBalance() {
  if (!currentUser) return;
  try {
    const res = await fetch(`/api/v1/me?user_id=${currentUser.id}`);
    const data = await res.json();
    if (data.success && data.user) {
      const free = data.user.ai_free_tokens || 0;
      const paid = data.user.ai_paid_tokens || 0;
      updateAiTokenHud(free, paid);
    }
  } catch (e) { /* silent */ }
}

// ── Attachment Tray helpers ───────────────────────────────────────────────────
function refreshAttachmentTray() {
  const hasAttachment = aiPendingImage || aiPendingFile;
  if (aiAttachmentTray) aiAttachmentTray.style.display = hasAttachment ? 'flex' : 'none';
  if (aiAttachPreviewImg) aiAttachPreviewImg.style.display = aiPendingImage ? 'flex' : 'none';
  if (aiAttachPreviewFile) aiAttachPreviewFile.style.display = aiPendingFile ? 'flex' : 'none';
}

function clearImage() {
  aiPendingImage = null;
  if (aiAttachImgThumb) aiAttachImgThumb.src = '';
  if (aiImageFileInput) aiImageFileInput.value = '';
  refreshAttachmentTray();
}

function clearFile() {
  aiPendingFile = null;
  if (aiDocFileInput) aiDocFileInput.value = '';
  refreshAttachmentTray();
}

function attachImageFromFile(file) {
  if (!file || !file.type.startsWith('image/')) {
    showToast('Chỉ hỗ trợ file ảnh (PNG, JPG, GIF, WebP)!');
    return;
  }
  if (file.size > 5 * 1024 * 1024) {
    showToast('Ảnh quá lớn! Tối đa 5MB.');
    return;
  }
  const reader = new FileReader();
  reader.onload = (ev) => {
    const dataUrl = ev.target.result;
    aiPendingImage = { dataUrl, base64: dataUrl, name: file.name };
    if (aiAttachImgThumb) aiAttachImgThumb.src = dataUrl;
    if (aiAttachImgLabel) aiAttachImgLabel.textContent = file.name;
    refreshAttachmentTray();
    showToast(`Đã đính kèm ảnh: ${file.name}`);
  };
  reader.readAsDataURL(file);
}

function attachDocFile(file) {
  if (!file) return;
  if (file.size > 2 * 1024 * 1024) {
    showToast('File quá lớn! Tối đa 2MB văn bản.');
    return;
  }
  const reader = new FileReader();
  reader.onload = (ev) => {
    aiPendingFile = { content: ev.target.result, name: file.name };
    if (aiAttachFileLabel) aiAttachFileLabel.textContent = file.name;
    refreshAttachmentTray();
    showToast(`Đã đính kèm file: ${file.name}`);
  };
  reader.readAsText(file);
}

// ── Event: Search toggle ──────────────────────────────────────────────────────
if (btnToggleSearch) {
  btnToggleSearch.addEventListener('click', () => {
    aiSearchEnabled = !aiSearchEnabled;
    btnToggleSearch.classList.toggle('active', aiSearchEnabled);
    showToast(aiSearchEnabled ? '🔍 Live Search ĐÃ BẬT (+500 tokens)' : 'Đã tắt Live Search');
  });
}

// ── Event: Attach Image button ────────────────────────────────────────────────
if (btnAttachImage) {
  btnAttachImage.addEventListener('click', () => aiImageFileInput && aiImageFileInput.click());
}
if (aiImageFileInput) {
  aiImageFileInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (file) attachImageFromFile(file);
  });
}

// ── Event: Attach File button ─────────────────────────────────────────────────
if (btnAttachFile) {
  btnAttachFile.addEventListener('click', () => aiDocFileInput && aiDocFileInput.click());
}
if (aiDocFileInput) {
  aiDocFileInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (file) attachDocFile(file);
  });
}

// ── Event: Remove attachments ─────────────────────────────────────────────────
if (btnRemoveImage) btnRemoveImage.addEventListener('click', () => { clearImage(); showToast('Đã xóa ảnh đính kèm'); });
if (btnRemoveFile) btnRemoveFile.addEventListener('click', () => { clearFile(); showToast('Đã xóa file đính kèm'); });

// ── Event: Paste image from clipboard (Ctrl+V) ────────────────────────────────
document.addEventListener('paste', (e) => {
  const target = document.getElementById('viewPlaygroundAI');
  if (!target || target.style.display === 'none') return;
  const cbData = e.clipboardData || window.clipboardData;
  const items = cbData ? cbData.items : null;
  if (!items) return;
  for (let i = 0; i < items.length; i++) {
    if (items[i].type.startsWith('image/')) {
      const file = items[i].getAsFile();
      if (file) {
        attachImageFromFile(file);
        e.preventDefault();
        break;
      }
    }
  }
});

// ── Auto-resize textarea ──────────────────────────────────────────────────────
if (aiCanvasInput) {
  aiCanvasInput.addEventListener('input', function() {
    this.style.height = 'auto';
    this.style.height = Math.min(this.scrollHeight, 160) + 'px';
  });
  aiCanvasInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (aiCanvasForm) aiCanvasForm.dispatchEvent(new Event('submit'));
    }
  });
}

// ── Quick pill prompt injectors ───────────────────────────────────────────────
document.querySelectorAll('.ai-pill-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const query = btn.getAttribute('data-query');
    if (query && aiCanvasInput) {
      aiCanvasInput.value = query;
      aiCanvasInput.style.height = 'auto';
      aiCanvasInput.focus();
    }
  });
});

// ── Chat message renderer ─────────────────────────────────────────────────────
function renderMarkdownAI(text) {
  if (!text) return '';
  let html = escapeHtml(text);

  // Code blocks
  html = html.replace(/```(\w*)\n?([\s\S]*?)```/g, (_, lang, code) => {
    const langLabel = lang ? lang.toUpperCase() : 'CODE';
    const safeCode = code.replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&');
    const escaped = safeCode.replace(/</g, '&lt;').replace(/>/g, '&gt;');
    return `<div class="ai-code-preview-container">
      <div class="ai-code-header">
        <span class="ai-code-lang">${langLabel}</span>
        <button class="ai-code-copy-btn" onclick="navigator.clipboard.writeText(this.closest('.ai-code-preview-container').querySelector('pre').textContent);this.textContent='Đã sao chép!';setTimeout(()=>this.textContent='COPY',1500);">COPY</button>
      </div>
      <pre class="ai-code-body">${escaped}</pre>
    </div>`;
  });

  // Inline code
  html = html.replace(/`([^`]+)`/g, '<code class="ai-inline-code">$1</code>');
  // Bold
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  // Italic
  html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');
  // Blockquote
  html = html.replace(/^&gt; (.+)$/gm, '<blockquote style="border-left:3px solid var(--border-subtle);margin:6px 0;padding:6px 12px;color:var(--text-secondary);font-style:italic;">$1</blockquote>');
  // Headers
  html = html.replace(/^### (.+)$/gm, '<h4 style="margin:10px 0 4px;font-size:13px;font-weight:700;">$1</h4>');
  html = html.replace(/^## (.+)$/gm, '<h3 style="margin:12px 0 6px;font-size:15px;font-weight:800;">$1</h3>');
  html = html.replace(/^# (.+)$/gm, '<h2 style="margin:14px 0 8px;font-size:17px;font-weight:900;">$1</h2>');
  // Bullet list
  html = html.replace(/^- (.+)$/gm, '<li style="margin:3px 0;">$1</li>');
  html = html.replace(/(<li[^>]*>[\s\S]*?<\/li>)/g, '<ul style="margin:6px 0;padding-left:20px;">$1</ul>');
  // Line breaks
  html = html.replace(/\n\n/g, '</p><p style="margin:8px 0;">');
  html = html.replace(/\n/g, '<br>');
  return html;
}

function appendAIMessage(role, content, thought, imageDataUrl, fileName, fileSize) {
  if (!aiMainChatBody) return;

  const now = new Date();
  const timeStr = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`;

  // Strip <think>...</think> blocks from assistant replies (DeepSeek-style)
  let displayContent = content || '';
  let extractedThought = thought;
  if (role === 'assistant') {
    const thinkMatch = displayContent.match(/<think>([\s\S]*?)<\/think>/i);
    if (thinkMatch) {
      if (!extractedThought) extractedThought = thinkMatch[1].trim();
      displayContent = displayContent.replace(/<think>[\s\S]*?<\/think>/gi, '').trim();
    }
  }

  // Thought accordion
  let thoughtHtml = '';
  if (extractedThought && role === 'assistant') {
    const lines = extractedThought.split('\n').filter(Boolean)
      .map(l => `<div style="font-size:11.5px;color:var(--text-secondary);padding:2px 0;">${escapeHtml(l)}</div>`).join('');
    thoughtHtml = `
      <details class="ai-thought-accordion" style="margin-bottom:8px;">
        <summary style="cursor:pointer;font-size:11px;font-weight:700;color:var(--text-muted);letter-spacing:0.5px;list-style:none;display:flex;align-items:center;gap:6px;padding:6px 10px;background:var(--bg-surface);border-radius:var(--radius-sm);border:1px solid var(--border-subtle);">
          <svg style="width:12px;height:12px;stroke:currentColor;fill:none;stroke-width:2;" viewBox="0 0 24 24"><path d="M12 2a7 7 0 0 0-7 7c0 2.38 1.19 4.47 3 5.74V17a2 2 0 0 0 2 2h4a2 2 0 0 0 2-2v-2.26c1.81-1.27 3-3.36 3-5.74a7 7 0 0 0-7-7z"/><line x1="9" y1="21" x2="15" y2="21"/></svg>
          CHUỖI TƯ DUY (Chain-of-Thought)
        </summary>
        <div style="padding:10px 12px;background:var(--bg-deep);border-radius:0 0 var(--radius-sm) var(--radius-sm);border:1px solid var(--border-subtle);border-top:none;">${lines}</div>
      </details>`;
  }

  // Rich image preview (zoomable)
  let imagePreviewHtml = '';
  if (imageDataUrl && role === 'user') {
    imagePreviewHtml = `
      <div style="margin-bottom:10px;">
        <img src="${imageDataUrl}"
          style="max-width:220px;max-height:180px;border-radius:10px;border:1.5px solid var(--border-subtle);object-fit:cover;cursor:zoom-in;transition:transform 0.2s,box-shadow 0.2s;box-shadow:0 2px 12px rgba(0,0,0,0.3);"
          alt="Ảnh đính kèm"
          onclick="(function(el){
            const ov=document.createElement('div');
            ov.style.cssText='position:fixed;inset:0;background:rgba(0,0,0,0.88);z-index:99999;display:flex;align-items:center;justify-content:center;cursor:zoom-out;';
            const img2=document.createElement('img');
            img2.src=el.src;
            img2.style.cssText='max-width:90vw;max-height:90vh;border-radius:12px;box-shadow:0 8px 40px rgba(0,0,0,0.6);';
            ov.appendChild(img2);
            ov.onclick=()=>ov.remove();
            document.body.appendChild(ov);
          })(this)"
          title="Click để phóng to" />
      </div>`;
  }

  // Rich file attachment card
  let fileCardHtml = '';
  if (fileName && role === 'user') {
    const ext = (fileName.split('.').pop() || '').toLowerCase();
    const sizeStr = fileSize ? (fileSize >= 1024 ? `${(fileSize/1024).toFixed(1)} KB` : `${fileSize} B`) : '';
    const iconMap = {
      txt: '📄', py: '🐍', js: '📜', json: '📋', csv: '📊',
      md: '📝', html: '🌐', css: '🎨', log: '📃', xml: '📰'
    };
    const icon = iconMap[ext] || '📎';
    fileCardHtml = `
      <div style="display:inline-flex;align-items:center;gap:10px;margin-bottom:8px;padding:8px 14px;background:var(--bg-surface);border:1.5px solid var(--border-subtle);border-radius:10px;max-width:260px;">
        <span style="font-size:22px;flex-shrink:0;">${icon}</span>
        <div style="overflow:hidden;">
          <div style="font-size:12px;font-weight:700;color:var(--text-primary);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:180px;">${escapeHtml(fileName)}</div>
          ${sizeStr ? `<div style="font-size:10px;color:var(--text-muted);">${sizeStr}</div>` : ''}
        </div>
      </div>`;
  }

  const avatarHtml = role === 'assistant'
    ? `<img src="/assets/garena_logo.png" style="width:20px;height:20px;object-fit:contain;" alt="AI" />`
    : `<span>${((currentUser && currentUser.display_name) || (currentUser && currentUser.username) || 'U')[0].toUpperCase()}</span>`;
  const senderName = role === 'assistant'
    ? `AOV COPILOT <span class="ai-time">${timeStr}</span>`
    : `${((currentUser && currentUser.display_name) || (currentUser && currentUser.username) || 'Bạn').toUpperCase()} <span class="ai-time">${timeStr}</span>`;

  const row = document.createElement('div');
  row.className = `ai-message-row ${role}`;
  row.innerHTML = `
    <div class="ai-msg-avatar">${avatarHtml}</div>
    <div class="ai-msg-bubble">
      <div class="ai-sender-name">${senderName}</div>
      ${thoughtHtml}
      ${fileCardHtml}
      ${imagePreviewHtml}
      <div class="ai-msg-text">${renderMarkdownAI(displayContent)}</div>
    </div>`;
  aiMainChatBody.appendChild(row);
  aiMainChatBody.scrollTop = aiMainChatBody.scrollHeight;
}

function appendAITypingIndicator() {
  if (!aiMainChatBody) return null;
  const div = document.createElement('div');
  div.id = 'aiTypingIndicator';
  div.className = 'ai-message-row assistant';
  div.innerHTML = `
    <div class="ai-msg-avatar"><img src="/assets/garena_logo.png" style="width:20px;height:20px;object-fit:contain;" alt="AI"/></div>
    <div class="ai-msg-bubble">
      <div class="ai-sender-name">AOV COPILOT</div>
      <div class="ai-msg-text" style="display:flex;align-items:center;gap:6px;">
        <span class="ai-typing-dots">
          <span></span><span></span><span></span>
        </span>
        <span style="font-size:12px;color:var(--text-muted);">Đang phân tích...</span>
      </div>
    </div>`;
  aiMainChatBody.appendChild(div);
  aiMainChatBody.scrollTop = aiMainChatBody.scrollHeight;
  return div;
}

// ── Out-of-token interactive card ─────────────────────────────────────────────
function appendOutOfTokenCard(creditsAvailable, ratePerCredit, tokensNeeded) {
  if (!aiMainChatBody) return;
  const card = document.createElement('div');
  card.className = 'ai-token-out-card';
  card.innerHTML = `
    <div class="token-out-icon">⚡</div>
    <div class="token-out-body">
      <div class="token-out-title">Hết AI Tokens!</div>
      <div class="token-out-sub">Bạn cần <strong>${(tokensNeeded||500).toLocaleString()}</strong> tokens cho tin nhắn này. Hãy quy đổi Credits để tiếp tục.</div>
      <div class="token-out-meta">Credits khả dụng: <strong style="color:var(--gold-light);">${(creditsAvailable||0).toLocaleString()}</strong> Credits &nbsp;·&nbsp; Tỷ lệ: 1 Credit = ${(ratePerCredit||2000).toLocaleString()} Tokens</div>
    </div>
    <button class="token-out-btn" id="btnOpenTokenExchangeCard">Đổi Token Ngay →</button>`;
  aiMainChatBody.appendChild(card);
  aiMainChatBody.scrollTop = aiMainChatBody.scrollHeight;

  card.querySelector('#btnOpenTokenExchangeCard').addEventListener('click', () => {
    openTokenExchangeModal(creditsAvailable, ratePerCredit);
  });
}

// ── Token Exchange Modal ───────────────────────────────────────────────────────
function openTokenExchangeModal(creditsAvailable, ratePerCredit) {
  if (!modalTokenExchange) return;
  const slider = document.getElementById('sliderCreditsToExchange');
  const sliderVal = document.getElementById('sliderValueDisplay');
  const preview = document.getElementById('tokenExchangePreviewGain');
  const credLeft = document.getElementById('tokenExchangeCreditsLeft');
  const errMsg = document.getElementById('tokenExchangeError');

  const maxCr = Math.min(Math.max(creditsAvailable || 1, 1), 1000);
  if (slider) {
    slider.max = maxCr;
    slider.value = Math.min(5, maxCr);
  }
  if (credLeft) credLeft.textContent = `${(creditsAvailable||0).toLocaleString()} Credits khả dụng`;
  if (errMsg) errMsg.style.display = 'none';

  function updatePreview() {
    const v = parseInt((slider ? slider.value : null) || 5, 10);
    if (sliderVal) sliderVal.textContent = v;
    const gain = v * (ratePerCredit || 2000);
    if (preview) preview.textContent = `+${gain.toLocaleString()} AI Tokens`;
  }
  if (slider) { slider.oninput = updatePreview; updatePreview(); }

  modalTokenExchange.style.display = 'flex';
}

function closeTokenModal() {
  if (modalTokenExchange) modalTokenExchange.style.display = 'none';
}

const btnCloseTokenModal = document.getElementById('btnCloseTokenModal');
if (btnCloseTokenModal) btnCloseTokenModal.addEventListener('click', closeTokenModal);
if (modalTokenExchange) {
  modalTokenExchange.addEventListener('click', (e) => { if (e.target === modalTokenExchange) closeTokenModal(); });
}

async function callConvertTokens(creditsToSpend) {
  if (!currentUser) return null;
  try {
    const res = await fetch('/api/ai/convert-tokens', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: currentUser.id, credits: creditsToSpend })
    });
    return await res.json();
  } catch (e) {
    return null;
  }
}

const btnConfirmTokenExchange = document.getElementById('btnConfirmTokenExchange');
if (btnConfirmTokenExchange) {
  btnConfirmTokenExchange.addEventListener('click', async () => {
    const slider = document.getElementById('sliderCreditsToExchange');
    const errMsg = document.getElementById('tokenExchangeError');
    const credits = parseInt((slider ? slider.value : null) || 5, 10);

    btnConfirmTokenExchange.disabled = true;
    btnConfirmTokenExchange.textContent = 'Đang xử lý...';

    const data = await callConvertTokens(credits);
    btnConfirmTokenExchange.disabled = false;
    btnConfirmTokenExchange.textContent = 'XÁC NHẬN ĐỔI TOKEN';

    if ((data && data.success)) {
      closeTokenModal();
      updateAiTokenHud(data.free_tokens_remaining, data.paid_tokens_remaining);
      // Update credits in currentUser
      if (currentUser && data.credits_remaining !== undefined) {
        currentUser.credits = data.credits_remaining;
        localStorage.setItem('aov_user', JSON.stringify(currentUser));
        renderUserProfile();
      }
      showToast(`✅ Đã đổi thành công: +${data.tokens_gained.toLocaleString()} AI Tokens!`);

      // Auto re-send last message
      if (_lastSentPayload) {
        setTimeout(() => {
          _executeSendAI(_lastSentPayload);
          _lastSentPayload = null;
        }, 600);
      }
    } else {
      if (errMsg) {
        errMsg.style.display = 'block';
        errMsg.textContent = (data ? data.error : "") || 'Quy đổi thất bại. Vui lòng kiểm tra số dư Credits.';
      }
    }
  });
}

// ── Core: sendAICanvasMessage ─────────────────────────────────────────────────
async function _executeSendAI(payload) {
  const typingEl = appendAITypingIndicator();
  aiIsTyping = true;
  const submitBtn = document.getElementById('btnSendAICanvas');
  if (submitBtn) submitBtn.disabled = true;

  try {
    const res = await fetch('/api/ai/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();

    if (typingEl) typingEl.remove();
    aiIsTyping = false;
    if (submitBtn) submitBtn.disabled = false;

    if (data.out_of_tokens || res.status === 402) {
      // Show interactive out-of-token card
      appendOutOfTokenCard(
        data.credits_available,
        data.rate_per_credit,
        data.tokens_needed
      );
      _lastSentPayload = payload; // save for auto-resend
      return;
    }

    if (data.success && data.reply) {
      // Update conversation history
      aiConversationHistory.push({ role: 'user', content: payload.message });
      aiConversationHistory.push({ role: 'assistant', content: data.reply });
      if (aiConversationHistory.length > 20) aiConversationHistory = aiConversationHistory.slice(-20);

      appendAIMessage('assistant', data.reply, data.thought);

      // Update token HUD if we got token info
      if (data.tokens_used && currentUser) {
        loadAiTokenBalance();
      }
    } else {
      appendAIMessage('assistant', data.reply || data.error || 'Đã xảy ra lỗi. Vui lòng thử lại!', null);
    }
  } catch (err) {
    if (typingEl) typingEl.remove();
    aiIsTyping = false;
    if (submitBtn) submitBtn.disabled = false;
    appendAIMessage('assistant', `❌ Lỗi kết nối máy chủ AI: ${err.message}. Vui lòng thử lại sau.`, null);
  }
}

async function sendAICanvasMessage(messageOverride) {
  if (aiIsTyping) return;
  const msg = (messageOverride || (aiCanvasInput ? aiCanvasInput.value : "") || '').trim();
  if (!msg && !aiPendingImage && !aiPendingFile) {
    showToast('Vui lòng nhập nội dung trước khi gửi!');
    return;
  }

  // Snapshot attachments then clear tray
  const imgData = aiPendingImage ? aiPendingImage.base64 : null;
  const fileContent = aiPendingFile ? aiPendingFile.content : null;
  const fileName = aiPendingFile ? aiPendingFile.name : null;
  const imgDataUrl = aiPendingImage ? aiPendingImage.dataUrl : null;
  const msgText = msg || (imgData ? '(Phân tích ảnh)' : '(Phân tích file)');

  // Append user message to chat (with rich preview for image/file)
  const fileSizeBytes = aiPendingFile && aiPendingFile.content ? new Blob([aiPendingFile.content]).size : 0;
  appendAIMessage('user', msgText, null, imgDataUrl, fileName || null, fileSizeBytes || 0);

  // Reset input & tray
  if (aiCanvasInput) { aiCanvasInput.value = ''; aiCanvasInput.style.height = 'auto'; }
  clearImage();
  clearFile();

  // Build request payload
  const thinkingBtn = document.getElementById('btnToggleThinking');
  const deepBtn = document.getElementById('btnToggleDeepResearch');

  const payload = {
    message: msgText,
    user_name: (currentUser && currentUser.display_name) || (currentUser && currentUser.username) || 'Tris',
    user_id: (currentUser ? currentUser.id : null),
    history: aiConversationHistory.slice(-8),
    enable_thinking: thinkingBtn ? thinkingBtn.classList.contains('active') : false,
    enable_deep_research: deepBtn ? deepBtn.classList.contains('active') : false,
    enable_search: aiSearchEnabled,
    image_data: imgData || null,
    file_data: fileContent || null,
    file_name: fileName || null,
  };

  // Get active batch task context
  if (activeTaskId) payload.task_id = activeTaskId;

  await _executeSendAI(payload);
}

// ── Form Submit ───────────────────────────────────────────────────────────────
if (aiCanvasForm) {
  aiCanvasForm.addEventListener('submit', (e) => {
    e.preventDefault();
    sendAICanvasMessage();
  });
}

// ── Toggle Think & Deep Research ──────────────────────────────────────────────
const btnToggleThinking = document.getElementById('btnToggleThinking');
const btnToggleDeepResearch = document.getElementById('btnToggleDeepResearch');

if (btnToggleThinking) {
  btnToggleThinking.addEventListener('click', () => {
    btnToggleThinking.classList.toggle('active');
    const on = btnToggleThinking.classList.contains('active');
    showToast(on ? '💡 Chain-of-Thought ĐÃ BẬT (+300 tokens)' : 'Đã tắt Thinking');
  });
}
if (btnToggleDeepResearch) {
  btnToggleDeepResearch.addEventListener('click', () => {
    btnToggleDeepResearch.classList.toggle('active');
    const on = btnToggleDeepResearch.classList.contains('active');
    showToast(on ? '🔬 Deep Research ĐÃ BẬT (+300 tokens)' : 'Đã tắt Deep Research');
  });
}

// ── Load AI token balance on studio open ─────────────────────────────────────
const _origShowStudio = showStudio;
showStudio = function() {
  _origShowStudio();
  loadAiTokenBalance();
};

// ── Slider live update in Token Exchange Modal ──────────────────────────────
const sliderCredits = document.getElementById('sliderCreditsToExchange');
const sliderValDisplay = document.getElementById('sliderValueDisplay');
const tokenExchangePreviewGain = document.getElementById('tokenExchangePreviewGain');
if (sliderCredits) {
  sliderCredits.addEventListener('input', () => {
    const v = parseInt(sliderCredits.value, 10);
    if (sliderValDisplay) sliderValDisplay.textContent = v;
    if (tokenExchangePreviewGain) tokenExchangePreviewGain.textContent = `+${(v * 2000).toLocaleString()} AI Tokens`;
  });
}

// ── Theme & Language Initializer & Listeners ────────────────────────────────
const btnLandingTheme = document.getElementById('btnLandingTheme');
if (btnLandingTheme) {
  btnLandingTheme.addEventListener('click', () => {
    applyTheme(currentTheme === 'dark' ? 'light' : 'dark');
  });
}

const btnStudioTheme = document.getElementById('btnStudioTheme');
if (btnStudioTheme) {
  btnStudioTheme.addEventListener('click', () => {
    applyTheme(currentTheme === 'dark' ? 'light' : 'dark');
  });
}

const btnStudioLang = document.getElementById('btnStudioLang');
if (btnStudioLang) {
  btnStudioLang.addEventListener('click', () => {
    applyLanguage(currentLang === 'vi' ? 'en' : 'vi');
    showToast(currentLang === 'vi' ? 'ĐÃ ĐỔI SANG TIẾNG VIỆT' : 'SWITCHED TO ENGLISH');
  });
}

// Initial application of Theme & Lang
applyTheme(currentTheme);
applyLanguage(currentLang);

// Bootstrap
(function init() {
  const saved = localStorage.getItem('aov_user');
  if (saved) {
    try {
      currentUser = JSON.parse(saved);
      showStudio();
    } catch (e) {
      localStorage.removeItem('aov_user');
      showLanding();
    }
  } else {
    showLanding();
  }
})();

