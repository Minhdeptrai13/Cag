"""
AOV Engine - Core Engine for Garena & Arena of Valor (Lien Quan Mobile)
Delegates to the battle-tested Check1 socket & protocol engine and formats the result
for CLI, Web UI, and Desktop App.
"""
import os
import re
import sys

from Check1 import check_login as check1_login
from Check1 import _derive_tinh_trang as check1_derive_tinh_trang
from core.aov_database import translate_aov_rank

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
    """Derive market account condition matching Telegram bot standards."""
    phone = (raw.get("masked_phone") or "").replace("*", "").strip()
    has_phone = bool(phone) or bool(raw.get("mobile_bound"))

    email_verified = bool(raw.get("email_verified"))
    masked_email = (raw.get("masked_email") or "").strip()

    has_cccd = bool(raw.get("idcard", "").replace("*", "").strip())
    has_authen = bool(raw.get("authenticator_enable", 0))
    has_fb = bool(raw.get("fb_linked"))
    is_banned = str(raw.get("aov_banned", "")).upper() in ("CO", "YES", "TRUE", "BAN")

    if not has_phone and not has_cccd and not has_authen and not email_verified and not has_fb:
        base = "Acc Trắng"
    elif has_phone and not has_cccd and not has_authen and not email_verified and not has_fb:
        base = "Acc Dính Mỗi Số"
    elif not has_phone and not has_cccd and not has_authen and email_verified and not has_fb:
        base = "Acc Dính Mỗi Mail"
    elif has_phone and email_verified and (has_cccd or has_authen):
        base = "ACC FULL"
    else:
        parts = []
        if has_phone:
            parts.append("SĐT")
        if email_verified:
            parts.append("Mail")
        elif masked_email:
            parts.append("Mail (Chưa XT)")
        if has_cccd:
            parts.append("CCCD")
        if has_authen:
            parts.append("2FA")
        if has_fb:
            parts.append("FB")
        base = f"Acc Dính {' + '.join(parts)}" if parts else "Acc Trắng"

    if is_banned:
        base += " [BAN]"
    return base


def check_account(account: str, password: str, proxy=None, timeout: int = 10) -> dict:
    """
    Main checking method.
    Returns a unified result dictionary with login status, AOV profile, skins, rank, and security info.
    """
    account = account.strip()
    password = password.strip()

    raw = check1_login(account, password, timeout=timeout, fetch_info=True, proxy=proxy)
    status = raw.get("status", "ERROR")

    tinh_trang = derive_accurate_tinh_trang(raw) if status == "HIT" else "Chưa xác định"
    is_trang = (tinh_trang == "Acc Trắng" or "Acc Trắng" in tinh_trang)

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
        total_skins = skins_dict.get("total_skins", 0) if isinstance(skins_dict, dict) else 0
        total_champs = skins_dict.get("total_champs", 0) if isinstance(skins_dict, dict) else 0
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
            "masked_phone": raw.get("masked_phone", ""),
            "masked_email": raw.get("masked_email", ""),
            "email_v": bool(raw.get("email_verified")),
            "has_cccd": bool(raw.get("idcard", "").replace("*", "").strip()),
            "fb_linked": bool(raw.get("fb_linked")),
            "auth_2fa": bool(raw.get("authenticator_enable", 0)),
        },
    }

    # Root-level aliases for direct frontend & DB consumption
    vip_skins_list = sss_list + anime_list + ss_list
    vip_skins_str = ", ".join(vip_skins_list[:6]) if vip_skins_list else ""

    result["rank"] = rank_translated
    result["heroes_count"] = total_champs
    result["skins_count"] = total_skins
    result["ingame"] = player_name
    result["skins_vip"] = vip_skins_str
    result["tt_info"] = tinh_trang

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
    masked_phone = (sec.get("masked_phone") or "").strip()
    sdt_str = "NO" if not masked_phone or masked_phone == "Trắng" else f"YES [{masked_phone}]"

    # CMND / CCCD
    cmnd_str = "YES" if sec.get("has_cccd") else "NO"

    # AUTHEN 2FA (Only app authenticator)
    authen_str = "YES" if sec.get("auth_2fa") else "NO"

    # FB
    fb_linked = sec.get("fb_linked", False)
    fb_str = "YES" if fb_linked else "DIE"

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



