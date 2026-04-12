#!/usr/bin/env python
"""
智能选题系统性能监控脚本（PostgreSQL 版）
监控选题算法的关键指标和性能
"""

import json
import numpy as np
from datetime import datetime, timedelta
import atplotlib.pyplot as plt
from pathlib import Path
import sys
import psycopg2
from app.core.config import settings


def get_pg_connection():
    """获取 PostgreSQL 连接"""
    return psycopg2.connect(settings.DATABASE_URL)


def analyze_question_difficulty_distribution():
    """分析题目难度分布"""
    print("=" * 60)
    print("[图表] 题目难度分布分析")
    print("=" * 60)

    try:
        conn = get_pg_connection()
        cursor = conn.cursor()

        # 查询所有题目的难度和区分度
        cursor.execute("SELECT difficulty, discrimination FROM atmr_questions WHERE difficulty IS NOT NULL")
        results = cursor.fetchall()

        if not results:
            print("[警告] 数据库中没有题目难度数据")
            return

        difficulties = [r[0] for r in results]
        discriminations = [r[1] for r in results]

        print(f"[列表] 题目总数: {len(difficulties)}")
        print(f"[统计] 难度统计:")
        print(f"   平均值: {np.mean(difficulties):.3f}")
        print(f"   中位数: {np.median(difficulties):.3f}")
        print(f"   标准差: {np.std(difficulties):.3f}")
        print(f"   最小值: {np.min(difficulties):.3f}")
        print(f"   最大值: {np.max(difficulties):.3f}")

        print(f"\n[统计] 区分度统计:")
        print(f"   平均值: {np.mean(discriminations):.3f}")
        print(f"   中位数: {np.median(discriminations):.3f}")
        print(f"   标准差: {np.std(discriminations):.3f}")

        # 难度分布直方图
        plt.figure(figsize=(12, 5))

        plt.subplot(1, 2, 1)
        plt.hist(difficulties, bins=20, alpha=0.7, color='skyblue', edgecolor='black')
        plt.xlabel('难度系数 (0=容易, 1=困难)')
        plt.ylabel('题目数量')
        plt.title('题目难度分布')
        plt.grid(True, alpha=0.3)

        plt.subplot(1, 2, 2)
        plt.hist(discriminations, bins=20, alpha=0.7, color='lightcoral', edgecolor='black')
        plt.xlabel('区分度系数 (0=低, 1=高)')
        plt.ylabel('题目数量')
        plt.title('题目区分度分布')
        plt.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig('question_stats_distribution.png', dpi=150)
        print(f"\n[图片] 分布图已保存: question_stats_distribution.png")

        conn.close()

    except Exception as e:
        print(f"[错误] 分析难度分布时出错: {e}")


def analyze_feature_vectors():
    """分析特征向量状态"""
    print("\n" + "=" * 60)
    print("特征向量状态分析")
    print("=" * 60)

    try:
        conn = get_pg_connection()
        cursor = conn.cursor()

        # 检查特征向量相关列
        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'atmr_questions'
        """)
        columns = [row[0] for row in cursor.fetchall()]

        required_columns = ['feature_vector', 'feature_dim', 'difficulty', 'discrimination']
        for col in required_columns:
            if col in columns:
                print(f"[OK] {col}: 存在")
            else:
                print(f"[MISSING] {col}: 缺失")

        # 统计特征向量状态
        cursor.execute("SELECT COUNT(*) FROM atmr_questions")
        total = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM atmr_questions WHERE feature_vector IS NOT NULL")
        with_features = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM atmr_questions WHERE difficulty IS NOT NULL AND discrimination IS NOT NULL")
        with_params = cursor.fetchone()[0]

        print(f"\n特征向量覆盖度:")
        print(f"   总题目数: {total}")
        if total > 0:
            print(f"   有特征向量: {with_features} ({with_features/total*100:.1f}%)")
            print(f"   有难度区分度: {with_params} ({with_params/total*100:.1f}%)")

        # 检查特征向量维度
        if with_features > 0:
            cursor.execute("SELECT feature_dim FROM atmr_questions WHERE feature_dim IS NOT NULL LIMIT 1")
            result = cursor.fetchone()
            if result:
                print(f"   特征向量维度: {result[0]}")

        conn.close()

    except Exception as e:
        print(f"[错误] 分析特征向量时出错: {e}")


def analyze_user_answer_patterns():
    """分析用户答题模式"""
    print("\n" + "=" * 60)
    print("用户答题模式分析")
    print("=" * 60)

    try:
        conn = get_pg_connection()
        cursor = conn.cursor()

        # 检查 answer_records 表是否存在
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'answer_records'
            )
        """)
        if not cursor.fetchone()[0]:
            print("[警告] answer_records 表不存在，无答题数据")
            conn.close()
            return

        # 统计答题记录
        cursor.execute("SELECT COUNT(*) FROM answer_records")
        total_records = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(DISTINCT user_id) FROM answer_records")
        unique_users = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(DISTINCT session_id) FROM answer_records")
        unique_sessions = cursor.fetchone()[0]

        print(f"答题记录统计:")
        print(f"   总答题记录: {total_records}")
        print(f"   独立用户数: {unique_users}")
        print(f"   独立会话数: {unique_sessions}")

        if total_records > 0:
            # 平均每会话答题数
            cursor.execute("SELECT session_id, COUNT(*) as cnt FROM answer_records GROUP BY session_id")
            session_counts = [row[1] for row in cursor.fetchall()]

            print(f"\n会话答题分析:")
            print(f"   平均每会话答题数: {np.mean(session_counts):.1f}")
            print(f"   最大每会话答题数: {np.max(session_counts)}")
            print(f"   最小每会话答题数: {np.min(session_counts)}")

            # 异常作答统计
            cursor.execute("SELECT COUNT(*) FROM answer_records WHERE is_anomaly = 1")
            anomaly_count = cursor.fetchone()[0]

            print(f"\n异常作答分析:")
            print(f"   异常作答次数: {anomaly_count} ({anomaly_count/total_records*100:.1f}%)")

            # 作答时间统计
            cursor.execute("SELECT time_spent FROM answer_records WHERE time_spent > 0")
            time_data = [row[0] for row in cursor.fetchall()]

            if time_data:
                print(f"\n作答时间分析:")
                print(f"   平均作答时间: {np.mean(time_data):.1f}秒")
                print(f"   中位数作答时间: {np.median(time_data):.1f}秒")
                print(f"   最短作答时间: {np.min(time_data):.1f}秒")
                print(f"   最长作答时间: {np.max(time_data):.1f}秒")

        conn.close()

    except Exception as e:
        print(f"[错误] 分析用户答题模式时出错: {e}")


def check_system_health():
    """检查系统健康状态"""
    print("\n" + "=" * 60)
    print("系统健康状态检查")
    print("=" * 60)

    # 检查数据库连接
    try:
        conn = get_pg_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT pg_database_size(current_database())")
        db_size = cursor.fetchone()[0] / (1024 * 1024)  # MB
        print(f"[OK] 数据库连接正常, 大小: {db_size:.2f} MB")
        conn.close()
    except Exception as e:
        print(f"[ERROR] 数据库连接失败: {e}")
        return False

    # 检查关键文件
    required_files = [
        "app/services/question_selection.py",
        "app/models/question.py",
        "app/api/assessment.py"
    ]

    all_ok = True
    for file_path in required_files:
        if Path(file_path).exists():
            print(f"[OK] {file_path}: 存在")
        else:
            print(f"[ERROR] {file_path}: 缺失")
            all_ok = False

    # 检查前端文件
    frontend_path = Path("frontend/src/components/Assessment.vue")
    if frontend_path.exists():
        print(f"[OK] 前端组件: 存在")
    else:
        print(f"[WARN] 前端组件: 可能已修改路径")

    return all_ok


def generate_recommendations():
    """生成优化建议"""
    print("\n" + "=" * 60)
    print("优化建议")
    print("=" * 60)

    recommendations = []

    try:
        conn = get_pg_connection()
        cursor = conn.cursor()

        # 检查特征向量覆盖度
        cursor.execute("SELECT COUNT(*) FROM atmr_questions WHERE feature_vector IS NOT NULL")
        with_features = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM atmr_questions")
        total = cursor.fetchone()[0]

        if with_features < total:
            recommendations.append(f"特征向量生成: {with_features}/{total} 题目有特征向量，建议运行 python scripts/generate_feature_vectors.py 补全")

        # 检查答题数据量
        cursor.execute("SELECT COUNT(*) FROM answer_records")
        answer_count = cursor.fetchone()[0]

        if answer_count < 50:
            recommendations.append(f"训练数据不足: 仅有 {answer_count} 条答题记录，建议收集更多用户数据以优化算法")
        elif answer_count < 200:
            recommendations.append(f"数据收集进展: 已有 {answer_count} 条答题记录，继续收集可进一步优化算法")
        else:
            recommendations.append(f"数据充足: 已有 {answer_count} 条答题记录，算法有足够训练数据")

        conn.close()

    except Exception as e:
        recommendations.append(f"无法获取详细数据: {e}")

    # 通用建议
    recommendations.append("算法调优: 可根据实际使用情况调整 question_selection.py 中的权重参数")
    recommendations.append("性能监控: 建议定期运行此监控脚本，跟踪系统演进")
    recommendations.append("A/B测试: 可对比智能选题与传统固定顺序的效果差异")

    for i, rec in enumerate(recommendations, 1):
        print(f"{i}. {rec}")


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("[AI] TestAgent 智能选题系统性能监控 (PostgreSQL)")
    print("=" * 60)

    print(f"\n[日期] 运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 检查系统健康状态
    if not check_system_health():
        print("\n[警告] 系统健康状态异常，部分分析可能无法进行")

    # 执行各项分析
    analyze_question_difficulty_distribution()
    analyze_feature_vectors()
    analyze_user_answer_patterns()
    generate_recommendations()

    print("\n" + "=" * 60)
    print("监控报告生成完成！")
    print("=" * 60)
    print("\n下一步行动:")
    print("   1. 查看生成的图表: question_stats_distribution.png")
    print("   2. 根据建议优化系统")
    print("   3. 定期运行此脚本监控系统演进")
    print("   4. 收集用户反馈，持续改进算法")

    return 0


if __name__ == "__main__":
    sys.exit(main())
