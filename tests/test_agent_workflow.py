from app.services.agent_workflow import (
    build_agent_state,
    build_agent_trace,
    build_report_critic,
    build_agent_workflow_payload,
)


def test_agent_state_marks_conservative_policy_for_low_trust_and_missing_evidence():
    state = build_agent_state(
        trust_summary={
            "assessment_confidence": 0.58,
            "label": "中等",
            "anomaly_count": 3,
            "notes": ["存在较多异常作答"],
        },
        adaptive_metrics={"coverage_ratio": 0.75, "algorithm": "ATMR-CAT"},
        evidence_chain={"modules": {"A": {"evidence": [1]}, "T": {"evidence": []}}},
        module_debates={"A": "debate"},
        report_content="这是非临床参考报告。",
    )

    assert state["workflow"] == "evidence_constrained_static_agent"
    assert state["assessment_trust_level"] == "medium"
    assert state["report_policy"] == "conservative"
    assert "low_assessment_confidence" in state["risk_flags"]
    assert "incomplete_module_debate" in state["risk_flags"]
    assert state["evidence_status"] == "partial"


def test_agent_trace_contains_fixed_static_workflow_steps():
    state = {
        "rag_status": "available",
        "evidence_status": "available",
        "report_policy": "normal",
        "risk_flags": [],
        "critic_status": "passed",
    }

    trace = build_agent_trace(state)

    assert [step["key"] for step in trace["steps"]] == [
        "observe_assessment",
        "build_evidence_state",
        "multi_agent_analysis",
        "policy_selection",
        "safety_critic",
        "finalize_report",
    ]
    assert trace["steps"][0]["status"] == "done"
    assert trace["mode"] == "static_workflow"


def test_report_critic_detects_clinical_terms_and_missing_boundary():
    critic = build_report_critic("你可能患有抑郁症，需要治疗。")

    assert critic["status"] == "warning"
    assert "clinical_language" in critic["flags"]
    assert "missing_non_clinical_boundary" in critic["flags"]
    assert any("非临床" in note for note in critic["notes"])


def test_report_critic_passes_non_clinical_bounded_report():
    critic = build_report_critic("本报告仅作为非临床参考，帮助你理解人格倾向，不能替代专业诊断。")

    assert critic["status"] == "passed"
    assert critic["flags"] == []


def test_agent_workflow_payload_is_graceful_without_report():
    payload = build_agent_workflow_payload(
        trust_summary={},
        adaptive_metrics={},
        evidence_chain={},
        module_debates={},
        report_content=None,
    )

    assert payload["state"]["report_policy"] == "pending"
    assert payload["critic"]["status"] == "pending"
    assert payload["trace"]["steps"][-1]["status"] == "pending"
