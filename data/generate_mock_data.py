"""
生成高质量二手车模拟数据集
- 基于真实中国市场价格分布（品牌保有量、折旧曲线、区域差异）
- 含可控脏数据（缺失、异常、别名、单位错误）
- 用于展示数据清洗完整流程
"""
import pandas as pd
import numpy as np
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from src.brands import BRANDS, MODELS, get_new_car_price

np.random.seed(42)

CURRENT_YEAR = 2026

# 中国各品牌市场占有率（大致比例，用于模拟真实分布）
BRAND_MARKET_SHARE = {
    "volkswagen": 0.12, "toyota": 0.10, "byd": 0.10, "honda": 0.08,
    "changan": 0.06, "geely": 0.06, "chery": 0.05, "haval": 0.05,
    "nissan": 0.04, "bmw": 0.04, "mercedes-benz": 0.04, "audi": 0.03,
    "buick": 0.03, "wuling": 0.03, "tesla": 0.02, "hyundai": 0.02,
    "lexus": 0.02, "cadillac": 0.01, "volvo": 0.01, "ford": 0.01,
    "mazda": 0.01, "kia": 0.01, "chevrolet": 0.01, "gac": 0.01,
    "nio": 0.005, "li-auto": 0.005, "xpeng": 0.005, "hongqi": 0.005,
    "land-rover": 0.005, "porsche": 0.003, "mini": 0.003,
    "jeep": 0.002, "skoda": 0.002, "subaru": 0.002, "mitsubishi": 0.002,
    "peugeot": 0.002, "citroen": 0.002, "lincoln": 0.001,
    "maserati": 0.0005, "bentley": 0.0002, "ferrari": 0.0001,
}
# 归一化
total_share = sum(BRAND_MARKET_SHARE.values())
for k in BRAND_MARKET_SHARE:
    BRAND_MARKET_SHARE[k] /= total_share

# 中国主要城市及区域价格系数
CITIES = {
    "北京": 1.03, "上海": 1.04, "广州": 1.02, "深圳": 1.03,
    "成都": 1.00, "杭州": 1.02, "武汉": 0.99, "南京": 1.01,
    "重庆": 0.98, "西安": 0.97, "郑州": 0.97, "长沙": 0.98,
    "苏州": 1.00, "天津": 0.98, "东莞": 0.99, "青岛": 0.98,
    "合肥": 0.97, "佛山": 0.99, "沈阳": 0.96, "济南": 0.97,
}

# 燃油类型分布
FUEL_TYPES = ["汽油", "纯电", "混动", "插混", "柴油"]
FUEL_WEIGHTS = [0.65, 0.15, 0.12, 0.06, 0.02]

# 变速箱类型
TRANSMISSIONS = ["自动", "手动", "CVT", "双离合", "AMT"]
TRANS_WEIGHTS = [0.45, 0.25, 0.18, 0.10, 0.02]

# 车况分布
CONDITIONS = ["优秀", "良好", "一般", "较差"]
COND_WEIGHTS = [0.15, 0.55, 0.25, 0.05]


def weighted_choice(items, weights):
    return np.random.choice(items, p=weights)


def generate_realistic_price(brand_key: str, model: str, year: int, mileage_km: float,
                             condition: str, fuel_type: str, city_coef: float) -> float:
    """基于真实市场折旧模型生成价格"""
    # 获取品牌折旧系数
    brand_info = BRANDS.get(brand_key, {})
    brand_dep_rate = brand_info.get("depreciation_rate", 0.80)

    # 新车指导价
    price_range = get_new_car_price(brand_key, model)
    if price_range:
        original_price = np.random.uniform(price_range[0], price_range[1])
    else:
        tier_prices = {1: 15, 2: 32, 3: 70}
        original_price = tier_prices.get(brand_info.get("tier", 1), 15)
        original_price *= np.random.uniform(0.8, 1.2)

    car_age = max(0, CURRENT_YEAR - year)

    # 年份折旧：前3年陡，之后缓
    if car_age <= 3:
        year_dep = np.power(brand_dep_rate, car_age)
    else:
        year_dep = np.power(brand_dep_rate, 3) * np.power(0.92, car_age - 3)

    # 新能源额外折旧
    if fuel_type in ["纯电", "插混"]:
        year_dep *= 0.90

    # 里程折损
    expected_mileage = car_age * 15000
    mileage_ratio = mileage_km / max(expected_mileage, 1)
    if mileage_ratio <= 1:
        mileage_factor = 1.0
    elif mileage_ratio <= 2:
        mileage_factor = 1.0 - (mileage_ratio - 1) * 0.15
    else:
        mileage_factor = 0.85 - (mileage_ratio - 2) * 0.1
    mileage_factor = max(mileage_factor, 0.3)

    # 车况调整
    cond_factors = {"优秀": 1.10, "良好": 1.00, "一般": 0.85, "较差": 0.65}
    cond_factor = cond_factors.get(condition, 1.0)

    # 燃油类型对二手价的影响
    fuel_factors = {"汽油": 1.0, "纯电": 0.88, "混动": 0.97, "插混": 0.90, "柴油": 0.95}
    fuel_factor = fuel_factors.get(fuel_type, 1.0)

    # 综合计算
    price = original_price * year_dep * mileage_factor * cond_factor * fuel_factor * city_coef

    # 市场噪声 (±8%)
    price *= np.random.normal(1.0, 0.04)
    price = max(0.3, min(200, price))

    return round(price, 2)


def generate_data(n: int = 2000) -> pd.DataFrame:
    """生成含脏数据的高质量模拟二手车数据集"""
    records = []

    brand_keys = list(BRAND_MARKET_SHARE.keys())
    brand_probs = [BRAND_MARKET_SHARE[k] for k in brand_keys]
    city_names = list(CITIES.keys())
    city_probs = [1.0 / len(city_names)] * len(city_names)

    for i in range(n):
        # 品牌（按市场占有率分布）
        brand_key = np.random.choice(brand_keys, p=brand_probs)
        brand_info = BRANDS[brand_key]

        # 车型
        models = MODELS.get(brand_key, ["未知车型"])
        model = np.random.choice(models)

        # 年份（集中分布在2016-2025年）
        year_weights = [0.02, 0.03, 0.04, 0.06, 0.07, 0.09, 0.11, 0.13, 0.12, 0.10,
                        0.08, 0.06, 0.04, 0.03, 0.01, 0.01, 0.005]
        year_weights = np.array(year_weights) / sum(year_weights)
        year = int(np.random.choice(range(2010, 2027), p=year_weights))

        car_age = CURRENT_YEAR - year

        # 里程（对数正态分布，更真实）
        annual_km = np.random.lognormal(np.log(13000), 0.4)
        annual_km = max(3000, min(50000, annual_km))
        mileage_km = round(annual_km * max(1, car_age), 0)

        # 其他属性
        fuel_type = weighted_choice(FUEL_TYPES, FUEL_WEIGHTS)
        transmission = weighted_choice(TRANSMISSIONS, TRANS_WEIGHTS)
        condition = weighted_choice(CONDITIONS, COND_WEIGHTS)
        city = np.random.choice(city_names)
        city_coef = CITIES[city]

        # 事故历史（15%概率）
        has_accident = np.random.random() < 0.15

        # 计算价格
        price = generate_realistic_price(
            brand_key, model, year, mileage_km,
            condition, fuel_type, city_coef
        )

        # 事故车折价
        if has_accident:
            price *= np.random.uniform(0.75, 0.92)

        records.append({
            "brand": brand_info["name_cn"],
            "model": model,
            "year": int(year),
            "mileage": mileage_km,
            "price": price,
            "fuel_type": fuel_type,
            "transmission": transmission,
            "condition": condition,
            "city": city,
            "has_accident": has_accident,
        })

    df = pd.DataFrame(records)

    # ========== 注入脏数据（约15%） ==========
    n = len(df)

    # 1. 品牌英文名/别名（5%）
    alias_map = {
        "toyota": "Toyota", "honda": "Honda", "bmw": "BMW",
        "mercedes-benz": "Benz", "volkswagen": "VW", "audi": "Audi",
        "nissan": "尼桑", "lexus": "凌志", "byd": "byd",
        "porsche": "Porsche", "land-rover": "Land Rover",
        "cadillac": "Cadillac",  "volvo": "Volvo",
        "hyundai": "Hyundai", "kia": "Kia",
    }
    for idx in np.random.choice(df.index, size=int(n * 0.05), replace=False):
        bk = np.random.choice(list(alias_map.keys()))
        df.at[idx, "brand"] = alias_map[bk]

    # 2. 品牌错别字/缩写（3%）
    typo_map = {
        "大众": "大从", "丰田": "丰天", "本田": "本天", "宝马": "宝馬",
        "奔驰": "梅赛德斯", "奥迪": "四个圈", "比亚迪": "比压迪",
        "特斯拉": "Telsa", "吉利": "吉利汽车", "长安": "長安",
        "保时捷": "破鞋", "路虎": "陸虎", "玛莎拉蒂": "玛莎",
        "劳斯莱斯": "RR", "兰博基尼": "牛", "沃尔沃": "富豪",
    }
    for idx in np.random.choice(df.index, size=int(n * 0.03), replace=False):
        brand = df.at[idx, "brand"]
        if brand in typo_map:
            df.at[idx, "brand"] = typo_map[brand]

    # 3. 缺失值（各列 3-5%）
    for col in ["brand", "model", "year", "mileage", "price", "fuel_type", "city"]:
        null_idx = np.random.choice(df.index, size=int(n * np.random.uniform(0.03, 0.05)), replace=False)
        df.loc[null_idx, col] = np.nan

    # 4. 里程单位错误（万公里 < 100的小数，10%）
    wkm_idx = np.random.choice(df.index, size=int(n * 0.10), replace=False)
    for idx in wkm_idx:
        if pd.notna(df.at[idx, "mileage"]) and df.at[idx, "mileage"] >= 1000:
            df.at[idx, "mileage"] = round(df.at[idx, "mileage"] / 10000, 1)

    # 5. 异常值
    # 年份异常
    for idx in np.random.choice(df.index, size=10, replace=False):
        df.at[idx, "year"] = np.random.choice([1888, 2035, -5, 2050])

    # 里程异常
    for idx in np.random.choice(df.index, size=8, replace=False):
        df.at[idx, "mileage"] = np.random.choice([-9999, 0, 88888888])

    # 价格异常
    for idx in np.random.choice(df.index, size=8, replace=False):
        df.at[idx, "price"] = np.random.choice([-50, 0, 9999])

    return df


if __name__ == "__main__":
    n_records = 2000
    df = generate_data(n_records)

    output_path = os.path.join(os.path.dirname(__file__), "raw", "used_car_data.csv")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df.to_csv(output_path, index=False, encoding="utf-8-sig")

    print(f"Generated {len(df)} realistic car records with dirty data")
    print(f"Saved to: {output_path}")
    print(f"\nBrand distribution (top 15):")
    print(df["brand"].value_counts().head(15).to_string())
    print(f"\nPrice distribution:")
    print(df["price"].describe().to_string())
    print(f"\nYear distribution:")
    print(df["year"].value_counts().sort_index().head(10).to_string())
    print(f"\nDirty data summary:")
    print(f"  Missing values:")
    print(df.isnull().sum().to_string())
    print(f"  Negative mileage: {(df['mileage'] < 0).sum()}")
    print(f"  Abnormal year (>2026): {(df['year'] > 2026).sum() if df['year'].notna().any() else 0}")
    print(f"  Negative price: {(df['price'] < 0).sum()}")
