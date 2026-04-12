"""
项目共享常量
"""

# === 测评配置 ===
TOTAL_QUESTIONS = 42
FIXED_QUESTIONS = 2
QUESTIONS_PER_MODULE = 10
MODULES = ["A", "T", "M", "R"]
MODULE_NAMES = {
    "A": "欣赏型 (Appreciation)",
    "T": "目标型 (Target)",
    "M": "包容型 (Magnanimity)",
    "R": "责任型 (Responsibility)",
}

# 模块 <-> 数据库 dimension_id 的映射（唯一真相源）
MODULE_DIM_MAP = {
    "A": "6",
    "T": "4",
    "M": "5",
    "R": "7",
}

DIM_MODULE_MAP = {v: k for k, v in MODULE_DIM_MAP.items()}

# 模块显示名称
MODULE_DISPLAY_NAMES = {
    "A": "欣赏型",
    "T": "目标型",
    "M": "包容型",
    "R": "责任型",
}

# === 模块辩论配置 ===
MODULE_COOLDOWN_SECONDS = 30
