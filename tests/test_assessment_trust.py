from types import SimpleNamespace

from app.services.assessment_trust import (
    build_adaptive_metrics,
    build_answer_insight,
    build_assessment_trust_summary,
    build_confidence_weighted_score_reference,
    build_evidence_chain,
    calculate_answer_confidence,
)


def test_answer_confidence_uses_risk_and_anomaly_only():
    normal = calculate_answer_confidence(risk_score=0, is_anomaly=False)
    anomaly = calculate_answer_confidence(risk_score=70, is_anomaly=True, user_explanation="历史兼容解释不再加分")
    floor = calculate_answer_confidence(risk_score=100, is_anomaly=True)

    assert normal == 1.0
    assert anomaly == 0.465
    assert floor == 0.27


def test_answer_confidence_has_lower_bound_for_extreme_risk():
    assert calculate_answer_confidence(risk_score=200, is_anomaly=True) == 0.27
    assert calculate_answer_confidence(risk_score=500, is_anomaly=True) == 0.27


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


def test_dimension_confidence_combines_mean_completion_and_anomaly_penalty():
    partial_records = [
        {"exam_no": f"A{i}", "module": "A", "answer_confidence": 1.0, "risk_score": 0, "is_anomaly": False}
        for i in range(5)
    ]
    full_records = [
        {"exam_no": f"A{i}", "module": "A", "answer_confidence": 1.0, "risk_score": 0, "is_anomaly": False}
        for i in range(10)
    ]
    anomalous_records = full_records[:-2] + [
        {"exam_no": "AX1", "module": "A", "answer_confidence": 0.465, "risk_score": 70, "is_anomaly": True},
        {"exam_no": "AX2", "module": "A", "answer_confidence": 0.465, "risk_score": 70, "is_anomaly": True},
    ]

    partial = build_assessment_trust_summary(partial_records)["dimension_confidence"]["A"]
    full = build_assessment_trust_summary(full_records)["dimension_confidence"]["A"]
    anomalous = build_assessment_trust_summary(anomalous_records)["dimension_confidence"]["A"]

    assert partial["confidence"] == 0.925
    assert full["confidence"] == 1.0
    assert anomalous["confidence"] < full["confidence"]
    assert anomalous["anomaly_count"] == 2


def test_assessment_confidence_applies_capped_global_anomaly_penalty():
    records = [
        {"exam_no": f"A{i}", "module": "A", "answer_confidence": 1.0, "risk_score": 0, "is_anomaly": False}
        for i in range(5)
    ] + [
        {"exam_no": f"T{i}", "module": "T", "answer_confidence": 0.9, "risk_score": 20, "is_anomaly": True}
        for i in range(20)
    ]

    summary = build_assessment_trust_summary(records)

    assert summary["anomaly_count"] == 20
    assert summary["assessment_confidence"] == 0.8
    assert summary["label"] == "较高"


def test_confidence_weighted_reference_matches_raw_when_all_confident():
    records = [
        {"score": 4, "answer_confidence": 1.0},
        {"score": 5, "answer_confidence": 1.0},
        {"score": 3, "answer_confidence": 1.0},
    ]

    reference = build_confidence_weighted_score_reference(records, primary_total_score=12)

    assert reference["confidence_weighted_raw_score"] == 12
    assert reference["confidence_weighted_score"] == 12
    assert reference["confidence_weighted_delta"] == 0


def test_confidence_weighted_reference_downweights_low_confidence_high_score():
    records = [
        {"score": 5, "answer_confidence": 0.2},
        {"score": 3, "answer_confidence": 1.0},
    ]

    reference = build_confidence_weighted_score_reference(records, primary_total_score=8)

    assert reference["confidence_weighted_score"] == 6.67
    assert reference["confidence_weighted_delta"] == -1.33


def test_confidence_weighted_reference_downweights_low_confidence_low_score():
    records = [
        {"score": 1, "answer_confidence": 0.2},
        {"score": 3, "answer_confidence": 1.0},
    ]

    reference = build_confidence_weighted_score_reference(records, primary_total_score=4)

    assert reference["confidence_weighted_score"] == 5.33
    assert reference["confidence_weighted_delta"] == 1.33


def test_confidence_weighted_reference_falls_back_when_confidence_sum_is_zero():
    records = [
        {"score": 4, "answer_confidence": 0.0},
        {"score": 2, "answer_confidence": 0.0},
    ]

    reference = build_confidence_weighted_score_reference(records, primary_total_score=6)

    assert reference["confidence_weighted_score"] == 6
    assert reference["confidence_weighted_delta"] == 0


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
