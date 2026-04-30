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
        assert result["answer_confidence"] == 1.0

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
        assert result["follow_up"] is None
        assert result["answer_confidence"] < 0.6

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
    async def test_近期异常密度触发异常(self):
        recent_answers = [
            {"exam_no": "Q1", "selected_option": "A", "time_spent": 1.0, "score": 3.0, "is_anomaly": 1},
            {"exam_no": "Q2", "selected_option": "B", "time_spent": 1.0, "score": 3.0, "is_anomaly": 1},
            {"exam_no": "Q3", "selected_option": "C", "time_spent": 8.0, "score": 3.0, "is_anomaly": 0},
            {"exam_no": "Q4", "selected_option": "B", "time_spent": 1.0, "score": 3.0, "is_anomaly": 0},
        ]
        result = await check_anomaly_and_generate_question(
            time_spent=0.8,
            avg_time=10.0,
            question_content="测试题目",
            selected_option="C",
            recent_answers=recent_answers,
            available_options=["A", "B", "C"],
        )
        assert result["status"] == "anomaly"
        assert "近期异常作答密度较高" in result["reasons"]

    @pytest.mark.asyncio
    async def test_重复选项触发异常(self):
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
        assert result["status"] == "anomaly"
        assert "连续多题选择同一选项" in result["reasons"]

    @pytest.mark.asyncio
    async def test_前台行为特征触发后台风险(self):
        result = await check_anomaly_and_generate_question(
            time_spent=1.8,
            avg_time=8.0,
            question_content="测试题目",
            selected_option="B",
            recent_answers=[],
            available_options=["A", "B", "C"],
            behavior_metrics={
                "first_action_latency": 0.18,
                "mouse_move_count": 0,
                "mouse_path_length": 0,
                "pointer_down_count": 2,
                "option_change_count": 4,
                "option_change_path": ["A", "B", "C", "B"],
                "focus_blur_count": 0,
                "idle_time": 0,
                "rapid_click_flag": False,
            },
        )

        assert result["status"] == "anomaly"
        assert "首次交互过快" in result["reasons"]
        assert "作答过程几乎无前台交互" in result["reasons"]
        assert "选项反复更改" in result["reasons"]
        assert result["behavior_metrics"]["option_change_count"] == 4

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
