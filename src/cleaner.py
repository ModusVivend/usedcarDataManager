"""
数据清洗模块
- pandas读取CSV，输出清洗报告
- 缺失值处理、异常值检测、品牌标准化
- 特征工程：车龄、年均里程、预估折旧率
"""

import pandas as pd
import numpy as np
from datetime import datetime
from src.brands import normalize_brand, fuzzy_match_brand, get_brand_info

CURRENT_YEAR = 2026


def load_data(filepath: str) -> pd.DataFrame:
    """加载CSV数据集，自动检测编码"""
    for enc in ["utf-8", "gbk", "gb2312", "gb18030", "latin1"]:
        try:
            return pd.read_csv(filepath, encoding=enc)
        except (UnicodeDecodeError, UnicodeError):
            continue
    return pd.read_csv(filepath, encoding="utf-8", errors="replace")


def clean_data(df: pd.DataFrame, column_mapping: dict | None = None) -> tuple[pd.DataFrame, dict]:
    """
    清洗二手车数据，返回 (cleaned_df, report)

    默认期望列: brand, model, year, mileage, price（可通过column_mapping自定义映射）

    report包含:
        - original_rows, final_rows, removed_rows
        - missing_stats: 各列缺失值数量
        - outlier_stats: 各列异常值数量
        - brand_normalize_stats: 品牌标准化统计
        - badcase_records: 被标记为异常的行索引列表
    """
    report = {"original_rows": len(df), "removed_rows": 0, "badcase_records": []}

    # Step 1: 列名映射（如果列名不一致）
    if column_mapping:
        df = df.rename(columns=column_mapping)

    # 检测并处理缺失的必需列
    required_cols = ["brand", "model", "year", "mileage"]
    available_cols = [c for c in required_cols if c in df.columns]
    missing_cols = [c for c in required_cols if c not in df.columns]
    report["missing_columns"] = missing_cols

    if "brand" not in df.columns:
        raise ValueError("数据集缺少 'brand' 列，且未提供 column_mapping")

    # Step 2: 缺失值统计与处理
    report["missing_stats"] = {}
    for col in available_cols:
        n_missing = int(df[col].isna().sum())
        report["missing_stats"][col] = n_missing

    # 价格列缺失处理（如果有）
    if "price" in df.columns:
        n_price_missing = int(df["price"].isna().sum())
        report["missing_stats"]["price"] = n_price_missing

    # 删除品牌为空的记录
    before = len(df)
    df = df.dropna(subset=["brand"]).copy()
    report["removed_brand_null"] = before - len(df)

    # 填充年份/里程缺失值（中位数）
    if "year" in df.columns:
        df["year"] = df["year"].fillna(df["year"].median())
    if "mileage" in df.columns:
        df["mileage"] = df["mileage"].fillna(df["mileage"].median())
    if "price" in df.columns:
        df["price"] = df["price"].fillna(df["price"].median())

    # Step 3: 异常值检测
    report["outlier_stats"] = {}
    badcase_indices = []

    if "year" in df.columns:
        # 年份异常：不在 1990~2026 范围
        year_mask = (df["year"] < 1990) | (df["year"] > CURRENT_YEAR)
        badcase_indices.extend(df[year_mask].index.tolist())
        report["outlier_stats"]["year"] = int(year_mask.sum())
        df = df[~year_mask]

    if "mileage" in df.columns:
        # 里程异常：负数或 >100万公里
        mileage_mask = (df["mileage"] < 0) | (df["mileage"] > 100)
        # mileage可能以"万公里"为单位，检测判断
        if df["mileage"].max() > 1000:
            # 很可能是以公里为单位的，上限放宽到100万
            mileage_mask = (df["mileage"] < 0) | (df["mileage"] > 1_000_000)
        badcase_indices.extend(df[mileage_mask].index.tolist())
        report["outlier_stats"]["mileage"] = int(mileage_mask.sum())
        df = df[~mileage_mask]

    if "price" in df.columns:
        # 价格异常：负数或 >500万
        price_mask = (df["price"] < 0) | (df["price"] > 500)
        badcase_indices.extend(df[price_mask].index.tolist())
        report["outlier_stats"]["price"] = int(price_mask.sum())
        df = df[~price_mask]

    report["removed_outliers"] = report["original_rows"] - len(df) - report.get("removed_brand_null", 0)
    report["badcase_records"] = list(set(badcase_indices))

    # Step 4: 品牌标准化
    report["brand_normalize_stats"] = {"total": len(df), "matched": 0, "unmatched": 0, "unmatched_list": []}
    unmatched_brands = set()

    def try_normalize(name):
        result = normalize_brand(str(name))
        if result:
            return result
        # 尝试模糊匹配
        candidates = fuzzy_match_brand(str(name))
        if candidates:
            return candidates[0][0]
        unmatched_brands.add(str(name))
        return None

    df["brand_normalized"] = df["brand"].apply(try_normalize)
    report["brand_normalize_stats"]["matched"] = int(df["brand_normalized"].notna().sum())
    report["brand_normalize_stats"]["unmatched"] = int(df["brand_normalized"].isna().sum())
    report["brand_normalize_stats"]["unmatched_list"] = list(unmatched_brands)

    # Step 5: 统一里程单位（如果里程>5000就当作公里）
    if "mileage" in df.columns:
        if df["mileage"].median() > 1000:
            df["mileage_km"] = df["mileage"]
        else:
            df["mileage_km"] = df["mileage"] * 10000  # 万公里→公里

    # Step 6: 特征工程
    if "year" in df.columns:
        df["car_age"] = CURRENT_YEAR - df["year"]
        df["car_age"] = df["car_age"].clip(0, 30)

    if "mileage_km" in df.columns and "car_age" in df.columns:
        df["annual_mileage"] = df["mileage_km"] / df["car_age"].clip(1)
        df["annual_mileage"] = df["annual_mileage"].clip(0, 200000)

    if "price" in df.columns:
        # 计算实际折旧率 (price / estimated_original_price) ^ (1 / car_age)
        pass  # 在新车指导价不可得时跳过

    report["final_rows"] = len(df)
    report["removed_rows"] = report["original_rows"] - report["final_rows"]

    return df, report


def clean_single_input(brand: str, model: str, year: str | int, mileage: str | float) -> dict:
    """
    清洗单条用户输入，返回标准化后的 dict 或 error 信息。
    这是CLI/Streamlit入口调用的快捷函数。
    """
    errors = []
    warnings = []

    # 品牌标准化
    brand_key = normalize_brand(brand)
    if not brand_key:
        candidates = fuzzy_match_brand(brand)
        if candidates:
            brand_key = candidates[0][0]
            brand_display = get_brand_info(brand_key)["name_cn"]
            warnings.append(f"品牌 '{brand}' 模糊匹配为 '{brand_display}'")
        else:
            errors.append(f"无法识别品牌: '{brand}'")

    # 年份校验
    try:
        year_val = int(year)
    except (ValueError, TypeError):
        errors.append(f"年份格式错误: '{year}'")
        year_val = None
    else:
        if year_val < 1990:
            errors.append(f"年份 {year_val} 太早，不支持1990年之前的车辆")
        elif year_val > CURRENT_YEAR:
            errors.append(f"年份 {year_val} 不能超过当前年份 {CURRENT_YEAR}")

    # 里程校验与单位转换
    try:
        mileage_val = float(str(mileage).replace(",", "").replace("_", ""))
    except (ValueError, TypeError):
        errors.append(f"里程格式错误: '{mileage}'")
        mileage_km = None
    else:
        if mileage_val < 0:
            errors.append(f"里程不能为负数: {mileage_val}")
            mileage_km = None
        elif mileage_val > 5000:
            mileage_km = mileage_val  # 已是公里
        else:
            mileage_km = mileage_val * 10000  # 万公里→公里

        if mileage_km and mileage_km > 1_000_000:
            warnings.append(f"里程 {mileage_km:.0f} 公里偏高，请注意")

    # 车型
    model_clean = str(model).strip() if model else ""
    if not model_clean:
        errors.append("车型不能为空")

    return {
        "brand_raw": brand,
        "brand_key": brand_key,
        "brand_display": get_brand_info(brand_key)["name_cn"] if brand_key else None,
        "model": model_clean,
        "year": year_val,
        "mileage_raw": mileage,
        "mileage_km": mileage_km,
        "car_age": CURRENT_YEAR - year_val if year_val else None,
        "errors": errors,
        "warnings": warnings,
        "valid": len(errors) == 0,
    }


def print_cleaning_report(report: dict):
    """打印清洗报告"""
    print(f"\n{'='*50}")
    print(f"  数据清洗报告")
    print(f"{'='*50}")
    print(f"  原始记录数: {report['original_rows']}")
    print(f"  最终记录数: {report['final_rows']}")
    print(f"  移除记录数: {report['removed_rows']}")
    print(f"\n  缺失值统计:")
    for col, count in report["missing_stats"].items():
        print(f"    {col}: {count} 条缺失")
    print(f"\n  异常值统计:")
    for col, count in report["outlier_stats"].items():
        print(f"    {col}: {count} 条异常")

    bs = report["brand_normalize_stats"]
    print(f"\n  品牌标准化:")
    print(f"    匹配成功: {bs['matched']} / {bs['total']}")
    print(f"    未匹配: {bs['unmatched']}")
    if bs["unmatched_list"]:
        print(f"    未识别品牌: {', '.join(list(bs['unmatched_list'])[:10])}")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    # 自测
    test = clean_single_input("宝马", "3系", "2021", "4.5")
    print(test)
