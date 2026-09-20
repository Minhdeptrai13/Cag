"""
Core Database for Lien Quan Mobile (Arena of Valor - AOV)
Contains mappings for:
- Skin SSS: Thứ Nguyên Vệ Thần, SSS Hữu Hạn
- Skin Anime: Hợp tác bản quyền (SAO, Kimetsu, Bleach, Hunter x Hunter, JJK, AOT, OPM, Conan, Sailor Moon...)
- Skin SS: Chuẩn bậc [SS] và [SS Hữu Hạn] chính thức của game Liên Quân Mobile
- Skin Other: CHỈ lọc các skin có mác riêng, skin hiếm mở 1 lần (Evo Tiến Hóa, Idol WaVe, Tiệc Bãi Biển, Sự Kiện Đặc Biệt).
  Loại bỏ toàn bộ các skin thường (A, B, Quang Vinh, Thám Hiểm, Nạp Đầu, Mặc Định...).
"""

# ── Skin Bậc SSS (Thứ Nguyên Vệ Thần / SSS Hữu Hạn) ──────────────────────────
SKIN_SSS = {
    "10620": "Krixi Phù thủy thời không",
    "11101": "Violet Thứ nguyên vệ thần",
    "11107": "Violet Thứ nguyên vệ thần",
    "11119": "Violet Vọng nguyệt Long Cơ",
    "11607": "Butterfly Phượng Cửu Thiên",
    "12912": "Triệu Vân Minh Chung Long Đế",
    "13011": "Airi Bích hải thánh nữ",
    "13014": "Airi Thứ nguyên Vệ thần",
    "13015": "Airi Thứ nguyên Vệ thần",
    "13116": "Murad Tuyệt thế thần binh",
    "13118": "Murad Thánh Luân Kiếm Thánh",
    "13210": "Hayate Tu Di Thánh Đế",
    "13314": "Valhein Thứ nguyên vệ thần",
    "13315": "Valhein Thứ nguyên vệ thần",
    "13613": "Ilumia Lưỡng Nghi Long Hậu",
    "14111": "Lauriel Thứ nguyên vệ thần",
    "15009": "Nakroth thứ nguyên vệ thần",
    "15013": "Nakroth Quỷ thương liệp đế",
    "15015": "Nakroth Bạch diện chiến thương",
    "15217": "Điêu Thuyền Nhật Nguyệt Thánh Linh",
    "15412": "Yena Huyền cửu thiên",
    "15710": "Raz Bão vũ Cuồng lôi",
    "19007": "Tulen Chí tôn kiếm tiên",
    "19009": "Tulen Thần sứ ST.L-79",
    "19908": "Eland'orr Mộng Giới Thần Chủ",
    "50105": "Tel'Annas Thần sứ F.E.E-X1",
    "50108": "Tel'Annas Thứ nguyên vệ thần",
    "50112": "Tel'Annas Tân niên vệ thần",
    "50119": "Tel'Annas Lân Quang Thánh Diệu",
    "51015": "Liliana Ma Pháp Tối Thượng",
    "52011": "Veres Lưu ly Long mẫu",
    "52414": "Capheny Càn Nguyên Điện Chủ",
    "54307": "Aya Công chúa cầu vồng",
    "54804": "Bijan Kình thiên Long Kỵ",
}

# ── Skin Bậc SS Chuẩn Xác (Đúng bậc SS / SS Hữu Hạn trong game) ───────────────
SKIN_SS = {
    # Yorn
    "11202": "Yorn Thế Tử Nguyệt Tộc",
    "11204": "Yorn Long thần soái",
    "11205": "Yorn Long thần soái",
    # Tel'Annas
    "50111": "Tel'Annas Vũ khúc yêu hồ",
    "50117": "Tel'Annas Thiên Vũ Thần Long",
    # Hayate
    "13204": "Hayate Tử thần vũ trụ",
    # Raz
    "15704": "Raz Chiến thần Muay Thái",
    # Lauriel
    "14107": "Lauriel Tinh vân sứ",
    "14110": "Lauriel Phi thiên",
    "14117": "Lauriel Vũ khúc miêu ảnh",
    "14118": "Lauriel Thiên nữ Dạ Ưng",
    "14120": "Lauriel Mã Đằng Cửu Thế",
    # Tulen
    "19002": "Tulen Tân Thần Thiên Hà",
    "19012": "Tulen Tân Niên Vệ Thần",
    "19013": "Tulen Tiêu Dao Vũ Thần",
    "19016": "Tulen Thiên Cơ Bạch Trạch",
    # Arum
    "18702": "Arum Vũ khúc long hổ",
    "18704": "Arum Vũ khúc thần sứ",
    # Quillen
    "51802": "Quillen Đặc công mãng xà",
    "51808": "Quillen Nghịch Thiên Long Đế",
    "51814": "Quillen Thẩm Phán Trăng Khuyết",
    # Airi
    "13005": "Airi Kiemono",
    "13006": "Airi Bạch Kiemono",
    # Liliana
    "51003": "Liliana Nguyệt mị ly",
    "51005": "Liliana Tân nguyệt mị ly",
    "51010": "Liliana Lưu Thủy Thần Long",
    "51013": "Liliana Lưu Thủy Thần Long",
    # Violet
    "11113": "Violet Huyết Ma Thần",
    "11115": "Violet Thần long tỷ tỷ",
    "11118": "Violet Huyết ma thần",
    # Butterfly
    "11604": "Butterfly Nữ Quái Nổi Loạn",
    "11611": "Butterfly Thánh nữ khởi nguyên",
    "11612": "Butterfly Kim Ngư Thần Nữ",
    "11616": "Butterfly Thánh nữ khởi nguyên",
    # Maloch
    "12304": "Maloch Đại Tướng Robot",
    # Lữ Bố
    "12806": "Lữ Bố Tư lệnh Robot",
    # Murad
    "13109": "Murad Chí tôn thần kiếm",
    # Ngộ Không
    "16711": "Ngộ Không Thần Giáp Xích Diễm",
    "16712": "Ngộ Không Tề Thiên Võ Thánh",
    # Omen
    "50604": "Omen Đao phủ tận thế",
    "50605": "Omen Đao phủ tận thế",
    # Capheny
    "52404": "Capheny Kimono",
    # Veres
    "52007": "Veres Kimono",
    # Laville
    "53304": "Laville Xạ Thần Tinh Vệ",
    # Richter
    "51504": "Richter Kiếm thần Susanoo",
    # Điêu Thuyền
    "15211": "Điêu Thuyền Thất Tịch Tiên Tử",
    "15216": "Điêu Thuyền Tuế Hàn Đỗ Quyên",
    # Yena
    "15413": "Yena Trấn Yêu Thần Lộc",
    # Enzo
    "19509": "Enzo Sát Thần Bạch Hổ",
    # Elsu
    "19605": "Elsu Sứ Giả Tận Thế",
    "19609": "Elsu Trấn Thiên Phi Hồ",
    # Yue
    "54507": "Yue Hỗn Độn Thần Ma",
    # Teeri
    "54607": "Teeri Vân Y Cẩm Tú",
    # Bijan
    "54802": "Bijan Hoàng Kim Cơ Giáp",
    "54805": "Bijan Lữ Hành Thời Không",
    # Heino
    "56301": "Heino Nhật Ký Tình Yêu",
    # Erin
    "56703": "Erin Tình Yêu Cổ Tích",
    "56704": "Erin Huyễn Ảnh Mị Điệp",
    # Zata
    "51306": "Zata Chí Tôn Tà Phượng",
    # Allain
    "53703": "Allain Tuyết Sơn Song Kiếm",
    # Sinestrea
    "53513": "Sinestrea Định Vị Tuyệt Đối",
    # Aoi
    "53611": "Aoi Bách Thú Triều Long",
    # Charlotte
    "20601": "Charlotte Hexsword",
    # Billow
    "59901": "Billow Thiên Tướng Độ Ách",
    # Ryoma
    "16311": "Ryoma Maple Frost",
    # Helen
    "18408": "Helen Bé Hoa Xuân",
    # Aleister
    "15611": "Aleister HLV Bất Bại",
    # Dòng Siêu Việt (Bậc SS trong game)
    "16607": "Arthur Siêu Việt",
    "14609": "Zill Siêu Việt",
    "15705": "Raz Siêu Việt",
    "10704": "Zephys Siêu Việt",
    "16703": "Ngộ Không Siêu Việt",
    "16705": "Ngộ Không Siêu Việt 2.0",
    "13107": "Murad Siêu Việt 2.0",
    "13108": "Murad Siêu Việt 2.0",
    # Dòng Kỷ Nguyên Hổ Phách & Đặc Biệt Bậc SS
    "10714": "Zephys Kỷ Nguyên Hổ Phách",
    "50120": "Tel'annas Kỷ Nguyên Hổ Phách",
    "52113": "Florentino Kỷ Nguyên Hổ Phách",
    # Các Skin Bậc SS Hữu Hạn & Sự Kiện Lớn
    "10912": "Veera A.I Love you",
    "10915": "Veera Thất Sát - Thượng Sinh",
    "11212": "Yorn Vệ Binh ngân hà",
    "11614": "Butterfly Kim ngư thần nữ",
    "11619": "Butterfly Rockgirl Siêu Đẳng",
    "11808": "Alice Quân Nhạc Athanor",
    "12008": "Mina Linh Xà yêu vũ",
    "12606": "Arduin Bạch vệ chiến giáp",
    "12608": "Arduin Ngạo Hổ Hàn Đao",
    "12812": "Lữ Bố Cửu Thiên Lôi Thần",
    "12907": "Triệu Vân Kỵ sĩ tận thế",
    "12913": "Triệu Vân Chiến Thần Vô Song",
    "13212": "Hayate Thống Soái Dạ Ưng",
    "13313": "Valhein Đệ nhất thần thám",
    "13316": "Valhein Mã Hành Vạn Lý",
    "13609": "Ilumia Khải Huyền Thiên Hậu",
    "13612": "Ilumia Nộ hải Thiên ngư",
    "13705": "Paine Tử xà Bá tước",
    "14104": "Lauriel Thánh quang sứ",
    "14109": "Lauriel thiên sứ công nghệ",
    "14206": "Natalya Nghiệp Hoả Yêu Hậu",
    "14213": "Natalya Nguyệt Ảnh Kiếm Tiên",
    "15007": "Nakroth Lôi Quang Sứ",
    "15903": "Dolia Nhật Ký Tình Yêu",
    "15905": "Dolia Mã Khởi Thiên Ca",
    "17106": "Cresht Bách Tướng Lão Tam",
    "17309": "Fennik Phong Tranh Thám Xuân",
    "17408": "Stuart Siêu Trùm phản diện",
    "19006": "Tulen Tân thần hoàng kim",
    "19010": "Tulen Hoả thần long tộc",
    "19109": "Rouie Lữ hành Thời không",
    "50613": "Omen Liệt Hỏa Thiên Cang",
    "51004": "Liliana Tiểu thơ anh đào",
    "51208": "Rourke Bách Tướng Lão Đại",
    "52014": "Veres Idol Giáng Sinh",
    "52108": "Florentino Bá vương Âm nhạc",
    "52709": "Sephera Bách nhạn ngân linh",
    "52710": "Sephera Nova Stardust",
    "52908": "Volkath Ma Ảnh Thần Đao",
    "53309": "Laville Vệ binh giáng sinh",
    "53311": "Laville Thợ Săn Truy Ảnh",
    "59802": "Bolt Baron Thiên Phủ",
    "59902": "Billow T-Rex Bất Bại",
}

# ── Skin Anime / Hợp Tác Bản Quyền ─────────────────────────────────────────
SKIN_ANIME = {
    # Sword Art Online (SAO)
    "53701": "Allain Kirito Hắc kiếm sĩ",
    "53702": "Allain Kirito",
    "11610": "Butterfly Asuna Tia chớp",
    "11611": "Butterfly Stacia",
    # Kimetsu no Yaiba (Demon Slayer)
    "54402": "Yan Tanjiro Kamado",
    "53107": "Keera Nezuko Kamado",
    "10708": "Zephys Inosuke Hashibira",
    "13112": "Murad Zenitsu Agatsuma",
    # Bleach
    "12808": "Lữ Bố Ichigo Kurosaki",
    "13111": "Murad Byakuya Kuchiki",
    "54002": "Bright Toshiro Hitsugaya",
    # Hunter x Hunter
    "15012": "Nakroth Killua",
    "19508": "Enzo Kurapika",
    "15711": "Raz Gon",
    "52107": "Florentino Hisoka",
    # Attack on Titan (AOT)
    "15016": "Nakroth Levi",
    "53612": "Aoi Mikasa",
    "52810": "Qi Annie Leonhart",
    "17108": "Cresht Eren Jaegar",
    # Jujutsu Kaisen (JJK)
    "19015": "Tulen Satoru Gojo",
    "11120": "Violet Nobara Kugisaki",
    "13706": "Paine Megumi Fushiguro",
    "59702": "Biron Yuji Itadori",
    "50118": "Tel'Annas Jujutsu Sorcerer",
    # One Punch Man
    "52204": "Errol Genos",
    # Sailor Moon
    "15212": "Eternal Sailor Moon",
    "11812": "Alice - Eternal Sailor Chibi Moon",
    "19906": "Eland'orr-Tuxedo",
    # Thám Tử Lừng Danh Conan
    "11215": "Yorn Conan Edogawa",
    "13213": "Hayate Siêu đạo chích Kid",
    # Tensei Shitara Slime Datta Ken
    "53806": "Iggy Rimuru Tempest",
    "52809": "Qi Milim Nava",
    "14412": "Taara Shion",
    # Sanrio & Bản Quyền Khác
    "54309": "Aya Cinnamoroll's Dream",
    "10916": "Veera My Melody's Love",
    "14214": "Natalya Kuromi's Heart",
    "16612": "Arthur Pompompurin's Oath",
    "16307": "Ryoma Ultraman",
    "52104": "Florentino SEVEN",
    "52407": "Capheny Harley Quinn",
}

# ── Skin Other: CHỈ GIỮ CÁC DÒNG CÓ MÁC RIÊNG & HIẾM (Evo chuẩn, WaVe, Tiệc Bãi Biển, Sự Kiện Hiếm) ──
# (Tuyệt đối không lưu skin thường A, B, Quang Vinh, Noel thường, Thám Hiểm...)
SKIN_OTHER = {
    # ── 1. Dòng EVO Tiến Hóa CHUẨN CỦA LIÊN QUÂN ──────────────────────────────
    # Chỉ có duy nhất 5 con Tiến Hóa (Evo):
    # - Nakroth Siêu Việt
    # - Ngộ Không Nhóc Tì Bá Đạo
    # - Butterfly Bình Minh Tận Thế
    # - Valhein Xạ Thần Kagutsuchi
    # - Murad Siêu Việt
    "15003": "Nakroth Siêu Việt (Evo)",
    "15004": "Nakroth Siêu Việt (Evo)",
    "16704": "Ngộ Không Nhóc Tì Bá Đạo (Evo)",
    "11608": "Butterfly Bình Minh Tận Thế (Evo)",
    "13312": "Valhein Xạ Thần Kagutsuchi (Evo)",
    "13104": "Murad Siêu Việt (Evo)",

    # ── 2. Dòng WaVe (Nhóm Idol WaVe) ─────────────────────────────────────────
    "51008": "Liliana WaVe",
    "51009": "Liliana WaVe",
    "15204": "Điêu Thuyền WaVe",
    "15409": "Yena WaVe",
    "53503": "Sinestrea Wave",

    # ── 3. Dòng Tiệc Bãi Biển (Beach Party Hữu Hạn) ───────────────────────────
    "11105": "Violet Tiệc bãi biển",
    "11106": "Violet Tiệc bãi biển",
    "10801": "Gildur Tiệc Bãi Biển",
    "10802": "Gildur Tiệc Bãi Biển",
    "14403": "Taara Tiệc bãi biển",
    "14404": "Taara Tiệc bãi biển",
    "53104": "Keera Tiệc bãi biển",
    "10603": "Krixi Tiệc Bãi Biển",
    "13008": "Airi Tiệc bãi biển",
    "12801": "Lữ Bố Tiệc Bãi Biển",
    "12804": "Lữ Bố Tiệc Bãi Biển",
    "14108": "Lauriel Tiệc bãi biển",
    "12011": "Mina Tiệc bãi biển",
    "15202": "Điêu Thuyền Tiệc bãi biển",
    "17506": "Grakk Tiệc bãi biển",
    "50110": "Astrid Tiệc bãi biển",
    "50121": "Tel'annas Tiệc bãi biển",
    "51904": "Annette Tiệc bãi biển",
    "53204": "Thorne Tiệc bãi biển",
    "53306": "Laville Tiệc bãi biển",
    "53603": "Aoi Tiệc bãi biển",

    # ── 4. Skin Hiếm Có Mác Riêng / Mở Bán 1 Lần / S+ Hữu Hạn Độc Quyền ───────
    "11109": "Violet Vợ người ta",
    "11110": "Violet Vợ người ta",
    "16709": "Ngộ Không Tân niên Võ Thần",
    "16710": "Ngộ Không Tân niên Võ Thần",
    "13306": "Valhein Số 7 thần sầu",
    "13302": "Valhein Vũ khí tối thượng",
    "53708": "Allain Lân sư Vũ thần",
    "11603": "Butterfly Quận chúa đế chế",
    "12301": "Maloch Ác ma địa ngục",
    "10803": "Gildur Bác học thiên tài",
    "14602": "Zill Dung nham",
    "51901": "Amily Đặc công Nhện đỏ",
    "10902": "Veera Góa phụ giả kim",
    "11102": "Violet Đặc dị",
    "53302": "Laville Tay súng diệt thần",
    "51001": "Liliana Thủy thủ hồ ly",
    "52702": "Sephera Chiêm tinh gia",
    "50602": "Omen Ám tử đao",
    "17502": "Grakk Thần ẩm thực",
    "17508": "Grakk Mèo Thần tài",
    "12003": "Mina Tiểu thư đoạt hồn",
    "18605": "Zuka Phát tài",
    "52804": "Qi Blogger Ẩm thực",
    "12906": "Triệu Vân Thần tài",
    "16304": "Ryoma Samurai huyền thoại",
}


def skin_hero_id(skin_id) -> str:
    """Extract hero id from skin item id (hero*100 + variant)."""
    sid = str(skin_id).strip()
    if not sid.isdigit():
        return sid
    n = int(sid)
    if n >= 100:
        return str(n // 100)
    return sid


def classify_skins(owned_ids: list) -> dict:
    """
    Classify owned skin IDs into SSS, Anime, SS, and Other tiers.
    Strict priority: SSS > Anime > SS > Other.
    Only curated rare / marked skins are categorized into Other.
    Generic normal skins are omitted from Other list.
    """
    sss_list, anime_list, ss_list, other_list = [], [], [], []
    hero_ids = set()
    for item_id in (owned_ids or []):
        sid = str(item_id).strip()
        if not sid:
            continue
        if sid in SKIN_SSS:
            sss_list.append(SKIN_SSS[sid])
        elif sid in SKIN_ANIME:
            anime_list.append(SKIN_ANIME[sid])
        elif sid in SKIN_SS:
            ss_list.append(SKIN_SS[sid])
        elif sid in SKIN_OTHER:
            other_list.append(SKIN_OTHER[sid])
        hero_ids.add(skin_hero_id(sid))

    return {
        "total_skins": len(owned_ids or []),
        "total_champs": len(hero_ids),
        "sss": len(sss_list),
        "sss_list": sss_list,
        "anime": len(anime_list),
        "anime_list": anime_list,
        "ss": len(ss_list),
        "ss_list": ss_list,
        "other": len(other_list),
        "other_list": other_list,
    }


def translate_aov_rank(rank_str: str) -> str:
    """Normalize rank name to Vietnamese."""
    if not rank_str:
        return "Chưa Đấu Hạng"
    s = str(rank_str).lower()
    if "đồng" in s or "bronze" in s or "บรอนซ์" in s or "青銅" in s:
        return "Đồng"
    if "bạc" in s or "silver" in s or "ซิลเวอร์" in s or "白銀" in s:
        return "Bạc"
    if "vàng" in s or "gold" in s or "โกลด์" in s or "黃金" in s:
        return "Vàng"
    if "bạch kim" in s or "platinum" in s or "แพลทินัม" in s or "鉑金" in s:
        return "Bạch Kim"
    if "kim cương" in s or "diamond" in s or "ไดมอนด์" in s or "鑽石" in s:
        return "Kim Cương"
    if "tinh anh" in s or "commander" in s or "คอมมานเดอร์" in s or "星耀" in s:
        return "Tinh Anh"
    if "thách đấu" in s or "glorious ruler" in s or "กลอเรียสรูเลอร์" in s:
        return "Thách Đấu"
    if "chiến tướng" in s or "supreme conqueror" in s or "ซูพรีมคอนเควอร์เรอร์" in s or "璀璨傳說" in s:
        return "Chiến Tướng"
    if "cao thủ" in s or "conqueror" in s or "master" in s or "คอนเควอร์เรอร์" in s or "戰場傳說" in s:
        return "Cao Thủ"
    return rank_str
