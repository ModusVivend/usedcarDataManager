"""
天池二手车数据集解析器
- 空格分隔格式
- 脱敏字段解码 (bodyType, fuelType, gearbox 等)
- brand/model 保持编码值（官方脱敏）
- 单位转换、日期解析
"""

import pandas as pd
import numpy as np

# ============================================================
# 官方公布的字段解码映射
# ============================================================

BODY_TYPE_MAP = {
    0: "豪华轿车", 1: "微型车", 2: "厢型车", 3: "大巴车",
    4: "敞篷车", 5: "双门汽车", 6: "商务车", 7: "搅拌车",
}

FUEL_TYPE_MAP = {
    0: "汽油", 1: "柴油", 2: "液化石油气", 3: "天然气",
    4: "混合动力", 5: "其他", 6: "电动",
}

GEARBOX_MAP = {0: "手动", 1: "自动"}

NOT_REPAIRED_MAP = {0: "是", 1: "否"}  # 0=有未修复损坏, 1=无

SELLER_MAP = {0: "个人", 1: "商家"}

OFFER_TYPE_MAP = {0: "出售", 1: "求购"}

# ============================================================
# 基于社区 EDA 推测的常见 brand 编码（高频品牌）
# 注意：这不是官方映射，是社区通过 name 字段等推测的
# ============================================================
BRAND_HINTS = {
    # 高频编码 → 推测品牌（基于 EDA 中的价格/功率分布等）
    # 仅供参考，实际用途是展示数据清洗能力
    0: "品牌_0(推测大众)",   # 最高频，10K+条，推测为大众
    4: "品牌_4(推测丰田)",   # 次高频
    14: "品牌_14(推测本田)",
    10: "品牌_10(推测日产)",
    1: "品牌_1(推测宝马)",
    6: "品牌_6(推测奔驰)",
    9: "品牌_9(推测奥迪)",
    5: "品牌_5",
    13: "品牌_13",
    11: "品牌_11",
    3: "品牌_3",
    8: "品牌_8",
    2: "品牌_2",
    7: "品牌_7",
    12: "品牌_12",
}


def parse_tianchi(filepath: str) -> pd.DataFrame:
    """
    解析天池数据集，返回规范化 DataFrame。

    处理步骤：
    1. 空格分隔解析
    2. 脱敏字段解码
    3. 日期解析 (regDate: YYYYMMDD → year)
    4. 里程单位转换 (kilometer 万公里 → 公里)
    5. notRepairedDamage '-' → NaN
    """
    # Step 1: 空格分隔读取
    df = pd.read_csv(filepath, sep=r"\s+", engine="python")

    print(f"[Tianchi Parser] Loaded {len(df):,} rows, {len(df.columns)} columns")

    # Step 2: 解码分类字段
    if "bodyType" in df.columns:
        df["bodyType_name"] = df["bodyType"].map(BODY_TYPE_MAP)

    if "fuelType" in df.columns:
        df["fuelType_name"] = df["fuelType"].map(FUEL_TYPE_MAP)

    if "gearbox" in df.columns:
        df["gearbox"] = pd.to_numeric(df["gearbox"], errors="coerce")
        df["gearbox_name"] = df["gearbox"].map(GEARBOX_MAP)

    if "notRepairedDamage" in df.columns:
        df["notRepairedDamage"] = df["notRepairedDamage"].replace("-", np.nan)
        df["notRepairedDamage"] = pd.to_numeric(df["notRepairedDamage"], errors="coerce")
        df["notRepairedDamage_name"] = df["notRepairedDamage"].map(NOT_REPAIRED_MAP)

    if "seller" in df.columns:
        df["seller_name"] = df["seller"].map(SELLER_MAP)

    if "offerType" in df.columns:
        df["offerType_name"] = df["offerType"].map(OFFER_TYPE_MAP)

    # Step 3: 日期解析
    if "regDate" in df.columns:
        df["regDate_int"] = df["regDate"].astype(str).str.strip()
        # regDate 格式: YYYYMMDD 的整数
        df["reg_year"] = df["regDate_int"].str[:4].astype(float).astype("Int64", errors="ignore")
        df["reg_month"] = df["regDate_int"].str[4:6].astype(float).astype("Int64", errors="ignore")

    # creatDate 格式也是 YYYYMMDD
    if "creatDate" in df.columns:
        df["creatDate_int"] = df["creatDate"].astype(str).str.replace(".0", "").str.strip()
        df["creat_year"] = df["creatDate_int"].str[:4].astype(float).astype("Int64", errors="ignore")

    # Step 4: 里程单位 (万公里 → 公里)
    if "kilometer" in df.columns:
        df["kilometer"] = pd.to_numeric(df["kilometer"], errors="coerce")
        df["mileage_km"] = df["kilometer"] * 10000  # 万公里 → 公里

    # Step 5: brand/model 编码转可读标签
    if "brand" in df.columns:
        df["brand"] = pd.to_numeric(df["brand"], errors="coerce")
        df["brand_label"] = df["brand"].apply(
            lambda x: BRAND_HINTS.get(int(x), f"品牌_{int(x)}") if pd.notna(x) else None
        )

    if "model" in df.columns:
        df["model"] = pd.to_numeric(df["model"], errors="coerce")
        df["model_label"] = df["model"].apply(
            lambda x: f"车型_{int(x)}" if pd.notna(x) else None
        )

    # Step 6: power 字段
    if "power" in df.columns:
        df["power"] = pd.to_numeric(df["power"], errors="coerce")

    # 数据质量统计
    print(f"\n[Tianchi Parser] Data Quality Summary:")
    print(f"  bodyType decoded: {df['bodyType_name'].notna().sum():,}/{len(df):,}")
    print(f"  fuelType decoded:  {df['fuelType_name'].notna().sum():,}/{len(df):,}")
    print(f"  gearbox decoded:   {df['gearbox_name'].notna().sum():,}/{len(df):,}")
    print(f"  notRepairedDamage: {df['notRepairedDamage_name'].notna().sum():,}/{len(df):,} (missing: {df['notRepairedDamage'].isna().sum():,})")
    print(f"  reg_year range:    {df['reg_year'].min()} - {df['reg_year'].max()}")
    print(f"  brand codes:       {int(df['brand'].nunique())} unique")
    print(f"  model codes:       {int(df['model'].nunique())} unique")

    # 匿名特征统计
    v_cols = [c for c in df.columns if c.startswith("v_")]
    if v_cols:
        missing_v = df[v_cols].isna().sum()
        print(f"  anonymous features: {len(v_cols)} (v_0 ~ v_{len(v_cols)-1})")
        print(f"  v_* missing total:  {missing_v.sum():,} cells")

    return df


def get_tianchi_stats(df: pd.DataFrame) -> dict:
    """输出天池数据集的统计摘要"""
    stats = {
        "total_records": len(df),
        "brand_count": int(df["brand"].nunique()) if "brand" in df.columns else 0,
        "model_count": int(df["model"].nunique()) if "model" in df.columns else 0,
        "year_range": f"{df['reg_year'].min()} - {df['reg_year'].max()}" if "reg_year" in df.columns else "N/A",
        "avg_mileage_km": round(df["mileage_km"].mean(), 0) if "mileage_km" in df.columns else 0,
        "avg_power": round(df["power"].mean(), 0) if "power" in df.columns else 0,
        "fuel_type_dist": df["fuelType_name"].value_counts().to_dict() if "fuelType_name" in df.columns else {},
        "gearbox_dist": df["gearbox_name"].value_counts().to_dict() if "gearbox_name" in df.columns else {},
        "top_brands": df["brand_label"].value_counts().head(10).to_dict() if "brand_label" in df.columns else {},
    }
    return stats


if __name__ == "__main__":
    import os
    data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "raw")

    # 尝试加载天池测试集
    testb_path = os.path.join(data_dir, "used_car_testB_20200421.csv")
    if os.path.exists(testb_path):
        df = parse_tianchi(testb_path)
        stats = get_tianchi_stats(df)
        print(f"\n[Tianchi Stats]")
        for k, v in stats.items():
            print(f"  {k}: {v}")
    else:
        print(f"File not found: {testb_path}")
