from types import SimpleNamespace

from app.services.assessment_trust import (
    build_adaptive_metrics,
    build_answer_insight,
    build_assessment_trust_summary,
    build_evidence_chain,
    calculate_answer_confidence,
)


def test_answer_confidence_rewards_explanation_for_anomaly():
    without_explanation = calculate_answer_confidence(risk_score=70, is_anomaly=True, user_explanation="")
    with_explanation = calculate_answer_confidence(risk_score=70, is_anomaly=True, user_explanation="我看到关键词后马上判断。")

    assert with_explanation > without_explanation
    assert 0.2 <= without_explanation <= 1.0


def test_build_assessment_trust_summary_groups_by_dimension():
    answer_items = [
        {"exam_no": "A1", "module": "A", "answer_confidence": 0.9, "risk_score": 0, "is_anomaly": False},
        {"exam_no": "A2", "module": "A", "answer_confidence": 0.5, "risk_score": 70, "is_anomaly": True},
        {"exam_no": "T1", "module": "T", "answer_confidence": 0.8, "risk_score": 0, "is_anomaly": False},
    ]

    summary = build_assessment_trust_summary(answer_items)

    assert summary["assessment_confidence"] < 0.9
    assert summary["anomaly_count"] == 1
    assert summary["dimension_confidence"]["A"]["anomaly_count"] == 1
    assert summary["dimension_confidence"]["T"]["question_count"] == 1


def test_build_answer_insight_and_evidence_chain():
    question = SimpleNamespace(dimension_id="6", trait_label="欣赏线索")
    record = {
        "exam_no": "A1",
        "score": 5,
        "is_anomaly": 1,
        "risk_score": 70,
        "risk_reasons": ["作答时间明显过快"],
        "answer_confidence": 0.45,
        "behavior_metrics": {"first_action_latency": 0.2, "mouse_move_count": 0},
    }

    insight = build_answer_insight(record, question)
    chain = build_evidence_chain([insight])
    metrics = build_adaptive_metrics([insight])

    assert insight["module"] == "A"
    assert insight["behavior_metrics"]["first_action_latency"] == 0.2
    assert insight["support_strength"] == "强支持"
    assert chain["modules"]["A"]["evidence"][0]["exam_no"] == "A1"
    assert metrics["algorithm"] == "ATMR-CAT"
