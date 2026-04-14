"""
Pytest 共享 fixtures
"""

import pytest
import numpy as np
from unittest.mock import MagicMock, patch
from sqlalchemy import Column, Integer, String, Float, Boolean, Text, JSON, Numeric
from sqlalchemy.orm import Session


@pytest.fixture
def mock_db():
    """创建一个 mock 数据库 session"""
    db = MagicMock(spec=Session)
    return db


@pytest.fixture
def sample_question():
    """创建一个示例题目对象"""
    question = MagicMock()
    question.id = 1
    question.exam_no = "Q001"
    question.content = "这是一道测试题目"
    question.options = ["A. 完全不符合", "B. 比较不符合", "C. 不确定", "D. 比较符合", "E. 完全符合"]
    question.scores = [1, 2, 3, 4, 5]
    question.dimension_id = "6"
    question.is_reverse = False
    question.avg_time = 8.0
    question.feature_vector = [0.1, 0.2, 0.3, 0.4, 0.5]
    question.difficulty = 0.5
    question.discrimination = 0.7
    question.trait_label = "测试特质"
    return question
