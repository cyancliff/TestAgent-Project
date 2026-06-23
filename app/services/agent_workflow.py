"""Pure helpers for the evidence-constrained static agent workflow."""

from __future__ import annotations

from typing import Any


WORKFLOW_NAME = "evidence_constrained_static_agent"

CLINICAL_TERMS = (
    "抑郁症",
    "焦虑症",
    "躁郁",
    "双相",
    "人格障碍",
    "精神疾病",
    "确诊",
    "诊断为",
    "治疗方案",
)
BOUNDARY_TERMS = (
    "非临床",
    "不能替代",
    "不替代",
    "仅供参考",
    "专业诊断",
    "专业帮助",
)
OVER_STRONG_TERMS = (
    "一定",
    "必然",
    "完全说明",
    "绝对",
    "决定了",
)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def build_report_critic(report_content: str | None) -> dict[str, Any]:
    if not report_content:
        return {
            "status": "pending",
            "flags": [],
            "notes": ["报告尚未生成，暂无法执行安全边界审查。"],
        }

    flags = []
    notes = []

    if _contains_any(report_content, CLINICAL_TERMS):
        flags.append("clinical_language")
        notes.append("检测到可能越过非临床边界的临床化表述。")

    if not _contains_any(report_content, BOUNDARY_TERMS):
        flags.append("missing_non_clinical_boundary")
        notes.append("报告缺少非临床参考或不能替代专业诊断的边界说明。")

    if _contains_any(report_content, OVER_STRONG_TERMS):
        flags.append("over_strong_language")
        notes.append("检测到过强或绝对化措辞，建议改为概率性描述。")

    if not flags:
        notes.append("未发现明显的临床化、边界缺失或绝对化表述问题。")

    return {
        "status": "warning" if flags else "passed",
        "flags": flags,
        "notes": notes,
    }


def _assessment_trust_level(confidence: float, label: Any = None) -> str:
    label_map = {
        "高": "high",
        "较高": "high",
        "high": "high",
        "中等": "medium",
        "medium": "medium",
        "低": "low",
        "较低": "low",
        "low": "low",
    }
    if isinstance(label, str) and label in label_map:
        return label_map[label]
    if confidence >= 0.8:
        return "high"
    if confidence >= 0.6:
        return "medium"
    if confidence > 0:
        return "low"
    return "unknown"


def _evidence_count(evidence_chain: dict[str, Any]) -> int:
    modules = evidence_chain.get("modules") if isinstance(evidence_chain, dict) else {}
    if not isinstance(modules, dict):
        return 0

    count = 0
    for module_payload in modules.values():
        if not isinstance(module_payload, dict):
            continue
        evidence = module_payload.get("evidence")
        if isinstance(evidence, list):
            count += len(evidence)
    return count


def _evidence_status(evidence_count: int, module_debate_count: int) -> str:
    if evidence_count >= 40 and module_debate_count >= 4:
        return "available"
    if evidence_count > 0 or module_debate_count > 0:
        return "partial"
    return "missing"


def build_agent_state(
    *,
    trust_summary: dict[str, Any],
    adaptive_metrics: dict[str, Any],
    evidence_chain: dict[str, Any],
    module_debates: dict[str, Any],
    report_content: str | None,
) -> dict[str, Any]:
    assessment_confidence = _safe_float(trust_summary.get("assessment_confidence"))
    anomaly_count = _safe_int(trust_summary.get("anomaly_count"))
    adaptive_coverage = _safe_float(adaptive_metrics.get("coverage_ratio"))
    evidence_count = _evidence_count(evidence_chain)
    module_debate_count = len(module_debates) if isinstance(module_debates, dict) else 0
    evidence_status = _evidence_status(evidence_count, module_debate_count)
    critic = build_report_critic(report_content)

    risk_flags = []
    if 0 < assessment_confidence < 0.6:
        risk_flags.append("low_assessment_confidence")
    if anomaly_count >= 3:
        risk_flags.append("multiple_anomalous_answers")
    if 0 < adaptive_coverage < 0.8:
        risk_flags.append("low_adaptive_coverage")
    if module_debate_count < 4:
        risk_flags.append("incomplete_module_debate")
    if evidence_status == "missing":
        risk_flags.append("missing_evidence_chain")
    if critic["status"] == "warning":
        risk_flags.append("critic_warning")

    if not report_content:
        report_policy = "pending"
    elif risk_flags:
        report_policy = "conservative"
    else:
        report_policy = "normal"

    return {
        "workflow": WORKFLOW_NAME,
        "assessment_confidence": assessment_confidence,
        "assessment_trust_level": _assessment_trust_level(assessment_confidence, trust_summary.get("label")),
        "anomaly_count": anomaly_count,
        "adaptive_coverage": adaptive_coverage,
        "evidence_count": evidence_count,
        "evidence_status": evidence_status,
        "module_debate_count": module_debate_count,
        "critic_status": critic["status"],
        "risk_flags": risk_flags,
        "report_policy": report_policy,
    }


def _critic_step_status(critic_status: str | None) -> str:
    if critic_status == "passed":
        return "done"
    if critic_status == "warning":
        return "warning"
    return "pending"


def build_agent_trace(state: dict[str, Any]) -> dict[str, Any]:
    evidence_status = state.get("evidence_status")
    report_policy = state.get("report_policy")
    module_debate_count = _safe_int(state.get("module_debate_count"), 0)

    steps = [
        {"key": "observe_assessment", "status": "done"},
        {
            "key": "build_evidence_state",
            "status": "warning" if evidence_status == "missing" else "done",
        },
        {
            "key": "multi_agent_analysis",
            "status": "warning" if module_debate_count < 4 else "done",
        },
        {
            "key": "policy_selection",
            "status": "pending" if report_policy == "pending" else "done",
        },
        {
            "key": "safety_critic",
            "status": _critic_step_status(state.get("critic_status")),
        },
        {
            "key": "finalize_report",
            "status": "pending" if report_policy == "pending" else "done",
        },
    ]

    return {
        "workflow": WORKFLOW_NAME,
        "mode": "static_workflow",
        "steps": steps,
    }


def build_agent_workflow_payload(
    *,
    trust_summary: dict[str, Any],
    adaptive_metrics: dict[str, Any],
    evidence_chain: dict[str, Any],
    module_debates: dict[str, Any],
    report_content: str | None,
) -> dict[str, Any]:
    state = build_agent_state(
        trust_summary=trust_summary,
        adaptive_metrics=adaptive_metrics,
        evidence_chain=evidence_chain,
        module_debates=module_debates,
        report_content=report_content,
    )
    trace = build_agent_trace(state)
    critic = build_report_critic(report_content)

    return {
        "name": WORKFLOW_NAME,
        "description": "证据约束型静态多 Agent 工作流",
        "state": state,
        "trace": trace,
        "critic": critic,
    }
