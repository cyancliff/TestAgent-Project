"""
评分工具函数
实现评分标准中的三分法等级、前两题加权机制、分数封顶。
"""

from app.core.constants import SCORE_LEVELS, WEIGHT_BONUS_SCORE, DIMENSION_MAX_SCORE


def get_dimension_level(score: float) -> dict:
    """根据维度得分返回等级信息

    等级划分（基于评分标准.md）：
    - 偏低: 10-23分
    - 中等: 24-37分
    - 偏高: 38-50分
    """
    for level_key, level_info in SCORE_LEVELS.items():
        if level_info["min"] <= score <= level_info["max"]:
            return {
                "level": level_key,
                "label": level_info["label"],
                "color": level_info["color"],
            }
    # 超出范围时（如加权后超过50），按最高等级返回
    if score > SCORE_LEVELS["high"]["max"]:
        return {
            "level": "high",
            "label": SCORE_LEVELS["high"]["label"],
            "color": SCORE_LEVELS["high"]["color"],
        }
    return {
        "level": "low",
        "label": SCORE_LEVELS["low"]["label"],
        "color": SCORE_LEVELS["low"]["color"],
    }


def clamp_score(score: float, max_score: float = DIMENSION_MAX_SCORE) -> float:
    """维度分数封顶处理

    内部计算可超过满分用于比较第一主导特质，
    但对外展示（雷达图、报告）不应突破满分刻度。
    """
    return min(score, max_score)


def calculate_weight_bonus(answer_records: list, question_map: dict) -> dict:
    """计算前两题破局加权分

    加权规则（评分标准.md 第3节）：
    - 第1题选A("做事快") + 第2题选C → A维度 +2分
    - 第1题选B("靠分析") + 第2题选C → T维度 +2分
    - 第1题选A("做事快") + 第2题选D → M维度 +2分
    - 第1题选B("靠分析") + 第2题选D → R维度 +2分

    Args:
        answer_records: 答题记录列表（dict 或 ORM 对象）
        question_map: exam_no → Question 的映射

    Returns:
        {"A": 0, "T": 0, "M": 0, "R": 0} 各维度加权分
    """
    bonus = {"A": 0, "T": 0, "M": 0, "R": 0}

    # 找到前两题（exam_no 为 A1, A2 的题目）
    q1_record = None
    q2_record = None
    for record in answer_records:
        exam_no = record.get("exam_no") if isinstance(record, dict) else getattr(record, "exam_no", None)
        if exam_no == "A1":
            q1_record = record
        elif exam_no == "A2":
            q2_record = record

    if not q1_record or not q2_record:
        return bonus

    def _get_option(record):
        if isinstance(record, dict):
            return record.get("selected_option", "")
        return getattr(record, "selected_option", "")

    q1_option = _get_option(q1_record)
    q2_option = _get_option(q2_record)

    # 第1题：A="做事快", B="靠分析"
    # 第2题：C/D 为破局选项
    q1_is_a = "快" in q1_option or q1_option.startswith("A")
    q1_is_b = "分析" in q1_option or q1_option.startswith("B")

    if q1_is_a and q2_option.startswith("C"):
        bonus["A"] = WEIGHT_BONUS_SCORE
    elif q1_is_b and q2_option.startswith("C"):
        bonus["T"] = WEIGHT_BONUS_SCORE
    elif q1_is_a and q2_option.startswith("D"):
        bonus["M"] = WEIGHT_BONUS_SCORE
    elif q1_is_b and q2_option.startswith("D"):
        bonus["R"] = WEIGHT_BONUS_SCORE

    return bonus
