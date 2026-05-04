"""
用2024数据训练校准器，输出可持久化的校准参数
"""
import os, sys, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.dataset_2024 import load_kaggle_dataset, load_github_dataset
from src.brands import normalize_brand
from src.cleaner import clean_single_input
from src.valuation import valuate


def build_calibration(n_calibrate: int = 50):
    """
    用2024数据跑N条估值 → 收集LLM估计vs实际价格 → 训练校准器 → 保存
    """
    print(f"[校准] 用 {n_calibrate} 条2024数据训练校准器...")

    kaggle = load_kaggle_dataset()
    github = load_github_dataset()
    df = kaggle.merge(github, how="outer")
    df = df.dropna(subset=["price_wan", "year", "mileage_km", "brand"])
    df = df[df["price_wan"].between(1, 200)]
    df = df[df["mileage_km"].between(1000, 300000)]
    df["brand_key"] = df["brand"].apply(lambda x: normalize_brand(str(x)))
    df = df.dropna(subset=["brand_key"])

    sample = df.sample(n=n_calibrate, random_state=42)

    calib_data = []
    for i, (_, row) in enumerate(sample.iterrows()):
        cleaned = clean_single_input(str(row["brand"]), str(row.get("model", "")),
                                      int(row["year"]), float(row["mileage_km"]))
        if not cleaned["valid"]:
            continue
        result = valuate(cleaned)
        if not result.get("ok"):
            continue
        v = result["valuation"]
        est_mid = (v["price_low"] + v["price_high"]) / 2 * 10000  # 万元→元
        calib_data.append({
            "llm_estimate_yuan": est_mid,
            "actual_yuan": float(row["price_wan"]) * 10000,
            "year": int(row["year"]),
        })
        print(f"  [{len(calib_data)}/{n_calibrate}] {row['brand']} {row['year']:.0f}年 | "
              f"LLM:{est_mid:.0f}元 vs 实际:{row['price_wan']*10000:.0f}元")

    # 保存校准数据
    out_path = os.path.join(os.path.dirname(__file__), "calibration_data.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(calib_data, f, ensure_ascii=False, indent=2)

    # 用quantile校准器计算效果
    from src.calibration import build_quantile_calibrator
    cal_fn = build_quantile_calibrator(calib_data)

    errors_before = [abs(d["llm_estimate_yuan"] - d["actual_yuan"]) for d in calib_data]
    errors_after = [abs(cal_fn(d["llm_estimate_yuan"], 0) - d["actual_yuan"]) for d in calib_data]
    print(f"\n  校准前MAE: {np.mean(errors_before):.0f}元")
    print(f"  校准后MAE: {np.mean(errors_after):.0f}元")
    print(f"  改善: {(1 - np.mean(errors_after)/np.mean(errors_before))*100:.0f}%")
    print(f"\n  校准数据保存到: {out_path}")


if __name__ == "__main__":
    build_calibration(n_calibrate=50)
