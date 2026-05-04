"""
Prompt 模板 & 工程化
- System Prompt: 资深评估师角色 + 多因子估值方法论
- 结构化输出: JSON Schema 约束
- Chain-of-Thought: 逐因子分析 → 综合定价
- Few-shot: 3个校准样本
"""

# ============================================================
# System Prompt — 角色定义 + 估值方法论
# ============================================================
SYSTEM_PROMPT = """你是一位资深二手车评估师，拥有15年从业经验，精通中国市场所有主流品牌的二手车估值。

## 你的估值方法论（多因子加权模型）

你要综合考虑以下因子，按重要性排序：

1. **品牌保值率 (25%)**: 日系（丰田/本田/雷克萨斯）最保值，德系豪华品牌次之，国产新能源折旧较快
2. **车型热度 (20%)**: 热门车型（如卡罗拉、思域、Model Y）保值好，冷门/停售车型折价多
3. **年份折旧 (25%)**: 前3年折旧最快（每年约贬值10-15%），之后逐年放缓。新能源车前3年折旧更快
4. **里程折损 (15%)**: 年均里程越少越好。正常年均1-2万公里。超过3万公里/年加速折旧
5. **车况与配置 (10%)**: 有无事故、保养记录、配置高低（未提供时按"良好"估算）
6. **区域市场 (5%)**: 一线城市（北上广深）价格通常略高，但差异不大

## 估值输出要求

1. 先用 Chain-of-Thought 推理每个因子的得分和影响
2. 预估新车指导价（参考你对中国市场的了解）
3. 综合各因子，计算当前合理市场价区间
4. 给出置信度（0-1），考虑信息完整度
5. 如果感觉输入信息有异常（如里程过低/过高），在 warnings 中提醒

## 中国市场参考基准
- 主流家用车新车指导价: 10-20万
- 主流B级车: 18-28万
- 豪华品牌入门: 25-40万
- 豪华品牌中大型: 45-80万
- 保值神车: 丰田卡罗拉/汉兰达、本田飞度/思域、雷克萨斯ES
- 折旧较快: 法系车（标致/雪铁龙）、部分国产燃油车、早期新能源

## 重要提示
- 只输出合法JSON，不要有任何其他文字
- 价格单位为"万元人民币"
- confidence 取值 0-1，保留两位小数
- 推理要充分但不啰嗦，直击要点
"""

# ============================================================
# JSON Schema — 结构化输出定义
# ============================================================
OUTPUT_SCHEMA_DESC = """
输出以下JSON结构:
{
  "price_low": 数字(万元),  // 合理市场价下限
  "price_high": 数字(万元), // 合理市场价上限
  "confidence": 0.0-1.0,    // 置信度
  "estimated_original_price": 数字(万元), // 估算新车指导价
  "factor_analysis": {
    "brand_value": {"score": 0-100, "comment": "品牌保值率说明"},
    "model_popularity": {"score": 0-100, "comment": "车型热度说明"},
    "year_depreciation": {"score": 0-100, "comment": "年份折旧分析"},
    "mileage_depreciation": {"score": 0-100, "comment": "里程折损分析"},
    "condition_estimate": {"score": 0-100, "comment": "车况预估"}
  },
  "comprehensive_reasoning": "综合推理过程，100字以内",
  "warnings": ["需要注意的问题1", "问题2"]  // 无异常则为空数组
}
"""

# ============================================================
# Few-shot 样本（3个校准案例）
# ============================================================
FEW_SHOT_EXAMPLES = [
    {
        "input": "品牌: 丰田, 车型: 卡罗拉, 年份: 2021, 里程: 4万公里",
        "output": {
            "price_low": 7.5,
            "price_high": 9.0,
            "confidence": 0.88,
            "estimated_original_price": 13.5,
            "factor_analysis": {
                "brand_value": {"score": 95, "comment": "丰田品牌保值率极高，卡罗拉是保值标杆"},
                "model_popularity": {"score": 95, "comment": "全球销冠车型，市场认可度极高，二手流通快"},
                "year_depreciation": {"score": 72, "comment": "2021年至今5年，前3年折旧快进入平缓期"},
                "mileage_depreciation": {"score": 88, "comment": "5年4万公里，年均8千公里，使用强度低"},
                "condition_estimate": {"score": 80, "comment": "正常使用5年，无事故的话车况良好"}
            },
            "comprehensive_reasoning": "卡罗拉作为保值标杆，5年车龄折旧约45%。年均8千公里远低于正常水平，里程优势明显。当前二手市场该车况卡罗拉成交价在7.5-9万之间。",
            "warnings": []
        }
    },
    {
        "input": "品牌: 宝马, 车型: 3系, 年份: 2019, 里程: 10万公里",
        "output": {
            "price_low": 12.0,
            "price_high": 15.5,
            "confidence": 0.82,
            "estimated_original_price": 34.0,
            "factor_analysis": {
                "brand_value": {"score": 85, "comment": "宝马品牌保值率中等偏上，3系是销量主力"},
                "model_popularity": {"score": 90, "comment": "3系是豪华B级车标杆，二手市场需求旺盛"},
                "year_depreciation": {"score": 55, "comment": "2019年已7年车龄，进入折旧深水区"},
                "mileage_depreciation": {"score": 60, "comment": "7年10万公里，年均1.4万公里属正常水平"},
                "condition_estimate": {"score": 65, "comment": "7年车龄需关注发动机和变速箱状态"}
            },
            "comprehensive_reasoning": "宝马3系7年车龄折旧约60-65%，10万公里属于正常使用强度。豪华品牌后期维保成本影响二手价。当前市场行情12-15.5万。",
            "warnings": ["7年车龄德系车建议检查漏油和电子系统"]
        }
    },
    {
        "input": "品牌: 比亚迪, 车型: 秦PLUS, 年份: 2023, 里程: 2万公里",
        "output": {
            "price_low": 6.5,
            "price_high": 8.5,
            "confidence": 0.85,
            "estimated_original_price": 11.0,
            "factor_analysis": {
                "brand_value": {"score": 70, "comment": "比亚迪品牌近年上升明显，但新能源二手车折价仍较快"},
                "model_popularity": {"score": 88, "comment": "秦PLUS销量高，市场保有量大，二手流通性好"},
                "year_depreciation": {"score": 78, "comment": "2023年3年车龄，仍在快速折旧期但已过最陡阶段"},
                "mileage_depreciation": {"score": 90, "comment": "3年2万公里，使用强度很低"},
                "condition_estimate": {"score": 85, "comment": "3年车龄年轻，电池健康度良好"}
            },
            "comprehensive_reasoning": "秦PLUS作为国产新能源代表，3年折旧约35-40%。新车指导价约11万，考虑新能源二手车折价较快和里程优势，当前市场价6.5-8.5万。",
            "warnings": ["新能源汽车需关注电池健康度"]
        }
    }
]


def build_few_shot_messages() -> list:
    """构建 few-shot 示例消息列表"""
    msgs = []
    for ex in FEW_SHOT_EXAMPLES:
        msgs.append({"role": "user", "content": f"请评估以下二手车:\n{ex['input']}"})
        msgs.append({"role": "assistant", "content": json.dumps(ex["output"], ensure_ascii=False)})
    return msgs


def build_user_prompt(brand: str, model: str, year: int, mileage_km: float,
                      city: str = "", condition: str = "", extra: str = "",
                      version: str = "", transmission: str = "", emission: str = "",
                      color: str = "", configs: list[str] | None = None) -> str:
    """
    构建用户估值请求 Prompt。

    参数：
        brand: 品牌显示名（中文）
        model: 车型名称
        year: 上牌年份
        mileage_km: 里程（公里）
        city: 所在城市（可选）
        condition: 车况描述（可选）
        version: 版本/配置款（可选）
        transmission: 变速箱类型（可选）
        emission: 排放标准（可选）
        color: 车身颜色（可选）
        configs: 选装配置列表（可选）
        extra: 额外信息（可选）

    返回完整的用户Prompt字符串
    """
    # 里程显示：智能选择单位
    if mileage_km >= 10000:
        mileage_display = f"{mileage_km / 10000:.1f}万公里 ({mileage_km:.0f}公里)"
    else:
        mileage_display = f"{mileage_km:.0f}公里"

    parts = [
        f"请评估以下二手车:",
        f"  品牌: {brand}",
        f"  车型: {model}",
        f"  上牌年份: {year}年",
        f"  行驶里程: {mileage_display}",
    ]
    if version:
        parts.append(f"  版本/配置款: {version}")
    if transmission:
        parts.append(f"  变速箱: {transmission}")
    if emission:
        parts.append(f"  排放标准: {emission}")
    if color:
        parts.append(f"  车身颜色: {color}")
    if condition:
        parts.append(f"  车况: {condition}")
    if configs:
        parts.append(f"  选装配置: {', '.join(configs)}")
    if city:
        parts.append(f"  所在城市: {city}")
    if extra:
        parts.append(f"  备注: {extra}")

    parts.append(f"\n请按JSON格式输出估值结果。注意：配置越高溢价越多，热销颜色(白/黑)比冷门颜色保值。")
    return "\n".join(parts)


def build_messages(brand: str, model: str, year: int, mileage_km: float,
                   extra_context: dict | None = None) -> list[dict]:
    """
    构建完整的 messages 数组（System + Market Data + Few-shot + User）

    Args:
        extra_context: {version, transmission, emission, color, condition, configs, city, extra}
    """
    ctx = extra_context or {}

    # 动态注入市场数据
    system_content = SYSTEM_PROMPT + "\n\n" + OUTPUT_SCHEMA_DESC
    try:
        from src.market_stats import compute_market_reference
        market_ref = compute_market_reference()
        if market_ref:
            system_content = SYSTEM_PROMPT + "\n\n" + market_ref + "\n\n" + OUTPUT_SCHEMA_DESC
    except Exception:
        pass  # 无法加载市场数据时使用默认 Prompt

    messages = [{"role": "system", "content": system_content}]

    # 添加 few-shot 示例
    for ex in FEW_SHOT_EXAMPLES:
        messages.append({"role": "user", "content": f"请评估以下二手车:\n{ex['input']}"})
        messages.append({"role": "assistant", "content": json.dumps(ex["output"], ensure_ascii=False)})

    # 添加用户实际请求
    user_prompt = build_user_prompt(
        brand, model, year, mileage_km,
        version=ctx.get("version", ""),
        transmission=ctx.get("transmission", ""),
        emission=ctx.get("emission", ""),
        color=ctx.get("color", ""),
        condition=ctx.get("condition", ""),
        configs=ctx.get("configs", []),
        city=ctx.get("city", ""),
        extra=ctx.get("extra", ""),
    )
    messages.append({"role": "user", "content": user_prompt})

    return messages


# 用于对比的简化版 prompt（展示Prompt优化的效果差异）
SIMPLE_SYSTEM_PROMPT = """你是一位二手车评估师。请根据用户提供的车辆信息给出估价。
输出JSON格式: {"price_low": 数字, "price_high": 数字, "reasoning": "简要理由"}。价格单位: 万元。"""


import json  # noqa: E402 (at bottom for few-shot serialization)
