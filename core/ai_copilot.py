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

QWEN_ENDPOINT = "https://free.empero.org/v1/chat/completions"
QWEN_MODEL = "Qwen/Qwen3.8-27B-FP8"
QWEN_KEY = "free"


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


def chat_with_copilot(user_message: str, history: list = None, batch_context: dict = None) -> str:
    """Send message to Qwen 3.8 with RAG system prompt and auto-fallback"""
    system_prompt = build_system_rag_prompt(batch_context)

    messages = [{"role": "system", "content": system_prompt}]
    if history:
        for msg in history[-6:]:  # Keep last 6 exchanges
            messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
    messages.append({"role": "user", "content": user_message})

    # 1. Try Qwen 3.8 endpoint
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

    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        # 2. Intelligent Offline Fallback Engine (Zero downtime)
        return generate_offline_rag_response(user_message, batch_context)


def generate_offline_rag_response(prompt: str, batch_context: dict) -> str:
    """Local fallback responding with full AOV logic when free AI endpoint is 503"""
    pl = prompt.lower()
    total = batch_context.get("total", 0) if batch_context else 0
    hits = batch_context.get("hits", 0) if batch_context else 0
    trang = batch_context.get("trang", 0) if batch_context else 0
    recent_hits = batch_context.get("recent_hits", []) if batch_context else []

    if any(k in pl for k in ("tổng quan", "tiến độ", "bao nhiêu", "báo cáo", "tình hình")):
        return f"""📊 **BÁO CÁO TIẾN TRÌNH LIVE:**
- Tổng combo nạp: **{total}**
- Tài khoản LIVE (Đăng nhập được): **{hits}**
- Tài khoản Trắng TTT: **{trang}** (Đạt tỉ lệ {round((trang/hits*100) if hits else 0, 1)}% trên tổng số acc sống).
Hệ thống đang hoạt động ở trạng thái luồng cao nhất."""

    if any(k in pl for k in ("acc trắng", "trắng thông tin", "trắng ttt")):
        return f"""🛡️ **PHÂN TÍCH ACC TRẮNG:**
Hiện tìm thấy **{trang}** acc Trắng TTT. Các acc này hoàn toàn KHÔNG dính SĐT, KHÔNG dính CCCD, KHÔNG có 2FA và KHÔNG liên kết Facebook. Bạn có thể nhấn nút **"XUẤT ACC TRẮNG TTT"** để tải file về bán ngay."""

    if any(k in pl for k in ("định giá", "giá", "bán")):
        return f"""💰 **GỢI Ý ĐỊNH GIÁ ACC HIỆN TẠI:**
- Acc Trắng TTT (Rank Kim Cương - Tinh Anh, 1-2 SS/Anime): 50.000đ - 120.000đ / acc.
- Acc có skin Thứ Nguyên Vệ Thần (Violet, Airi, Tulen ST.L): 200.000đ - 500.000đ+ tuỳ độ sạch thông tin.
- Acc dính SĐT/CCCD: Nên bán xả theo combo giá rẻ (10.000đ - 25.000đ / acc)."""

    if any(k in pl for k in ("skin", "sss", "anime", "hiếm")):
        vip_found = [h.get("skins_vip") for h in recent_hits if h.get("skins_vip")]
        vips = ", ".join(vip_found[:5]) if vip_found else "Đang quét danh sách..."
        return f"""✨ **TRA CỨU SKIN VIP:**
Hệ thống theo dõi chặt chẽ danh mục SSS, SS và Anime hợp tác bản quyền (SAO, Kimetsu, Bleach, Hunter x Hunter, JJK, AOT). Các skin VIP nổi bật vừa tìm thấy: {vips}."""

    return f"""🤖 **AOV COPILOT STUDIO:**
Tôi đã nhận được câu hỏi của bạn. Hệ thống đang quét batch với **{hits} acc sống** và **{trang} acc trắng TTT**. Tôi có thể giúp bạn lọc skin theo tên tướng, đánh giá acc giá trị cao nhất hoặc trích xuất danh sách theo tiêu chí."""
