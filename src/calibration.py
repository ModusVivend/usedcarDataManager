"""
价格校准层

问题：LLM 不知道数据集的真实价格分布，对脱敏品牌输出偏高
解法：在 LLM 输出后加一层校准，映射到真实分布

三种策略（从简到繁）：
  Strategy 1 - Ratio: 按车龄分组计算 median(actual/estimated)，做乘法修正
  Strategy 2 - Quantile: 百分位映射，LLM估价 Px 映射到真实价格 Px
  Strategy 3 - Isotonic: 保序回归，最优但需要足够校准样本
"""

import numpy as np
import pandas as pd
from typing import Callable


def build_ratio_calibrator(calib_data: list[dict]) -> Callable:
    """
    策略1：按车龄分组比例校准

    calib_data: [{"year": int, "llm_estimate_yuan": float, "actual_yuan": float}, ...]

    Returns: calibrator(estimate_yuan: float, car_age: int) -> float
    """
    df = pd.DataFrame(calib_data)
    df["car_age"] = 2026 - df["year"]
    df["ratio"] = df["actual_yuan"] / df["llm_estimate_yuan"].clip(1)
    # 过滤极端值
    df = df[df["ratio"].between(0.01, 5.0)]

    # 按车龄分组
    bins = [0, 5, 10, 15, 30]
    labels = ["0-5年", "5-10年", "10-15年", "15年+"]
    df["age_group"] = pd.cut(df["car_age"], bins=bins, labels=labels)

    group_ratios = {}
    for group in labels:
        g = df[df["age_group"] == group]
        if len(g) >= 3:
            group_ratios[group] = g["ratio"].median()
        else:
            group_ratios[group] = df["ratio"].median()  # fallback

    print(f"  Ratio calibrator built:")
    for group, ratio in group_ratios.items():
        print(f"    {group}: correction_ratio = {ratio:.3f}")

    def calibrate(estimate_yuan: float, car_age: int) -> float:
        age_group = pd.cut([car_age], bins=bins, labels=labels)[0]
        ratio = group_ratios.get(age_group, group_ratios.get("10-15年", 0.3))
        return estimate_yuan * ratio

    calibrate.__doc__ = "Ratio-based calibration by car age group"
    return calibrate


def build_quantile_calibrator(calib_data: list[dict]) -> Callable:
    """
    策略2：百分位映射校准

    对校准集：
    1. 排序 LLM 估计值和真实价格
    2. 对于新估计值，找到它在 LLM 分布中的百分位
    3. 返回真实价格中相同百分位的值

    优势：不依赖参数假设，自动适应分布形状
    """
    if len(calib_data) < 10:
        # 样本太少，退化到中位数校准
        ratios = [d["actual_yuan"] / max(d["llm_estimate_yuan"], 1) for d in calib_data]
        median_ratio = np.median(ratios)
        print(f"  Quantile calibrator (fallback): median_ratio = {median_ratio:.3f}")
        return lambda estimate_yuan, car_age=0: estimate_yuan * median_ratio

    estimates = np.array([d["llm_estimate_yuan"] for d in calib_data])
    actuals = np.array([d["actual_yuan"] for d in calib_data])

    # 过滤极端 ratio
    ratios = actuals / estimates.clip(1)
    mask = (ratios > 0.001) & (ratios < 10)
    estimates = estimates[mask]
    actuals = actuals[mask]

    if len(estimates) < 5:
        median_ratio = np.median(ratios[mask]) if mask.any() else 0.3
        return lambda estimate_yuan, car_age=0: estimate_yuan * median_ratio

    # 排序并建立映射
    sorted_estimates = np.sort(estimates)
    sorted_actuals = np.sort(actuals)

    print(f"  Quantile calibrator built: {len(estimates)} samples")
    print(f"    Estimate range: {sorted_estimates[0]:.0f} - {sorted_estimates[-1]:.0f} yuan")
    print(f"    Actual range:   {sorted_actuals[0]:.0f} - {sorted_actuals[-1]:.0f} yuan")

    def calibrate(estimate_yuan: float, car_age: int = 0) -> float:
        # 找到 estimate 在 sorted_estimates 中的百分位
        quantile = np.searchsorted(sorted_estimates, estimate_yuan) / len(sorted_estimates)
        quantile = np.clip(quantile, 0, 1)
        # 映射到 sorted_actuals 的相同百分位
        idx = int(quantile * (len(sorted_actuals) - 1))
        idx = np.clip(idx, 0, len(sorted_actuals) - 1)
        return float(sorted_actuals[idx])

    calibrate.__doc__ = "Quantile-mapping calibration"
    return calibrate


def build_isotonic_calibrator(calib_data: list[dict]) -> Callable:
    """
    策略3：保序回归校准（最优，但需要 sklearn）

    在保持价格排序不变的前提下，最小化 actual - f(estimate) 的误差。
    """
    try:
        from sklearn.isotonic import IsotonicRegression
    except ImportError:
        print("  sklearn not available, falling back to quantile calibrator")
        return build_quantile_calibrator(calib_data)

    if len(calib_data) < 10:
        return build_quantile_calibrator(calib_data)

    estimates = np.array([d["llm_estimate_yuan"] for d in calib_data])
    actuals = np.array([d["actual_yuan"] for d in calib_data])

    # 过滤
    ratios = actuals / estimates.clip(1)
    mask = (ratios > 0.001) & (ratios < 10)
    estimates = estimates[mask]
    actuals = actuals[mask]

    if len(estimates) < 5:
        return build_quantile_calibrator(calib_data)

    ir = IsotonicRegression(out_of_bounds="clip", y_min=0)
    ir.fit(estimates, actuals)

    print(f"  Isotonic calibrator built: {len(estimates)} samples")
    print(f"    Score: {ir.score(estimates, actuals):.3f}")

    def calibrate(estimate_yuan: float, car_age: int = 0) -> float:
        return float(ir.predict([estimate_yuan])[0])

    calibrate.__doc__ = "Isotonic regression calibration"
    return calibrate


def calibrate_results(results: list[dict], strategy: str = "quantile") -> list[dict]:
    """
    对一批估值结果进行校准，返回含校准前后的对比结果。

    results: [{"llm_estimate_yuan": float, "actual_yuan": float, "year": int, ...}, ...]
    strategy: "ratio" | "quantile" | "isotonic"

    Returns: enriched results with calibrated_estimate and calibrated_error
    """
    if strategy == "ratio":
        cal_fn = build_ratio_calibrator(results)
    elif strategy == "isotonic":
        cal_fn = build_isotonic_calibrator(results)
    else:
        cal_fn = build_quantile_calibrator(results)

    for r in results:
        car_age = 2026 - r.get("year", 2015)
        r["calibrated_yuan"] = cal_fn(r["llm_estimate_yuan"], car_age)
        r["calibrated_error"] = abs(r["calibrated_yuan"] - r["actual_yuan"])
        r["original_error"] = abs(r["llm_estimate_yuan"] - r["actual_yuan"])

    # 计算改善
    orig_mae = np.mean([r["original_error"] for r in results])
    cal_mae = np.mean([r["calibrated_error"] for r in results])
    improvement = (orig_mae - cal_mae) / orig_mae * 100 if orig_mae > 0 else 0

    print(f"\n  【校准效果】")
    print(f"    原始 MAE:  {orig_mae:,.0f} 元 ({orig_mae/10000:.2f}万元)")
    print(f"    校准后 MAE: {cal_mae:,.0f} 元 ({cal_mae/10000:.2f}万元)")
    print(f"    改善:      {improvement:.1f}%")

    return results
