"""
天池二手车数据集下载器
- 来源：阿里云天池「二手车交易价格预测」赛题
- 训练集 15万条，测试集 5万条，31个字段
- 真实成交记录：品牌、车系、里程、价格、排放标准、变速箱等

手动下载指南（任选其一）：
1. 天池官方：https://tianchi.aliyun.com/dataset/175540
2. 飞桨AI Studio：https://aistudio.baidu.com/datasetdetail/224712/1
3. 和鲸社区：https://www.heywhale.com/mw/dataset/5eabb56b366f4d002d73f0bd

下载后把 CSV 放到 data/raw/ 目录下，然后运行本脚本自动处理。
"""

import os
import sys
import pandas as pd

DATA_RAW = os.path.join(os.path.dirname(__file__), "raw")


def find_tianchi_files() -> list[str]:
    """自动查找天池数据集文件"""
    if not os.path.exists(DATA_RAW):
        return []

    files = []
    for f in os.listdir(DATA_RAW):
        lower = f.lower()
        if lower.endswith(".csv") and any(kw in lower for kw in ["used_car", "二手车", "train", "test"]):
            files.append(os.path.join(DATA_RAW, f))
    return sorted(files)


def load_and_inspect(filepath: str) -> pd.DataFrame:
    """加载天池数据并输出基本信息"""
    for enc in ["utf-8", "gbk", "gb2312", "gb18030", "utf-8-sig"]:
        try:
            df = pd.read_csv(filepath, encoding=enc)
            break
        except (UnicodeDecodeError, UnicodeError):
            continue
    else:
        df = pd.read_csv(filepath, encoding="utf-8", errors="replace")

    print(f"\n{'='*60}")
    print(f"  文件: {os.path.basename(filepath)}")
    print(f"{'='*60}")
    print(f"  行数: {len(df):,}")
    print(f"  列数: {len(df.columns)}")
    print(f"  列名: {list(df.columns)}")
    print(f"\n  前5行:")
    print(df.head().to_string(max_colwidth=30))
    print(f"\n  缺失值统计 (前15列):")
    missing = df.isnull().sum()
    for col in list(df.columns)[:15]:
        pct = missing[col] / len(df) * 100
        print(f"    {col}: {missing[col]:,} ({pct:.1f}%)")
    print(f"\n  数值列统计:")
    print(df.describe().to_string())
    print(f"{'='*60}\n")

    return df


def compare_with_mock(mock_path: str, real_path: str):
    """
    对比模拟数据与真实数据的关键差异。
    这是面试核心话术素材。
    """
    mock_df = pd.read_csv(mock_path)
    real_df = pd.read_csv(real_path)

    print(f"\n{'='*70}")
    print(f"  数据质量对比分析：模拟数据 vs 真实天池数据")
    print(f"{'='*70}")

    # 价格分布对比
    print(f"\n  【价格分布】")
    for label, df in [("模拟数据", mock_df), ("真实数据", real_df)]:
        price_col = "price" if "price" in df.columns else None
        if price_col and df[price_col].notna().any():
            p = df[price_col].dropna()
            print(f"    {label}: mean={p.mean():.1f}, median={p.median():.1f}, "
                  f"std={p.std():.1f}, skew={p.skew():.2f}, "
                  f"min={p.min():.1f}, max={p.max():.1f}")

    # 缺失率对比
    print(f"\n  【缺失率对比】")
    mock_missing = mock_df.isnull().sum() / len(mock_df) * 100
    real_missing = real_df.isnull().sum() / len(real_df) * 100
    common_cols = set(mock_df.columns) & set(real_df.columns)
    for col in sorted(common_cols):
        print(f"    {col}: 模拟={mock_missing.get(col,0):.1f}% vs 真实={real_missing.get(col,0):.1f}%")

    # 数据规模
    print(f"\n  【数据规模】")
    print(f"    模拟数据: {len(mock_df):,} 条")
    print(f"    真实数据: {len(real_df):,} 条 ({len(real_df)/len(mock_df):.0f}x)")

    # 品牌数量
    if "brand" in mock_df.columns and "brand" in real_df.columns:
        mock_brands = mock_df["brand"].dropna().nunique()
        real_brands = real_df["brand"].dropna().nunique()
        print(f"\n  【品牌覆盖】")
        print(f"    模拟数据: {mock_brands} 个品牌")
        print(f"    真实数据: {real_brands} 个品牌")

    print(f"\n  【面试话术要点】")
    print(f"    1. 真实数据分布是偏态（大量中低价车），模拟用正态分布 → 说明理解真实市场")
    print(f"    2. 真实数据缺失模式反映录入习惯，模拟是随机缺失 → 说明理解数据采集过程")
    print(f"    3. 真实数据有匿名特征(v0-v14)，考验特征工程能力 → 可展开聊")
    print(f"    4. 如果换了真实数据，MAPE可能变化 → 说明理解数据分布影响模型表现")
    print(f"{'='*70}\n")


def main():
    print("="*60)
    print("  天池二手车数据集 — 下载处理工具")
    print("="*60)

    files = find_tianchi_files()
    if not files:
        print("\n未找到天池数据文件。请先手动下载 CSV 放到 data/raw/ 目录。")
        print("\n下载入口（任选其一，国内直连，无需翻墙）：")
        print("  1. 天池官方: https://tianchi.aliyun.com/dataset/175540")
        print("  2. 飞桨AI Studio: https://aistudio.baidu.com/datasetdetail/224712/1")
        print("  3. 和鲸社区: https://www.heywhale.com/mw/dataset/5eabb56b366f4d002d73f0bd")
        print("\n下载文件说明：")
        print("  - used_car_train_20200313.csv   15万条训练集 (~50MB)")
        print("  - used_car_testA_20200313.csv    5万条测试集 (~17MB)")
        print("  - used_car_testB_20200421.csv    5万条测试集 (~17MB)")
        return

    print(f"\n找到 {len(files)} 个数据文件:")
    for f in files:
        print(f"  - {os.path.basename(f)}")

    # 加载并检查每个文件
    dataframes = {}
    for f in files:
        try:
            df = load_and_inspect(f)
            dataframes[os.path.basename(f)] = df
        except Exception as e:
            print(f"  加载失败: {e}")

    # 对比分析
    mock_path = os.path.join(DATA_RAW, "used_car_data.csv")
    if os.path.exists(mock_path) and files:
        compare_with_mock(mock_path, files[0])


if __name__ == "__main__":
    main()
