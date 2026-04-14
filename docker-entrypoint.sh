#!/bin/bash
set -e

echo "=== TestAgent 后端启动 ==="

# 等待 PostgreSQL 就绪
echo "等待数据库就绪..."
for i in $(seq 1 30); do
    python -c "
from sqlalchemy import create_engine, text
import os
engine = create_engine(os.environ.get('DATABASE_URL', 'postgresql://postgres:123456@db:5432/atmr_db'))
with engine.connect() as conn:
    conn.execute(text('SELECT 1'))
print('数据库连接成功')
" 2>/dev/null && break
    echo "  等待中... ($i/30)"
    sleep 2
done

# 自动建表（SQLAlchemy create_all 在模型导入时执行）
echo "初始化数据库表..."
python -c "from app.models import Base, engine; Base.metadata.create_all(bind=engine)"

# 检查是否需要导入题库
echo "检查题库数据..."
NEED_IMPORT=$(python -c "
from app.core.database import SessionLocal
from app.models.assessment import Question
db = SessionLocal()
count = db.query(Question).count()
db.close()
print(count)
")

if [ "$NEED_IMPORT" = "0" ]; then
    echo "题库为空，开始导入数据..."
    python scripts/import_data.py
else
    echo "题库已有 $NEED_IMPORT 道题目，跳过导入"
fi

echo "=== 启动 FastAPI 服务 ==="
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
