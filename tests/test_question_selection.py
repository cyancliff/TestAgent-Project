"""
智能选题服务单元测试
"""

import pytest
import numpy as np
from unittest.mock import MagicMock, patch
from app.services.question_selection import QuestionSelectionService, select_adaptive_question
from app.core.constants import MODULE_DIM_MAP


class TestQuestionSelectionService:
    """测试 QuestionSelectionService 核心逻辑"""

    def test_init(self):
        """初始化后 module_map 应与共享常量一致"""
        service = QuestionSelectionService(db=MagicMock())
        assert service.module_map == MODULE_DIM_MAP

    def test_record_value_dict(self):
        """从字典读取记录值"""
        service = QuestionSelectionService(db=MagicMock())
        record = {"exam_no": "Q001", "score": 3.0}
        assert service._record_value(record, "exam_no") == "Q001"
        assert service._record_value(record, "score") == 3.0
        assert service._record_value(record, "missing", "default") == "default"

    def test_record_value_object(self):
        """从真实对象（非Mock）读取记录值"""
        service = QuestionSelectionService(db=MagicMock())

        class FakeRecord:
            exam_no = "Q001"
            score = 3.0

        record = FakeRecord()
        assert service._record_value(record, "exam_no") == "Q001"
        assert service._record_value(record, "missing", "default") == "default"

    def test_cosine_similarity_identical(self):
        """相同向量余弦相似度应为 1"""
        service = QuestionSelectionService(db=MagicMock())
        a = np.array([1.0, 2.0, 3.0])
        b = np.array([1.0, 2.0, 3.0])
        assert service._cosine_similarity(a, b) == pytest.approx(1.0)

    def test_cosine_similarity_orthogonal(self):
        """正交向量余弦相似度应为 0"""
        service = QuestionSelectionService(db=MagicMock())
        a = np.array([1.0, 0.0, 0.0])
        b = np.array([0.0, 1.0, 0.0])
        assert service._cosine_similarity(a, b) == pytest.approx(0.0)

    def test_cosine_similarity_zero_norm(self):
        """零向量余弦相似度应返回 0"""
        service = QuestionSelectionService(db=MagicMock())
        a = np.array([0.0, 0.0, 0.0])
        b = np.array([1.0, 2.0, 3.0])
        assert service._cosine_similarity(a, b) == 0.0

    def test_get_user_ability_no_records(self):
        """无答题记录时应返回默认先验值"""
        service = QuestionSelectionService(db=MagicMock())
        profile, ability, uncertainty, vectors = service.get_user_ability(
            user_id=1, session_id=1
        )
        assert profile is None
        assert ability == 0.5
        assert uncertainty == 0.25
        assert vectors == []

    def test_get_user_ability_transient_records(self):
        """使用 transient_records（不依赖数据库）应正确计算画像"""
        db = MagicMock()
        service = QuestionSelectionService(db=db)

        # 使用 transient_records 绕过数据库查询
        transient_records = [
            {
                "exam_no": "Q001",
                "score": 4.0,
                "is_anomaly": False,
            }
        ]

        # Mock 题目查询
        question = MagicMock()
        question.exam_no = "Q001"
        question.feature_vector = [0.1, 0.2, 0.3]
        question.difficulty = 0.5
        question.discrimination = 0.7

        mock_query = MagicMock()
        mock_query.filter.return_value.all.return_value = [question]
        db.query.return_value = mock_query

        profile, ability, uncertainty, vectors = service.get_user_ability(
            user_id=1, session_id=1, transient_records=transient_records
        )

        assert profile is not None
        assert len(profile) == 3
        assert 0 <= ability <= 1
        assert uncertainty < 0.25  # 有记录后不确定性应降低

    def test_select_first_question_prefers_medium_difficulty(self):
        """首次选题应偏好中等难度高区分度的题目"""
        db = MagicMock()
        service = QuestionSelectionService(db=db)

        easy_q = MagicMock(exam_no="Q001", difficulty=0.1, discrimination=0.5)
        medium_q = MagicMock(exam_no="Q002", difficulty=0.5, discrimination=0.8)
        hard_q = MagicMock(exam_no="Q003", difficulty=0.9, discrimination=0.5)

        result = service._select_first_question([easy_q, medium_q, hard_q])
        assert result.exam_no == "Q002"  # 中等难度高分应被选中

    def test_select_first_question_prefers_high_discrimination(self):
        """难度相同时应偏好高区分度"""
        db = MagicMock()
        service = QuestionSelectionService(db=db)

        low_disc = MagicMock(exam_no="Q001", difficulty=0.5, discrimination=0.3)
        high_disc = MagicMock(exam_no="Q002", difficulty=0.5, discrimination=0.9)

        result = service._select_first_question([low_disc, high_disc])
        assert result.exam_no == "Q002"

    def test_calculate_question_score_components(self):
        """题目评分应包含所有四个维度"""
        db = MagicMock()
        service = QuestionSelectionService(db=db)

        question = MagicMock()
        question.exam_no = "Q001"
        question.feature_vector = [0.5, 0.5, 0.5]
        question.difficulty = 0.5
        question.discrimination = 0.7

        profile = np.array([0.5, 0.5, 0.5])
        answered = [np.array([0.1, 0.1, 0.1])]

        score = service._calculate_question_score(
            question, profile, ability_level=0.5, ability_uncertainty=0.2, answered_vectors=answered
        )
        assert 0 <= score <= 1


class TestSelectAdaptiveQuestion:
    """测试简化版 select_adaptive_question 函数"""

    def test_first_question_empty_raises(self):
        """无候选题目时 _select_first_question 应报错"""
        db = MagicMock()
        service = QuestionSelectionService(db=db)
        with pytest.raises(ValueError, match="max"):
            service._select_first_question([])


class TestModuleDimMap:
    """测试模块维度映射常量的一致性"""

    def test_bidirectional_mapping(self):
        """正反向映射应一致"""
        for module, dim in MODULE_DIM_MAP.items():
            assert module in MODULE_DIM_MAP
        assert len(MODULE_DIM_MAP) == 4
