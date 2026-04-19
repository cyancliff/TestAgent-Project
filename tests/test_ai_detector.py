"""
异常作答检测服务单元测试
"""

import pytest

from app.services.ai_detector import _build_follow_up, check_anomaly_and_generate_question


class TestBuildFollowUp:
    """测试异常追问生成"""

    def test_过快作答(self):
        result = _build_follow_up(["作答时间明显过快"])
        assert "很快" in result
        assert "具体说说" in result

    def test_无具体原因(self):
        result = _build_follow_up(["其他原因"])
        assert "原因" in result

    def test_空原因(self):
        result = _build_follow_up([])
        assert result is not None
        assert "原因" in result


class TestCheckAnomaly:
    """测试异常检测核心逻辑"""

    @pytest.mark.asyncio
    async def test_正常作答(self):
        result = await check_anomaly_and_generate_question(
            time_spent=8.0,
            avg_time=8.0,
            question_content="测试题目",
            selected_option="A",
            recent_answers=[],
            available_options=["A", "B"],
        )
        assert result["status"] == "normal"
        assert result["risk_score"] == 0
        assert result["follow_up"] is None
        assert result["reasons"] == []

    @pytest.mark.asyncio
    async def test_作答明显过快(self):
        result = await check_anomaly_and_generate_question(
            time_spent=0.5,
            avg_time=8.0,
            question_content="测试题目",
            selected_option="A",
            available_options=["A", "B"],
        )
        assert result["status"] == "anomaly"
        assert result["risk_score"] == 70
        assert result["reasons"] == ["作答时间明显过快"]
        assert result["follow_up"] is not None

    @pytest.mark.asyncio
    async def test_偏快但不再视为异常(self):
        result = await check_anomaly_and_generate_question(
            time_spent=2.5,
            avg_time=10.0,
            question_content="测试题目",
            selected_option="A",
            available_options=["A", "B"],
        )
        assert result["status"] == "normal"
        assert result["risk_score"] == 0
        assert result["reasons"] == []

    @pytest.mark.asyncio
    async def test_最近多题连续快速作答不再触发异常(self):
        recent_answers = [
            {"exam_no": "Q1", "selected_option": "A", "time_spent": 1.0, "score": 3.0, "is_anomaly": 0},
            {"exam_no": "Q2", "selected_option": "B", "time_spent": 1.0, "score": 3.0, "is_anomaly": 0},
            {"exam_no": "Q3", "selected_option": "A", "time_spent": 1.0, "score": 3.0, "is_anomaly": 0},
            {"exam_no": "Q4", "selected_option": "B", "time_spent": 1.0, "score": 3.0, "is_anomaly": 0},
        ]
        result = await check_anomaly_and_generate_question(
            time_spent=3.0,
            avg_time=10.0,
            question_content="测试题目",
            selected_option="A",
            recent_answers=recent_answers,
            available_options=["A", "B"],
        )
        assert result["status"] == "normal"
        assert result["risk_score"] == 0

    @pytest.mark.asyncio
    async def test_重复选项不再触发异常(self):
        recent_answers = [
            {"exam_no": "Q1", "selected_option": "A", "time_spent": 10.0, "score": 3.0, "is_anomaly": 0},
            {"exam_no": "Q2", "selected_option": "A", "time_spent": 10.0, "score": 3.0, "is_anomaly": 0},
            {"exam_no": "Q3", "selected_option": "A", "time_spent": 10.0, "score": 3.0, "is_anomaly": 0},
        ]
        result = await check_anomaly_and_generate_question(
            time_spent=10.0,
            avg_time=10.0,
            question_content="测试题目",
            selected_option="A",
            recent_answers=recent_answers,
            available_options=["A", "B", "C"],
        )
        assert result["status"] == "normal"
        assert result["risk_score"] == 0

    @pytest.mark.asyncio
    async def test_所选答案不在选项中(self):
        with pytest.raises(ValueError, match="所选答案不在题目选项中"):
            await check_anomaly_and_generate_question(
                time_spent=5.0,
                avg_time=8.0,
                question_content="测试题目",
                selected_option="Z",
                available_options=["A", "B"],
            )

    @pytest.mark.asyncio
    async def test_recent_answers_none(self):
        result = await check_anomaly_and_generate_question(
            time_spent=5.0,
            avg_time=8.0,
            question_content="测试题目",
            selected_option="A",
            recent_answers=None,
            available_options=["A", "B"],
        )
        assert result["status"] == "normal"
