#!/usr/bin/env python
"""
数据库迁移脚本
为现有数据库表添加新字段（特征向量、难度、区分度等）
适配 PostgreSQL 数据库
"""

import json
import psycopg2
from app.core.config import settings


def get_pg_connection():
    """获取 PostgreSQL 连接"""
    url = settings.DATABASE_URL
    return psycopg2.connect(url)


def check_and_add_columns():
    """检查并添加缺失的列"""
    print("[CHECK] 检查数据库表结构...")

    conn = get_pg_connection()
    cursor = conn.cursor()

    try:
        # 获取 atmr_questions 表的列信息
        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'atmr_questions'
            ORDER BY ordinal_position
        """)
        columns = [row[0] for row in cursor.fetchall()]

        if not columns:
            print("[ERROR] 表 atmr_questions 不存在，请先启动应用创建表")
            return False

        print(f"[OK] 现有列: {columns}")

        # 需要添加的列
        new_columns = [
            ("feature_vector", "JSONB"),
            ("feature_dim", "INTEGER"),
            ("discrimination", "DOUBLE PRECISION"),
            ("difficulty", "DOUBLE PRECISION")
        ]

        added_count = 0
        for col_name, col_type in new_columns:
            if col_name not in columns:
                print(f"  [ADD] 添加列: {col_name} ({col_type})")
                try:
                    cursor.execute(f"ALTER TABLE atmr_questions ADD COLUMN {col_name} {col_type}")
                    added_count += 1
                except Exception as e:
                    print(f"  [ERROR] 添加列 {col_name} 失败: {e}")
                    conn.rollback()

        if added_count > 0:
            conn.commit()
            print(f"[OK] 成功添加 {added_count} 个新列")
        else:
            print("[OK] 表结构已是最新，无需迁移")

        # 验证列已添加
        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'atmr_questions'
            ORDER BY ordinal_position
        """)
        updated_columns = [row[0] for row in cursor.fetchall()]
        print(f"[COLUMNS] 更新后列: {updated_columns}")

        return True

    except Exception as e:
        print(f"[ERROR] 迁移失败: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def update_existing_records():
    """更新现有记录的难度和区分度"""
    print("\n[UPDATE] 更新现有题目参数...")

    conn = get_pg_connection()
    cursor = conn.cursor()

    try:
        # 获取所有题目
        cursor.execute("SELECT id, scores FROM atmr_questions")
        questions = cursor.fetchall()

        updated_count = 0
        for q_id, scores_data in questions:
            if not scores_data:
                continue

            try:
                # PostgreSQL JSONB 已经是 Python 对象，无需 json.loads
                scores = scores_data if isinstance(scores_data, list) else json.loads(scores_data)
                if not scores or len(scores) < 2:
                    continue

                # 计算难度和区分度（简化版）
                score_values = [float(s) for s in scores]
                avg_score = sum(score_values) / len(score_values)
                max_score = max(score_values)

                # 难度
                difficulty = 1.0 - (avg_score / max_score) if max_score > 0 else 0.5

                # 区分度（基于方差）
                variance = sum((s - avg_score) ** 2 for s in score_values) / len(score_values)
                max_variance = 6.25  # 0-5分数的最大方差
                discrimination = min(0.5 + (variance / max_variance), 1.0)

                # 限制范围
                difficulty = max(0.0, min(1.0, difficulty))
                discrimination = max(0.3, min(1.0, discrimination))

                # 更新数据库
                cursor.execute(
                    "UPDATE atmr_questions SET difficulty = %s, discrimination = %s WHERE id = %s",
                    (difficulty, discrimination, q_id)
                )
                updated_count += 1

            except Exception as e:
                print(f"  [WARN] 题目 {q_id} 更新失败: {e}")
                continue

        conn.commit()
        print(f"[OK] 成功更新 {updated_count} 道题目的参数")

    except Exception as e:
        print(f"[ERROR] 更新记录失败: {e}")
        conn.rollback()
    finally:
        conn.close()


def main():
    """主函数"""
    print("=" * 50)
    print("[DB] 数据库迁移工具 (PostgreSQL)")
    print("=" * 50)

    # 1. 添加新列
    if not check_and_add_columns():
        print("[WARN] 表结构检查/更新失败")
        return 1

    # 2. 更新现有记录
    update_existing_records()

    print("\n[SUCCESS] 迁移完成！")
    print("[INFO] 现在可以运行: python scripts/generate_feature_vectors.py 生成特征向量")

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
