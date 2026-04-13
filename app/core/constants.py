"""
项目共享常量
"""

# === 测评阶段配置 ===
STAGES = ["intro", "A", "T", "M", "R"]
TOTAL_QUESTIONS = 42

STAGE_NAMES = {
    "intro": "序章",
    "A": "欣赏型 (Appreciation)",
    "T": "目标型 (Target)",
    "M": "包容型 (Magnanimity)",
    "R": "责任型 (Responsibility)",
}

# 阶段 <-> 数据库 dimension_id 的映射（唯一真相源）
STAGE_DIM_MAP = {
    "intro": "1",
    "A": "6",
    "T": "4",
    "M": "5",
    "R": "7",
}

STAGE_QUESTION_COUNT = {
    "intro": 2,
    "A": 10,
    "T": 10,
    "M": 10,
    "R": 10,
}

# 兼容旧代码的别名
MODULES = ["A", "T", "M", "R"]
MODULE_NAMES = STAGE_NAMES
MODULE_DIM_MAP = {k: v for k, v in STAGE_DIM_MAP.items() if k != "intro"}

DIM_MODULE_MAP = {v: k for k, v in MODULE_DIM_MAP.items()}

# 阶段显示名称（短名）
MODULE_DISPLAY_NAMES = {
    "A": "欣赏型",
    "T": "目标型",
    "M": "包容型",
    "R": "责任型",
}

# === 评分标准配置 ===
DIMENSION_MAX_SCORE = 50  # 维度满分封顶
WEIGHT_BONUS_SCORE = 2  # 前两题加权加分分值

# 三分法等级阈值（维度基础满分50分，最低10分）
SCORE_LEVELS = {
    "low": {"min": 10, "max": 23, "label": "偏低", "color": "#3b82f6"},
    "medium": {"min": 24, "max": 37, "label": "中等", "color": "#8b5cf6"},
    "high": {"min": 38, "max": 50, "label": "偏高", "color": "#f59e0b"},
}
