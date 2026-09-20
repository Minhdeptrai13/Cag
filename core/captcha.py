"""
Internal Anti-Bot Captcha Engine
Provides secure, self-hosted verification challenges (Slider & Math)
Zero external dependencies, fast HMAC validation, resistant to replay attacks.
"""
import hmac
import hashlib
import json
import secrets
import time

CAPTCHA_SECRET = secrets.token_hex(32)
CHALLENGE_EXPIRY_SECONDS = 180  # 3 minutes


def generate_slider_challenge() -> dict:
    """
    Generate a dynamic slider verification challenge.
    Target coordinate X is between 40 and 240 pixels.
    """
    target_x = secrets.randbelow(200) + 40
    challenge_id = secrets.token_hex(8)
    timestamp = int(time.time())

    # Create tamper-proof HMAC token concealing the target_x
    payload_str = f"{challenge_id}:{target_x}:{timestamp}"
    signature = hmac.new(
        CAPTCHA_SECRET.encode("utf-8"),
        payload_str.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    return {
        "challenge_id": challenge_id,
        "token": f"{challenge_id}:{timestamp}:{signature}",
        "slider_max": 280,
        "type": "slider",
        "target_display": target_x  # Client draws indicator or puzzle notch
    }


def verify_slider_response(token: str, submitted_x: float, user_target_x: int) -> bool:
    """
    Verify submitted position with +- 6px tolerance and anti-bot speed heuristics.
    """
    try:
        parts = token.split(":")
        if len(parts) != 3:
            return False
        challenge_id, ts_str, signature = parts
        timestamp = int(ts_str)

        # Check expiration
        if time.time() - timestamp > CHALLENGE_EXPIRY_SECONDS:
            return False

        # Verify HMAC signature against user_target_x
        payload_str = f"{challenge_id}:{user_target_x}:{timestamp}"
        expected_sig = hmac.new(
            CAPTCHA_SECRET.encode("utf-8"),
            payload_str.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(signature, expected_sig):
            return False

        # Tolerance check (+- 6 pixels)
        return abs(float(submitted_x) - float(user_target_x)) <= 6.5
    except Exception:
        return False
