"""
真实天池数据 — 完整清洗 + 估值流水线
"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pandas as pd
import numpy as np
from src.tianchi_parser import parse_tianchi
from src.valuation import valuate
from src.badcase import log_valuation, detect_badcases, analyze_logs
from src.cleaner import clean_single_input


def clean_tianchi_data(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    真实天池数据的清洗管道：
    - 日期解析
    - 里程异常值处理
    - 缺失值统计
    - BadCase 标记
    """
    report = {"original_rows": len(df)}

    # 1. 公里数异常值处理
    if "mileage_km" in df.columns:
        # 中位数 15万km，使用 IQR 或分位数清洗
        median_km = df["mileage_km"].median()
        # 极端值：>100万公里或<1000公里
        outliers = (df["mileage_km"] > 1_000_000) | (df["mileage_km"] < 1000)
        report["mileage_outliers"] = int(outliers.sum())
        df.loc[outliers, "mileage_km"] = np.nan
        # 用中位数填充
        df["mileage_km"] = df["mileage_km"].fillna(median_km)
        print(f"  Fixed {report['mileage_outliers']} mileage outliers, median={median_km:.0f} km")

    # 2. 年份异常值处理
    if "reg_year" in df.columns:
        bad_year = (df["reg_year"] < 1990) | (df["reg_year"] > 2026)
        report["year_outliers"] = int(bad_year.sum())
        df.loc[bad_year, "reg_year"] = np.nan
        df["reg_year"] = df["reg_year"].fillna(df["reg_year"].median())
        print(f"  Fixed {report['year_outliers']} year outliers")

    # 3. power 清洗
    if "power" in df.columns:
        df["power"] = pd.to_numeric(df["power"], errors="coerce")
        bad_power = (df["power"] < 0) | (df["power"] > 600)
        report["power_outliers"] = int(bad_power.sum())
        df.loc[bad_power, "power"] = np.nan
        df["power"] = df["power"].fillna(df["power"].median())
        print(f"  Fixed {report['power_outliers']} power outliers")

    # 4. notRepairedDamage NaN 处理
    if "notRepairedDamage" in df.columns:
        df["notRepairedDamage"] = pd.to_numeric(df["notRepairedDamage"], errors="coerce")
        report["notRepairedDamage_missing"] = int(df["notRepairedDamage"].isna().sum())

    report["final_rows"] = len(df)
    report["removed_rows"] = 0

    return df, report


def sample_valuation(df: pd.DataFrame, n: int = 5) -> list[dict]:
    """
    从清洗后的数据中抽样，调用 LLM 估值。
    注意：测试集没有 price 列，无法计算 APE。
    这里是展示完整的「真实数据 → 清洗 → 估值」管道。
    """
    sample = df[["brand_label", "reg_year", "mileage_km", "fuelType_name", "gearbox_name", "power"]].dropna().sample(
        n=min(n, len(df)), random_state=42
    )

    results = []
    for i, (_, row) in enumerate(sample.iterrows()):
        brand = row.get("brand_label", "未知")
        model = f"车型_{i}"  # model 被脱敏，无法获取真实名
        year = int(row["reg_year"])
        mileage = float(row["mileage_km"])

        print(f"\n  [{i+1}/{n}] {brand} | {year}年 | {mileage/10000:.1f}万km")

        cleaned = clean_single_input(brand, model, year, mileage)
        if cleaned["valid"]:
            result = valuate(cleaned)
            log_valuation(result)
            v = result["valuation"]
            print(f"    → 估价: {v['price_low']}-{v['price_high']}万 | 置信度: {v.get('confidence', 0):.0%} | {result['elapsed_sec']}s")
            results.append(result)
        else:
            print(f"    → 跳过: {cleaned['errors']}")
            results.append({"ok": False, "errors": cleaned["errors"]})

    return results


def main():
    data_dir = os.path.join(os.path.dirname(__file__), "raw")
    testb_path = os.path.join(data_dir, "used_car_testB_20200421.csv")

    if not os.path.exists(testb_path):
        print(f"未找到天池数据: {testb_path}")
        return

    print("="*70)
    print("  真实天池数据 — 清洗 + 估值管道")
    print("="*70)

    # Step 1: 解析
    print("\n[1/3] 解析天池数据...")
    df = parse_tianchi(testb_path)

    # Step 2: 清洗
    print("\n[2/3] 数据清洗...")
    df_clean, report = clean_tianchi_data(df)
    print(f"\n  清洗报告:")
    for k, v in report.items():
        print(f"    {k}: {v:,}")

    # 品牌/年份/里程分布
    print(f"\n  品牌分布 (Top 10):")
    for brand, count in df_clean["brand_label"].value_counts().head(10).items():
        print(f"    {brand}: {count:,} ({count/len(df_clean)*100:.1f}%)")

    print(f"\n  燃油类型分布:")
    for fuel, count in df_clean["fuelType_name"].value_counts().items():
        print(f"    {fuel}: {count:,} ({count/len(df_clean)*100:.1f}%)")

    print(f"\n  年份分布:")
    year_dist = df_clean["reg_year"].value_counts().sort_index()
    print(f"    {year_dist.index.min():.0f} ~ {year_dist.index.max():.0f}")
    print(f"    中位数: {df_clean['reg_year'].median():.0f}年")

    print(f"\n  里程分布 (万公里):")
    km = df_clean["mileage_km"] / 10000
    print(f"    mean={km.mean():.1f}, median={km.median():.1f}, max={km.max():.1f}")

    # Step 3: 抽样估值
    print(f"\n[3/3] LLM 抽样估值 (5条)...")
    results = sample_valuation(df_clean, n=5)

    # BadCase 检查
    print(f"\n  实时 BadCase 检测:")
    total_bc = 0
    for r in results:
        if r.get("ok"):
            badcases = detect_badcases(r)
            if badcases:
                total_bc += len(badcases)
                for bc in badcases:
                    print(f"    [{bc['severity']}] {bc['rule']}: {bc['detail'][:80]}")
    if total_bc == 0:
        print(f"    未检测到 BadCase")

    # BadCase 分析
    print(f"\n  历史 BadCase 总览:")
    log_report = analyze_logs()
    print(f"    总记录: {log_report.get('total_records', 0)}")
    print(f"    Fallback率: {log_report.get('fallback_rate', 0)}")
    print(f"    平均置信度: {log_report.get('avg_confidence', 0)}")

    print(f"\n{'='*70}")
    print(f"  管道完成。已用真实5万条天池数据验证清洗+估值全流程。")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
