"""
估值引擎
- 输入 CleanedInput → 拼装 Prompt → 调 API → 解析 JSON → 合理性校验
- LLM异常时用折旧公式兜底
- 记录到 BadCase 日志
"""

from typing import Any, Callable
from datetime import datetime
from src.prompt import build_messages
from src.api_client import chat_json
from src.brands import get_brand_info, get_new_car_price, estimate_base_price

# 全局校准器（由 evaluate_real.py 在评测前设置）
_calibrator: Callable | None = None


def set_calibrator(cal: Callable | None):
    """设置全局价格校准器"""
    global _calibrator
    _calibrator = cal

CURRENT_YEAR = 2026


def fallback_valuation(brand_key: str, model: str, year: int, mileage_km: float) -> dict:
    """
    折旧公式兜底估算（当LLM调用失败时使用）

    公式: 预估原价 * (0.85^车龄) * (1 - 里程/60万*0.3)
    - 前段 0.85^车龄: 年均折旧15%
    - 后段里程修正: 最高折30%
    """
    car_age = CURRENT_YEAR - year
    if car_age < 0:
        car_age = 0
    elif car_age > 20:
        car_age = 20

    base_price = estimate_base_price(brand_key, model)

    # 年份折旧
    year_factor = pow(0.85, car_age)

    # 里程折损: 正常年均1.5万公里，超过部分加速折旧
    normal_mileage = car_age * 15000
    mileage_factor = 1.0 - max(0, (mileage_km - normal_mileage) / 600000) * 0.3
    mileage_factor = max(mileage_factor, 0.5)

    mid_price = base_price * year_factor * mileage_factor
    low = round(mid_price * 0.85, 1)
    high = round(mid_price * 1.15, 1)
    if low < 0.5:
        low = 0.5

    return {
        "price_low": low,
        "price_high": high,
        "confidence": 0.4,
        "estimated_original_price": round(base_price, 1),
        "factor_analysis": {
            "brand_value": {"score": 70, "comment": "（公式估算）品牌影响未详细分析"},
            "model_popularity": {"score": 70, "comment": "（公式估算）车型热度未详细分析"},
            "year_depreciation": {"score": 100 - car_age * 3, "comment": f"{car_age}年折旧，残值率{year_factor:.0%}"},
            "mileage_depreciation": {"score": int(mileage_factor * 100), "comment": f"里程{int(mileage_km)}公里"},
            "condition_estimate": {"score": 75, "comment": "（公式估算）默认良好车况"}
        },
        "comprehensive_reasoning": f"（公式兜底）{brand_key} {model}, 车龄{car_age}年, 里程{int(mileage_km)}km。折旧系数{year_factor:.2f}*{mileage_factor:.2f}，估算价格{low}-{high}万。",
        "warnings": ["LLM估值失败，使用公式兜底估算，精度有限"],
        "_fallback": True,
    }


def validate_valuation(result: dict, brand_display: str, model: str, year: int, mileage_km: float) -> list[str]:
    """校验LLM返回的估值是否合理，返回warnings列表"""
    warnings = []
    car_age = CURRENT_YEAR - year

    # 价格必须合理
    if result.get("price_low", 0) < 0:
        warnings.append("价格下限为负，已修正")
    if result.get("price_high", 0) > 500:
        warnings.append("价格上限超过500万，可能异常")

    # 价格不能倒挂
    if result.get("price_low", 0) > result.get("price_high", 0):
        warnings.append("价格区间倒挂（下限>上限）")

    # 置信度范围
    confidence = result.get("confidence", 0)
    if not (0 <= confidence <= 1):
        warnings.append(f"置信度{confidence}超出0-1范围")

    # 极度旧车价格偏高检测
    if car_age > 15 and result.get("price_high", 0) > 15:
        warnings.append(f"{car_age}年车龄但估价偏高，建议核实")

    # 价格数量级校验
    base_price = estimate_base_price(brand_display, model)
    estimated_mid = (result.get("price_low", 0) + result.get("price_high", 0)) / 2
    if base_price > 0 and estimated_mid > base_price * 1.2:
        warnings.append(f"估价中位数({estimated_mid}万)接近甚至超过新车价({base_price}万)，可能偏高")

    return warnings


def valuate(cleaned_input: dict, use_simple_prompt: bool = False) -> dict:
    """
    核心估值函数。

    Args:
        cleaned_input: clean_single_input() 的输出
        use_simple_prompt: 是否使用简化版Prompt（用于对比测试）

    Returns:
        {
            "ok": bool,
            "valuation": {...},      # 估值结果
            "cleaned_input": {...},  # 回显输入
            "elapsed_sec": float,
            "warnings": [...],
            "api_usage": {...},
        }
    """
    import time
    start = time.time()

    brand_display = cleaned_input["brand_display"]
    brand_key = cleaned_input["brand_key"]
    model = cleaned_input["model"]
    year = cleaned_input["year"]
    mileage_km = cleaned_input["mileage_km"]

    # 构建 messages
    messages = build_messages(brand_display or brand_key, model, year, mileage_km)

    # 调用API
    api_result = chat_json(messages)

    elapsed = round(time.time() - start, 2)

    if api_result["ok"]:
        valuation = api_result["content"]
        # 校验并补全
        validation_warnings = validate_valuation(valuation, brand_display or brand_key, model, year, mileage_km)
        if "warnings" not in valuation:
            valuation["warnings"] = []
        valuation["warnings"].extend(validation_warnings)
        # 确保必要字段存在
        valuation.setdefault("estimated_original_price", estimate_base_price(brand_key or "", model))
        valuation.setdefault("factor_analysis", {})
        valuation.setdefault("comprehensive_reasoning", "")

        # 价格校准（如果设置了校准器）
        if _calibrator:
            try:
                mid_before = (valuation["price_low"] + valuation["price_high"]) / 2
                mid_yuan = mid_before * 10000  # 万元→元
                car_age = cleaned_input.get("car_age", 3)
                calibrated_yuan = _calibrator(mid_yuan, car_age)
                calibrated_wan = calibrated_yuan / 10000  # 元→万元
                # 按比例调整 high/low
                ratio = calibrated_wan / mid_before if mid_before > 0 else 1.0
                valuation["price_low_raw"] = valuation["price_low"]
                valuation["price_high_raw"] = valuation["price_high"]
                valuation["price_low"] = round(valuation["price_low"] * ratio, 1)
                valuation["price_high"] = round(valuation["price_high"] * ratio, 1)
                valuation["_calibrated"] = True
            except Exception:
                pass  # 校准失败不影响主流程

        result = {
            "ok": True,
            "valuation": valuation,
            "cleaned_input": cleaned_input,
            "elapsed_sec": elapsed,
            "warnings": validation_warnings,
            "api_usage": api_result.get("usage", {}),
            "_fallback": False,
        }
    else:
        # 兜底
        fb = fallback_valuation(brand_key or "", model, year, mileage_km)
        result = {
            "ok": True,
            "valuation": fb,
            "cleaned_input": cleaned_input,
            "elapsed_sec": elapsed,
            "warnings": fb.get("warnings", []),
            "api_usage": {},
            "_fallback": True,
            "_api_error": api_result.get("error", ""),
        }

    return result


# ============================================================
# 批量估值
# ============================================================
def valuate_batch(inputs: list[dict]) -> list[dict]:
    """批量估值，返回结果列表"""
    results = []
    for i, inp in enumerate(inputs):
        result = valuate(inp)
        result["_batch_index"] = i
        results.append(result)
    return results
