import json
from app.models.question import SessionLocal, Question


def calculate_avg_time(question_text: str, options: list) -> float:
    """
    智能计算预估作答时间（用于触发 AI 异常拦截）
    公式：(题干字数 + 选项总字数) / 10(每秒阅读速度) + 2(思考秒数)
    """
    text_length = len(question_text or "")
    options_length = sum(len(opt) for opt in options) if options else 0
    total_length = text_length + options_length

    # 保留一位小数
    return round((total_length / 10.0) + 2.0, 1)


def import_questions_to_db():
    print("⏳ 开始解析 atmr_full_questions.json 并写入数据库...")

    # 1. 打开我们刚才抓取的 JSON 文件
    try:
        with open("atmr_full_questions.json", "r", encoding="utf-8") as f:
            raw_data = json.load(f)
    except FileNotFoundError:
        print("❌ 找不到 atmr_full_questions.json，请确认文件在当前目录！")
        return

    # 2. 开启数据库会话
    db = SessionLocal()
    success_count = 0

    for item in raw_data:
        exam_no = item.get("examNo")

        # 查重：如果数据库里已经有这道题，就跳过
        if db.query(Question).filter(Question.exam_no == exam_no).first():
            continue

        # 清洗数据
        q_content = item.get("exam", "")
        q_options = item.get("options", [])

        # 判断是否反向计分 (只要有 reversalDesc 字段且不为空，我们就认为是反向题)
        is_reverse = True if item.get("reversalDesc") else False

        # 核心：自动计算出我们系统独有的 avg_time
        calculated_time = calculate_avg_time(q_content, q_options)

        # 组装一条数据库记录
        new_question = Question(
            exam_no=exam_no,
            dimension_id=item.get("examTypeId"),
            content=q_content,
            options=q_options,
            scores=item.get("scores", []),
            trait_label=item.get("title"),  # 这个可能部分题目没有，会自动存为 null
            ai_analysis_prompt=item.get("description"),  # 同上
            is_reverse=is_reverse,
            avg_time=calculated_time
        )

        db.add(new_question)
        success_count += 1

    # 3. 提交到数据库并保存
    db.commit()
    db.close()

    print(f"🎉 导入完成！成功将 {success_count} 道清洗后的题目存入数据库！")
    print("💡 你的系统中现在已经拥有了每道题的【预估作答时间】和【AI辩论参考字典】！")


if __name__ == "__main__":
    import_questions_to_db()