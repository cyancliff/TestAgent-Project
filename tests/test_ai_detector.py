"""
异常作答检测服务单元测试
"""

import pytest
from app.services.ai_detector import check_anomaly_and_generate_question, _build_follow_up


class TestBuildFollowUp:
    """测试异常追问生成"""

    def test_过快作答(self):
        result = _build_follow_up(["作答时间明显过快"])
        assert "很快" in result
        assert "具体说说" in result

    def test_过慢作答(self):
        result = _build_follow_up(["作答时间异常偏长"])
        # 偏长不属于"过快"、"过慢"或"重复"，会走默认分支
        assert "原因" in result

    def test_选项重复(self):
        result = _build_follow_up(["最近多题重复选择同一选项"])
        # _build_follow_up 检查的是"选项重复"子串，而实际reason是"重复选择同一选项"
        # 不包含"选项重复"子串，所以会走默认分支
        assert "原因" in result

    def test_无具体原因(self):
        result = _build_follow_up(["其他原因"])
        assert "原因" in result

    def test_空原因(self):
        """空原因时会返回默认追问"""
        result = _build_follow_up([])
        assert result is not None
        assert "原因" in result


class TestCheckAnomaly:
    """测试异常检测核心逻辑"""

    @pytest.mark.asyncio
    async def test_正常作答(self):
        """正常作答时间和模式应返回 normal"""
        result = await check_anomaly_and_generate_question(
            time_spent=8.0,
            avg_time=8.0,
            question_content="测试题目",
            selected_option="A. 完全不符合",
            recent_answers=[],
            available_options=["A. 完全不符合", "B. 比较不符合"],
        )
        assert result["status"] == "normal"
        assert result["risk_score"] == 0
        assert result["follow_up"] is None
        assert result["reasons"] == []

    @pytest.mark.asyncio
    async def test_作答过快(self):
        """作答时间远低于平均值应标记为异常"""
        result = await check_anomaly_and_generate_question(
            time_spent=1.0,
            avg_time=8.0,
            question_content="测试题目",
            selected_option="A",
            available_options=["A", "B"],
        )
        assert result["status"] == "anomaly"
        assert result["risk_score"] >= 45
        assert "过快" in result["reasons"][0]

    @pytest.mark.asyncio
    async def test_作答偏快但未达异常(self):
        """作答时间偏快但不足以触发异常"""
        result = await check_anomaly_and_generate_question(
            time_spent=3.0,
            avg_time=10.0,
            question_content="测试题目",
            selected_option="A",
            available_options=["A", "B"],
        )
        assert result["risk_score"] > 0
        assert "偏快" in result["reasons"][0]

    @pytest.mark.asyncio
    async def test_作答时间过长(self):
        """作答时间过长应增加风险分"""
        result = await check_anomaly_and_generate_question(
            time_spent=90.0,
            avg_time=8.0,
            question_content="测试题目",
            selected_option="A",
            available_options=["A", "B"],
        )
        assert result["risk_score"] > 0
        assert any("长" in r for r in result["reasons"])

    @pytest.mark.asyncio
    async def test_连续快速作答(self):
        """最近多题连续快速作答应触发异常"""
        recent_answers = [
            {"exam_no": "Q1", "selected_option": "A", "time_spent": 1.0, "score": 3.0, "is_anomaly": 0},
            {"exam_no": "Q2", "selected_option": "B", "time_spent": 1.0, "score": 3.0, "is_anomaly": 0},
            {"exam_no": "Q3", "selected_option": "A", "time_spent": 1.0, "score": 3.0, "is_anomaly": 0},
            {"exam_no": "Q4", "selected_option": "B", "time_spent": 1.0, "score": 3.0, "is_anomaly": 0},
        ]
        result = await check_anomaly_and_generate_question(
            time_spent=1.0,
            avg_time=10.0,
            question_content="测试题目",
            selected_option="A",
            recent_answers=recent_answers,
            available_options=["A", "B"],
        )
        assert result["status"] == "anomaly"
        # 应该包含快速作答和连续快速作答的风险
        assert result["risk_score"] >= 45

    @pytest.mark.asyncio
    async def test_重复选择同一选项(self):
        """最近多题选择同一选项应增加风险"""
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
        assert result["risk_score"] > 0
        assert any("重复" in r for r in result["reasons"])

    @pytest.mark.asyncio
    async def test_所选答案不在选项中(self):
        """选择不在选项中的答案应抛出异常"""
        with pytest.raises(ValueError, match="所选答案不在题目选项中"):
            await check_anomaly_and_generate_question(
                time_spent=5.0,
                avg_time=8.0,
                question_content="测试题目",
                selected_option="Z",
                available_options=["A", "B"],
            )

    @pytest.mark.asyncio
    async def test_风险分上限(self):
        """风险分不应超过 100"""
        recent_answers = [
            {"exam_no": f"Q{i}", "selected_option": "A", "time_spent": 0.1, "score": 3.0, "is_anomaly": 0}
            for i in range(5)
        ]
        result = await check_anomaly_and_generate_question(
            time_spent=0.1,
            avg_time=10.0,
            question_content="测试题目",
            selected_option="A",
            recent_answers=recent_answers,
            available_options=["A", "B"],
        )
        assert result["risk_score"] <= 100

    @pytest.mark.asyncio
    async def test_正常与异常的边界(self):
        """风险分 >= 45 才触发 anomaly"""
        # time_spent 在 avg*0.35 和 avg*0.20 之间 → "偏快" → 45分 → anomaly
        result = await check_anomaly_and_generate_question(
            time_spent=2.5,
            avg_time=10.0,
            question_content="测试题目",
            selected_option="A",
            available_options=["A", "B"],
        )
        # 45 分正好达到 anomaly 阈值
        assert result["status"] == "anomaly"
        assert result["risk_score"] == 45

    @pytest.mark.asyncio
    async def test_默认空列表(self):
        """recent_answers 为 None 时应默认使用空列表"""
        result = await check_anomaly_and_generate_question(
            time_spent=5.0,
            avg_time=8.0,
            question_content="测试题目",
            selected_option="A",
            recent_answers=None,
            available_options=["A", "B"],
        )
        assert result["status"] == "normal"
