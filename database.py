from fastapi import FastAPI
from sqlalchemy import create_engine, Column, Integer, String, Float, JSON, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker

# 1. 数据库配置（先用 SQLite 存在本地，免安装极速测试）
SQLALCHEMY_DATABASE_URL = "sqlite:///./atmr_test.db"
# 未来换 MySQL 只需要把上面这行改成：
# SQLALCHEMY_DATABASE_URL = "mysql+pymysql://root:你的密码@localhost:3306/atmr_db"

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# 2. 定义【题目表】的结构
class Question(Base):
    __tablename__ = "questions"
    id = Column(Integer, primary_key=True, index=True)
    content = Column(String(500))  # 题目内容
    dimension = Column(String(50))  # ATMR维度
    options = Column(JSON)  # 选项 JSON
    avg_time = Column(Float, default=8.0)  # 平均耗时（秒）


# 3. 定义【作答记录表】的结构
class AnswerRecord(Base):
    __tablename__ = "answer_records"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer)
    question_id = Column(Integer)
    selected_choice = Column(String(10))
    time_spent = Column(Float)  # 实际作答耗时
    is_anomaly = Column(Boolean, default=False)  # 是否异常


# 4. 初始化：自动在本地创建这个数据库文件
Base.metadata.create_all(bind=engine)

app = FastAPI()


# ==========================================
# 下面是你的第一个带数据库的 API 接口
# ==========================================

@app.post("/api/mock_init")
def init_mock_data():
    """这是一个辅助接口：一键往数据库里塞入一条假数据，方便你测试"""
    db = SessionLocal()
    # 检查是不是已经有数据了
    if db.query(Question).first():
        return {"msg": "已经有测试数据啦！"}

    # 手捏一条 ATMR 假数据
    mock_q = Question(
        content="当团队项目进度落后时，你通常的反应是？",
        dimension="行为模式",
        options={"A": "推诿责任", "B": "呼吁开会", "C": "独自加班把缺口补上"},
        avg_time=8.5
    )
    db.add(mock_q)
    db.commit()
    db.close()
    return {"msg": "假数据注入成功！"}


@app.get("/api/get_question")
def get_next_question():
    """前端调用这个接口，获取要做的题目"""
    db = SessionLocal()
    # 随便取第一道题出来
    question = db.query(Question).first()
    db.close()
    return {"id": question.id, "content": question.content, "options": question.options}