"""
下载真实二手车数据集
数据来源: Kaggle Playground Series S4E9 (2024)
- 188K 训练集 + 125K 测试集
- 字段: brand, model, year, mileage, price, fuel_type, engine, transmission 等
"""
import os
import sys
import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(__file__), "raw")
URL_KAGGLE_TRAIN = "https://raw.githubusercontent.com/playground-series/s4e9/main/train.csv"

# Kaggle S4E9 的 GitHub mirror（更可靠）
GITHUB_MIRROR_BASE = "https://huggingface.co/datasets/playground-series/s4e9/resolve/main"


def download_kaggle(use_kagglehub: bool = True) -> str | None:
    """通过 kagglehub 下载"""
    try:
        import kagglehub
        path = kagglehub.dataset_download("playground-series/s4e9")
        # 复制到 data/raw/
        for f in ["train.csv", "test.csv"]:
            src = os.path.join(path, f)
            if os.path.exists(src):
                dst = os.path.join(DATA_DIR, f"kaggle_{f}")
                import shutil
                shutil.copy(src, dst)
                print(f"  Downloaded: {f} -> {dst}")
        return path
    except Exception as e:
        print(f"  kagglehub failed: {e}")
        return None


def download_direct() -> str | None:
    """通过 HuggingFace mirror 直接下载"""
    import urllib.request
    import shutil

    os.makedirs(DATA_DIR, exist_ok=True)

    files = {
        "kaggle_train.csv": f"{GITHUB_MIRROR_BASE}/train.csv",
        "kaggle_test.csv": f"{GITHUB_MIRROR_BASE}/test.csv",
    }

    for filename, url in files.items():
        dst = os.path.join(DATA_DIR, filename)
        if os.path.exists(dst):
            print(f"  Already exists: {filename}")
            continue
        try:
            print(f"  Downloading {filename} from HuggingFace mirror...")
            with urllib.request.urlopen(url, timeout=120) as resp:
                with open(dst, "wb") as f:
                    shutil.copyfileobj(resp, f)
            size_mb = os.path.getsize(dst) / 1024 / 1024
            print(f"  Downloaded: {filename} ({size_mb:.1f} MB)")
        except Exception as e:
            print(f"  Failed to download {filename}: {e}")
            return None

    return DATA_DIR


def preview_data():
    """预览下载的数据"""
    train_path = os.path.join(DATA_DIR, "kaggle_train.csv")
    if not os.path.exists(train_path):
        return

    df = pd.read_csv(train_path)
    print(f"\n{'='*60}")
    print(f"  真实数据集预览 (Kaggle S4E9)")
    print(f"{'='*60}")
    print(f"  总记录数: {len(df):,}")
    print(f"  列数: {len(df.columns)}")
    print(f"  列名: {list(df.columns)}")
    print(f"\n  缺失值统计:")
    print(df.isnull().sum().to_string())
    print(f"\n  前5行:")
    print(df.head().to_string())
    print(f"\n  数值统计:")
    print(df.describe().to_string())
    print(f"{'='*60}\n")

    # 获取品牌列表
    if "brand" in df.columns:
        brands = df["brand"].dropna().unique()
        print(f"  品牌数: {len(brands)}")
        print(f"  品牌列表: {sorted(brands)[:30]}...")


if __name__ == "__main__":
    print("Downloading real used car dataset...")

    # 优先尝试 HuggingFace mirror（无需认证）
    result = download_direct()

    if result is None:
        print("\nDirect download failed, trying kagglehub...")
        result = download_kaggle()

    if result:
        preview_data()
        print(f"\nData saved to: {DATA_DIR}")
    else:
        print("\nAll download methods failed. Using mock data as fallback.")
