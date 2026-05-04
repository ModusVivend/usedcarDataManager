"""
二手车智能估价系统 — Streamlit 交互式 Demo
"""

import streamlit as st
import pandas as pd
import json
import os
import sys

# 确保项目根目录在 path 中
sys.path.insert(0, os.path.dirname(__file__))

from src.cleaner import clean_single_input, load_data, clean_data, print_cleaning_report
from src.valuation import valuate
from src.badcase import log_valuation, analyze_logs, detect_badcases, print_analysis_report
from src.brands import BRANDS, get_brand_info, get_new_car_price, fuzzy_match_brand, normalize_brand
from src.models_db import get_series_names, get_trims, get_price_range, generate_years, get_transmissions, get_series_configs

st.set_page_config(
    page_title="二手车智能估价",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# 可选项常量
# ============================================================
TRANSMISSION_OPTIONS = ["", "手动 (MT)", "自动 (AT)", "CVT无级变速", "双离合 (DCT)", "AMT", "手动/自动一体"]
EMISSION_OPTIONS = ["", "国IV", "国V", "国VI(A)", "国VI(B)", "欧IV", "欧V", "欧VI", "不明确"]
COLOR_OPTIONS = ["", "白色", "黑色", "银色", "灰色", "红色", "蓝色", "棕色", "金色", "绿色", "其他"]
CONDITION_OPTIONS = ["", "优秀 (准新车,全程4S保养)", "良好 (正常使用,少量划痕)", "一般 (有维修记录)", "较差 (事故车/泡水车)"]
CONFIG_OPTIONS = [
    "天窗", "真皮座椅", "座椅加热/通风", "导航/GPS", "倒车影像",
    "360全景影像", "定速巡航", "自适应巡航", "自动泊车",
    "无钥匙进入/启动", "电动尾门", "LED大灯", "自动空调",
    "后排独立空调", "空气悬架", "四驱", "换挡拨片",
    "HUD抬头显示", "品牌音响", "后排娱乐系统",
]

# ============================================================
# 侧边栏 - 输入区
# ============================================================
with st.sidebar:
    st.title("🚗 二手车智能估价")
    st.markdown("输入车辆详细信息，获取AI多因子智能估价")
    st.markdown("---")

    # ── 基本信息 (级联选择) ──
    st.subheader("📌 基本信息")

    # 品牌列表
    brand_options = sorted([
        f"{info['name_cn']} ({info['name_en']})"
        for info in BRANDS.values()
    ], key=lambda x: x.split("(")[0])

    # Step 1: 品牌
    brand_selected = st.selectbox(
        "品牌 *",
        options=[""] + brand_options,
        help="选择车辆品牌"
    )
    brand_manual = st.text_input("或手动输入品牌", placeholder="如: 奔驰、BMW、大众...")
    raw_brand = brand_manual.strip() or (brand_selected.split("(")[0].strip() if brand_selected else "")
    brand_key = normalize_brand(raw_brand) if raw_brand else None

    # Step 2: 车系（级联品牌）
    if brand_key:
        series_names = get_series_names(brand_key)
        if series_names:
            series = st.selectbox(
                f"车系 * ({len(series_names)}款)",
                options=[""] + series_names,
                help="选择车系"
            )
        else:
            series = st.text_input(
                f"车系 * ({raw_brand}暂无级联数据，请手动输入)",
                placeholder="如: 3系、卡罗拉、Model Y..."
            )
    else:
        series = st.text_input(
            "车系 * (请先选择品牌)" if not raw_brand else f"车系 * (品牌'{raw_brand}'未识别)",
            placeholder="如: 3系、卡罗拉、Model Y...",
            disabled=not raw_brand
        )

    # Step 3: 配置款（级联车系）
    trim_options = []
    if brand_key and series and series in get_series_names(brand_key):
        trims = get_trims(brand_key, series)
        trim_options = [""] + trims

    if trim_options:
        version = st.selectbox(
            "配置款",
            options=trim_options,
            help="选择具体配置版本"
        )
    else:
        version = st.text_input(
            "配置款",
            placeholder="如: 320Li M运动套装、1.2T精英版、长续航全轮驱动版...",
            help="具体的配置版本名称，越详细估价越准"
        )

    # Step 4: 年份（级联车系）
    year_options = []
    if brand_key and series and series in get_series_names(brand_key):
        years = generate_years(brand_key, series)
        year_options = [""] + [str(y) for y in reversed(years)]  # 最新的在前

    if year_options:
        year_str = st.selectbox("上牌年份 *", options=year_options)
        year = int(year_str) if year_str else 2022
    else:
        year = st.number_input("上牌年份 *", min_value=1990, max_value=2026, value=2022)

    # 显示新车指导价参考
    if brand_key and series:
        price_range = get_price_range(brand_key, series)
        if price_range:
            st.caption(f"💰 新车指导价参考: {price_range[0]} - {price_range[1]} 万元")

    # 使用 series 作为 model
    model = series if series else ""

    st.markdown("---")

    # ── 车辆参数 ──
    st.subheader("⚙️ 车辆参数")

    mileage_input = st.text_input("行驶里程 *", placeholder="如: 50000公里 或 5万公里",
                                   help="输入公里或万公里（>=10000视为公里，<10000视为万公里）")

    # 变速箱（级联车系）
    if brand_key and series and series in get_series_names(brand_key):
        trans_options = get_transmissions(brand_key, series)
        trans_label = f"变速箱 ({len(trans_options)}种)"
    else:
        trans_options = TRANSMISSION_OPTIONS
        trans_label = "变速箱"
    transmission = st.selectbox(trans_label, options=[""] + trans_options,
                                 help="变速箱类型影响二手残值")

    emission = st.selectbox("排放标准", options=EMISSION_OPTIONS,
                             help="影响迁入资格和残值")

    col_c, col_co = st.columns(2)
    with col_c:
        color = st.selectbox("车身颜色", options=COLOR_OPTIONS,
                              help="热销色（白/黑）通常更保值")
    with col_co:
        condition = st.selectbox("车况", options=CONDITION_OPTIONS,
                                  help="车况对价格影响最大")

    # 配置选装（级联车系）
    if brand_key and series and series in get_series_names(brand_key):
        config_options = get_series_configs(brand_key, series)
        config_label = f"选装配置 ({series}亮点)"
    else:
        config_options = CONFIG_OPTIONS
        config_label = "选装配置"
    configs = st.multiselect(
        config_label,
        options=config_options,
        help="勾选车辆带有的配置（可多选），高配车溢价明显"
    )
    if configs:
        st.caption(f"已选 {len(configs)} 项: {', '.join(configs[:5])}{'...' if len(configs) > 5 else ''}")

    # 城市
    city = st.text_input("所在城市", placeholder="如: 北京、上海、广州...",
                          help="一线城市通常价格略高")

    st.markdown("---")

    # 估价按钮
    col1, col2 = st.columns(2)
    with col1:
        estimate_btn = st.button("🔍 智能估价", type="primary", use_container_width=True)
    with col2:
        batch_upload = st.file_uploader("📁 批量CSV", type=["csv"], label_visibility="collapsed")

# ============================================================
# 主区域
# ============================================================
tab1, tab2, tab3 = st.tabs(["📊 估价结果", "📋 BadCase分析", "📖 使用说明"])

# ============================================================
# Tab 1: 估价结果
# ============================================================
with tab1:
    if estimate_btn and raw_brand and model and mileage_input:
        # 数据清洗
        cleaned = clean_single_input(raw_brand, model, year, mileage_input)

        # 附加上下文到估值请求
        extra_context = {}
        if version.strip():
            extra_context["version"] = version.strip()
        if transmission:
            extra_context["transmission"] = transmission
        if emission:
            extra_context["emission"] = emission
        if color:
            extra_context["color"] = color
        if condition:
            extra_context["condition"] = condition
        if configs:
            extra_context["configs"] = configs
        if city.strip():
            extra_context["city"] = city.strip()

        if not cleaned["valid"]:
            st.error("❌ 输入数据校验失败")
            for e in cleaned["errors"]:
                st.error(f"  • {e}")
        else:
            with st.spinner("AI正在分析车辆信息..."):
                result = valuate(cleaned, extra_context=extra_context)
                log_valuation(result)

            # 显示警告
            for w in cleaned.get("warnings", []):
                st.warning(f"⚠️ {w}")

            valuation = result["valuation"]

            st.markdown("---")

            # 价格展示
            col_price, col_conf, col_meta = st.columns([2, 1, 1])
            with col_price:
                calibrated_label = ""
                if valuation.get("_calibrated"):
                    raw_low = valuation.get("price_low_raw", valuation["price_low"])
                    raw_high = valuation.get("price_high_raw", valuation["price_high"])
                    calibrated_label = f"<br><span style='font-size:11px;opacity:0.7;'>原始估价: {raw_low}-{raw_high}万 (已校准)</span>"

                st.markdown(f"""
                <div style="text-align:center; padding:20px; background:linear-gradient(135deg,#667eea,#764ba2); border-radius:15px; color:white;">
                    <p style="font-size:14px; margin:0; opacity:0.9;">💰 智能估价区间</p>
                    <h1 style="font-size:48px; margin:10px 0;">{valuation['price_low']} - {valuation['price_high']} 万</h1>
                    <p style="font-size:12px; margin:0; opacity:0.8;">新车指导价约 {valuation.get('estimated_original_price', 'N/A')} 万 {calibrated_label}</p>
                </div>
                """, unsafe_allow_html=True)

            with col_conf:
                confidence = valuation.get("confidence", 0)
                conf_color = "green" if confidence >= 0.8 else ("orange" if confidence >= 0.6 else "red")
                st.markdown(f"""
                <div style="text-align:center; padding:20px; background:#f0f2f6; border-radius:15px;">
                    <p style="font-size:14px; margin:0;">📊 置信度</p>
                    <h1 style="font-size:48px; margin:10px 0; color:{conf_color};">{confidence:.0%}</h1>
                    <p style="font-size:12px; margin:0; color:#666;">
                        {"高置信度" if confidence >= 0.8 else ("中等置信度" if confidence >= 0.6 else "低置信度")}
                    </p>
                </div>
                """, unsafe_allow_html=True)

            with col_meta:
                is_fallback = result.get("_fallback", False)
                st.markdown(f"""
                <div style="text-align:center; padding:20px; background:#f0f2f6; border-radius:15px;">
                    <p style="font-size:14px; margin:0;">⚡ 响应耗时</p>
                    <h1 style="font-size:36px; margin:10px 0;">{result['elapsed_sec']}s</h1>
                    <p style="font-size:12px; margin:0; color:#666;">
                        {"🤖 AI智能评估" if not is_fallback else "📐 公式估算(兜底)"}
                    </p>
                </div>
                """, unsafe_allow_html=True)

            # 车辆信息摘要
            st.markdown("---")
            st.subheader("📋 车辆信息摘要")
            summary_parts = [f"**{raw_brand} {model}**"]
            if version.strip():
                summary_parts.append(f"版本: {version.strip()}")
            summary_parts.append(f"{year}年上牌 | 行驶{mileage_input}")
            if transmission:
                summary_parts.append(f"变速箱: {transmission}")
            if emission:
                summary_parts.append(f"排放: {emission}")
            if color:
                summary_parts.append(f"颜色: {color}")
            if condition:
                summary_parts.append(f"车况: {condition}")
            if configs:
                summary_parts.append(f"配置: {len(configs)}项")
            st.markdown(" | ".join(summary_parts))

            # 因子分析
            st.subheader("🔍 多因子分析")
            factor_analysis = valuation.get("factor_analysis", {})
            if factor_analysis:
                factor_data = []
                name_map = {
                    "brand_value": "品牌保值率",
                    "model_popularity": "车型热度",
                    "year_depreciation": "年份折旧",
                    "mileage_depreciation": "里程折损",
                    "condition_estimate": "车况预估",
                    "config_premium": "配置溢价",
                }
                for factor_name, info in factor_analysis.items():
                    display_name = name_map.get(factor_name, factor_name)
                    score = info.get("score", 0) if isinstance(info, dict) else 70
                    comment = info.get("comment", "") if isinstance(info, dict) else str(info)
                    factor_data.append({
                        "因子": display_name,
                        "得分": f"{score}/100",
                        "分析": comment,
                    })

                if factor_data:
                    st.dataframe(
                        pd.DataFrame(factor_data),
                        use_container_width=True,
                        hide_index=True,
                    )

            # 综合推理
            reasoning = valuation.get("comprehensive_reasoning", "")
            if reasoning:
                st.markdown("---")
                st.subheader("🧠 AI综合推理")
                st.info(reasoning)

            # BadCase检测
            st.markdown("---")
            st.subheader("🔎 实时BadCase检测")
            badcases = detect_badcases(result)
            if badcases:
                for bc in badcases:
                    sev_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(bc["severity"], "⚪")
                    st.warning(f"{sev_icon} [{bc['severity'].upper()}] **{bc['rule']}**: {bc['detail']}")
            else:
                st.success("✅ 未检测到BadCase，估值质量良好")

    elif estimate_btn:
        st.warning("请先填写品牌、车型和里程信息")

    # 批量上传处理
    if batch_upload:
        st.markdown("---")
        st.subheader("📋 批量估值结果")
        try:
            df = load_data(batch_upload)
            st.info(f"已加载 {len(df)} 条记录")

            df_clean, report = clean_data(df)
            st.success(f"清洗完成: {report['final_rows']}/{report['original_rows']} 条有效记录")

            max_batch = 5
            if len(df_clean) > max_batch:
                st.warning(f"批量估值限制 {max_batch} 条/次，将处理前 {max_batch} 条")
                df_clean = df_clean.head(max_batch)

            if st.button("🚀 开始批量估价", type="primary"):
                results_list = []
                progress = st.progress(0)
                status = st.empty()

                for i, (_, row) in enumerate(df_clean.iterrows()):
                    status.text(f"正在评估第 {i+1}/{len(df_clean)} 条...")
                    cleaned = clean_single_input(
                        str(row.get("brand", "")),
                        str(row.get("model", "")),
                        int(row.get("year", 0)),
                        float(row.get("mileage", 0)),
                    )
                    if cleaned["valid"]:
                        r = valuate(cleaned)
                        log_valuation(r)
                        results_list.append({
                            "品牌": cleaned["brand_display"],
                            "车型": cleaned["model"],
                            "年份": cleaned["year"],
                            "里程(km)": cleaned["mileage_km"],
                            "估价低(万)": r["valuation"]["price_low"],
                            "估价高(万)": r["valuation"]["price_high"],
                            "置信度": r["valuation"]["confidence"],
                            "API用时(s)": r["elapsed_sec"],
                        })
                    progress.progress((i + 1) / len(df_clean))

                if results_list:
                    st.dataframe(pd.DataFrame(results_list), use_container_width=True, hide_index=True)
                    csv_data = pd.DataFrame(results_list).to_csv(index=False).encode("utf-8")
                    st.download_button("📥 下载结果CSV", csv_data, "valuation_results.csv", "text/csv")
                status.text("批量评估完成!")
        except Exception as e:
            st.error(f"批量处理失败: {e}")

# ============================================================
# Tab 2: BadCase分析
# ============================================================
with tab2:
    st.subheader("📋 BadCase 分析面板")

    col1, col2 = st.columns([1, 2])
    with col1:
        if st.button("🔄 刷新分析", use_container_width=True):
            st.rerun()

        report = analyze_logs()
        if report.get("total_records", 0) > 0:
            st.metric("总估值记录", report["total_records"])
            st.metric("Fallback率", f"{report['fallback_rate']:.1%}")
            st.metric("平均置信度", f"{report['avg_confidence']:.2f}")
        else:
            st.info("暂无估值日志，请先进行估价操作")

    with col2:
        if report.get("total_records", 0) > 0:
            st.markdown("**BadCase分布**")
            badcase_dist = report.get("badcase_distribution", {})
            if badcase_dist:
                df_dist = pd.DataFrame(
                    [{"规则": k, "次数": v} for k, v in sorted(badcase_dist.items(), key=lambda x: -x[1])]
                )
                st.bar_chart(df_dist.set_index("规则"))

            st.markdown("**严重度分布**")
            sev_dist = report.get("severity_distribution", {})
            if sev_dist:
                df_sev = pd.DataFrame(
                    [{"严重度": k, "次数": v} for k, v in sev_dist.items()]
                )
                st.dataframe(df_sev, use_container_width=True, hide_index=True)

            st.markdown("**最近高危问题**")
            for issue in report.get("recent_issues", []):
                st.warning(f"[{issue['timestamp'][:19]}] **{issue['rule']}**: {issue['detail'][:100]}")

# ============================================================
# Tab 3: 使用说明
# ============================================================
with tab3:
    st.markdown("""
    ## 📖 使用说明

    ### 🎯 核心功能
    输入车辆的**品牌、车系、版本、年份、里程、变速箱、配置**等信息，AI将运用多因子估值模型给出智能估价。

    ### 📊 估值方法论
    本系统采用**多因子加权估值模型**：
    1. **品牌保值率** (25%) — 日系最保值，国产新能源折旧快
    2. **车型热度** (20%) — 热门车型二手流通性好
    3. **年份折旧** (25%) — 前3年折旧最快
    4. **里程折损** (15%) — 年均里程越少越好
    5. **车况配置** (10%) — 高配溢价、事故折价
    6. **区域因素** (5%) — 一线城市略高

    ### 💡 数据清洗能力
    - 品牌模糊匹配：支持中英文、别名、近似名
    - 里程智能识别：自动判断"公里"vs"万公里"
    - 异常值拦截：年份超出范围、负里程等

    ### 🔍 BadCase分析
    - 自动检测6类估值异常
    - 4类根因分类体系
    - 每次估价自动记录到JSONL日志

    ### 📁 批量估价
    支持上传CSV文件批量估价（需包含 brand/model/year/mileage 列）

    ### ⚙️ 技术栈
    - **前端**: Streamlit
    - **AI模型**: DeepSeek Chat
    - **数据处理**: pandas + NumPy
    - **评测框架**: MAE/MAPE/区间重叠率
    """)

# ============================================================
# 底部状态栏
# ============================================================
st.markdown("---")
st.markdown(
    "<p style='text-align:center; color:#999; font-size:12px;'>"
    "二手车智能估价系统 v1.0 | Powered by DeepSeek | Built with Streamlit"
    "</p>",
    unsafe_allow_html=True
)
