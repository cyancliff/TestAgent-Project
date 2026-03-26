# app/services/report_service.py
import json
from sqlalchemy.orm import Session
from app.models.record import AnswerRecord
from app.models.question import Question
# 这里导入你现有的多智能体辩论入口
from agents.debate_manager import run_debate


def generate_final_report_task(user_id: str, db: Session):
    """
    后台任务：提取用户全量作答数据，触发多智能体辩论
    """
    try:
        # 1. 获取该用户的所有作答记录
        records = db.query(AnswerRecord).filter(AnswerRecord.user_id == user_id).all()
        if not records:
            print(f"用户 {user_id} 没有作答记录，无法生成报告。")
            return

        # 2. 组装辩论上下文 (Data Payload)
        debate_context = []
        for r in records:
            # 关联查询题目内容
            question = db.query(Question).filter(Question.id == r.question_id).first()
            q_content = question.content if question else "未知题目"

            # 提取关键信息，格式化为字典
            record_data = {
                "question_id": r.question_id,
                "question_content": q_content,
                "selected_choice": r.selected_choice,
                "time_spent_ms": r.time_spent,
                "is_anomaly": r.is_anomaly
            }
            # 如果有追问解释，一并附上（假设你的模型里存了这个字段）
            if hasattr(r, 'user_explanation') and r.user_explanation:
                record_data["user_explanation"] = r.user_explanation

            debate_context.append(record_data)

        # 3. 转化为漂亮的 JSON 或 Markdown 字符串，喂给多智能体
        context_str = json.dumps(debate_context, ensure_ascii=False, indent=2)
        prompt = (
            f"以下是用户（ID: {user_id}）在 ATMR 心理测评中的作答记录（包含异常检测与用户的自我解释）。\n"
            f"请你们（正方、反方、裁决者）根据这些数据展开辩论，并生成最终的心理画像报告。\n"
            f"【作答数据】：\n{context_str}"
        )

        print(f"开始为用户 {user_id} 进行多智能体辩论推理...")

        # 4. 唤醒慢车道：调用 debate_manager
        # 这里的 run_debate 是你 agents/debate_manager.py 中暴露的主函数
        final_report = run_debate(prompt_context=prompt)

        # 5. （可选）将生成的报告落盘保存到数据库或本地 Markdown 文件
        save_report_to_db(user_id, final_report, db)
        print(f"用户 {user_id} 的心理画像报告已生成并保存！")

    except Exception as e:
        print(f"后台生成报告时发生错误: {str(e)}")