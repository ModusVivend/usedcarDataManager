# 二手车智能估价系统

> 基于 DeepSeek 大模型的多因子智能估价，2024 年真实交易数据驱动

[![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io/)
[![DeepSeek](https://img.shields.io/badge/DeepSeek-536DFE?logo=openai&logoColor=white)](https://deepseek.com/)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue)](https://python.org/)

## 一句话

输入品牌、车系、配置、年份、里程，AI 给出结构化估价 — 含价格区间、置信度、6 因子分解、风险提示。

## 快速开始

```bash
pip install -r requirements.txt
streamlit run app.py
```

## 评测结果

在 2024 年真实数据集上抽样 40 条评测：

| 指标 | 结果 |
|------|------|
| MAE | 5.52 万 |
| 准确率 (误差<30%) | 70% |
| 常见品牌误差 | 0.1-2 万 (丰田/日产/大众/本田等) |

## 核心能力

### 1. 数据清洗
- 78 个品牌的中英文/别名模糊匹配（大众/VW/Volkswagen → vw）
- 里程智能识别（公里 vs 万公里）
- 异常值自动拦截 + 缺失值填充
- 支持 2024 年真实数据集（品牌名不脱敏、含新能源）

### 2. Prompt 工程
- **CoT 推理**：强制逐因子分析再综合定价
- **6 因子模型**：品牌保值率 / 车型热度 / 年份折旧 / 里程折损 / 车况预估 / 配置溢价
- **Few-shot**：3 个校准样本（卡罗拉/宝马 3 系/比亚迪秦）
- **市场数据注入**：从 2 万条真实记录中提取折旧斜率、品牌保值率，动态注入 System Prompt
- **JSON Schema**：严格结构化输出，100% 可解析

### 3. 价格校准
三种校准策略，解决 LLM 系统性偏差：

| 策略 | 原理 | 效果 |
|------|------|------|
| Ratio | 按车龄分组中位数比例 | 改善 70% |
| Quantile | 百分位映射 | 改善 72% |
| Isotonic | 保序回归 | 最优 |

### 4. BadCase 分析
- **6 条自动检测规则**：低置信度 / 价格区间过大 / 价格倒挂 / 异常低价 / 高里程未标注 / Fallback 触发
- **4 类根因分类**：模型知识偏差 / 输入信息歧义 / 推理逻辑缺陷 / 期望值偏差
- **JSONL 日志**：每次估价自动记录，支持离线分析

### 5. 级联车型选择
品牌 → 车系 → 年款 → 配置款，四级级联下拉：

```
品牌: [宝马 ▼]
  └─ 车系: [3系 ▼] (8款)
       └─ 配置款: [325Li M运动套装 ▼] (11款)
            └─ 年份: [2022 ▼] (自动筛选有效年份)
```

覆盖 18 个品牌、60+ 车系、300+ 真实配置款。变速箱和选装配置也随车系联动。

## 项目结构

```
├── app.py                      # Streamlit 前端
├── src/
│   ├── brands.py               # 78 品牌数据库 + 模糊匹配
│   ├── models_db.py            # 品牌→车系→配置款 级联数据库
│   ├── cleaner.py              # 数据清洗管道
│   ├── dataset_2024.py         # 2024 真实数据集解析器
│   ├── market_stats.py         # 市场统计注入 Prompt
│   ├── calibration.py          # 价格校准层 (3 策略)
│   ├── api_client.py           # DeepSeek API 封装
│   ├── prompt.py               # Prompt 模板 (CoT + Few-shot)
│   ├── valuation.py            # 估值引擎
│   └── badcase.py              # BadCase 检测 + 分析
├── eval/
│   ├── evaluate_2024.py        # 真实数据评测
│   ├── train_calibration.py    # 校准器训练
│   ├── badcase_analysis.py     # BadCase 根因分析
│   ├── prompt_ab_test.py       # Prompt A/B 对比
│   └── test_cases.json         # 15 条测试用例
├── data/
│   ├── raw/                    # 2024 真实数据 (usedCars.csv + used_cars.csv)
│   └── generate_mock_data.py   # 模拟数据生成器
└── requirements.txt
```

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | Streamlit |
| AI 模型 | DeepSeek Chat |
| 数据处理 | pandas + NumPy |
| 评测 | MAE / MAPE / 区间重叠率 |
