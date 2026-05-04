"""
市场数据注入层
从天池15万训练集提取折旧规律，注入System Prompt作为参考
不注入绝对价格（数据太老），而是注入折旧斜率、里程折损率、品牌溢价
"""

import pandas as pd
import numpy as np
import os

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "raw")


def compute_market_reference() -> str:
    """计算并返回注入Prompt的市场参考文本"""
    train_path = os.path.join(DATA_DIR, "used_car_train_20200313.csv")
    if not os.path.exists(train_path):
        return ""  # 无数据，不注入

    df = pd.read_csv(train_path, sep=r"\s+", engine="python")
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df["kilometer"] = pd.to_numeric(df["kilometer"], errors="coerce")
    df["brand"] = pd.to_numeric(df["brand"], errors="coerce")
    df["fuelType"] = pd.to_numeric(df["fuelType"], errors="coerce")

    # 清洗
    df = df[df["price"].between(100, 500000)]
    df = df[df["kilometer"].between(0.01, 100)]
    df["car_age"] = 2026 - df["regDate"].astype(str).str[:4].astype(int)

    # ==================== 折旧斜率 ====================
    # 计算每个车龄区间的价格中位数，然后算出逐年折旧率
    age_bins = [(10, 12), (12, 14), (14, 16), (16, 20)]
    age_medians = {}
    for lo, hi in age_bins:
        g = df[(df["car_age"] >= lo) & (df["car_age"] < hi)]
        if len(g) > 100:
            age_medians[f"{lo}-{hi}年"] = g["price"].median()

    # 折旧斜率（年化）
    depreciation_lines = []
    if len(age_medians) >= 2:
        ages = sorted(age_medians.items())
        for i in range(1, len(ages)):
            a1_label, p1 = ages[i-1]
            a2_label, p2 = ages[i]
            # 取区间中点
            a1_mid = (int(a1_label.split("-")[0]) + int(a1_label.split("-")[1].replace("年", ""))) / 2
            a2_mid = (int(a2_label.split("-")[0]) + int(a2_label.split("-")[1].replace("年", ""))) / 2
            years_gap = a2_mid - a1_mid
            if years_gap > 0 and p1 > 0:
                annual_dep = 1 - (p2 / p1) ** (1 / years_gap)
                depreciation_lines.append(f"    车龄{a1_label}→{a2_label}: 年折旧约{annual_dep*100:.1f}%")

    # ==================== 里程折损 ====================
    mile_bins = [(3, 6), (6, 10), (10, 15), (15, 20)]
    mile_medians = {}
    for lo, hi in mile_bins:
        g = df[(df["kilometer"] >= lo) & (df["kilometer"] < hi)]
        if len(g) > 100:
            mile_medians[f"{lo}-{hi}万km"] = g["price"].median()

    mileage_lines = []
    if len(mile_medians) >= 2:
        items = sorted(mile_medians.items())
        for i in range(1, len(items)):
            m1_label, p1 = items[i-1]
            m2_label, p2 = items[i]
            ratio = p2 / p1 if p1 > 0 else 1
            mileage_lines.append(f"    里程{m1_label} vs {m2_label}: 价格比 {ratio:.2f}")

    # ==================== 品牌溢价 ====================
    overall_median = df["price"].median()
    brand_premiums = []
    for b in df["brand"].value_counts().head(8).index:
        g = df[df["brand"] == b]
        if len(g) > 500:
            ratio = g["price"].median() / overall_median if overall_median > 0 else 1
            label = "高于" if ratio > 1 else "低于"
            brand_premiums.append(f"    品牌编码{int(b)}: 均价{label}市场均值{abs(ratio-1)*100:.0f}% (N={len(g):,})")

    # ==================== 拼装输出 ====================
    parts = [
        "",
        "## 中国市场二手车交易数据参考（基于15万条真实成交记录）",
        "",
        "以下数据来自历史成交记录，反映市场折旧规律。你估值时应参考这些相对关系，",
        "而不是直接套用绝对价格（因为数据集中多数为老旧车辆）。",
        "",
        "### 折旧斜率（老车阶段）",
    ]
    parts.extend(depreciation_lines if depreciation_lines else ["    数据不足"])

    parts.append("")
    parts.append("### 里程对价格的影响")
    parts.extend(mileage_lines if mileage_lines else ["    数据不足"])

    parts.append("")
    parts.append("### 品牌相对市场均值的溢价/折价")
    parts.extend(brand_premiums if brand_premiums else ["    数据不足"])

    parts.append("")
    parts.append("### 使用时注意")
    parts.append("- 以上数据反映的是2015年之前的老旧车市场，新车(0-5年)价格应明显高于上述区间")
    parts.append("- 折旧斜率可用于推断新车到旧车的价格衰减规律")
    parts.append("- 里程每增加1万公里(年均)，价格约下降3-8%，视车龄而定")

    return "\n".join(parts)


if __name__ == "__main__":
    ref = compute_market_reference()
    print(ref)
