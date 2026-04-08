#!/usr/bin/env python
"""
数据库整理脚本（PostgreSQL 版）：
1. 根据题目编号排序（在输出时）
2. 移除冗余数据（重复项、空值）
3. 根据 dimension_id 更新 trait_label
"""

import psycopg2
import psycopg2.extras
from app.core.config import settings


def get_pg_connection():
    """获取 PostgreSQL 连接"""
    conn = psycopg2.connect(settings.DATABASE_URL)
    return conn


def cleanup_database():
    """整理数据库"""
    print("开始整理数据库...")
    conn = get_pg_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    try:
        # 1. 检查表结构
        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'atmr_questions'
            ORDER BY ordinal_position
        """)
        columns = [row[0] for row in cursor.fetchall()]
        print(f"现有列: {columns}")

        # 2. 删除重复记录（基于 exam_no）
        print("\n检查重复记录...")
        cursor.execute("""
            DELETE FROM atmr_questions
            WHERE id NOT IN (
                SELECT MIN(id)
                FROM atmr_questions
                GROUP BY exam_no
            )
        """)
        deleted_count = cursor.rowcount
        if deleted_count > 0:
            conn.commit()
            print(f"删除 {deleted_count} 条重复记录")
        else:
            print("无重复记录")

        # 3. 删除 dimension_id 为空的记录
        cursor.execute("DELETE FROM atmr_questions WHERE dimension_id IS NULL")
        null_deleted = cursor.rowcount
        if null_deleted > 0:
            conn.commit()
            print(f"删除 {null_deleted} 条 dimension_id 为空的记录")

        # 4. 根据 dimension_id 更新 trait_label
        print("\n更新特质标签...")
        trait_mapping = {
            '6': '欣赏型',
            '4': '目标型',
            '5': '包容型',
            '7': '责任型'
        }

        updated_count = 0
        for dim_id, label in trait_mapping.items():
            cursor.execute("""
                UPDATE atmr_questions
                SET trait_label = %s
                WHERE dimension_id = %s
            """, (label, dim_id))
            updated_count += cursor.rowcount

        conn.commit()
        print(f"更新 {updated_count} 条记录的特质标签")

        # 5. 验证更新结果
        print("\n验证更新结果...")
        cursor.execute("""
            SELECT dimension_id, trait_label, COUNT(*) as count
            FROM atmr_questions
            GROUP BY dimension_id, trait_label
            ORDER BY dimension_id
        """)
        for row in cursor.fetchall():
            print(f"  维度 {row['dimension_id']}: {row['trait_label']} - {row['count']} 题")

        # 6. 按 exam_no 排序并显示样例
        print("\n题目排序样例 (前10题):")
        cursor.execute("""
            SELECT exam_no, dimension_id, trait_label
            FROM atmr_questions
            WHERE exam_no LIKE 'Z%%'
            ORDER BY exam_no
            LIMIT 10
        """)
        for row in cursor.fetchall():
            print(f"  {row['exam_no']}: {row['dimension_id']} - {row['trait_label']}")

        # 7. 统计各特质题目数量
        print("\n各特质题目统计:")
        cursor.execute("""
            SELECT trait_label, COUNT(*) as count
            FROM atmr_questions
            WHERE trait_label IS NOT NULL
            GROUP BY trait_label
            ORDER BY trait_label
        """)
        for row in cursor.fetchall():
            print(f"  {row['trait_label']}: {row['count']} 题")

        # 8. PostgreSQL 的 VACUUM 需要在 autocommit 模式下执行
        print("\n压缩数据库...")
        conn.commit()
        old_isolation = conn.isolation_level
        conn.set_isolation_level(0)  # AUTOCOMMIT
        cursor.execute("VACUUM ANALYZE atmr_questions")
        conn.set_isolation_level(old_isolation)
        print("数据库压缩完成")

    except Exception as e:
        print(f"整理过程中出错: {e}")
        conn.rollback()
    finally:
        conn.close()

    print("\n数据库整理完成！")
    return True


if __name__ == "__main__":
    cleanup_database()
