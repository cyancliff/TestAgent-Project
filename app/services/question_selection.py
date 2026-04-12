"""
智能选题服务
基于贝叶斯能力估计和信息增益的自适应选题算法。

核心思路：
- 贝叶斯能力估计：先验 N(0.5, 0.25)，每答一题根据得分和题目参数更新后验
- 用户画像向量 = 已答题目特征向量的加权平均（异常作答降权）
- 选题策略 = Fisher信息量 + 覆盖度 + 难度匹配 + 区分度（权重随不确定性动态调整）
"""

import logging
import os
from typing import Any

import numpy as np
from sqlalchemy.orm import Session

from app.core.constants import MODULE_DIM_MAP
from app.models.question import AnswerRecord, Question

# 配置日志
log_level = os.environ.get("QUESTION_SELECTION_LOG_LEVEL", "INFO").upper()
log_level = getattr(logging, log_level, logging.INFO)

logging.basicConfig(
    level=log_level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


class QuestionSelectionService:
    """智能选题服务"""

    def __init__(self, db: Session):
        self.db = db
        self.module_map = MODULE_DIM_MAP

    @staticmethod
    def _record_value(record: Any, key: str, default=None):
        if isinstance(record, dict):
            return record.get(key, default)
        return getattr(record, key, default)

    def get_user_ability(
        self,
        user_id: int,
        session_id: int | None = None,
        module: str | None = None,
        transient_records: list[Any] | None = None,
    ) -> tuple[np.ndarray | None, float, float, list[np.ndarray]]:
        """
        计算用户作答画像向量和贝叶斯能力估计

        Returns:
            (profile_vector, ability_level, ability_uncertainty, answered_vectors)
            - profile_vector: 加权平均的作答画像向量
            - ability_level: 贝叶斯后验能力均值 (0-1)
            - ability_uncertainty: 贝叶斯后验方差（越小越确定）
            - answered_vectors: 已答题目的特征向量列表
        """
        logger.info(f"[ABILITY] 计算用户画像 - 用户ID: {user_id}, 会话ID: {session_id}, 模块: {module or '所有'}")

        if transient_records is not None:
            records = transient_records
        else:
            query = self.db.query(AnswerRecord).filter(AnswerRecord.user_id == user_id)
            if session_id:
                query = query.filter(AnswerRecord.session_id == session_id)
            records = query.all()

        if not records:
            logger.info("[ABILITY] 无答题记录")
            return None, 0.5, 0.25, []

        record_exam_nos = [self._record_value(r, "exam_no") for r in records]
        questions = self.db.query(Question).filter(Question.exam_no.in_(record_exam_nos)).all()
        question_map = {q.exam_no: q for q in questions}

        vectors = []
        weights = []
        answered_vectors = []

        # 贝叶斯能力估计：先验 N(mu=0.5, sigma2=0.25)
        mu = 0.5
        sigma2 = 0.25

        for record in records:
            exam_no = self._record_value(record, "exam_no")
            question = question_map.get(exam_no)
            if not question:
                continue

            if module is not None:
                target_dimension = self.module_map.get(module)
                if target_dimension is None or question.dimension_id != target_dimension:
                    continue

            if not question.feature_vector:
                continue

            is_anomaly = bool(self._record_value(record, "is_anomaly", False))
            score = float(self._record_value(record, "score", 0) or 0)

            vector = np.array(question.feature_vector)
            answered_vectors.append(vector)

            weight = 0.5 if is_anomaly else 1.0
            vectors.append(vector)
            weights.append(weight)

            score_norm = score / 5.0  # 归一化到 0-1
            discrimination = float(question.discrimination or 0.5)

            anomaly_factor = 0.3 if is_anomaly else 1.0

            # 观测精度 = 区分度决定了这道题提供多少信息
            obs_precision = discrimination * 2.0 * anomaly_factor

            # 贝叶斯正态-正态共轭更新
            prior_precision = 1.0 / sigma2
            posterior_precision = prior_precision + obs_precision

            # 观测信号：得分归一化值（已经包含了能力信息）
            observed_ability = score_norm

            mu = (prior_precision * mu + obs_precision * observed_ability) / posterior_precision
            sigma2 = 1.0 / posterior_precision

        if not vectors:
            logger.info("[ABILITY] 无有效特征向量")
            return None, 0.5, 0.25, []

        # 计算画像向量
        weights_array = np.array(weights)
        weights_normalized = weights_array / (weights_array.sum() + 1e-10)
        vectors_array = np.array(vectors)
        profile_vector = np.average(vectors_array, axis=0, weights=weights_normalized)

        # 确保能力值在合理范围
        mu = float(np.clip(mu, 0.0, 1.0))
        sigma2 = float(max(sigma2, 1e-6))

        logger.info(f"[ABILITY] 有效记录: {len(vectors)}, 能力水平: {mu:.3f}, 不确定性: {sigma2:.4f}")

        return profile_vector, mu, sigma2, answered_vectors

    # 保持旧接口兼容
    def get_user_ability_vector(
        self,
        user_id: int,
        session_id: int | None = None,
        module: str | None = None,
        transient_records: list[Any] | None = None,
    ) -> tuple[np.ndarray | None, float, list[np.ndarray]]:
        """兼容旧接口"""
        profile_vector, ability_level, _, answered_vectors = self.get_user_ability(
            user_id, session_id, module, transient_records=transient_records
        )
        return profile_vector, ability_level, answered_vectors

    def select_next_question(
        self,
        user_id: int,
        session_id: int,
        answered_question_ids: list[int],
        module: str | None = None,
        transient_records: list[Any] | None = None,
    ) -> Question | None:
        """
        智能选择下一题

        策略：Fisher信息量 + 覆盖度 + 难度匹配 + 区分度
        权重随能力不确定性动态调整
        """
        logger.info(
            f"[SELECT] 开始选题 - 用户: {user_id}, 已答: {len(answered_question_ids)}题, 模块: {module or '无'}"
        )

        if transient_records == []:
            transient_records = None

        # 1. 获取用户画像和能力水平
        profile_vector, ability_level, ability_uncertainty, answered_vectors = self.get_user_ability(
            user_id, session_id, module, transient_records=transient_records
        )

        # 2. 获取候选题目
        query = self.db.query(Question).filter(Question.id.notin_(answered_question_ids))
        if module:
            if module in self.module_map:
                query = query.filter(Question.dimension_id == self.module_map[module])

        candidate_questions = query.all()
        logger.info(f"[SELECT] 候选题目: {len(candidate_questions)}")

        if not candidate_questions:
            return None

        # 3. 首次答题策略
        if profile_vector is None:
            return self._select_first_question(candidate_questions)

        # 4. 计算每个候选题目的推荐分数
        question_scores = []
        for question in candidate_questions:
            score = self._calculate_question_score(
                question, profile_vector, ability_level, ability_uncertainty, answered_vectors
            )
            question_scores.append((question, score))

        if not question_scores:
            return None

        # 选择分数最高的题目
        best_question, best_score = max(question_scores, key=lambda x: x[1])

        # 日志：前3名
        top3 = sorted(question_scores, key=lambda x: x[1], reverse=True)[:3]
        for i, (q, s) in enumerate(top3):
            logger.info(
                f"  Top{i + 1}: {q.exam_no} 分数={s:.4f} 难度={float(q.difficulty or 0.5):.2f} 区分度={float(q.discrimination or 0.7):.2f}"
            )

        return best_question

    def _select_first_question(self, candidate_questions: list[Question]) -> Question:
        """
        选择第一题：中等难度 + 高区分度
        """
        question_scores = []
        for question in candidate_questions:
            difficulty = float(question.difficulty or 0.5)
            discrimination = float(question.discrimination or 0.7)

            difficulty_score = 1.0 - abs(difficulty - 0.5) * 2
            discrimination_score = discrimination

            score = 0.6 * difficulty_score + 0.4 * discrimination_score
            question_scores.append((question, score))

        best_question, best_score = max(question_scores, key=lambda x: x[1])
        logger.info(f"[FIRST] 选择: {best_question.exam_no}, 分数={best_score:.4f}")
        return best_question

    def _calculate_question_score(
        self,
        question: Question,
        profile_vector: np.ndarray,
        ability_level: float,
        ability_uncertainty: float,
        answered_vectors: list[np.ndarray],
    ) -> float:
        """
        计算题目的推荐分数

        四个维度（权重随不确定性动态调整）：
        1. Fisher信息量：该题对缩小能力不确定性的贡献
        2. 覆盖度：与已答题越不同越好
        3. 难度匹配：题目难度与用户能力水平匹配
        4. 区分度：高区分度题目优先
        """
        difficulty = float(question.difficulty or 0.5)
        discrimination = float(question.discrimination or 0.5)

        # 1. Fisher信息量
        # 区分度高 + 难度接近能力水平 → 该题能最有效地缩小不确定性
        fisher_info = (discrimination**2) * np.exp(-((difficulty - ability_level) ** 2) / (2 * 0.15))
        # 归一化到 0~1
        fisher_info = float(np.clip(fisher_info, 0.0, 1.0))

        # 2. 覆盖度（信息增益）
        if question.feature_vector and answered_vectors:
            question_vector = np.array(question.feature_vector)
            similarities = [abs(self._cosine_similarity(question_vector, av)) for av in answered_vectors]
            avg_similarity = float(np.mean(similarities))
            coverage_score = 1.0 - avg_similarity
        else:
            coverage_score = 0.5

        # 3. 难度匹配
        difficulty_match = 1.0 - abs(difficulty - ability_level)

        # 4. 区分度
        discrimination_score = discrimination

        # === 动态权重 ===
        # 不确定性高时（前几题）：Fisher信息量权重高，快速锁定能力
        # 不确定性低时（后面的题）：覆盖度权重高，拓宽诊断面
        uncertainty_ratio = min(ability_uncertainty / 0.25, 1.0)  # 0~1，越大越不确定

        # 不确定时：更看重Fisher信息量和区分度
        # 确定后：更看重覆盖度和难度匹配
        w_fisher = 0.15 + 0.25 * uncertainty_ratio  # 0.15 ~ 0.40
        w_coverage = 0.40 - 0.15 * uncertainty_ratio  # 0.25 ~ 0.40
        w_difficulty = 0.25 - 0.05 * uncertainty_ratio  # 0.20 ~ 0.25
        w_discrimination = 0.20 - 0.05 * uncertainty_ratio  # 0.15 ~ 0.20

        score = (
            w_fisher * fisher_info
            + w_coverage * coverage_score
            + w_difficulty * difficulty_match
            + w_discrimination * discrimination_score
        )

        logger.debug(
            f"[SCORE] {question.exam_no}: 总分={score:.4f} "
            f"(Fisher={fisher_info:.3f}×{w_fisher:.2f}, 覆盖={coverage_score:.3f}×{w_coverage:.2f}, "
            f"难度匹配={difficulty_match:.3f}×{w_difficulty:.2f}, 区分度={discrimination_score:.3f}×{w_discrimination:.2f})"
        )

        return score

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """计算余弦相似度"""
        dot_product = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot_product / (norm_a * norm_b)

    def get_adaptive_test_plan(
        self, user_id: int, session_id: int, total_questions: int = 10, modules: list[str] = None
    ) -> list[Question]:
        """生成自适应测评计划"""
        if modules is None:
            modules = ["A", "T", "M", "R"]

        questions_per_module = max(1, total_questions // len(modules))
        selected_questions = []
        answered_ids = []

        for module in modules:
            for _ in range(questions_per_module):
                question = self.select_next_question(user_id, session_id, answered_ids, module)
                if question:
                    selected_questions.append(question)
                    answered_ids.append(question.id)

        if len(selected_questions) < total_questions:
            remaining = total_questions - len(selected_questions)
            extra = self.db.query(Question).filter(Question.id.notin_(answered_ids)).limit(remaining).all()
            selected_questions.extend(extra)

        return selected_questions[:total_questions]


# 简化版选题函数（用于直接集成）
def select_adaptive_question(
    db: Session, user_id: int, session_id: int, answered_question_nos: list[str]
) -> dict | None:
    """简化版自适应选题函数"""
    logger.info(f"[API] 自适应选题 - 用户: {user_id}, 已答: {len(answered_question_nos)}题")

    service = QuestionSelectionService(db)

    # 批量查询，避免 N+1
    answered_questions = (
        db.query(Question).filter(Question.exam_no.in_(answered_question_nos)).all() if answered_question_nos else []
    )
    answered_ids = [q.id for q in answered_questions]

    profile_vector, ability_level, _ = service.get_user_ability_vector(user_id, session_id, None)

    selected_question = service.select_next_question(user_id, session_id, answered_ids)

    if selected_question:
        similarity = None
        if profile_vector is not None and selected_question.feature_vector:
            question_vector = np.array(selected_question.feature_vector)
            similarity = service._cosine_similarity(profile_vector, question_vector)

        return {
            "question": selected_question,
            "similarity": similarity,
            "ability_level": ability_level,
            "ability_vector_exists": profile_vector is not None,
        }
    return None
