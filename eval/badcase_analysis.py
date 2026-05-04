"""
BadCase 根因分析 & 分类体系

面试核心：展示 BadCase 分析方法论
- 不是简单统计"哪里错了"
- 而是要回答：错在哪里 → 为什么会错 → 怎么修

分类体系（4大类）：
  Type A - 模型知识偏差: LLM 对该车型市场行情不了解
  Type B - 输入信息歧义: 品牌/车型匹配错误，或信息不足以估值
  Type C - 推理逻辑缺陷: LLM 的推理链有问题（如折旧计算错误）
  Type D - 期望值不合理: 测试用例的 expected_price 本身有偏差
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from datetime import datetime

# ============================================================
# BadCase 类型定义
# ============================================================

BADCASE_TYPES = {
    "A": {
        "name": "模型知识偏差",
        "description": "LLM 对该车型的市场行情、保值率、折旧曲线存在知识盲区或过时认知",
        "typical_signals": [
            "价格严重偏离合理范围（APE>50%）且置信度正常",
            "对冷门车型（法系/小品牌）的估值偏差大",
            "对新能源车新势力的折旧理解不准确",
        ],
        "fix_strategy": "补充 Few-shot 样本、增加该车型的市场数据到 Prompt",
    },
    "B": {
        "name": "输入信息歧义",
        "description": "品牌模糊匹配错误、车型名歧义、或缺失关键信息（如车况）",
        "typical_signals": [
            "品牌别名未识别导致使用了错误品牌",
            "车型名在不同品牌间重复（如多个品牌都有 X5）",
            "里程单位混淆（公里 vs 万公里）",
        ],
        "fix_strategy": "扩充品牌别名库、增加车型消歧逻辑、加强输入校验提示",
    },
    "C": {
        "name": "推理逻辑缺陷",
        "description": "LLM 的估价推理链有逻辑错误，如折旧率计算、年份理解、价格数量级",
        "typical_signals": [
            "置信度极低（<0.3）但价格其实在合理范围",
            "warning 中提示的问题与实际不符",
            "factor_analysis 中各因子得分自相矛盾",
        ],
        "fix_strategy": "优化 CoT 推理步骤、增加逻辑校验 Prompt、增加反例 Few-shot",
    },
    "D": {
        "name": "期望值偏差",
        "description": "测试用例的 expected_price 不够准确（基于主观判断而非真实成交数据）",
        "typical_signals": [
            "多个人工标注者对同一 case 的价格判断差异大",
            "LLM 的估值看起来合理但 APE 很高",
        ],
        "fix_strategy": "用真实成交数据校准 expected_price、增加标注者间一致性评估",
    },
}

# ============================================================
# 单条 BadCase 诊断
# ============================================================

def diagnose_case(case_result: dict) -> dict:
    """
    对一条评测结果进行根因诊断。

    Args:
        case_result: evaluate_single() 的输出

    Returns:
        {"type": "A|B|C|D", "type_name": "...", "evidence": [...], "suggested_fix": "..."}
    """
    evidence = []
    scores = {"A": 0, "B": 0, "C": 0, "D": 0}

    ape = case_result.get("ape", 0)
    confidence = case_result.get("actual", {}).get("confidence", 0)
    is_fallback = case_result.get("is_fallback", False)
    badcases = case_result.get("badcases", [])
    description = case_result.get("description", "")

    actual_low = case_result.get("actual", {}).get("low", 0)
    actual_high = case_result.get("actual", {}).get("high", 0)
    expected_low = case_result.get("expected", {}).get("low", 0)
    expected_high = case_result.get("expected", {}).get("high", 0)
    actual_mid = (actual_low + actual_high) / 2
    expected_mid = (expected_low + expected_high) / 2

    price_gap = abs(actual_mid - expected_mid)

    # Type A 判断: 高置信度 + 高误差 → 模型对车型不了解
    if confidence > 0.7 and ape > 0.25:
        scores["A"] += 3
        evidence.append(f"置信度{confidence:.0%}但APE{ape*100:.0f}%，模型对该车型估值有系统性偏差")
    if "新能源" in description or "纯电" in description:
        if ape > 0.2:
            scores["A"] += 1
            evidence.append("新能源车型，模型对电池折旧理解可能不准确")

    # Type B 判断: 输入处理问题
    if is_fallback:
        scores["B"] += 2
        evidence.append("触发公式兜底，可能是品牌匹配或API调用问题")
    if case_result.get("input", {}).get("brand") != case_result.get("input", {}).get("brand"):
        scores["B"] += 1
    if "warnings" in str(case_result.get("cleaned_input", {})):
        scores["B"] += 1
        evidence.append("数据清洗阶段有警告，输入数据可能有问题")

    # Type C 判断: 推理问题
    if confidence < 0.3 and ape < 0.3:
        scores["C"] += 2
        evidence.append(f"置信度极低({confidence:.0%})但价格偏差不大({ape*100:.0f}%)，LLM推理自相矛盾")
    if "wide_price_range" in badcases:
        scores["C"] += 1
        evidence.append("价格区间过宽，LLM无法在高低值之间做出合理选择")
    if confidence < 0.2:
        scores["C"] += 2
        evidence.append("置信度低于0.2，LLM对自身推理极度不确定")

    # Type D 判断: 期望值是否合理
    if ape > 0.3 and price_gap > 5 and actual_mid > 0:
        # 检查实际价格是否在常识范围内
        if expected_high < 100 and actual_low > 0:
            scores["D"] += 1
            evidence.append(f"期望价中位{expected_mid}万 vs 实际{actual_mid}万，差距{price_gap:.1f}万，需复核期望值")

    # 确定主类型
    best_type = max(scores, key=scores.get)
    if scores[best_type] == 0:
        best_type = "A"  # 默认归类为知识偏差

    return {
        "case_id": case_result.get("case_id", ""),
        "primary_type": best_type,
        "type_name": BADCASE_TYPES[best_type]["name"],
        "evidence": evidence,
        "suggested_fix": BADCASE_TYPES[best_type]["fix_strategy"],
        "type_scores": scores,
        "ape": round(ape, 4),
        "confidence": confidence,
    }


# ============================================================
# 批量分析 & 报告
# ============================================================

def analyze_eval_results(eval_report_path: str = None) -> dict:
    """分析评测报告中的所有 BadCase，输出分类统计和改进建议"""
    if eval_report_path is None:
        eval_report_path = os.path.join(os.path.dirname(__file__), "eval_report.json")

    if not os.path.exists(eval_report_path):
        print(f"评测报告未找到: {eval_report_path}")
        print("请先运行 evaluate.py 生成评测结果")
        return {}

    with open(eval_report_path, "r", encoding="utf-8") as f:
        report = json.load(f)

    # 从完整评测中获取逐条结果
    # 如果 eval_report.json 不含 results，需要从 test_cases + 重新评估
    # 这里基于已有的 eval_report.json

    print(f"\n{'='*80}")
    print(f"  BadCase 根因分析报告")
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*80}\n")

    print(f"  BadCase 分类体系 (4大类):")
    print(f"  ┌──────┬────────────────────┬──────────────────────────────────┐")
    print(f"  │ Type │ 名称               │ 典型表现                         │")
    print(f"  ├──────┼────────────────────┼──────────────────────────────────┤")
    for key, info in BADCASE_TYPES.items():
        print(f"  │  {key}   │ {info['name']:10s}          │ {info['typical_signals'][0][:34]:34s} │")
    print(f"  └──────┴────────────────────┴──────────────────────────────────┘")

    # 总结指标
    print(f"\n  【评测汇总】")
    print(f"  MAPE: {report.get('mape', 0)*100:.1f}%")
    print(f"  Accuracy (APE<15%): {report.get('accuracy_15pct', 0)*100:.1f}%")
    print(f"  Range Overlap: {report.get('range_overlap_rate', 0)*100:.1f}%")
    print(f"  Fallback: {report.get('fallback_count', 0)} 次")

    results = report.get("results", [])
    if not results:
        print("\n  报告中没有逐条结果数据，跳过逐条诊断。")
        print(f"\n{'='*80}\n")
        return report

    # 逐条诊断
    diagnoses = [diagnose_case(r) for r in results]

    # 分类统计
    type_counts = {"A": 0, "B": 0, "C": 0, "D": 0}
    for d in diagnoses:
        type_counts[d["primary_type"]] += 1

    print(f"\n  【根因分布】")
    for t in ["A", "B", "C", "D"]:
        count = type_counts[t]
        bar = "█" * count
        print(f"  Type {t} ({BADCASE_TYPES[t]['name']}): {count} 条 {bar}")

    # 详细诊断
    print(f"\n  【逐条诊断】")
    for d in diagnoses:
        if d["type_scores"][d["primary_type"]] > 0:
            sev = "🔴" if d["ape"] > 0.3 else ("🟡" if d["ape"] > 0.15 else "🟢")
            print(f"  {sev} [{d['case_id']}] → Type {d['primary_type']}: {d['type_name']}")
            print(f"     APE={d['ape']*100:.1f}% | 置信度={d['confidence']:.0%}")
            for e in d["evidence"]:
                print(f"     · {e}")
            print(f"     建议: {d['suggested_fix']}")

    # 改进建议汇总
    print(f"\n  【改进优先级】")
    if type_counts["A"] > type_counts["C"]:
        print(f"  1. [高] 补充 Few-shot 样本覆盖高频出错车型")
    if type_counts["B"] > 0:
        print(f"  2. [中] 扩充品牌别名库，加强输入校验")
    if type_counts["C"] > 0:
        print(f"  3. [中] 优化 CoT 推理步骤，加入反例")
    if type_counts["D"] > 0:
        print(f"  4. [低] 用真实成交数据校准 expected_price")

    print(f"\n  【面试话术】")
    print(f"  '我把 BadCase 分成了 4 类：模型知识偏差、输入信息歧义、推理逻辑缺陷、期望值偏差。'")
    print(f"  '对于每一类我设计了不同的检测规则和改进策略。比如 Type A 通过增加'")
    print(f"  'Few-shot 样本解决，Type C 通过优化 CoT 推理步骤解决。'")
    print(f"  '这个分类体系可以直接复用到懂车帝的 BadCase 分析工作中。'")
    print(f"{'='*80}\n")

    # 保存
    out_path = os.path.join(os.path.dirname(__file__), "badcase_diagnosis.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "type_summary": type_counts,
            "diagnoses": diagnoses,
        }, f, ensure_ascii=False, indent=2)
    print(f"  诊断结果已保存: {out_path}")

    return report


if __name__ == "__main__":
    analyze_eval_results()
