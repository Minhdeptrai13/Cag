"""
AOV Engine - Core Engine for Garena & Arena of Valor (Lien Quan Mobile)
Delegates to the battle-tested Check1 socket & protocol engine and formats the result
for CLI, Web UI, and Desktop App.
"""
import os
import re
import sys

import Check1
from Check1 import check_login as check1_login
from Check1 import _derive_tinh_trang as check1_derive_tinh_trang
from core.aov_database import translate_aov_rank

# ── High-Performance Optimization ──────────────────────────────────────────
# Garena servers no longer reply to legacy socket CMD 289 (user_basic) & CMD 342 (account_info),
# which previously caused 14s-19s socket timeouts per account.
# All account security (phone, email, 2FA, CCCD) is fully retrieved in 0.05s via SSO key.
Check1._fetch_user_basic = lambda *a, **k: {}
Check1._fetch_account_info = lambda *a, **k: {}
Check1._fetch_kientuong_player = lambda *a, **k: {}

derive_tinh_trang = check1_derive_tinh_trang


def parse_combo_line(line: str) -> tuple[str, str]:
    """
    Parse account and password from a line with arbitrary delimiters:
    :, |, ;, tab, slash, double slash, space, etc.
    Examples:
      acc:pass
      acc|pass
      acc;pass
      acc/pass
      acc pass
    """
    line = str(line or "").strip()
    if not line or line.startswith("#"):
        return "", ""

    # Common delimiters in order of priority
    for sep in (":", "|", ";", "\t", "---", "--"):
        if sep in line:
            parts = line.split(sep, 1)
            u, p = parts[0].strip(), parts[1].strip()
            if u and p:
                return u, p

    # Fallback to multiple spaces or single space/slash
    m = re.split(r"[\s/]+", line, maxsplit=1)
    if len(m) >= 2 and m[0].strip() and m[1].strip():
        return m[0].strip(), m[1].strip()

    return "", ""


def derive_accurate_tinh_trang(raw: dict) -> str:
    """Derive account condition using the exact proven algorithm from Check1.py."""
    if not raw or raw.get("status") != "HIT":
        return "Chưa xác định"
    return check1_derive_tinh_trang(raw)


def check_account(account: str, password: str, proxy=None, timeout: int = 10) -> dict:
    """
    Main checking method.
    Returns a unified result dictionary with login status, AOV profile, skins, rank, and security info.
    """
    account = account.strip()
    password = password.strip()

    raw = check1_login(account, password, timeout=timeout, fetch_info=True, proxy=proxy)
    status = raw.get("status", "ERROR")

    phone_display = (raw.get("aov_prefill_mobile") or raw.get("fcmobile_prefill_mobile") or raw.get("masked_phone") or "").strip()
    mobile_bound = bool(raw.get("mobile_bound"))
    has_phone = mobile_bound or bool(phone_display and phone_display != "Trắng")
    if not phone_display and mobile_bound:
        phone_display = "ĐÃ LIÊN KẾT"

    tinh_trang = derive_accurate_tinh_trang(raw) if status == "HIT" else "Chưa xác định"
    is_trang = (tinh_trang == "Acc Trắng") and not has_phone
    if has_phone and (is_trang or tinh_trang == "Acc Trắng"):
        is_trang = False
        tinh_trang = "Acc Dính SĐT"

    from core.aov_database import classify_skins, translate_aov_rank

    skins_dict = raw.get("aov_skins") or {}
    owned_ids = skins_dict.get("owned_ids") if isinstance(skins_dict, dict) else None

    if owned_ids:
        classified = classify_skins(owned_ids)
        total_skins = classified["total_skins"]
        total_champs = classified["total_champs"]
        sss_list = classified["sss_list"]
        anime_list = classified["anime_list"]
        ss_list = classified["ss_list"]
        other_list = classified["other_list"]
    else:
        total_skins = int(skins_dict.get("total_skins", 0) or 0) if isinstance(skins_dict, dict) else 0
        total_champs = int(skins_dict.get("total_champs", 0) or 0) if isinstance(skins_dict, dict) else 0
        sss_list = skins_dict.get("sss_list", []) if isinstance(skins_dict, dict) else []
        anime_list = skins_dict.get("anime_list", []) if isinstance(skins_dict, dict) else []
        ss_list = skins_dict.get("ss_list", []) if isinstance(skins_dict, dict) else []
        other_list = skins_dict.get("other_list", []) if isinstance(skins_dict, dict) else []

    rank_name = raw.get("aov_rank") or "Chưa Đấu Hạng"
    rank_translated = translate_aov_rank(rank_name)

    player_name = raw.get("aov_name") or raw.get("username") or ""
    country = raw.get("country") or raw.get("acc_country") or raw.get("country_code") or "VN"

    # Extract latest login specifically for Lien Quan Mobile
    last_login = ""
    for hist in (raw.get("login_history") or []):
        gname = str(hist.get("game") or "").lower()
        if any(x in gname for x in ("liên quân", "aov", "arena of valor", "moba")):
            last_login = hist.get("time") or ""
            break
    if not last_login:
        last_login = raw.get("last_login") or "Chưa ghi nhận"

    level = int(raw.get("aov_level", 0) or 0)
    if level == 0 and rank_translated != "Chưa Đấu Hạng":
        level = 30  # Lien Quan accounts with ranked divisions have achieved level 30

    result = {
        "status": status,
        "account": account,
        "password": password,
        "message": raw.get("detail") or ("Đăng nhập thành công." if status == "HIT" else "Sai tài khoản hoặc mật khẩu."),
        "tinh_trang": tinh_trang,
        "is_trang": is_trang,
        "country": country,
        "last_login": last_login,
        "shells": int(raw.get("shells", 0) or 0),
        "aov": {
            "name": player_name,
            "level": level,
            "rank": rank_translated,
            "stars": int(raw.get("aov_rank_stars", 0) or 0),
            "total_champs": total_champs,
            "total_skins": total_skins,
            "banned": raw.get("aov_banned", "KHÔNG"),
            "reg_time": raw.get("aov_reg_time", ""),
            "sss_count": len(sss_list),
            "sss_list": sss_list,
            "anime_count": len(anime_list),
            "anime_list": anime_list,
            "ss_count": len(ss_list),
            "ss_list": ss_list,
            "other_count": len(other_list),
            "other_list": other_list,
            "cp": skins_dict.get("cp", 0) if isinstance(skins_dict, dict) else 0,
        },
        "security": {
            "has_phone": has_phone,
            "mobile_bound": mobile_bound,
            "masked_phone": phone_display,
            "masked_email": (raw.get("masked_email") or "").strip(),
            "email_v": bool(raw.get("email_verified")) or bool(int(raw.get("email_v", 0) or 0)),
            "has_cccd": bool((raw.get("idcard") or "").replace("*", "").strip()),
            "idcard": (raw.get("idcard") or "").strip(),
            "fb_linked": bool(raw.get("fb_linked")),
            "fb_uid": (raw.get("fb_uid") or raw.get("fb_uid_login") or "").strip(),
            "auth_2fa": bool(raw.get("authenticator_enable", 0)) or bool(raw.get("two_step_verify", 0)),
        },
    }

    # Root-level aliases for direct frontend & DB consumption
    vip_skins_list = sss_list + anime_list + ss_list
    vip_skins_str = ", ".join(vip_skins_list) if vip_skins_list else ""
    splus_skins_str = ", ".join(other_list) if other_list else ""

    result["rank"] = rank_translated
    result["heroes_count"] = total_champs
    result["skins_count"] = total_skins
    result["ingame"] = player_name
    result["skins_vip"] = vip_skins_str
    result["skins_splus"] = splus_skins_str
    result["sss_list"] = sss_list
    result["anime_list"] = anime_list
    result["ss_list"] = ss_list
    result["other_list"] = other_list
    result["tt_info"] = tinh_trang
    result["has_phone"] = has_phone
    result["mobile_bound"] = mobile_bound
    result["masked_phone"] = phone_display
    result["masked_email"] = result["security"]["masked_email"]
    result["email_v"] = result["security"]["email_v"]
    result["has_cccd"] = result["security"]["has_cccd"]
    result["idcard"] = result["security"]["idcard"]
    result["fb_linked"] = result["security"]["fb_linked"]
    result["fb_uid"] = result["security"]["fb_uid"]
    result["auth_2fa"] = result["security"]["auth_2fa"]
    result["full_info"] = format_account_full_info(result)

    return result


def format_account_full_info(r: dict) -> str:
    """
    Format exact string requested by user:
    tk:mk | NAME :Shadow Hunter | RANK : Thách Đấu | LEVEL : 64 | HERO : 111 | SKIN : 116 | BAN : KHÔNG | EMAIL : NO [CHƯA XÁC THỰC] | SDT : NO | CMND : YES | AUTHEN : YES | FB : DIE | SÒ : 9 | QUỐC GIA : ID | LOGIN LẦN CUỐI : 21:26:53 09/09/2026 | SS : 1 [Butterfly Kim Ngư Thần Nữ] | SSS : 2 [Tulen Thần Sứ STL‑79, Tulen Chí Tôn Kiếm Tiên] | ANIME : 3 [Allain – Kirito V2, Lữ Bố – Ichigo Kurosaki, Nakroth – Gon Freecss] | OTHER : 110 [] | TRẠNG THÁI : ACC FULL
    """
    if not r:
        return ""

    acc = r.get("account", "")
    pwd = r.get("password", "")
    status = r.get("status", "ERROR")

    if status != "HIT":
        return f"{acc}:{pwd} | STATUS : {status} | DETAIL : {r.get('message', 'Thất bại')}"

    aov = r.get("aov") or {}
    sec = r.get("security") or {}

    name = aov.get("name") or "Chưa đặt tên"
    rank = aov.get("rank") or "Chưa Đấu Hạng"
    stars = aov.get("stars", 0)
    rank_str = f"{rank} {stars} sao" if stars > 0 else rank
    level = aov.get("level", 0)
    hero = aov.get("total_champs", 0)
    skin = aov.get("total_skins", 0)
    ban = aov.get("banned") or "KHÔNG"

    # Email
    masked_email = (sec.get("masked_email") or "").strip()
    email_verified = sec.get("email_v", False)
    if not masked_email or masked_email == "Trắng":
        email_str = "NO [CHƯA LIÊN KẾT]"
    elif email_verified:
        email_str = f"YES [{masked_email} - ĐÃ XÁC THỰC]"
    else:
        email_str = f"NO [{masked_email} - CHƯA XÁC THỰC]"

    # SDT
    has_phone = bool(sec.get("has_phone")) or bool(sec.get("mobile_bound"))
    masked_phone = (sec.get("masked_phone") or "").strip()
    if masked_phone and masked_phone != "Trắng":
        sdt_str = f"YES [{masked_phone}]"
    elif has_phone:
        sdt_str = "YES [ĐÃ LIÊN KẾT]"
    else:
        sdt_str = "NO"

    # CMND / CCCD
    idcard = (sec.get("idcard") or "").strip()
    if sec.get("has_cccd"):
        cmnd_str = f"YES [{idcard}]" if idcard and idcard.replace("*", "").strip() else "YES"
    else:
        cmnd_str = "NO"

    # AUTHEN 2FA (Only app authenticator)
    authen_str = "YES" if sec.get("auth_2fa") else "NO"

    # FB
    fb_linked = sec.get("fb_linked", False)
    fb_uid = (sec.get("fb_uid") or "").strip()
    if fb_linked:
        fb_str = f"YES [{fb_uid}]" if fb_uid else "YES"
    else:
        fb_str = "DIE"

    # SO
    shells = r.get("shells", 0)

    # QUOC GIA
    country = (r.get("country") or "VN").upper()

    # LOGIN LAN CUOI
    last_login = r.get("last_login") or "Chưa ghi nhận"

    # SS
    ss_list = aov.get("ss_list") or []
    ss_str = f"{len(ss_list)} [{', '.join(ss_list)}]"

    # SSS
    sss_list = aov.get("sss_list") or []
    sss_str = f"{len(sss_list)} [{', '.join(sss_list)}]"

    # ANIME
    anime_list = aov.get("anime_list") or []
    anime_str = f"{len(anime_list)} [{', '.join(anime_list)}]"

    # OTHER
    other_list = aov.get("other_list") or []
    other_str = f"{len(other_list)} [{', '.join(other_list[:10])}{'...' if len(other_list) > 10 else ''}]"

    # TRANG THAI
    trang_thai = (r.get("tinh_trang") or "CÓ THÔNG TIN").upper()

    return f"{acc}:{pwd} | NAME :{name} | RANK : {rank_str} | LEVEL : {level} | HERO : {hero} | SKIN : {skin} | BAN : {ban} | EMAIL : {email_str} | SDT : {sdt_str} | CMND : {cmnd_str} | AUTHEN : {authen_str} | FB : {fb_str} | SÒ : {shells} | QUỐC GIA : {country} | LOGIN LẦN CUỐI : {last_login} | SS : {ss_str} | SSS : {sss_str} | ANIME : {anime_str} | OTHER : {other_str} | TRẠNG THÁI : {trang_thai}"



