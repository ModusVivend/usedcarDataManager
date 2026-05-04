"""
2024真实数据评测 — 用Kaggle+GitHub数据集计算MAE
品牌名真实、年份新(到2024)、含新能源
"""
import os, sys, time, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.dataset_2024 import load_kaggle_dataset, load_github_dataset
from src.brands import normalize_brand
from src.cleaner import clean_single_input
from src.valuation import valuate
from src.badcase import log_valuation, detect_badcases


def evaluate_2024(n_samples: int = 40):
    """
    从2024数据抽样，LLM估值 vs 实际挂牌价，计算MAE。
    注意：sh_price是挂牌价（卖家报价），真实成交价通常略低。
    """
    print("=" * 70)
    print("  2024真实数据评测 — 2万条交易记录")
    print("=" * 70)

    # 加载合并
    kaggle = load_kaggle_dataset()
    github = load_github_dataset()
    df = kaggle.merge(github, how="outer")
    df = df.dropna(subset=["price_wan", "year", "mileage_km", "brand"])
    df = df[df["price_wan"].between(1, 200)]  # 1-200万
    df = df[df["mileage_km"].between(1000, 300000)]  # 1k-30万km
    df = df[df["year"].between(2010, 2024)]

    print(f"  可用记录: {len(df):,}")

    # 匹配品牌
    df["brand_key"] = df["brand"].apply(lambda x: normalize_brand(str(x)))
    df = df.dropna(subset=["brand_key"])

    print(f"  品牌匹配后: {len(df):,} (覆盖 {df['brand_key'].nunique()} 个品牌)")
    print(f"  价格: median={df['price_wan'].median():.1f}万, "
          f"p25={df['price_wan'].quantile(0.25):.1f}万, "
          f"p75={df['price_wan'].quantile(0.75):.1f}万")
    print(f"  年份: {df['year'].min():.0f}-{df['year'].max():.0f}")

    # 分层抽样
    sample = df.groupby("brand_key", group_keys=False).apply(
        lambda g: g.sample(n=min(3, len(g)), random_state=42)
    ).reset_index(drop=True)
    if len(sample) > n_samples:
        sample = sample.sample(n=n_samples, random_state=42)

    print(f"\n[评测] 抽样 {len(sample)} 条...\n")

    results = []
    errors_wan = []

    for i, (_, row) in enumerate(sample.iterrows()):
        brand = str(row["brand"])
        model = str(row.get("model", ""))
        year = int(row["year"])
        mileage = float(row["mileage_km"])
        actual_wan = float(row["price_wan"])  # 万元

        cleaned = clean_single_input(brand, model, year, mileage)
        if not cleaned["valid"]:
            continue

        result = valuate(cleaned)
        log_valuation(result)

        if not result.get("ok"):
            continue

        v = result["valuation"]
        est_mid = (v["price_low"] + v["price_high"]) / 2
        abs_error = abs(est_mid - actual_wan)

        errors_wan.append(abs_error)
        results.append({
            "brand": brand, "model": model[:20], "year": year,
            "mileage_wan": round(mileage / 10000, 1),
            "actual_wan": actual_wan,
            "est_wan": round(est_mid, 1),
            "error_wan": round(abs_error, 1),
            "confidence": v.get("confidence", 0),
        })

        icon = "[OK]" if abs_error < actual_wan * 0.3 else ("[~]" if abs_error < actual_wan * 0.5 else "[X]")
        print(f"  [{len(results):02d}] {icon} {brand:10s} {model[:12]:12s} {year}年 {mileage/10000:.1f}万km | "
              f"实际:{actual_wan:>6.1f}万 | 估值:{est_mid:>6.1f}万 | "
              f"误差:{abs_error:>5.1f}万 | 置信度{v.get('confidence',0):.0%}")

    # 汇总
    if not errors_wan:
        print("\n  无有效结果")
        return

    mae = np.mean(errors_wan)
    rmse = np.sqrt(np.mean(np.array(errors_wan) ** 2))
    pct_errors = [e / r["actual_wan"] * 100 for e, r in zip(errors_wan, results) if r["actual_wan"] > 0]
    acc_30 = sum(1 for e in pct_errors if e < 30) / len(pct_errors) * 100 if pct_errors else 0

    print(f"\n{'='*70}")
    print(f"  评测汇总")
    print(f"{'='*70}")
    print(f"  有效估值: {len(results)}")
    print(f"  MAE:  {mae:.2f}万")
    print(f"  RMSE: {rmse:.2f}万")
    if pct_errors:
        print(f"  MAPE: {np.mean(pct_errors):.1f}%")
        print(f"  Accuracy (误差<30%): {acc_30:.0f}%")
    print(f"  平均置信度: {np.mean([r['confidence'] for r in results]):.1%}")

    # 按品牌统计
    brand_errors = {}
    for r in results:
        b = r["brand"]
        if b not in brand_errors:
            brand_errors[b] = []
        brand_errors[b].append(r["error_wan"])
    print(f"\n  分品牌MAE:")
    for brand, errs in sorted(brand_errors.items(), key=lambda x: -len(x[1]))[:8]:
        print(f"    {brand}: MAE={np.mean(errs):.2f}万 (N={len(errs)})")

    # 保存
    out = {"mae_wan": round(mae, 2), "rmse_wan": round(rmse, 2),
           "n_samples": len(results), "avg_confidence": round(np.mean([r['confidence'] for r in results]), 2),
           "results": results}
    out_path = os.path.join(os.path.dirname(__file__), "eval_2024.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n  报告已保存: {out_path}")
    print(f"{'='*70}")


if __name__ == "__main__":
    evaluate_2024(n_samples=40)
