"""
真实数据评测 — 用天池训练集计算 MAE
"""
import os, sys, time, json
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pandas as pd
import numpy as np
from src.tianchi_parser import parse_tianchi
from src.valuation import valuate
from src.badcase import log_valuation, detect_badcases
from src.cleaner import clean_single_input


def clean_train_data(df):
    """清洗训练集（含 price）"""
    # 价格清洗
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    price_median = df["price"].median()
    df["price"] = df["price"].clip(1, 500_000)  # 1元~50万
    df["price"] = df["price"].fillna(price_median)

    # 年份清洗
    df["reg_year"] = pd.to_numeric(df["reg_year"], errors="coerce")
    df["reg_year"] = df["reg_year"].clip(1990, 2015)

    # 里程清洗
    df["mileage_km"] = pd.to_numeric(df["mileage_km"], errors="coerce")
    med_km = df["mileage_km"].median()
    df.loc[(df["mileage_km"] < 100) | (df["mileage_km"] > 500_000), "mileage_km"] = np.nan
    df["mileage_km"] = df["mileage_km"].fillna(med_km)

    return df


def evaluate_real(n_samples: int = 30):
    """
    从训练集抽样，LLM 估值 vs 真实成交价，计算 MAE。
    """
    train_path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                              "data", "raw", "used_car_train_20200313.csv")

    print("="*70)
    print("  真实数据 MAE 评测 — 天池训练集 15万条")
    print("="*70)

    # 解析
    print("\n[1/4] 解析训练集...")
    df = parse_tianchi(train_path)

    # 清洗
    print("\n[2/4] 清洗...")
    df = clean_train_data(df)
    print(f"  Cleaned: {len(df):,} rows")

    # 抽样（分层：按年份 + 品牌）
    print(f"\n[3/4] 抽样 {n_samples} 条（分层: 年份 + 品牌高频）...")
    # 选高频品牌 + 年份不太老的
    top_brands = df["brand_label"].value_counts().head(10).index
    sample_pool = df[df["brand_label"].isin(top_brands) & (df["reg_year"] >= 2008)]
    # 限制年份不要太老（>=2008年），不然全是报废价
    sample = sample_pool.sample(n=min(n_samples, len(sample_pool)), random_state=42)

    # 估值
    print(f"\n[4/4] LLM 估值对比...")
    results = []
    errors_abs = []
    errors_pct = []

    for i, (_, row) in enumerate(sample.iterrows()):
        brand = row.get("brand_label", "未知")
        model = f"车型编码{int(row['model'])}" if pd.notna(row.get("model")) else "未知"
        year = int(row["reg_year"])
        mileage = float(row["mileage_km"])
        actual_price_yuan = float(row["price"])  # 元

        cleaned = clean_single_input(brand, model, year, mileage)
        if not cleaned["valid"]:
            continue

        result = valuate(cleaned)
        log_valuation(result)

        if not result.get("ok"):
            continue

        v = result["valuation"]
        # LLM 输出的是万元，转成元
        estimated_yuan = (v["price_low"] + v["price_high"]) / 2 * 10000
        abs_error = abs(estimated_yuan - actual_price_yuan)
        pct_error = abs_error / actual_price_yuan * 100 if actual_price_yuan > 0 else float("inf")

        errors_abs.append(abs_error)
        if actual_price_yuan > 100:  # 过滤掉极低价
            errors_pct.append(pct_error)

        results.append({
            "brand": brand,
            "year": year,
            "mileage_km": mileage,
            "actual_yuan": actual_price_yuan,
            "estimated_yuan": estimated_yuan,
            "abs_error": abs_error,
            "pct_error": pct_error,
            "confidence": v.get("confidence", 0),
            "elapsed": result["elapsed_sec"],
        })

        print(f"  [{len(results):02d}] {brand:16s} {year}年 {mileage/10000:.1f}万km | "
              f"实际:{actual_price_yuan:>8.0f}元 | 估算:{estimated_yuan:>8.0f}元 | "
              f"误差:{abs_error:>6.0f}元 ({pct_error:.0f}%) | {v.get('confidence',0):.0%}")

    # 汇总
    print(f"\n{'='*70}")
    print(f"  评测汇总")
    print(f"{'='*70}")
    print(f"  有效估值: {len(results)} / {n_samples}")

    if errors_abs:
        mae = np.mean(errors_abs)
        mae_wan = mae / 10000
        rmse = np.sqrt(np.mean(np.array(errors_abs)**2))

        print(f"\n  MAE (Mean Absolute Error):")
        print(f"    {mae:,.0f} 元 = {mae_wan:.2f} 万元")
        print(f"  RMSE: {rmse:,.0f} 元")

        valid_pct_errors = [e for e in errors_pct if e < float("inf")]
        if valid_pct_errors:
            mape = np.mean(valid_pct_errors)
            acc_30 = sum(1 for e in errors_pct if e < 30) / len(errors_pct) * 100
            print(f"\n  MAPE: {mape:.1f}%")
            print(f"  Accuracy (误差<30%): {acc_30:.0f}%")

        # 置信度 vs 误差
        confs = [r["confidence"] for r in results]
        avg_conf = np.mean(confs)
        print(f"\n  平均置信度: {avg_conf:.2%}")
        print(f"  平均耗时: {np.mean([r['elapsed'] for r in results]):.1f}s")

    # 面试话术
    print(f"\n  【面试要点】")
    print(f"  1. 数据集: 天池真实成交记录15万条，含31个特征(15个匿名)")
    print(f"  2. 评价指标: MAE (Mean Absolute Error)，天池官方指标")
    print(f"  3. MAE={mae/10000:.2f}万元 — 对二手车估价来说，误差在1-2万以内即为良好")
    print(f"  4. 实际价格分布: mean={df['price'].mean():.0f}元, median={df['price'].median():.0f}元")
    print(f"  5. 数据脱敏挑战: brand/model编码化，LLM只能依赖年份+里程+功率判断")
    print(f"{'='*70}")

    # 保存结果
    out_path = os.path.join(os.path.dirname(__file__), "real_eval_report.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "n_samples": n_samples,
            "n_valid": len(results),
            "mae_yuan": round(mae, 0),
            "mae_wan": round(mae_wan, 2),
            "rmse_yuan": round(rmse, 0),
            "avg_confidence": round(avg_conf, 3),
            "results": results,
        }, f, ensure_ascii=False, indent=2)
    print(f"  报告已保存: {out_path}")


if __name__ == "__main__":
    evaluate_real(n_samples=30)
