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

  const targetPane = document.getElementById(`view${tabId.charAt(0).toUpperCase() + tabId.slice(1)}`) ||
                     document.getElementById(`viewPlayground${tabId.toUpperCase()}`);
  if (targetPane) {
    targetPane.classList.add('active');
    targetPane.style.display = 'block';
  }

  if (tabId === 'dashboard') loadDashboardStats();
  if (tabId === 'api') loadApiKeys();
  if (tabId === 'settings') loadSettings();
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
  document.getElementById('studioUsername').textContent = currentUser.username || 'User';
  document.getElementById('studioUserAvatar').textContent = (currentUser.username || 'U')[0].toUpperCase();
  document.getElementById('studioCredits').textContent = (currentUser.credits !== undefined ? currentUser.credits : 0).toLocaleString();
  
  const roleEl = document.getElementById('studioUserRole');
  const role = (currentUser.role || 'user').toLowerCase();
  roleEl.textContent = role.toUpperCase();
  roleEl.className = `role-badge ${role}`;

  // Admin Box visibility
  const adminBox = document.getElementById('adminControlBox');
  if (adminBox) {
    if (role === 'owner' || role === 'admin') {
      adminBox.style.display = 'block';
      loadAdminUsersList();
    } else {
      adminBox.style.display = 'none';
    }
  }
}

// ── 3-MODE FAST INTERNAL CAPTCHA ENGINE ─────────────────────────────────────
async function initCaptcha(mode = 'click') {
  currentCaptchaMode = mode;
  captchaVerifiedPayload = null;
  matrixSelectedCells = [];

// ── Google reCAPTCHA Engine for Login & Register ────────────────────────────
let loginRecaptchaId = null;
let registerRecaptchaId = null;
let currentSiteKey = '6LeIxAcTAAAAAJcZVRqyHh71UMIEGNQ_MXjiZKhI';

async function initRecaptcha() {
  try {
    const res = await fetch('/api/captcha/new');
    const data = await res.json();
    if (data.site_key) {
      currentSiteKey = data.site_key;
    }
  } catch (e) {}

  // Check if grecaptcha is loaded
  const checkRecaptchaReady = setInterval(() => {
    if (window.grecaptcha && window.grecaptcha.render) {
      clearInterval(checkRecaptchaReady);
      renderRecaptchaWidgets();
    }
  }, 100);
}

function renderRecaptchaWidgets() {
  try {
    const loginWrap = document.getElementById('recaptchaLoginWidget');
    if (loginWrap && loginRecaptchaId === null) {
      loginRecaptchaId = grecaptcha.render('recaptchaLoginWidget', {
        'sitekey': currentSiteKey,
        'theme': 'dark'
      });
    }

    const regWrap = document.getElementById('recaptchaRegisterWidget');
    if (regWrap && registerRecaptchaId === null) {
      registerRecaptchaId = grecaptcha.render('recaptchaRegisterWidget', {
        'sitekey': currentSiteKey,
        'theme': 'dark'
      });
    }
  } catch (err) {
    console.warn('reCAPTCHA render warning:', err);
  }
}

// ── Auth Forms Handling ─────────────────────────────────────────────────────
document.getElementById('tabBtnLogin').addEventListener('click', () => showAuth('login'));
document.getElementById('tabBtnRegister').addEventListener('click', () => showAuth('register'));
document.getElementById('btnLandingLogin').addEventListener('click', () => showAuth('login'));
document.getElementById('btnHeroRegister').addEventListener('click', () => showAuth('register'));
document.getElementById('btnHeroOpenStudio').addEventListener('click', () => {
  if (currentUser) showStudio();
  else showAuth('login');
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

// Submit Login with Google reCAPTCHA
document.getElementById('formLogin').addEventListener('submit', async (e) => {
  e.preventDefault();
  const username = document.getElementById('loginUser').value.trim();
  const password = document.getElementById('loginPass').value;

  let recaptchaResponse = '';
  if (window.grecaptcha && loginRecaptchaId !== null) {
    recaptchaResponse = grecaptcha.getResponse(loginRecaptchaId);
  }

  if (!recaptchaResponse) {
    showToast('Vui lòng tích vào ô Tôi không phải là người máy!');
    return;
  }

  try {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        username,
        password,
        recaptcha_response: recaptchaResponse
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
      if (window.grecaptcha && loginRecaptchaId !== null) grecaptcha.reset(loginRecaptchaId);
    }
  } catch (err) {
    showToast('Lỗi kết nối máy chủ');
    if (window.grecaptcha && loginRecaptchaId !== null) grecaptcha.reset(loginRecaptchaId);
  }
});

// Submit Register with Google reCAPTCHA
document.getElementById('formRegister').addEventListener('submit', async (e) => {
  e.preventDefault();
  const username = document.getElementById('regUser').value.trim();
  const password = document.getElementById('regPass').value;

  let recaptchaResponse = '';
  if (window.grecaptcha && registerRecaptchaId !== null) {
    recaptchaResponse = grecaptcha.getResponse(registerRecaptchaId);
  }

  if (!recaptchaResponse) {
    showToast('Vui lòng tích vào ô xác minh Tôi không phải là người máy!');
    return;
  }

  try {
    const res = await fetch('/api/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        username,
        password,
        recaptcha_response: recaptchaResponse
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
      if (window.grecaptcha && registerRecaptchaId !== null) grecaptcha.reset(registerRecaptchaId);
    }
  } catch (err) {
    showToast('Lỗi máy chủ');
    if (window.grecaptcha && registerRecaptchaId !== null) grecaptcha.reset(registerRecaptchaId);
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

document.querySelectorAll('.ai-prompt-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const q = btn.getAttribute('data-query');
    if (q) {
      aiCanvasInput.value = q;
      sendAICanvasMessage(q);
    }
  });
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
    const res = await fetch('/api/ai/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt: text, task_id: activeTaskId || '' })
    });
    const data = await res.json();
    typing.remove();
    if (data.status === 'ok') {
      appendAIMessage('assistant', data.response);
    } else {
      appendAIMessage('assistant', data.error || 'Trợ lý AI gặp gián đoạn kết nối.');
    }
  } catch (err) {
    typing.remove();
    appendAIMessage('assistant', 'Lỗi kết nối tới AI Copilot.');
  }
}

function appendAIMessage(role, content, isTyping = false) {
  const wrap = document.createElement('div');
  wrap.className = `ai-bubble-msg ${role}`;

  const av = document.createElement('div');
  av.className = 'ai-msg-avatar';
  av.textContent = role === 'user' ? 'U' : '🤖';

  const body = document.createElement('div');
  body.className = 'ai-msg-content';
  body.innerHTML = content.replace(/\n/g, '<br/>');

  wrap.appendChild(av);
  wrap.appendChild(body);
  aiMainChatBody.appendChild(wrap);
  aiMainChatBody.scrollTop = aiMainChatBody.scrollHeight;
  return wrap;
}

// ── TAB 4: API KEY MANAGER ──────────────────────────────────────────────────
async function loadApiKeys() {
  if (!currentUser) return;
  try {
    const res = await fetch(`/api/user/keys?user_id=${currentUser.id}`);
    const data = await res.json();
    if (data.success && data.keys && data.keys.length > 0) {
      currentApiKey = data.keys[0].key;
      document.getElementById('displayActiveApiKey').textContent = currentApiKey;
    } else {
      document.getElementById('displayActiveApiKey').textContent = 'Chưa có API Key nào';
    }
  } catch (e) {
    console.error('Load keys error:', e);
  }
}

document.getElementById('btnCopyCurrentApiKey').addEventListener('click', () => {
  if (currentApiKey) {
    navigator.clipboard.writeText(currentApiKey);
    showToast('ĐÃ SAO CHÉP API KEY VÀO CLIPBOARD!');
  }
});

document.getElementById('btnCreateNewApiKey').addEventListener('click', async () => {
  if (!currentUser) return;
  try {
    const res = await fetch('/api/keys/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: currentUser.id, name: 'Production Key' })
    });
    const data = await res.json();
    if (data.success) {
      showToast('ĐÃ TẠO MÃ API KEY MỚI THÀNH CÔNG!');
      loadApiKeys();
    }
  } catch (err) {
    showToast('Lỗi khi tạo API Key');
  }
});

// ── TAB 5: SETTINGS & ADMIN ─────────────────────────────────────────────────
function loadSettings() {
  if (!currentUser) return;
  document.getElementById('settUsername').textContent = currentUser.username || '-';
  document.getElementById('settRole').textContent = (currentUser.role || 'USER').toUpperCase();
  document.getElementById('settCredits').textContent = `${(currentUser.credits || 0).toLocaleString()} CR`;
}

document.getElementById('formRedeemCode').addEventListener('submit', async (e) => {
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
      loadSettings();
      document.getElementById('inputRedeemCode').value = '';
      showToast(`NẠP THÀNH CÔNG +${data.credits_added} CREDITS!`);
    } else {
      showToast(data.error || 'Mã Giftcode không hợp lệ');
    }
  } catch (err) {
    showToast('Lỗi máy chủ');
  }
});

async function loadAdminUsersList() {
  if (!currentUser) return;
  try {
    const res = await fetch(`/api/admin/users?user_id=${currentUser.id}`);
    const data = await res.json();
    if (data.success) {
      const tbody = document.getElementById('adminUserListTbody');
      tbody.innerHTML = (data.users || []).map(u => `
        <tr style="border-bottom:1px solid rgba(255,255,255,0.05);">
          <td style="padding:10px 8px;">#${u.id}</td>
          <td style="padding:10px 8px;"><strong>${escapeHtml(u.username)}</strong></td>
          <td style="padding:10px 8px;"><span class="role-badge ${u.role}">${(u.role||'user').toUpperCase()}</span></td>
          <td style="padding:10px 8px;color:var(--gold-light);font-family:var(--font-mono);">${u.credits.toLocaleString()} CR</td>
          <td style="padding:10px 8px;">
            <button class="btn btn-ghost" style="padding:4px 8px;font-size:11px;" onclick="promptAdjustCredit('${u.username}')">+ CR</button>
          </td>
        </tr>
      `).join('');
    }
  } catch (e) {
    console.error('Admin users error:', e);
  }
}

window.promptAdjustCredit = async function(targetUsername) {
  const deltaStr = prompt(`Nhập số credits muốn cộng/trừ cho ${targetUsername}:`, "100");
  if (!deltaStr) return;
  const delta = parseInt(deltaStr, 10);
  if (isNaN(delta)) return;

  try {
    const res = await fetch('/api/admin/adjust-credits', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        admin_id: currentUser.id,
        target_username: targetUsername,
        credits_delta: delta
      })
    });
    const data = await res.json();
    if (data.success) {
      showToast(`ĐÃ CẬP NHẬT CREDITS CHO ${targetUsername}!`);
      loadAdminUsersList();
    } else {
      showToast(data.error || 'Cập nhật thất bại');
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

document.getElementById('btnLandingTheme').addEventListener('click', () => applyTheme(currentTheme === 'dark' ? 'light' : 'dark'));
document.getElementById('btnStudioTheme').addEventListener('click', () => applyTheme(currentTheme === 'dark' ? 'light' : 'dark'));

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
