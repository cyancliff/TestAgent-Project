#!/usr/bin/env python
"""
检查特征向量系统状态（PostgreSQL 版）
"""
import sys
import psycopg2
from app.core.config import settings


def check_db_status():
    """检查数据库中的特征向量状态"""
    try:
        conn = psycopg2.connect(settings.DATABASE_URL)
        cursor = conn.cursor()
    except Exception as e:
        print(f"[ERROR] 无法连接数据库: {e}")
        return False

    try:
        # 检查表结构
        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'atmr_questions'
            ORDER BY ordinal_position
        """)
        columns = [row[0] for row in cursor.fetchall()]

        if not columns:
            print("[ERROR] 表 atmr_questions 不存在")
            return False

        print("[INFO] 数据库表结构:")
        for col in columns:
            print(f"  - {col}")

        # 检查特征向量相关列是否存在
        required_columns = ['feature_vector', 'feature_dim', 'discrimination', 'difficulty']
        missing_columns = [col for col in required_columns if col not in columns]

        if missing_columns:
            print(f"[ERROR] 缺少必要列: {missing_columns}")
            print("[HINT] 请运行: python scripts/migrate_database.py")
            return False
        else:
            print("[OK] 所有特征向量相关列已存在")

        # 统计题目数量
        cursor.execute("SELECT COUNT(*) FROM atmr_questions")
        total = cursor.fetchone()[0]
        print(f"[INFO] 题目总数: {total}")

        # 统计有特征向量的题目数量
        cursor.execute("SELECT COUNT(*) FROM atmr_questions WHERE feature_vector IS NOT NULL")
        with_features = cursor.fetchone()[0]
        print(f"[INFO] 有特征向量的题目: {with_features}")

        # 统计有难度区分度的题目数量
        cursor.execute("SELECT COUNT(*) FROM atmr_questions WHERE difficulty IS NOT NULL AND discrimination IS NOT NULL")
        with_params = cursor.fetchone()[0]
        print(f"[INFO] 有难度区分度的题目: {with_params}")

        # 如果存在特征向量，显示样本
        if with_features > 0:
            cursor.execute("SELECT exam_no, feature_dim, difficulty, discrimination FROM atmr_questions WHERE feature_vector IS NOT NULL LIMIT 3")
            samples = cursor.fetchall()
            print("\n[INFO] 样本特征向量信息:")
            for sample in samples:
                print(f"  - {sample[0]}: 维度={sample[1]}, 难度={sample[2]:.2f}, 区分度={sample[3]:.2f}")

        conn.close()

        # 评估状态
        if total == 0:
            print("\n[ERROR] 数据库中没有题目，请先运行: python scripts/import_data.py")
            return False
        elif with_features == 0:
            print("\n[WARN] 特征向量尚未生成")
            print("[HINT] 请安装依赖后运行: python scripts/generate_feature_vectors.py")
            return False
        elif with_features < total:
            print(f"\n[WARN] 部分题目({with_features}/{total})有特征向量")
            return True
        else:
            print("\n[OK] 所有题目都有特征向量!")
            return True

    except Exception as e:
        print(f"[ERROR] 检查数据库时出错: {e}")
        return False
    finally:
        conn.close()


def check_requirements():
    """检查依赖包状态"""
    print("\n[INFO] 检查依赖包状态:")

    required_packages = ['numpy', 'sklearn', 'sentence_transformers', 'torch', 'psycopg2']
    missing_packages = []

    for package in required_packages:
        try:
            if package == 'sentence_transformers':
                import sentence_transformers
            elif package == 'torch':
                import torch
            elif package == 'psycopg2':
                import psycopg2
            else:
                __import__(package)
            print(f"[OK] {package} 已安装")
        except ImportError:
            print(f"[ERROR] {package} 未安装")
            missing_packages.append(package)

    if missing_packages:
        print(f"\n[WARN] 缺少依赖包: {missing_packages}")
        print(f"[HINT] 请安装依赖: pip install {' '.join(missing_packages)}")
        return False
    else:
        print("\n[OK] 所有依赖包已安装")
        return True


def main():
    print("=" * 50)
    print("[INFO] 特征向量系统状态检查 (PostgreSQL)")
    print("=" * 50)

    # 检查数据库状态
    db_ok = check_db_status()

    # 检查依赖状态
    deps_ok = check_requirements()

    print("\n" + "=" * 50)
    print("[INFO] 状态总结:")

    if not db_ok and not deps_ok:
        print("[ERROR] 系统未就绪")
        print("   1. 安装依赖: pip install -r requirements_feature.txt")
        print("   2. 导入数据: python scripts/import_data.py")
        print("   3. 生成特征向量: python scripts/generate_feature_vectors.py")
        return 1
    elif not db_ok:
        print("[WARN] 数据库状态异常")
        print("   请检查数据库和特征向量生成")
        return 2
    elif not deps_ok:
        print("[WARN] 依赖包未安装")
        print("   请安装缺失的依赖包")
        return 3
    else:
        print("[OK] 特征向量系统已就绪!")
        print("   智能选题功能可以正常工作")
        return 0


if __name__ == "__main__":
    sys.exit(main())
