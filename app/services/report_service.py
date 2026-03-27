# app/services/report_service.py

import os
from datetime import datetime
import json
from sqlalchemy.orm import Session
from app.models.question import SessionLocal, Question, AnswerRecord


def build_debate_context(user_id: str, db: Session) -> str:
    """从数据库查询用户作答记录，组装辩论 prompt"""
    records = db.query(AnswerRecord).filter(AnswerRecord.user_id == user_id).all()
    if not records:
        raise ValueError(f"用户 {user_id} 没有作答记录，无法生成报告。")

    debate_context = []
    for r in records:
        question = db.query(Question).filter(Question.exam_no == r.exam_no).first()
        q_content = question.content if question else "未知题目"

        record_data = {
            "exam_no": r.exam_no,
            "question_content": q_content,
            "selected_option": r.selected_option,
            "time_spent": r.time_spent,
            "is_anomaly": r.is_anomaly
        }
        if hasattr(r, 'user_explanation') and r.user_explanation:
            record_data["user_explanation"] = r.user_explanation

        debate_context.append(record_data)

    context_str = json.dumps(debate_context, ensure_ascii=False, indent=2)
    return (
        f"以下是用户（ID: {user_id}）在 ATMR 心理测评中的作答记录（包含异常检测与用户的自我解释）。\n"
        f"请你们（正方、反方、裁决者）根据这些数据展开辩论，并生成最终的心理画像报告。\n"
        f"【作答数据】：\n{context_str}"
    )


def save_report_to_file(user_id: str, report_content: str) -> str:
    """将报告保存为 Markdown 文件，返回文件路径"""
    os.makedirs("reports", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = f"reports/user_{user_id}_{timestamp}.md"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(f"# ATMR 心理测评深度画像报告 (用户: {user_id})\n\n")
        f.write(report_content)
    print(f"报告已保存至: {file_path}")
    return file_path



