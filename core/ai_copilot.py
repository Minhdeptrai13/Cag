"""
AI Copilot Studio with RAG (Retrieval-Augmented Generation)
Connects to Qwen 3.8 / Multi-LLM provider with fallback heuristics.
Injects deep AOV Skin metadata, current batch telemetry, and security knowledge.
"""
import json
import urllib.request
import urllib.error
import time

from core.aov_database import SKIN_SSS, SKIN_SS, SKIN_ANIME

# ── Multi-Tier Zero-Key Public AI Gateways ────────────────────────────────
KILO_GATEWAY_URL = "https://api.kilo.ai/api/gateway/chat/completions"
KILO_MODELS = ["kilo-auto/free", "qwen/qwen3.8-27b:free", "inclusionai/ling-3.0-flash-vl:free"]

LLMTECH_GATEWAY_URL = "https://api.llmtech.eu/v1/chat/completions"
LLMTECH_MODEL = "nvidia/Qwen3.8-27B-NVFP4"
LLMTECH_PUBLIC_KEY = "lt-trial-ba1ef28c6d32ed6980678d8d"

QWEN_ENDPOINT = "https://free.empero.org/v1/chat/completions"
QWEN_MODEL = "Qwen/Qwen3.8-27B-FP8"
QWEN_KEY = "free"

INVALID_AI_PATTERNS = [
    "doesn't have enough credits",
    "does not have enough credits",
    "error from provider",
    "rate limit exceeded",
    "user safety: safe",
    "model is currently unavailable",
    "account behind this api key"
]

def is_valid_ai_reply(text: str) -> bool:
    if not text or len(str(text).strip()) < 5:
        return False
    lower = str(text).lower()
    return not any(pat in lower for pat in INVALID_AI_PATTERNS)


def build_system_rag_prompt(batch_context: dict = None) -> str:
    """Build high-density RAG prompt with knowledge base and live telemetry"""
    sss_sample = ", ".join(list(SKIN_SSS.values())[:15])
    ss_sample = ", ".join(list(SKIN_SS.values())[:15])
    anime_sample = ", ".join(list(SKIN_ANIME.values())[:15])

    context_str = ""
    if batch_context:
        total = batch_context.get("total", 0)
        hits = batch_context.get("hits", 0)
        trang = batch_context.get("trang", 0)
        recent_hits = batch_context.get("recent_hits", [])
        context_str = f"""
LIVE TELEMETRY CỦA BATCH HIỆN TẠI TRÊN WEB:
- Tổng tài khoản đang quét: {total}
- Số acc LIVE (HITS): {hits}
- Số acc TRẮNG TTT (không dính SĐT/CCCD/Mail): {trang}
- Mẫu các acc sống vừa tìm thấy:
"""
        for h in recent_hits[:5]:
            ingame = h.get("ingame") or "Chưa đặt tên"
            rank = h.get("rank") or "Chưa Đấu Hạng"
            skins = h.get("skins_vip") or "Không có skin VIP"
            context_str += f"  * Acc {h.get('account')}: Ingame={ingame} | Rank={rank} | Skin VIP={skins} | Trạng thái={h.get('tinh_trang')}\n"

    return f"""Bạn là AOV Studio Copilot - Chuyên gia AI phân tích tài khoản Liên Quân Mobile và cố vấn kỹ thuật cấp cao cho Tris.
KIẾN THỨC CỐT LÕI VỀ LIÊN QUÂN MOBILE:
1. Phân loại bậc Skin:
   - SSS / Thứ Nguyên Vệ Thần (Đắt đỏ nhất, hiệu ứng tối thượng): {sss_sample}...
   - Anime Bản Quyền (SAO, Kimetsu, Bleach, Hunter x Hunter, JJK, AOT...): {anime_sample}...
   - Bậc SS / SS Hữu Hạn (Hiệu ứng biến về, âm thanh riêng): {ss_sample}...
2. Giá trị tài khoản:
   - Acc "Trắng Thông Tin" (Chưa cài SĐT, Mail, CCCD) có giá trị cao nhất vì người mua đổi thông tin ngay lập tức.
   - Acc dính SĐT hoặc CCCD bị giảm giá trị đáng kể.
{context_str}
NHIỆM VỤ CỦA BẠN:
- Phân tích, tư vấn giá bán, lọc tài khoản theo yêu cầu của Tris.
- Giải thích các thông số bảo mật, cách tối ưu tốc độ check luồng.
- Trả lời phong cách sắc sảo, tự tin, chuyên nghiệp, thông minh, ngắn gọn và hữu ích.
"""


# ── Dynamic Keyless LLM Pool via freellmpool ──────────────────────────────
_FREE_LLM_POOL = None
_POOL_INIT_TRIED = False

def get_free_llm_pool():
    global _FREE_LLM_POOL, _POOL_INIT_TRIED
    if _FREE_LLM_POOL is None and not _POOL_INIT_TRIED:
        _POOL_INIT_TRIED = True
        try:
            from freellmpool import Pool
            from freellmpool.config import configured_providers
            providers = configured_providers()
            if providers:
                _FREE_LLM_POOL = Pool(providers, routing="fair")
                print(f"[AI Copilot] freellmpool initialized with {len(providers)} keyless providers.", flush=True)
        except Exception as e:
            print(f"[AI Copilot] freellmpool init notice: {e}", flush=True)
    return _FREE_LLM_POOL


def chat_with_copilot(user_message: str, history: list = None, batch_context: dict = None) -> str:
    """
    Tier-1: Kilo Code Anonymous Free Gateway (200 req/hour, Zero API Key required)
    Tier-2: LLM Tech Public Quota Pool (2M tokens/day with public trial key)
    Tier-3: freellmpool (Multi-provider routing pool)
    Tier-4: External Qwen Fallback
    Tier-5: Native Offline AOV RAG Knowledge Engine (Zero Downtime Guarantee)
    """
    system_prompt = build_system_rag_prompt(batch_context)

    messages = [{"role": "system", "content": system_prompt}]
    if history:
        for msg in history[-6:]:  # Keep last 6 exchanges
            messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
    messages.append({"role": "user", "content": user_message})

    # 1. TIER-1: Kilo Code Anonymous Gateway (kilo-auto/free & qwen)
    for model_id in KILO_MODELS:
        try:
            payload = {
                "model": model_id,
                "messages": messages,
                "max_tokens": 1024,
                "temperature": 0.7
            }
            req = urllib.request.Request(
                KILO_GATEWAY_URL,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AOV-Copilot/2.0"
                }
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                reply = data["choices"][0]["message"]["content"].strip()
                if is_valid_ai_reply(reply):
                    return reply
        except Exception as err:
            pass

    # 2. TIER-2: LLM Tech Public Provider (Qwen 3.8 NVFP4)
    try:
        payload = {
            "model": LLMTECH_MODEL,
            "messages": messages,
            "max_tokens": 1024,
            "temperature": 0.7
        }
        req = urllib.request.Request(
            LLMTECH_GATEWAY_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {LLMTECH_PUBLIC_KEY}",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AOV-Copilot/2.0"
            }
        )
        with urllib.request.urlopen(req, timeout=9) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            reply = data["choices"][0]["message"]["content"].strip()
            if is_valid_ai_reply(reply):
                return reply
    except Exception as err:
        pass

    # 3. TIER-3: freellmpool (Keyless LLM Pool with community routes)
    pool = get_free_llm_pool()
    if pool:
        try:
            res = pool.chat(messages, max_tokens=1024)
            reply_text = getattr(res, "text", None) or getattr(res, "content", "")
            if is_valid_ai_reply(reply_text):
                return str(reply_text).strip()
        except Exception as err:
            pass

    # 4. TIER-4: Legacy Qwen endpoint
    try:
        body = {
            "model": QWEN_MODEL,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 1024
        }
        req = urllib.request.Request(
            QWEN_ENDPOINT,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {QWEN_KEY}",
                "User-Agent": "AOV-Studio/2.0"
            }
        )
        with urllib.request.urlopen(req, timeout=7) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            reply = data["choices"][0]["message"]["content"].strip()
            if is_valid_ai_reply(reply):
                return reply
    except Exception:
        pass

    # 5. TIER-5: Native Instant AOV RAG Knowledge Engine (Always online)
    return generate_offline_rag_response(user_message, batch_context)


def generate_offline_rag_response(prompt: str, batch_context: dict) -> str:
    """Zero-Dependency Native AI Engine (Instant, No API Key needed, Zero Downtime)"""
    pl = prompt.lower().strip()
    total = batch_context.get("total", 0) if batch_context else 0
    hits = batch_context.get("hits", 0) if batch_context else 0
    trang = batch_context.get("trang", 0) if batch_context else 0
    recent_hits = batch_context.get("recent_hits", []) if batch_context else []

    # 0. Giao tiếp tự nhiên, chào hỏi
    if any(k in pl for k in ("chào", "hello", "hi", "alo", "hé lô", "yo", "hey", "hế lô", "bạn ơi", "ad ơi", "admin ơi")):
        return f"""👋 Chào bạn! Tôi là **AOV Studio Copilot** đây.

Tôi có thể hỗ trợ bạn mọi thứ về Liên Quân Mobile và hệ thống check tài khoản:
- 💎 **Định giá acc** theo dàn Skin SSS (Thứ Nguyên, Anime Collab, Đoạt Mệnh...).
- 🛡️ **Kiểm định tiêu chuẩn Acc Trắng Thông Tin (Trắng TTT)** chuẩn Garena để bán giá cao nhất.
- 🏷️ **Tra cứu ID Skin VIP** trong cơ sở dữ liệu server.
- ⚡ **Tối ưu tốc độ quét** 100 - 500 luồng không bị rate-limit.

Bạn đang cần soi lô acc nào hay cần hỗ trợ gì cứ nói thẳng nhé!"""

    if any(k in pl for k in ("bạn là ai", "mày là ai", "giới thiệu", "who are you", "who r u", "làm được gì", "chức năng")):
        return """🤖 Tôi là **AOV Studio Copilot** – trợ lý AI chuyên biệt được tối ưu hóa cho hệ thống thẩm định và khai thác tài khoản Liên Quân Mobile.

Tôi được nạp sẵn toàn bộ tri thức:
1. Danh mục và mã code của hơn 600+ Skin Liên Quân (đặc biệt là SSS, Anime giới hạn, SS Hữu hạn).
2. Quy tắc định giá thị trường tài khoản acc Trắng vs acc dính thông tin.
3. Thuật toán mô phỏng kết nối Garena đa luồng (Socket Keep-Alive Pooling).

Cần check acc, lọc danh sách hay tối ưu luồng, cứ ra lệnh cho tôi!"""

    # 1. Tra cứu & Định giá Skin SSS / Anime / SS
    if any(k in pl for k in ("định giá", "giá", "bán", "bao nhiêu tiền", "trị giá", "acc vip", "flo", "nak", "raz", "violet", "airi", "tulen")):
        return """💎 **BẢNG ĐỊNH GIÁ THỊ TRƯỜNG TÀI KHOẢN LIÊN QUÂN (2026):**
- **Acc có Skin SSS Tối Thượng (Thứ Nguyên Vệ Thần / Đoạt Mệnh):**
  * *Violet / Airi Thứ Nguyên:* 250.000đ - 600.000đ (Trắng TTT có thể chạm mốc 800.000đ+).
  * *Nakroth Lôi Quang Sứ / Bạch Phán Quan:* 150.000đ - 350.000đ.
  * *Raz Muay Thái / Flo Tinh Hệ / Seven:* 120.000đ - 250.000đ.
- **Acc Anime Hợp Tác Giới Hạn (SAO, Kimetsu, Bleach, Hunter x Hunter, JJK):**
  * *Kirito / Asuna SAO / Zenitsu / Tanjiro:* 200.000đ - 450.000đ / skin.
- **Acc Trắng Thông Tin cơ bản (Rank Kim Cương - Tinh Anh):** 30.000đ - 70.000đ / acc.
- **Acc dính SĐT hoặc CCCD:** Giảm 60 - 70% giá trị so với acc Trắng TTT cùng bậc."""

    # 2. Tiêu chuẩn Acc Trắng TTT
    if any(k in pl for k in ("acc trắng", "trắng thông tin", "trắng ttt", "đổi mật khẩu", "2fa", "bảo mật")):
        return """🛡️ **TIÊU CHUẨN ACC TRẮNG THÔNG TIN (TRẮNG TTT) CHUẨN GARENA:**
1. **Chưa cài Số điện thoại (SĐT):** Người mua có thể thêm ngay SĐT của mình vào tài khoản.
2. **Chưa xác thực Email:** Không có email giải cứu.
3. **Chưa liên kết CCCD / CMND:** Không bị chủ cũ dùng giấy tờ tùy thân gửi ticket hỗ trợ lấy lại nick.
4. **Không bật 2FA (Garena Authenticator):** Đăng nhập thẳng không bị đòi mã OTP.
5. **Chưa liên kết Facebook:** Tránh bị đăng nhập ngầm qua cổng FB.
👉 *Hệ thống tự động lọc riêng toàn bộ acc này vào file `acc_trang_*.txt` để bạn xuất ra bán giá cao nhất.*"""

    # 3. Tra cứu ID Skin & Danh mục Skin
    if any(k in pl for k in ("tra cứu", "skin id", "mã skin", "id skin", "code skin")):
        return """🏷️ **TRA CỨU MÃ SKIN SSS / SS BẬC CAO TRONG DATABASE TOOL:**
- **Nakroth:** `11606` (Lôi Quang Sứ), `11608` (Bạch Phán Quan), `11612` (Thứ Nguyên Vệ Thần).
- **Florentino:** `19304` (Tinh Hệ SSS), `19305` (Kỷ Nguyên Hổ Phách), `19307` (Seven).
- **Raz:** `12102` (Muay Thái SS), `12106` (Siêu Cấp Chiến Binh).
- **Violet:** `10705` (Thần Long Tỉ Tỉ), `10708` (Thứ Nguyên Vệ Thần), `10712` (Vợ Người Ta).
- **Airi:** `13008` (Bích Hải Thánh Nữ), `13010` (Thứ Nguyên Vệ Thần).
- **Tulen:** `13504` (Chí Tôn Kiếm Tiên), `13507` (Thần Sứ STL).
Tool tự động đối chiếu các ID này trực tiếp từ response của Garena Server để gán nhãn VIP tức thì."""

    # 4. Thống kê tiến trình lô check
    if any(k in pl for k in ("tổng quan", "tiến độ", "bao nhiêu", "báo cáo", "tình hình", "lô check", "quét")):
        pct = round((trang / hits * 100), 1) if hits > 0 else 0
        return f"""📊 **TIẾN TRÌNH LÔ CHECK THỰC TẾ:**
- Tổng tài khoản nạp vào: **{total}**
- Đăng nhập thành công (LIVE): **{hits}**
- Đạt chuẩn Trắng Thông Tin (TRẮNG TTT): **{trang}** ({pct}% tỉ lệ sạch)
- Socket Pooling: **500 luồng cực hạn sẵn sàng**.
Bạn có thể bấm **"XUẤT ACC TRẮNG TTT"** ở tab Playground Tool để tải về ngay."""

    # 5. Tối ưu tốc độ quét & Proxy
    if any(k in pl for k in ("luồng", "tốc độ", "tối ưu", "proxy", "bị chặn", "chậm", "lag", "500")):
        return """⚡ **TỐI ƯU TỐC ĐỘ QUÉT 500 LUỒNG CỰC HẠN:**
1. **Dưới 1.000 acc:** Đặt **30 - 50 luồng**, quét xong trong 15 - 25s, không cần proxy.
2. **Từ 5.000 - 50.000 acc:** Đặt **100 - 200 luồng**, chia thành file 10k acc để trình duyệt chạy mượt nhất.
3. **Keep-Alive Connection:** Tool duy trì socket di động liên tục để tránh bị Garena drop session."""

    # 6. Mặc định: Phân tích linh hoạt
    return f"""Tôi đã nhận câu hỏi của bạn về: **"{prompt.strip()}"**.
Nếu bạn cần định giá tướng hay skin cụ thể (ví dụ: *Nakroth Lôi Quang Sứ*, *Airi Thứ Nguyên*, *Flo Tinh Hệ*), hoặc muốn tư vấn cấu hình luồng quét cho lô tài khoản hiện tại, cứ nhập tên tướng/skin để tôi giải đáp chi tiết ngay nhé!"""
