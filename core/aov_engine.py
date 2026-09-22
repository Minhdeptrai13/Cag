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
from core.aov_database import translate_aov_rank

def _security_flag(value) -> bool:
    """Normalize the mixed boolean/int/string flags returned by Garena."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().upper() in {"1", "TRUE", "YES", "Y", "ON", "LINKED", "CONNECTED"}
    return False


def _security_text(value) -> str:
    return str(value or "").strip()


def _has_masked_value(value) -> bool:
    """A masked value such as phu****@gmail.com or 33*****91 is still bound."""
    text = _security_text(value)
    if not text:
        return False
    normalized = text.lower()
    if normalized in {"trắng", "trang", "none", "null", "n/a", "no", "false", "0", "không"}:
        return False
    return bool(text.replace("*", "").strip())


def _build_security(raw: dict) -> dict:
    """Build one canonical security snapshot from Check1's flat result."""
    phone = (
        _security_text(raw.get("aov_prefill_mobile"))
        or _security_text(raw.get("fcmobile_prefill_mobile"))
        or _security_text(raw.get("masked_phone"))
    )
    email = _security_text(raw.get("masked_email"))
    idcard = _security_text(raw.get("idcard"))
    fb_uid = _security_text(raw.get("fb_uid") or raw.get("fb_uid_login"))
    fb_account = _security_text(raw.get("fb_account_name"))
    has_phone = _security_flag(raw.get("mobile_bound")) or _has_masked_value(phone)
    has_email = _security_flag(raw.get("email_verified")) or _security_flag(raw.get("email_v")) or _has_masked_value(email)
    has_cccd = bool(idcard.replace("*", "").strip())
    auth_2fa = _security_flag(raw.get("authenticator_enable")) or _security_flag(raw.get("two_step_verify"))
    # The reference checker may expose a truthy string such as "0" from the
    # account-init endpoint. Require actual FB identity data before marking
    # the account as linked.
    fb_linked = bool(fb_uid) or (
        _security_flag(raw.get("fb_linked")) and _has_masked_value(fb_account)
    )

    return {
        "has_phone": has_phone,
        "mobile_bound": _security_flag(raw.get("mobile_bound")),
        "masked_phone": phone,
        "masked_email": email,
        "email_verified": _security_flag(raw.get("email_verified")),
        "email_v": has_email,
        "has_cccd": has_cccd,
        "idcard": idcard,
        "fb_linked": fb_linked,
        "fb_uid": fb_uid,
        "auth_2fa": auth_2fa,
        "banned": _security_flag(raw.get("aov_banned")),
        "suspicious": _security_flag(raw.get("suspicious")),
    }


def _raw_security_snapshot(raw: dict) -> dict:
    """Keep the original security values without exposing login credentials."""
    fields = (
        "aov_prefill_mobile",
        "fcmobile_prefill_mobile",
        "masked_phone",
        "mobile_bound",
        "masked_email",
        "email_verified",
        "email_v",
        "idcard",
        "authenticator_enable",
        "two_step_verify",
        "fb_linked",
        "fb_uid",
        "fb_uid_login",
        "fb_account_name",
        "aov_banned",
        "suspicious",
    )
    return {key: raw[key] for key in fields if key in raw}


def _derive_security_status(raw: dict, security: dict) -> str:
    """Match Check1's security-based classification without trusting string truthiness."""
    parts = []
    if security["has_phone"]:
        parts.append("SĐT")
    if security["email_v"]:
        parts.append("Mail")
    if security["fb_linked"]:
        parts.append("FB")
    if security["has_cccd"]:
        parts.append("CCCD")
    if security["auth_2fa"]:
        parts.append("2FA")
    if _security_flag(raw.get("password_set")):
        parts.append("Pass")

    if not parts:
        status = "Acc Trắng"
    elif len(parts) >= 4:
        status = "Full Info"
    else:
        status = "Acc Dính " + " + ".join(parts)

    suffix = []
    if _security_flag(raw.get("aov_banned")):
        suffix.append("BAN")
    try:
        if int(raw.get("suspicious", 0) or 0):
            suffix.append("Suspicious")
    except (TypeError, ValueError):
        pass
    return f"{status} [{' + '.join(suffix)}]" if suffix else status


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
    """Derive account condition using the normalized Check1 security fields."""
    if not raw or raw.get("status") != "HIT":
        return "Chưa xác định"
    return _derive_security_status(raw, _build_security(raw))


def derive_tinh_trang(raw: dict) -> str:
    """Public status helper; keep CLI, API, and web on the same security rules."""
    return derive_accurate_tinh_trang(raw)


def check_account(account: str, password: str, proxy=None, timeout: int = 10) -> dict:
    """
    Main checking method.
    Returns a unified result dictionary with login status, AOV profile, skins, rank, and security info.
    """
    account = account.strip()
    password = password.strip()

    raw = check1_login(account, password, timeout=timeout, fetch_info=True, proxy=proxy)
    status = raw.get("status", "ERROR")

    security = _build_security(raw)
    phone_display = security["masked_phone"]
    mobile_bound = security["mobile_bound"]
    has_phone = security["has_phone"]
    if not phone_display and mobile_bound:
        phone_display = "ĐÃ LIÊN KẾT"

    tinh_trang = _derive_security_status(raw, security) if status == "HIT" else "Chưa xác định"
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
            "masked_email": security["masked_email"],
            "email_verified": security["email_verified"],
            "email_v": security["email_v"],
            "has_cccd": security["has_cccd"],
            "idcard": security["idcard"],
            "fb_linked": security["fb_linked"],
            "fb_uid": security["fb_uid"],
            "auth_2fa": security["auth_2fa"],
            "banned": security["banned"],
            "suspicious": security["suspicious"],
            "raw": _raw_security_snapshot(raw),
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
    result["email_verified"] = result["security"]["email_verified"]
    result["email_v"] = result["security"]["email_v"]
    result["has_cccd"] = result["security"]["has_cccd"]
    result["idcard"] = result["security"]["idcard"]
    result["fb_linked"] = result["security"]["fb_linked"]
    result["fb_uid"] = result["security"]["fb_uid"]
    result["auth_2fa"] = result["security"]["auth_2fa"]
    result["aov_banned"] = raw.get("aov_banned", "NO")
    result["raw_security"] = result["security"]["raw"]
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
    ban = "BAN" if _security_flag(aov.get("banned")) else "OK"

    # Email
    masked_email = (sec.get("masked_email") or "").strip()
    if not masked_email or masked_email.lower() in {"trắng", "trang"}:
        email_str = "NO [CHƯA LIÊN KẾT]"
    else:
        # Check1 treats the masked address as a linked email even when the
        # separate verification flag is unavailable.
        email_str = f"YES [{masked_email}]"

    # SDT
    has_phone = bool(sec.get("has_phone")) or bool(sec.get("mobile_bound"))
    masked_phone = (sec.get("masked_phone") or "").strip()
    if masked_phone and masked_phone.lower() not in {"trắng", "trang"}:
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
        fb_str = "NO"

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



