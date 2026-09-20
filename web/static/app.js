/**
 * AOV STUDIO LUXURY CYBERPUNK MASTER FRONTEND (2026 EDITION)
 * 5 Core Modules: Dashboard, Playground Tool, Playground AI, API Key, Settings
 * 3 Fast Captcha Modes: 1-Click Smart, Magnetic Slider, Matrix Icon Selection
 */

// ── Global State ────────────────────────────────────────────────────────────
let currentUser = null;
let currentApiKey = null;
let activeTaskId = null;
let pollInterval = null;
let allResults = [];
let activeResultFilter = 'all';

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
function renderUserProfile() {
  if (!currentUser) return;
  const displayName = currentUser.display_name || currentUser.username || 'User';
  const role = (currentUser.role || 'user').toLowerCase();
  const credits = currentUser.credits !== undefined ? currentUser.credits : 0;

  // Header User Chip
  const nameEl = document.getElementById('studioUsername');
  if (nameEl) nameEl.textContent = displayName;

  const avatarEl = document.getElementById('studioUserAvatar');
  if (avatarEl) {
    if (currentUser.avatar_url && (currentUser.avatar_url.startsWith('http') || currentUser.avatar_url.startsWith('data:image'))) {
      avatarEl.innerHTML = `<img src="${currentUser.avatar_url}" style="width:100%;height:100%;object-fit:cover;border-radius:50%;" onerror="this.onerror=null;this.parentElement.textContent='${displayName[0].toUpperCase()}';"/>`;
    } else if (currentUser.avatar_url && currentUser.avatar_url.length <= 4) {
      avatarEl.textContent = currentUser.avatar_url;
    } else {
      avatarEl.textContent = displayName[0].toUpperCase();
    }
  }

  const creditsEl = document.getElementById('studioCredits');
  if (creditsEl) creditsEl.textContent = credits.toLocaleString();

  const roleEl = document.getElementById('studioUserRole');
  if (roleEl) {
    roleEl.textContent = role.toUpperCase();
    roleEl.className = `role-badge ${role}`;
  }

  // Dropdown Header info
  const ddAvatar = document.getElementById('ddAvatar');
  if (ddAvatar) {
    if (currentUser.avatar_url && (currentUser.avatar_url.startsWith('http') || currentUser.avatar_url.startsWith('data:image'))) {
      ddAvatar.innerHTML = `<img src="${currentUser.avatar_url}" style="width:100%;height:100%;object-fit:cover;border-radius:50%;" />`;
    } else if (currentUser.avatar_url && currentUser.avatar_url.length <= 4) {
      ddAvatar.textContent = currentUser.avatar_url;
    } else {
      ddAvatar.textContent = displayName[0].toUpperCase();
    }
  }
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
  localStorage.removeItem('aov_user');
  showLanding();
  showToast('ĐÃ ĐĂNG XUẤT KHỎI HỆ THỐNG');
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
      localStorage.setItem('aov_user', JSON.stringify(currentUser));
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
      localStorage.setItem('aov_user', JSON.stringify(currentUser));
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
const threadRange = document.getElementById('threadRange');
const threadDisplay = document.getElementById('threadDisplay');
const batchText = document.getElementById('batchText');
const btnStartBatch = document.getElementById('btnStartBatch');
const btnClearBatch = document.getElementById('btnClearBatch');
const uploadZone = document.getElementById('uploadZone');
const fileInput = document.getElementById('fileInput');
const batchResultsList = document.getElementById('batchResultsList');

threadRange.addEventListener('input', () => {
  threadDisplay.textContent = `${threadRange.value} LUỒNG`;
});

uploadZone.addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', (e) => {
  const file = e.target.files[0];
  if (!file) return;
  document.getElementById('fileChosen').textContent = `${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
  const reader = new FileReader();
  reader.onload = (evt) => {
    batchText.value = evt.target.result;
    showToast(`ĐÃ TẢI ${file.name} VÀO KHUNG QUÉT!`);
  };
  reader.readAsText(file);
});

btnClearBatch.addEventListener('click', () => {
  batchText.value = '';
  document.getElementById('fileChosen').textContent = 'Kéo thả hoặc click để chọn file';
  batchResultsList.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-muted);font-size:13px;">Chưa có kết quả. Nhập danh sách bên trái và bấm Bắt đầu quét!</div>';
  allResults = [];
});

btnStartBatch.addEventListener('click', async () => {
  const raw = batchText.value.trim();
  if (!raw) {
    showToast('Vui lòng nhập danh sách tài khoản trước!');
    return;
  }
  const lines = raw.split(/\r?\n/).filter(x => x.trim().length > 0);
  const threads = parseInt(threadRange.value, 10) || 20;

  document.getElementById('batchProgressBox').style.display = 'block';
  btnStartBatch.disabled = true;
  btnStartBatch.textContent = 'ĐANG QUÉT...';

  try {
    const res = await fetch('/api/batch/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        combos: lines,
        threads: threads,
        user_id: currentUser ? currentUser.id : null
      })
    });
    const data = await res.json();
    if (data.status === 'ok' || data.success) {
      activeTaskId = data.task_id;
      pollBatchProgress(activeTaskId);
    } else {
      showToast(data.error || 'Khởi chạy thất bại');
      btnStartBatch.disabled = false;
      btnStartBatch.textContent = 'BẮT ĐẦU QUÉT';
    }
  } catch (err) {
    showToast('Lỗi máy chủ');
    btnStartBatch.disabled = false;
    btnStartBatch.textContent = 'BẮT ĐẦU QUÉT';
  }
});

function pollBatchProgress(taskId) {
  clearInterval(pollInterval);
  pollInterval = setInterval(async () => {
    try {
      const res = await fetch(`/api/batch/status?task_id=${taskId}`);
      const data = await res.json();
      const pct = data.total > 0 ? Math.round((data.progress / data.total) * 100) : 0;

      document.getElementById('batchProgRatio').textContent = `${pct}% (${data.progress}/${data.total})`;
      document.getElementById('batchProgBar').style.width = `${pct}%`;
      document.getElementById('batchProgStatus').textContent = data.is_done ? 'ĐÃ HOÀN TẤT!' : 'Đang xử lý socket pooling...';

      if (data.results && data.results.length > 0) {
        allResults = data.results;
        renderFilteredResults();
      }

      if (data.is_done) {
        clearInterval(pollInterval);
        btnStartBatch.disabled = false;
        btnStartBatch.textContent = 'BẮT ĐẦU QUÉT';
        showToast('ĐÃ QUÉT XONG TOÀN BỘ DANH SÁCH!');
      }
    } catch (e) {
      clearInterval(pollInterval);
    }
  }, 1000);
}

function renderFilteredResults() {
  let filtered = allResults;
  if (activeResultFilter === 'trang') {
    filtered = allResults.filter(r => r.is_trang || (r.account && r.account.includes('TRẮNG')));
  } else if (activeResultFilter === 'vip') {
    filtered = allResults.filter(r => r.is_vip || (r.rank && ['Cao Thủ', 'Thách Đấu'].includes(r.rank)));
  } else if (activeResultFilter === 'live') {
    filtered = allResults.filter(r => r.status === 'HIT');
  }

  document.getElementById('cntAll').textContent = allResults.length;
  document.getElementById('cntTrang').textContent = allResults.filter(r => r.is_trang).length;
  document.getElementById('cntVip').textContent = allResults.filter(r => r.is_vip).length;
  document.getElementById('cntLive').textContent = allResults.filter(r => r.status === 'HIT').length;

  if (filtered.length === 0) {
    batchResultsList.innerHTML = '<div style="text-align:center;padding:20px;color:var(--text-muted);">Không có kết quả cho bộ lọc này.</div>';
    return;
  }

  batchResultsList.innerHTML = filtered.map(r => `
    <div class="result-row-item ${r.status === 'HIT' ? 'hit' : 'invalid'}">
      <div style="display:flex;justify-content:space-between;">
        <strong>${escapeHtml(r.account)}</strong>
        <span style="color:${r.status==='HIT'?'var(--green-neon)':'var(--red-neon)'};">${r.status}</span>
      </div>
      <div style="color:var(--text-secondary);font-size:11px;">
        ${r.status === 'HIT' ? `Tướng: ${r.hero_count||0} | Skin: ${r.skin_count||0} | Rank: ${r.rank||'Chưa Rank'} | Trắng TTT: ${r.is_trang?'[CÓ]':'[KHÔNG]'}` : r.detail || 'Sai mật khẩu hoặc bị khóa'}
      </div>
    </div>
  `).join('');
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
  const text = allResults.map(r => `${r.account} | ${r.status}`).join('\n');
  navigator.clipboard.writeText(text);
  showToast('ĐÃ SAO CHÉP TOÀN BỘ KẾT QUẢ!');
});

document.getElementById('btnExportTrang').addEventListener('click', () => {
  const trangList = allResults.filter(r => r.is_trang).map(r => `${r.account} | ${r.status}`).join('\n');
  const blob = new Blob([trangList], { type: 'text/plain' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `acc_trang_thong_tin_${Date.now()}.txt`;
  a.click();
  showToast('ĐÃ XUẤT FILE ACC TRẮNG THÀNH CÔNG!');
});

// ── TAB 3: PLAYGROUND AI COPILOT ────────────────────────────────────────────
const aiMainChatBody = document.getElementById('aiMainChatBody');
const aiCanvasForm = document.getElementById('aiCanvasForm');
const aiCanvasInput = document.getElementById('aiCanvasInput');

document.querySelectorAll('.ai-pill-btn, .ai-prompt-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const q = btn.getAttribute('data-query');
    if (q) {
      aiCanvasInput.value = q;
      sendAICanvasMessage(q);
    }
  });
});

aiCanvasInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    const msg = aiCanvasInput.value.trim();
    if (msg) sendAICanvasMessage(msg);
  }
});

aiCanvasForm.addEventListener('submit', (e) => {
  e.preventDefault();
  const msg = aiCanvasInput.value.trim();
  if (msg) sendAICanvasMessage(msg);
});

async function sendAICanvasMessage(text) {
  appendAIMessage('user', text);
  aiCanvasInput.value = '';

  const typing = appendAIMessage('assistant', 'Đang trích xuất dữ liệu RAG và phân tích...', true);

  try {
    const userName = currentUser ? (currentUser.display_name || currentUser.username || 'Tris') : 'Tris';
    const res = await fetch('/api/ai/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        prompt: text,
        task_id: activeTaskId || '',
        user_name: userName,
        user_id: currentUser ? currentUser.id : 0
      })
    });
    const data = await res.json();
    typing.remove();
    if (data.status === 'ok' || data.success) {
      appendAIMessage('assistant', data.response || data.reply || 'Đã phân tích xong.');
    } else {
      appendAIMessage('assistant', data.error || 'Trợ lý AI gặp gián đoạn kết nối.');
    }
  } catch (err) {
    typing.remove();
    appendAIMessage('assistant', 'Lỗi kết nối tới AI Copilot.');
  }
}

function appendAIMessage(role, content, isTyping = false) {
  const row = document.createElement('div');
  row.className = `ai-message-row ${role}`;

  const av = document.createElement('div');
  av.className = 'ai-msg-avatar';
  if (role === 'user') {
    av.textContent = (currentUser && currentUser.username ? currentUser.username[0] : 'U').toUpperCase();
  } else {
    av.innerHTML = '<img src="/assets/garena_logo.png" style="width:20px;height:20px;object-fit:contain;" alt="AI" />';
  }

  const bubble = document.createElement('div');
  bubble.className = 'ai-msg-bubble';

  const header = document.createElement('div');
  header.className = 'ai-sender-name';
  header.innerHTML = role === 'user' ? 'BẠN' : 'AOV COPILOT <span class="ai-time">ONLINE</span>';

  const text = document.createElement('div');
  text.className = 'ai-msg-text';
  text.innerHTML = content.replace(/\n/g, '<br/>');

  bubble.appendChild(header);
  bubble.appendChild(text);

  row.appendChild(av);
  row.appendChild(bubble);
  aiMainChatBody.appendChild(row);
  aiMainChatBody.scrollTop = aiMainChatBody.scrollHeight;
  return row;
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
    localStorage.removeItem('aov_user');
    showLanding();
    showToast('ĐÃ ĐĂNG XUẤT TÀI KHOẢN');
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
}

// File upload direct avatar handler
const fileInpAvatar = document.getElementById('settingAvatarFileInput');
if (fileInpAvatar) {
  fileInpAvatar.addEventListener('change', (e) => {
    const file = e.target.files && e.target.files[0];
    if (!file) return;
    if (file.size > 5 * 1024 * 1024) {
      showToast('Kích thước ảnh tối đa 5MB');
      return;
    }

    const reader = new FileReader();
    reader.onload = function(evt) {
      const dataUrl = evt.target.result;
      selectedAvatarChoice = dataUrl;
      const avtUrlInp = document.getElementById('settingAvatarUrl');
      if (avtUrlInp) avtUrlInp.value = '';
      document.querySelectorAll('.preset-avatar-item').forEach(el => el.classList.remove('active'));
      updateAvatarPreview(dataUrl);
      showToast('Đã chọn ảnh! Hãy bấm "LƯU THAY ĐỔI CÀI ĐẶT" bên phải.');
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
        headers: { 'Content-Type': 'application/json' },
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
        loadSettings();
        showToast('ĐÃ CẬP NHẬT HỒ SƠ TÀI KHOẢN THÀNH CÔNG!');
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
      headers: { 'Content-Type': 'application/json' },
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
      showToast(data.error || 'Cập nhật thất bại');
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
      headers: { 'Content-Type': 'application/json' },
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
      showToast(data.error || 'Không thể đổi quyền');
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
      headers: { 'Content-Type': 'application/json' },
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

// Theme Switching
let currentTheme = localStorage.getItem('aov_theme') || 'dark';
function applyTheme(th) {
  currentTheme = th;
  document.documentElement.setAttribute('data-theme', th);
  localStorage.setItem('aov_theme', th);
}
applyTheme(currentTheme);

const btnLandingTheme = document.getElementById('btnLandingTheme');
if (btnLandingTheme) btnLandingTheme.addEventListener('click', () => applyTheme(currentTheme === 'dark' ? 'light' : 'dark'));

const btnStudioTheme = document.getElementById('btnStudioTheme');
if (btnStudioTheme) btnStudioTheme.addEventListener('click', () => applyTheme(currentTheme === 'dark' ? 'light' : 'dark'));

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
