#!/usr/bin/env python
"""
PostgreSQL 存储优化迁移脚本
将字段类型从 SQLite 兼容类型升级为 PostgreSQL 最优类型：
- JSON → JSONB
- FLOAT → NUMERIC
- DATETIME → TIMESTAMPTZ
- 添加复合索引
"""

import psycopg2
from app.core.config import settings


def get_conn():
    return psycopg2.connect(settings.DATABASE_URL)


def run_migration():
    print("=" * 60)
    print("[OPTIMIZE] PostgreSQL 存储优化迁移")
    print("=" * 60)

    conn = get_conn()
    conn.autocommit = False
    cursor = conn.cursor()

    migrations = []

    # ============================================================
    # 1. atmr_questions 表：JSON → JSONB
    # ============================================================
    migrations.append(("options → JSONB",
        "ALTER TABLE atmr_questions ALTER COLUMN options TYPE JSONB USING options::jsonb"))
    migrations.append(("scores → JSONB",
        "ALTER TABLE atmr_questions ALTER COLUMN scores TYPE JSONB USING scores::jsonb"))
    migrations.append(("feature_vector → JSONB",
        "ALTER TABLE atmr_questions ALTER COLUMN feature_vector TYPE JSONB USING feature_vector::jsonb"))

    # FLOAT → NUMERIC
    migrations.append(("avg_time → NUMERIC(5,2)",
        "ALTER TABLE atmr_questions ALTER COLUMN avg_time TYPE NUMERIC(5,2)"))
    migrations.append(("discrimination → NUMERIC(4,3)",
        "ALTER TABLE atmr_questions ALTER COLUMN discrimination TYPE NUMERIC(4,3)"))
    migrations.append(("difficulty → NUMERIC(4,3)",
        "ALTER TABLE atmr_questions ALTER COLUMN difficulty TYPE NUMERIC(4,3)"))

    # ============================================================
    # 2. users 表
    # ============================================================
    migrations.append(("password_hash → VARCHAR(255)",
        "ALTER TABLE users ALTER COLUMN password_hash TYPE VARCHAR(255)"))
    migrations.append(("users.created_at → TIMESTAMPTZ",
        "ALTER TABLE users ALTER COLUMN created_at TYPE TIMESTAMPTZ"))

    # ============================================================
    # 3. assessment_sessions 表
    # ============================================================
    migrations.append(("sessions.started_at → TIMESTAMPTZ",
        "ALTER TABLE assessment_sessions ALTER COLUMN started_at TYPE TIMESTAMPTZ"))
    migrations.append(("sessions.finished_at → TIMESTAMPTZ",
        "ALTER TABLE assessment_sessions ALTER COLUMN finished_at TYPE TIMESTAMPTZ"))

    # ============================================================
    # 4. answer_records 表
    # ============================================================
    migrations.append(("answer.score → NUMERIC(4,2)",
        "ALTER TABLE answer_records ALTER COLUMN score TYPE NUMERIC(4,2)"))
    migrations.append(("answer.time_spent → NUMERIC(6,2)",
        "ALTER TABLE answer_records ALTER COLUMN time_spent TYPE NUMERIC(6,2)"))
    migrations.append(("answer.created_at → TIMESTAMPTZ",
        "ALTER TABLE answer_records ALTER COLUMN created_at TYPE TIMESTAMPTZ"))

    # ============================================================
    # 5. module_debate_results 表
    # ============================================================
    migrations.append(("debate.created_at → TIMESTAMPTZ",
        "ALTER TABLE module_debate_results ALTER COLUMN created_at TYPE TIMESTAMPTZ"))

    # ============================================================
    # 6. 添加复合索引
    # ============================================================
    index_migrations = [
        ("idx_answer_session_user",
         "CREATE INDEX IF NOT EXISTS idx_answer_session_user ON answer_records(session_id, user_id)"),
        ("idx_answer_session_user_exam",
         "CREATE INDEX IF NOT EXISTS idx_answer_session_user_exam ON answer_records(session_id, user_id, exam_no)"),
        ("idx_debate_session_module",
         "CREATE INDEX IF NOT EXISTS idx_debate_session_module ON module_debate_results(session_id, module)"),
        ("idx_session_user_started",
         "CREATE INDEX IF NOT EXISTS idx_session_user_started ON assessment_sessions(user_id, started_at DESC)"),
    ]

    # 执行字段类型迁移
    print("\n[STEP 1] 字段类型优化...")
    success = 0
    skipped = 0
    for name, sql in migrations:
        try:
            cursor.execute(sql)
            print(f"  [OK] {name}")
            success += 1
        except Exception as e:
            err_msg = str(e)
            if "already" in err_msg.lower() or "nothing to alter" in err_msg.lower():
                print(f"  [SKIP] {name} (已是目标类型)")
                skipped += 1
            else:
                print(f"  [WARN] {name}: {err_msg.strip()}")
                skipped += 1
            conn.rollback()
            conn.autocommit = False

    try:
        conn.commit()
    except Exception:
        conn.rollback()

    # 执行索引创建
    print(f"\n[STEP 2] 添加复合索引...")
    for name, sql in index_migrations:
        try:
            conn.autocommit = True
            cursor.execute(sql)
            print(f"  [OK] {name}")
        except Exception as e:
            err_msg = str(e)
            if "already exists" in err_msg.lower():
                print(f"  [SKIP] {name} (已存在)")
            else:
                print(f"  [WARN] {name}: {err_msg.strip()}")

    # 验证结果
    print(f"\n[STEP 3] 验证优化结果...")
    conn.autocommit = True
    cursor.execute("""
        SELECT table_name, column_name, data_type, character_maximum_length, numeric_precision, numeric_scale
        FROM information_schema.columns
        WHERE table_schema = 'public'
        AND table_name IN ('atmr_questions', 'users', 'assessment_sessions', 'answer_records', 'module_debate_results')
        ORDER BY table_name, ordinal_position
    """)

    current_table = None
    for row in cursor.fetchall():
        table, col, dtype, max_len, precision, scale = row
        if table != current_table:
            print(f"\n  [{table}]")
            current_table = table
        type_info = dtype
        if max_len:
            type_info += f"({max_len})"
        elif precision and scale is not None:
            type_info += f"({precision},{scale})"
        print(f"    {col}: {type_info}")

    # 验证索引
    print(f"\n  [索引列表]")
    cursor.execute("""
        SELECT indexname, tablename
        FROM pg_indexes
        WHERE schemaname = 'public'
        AND indexname LIKE 'idx_%'
        ORDER BY tablename, indexname
    """)
    for row in cursor.fetchall():
        print(f"    {row[1]}.{row[0]}")

    conn.close()

    print(f"\n{'=' * 60}")
    print(f"[DONE] 优化完成: {success} 项成功, {skipped} 项跳过")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    run_migration()
