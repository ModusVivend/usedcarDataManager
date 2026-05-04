# 🚗 二手车智能估价系统

> 基于 DeepSeek 大模型的二手车智能估价系统 — 懂车帝「检测产品实习生」岗位作品

[![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io/)
[![DeepSeek](https://img.shields.io/badge/DeepSeek-536DFE?logo=openai&logoColor=white)](https://deepseek.com/)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue)](https://python.org/)

## 📖 项目故事

接到这个任务时，我思考了一个问题：**一个合格的二手车估价系统，除了"能估价"，还应该具备什么？**

答案是一个**数据闭环**：

```
输入 → 清洗 → 估值 → BadCase检测 → 根因分析 → 改进Prompt → 重新验证
```

这正是懂车帝检测产品团队日常工作的缩影：用大模型处理非标数据 → 发现 BadCase → 分析根因 → 优化模型/标注/Prompt → 上线验证。

下面是我沿这条链路做的工作。

---

## 🏗 系统架构

```
┌─────────────┐
│  Streamlit   │  交互式 Demo
│  前端        │  单条估价 / 批量CSV / BadCase面板
└──────┬───────┘
       │
┌──────▼───────┐
│  Cleaner     │  数据清洗管道
│  + Parser    │  pandas + 品牌模糊匹配 + 异常值检测
└──────┬───────┘
       │
┌──────▼───────┐
│  Valuation   │  6因子 CoT 估值引擎
│  + Prompt    │  DeepSeek API + Few-shot + 置信度
└──────┬───────┘
       │
┌──────▼───────┐
│  BadCase     │  自动检测 (6规则) + JSONL日志
│  分析        │  根因分类 (Type A/B/C/D)
└──────┬───────┘
       │
┌──────▼───────┐
│  Evaluate    │  MAE/MAPE/区间重叠率 评测
│  评测        │  Prompt A/B 对比实验
└──────────────┘
```

## 📊 核心能力展示

### 1. 数据清洗

**数据源**: 天池二手车数据集（15万条真实成交记录 + 30个特征）

| 清洗步骤 | 处理方式 | 效果 |
|---------|---------|------|
| 品牌规范化 | 55品牌中英文别名库 + 模糊匹配 | 匹配率 99%+ |
| 缺失值 | 中位数/众数填充 | 自动报告 |
| 异常值 | IQR + 阈值规则 | 2825条里程异常自动修复 |
| 脱敏解码 | bodyType/fuelType/gearbox 编码→中文 | 100%解码 |
| 单位统一 | 智能识别公里/万公里 | 自动转换 |

### 2. Prompt 工程

估值 Prompt 的进化过程：

| 版本 | 技术 | MAPE |
|------|------|------|
| v1 简化版 | 基础 System Prompt + 直接输出价格 | ~25% |
| v2 优化版 | CoT 推理 + 6因子分析 + Few-shot + JSON Schema + 置信度 | ~15% |

**v2 Prompt 结构**：
- **System Prompt**: 资深评估师角色 + 多因子估值方法论
- **Chain-of-Thought**: 强制逐因子分析再综合定价
- **Few-shot**: 3个校准样本（丰田卡罗拉、宝马3系、比亚迪秦PLUS）
- **JSON Schema**: 严格结构化输出（price_low/high, confidence, factor_analysis, warnings）
- **兜底机制**: LLM 异常时自动切换折旧公式

### 3. BadCase 分析

建立了 4 类根因分类体系：

| Type | 名称 | 检测信号 | 改进策略 |
|------|------|---------|---------|
| A | 模型知识偏差 | 高置信度 + 高误差 | 补充 Few-shot |
| B | 输入信息歧义 | 品牌匹配失败/单位混淆 | 扩充别名库 |
| C | 推理逻辑缺陷 | 低置信度 + 定价合理 | 优化 CoT 步骤 |
| D | 期望值偏差 | 估值合理但 APE 高 | 校准标注标准 |

自动检测规则：低置信度 / 价格区间过大 / 价格倒挂 / 异常低价 / 高里程未标注 / Fallback触发

### 4. 评测体系

**指标**:
- **MAE** (Mean Absolute Error) — 天池官方指标
- **MAPE** — 百分比误差
- **区间重叠率** — 估值区间是否覆盖真实价格
- **BadCase 触发率** — 自动检测命中比例

**对比实验**: 简化版 vs 优化版 Prompt 的 A/B 测试

---

## 🚀 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置 API Key
cp .env.example .env  # 编辑填入 DEEPSEEK_API_KEY

# 3. 启动 Demo
streamlit run app.py

# 4. 运行评测（需先下载天池数据集）
python eval/evaluate_real.py
```

## 📁 项目结构

```
├── app.py                          # Streamlit 前端
├── src/
│   ├── brands.py                   # 55品牌数据库 + 模糊匹配
│   ├── cleaner.py                  # 数据清洗管道
│   ├── tianchi_parser.py           # 天池数据集解析器
│   ├── api_client.py               # DeepSeek API 封装
│   ├── prompt.py                   # Prompt 模板 (CoT+Few-shot)
│   ├── valuation.py                # 估值引擎
│   └── badcase.py                  # BadCase 检测 + 分析
├── eval/
│   ├── evaluate.py                 # 评测脚本 (模拟数据)
│   ├── evaluate_real.py            # 评测脚本 (真实数据)
│   ├── prompt_ab_test.py           # Prompt A/B 对比实验
│   ├── badcase_analysis.py         # BadCase 根因分析
│   └── test_cases.json             # 15条测试用例
├── data/
│   ├── raw/                        # 原始数据 (天池CSV)
│   ├── generate_mock_data.py       # 模拟数据生成器
│   └── run_real_pipeline.py        # 真实数据管道
└── requirements.txt
```

## 🔧 技术栈

| 层 | 技术 | 说明 |
|---|---|---|
| 数据 | pandas / NumPy | 数据清洗、特征工程 |
| 模型 | DeepSeek Chat | LLM 智能估价 |
| 前端 | Streamlit | 交互式 Demo |
| 评测 | Python 脚本 | MAE/MAPE/区间重叠率 |
| 部署 | Streamlit Cloud | 在线 Demo |

## 💡 面试亮点

1. **不是 demo 而是系统**: 有清洗→估值→BadCase→评测的完整闭环
2. **用真实数据说话**: 天池15万条数据集，不是 mock
3. **Prompt 可量化**: 简化版 vs 优化版的 A/B 对比数字
4. **BadCase 有方法论**: 4类根因分类体系，不是"这里错了"
5. **懂评测指标**: MAE + MAPE + 区间重叠率，理解天池赛题的评分逻辑
