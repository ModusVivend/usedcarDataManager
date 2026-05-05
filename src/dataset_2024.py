"""
2024年真实二手车数据集解析器
来源: Kaggle 2024 + GitHub usedCars
特点: 真实品牌名、近年数据(含2023)、新能源车覆盖
"""
import pandas as pd
import numpy as np
import os
import re


def parse_price(val) -> float | None:
    """解析价格: '15.98万' -> 15.98 (万元)"""
    if pd.isna(val):
        return None
    s = str(val).replace("万", "").replace("元", "").replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def parse_year(val) -> int | None:
    """解析年份: '2023年' -> 2023"""
    if pd.isna(val):
        return None
    s = str(val).replace("年", "").strip()
    try:
        return int(float(s))
    except ValueError:
        return None


def parse_mileage(val) -> float | None:
    """解析里程: '6.80万公里' -> 68000 (公里)"""
    if pd.isna(val):
        return None
    s = str(val).replace("万公里", "").replace("公里", "").strip()
    try:
        wan = float(s)
        return wan * 10000
    except ValueError:
        return None


def load_kaggle_dataset() -> pd.DataFrame:
    """加载 Kaggle 2024 数据集"""
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                        "data", "raw", "used_cars.csv")
    df = pd.read_csv(path)
    df = df.rename(columns={
        "brand_name": "brand",
        "car_name": "model",
        "car_source_city_name": "city",
        "official_price": "official_price_raw",
        "sh_price": "price_raw",
        "car_year": "year_raw",
        "car_mileage": "mileage_raw",
    })

    df["price_wan"] = df["price_raw"].apply(parse_price)
    df["official_price_wan"] = df["official_price_raw"].apply(parse_price)
    df["year"] = df["year_raw"].apply(parse_year)
    df["mileage_km"] = df["mileage_raw"].apply(parse_mileage)
    df["transfer_cnt"] = pd.to_numeric(df["transfer_cnt"], errors="coerce")

    # 衍生特征
    df["car_age"] = 2026 - df["year"]
    df["annual_mileage"] = df["mileage_km"] / df["car_age"].clip(1)
    # 折旧率 = 二手价 / 官方价
    df["depreciation_ratio"] = df["price_wan"] / df["official_price_wan"].clip(0.1)

    return df


def load_github_dataset() -> pd.DataFrame:
    """加载 GitHub 2024 数据集（含新能源字段）"""
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                        "data", "raw", "usedCars.csv")
    # 尝试多种编码
    for enc in ["utf-8-sig", "utf-8", "gbk", "gb2312", "gb18030", "latin1"]:
        try:
            df = pd.read_csv(path, encoding=enc)
            break
        except (UnicodeDecodeError, UnicodeError):
            continue
    df = df.rename(columns={
        "brand_name": "brand",
        "car_name": "model",
        "car_source_city_name": "city",
        "official_price": "official_price_raw",
        "sh_price": "price_raw",
        "car_year": "year_raw",
        "car_mileage": "mileage_raw",
        "fuel_form": "fuel_type",
        "driver_form": "drive_type",
        "car_type": "body_type",
        "transfer_cnt": "transfer_count",
    })

    df["price_wan"] = df["price_raw"].apply(parse_price)
    df["official_price_wan"] = df["official_price_raw"].apply(parse_price)
    df["year"] = df["year_raw"].apply(parse_year)
    df["mileage_km"] = df["mileage_raw"].apply(parse_mileage)
    df["transfer_count"] = pd.to_numeric(df["transfer_count"], errors="coerce")

    df["car_age"] = 2026 - df["year"]
    df["annual_mileage"] = df["mileage_km"] / df["car_age"].clip(1)
    df["depreciation_ratio"] = df["price_wan"] / df["official_price_wan"].clip(0.1)

    return df


def get_combined_stats():
    """合并两个数据集的统计摘要"""
    kaggle = load_kaggle_dataset()
    github = load_github_dataset()

    print("=" * 70)
    print("  2024年真实二手车数据集 — 数据总览")
    print("=" * 70)

    for name, df in [("Kaggle 2024", kaggle), ("GitHub 2024", github)]:
        print(f"\n  [{name}]")
        print(f"    记录数: {len(df):,}")
        print(f"    品牌数: {df['brand'].nunique()}")
        print(f"    城市数: {df['city'].nunique()}")
        print(f"    年份范围: {df['year'].min():.0f} - {df['year'].max():.0f}")
        print(f"    价格(万): median={df['price_wan'].median():.1f}, "
              f"mean={df['price_wan'].mean():.1f}, "
              f"range={df['price_wan'].min():.1f}-{df['price_wan'].max():.1f}")
        print(f"    里程(万km): median={df['mileage_km'].median()/10000:.1f}")

        if "fuel_type" in df.columns:
            print(f"    燃料类型:")
            for ft, cnt in df["fuel_type"].value_counts().head(5).items():
                print(f"      {ft}: {cnt:,}")

        # 品牌分布
        print(f"    高频品牌:")
        for brand, cnt in df["brand"].value_counts().head(8).items():
            median_price = df[df["brand"] == brand]["price_wan"].median()
            print(f"      {brand}: {cnt:,}辆, 均价{median_price:.1f}万")

    # 合并统计
    all_prices = pd.concat([kaggle["price_wan"], github["price_wan"]])
    all_years = pd.concat([kaggle["year"], github["year"]])
    print(f"\n  [合并统计]")
    print(f"    总记录: {len(kaggle) + len(github):,}")
    print(f"    价格中位数: {all_prices.median():.1f}万")
    print(f"    价格 p5-p95: {all_prices.quantile(0.05):.1f} - {all_prices.quantile(0.95):.1f}万")
    print(f"    年份: {all_years.min():.0f} - {all_years.max():.0f}")
    print("=" * 70)

    return kaggle, github


if __name__ == "__main__":
    get_combined_stats()
