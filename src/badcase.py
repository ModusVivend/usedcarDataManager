"""
BadCase 分析模块
- 自动检测规则：价格偏离、置信度低、价格倒挂
- JSONL 日志记录
- 统计分析报告
"""

import json
import os
from datetime import datetime
from typing import Any

LOG_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "processed", "valuation_log.jsonl")


def ensure_log_dir():
    """确保日志目录存在"""
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)


def log_valuation(result: dict):
    """将估值结果追加写入 JSONL 日志"""
    ensure_log_dir()
    record = {
        "timestamp": datetime.now().isoformat(),
        "cleaned_input": result.get("cleaned_input", {}),
        "valuation": result.get("valuation", {}),
        "elapsed_sec": result.get("elapsed_sec", 0),
        "is_fallback": result.get("_fallback", False),
        "api_error": result.get("_api_error", ""),
        "warnings": result.get("warnings", []),
    }
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


# ============================================================
# BadCase 检测规则
# ============================================================

def detect_badcases(valuation_result: dict) -> list[dict]:
    """
    对单条估值结果运行所有检测规则，返回触发的BadCase列表。

    每条BadCase格式: {"rule": "规则名", "severity": "high|medium|low", "detail": "详细说明"}
    """
    badcases = []
    valuation = valuation_result.get("valuation", {})
    inp = valuation_result.get("cleaned_input", {})

    price_low = valuation.get("price_low", 0)
    price_high = valuation.get("price_high", 0)
    confidence = valuation.get("confidence", 0)
    est_original = valuation.get("estimated_original_price", 0)

    car_age = inp.get("car_age", 0) or 0
    mileage_km = inp.get("mileage_km", 0) or 0

    # Rule 1: 置信度过低
    if confidence < 0.6:
        badcases.append({
            "rule": "low_confidence",
            "severity": "high",
            "detail": f"置信度仅{confidence}，低于0.6阈值，估值结果可靠性存疑"
        })

    # Rule 2: 估价区间过大 (>中位数的40%)
    mid_price = (price_low + price_high) / 2 if (price_low + price_high) > 0 else 0
    if mid_price > 0 and (price_high - price_low) / mid_price > 0.4:
        badcases.append({
            "rule": "wide_price_range",
            "severity": "medium",
            "detail": f"价格区间{(price_high - price_low):.1f}万 (跨度{(price_high - price_low)/mid_price*100:.0f}%)，估值不确定性高"
        })

    # Rule 3: 估价超过新车价
    if est_original > 0 and price_high > est_original * 1.1:
        badcases.append({
            "rule": "price_exceeds_new",
            "severity": "high",
            "detail": f"估价上限{price_high}万超过新车指导价{est_original}万，可能存在价格倒挂"
        })

    # Rule 4: 极低价格但信息不足
    if price_low < 2 and car_age < 10:
        badcases.append({
            "rule": "suspicious_low_price",
            "severity": "medium",
            "detail": f"车龄{car_age}年但估价低至{price_low}万，需确认是否有重大事故"
        })

    # Rule 5: 里程极高 (>年均3万公里 且 未标注warning)
    if car_age > 0 and mileage_km / car_age > 30000:
        if "里程" not in str(valuation.get("warnings", "")) and "使用强度" not in str(valuation.get("warnings", "")):
            badcases.append({
                "rule": "high_mileage_not_flagged",
                "severity": "low",
                "detail": f"年均里程{mileage_km/car_age:.0f}公里偏高，但LLM未在warnings中标注"
            })

    # Rule 6: Fallback触发
    if valuation_result.get("_fallback"):
        badcases.append({
            "rule": "fallback_used",
            "severity": "high",
            "detail": f"LLM调用失败使用公式兜底: {valuation_result.get('_api_error', '')}"
        })

    return badcases


# ============================================================
# 日志分析
# ============================================================

def analyze_logs() -> dict:
    """
    分析所有估值日志，输出统计报告。

    Returns:
        {
            "total_records": int,
            "fallback_rate": float,
            "avg_confidence": float,
            "badcase_distribution": {"rule_name": count, ...},
            "severity_distribution": {"high": count, ...},
            "recent_issues": [...],
        }
    """
    if not os.path.exists(LOG_FILE):
        return {"total_records": 0, "message": "暂无估值日志"}

    records = []
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

    if not records:
        return {"total_records": 0, "message": "日志为空或解析失败"}

    # 基础统计
    total = len(records)
    fallback_count = sum(1 for r in records if r.get("is_fallback"))
    fallback_rate = fallback_count / total if total > 0 else 0

    confidences = [r.get("valuation", {}).get("confidence", 0) for r in records if not r.get("is_fallback")]
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0

    # BadCase 分布
    badcase_dist = {}
    severity_dist = {"high": 0, "medium": 0, "low": 0}
    recent_issues = []

    for r in records:
        # 重新构建result格式以复用detect_badcases
        fake_result = {
            "valuation": r.get("valuation", {}),
            "cleaned_input": r.get("cleaned_input", {}),
            "_fallback": r.get("is_fallback"),
            "_api_error": r.get("api_error"),
        }
        badcases = detect_badcases(fake_result)
        for bc in badcases:
            badcase_dist[bc["rule"]] = badcase_dist.get(bc["rule"], 0) + 1
            severity_dist[bc["severity"]] = severity_dist.get(bc["severity"], 0) + 1
            if bc["severity"] == "high":
                recent_issues.append({
                    "timestamp": r.get("timestamp", ""),
                    "rule": bc["rule"],
                    "detail": bc["detail"],
                })

    # 最近的高严重性问题（取最新5条）
    recent_issues.sort(key=lambda x: x["timestamp"], reverse=True)
    recent_issues = recent_issues[:5]

    return {
        "total_records": total,
        "fallback_rate": round(fallback_rate, 3),
        "avg_confidence": round(avg_confidence, 3),
        "badcase_distribution": badcase_dist,
        "severity_distribution": severity_dist,
        "recent_issues": recent_issues,
    }


def print_analysis_report(report: dict):
    """打印分析的格式化报告"""
    print(f"\n{'='*60}")
    print(f"  BadCase 分析报告")
    print(f"{'='*60}")

    if report.get("total_records", 0) == 0:
        print(f"  {report.get('message', '无数据')}")
        print(f"{'='*60}\n")
        return

    print(f"  总估值记录: {report['total_records']}")
    print(f"  Fallback率: {report['fallback_rate']:.1%}")
    print(f"  平均置信度: {report['avg_confidence']:.2f}")
    print(f"\n  BadCase 分布:")
    for rule, count in sorted(report.get("badcase_distribution", {}).items(), key=lambda x: -x[1]):
        print(f"    - {rule}: {count} 次")
    print(f"\n  严重度分布:")
    for severity, count in sorted(report.get("severity_distribution", {}).items()):
        print(f"    - {severity}: {count} 次")

    if report.get("recent_issues"):
        print(f"\n  最近高危问题:")
        for issue in report["recent_issues"]:
            print(f"    [{issue['timestamp'][:19]}] {issue['rule']}: {issue['detail'][:60]}...")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    report = analyze_logs()
    print_analysis_report(report)
