"""
评测脚本
- 加载测试用例
- 逐条调用估值引擎
- 计算 MAPE(平均绝对百分比误差)、准确率(误差<15%)
- 输出格式化评测报告
"""

import json
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.cleaner import clean_single_input
from src.valuation import valuate
from src.badcase import log_valuation, detect_badcases


def load_test_cases(path: str) -> list[dict]:
    """加载测试用例"""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def evaluate_single(case: dict) -> dict:
    """评估单条测试用例"""
    cleaned = clean_single_input(
        case["brand"],
        case["model"],
        case["year"],
        case["mileage_km"],
    )

    if not cleaned["valid"]:
        return {
            "case_id": case["id"],
            "ok": False,
            "error": "; ".join(cleaned["errors"]),
        }

    result = valuate(cleaned)
    log_valuation(result)

    valuation = result["valuation"]
    actual_mid = (valuation["price_low"] + valuation["price_high"]) / 2
    expected_mid = (case["expected_price_low"] + case["expected_price_high"]) / 2

    # 计算APE（绝对百分比误差）
    if expected_mid > 0:
        ape = abs(actual_mid - expected_mid) / expected_mid
    else:
        ape = float("inf")

    # 判断价格区间是否与期望区间有交集
    range_overlap = (
        valuation["price_low"] <= case["expected_price_high"]
        and valuation["price_high"] >= case["expected_price_low"]
    )

    badcases = detect_badcases(result)

    return {
        "case_id": case["id"],
        "ok": True,
        "description": case.get("description", ""),
        "input": {
            "brand": cleaned["brand_display"],
            "model": cleaned["model"],
            "year": cleaned["year"],
            "mileage_km": cleaned["mileage_km"],
        },
        "expected": {
            "low": case["expected_price_low"],
            "high": case["expected_price_high"],
            "mid": round(expected_mid, 1),
        },
        "actual": {
            "low": valuation["price_low"],
            "high": valuation["price_high"],
            "mid": round(actual_mid, 1),
            "confidence": valuation.get("confidence", 0),
        },
        "ape": round(ape, 4),
        "range_overlap": range_overlap,
        "is_fallback": result.get("_fallback", False),
        "elapsed_sec": result["elapsed_sec"],
        "badcases": [bc["rule"] for bc in badcases],
    }


def run_evaluation(test_cases_path: str = "") -> dict:
    """运行完整评测，返回汇总报告"""
    if not test_cases_path:
        test_cases_path = os.path.join(os.path.dirname(__file__), "test_cases.json")

    cases = load_test_cases(test_cases_path)
    print(f"\n{'='*70}")
    print(f"  二手车智能估价 — 评测报告")
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  测试用例数: {len(cases)}")
    print(f"{'='*70}\n")

    results = []
    passed = 0
    failed = 0
    apes = []
    overlap_count = 0
    badcase_count = 0
    fallback_count = 0
    total_time = 0

    for i, case in enumerate(cases):
        print(f"  [{i+1:02d}/{len(cases)}] {case['id']}: {case.get('description', '')}")
        result = evaluate_single(case)

        if not result["ok"]:
            print(f"    [FAIL] {result['error']}")
            failed += 1
            continue

        results.append(result)
        total_time += result["elapsed_sec"]
        ape = result["ape"]
        apes.append(ape)

        if ape < 0.15:
            passed += 1
            flag = "[OK]"
        elif ape < 0.30:
            flag = "[WARN]"
        else:
            flag = "[FAIL]"

        if result["range_overlap"]:
            overlap_count += 1

        if result["badcases"]:
            badcase_count += 1

        if result["is_fallback"]:
            fallback_count += 1

        print(f"    {flag} 期望: {result['expected']['low']}-{result['expected']['high']}万 | "
              f"实际: {result['actual']['low']}-{result['actual']['high']}万 | "
              f"APE: {ape*100:.1f}% | "
              f"置信度: {result['actual']['confidence']:.0%} | "
              f"耗时: {result['elapsed_sec']}s")

        if result["badcases"]:
            print(f"    [BadCase] {', '.join(result['badcases'])}")

    # 汇总统计
    n = len(results)
    mape = sum(apes) / n if n > 0 else float("inf")
    accuracy = passed / n if n > 0 else 0
    overlap_rate = overlap_count / n if n > 0 else 0
    avg_time = total_time / n if n > 0 else 0

    print(f"\n{'='*70}")
    print(f"  评测汇总")
    print(f"{'='*70}")
    print(f"  Valid results: {n} / {len(cases)}")
    print(f"  MAPE: {mape*100:.1f}%")
    print(f"  Accuracy (APE<15%): {accuracy*100:.1f}% ({passed}/{n})")
    print(f"  Range Overlap Rate: {overlap_rate*100:.1f}% ({overlap_count}/{n})")
    print(f"  Avg Time: {avg_time:.2f}s")
    print(f"  Fallback Count: {fallback_count}")
    print(f"  BadCase Triggered: {badcase_count}")
    print(f"{'='*70}\n")

    # 按APE排序，展示最佳和最差
    if results:
        sorted_results = sorted(results, key=lambda x: x["ape"])
        print("  Best (lowest APE):")
        for r in sorted_results[:3]:
            print(f"    {r['case_id']}: APE={r['ape']*100:.1f}% ({r['description']})")

        print("\n  Worst (highest APE):")
        for r in sorted_results[-3:]:
            print(f"    {r['case_id']}: APE={r['ape']*100:.1f}% ({r['description']})")

    print(f"\n{'='*70}\n")

    return {
        "timestamp": datetime.now().isoformat(),
        "total_cases": len(cases),
        "valid_results": n,
        "failed": failed,
        "mape": round(mape, 4),
        "accuracy_15pct": round(accuracy, 4),
        "range_overlap_rate": round(overlap_rate, 4),
        "avg_time_sec": round(avg_time, 2),
        "fallback_count": fallback_count,
        "badcase_trigger_count": badcase_count,
        "results": results,
    }


if __name__ == "__main__":
    report = run_evaluation()
    # 保存报告
    report_path = os.path.join(os.path.dirname(__file__), "eval_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump({k: v for k, v in report.items() if k != "results"}, f, ensure_ascii=False, indent=2)
    print(f"评测报告已保存到: {report_path}")
