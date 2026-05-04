"""
中国市场汽车品牌数据库
- 50+主流品牌，含中英文名、常见别名
- 热门车型系列
- 品牌折旧系数（基于公开数据估算）
- 模糊匹配工具
"""

from difflib import get_close_matches

# 品牌数据: { normalized_key: { name_cn, name_en, aliases, depreciation_rate } }
# depreciation_rate: 年折旧系数，越低越保值 (第1年折旧斜率参考)
BRANDS = {
    "toyota": {
        "name_cn": "丰田", "name_en": "Toyota",
        "aliases": ["丰田", "toyota", "豐田", "头又大", "ft"],
        "depreciation_rate": 0.88,  # 保值率高
        "country": "日本", "tier": 1
    },
    "honda": {
        "name_cn": "本田", "name_en": "Honda",
        "aliases": ["本田", "honda", "轟達", "bt"],
        "depreciation_rate": 0.87, "country": "日本", "tier": 1
    },
    "nissan": {
        "name_cn": "日产", "name_en": "Nissan",
        "aliases": ["日产", "nissan", "日產", "尼桑", "nisan", "rc"],
        "depreciation_rate": 0.83, "country": "日本", "tier": 1
    },
    "volkswagen": {
        "name_cn": "大众", "name_en": "Volkswagen",
        "aliases": ["大众", "volkswagen", "大眾", "vw", "dz", "大众汽车"],
        "depreciation_rate": 0.84, "country": "德国", "tier": 1
    },
    "bmw": {
        "name_cn": "宝马", "name_en": "BMW",
        "aliases": ["宝马", "bmw", "寶馬", "寳馬", "bm", "别摸我", "bimmer"],
        "depreciation_rate": 0.82, "country": "德国", "tier": 1
    },
    "mercedes-benz": {
        "name_cn": "奔驰", "name_en": "Mercedes-Benz",
        "aliases": ["奔驰", "mercedes", "benz", "梅赛德斯", "梅奔", "bc", "大奔", "mercedes-benz", "奔馳"],
        "depreciation_rate": 0.81, "country": "德国", "tier": 1
    },
    "audi": {
        "name_cn": "奥迪", "name_en": "Audi",
        "aliases": ["奥迪", "audi", "奧迪", "ad", "四个圈"],
        "depreciation_rate": 0.80, "country": "德国", "tier": 1
    },
    "porsche": {
        "name_cn": "保时捷", "name_en": "Porsche",
        "aliases": ["保时捷", "porsche", "保時捷", "破鞋", "bsj"],
        "depreciation_rate": 0.85, "country": "德国", "tier": 2
    },
    "lexus": {
        "name_cn": "雷克萨斯", "name_en": "Lexus",
        "aliases": ["雷克萨斯", "lexus", "凌志", "淩志", "lkss", "雷车"],
        "depreciation_rate": 0.89, "country": "日本", "tier": 1
    },
    "mazda": {
        "name_cn": "马自达", "name_en": "Mazda",
        "aliases": ["马自达", "mazda", "馬自達", "mzd"],
        "depreciation_rate": 0.83, "country": "日本", "tier": 1
    },
    "subaru": {
        "name_cn": "斯巴鲁", "name_en": "Subaru",
        "aliases": ["斯巴鲁", "subaru", "速霸陸", "sbl", "486"],
        "depreciation_rate": 0.82, "country": "日本", "tier": 2
    },
    "mitsubishi": {
        "name_cn": "三菱", "name_en": "Mitsubishi",
        "aliases": ["三菱", "mitsubishi", "sl"],
        "depreciation_rate": 0.80, "country": "日本", "tier": 2
    },
    "buick": {
        "name_cn": "别克", "name_en": "Buick",
        "aliases": ["别克", "buick", "別克", "bk"],
        "depreciation_rate": 0.82, "country": "美国", "tier": 1
    },
    "chevrolet": {
        "name_cn": "雪佛兰", "name_en": "Chevrolet",
        "aliases": ["雪佛兰", "chevrolet", "雪佛蘭", "xfl", "chevy"],
        "depreciation_rate": 0.79, "country": "美国", "tier": 1
    },
    "ford": {
        "name_cn": "福特", "name_en": "Ford",
        "aliases": ["福特", "ford", "ft"],
        "depreciation_rate": 0.80, "country": "美国", "tier": 1
    },
    "cadillac": {
        "name_cn": "凯迪拉克", "name_en": "Cadillac",
        "aliases": ["凯迪拉克", "cadillac", "凱迪拉克", "kdlk"],
        "depreciation_rate": 0.78, "country": "美国", "tier": 2
    },
    "tesla": {
        "name_cn": "特斯拉", "name_en": "Tesla",
        "aliases": ["特斯拉", "tesla", "tsl"],
        "depreciation_rate": 0.86, "country": "美国", "tier": 2
    },
    "byd": {
        "name_cn": "比亚迪", "name_en": "BYD",
        "aliases": ["比亚迪", "byd", "比亞迪", "byd王朝", "byd海洋"],
        "depreciation_rate": 0.75, "country": "中国", "tier": 1
    },
    "geely": {
        "name_cn": "吉利", "name_en": "Geely",
        "aliases": ["吉利", "geely", "jl", "吉利汽车"],
        "depreciation_rate": 0.72, "country": "中国", "tier": 1
    },
    "changan": {
        "name_cn": "长安", "name_en": "Changan",
        "aliases": ["长安", "changan", "ca", "长安汽车", "長安"],
        "depreciation_rate": 0.73, "country": "中国", "tier": 1
    },
    "haval": {
        "name_cn": "哈弗", "name_en": "Haval",
        "aliases": ["哈弗", "haval", "hf", "长城哈弗"],
        "depreciation_rate": 0.74, "country": "中国", "tier": 1
    },
    "great-wall": {
        "name_cn": "长城", "name_en": "Great Wall",
        "aliases": ["长城", "great wall", "greatwall", "cc", "长城汽车", "gwm"],
        "depreciation_rate": 0.73, "country": "中国", "tier": 1
    },
    "nio": {
        "name_cn": "蔚来", "name_en": "NIO",
        "aliases": ["蔚来", "nio", "wl", "未来", "蔚來"],
        "depreciation_rate": 0.72, "country": "中国", "tier": 2
    },
    "xpeng": {
        "name_cn": "小鹏", "name_en": "XPeng",
        "aliases": ["小鹏", "xpeng", "xmotors", "xiaopeng", "xp"],
        "depreciation_rate": 0.70, "country": "中国", "tier": 2
    },
    "li-auto": {
        "name_cn": "理想", "name_en": "Li Auto",
        "aliases": ["理想", "li auto", "lixiang", "lx", "理想汽车"],
        "depreciation_rate": 0.74, "country": "中国", "tier": 2
    },
    "hongqi": {
        "name_cn": "红旗", "name_en": "Hongqi",
        "aliases": ["红旗", "hongqi", "hq", "红旗汽车"],
        "depreciation_rate": 0.76, "country": "中国", "tier": 2
    },
    "chery": {
        "name_cn": "奇瑞", "name_en": "Chery",
        "aliases": ["奇瑞", "chery", "chery", "qr"],
        "depreciation_rate": 0.72, "country": "中国", "tier": 1
    },
    "roewe": {
        "name_cn": "荣威", "name_en": "Roewe",
        "aliases": ["荣威", "roewe", "rw", "榮威"],
        "depreciation_rate": 0.71, "country": "中国", "tier": 2
    },
    "lynk-co": {
        "name_cn": "领克", "name_en": "Lynk & Co",
        "aliases": ["领克", "lynk", "lynkco", "lynk & co", "lk", "領克"],
        "depreciation_rate": 0.76, "country": "中国", "tier": 2
    },
    "hyundai": {
        "name_cn": "现代", "name_en": "Hyundai",
        "aliases": ["现代", "hyundai", "現代", "xd", "韩国现代"],
        "depreciation_rate": 0.77, "country": "韩国", "tier": 1
    },
    "kia": {
        "name_cn": "起亚", "name_en": "Kia",
        "aliases": ["起亚", "kia", "起亞", "qy"],
        "depreciation_rate": 0.75, "country": "韩国", "tier": 2
    },
    "peugeot": {
        "name_cn": "标致", "name_en": "Peugeot",
        "aliases": ["标致", "peugeot", "標緻", "bz", "法国标致"],
        "depreciation_rate": 0.70, "country": "法国", "tier": 2
    },
    "citroen": {
        "name_cn": "雪铁龙", "name_en": "Citroen",
        "aliases": ["雪铁龙", "citroen", "雪鐵龍", "xtl"],
        "depreciation_rate": 0.69, "country": "法国", "tier": 2
    },
    "volvo": {
        "name_cn": "沃尔沃", "name_en": "Volvo",
        "aliases": ["沃尔沃", "volvo", "沃爾沃", "富豪", "wew"],
        "depreciation_rate": 0.79, "country": "瑞典", "tier": 2
    },
    "land-rover": {
        "name_cn": "路虎", "name_en": "Land Rover",
        "aliases": ["路虎", "land rover", "landrover", "lh", "路虎揽胜"],
        "depreciation_rate": 0.80, "country": "英国", "tier": 2
    },
    "jaguar": {
        "name_cn": "捷豹", "name_en": "Jaguar",
        "aliases": ["捷豹", "jaguar", "jb", "美洲豹"],
        "depreciation_rate": 0.70, "country": "英国", "tier": 2
    },
    "mini": {
        "name_cn": "MINI", "name_en": "MINI",
        "aliases": ["mini", "宝马mini", "迷你"],
        "depreciation_rate": 0.82, "country": "英国", "tier": 2
    },
    "jeep": {
        "name_cn": "Jeep", "name_en": "Jeep",
        "aliases": ["jeep", "吉普", "jp"],
        "depreciation_rate": 0.79, "country": "美国", "tier": 2
    },
    "dodge": {
        "name_cn": "道奇", "name_en": "Dodge",
        "aliases": ["道奇", "dodge", "dq"],
        "depreciation_rate": 0.72, "country": "美国", "tier": 3
    },
    "skoda": {
        "name_cn": "斯柯达", "name_en": "Skoda",
        "aliases": ["斯柯达", "skoda", "skd", "斯科达"],
        "depreciation_rate": 0.76, "country": "捷克", "tier": 2
    },
    "infiniti": {
        "name_cn": "英菲尼迪", "name_en": "Infiniti",
        "aliases": ["英菲尼迪", "infiniti", "yfnd", "无限"],
        "depreciation_rate": 0.75, "country": "日本", "tier": 2
    },
    "acura": {
        "name_cn": "讴歌", "name_en": "Acura",
        "aliases": ["讴歌", "acura", "og", "歐歌"],
        "depreciation_rate": 0.77, "country": "日本", "tier": 2
    },
    "lincoln": {
        "name_cn": "林肯", "name_en": "Lincoln",
        "aliases": ["林肯", "lincoln", "lk", "林肯汽车"],
        "depreciation_rate": 0.76, "country": "美国", "tier": 2
    },
    "maserati": {
        "name_cn": "玛莎拉蒂", "name_en": "Maserati",
        "aliases": ["玛莎拉蒂", "maserati", "msld", "玛莎"],
        "depreciation_rate": 0.65, "country": "意大利", "tier": 3
    },
    "ferrari": {
        "name_cn": "法拉利", "name_en": "Ferrari",
        "aliases": ["法拉利", "ferrari", "fll"],
        "depreciation_rate": 0.75, "country": "意大利", "tier": 3
    },
    "lamborghini": {
        "name_cn": "兰博基尼", "name_en": "Lamborghini",
        "aliases": ["兰博基尼", "lamborghini", "lbjn", "兰博", "牛"],
        "depreciation_rate": 0.74, "country": "意大利", "tier": 3
    },
    "rolls-royce": {
        "name_cn": "劳斯莱斯", "name_en": "Rolls-Royce",
        "aliases": ["劳斯莱斯", "rolls royce", "rolls-royce", "rr", "lsls", "劳斯"],
        "depreciation_rate": 0.78, "country": "英国", "tier": 3
    },
    "bentley": {
        "name_cn": "宾利", "name_en": "Bentley",
        "aliases": ["宾利", "bentley", "bl", "賓利"],
        "depreciation_rate": 0.76, "country": "英国", "tier": 3
    },
    "gac": {
        "name_cn": "广汽传祺", "name_en": "GAC Trumpchi",
        "aliases": ["广汽", "广汽传祺", "gac", "trumpchi", "传祺", "cq"],
        "depreciation_rate": 0.72, "country": "中国", "tier": 1
    },
    "wuling": {
        "name_cn": "五菱", "name_en": "Wuling",
        "aliases": ["五菱", "wuling", "wl", "五菱宏光"],
        "depreciation_rate": 0.78, "country": "中国", "tier": 1
    },
    "saic": {
        "name_cn": "名爵/MG", "name_en": "MG",
        "aliases": ["名爵", "mg", "mingjue", "mj", "上汽mg"],
        "depreciation_rate": 0.71, "country": "中国", "tier": 2
    },
    "jetour": {
        "name_cn": "捷途", "name_en": "Jetour",
        "aliases": ["捷途", "jetour", "jt"],
        "depreciation_rate": 0.72, "country": "中国", "tier": 2
    },
    "tank": {
        "name_cn": "坦克", "name_en": "Tank",
        "aliases": ["坦克", "tank", "tk", "长城坦克"],
        "depreciation_rate": 0.78, "country": "中国", "tier": 2
    },
    # === 2024数据集新增品牌 ===
    "aito": {
        "name_cn": "AITO问界", "name_en": "AITO",
        "aliases": ["aito", "AITO", "问界", "aito问界", "华为问界", "赛力斯问界"],
        "depreciation_rate": 0.74, "country": "中国", "tier": 2
    },
    "leapmotor": {
        "name_cn": "零跑", "name_en": "Leapmotor",
        "aliases": ["零跑", "leapmotor", "零跑汽车"],
        "depreciation_rate": 0.70, "country": "中国", "tier": 2
    },
    "nio": {
        "name_cn": "蔚来", "name_en": "NIO",
        "aliases": ["蔚来", "nio", "wl", "未来", "蔚來"],
        "depreciation_rate": 0.72, "country": "中国", "tier": 2
    },
    "nevo": {
        "name_cn": "哪吒", "name_en": "Nevo",
        "aliases": ["哪吒", "nevo", "nezha", "哪吒汽车"],
        "depreciation_rate": 0.68, "country": "中国", "tier": 2
    },
    "lantu": {
        "name_cn": "岚图", "name_en": "Lantu",
        "aliases": ["岚图", "lantu", "岚图汽车", "东风岚图"],
        "depreciation_rate": 0.72, "country": "中国", "tier": 2
    },
    "zeekr": {
        "name_cn": "极氪", "name_en": "Zeekr",
        "aliases": ["极氪", "zeekr", "极氪汽车", "吉利极氪"],
        "depreciation_rate": 0.73, "country": "中国", "tier": 2
    },
    "hiphi": {
        "name_cn": "高合", "name_en": "HiPhi",
        "aliases": ["高合", "hiphi", "高合汽车"],
        "depreciation_rate": 0.65, "country": "中国", "tier": 2
    },
    "avatr": {
        "name_cn": "阿维塔", "name_en": "Avatr",
        "aliases": ["阿维塔", "avatr", "阿维塔科技"],
        "depreciation_rate": 0.71, "country": "中国", "tier": 2
    },
    "im-motors": {
        "name_cn": "智己", "name_en": "IM Motors",
        "aliases": ["智己", "im motors", "智己汽车"],
        "depreciation_rate": 0.70, "country": "中国", "tier": 2
    },
    "denza": {
        "name_cn": "腾势", "name_en": "Denza",
        "aliases": ["腾势", "denza", "比亚迪腾势", "腾势汽车"],
        "depreciation_rate": 0.73, "country": "中国", "tier": 2
    },
    "deepal": {
        "name_cn": "深蓝", "name_en": "Deepal",
        "aliases": ["深蓝", "deepal", "长安深蓝", "深蓝汽车"],
        "depreciation_rate": 0.71, "country": "中国", "tier": 2
    },
    "voyah": {
        "name_cn": "岚图", "name_en": "Voyah",
        "aliases": ["voyah", "岚图"],
        "depreciation_rate": 0.72, "country": "中国", "tier": 2
    },
    "baic": {
        "name_cn": "北京汽车", "name_en": "BAIC",
        "aliases": ["北京", "baic", "北汽", "北京汽车"],
        "depreciation_rate": 0.70, "country": "中国", "tier": 2
    },
    "jac": {
        "name_cn": "江淮", "name_en": "JAC",
        "aliases": ["江淮", "jac", "江淮汽车", "江汽"],
        "depreciation_rate": 0.68, "country": "中国", "tier": 2
    },
    "soueast": {
        "name_cn": "东南", "name_en": "Soueast",
        "aliases": ["东南", "soueast", "东南汽车"],
        "depreciation_rate": 0.67, "country": "中国", "tier": 2
    },
    "smart": {
        "name_cn": "Smart", "name_en": "Smart",
        "aliases": ["smart", "精灵", "奔驰smart"],
        "depreciation_rate": 0.75, "country": "德国", "tier": 2
    },
    "polestar": {
        "name_cn": "极星", "name_en": "Polestar",
        "aliases": ["polestar", "极星", "polestar极星", "沃尔沃极星"],
        "depreciation_rate": 0.68, "country": "瑞典", "tier": 2
    },
    "swm": {
        "name_cn": "SWM斯威", "name_en": "SWM",
        "aliases": ["swm", "斯威", "swm斯威"],
        "depreciation_rate": 0.65, "country": "中国", "tier": 2
    },
    "maxus": {
        "name_cn": "大通", "name_en": "MAXUS",
        "aliases": ["大通", "maxus", "上汽大通", "上汽maxus"],
        "depreciation_rate": 0.70, "country": "中国", "tier": 2
    },
    "jetta-brand": {
        "name_cn": "捷达", "name_en": "Jetta",
        "aliases": ["捷达", "jetta", "大众捷达"],
        "depreciation_rate": 0.74, "country": "中国", "tier": 2
    },
    "roewe": {
        "name_cn": "荣威", "name_en": "Roewe",
        "aliases": ["荣威", "roewe", "荣威汽车", "上汽荣威"],
        "depreciation_rate": 0.71, "country": "中国", "tier": 2
    },
    "wey": {
        "name_cn": "魏牌", "name_en": "WEY",
        "aliases": ["魏牌", "wey", "魏", "wey牌"],
        "depreciation_rate": 0.72, "country": "中国", "tier": 2
    },
    "changan-kaicheng": {
        "name_cn": "长安凯程", "name_en": "Kaicheng",
        "aliases": ["凯程", "长安凯程", "kaicheng"],
        "depreciation_rate": 0.68, "country": "中国", "tier": 2
    },
    "venucia": {
        "name_cn": "启辰", "name_en": "Venucia",
        "aliases": ["启辰", "venucia", "东风启辰", "日产启辰"],
        "depreciation_rate": 0.70, "country": "中国", "tier": 2
    },
    "ds": {
        "name_cn": "DS", "name_en": "DS",
        "aliases": ["ds", "谛艾仕", "法国ds"],
        "depreciation_rate": 0.62, "country": "法国", "tier": 2
    },
    "zotye": {
        "name_cn": "众泰", "name_en": "Zotye",
        "aliases": ["众泰", "zotye", "众泰汽车"],
        "depreciation_rate": 0.60, "country": "中国", "tier": 2
    },
    "seres": {
        "name_cn": "赛力斯", "name_en": "Seres",
        "aliases": ["赛力斯", "seres", "赛力斯汽车"],
        "depreciation_rate": 0.72, "country": "中国", "tier": 2
    },
}

# 热门车型系列
MODELS = {
    "toyota": ["卡罗拉", "凯美瑞", "RAV4", "汉兰达", "普拉多", "皇冠", "亚洲龙", "威驰",
               "雷凌", "致炫", "C-HR", "奕泽", "赛那", "格瑞维亚", "卡罗拉锐放", "锋兰达"],
    "honda": ["思域", "雅阁", "CR-V", "飞度", "奥德赛", "XR-V", "缤智", "冠道",
              "皓影", "型格", "凌派", "享域", "艾力绅", "英仕派"],
    "nissan": ["轩逸", "天籁", "奇骏", "逍客", "劲客", "途达", "楼兰", "骐达"],
    "volkswagen": ["朗逸", "速腾", "迈腾", "帕萨特", "途观L", "探岳", "途昂", "高尔夫",
                   "宝来", "捷达", "桑塔纳", "凌渡", "途岳", "途铠", "揽境", "威然", "ID.4", "ID.6"],
    "bmw": ["3系", "5系", "7系", "X1", "X3", "X5", "X6", "X7", "i3", "iX3", "4系", "M3", "M4", "2系", "1系", "i5"],
    "mercedes-benz": ["C级", "E级", "S级", "GLC", "GLE", "GLS", "A级", "GLA", "GLB", "CLA", "EQE", "EQS"],
    "audi": ["A4L", "A6L", "A8L", "Q3", "Q5L", "Q7", "Q8", "e-tron", "A3", "A5", "Q2L", "Q4 e-tron"],
    "byd": ["秦PLUS", "汉", "唐", "宋PLUS", "元PLUS", "海豚", "海鸥", "海豹",
            "驱逐舰05", "护卫舰07", "仰望U8", "秦L", "宋L", "海狮07"],
    "geely": ["帝豪", "博越L", "星瑞", "星越L", "缤越", "缤瑞", "豪越L", "熊猫mini", "银河L7", "银河E8"],
    "changan": ["逸动", "CS75 PLUS", "CS55 PLUS", "UNI-V", "UNI-K", "锐程PLUS", "深蓝SL03", "启源A07", "阿维塔11"],
    "haval": ["H6", "大狗", "初恋", "赤兔", "神兽", "猛龙", "枭龙", "二代大狗"],
    "chery": ["瑞虎8", "瑞虎7", "瑞虎5x", "艾瑞泽8", "艾瑞泽5", "探索06", "瑞虎9", "捷途X70"],
    "buick": ["英朗", "君威", "君越", "昂科威", "昂科旗", "GL8", "微蓝6", "威朗", "昂科拉GX"],
    "lexus": ["ES", "RX", "NX", "LX", "LS", "UX", "GX", "LM"],
    "ford": ["福克斯", "蒙迪欧", "锐界", "探险者", "锐际", "领裕", "Mustang", "F-150"],
    "nio": ["ET5", "ET7", "ES6", "ES8", "EC6", "EC7", "ET5T"],
    "tesla": ["Model 3", "Model Y", "Model S", "Model X", "Cybertruck"],
    "hyundai": ["伊兰特", "索纳塔", "途胜", "胜达", "库斯途", "菲斯塔", "沐飒"],
    "porsche": ["Cayenne", "Macan", "Panamera", "911", "Taycan", "718", "卡宴"],
    "li-auto": ["理想L6", "理想L7", "理想L8", "理想L9", "理想ONE", "理想MEGA"],
    "great-wall": ["炮", "山海炮", "金刚炮", "风骏"],
    "chevrolet": ["科鲁泽", "迈锐宝XL", "探界者", "创酷", "开拓者", "星迈罗"],
    "mazda": ["马自达3 昂克赛拉", "马自达6 阿特兹", "CX-5", "CX-4", "CX-30", "CX-50"],
    "kia": ["K3", "K5", "智跑", "狮铂拓界", "嘉华", "EV5", "赛图斯", "焕驰"],
    "cadillac": ["CT5", "CT6", "XT4", "XT5", "XT6", "LYRIQ锐歌", "CT4"],
    "volvo": ["XC60", "XC90", "S60", "S90", "XC40", "V60", "EX30"],
    "land-rover": ["揽胜", "揽胜运动", "卫士", "发现", "揽胜极光", "发现运动版"],
    "xpeng": ["P7", "P5", "G6", "G9", "X9", "MONA M03"],
    "hongqi": ["H5", "H9", "HS5", "E-HS9", "H6", "HQ9", "HS3", "HS7"],
}

# 原始价格参考 (新车指导价区间，万元)
NEW_CAR_PRICE_RANGE = {
    ("toyota", "卡罗拉"): (11, 16),
    ("toyota", "凯美瑞"): (18, 27),
    ("toyota", "汉兰达"): (28, 38),
    ("toyota", "RAV4"): (18, 26),
    ("toyota", "普拉多"): (45, 60),
    ("honda", "思域"): (13, 19),
    ("honda", "雅阁"): (18, 26),
    ("honda", "CR-V"): (19, 27),
    ("honda", "飞度"): (8, 11),
    ("nissan", "轩逸"): (10, 15),
    ("nissan", "天籁"): (18, 27),
    ("volkswagen", "朗逸"): (9, 15),
    ("volkswagen", "帕萨特"): (18, 28),
    ("volkswagen", "迈腾"): (18, 27),
    ("volkswagen", "途观L"): (20, 28),
    ("bmw", "3系"): (29, 40),
    ("bmw", "5系"): (43, 56),
    ("bmw", "X3"): (39, 48),
    ("bmw", "X5"): (60, 80),
    ("mercedes-benz", "C级"): (33, 38),
    ("mercedes-benz", "E级"): (44, 56),
    ("mercedes-benz", "S级"): (94, 180),
    ("mercedes-benz", "GLC"): (40, 48),
    ("audi", "A4L"): (31, 38),
    ("audi", "A6L"): (42, 56),
    ("audi", "Q5L"): (38, 46),
    ("byd", "秦PLUS"): (8, 14),
    ("byd", "汉"): (19, 29),
    ("byd", "宋PLUS"): (12, 17),
    ("byd", "海豚"): (10, 13),
    ("tesla", "Model 3"): (23, 29),
    ("tesla", "Model Y"): (25, 33),
    ("lexus", "ES"): (30, 44),
    ("lexus", "RX"): (42, 60),
    ("cadillac", "CT5"): (28, 36),
    ("volvo", "XC60"): (37, 46),
    ("volvo", "S90"): (40, 50),
    ("haval", "H6"): (10, 15),
    ("chery", "瑞虎8"): (9, 15),
    ("geely", "星越L"): (14, 19),
    ("nio", "ET5"): (32, 38),
    ("li-auto", "理想L8"): (35, 42),
    ("porsche", "Cayenne"): (92, 120),
    ("porsche", "卡宴"): (92, 120),
    ("porsche", "Macan"): (57, 70),
    ("land-rover", "揽胜"): (140, 200),
    ("land-rover", "卫士"): (68, 90),
    ("buick", "GL8"): (23, 33),
    ("buick", "君威"): (15, 21),
    ("wuling", "宏光MINIEV"): (3, 5),
    ("hongqi", "H5"): (15, 21),
    ("hongqi", "H9"): (30, 53),
}


def normalize_brand(raw: str) -> str | None:
    """将用户输入的品牌名标准化为内部key，支持模糊匹配。返回None表示无法识别。"""
    if not raw or not raw.strip():
        return None

    raw = raw.strip().lower()

    # 精确匹配 alias
    for key, info in BRANDS.items():
        for alias in info["aliases"]:
            if raw == alias:
                return key

    # 包含匹配（输入在别名中）
    for key, info in BRANDS.items():
        for alias in info["aliases"]:
            if raw in alias or alias in raw:
                return key

    return None


def fuzzy_match_brand(raw: str, cutoff: float = 0.6) -> list[tuple[str, float]]:
    """模糊匹配品牌名，返回候选列表 [(brand_key, score), ...]"""
    if not raw:
        return []

    all_aliases = []
    alias_to_key = {}
    for key, info in BRANDS.items():
        for alias in info["aliases"]:
            all_aliases.append(alias)
            alias_to_key[alias] = key

    matches = get_close_matches(raw.strip().lower(), all_aliases, n=5, cutoff=cutoff)
    return [(alias_to_key[m], m) for m in matches]


def get_brand_info(key: str) -> dict | None:
    """获取品牌完整信息"""
    return BRANDS.get(key)


def get_models(brand_key: str) -> list[str]:
    """获取某品牌的热门车型列表"""
    return MODELS.get(brand_key, [])


def get_new_car_price(brand_key: str, model: str) -> tuple[float, float] | None:
    """获取新车指导价区间（万元）。返回 (low, high) 或 None"""
    # 先精确匹配
    key = (brand_key, model)
    if key in NEW_CAR_PRICE_RANGE:
        return NEW_CAR_PRICE_RANGE[key]

    # 模糊匹配（模型名包含关系）
    for (bk, mk), price in NEW_CAR_PRICE_RANGE.items():
        if bk == brand_key and (mk in model or model in mk):
            return price

    return None


def estimate_base_price(brand_key: str, model: str) -> float:
    """估算新车基础价格（取指导价中位数），未知车型返回同品牌均价"""
    price = get_new_car_price(brand_key, model)
    if price:
        return (price[0] + price[1]) / 2

    # 根据品牌tier估算一个默认新车价
    tier_prices = {1: 18, 2: 35, 3: 80}
    info = get_brand_info(brand_key)
    if info:
        return tier_prices.get(info["tier"], 20)
    return 20  # 完全未知默认20万
