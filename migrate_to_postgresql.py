#!/usr/bin/env python
"""
SQLite → PostgreSQL 数据迁移脚本
将现有 SQLite 数据库（atmr_data.db）中的所有数据迁移到 PostgreSQL。

使用方法:
    1. 确保 PostgreSQL 已安装并运行
    2. 创建数据库: CREATE DATABASE atmr_db;
    3. 配置 app/core/config.py 中的 DATABASE_URL（或设置环境变量）
    4. 运行: python migrate_to_postgresql.py
"""

import sqlite3
import json
import sys
from pathlib import Path
from datetime import datetime

import psycopg2
import psycopg2.extras
from app.core.config import settings


SQLITE_DB_PATH = "atmr_data.db"


def check_prerequisites():
    """检查迁移前提条件"""
    print("=" * 60)
    print("[CHECK] 检查迁移前提条件")
    print("=" * 60)

    # 检查 SQLite 文件
    if not Path(SQLITE_DB_PATH).exists():
        print(f"[ERROR] SQLite 数据库文件不存在: {SQLITE_DB_PATH}")
        return False
    print(f"[OK] SQLite 数据库文件存在: {SQLITE_DB_PATH}")

    # 检查 PostgreSQL 连接
    try:
        pg_conn = psycopg2.connect(settings.DATABASE_URL)
        pg_conn.close()
        print(f"[OK] PostgreSQL 连接成功: {settings.DATABASE_URL.split('@')[1] if '@' in settings.DATABASE_URL else settings.DATABASE_URL}")
    except Exception as e:
        print(f"[ERROR] PostgreSQL 连接失败: {e}")
        print("[HINT] 请确保 PostgreSQL 已启动，并且数据库已创建")
        print(f"[HINT] 当前连接字符串: {settings.DATABASE_URL}")
        return False

    return True


def create_pg_tables():
    """在 PostgreSQL 中创建表结构"""
    print("\n" + "=" * 60)
    print("[CREATE] 在 PostgreSQL 中创建表结构")
    print("=" * 60)

    try:
        # 通过 SQLAlchemy 的 Base.metadata.create_all 创建表
        from app.models.question import Base, engine
        Base.metadata.create_all(bind=engine)
        print("[OK] 表结构创建成功")
        return True
    except Exception as e:
        print(f"[ERROR] 创建表结构失败: {e}")
        return False


def get_sqlite_tables(sqlite_conn):
    """获取 SQLite 中的所有表"""
    cursor = sqlite_conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    return [row[0] for row in cursor.fetchall()]


def get_sqlite_columns(sqlite_conn, table_name):
    """获取 SQLite 表的列信息"""
    cursor = sqlite_conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    return [(row[1], row[2]) for row in cursor.fetchall()]  # (name, type)


def migrate_table(sqlite_conn, pg_conn, table_name):
    """迁移单个表的数据"""
    sqlite_cursor = sqlite_conn.cursor()
    pg_cursor = pg_conn.cursor()

    # 获取列信息
    columns = get_sqlite_columns(sqlite_conn, table_name)
    col_names = [col[0] for col in columns]

    # 检查 PostgreSQL 中该表是否存在
    pg_cursor.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = %s ORDER BY ordinal_position
    """, (table_name,))
    pg_columns = [row[0] for row in pg_cursor.fetchall()]

    if not pg_columns:
        print(f"  [SKIP] 表 {table_name} 在 PostgreSQL 中不存在，跳过")
        return 0

    # 取两边都有的列（交集）
    common_cols = [col for col in col_names if col in pg_columns]
    if not common_cols:
        print(f"  [SKIP] 表 {table_name} 无共同列，跳过")
        return 0

    # 从 SQLite 读取数据
    sqlite_cursor.execute(f"SELECT {', '.join(common_cols)} FROM {table_name}")
    rows = sqlite_cursor.fetchall()

    if not rows:
        print(f"  [INFO] 表 {table_name} 无数据")
        return 0

    # 清空 PostgreSQL 中的目标表（避免重复），使用 TRUNCATE CASCADE 处理外键
    pg_cursor.execute(f"TRUNCATE TABLE {table_name} CASCADE")

    # 构建插入语句
    placeholders = ', '.join(['%s'] * len(common_cols))
    insert_sql = f"INSERT INTO {table_name} ({', '.join(common_cols)}) VALUES ({placeholders})"

    # 获取 PostgreSQL 中各列的数据类型
    pg_cursor.execute("""
        SELECT column_name, data_type FROM information_schema.columns
        WHERE table_name = %s
    """, (table_name,))
    pg_col_types = {row[0]: row[1] for row in pg_cursor.fetchall()}

    # 批量插入
    inserted = 0
    for row in rows:
        # 处理类型转换：SQLite → PostgreSQL
        processed_row = []
        for i, val in enumerate(row):
            col_name = common_cols[i]
            pg_type = pg_col_types.get(col_name, '')

            if val is not None and col_name in ('options', 'scores', 'feature_vector'):
                # JSON 字段：确保是合法的 JSON
                if isinstance(val, str):
                    try:
                        parsed = json.loads(val)
                        processed_row.append(json.dumps(parsed))
                    except (json.JSONDecodeError, TypeError):
                        processed_row.append(val)
                else:
                    processed_row.append(json.dumps(val) if not isinstance(val, str) else val)
            elif pg_type == 'boolean':
                # Boolean 字段：SQLite 存的是 0/1，PostgreSQL 需要 True/False
                processed_row.append(bool(val) if val is not None else None)
            else:
                processed_row.append(val)

        try:
            pg_cursor.execute(insert_sql, processed_row)
            inserted += 1
        except Exception as e:
            print(f"  [WARN] 插入失败 (表 {table_name}): {e}")
            pg_conn.rollback()
            continue

    pg_conn.commit()

    # 重置自增序列（PostgreSQL SERIAL 类型）
    if 'id' in common_cols:
        try:
            pg_cursor.execute(f"SELECT MAX(id) FROM {table_name}")
            max_id = pg_cursor.fetchone()[0]
            if max_id:
                pg_cursor.execute(f"SELECT setval(pg_get_serial_sequence('{table_name}', 'id'), %s)", (max_id,))
                pg_conn.commit()
        except Exception:
            pass  # 某些表可能没有序列

    return inserted


def verify_migration(sqlite_conn, pg_conn):
    """验证迁移结果"""
    print("\n" + "=" * 60)
    print("[VERIFY] 验证迁移结果")
    print("=" * 60)

    sqlite_cursor = sqlite_conn.cursor()
    pg_cursor = pg_conn.cursor()

    tables = get_sqlite_tables(sqlite_conn)
    all_ok = True

    for table in tables:
        sqlite_cursor.execute(f"SELECT COUNT(*) FROM {table}")
        sqlite_count = sqlite_cursor.fetchone()[0]

        try:
            pg_cursor.execute(f"SELECT COUNT(*) FROM {table}")
            pg_count = pg_cursor.fetchone()[0]

            status = "[OK]" if sqlite_count == pg_count else "[WARN]"
            if sqlite_count != pg_count:
                all_ok = False

            print(f"  {status} {table}: SQLite={sqlite_count}, PostgreSQL={pg_count}")
        except Exception:
            print(f"  [SKIP] {table}: PostgreSQL 中不存在")

    return all_ok


def main():
    """主函数"""
    print("=" * 60)
    print("[MIGRATE] SQLite → PostgreSQL 数据迁移工具")
    print(f"[TIME] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 1. 检查前提条件
    if not check_prerequisites():
        return 1

    # 2. 创建 PostgreSQL 表结构
    if not create_pg_tables():
        return 1

    # 3. 连接数据库
    print("\n" + "=" * 60)
    print("[MIGRATE] 开始迁移数据")
    print("=" * 60)

    sqlite_conn = sqlite3.connect(SQLITE_DB_PATH)
    pg_conn = psycopg2.connect(settings.DATABASE_URL)

    try:
        # 获取所有表
        tables = get_sqlite_tables(sqlite_conn)
        print(f"[INFO] SQLite 中共有 {len(tables)} 个表: {tables}")

        # 按依赖顺序迁移（先父表后子表）
        migration_order = [
            'atmr_questions',
            'users',
            'assessment_sessions',
            'answer_records',
            'module_debate_results'
        ]

        # 添加不在预定义顺序中的表
        for table in tables:
            if table not in migration_order:
                migration_order.append(table)

        total_migrated = 0
        for table in migration_order:
            if table not in tables:
                continue
            print(f"\n[TABLE] 迁移表: {table}")
            count = migrate_table(sqlite_conn, pg_conn, table)
            total_migrated += count
            print(f"  [OK] 成功迁移 {count} 条记录")

        # 4. 验证迁移
        all_ok = verify_migration(sqlite_conn, pg_conn)

        print("\n" + "=" * 60)
        if all_ok:
            print(f"[SUCCESS] 迁移完成！共迁移 {total_migrated} 条记录")
        else:
            print(f"[WARN] 迁移完成，但部分表数据量不一致，请检查")

        print("=" * 60)
        print("\n[NEXT] 后续步骤:")
        print("  1. 启动后端: uvicorn app.main:app --reload")
        print("  2. 测试API: 访问 http://localhost:8000/docs")
        print("  3. 确认无误后可归档 SQLite 文件: atmr_data.db")

    except Exception as e:
        print(f"\n[ERROR] 迁移过程中出错: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        sqlite_conn.close()
        pg_conn.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
