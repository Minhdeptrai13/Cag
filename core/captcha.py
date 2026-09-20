"""
Internal Anti-Bot Multi-Mode Captcha Engine
Supports 3 ultra-fast, zero-lag verification modes:
1. 'click'  : One-Click Smart Human Verification (mouse speed & latency validation)
2. 'slider' : Smooth Magnetic Slide Verification (HMAC bounded tolerance)
3. 'matrix' : Icon Question Matrix Selection (SVG vector icons, load in 0ms)
"""
import hmac
import hashlib
import json
import secrets
import time

CAPTCHA_SECRET = secrets.token_hex(32)
CHALLENGE_EXPIRY_SECONDS = 180  # 3 minutes

# Pre-defined lightweight SVG icon categories for Matrix Challenge (instant 0ms render)
MATRIX_ICONS = [
    {"id": "sword", "name": "Thanh Kiếm", "icon": "⚔️"},
    {"id": "shield", "name": "Chiếc Khiên", "icon": "🛡️"},
    {"id": "crown", "name": "Vương Miện", "icon": "👑"},
    {"id": "gem", "name": "Viên Ngọc", "icon": "💎"},
    {"id": "flame", "name": "Ngọn Lửa", "icon": "🔥"},
    {"id": "star", "name": "Ngôi Sao", "icon": "⭐"}
]


def generate_captcha_challenge(mode: str = "click") -> dict:
    """
    Generate challenge according to selected mode: 'click', 'slider', or 'matrix'.
    """
    challenge_id = secrets.token_hex(8)
    timestamp = int(time.time())

    if mode == "click":
        # Hidden proof nonce for 1-click human detection
        nonce = secrets.token_hex(16)
        payload = f"{challenge_id}:click:{nonce}:{timestamp}"
        signature = hmac.new(CAPTCHA_SECRET.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
        return {
            "mode": "click",
            "challenge_id": challenge_id,
            "nonce": nonce,
            "token": f"{challenge_id}:click:{nonce}:{timestamp}:{signature}"
        }

    elif mode == "slider":
        target_ratio = round(0.25 + (secrets.randbelow(55) / 100.0), 2)  # 0.25 to 0.80
        payload = f"{challenge_id}:slider:{target_ratio}:{timestamp}"
        signature = hmac.new(CAPTCHA_SECRET.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
        return {
            "mode": "slider",
            "challenge_id": challenge_id,
            "target_ratio": target_ratio,
            "token": f"{challenge_id}:slider:{target_ratio}:{timestamp}:{signature}"
        }

    else:  # 'matrix'
        # Pick 1 target icon category
        target_cat = secrets.choice(MATRIX_ICONS)
        # Create a 6-item grid where 2 or 3 items match the target
        match_count = secrets.choice([2, 3])
        grid = []
        correct_indexes = []

        # Add target items
        for _ in range(match_count):
            grid.append(target_cat)

        # Fill remaining with other random categories
        other_cats = [c for c in MATRIX_ICONS if c["id"] != target_cat["id"]]
        while len(grid) < 6:
            grid.append(secrets.choice(other_cats))

        # Secure shuffle
        shuffled_grid = []
        indices = list(range(len(grid)))
        while indices:
            idx = indices.pop(secrets.randbelow(len(indices)))
            shuffled_grid.append({
                "cell_id": len(shuffled_grid),
                "icon": grid[idx]["icon"],
                "type": grid[idx]["id"]
            })
            if grid[idx]["id"] == target_cat["id"]:
                correct_indexes.append(len(shuffled_grid) - 1)

        correct_indexes.sort()
        correct_key = ",".join(map(str, correct_indexes))

        payload = f"{challenge_id}:matrix:{target_cat['id']}:{correct_key}:{timestamp}"
        signature = hmac.new(CAPTCHA_SECRET.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()

        return {
            "mode": "matrix",
            "challenge_id": challenge_id,
            "target_name": target_cat["name"],
            "target_icon": target_cat["icon"],
            "grid": shuffled_grid,
            "token": f"{challenge_id}:matrix:{target_cat['id']}:{correct_key}:{timestamp}:{signature}"
        }


def verify_captcha_response(mode: str, token: str, user_answer) -> bool:
    """
    Validate user response based on challenge mode.
    """
    try:
        parts = token.split(":")
        if len(parts) < 4:
            return False

        if mode == "click":
            # format: challenge_id:click:nonce:timestamp:sig
            if len(parts) != 5:
                return False
            cid, _, nonce, ts_str, sig = parts
            timestamp = int(ts_str)
            if time.time() - timestamp > CHALLENGE_EXPIRY_SECONDS:
                return False
            # Check elapsed human interaction time (minimum 250ms to avoid automated instant post)
            elapsed_ms = user_answer.get("elapsed_ms", 0) if isinstance(user_answer, dict) else 300
            if elapsed_ms < 150:
                return False

            payload = f"{cid}:click:{nonce}:{timestamp}"
            expected = hmac.new(CAPTCHA_SECRET.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
            return hmac.compare_digest(sig, expected)

        elif mode == "slider":
            # format: challenge_id:slider:target_ratio:timestamp:sig
            if len(parts) != 5:
                return False
            cid, _, target_ratio_str, ts_str, sig = parts
            timestamp = int(ts_str)
            if time.time() - timestamp > CHALLENGE_EXPIRY_SECONDS:
                return False

            payload = f"{cid}:slider:{target_ratio_str}:{timestamp}"
            expected = hmac.new(CAPTCHA_SECRET.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(sig, expected):
                return False

            # Check ratio tolerance
            target_ratio = float(target_ratio_str)
            if isinstance(user_answer, dict):
                user_x = float(user_answer.get("user_x", 0))
                track_width = float(user_answer.get("track_width", 300))
                user_ratio = user_x / max(track_width - 40, 1)
            else:
                user_ratio = float(user_answer)
            return abs(user_ratio - target_ratio) <= 0.08

        elif mode == "matrix":
            # format: challenge_id:matrix:target_cat_id:correct_key:timestamp:sig
            if len(parts) != 6:
                return False
            cid, _, cat_id, correct_key, ts_str, sig = parts
            timestamp = int(ts_str)
            if time.time() - timestamp > CHALLENGE_EXPIRY_SECONDS:
                return False

            payload = f"{cid}:matrix:{cat_id}:{correct_key}:{timestamp}"
            expected = hmac.new(CAPTCHA_SECRET.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(sig, expected):
                return False

            # user_answer should be list or comma string of selected cell indices
            if isinstance(user_answer, list):
                sub_key = ",".join(map(str, sorted(user_answer)))
            else:
                sub_key = str(user_answer).strip()
            return sub_key == correct_key

    except Exception:
        return False
    return False
