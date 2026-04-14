"""清除卡在"生成中"状态的会话"""
from app.core.database import SessionLocal
from app.models.assessment import AssessmentSession

db = SessionLocal()
try:
    stuck = db.query(AssessmentSession).filter(
        AssessmentSession.status == "completed",
        AssessmentSession.report_content.is_(None),
    ).all()
    if not stuck:
        print("没有卡住的会话")
    else:
        for s in stuck:
            s.report_content = "该会话报告生成失败，请重新测评。"
            print(f"已清除 session #{s.id} 的生成中状态")
        db.commit()
        print("完成")
finally:
    db.close()
