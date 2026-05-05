"""
2024数据评测 — 分段评测 (价格段/车龄/能源) + 全量抽样
"""
import os, sys, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.dataset_2024 import load_kaggle_dataset, load_github_dataset
from src.brands import normalize_brand
from src.cleaner import clean_single_input
from src.valuation import valuate
from src.badcase import log_valuation


def load_data():
    """加载并清洗2024数据（两个数据集合并）"""
    kaggle = load_kaggle_dataset()
    github = load_github_dataset()
    df = kaggle.merge(github, how="outer")
    # 只保留有效数据
    df = df.dropna(subset=["price_wan", "year", "mileage_km", "brand"])
    df = df[df["price_wan"].between(1, 200)]
    df = df[df["mileage_km"].between(1000, 300000)]
    df = df[df["year"].between(2010, 2024)]
    # 匹配品牌
    df["brand_key"] = df["brand"].apply(lambda x: normalize_brand(str(x)))
    df = df.dropna(subset=["brand_key"])
    # 读取 official_price（CSV自带）
    if "official_price_wan" in df.columns:
        # 有些 official_price 可能很大，clip 一下
        df["official_price_wan"] = df["official_price_wan"].clip(1, 300)
    return df


def run_one(row):
    """估值单条，返回结果"""
    cleaned = clean_single_input(str(row["brand"]), str(row.get("model", "")),
                                  int(row["year"]), float(row["mileage_km"]))
    if not cleaned["valid"]:
        return None
    result = valuate(cleaned)
    log_valuation(result)
    if not result.get("ok"):
        return None
    v = result["valuation"]
    est_mid = (v["price_low"] + v["price_high"]) / 2
    actual = float(row["price_wan"])
    return {
        "brand": str(row["brand"]),
        "model": str(row.get("model", ""))[:20],
        "year": int(row["year"]),
        "mileage_wan": round(float(row["mileage_km"]) / 10000, 1),
        "actual_wan": actual,
        "official_wan": float(row.get("official_price_wan", 0)),
        "est_wan": round(est_mid, 1),
        "error_wan": round(abs(est_mid - actual), 1),
        "confidence": v.get("confidence", 0),
        "fuel": str(row.get("fuel_type", "?")),
    }


def segment_eval(results, label, filter_fn):
    """分段统计"""
    subset = [r for r in results if filter_fn(r)]
    if not subset:
        return {"label": label, "n": 0, "mae": None}
    mae = np.mean([r["error_wan"] for r in subset])
    acc = sum(1 for r in subset if r["error_wan"] < r["actual_wan"] * 0.3) / len(subset) * 100
    return {"label": label, "n": len(subset), "mae": round(mae, 2), "accuracy_30": round(acc, 1)}


def main():
    print("=" * 70)
    print("  2024 真实数据评测 — 分段分析")
    print("=" * 70)

    df = load_data()
    print(f"  可用数据: {len(df):,} 条, {df['brand_key'].nunique()} 个品牌")
    print(f"  价格: median={df['price_wan'].median():.1f}万, p5={df['price_wan'].quantile(0.05):.1f}万, p95={df['price_wan'].quantile(0.95):.1f}万")
    print(f"  年份: {df['year'].min():.0f}-{df['year'].max():.0f}")

    # 分层抽样：按价格段
    price_bins = [(1, 10), (10, 25), (25, 60), (60, 200)]
    samples = []
    for lo, hi in price_bins:
        pool = df[df["price_wan"].between(lo, hi)]
        n = min(15, len(pool))
        if n > 0:
            s = pool.sample(n=n, random_state=42)
            samples.append(s)

    sample_df = samples[0]
    for s in samples[1:]:
        sample_df = sample_df.merge(s, how="outer")
    sample_df = sample_df.reset_index(drop=True)

    print(f"\n  抽样: {len(sample_df)} 条 (价格段分层)")

    # 跑估值
    results = []
    for i, (_, row) in enumerate(sample_df.iterrows()):
        r = run_one(row)
        if r:
            results.append(r)
            print(f"  [{len(results):02d}] {r['brand']:10s} {r['year']}年 {r['mileage_wan']:.1f}万km | "
                  f"实际:{r['actual_wan']:.1f} | 估值:{r['est_wan']:.1f} | 误差:{r['error_wan']:.1f}万 | "
                  f"信心:{r['confidence']:.0%} | {r['fuel']}")

    if not results:
        print("  无结果")
        return

    # 分段评测
    segments = [
        ("全部", lambda r: True),
        # 按价格
        ("  10万以下", lambda r: r["actual_wan"] < 10),
        ("  10-25万", lambda r: 10 <= r["actual_wan"] < 25),
        ("  25-60万", lambda r: 25 <= r["actual_wan"] < 60),
        ("  60万以上", lambda r: r["actual_wan"] >= 60),
        # 按车龄
        ("  0-3年", lambda r: 2026 - r["year"] <= 3),
        ("  3-8年", lambda r: 3 < 2026 - r["year"] <= 8),
        ("  8年+", lambda r: 2026 - r["year"] > 8),
        # 按能源
        ("  燃油", lambda r: "汽油" in r.get("fuel", "") or "柴油" in r.get("fuel", "")),
        ("  新能源", lambda r: "电" in r.get("fuel", "") or "混" in r.get("fuel", "")),
    ]

    print(f"\n{'='*70}")
    print(f"  分段结果")
    print(f"{'='*70}")
    print(f"  {'分段':14s} {'样本':>6s} {'MAE(万)':>8s} {'准确率<30%':>10s}")
    print(f"  {'-'*40}")

    seg_results = []
    for label, fn in segments:
        seg = segment_eval(results, label, fn)
        seg_results.append(seg)
        if seg["n"] > 0:
            print(f"  {label:14s} {seg['n']:>5d}  {seg['mae']:>7.2f}  {seg['accuracy_30']:>9.1f}%")

    # 总体
    total_mae = np.mean([r["error_wan"] for r in results])
    total_acc = sum(1 for r in results if r["error_wan"] < r["actual_wan"] * 0.3) / len(results) * 100
    print(f"  {'-'*40}")
    print(f"  {'总计':14s} {len(results):>5d}  {total_mae:>7.2f}  {total_acc:>9.1f}%")

    # 保存
    out = {
        "total_mae": round(total_mae, 2),
        "total_accuracy_30": round(total_acc, 1),
        "n_samples": len(results),
        "segments": seg_results,
        "results": results,
    }
    out_path = os.path.join(os.path.dirname(__file__), "eval_2024.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n  保存: {out_path}")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
