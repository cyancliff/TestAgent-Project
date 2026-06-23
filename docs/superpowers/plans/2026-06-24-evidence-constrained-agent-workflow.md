# Evidence-Constrained Agent Workflow Enhancement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a low-risk, deployable "evidence-constrained static multi-agent workflow" enhancement that exposes agent state, trace, and safety critique for ATMR reports without changing the database schema or core assessment flow.

**Architecture:** Keep the current assessment, debate, RAG, and report generation paths intact. Add a small pure-Python service that derives `agent_state`, `agent_trace`, and `report_critic` from existing report response data, then return these computed fields from the report API and render a compact "智能分析过程" card in the report page. The enhancement is read-only and computed on demand, so failures can degrade to hidden UI without blocking deployment.

**Tech Stack:** FastAPI, SQLAlchemy ORM, Vue 3 Composition API, pytest, existing ATMR trust/evidence utilities.

---

## Scope And Non-Goals

This plan intentionally does not implement dynamic per-question agents, strong multimodal arbitration, new LLM calls, LangGraph/AutoGen integration, or database migrations. The goal is a practical pre-deployment enhancement that supports the technical narrative: a controlled, evidence-constrained static multi-agent workflow for report generation and safety review.

## File Structure

- Create: `app/services/agent_workflow.py`
  - Pure functions for deriving agent state, trace steps, report critique, and a bundle payload from existing report fields.
  - No database access, no network calls, no LLM calls.

- Modify: `app/api/assessment/streaming.py`
  - Import `build_agent_workflow_payload`.
  - Add `agent_workflow`, `agent_state`, `agent_trace`, and `report_critic` to `/api/v1/assessment/report/{session_id}` response.

- Create: `tests/test_agent_workflow.py`
  - Unit tests for state derivation, trace generation, critic rules, and graceful defaults.

- Modify: `tests/test_assessment_streaming_api.py`
  - Add an API-level test that stubs DB records and verifies the report response includes workflow fields.

- Modify: `frontend/src/components/Report.vue`
  - Add a compact "智能分析过程" card after the trust card and before the final report body.
  - Add computed helpers for workflow payload and status display.
  - Add scoped CSS for the card.

- Create: `tests/test_agent_workflow_frontend.py`
  - Static frontend test to verify the report component renders the workflow card and consumes backend workflow fields.

- Modify: `docs/开发者日志.md`
  - Add a short dated entry explaining the controlled static agent workflow enhancement and deployment boundary.

- Optional Modify: `README.md`
  - Only if there is already a "current status" section being updated during deployment prep. Keep this short and product-facing.

---

### Task 1: Add Pure Agent Workflow Service

**Files:**
- Create: `app/services/agent_workflow.py`
- Test: `tests/test_agent_workflow.py`

- [ ] **Step 1: Write failing unit tests for agent workflow derivation**

Create `tests/test_agent_workflow.py` with these tests:

```python
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
```

- [ ] **Step 2: Run the new tests and verify they fail**

Run:

```powershell
python -m pytest tests/test_agent_workflow.py -q
```

Expected: FAIL because `app.services.agent_workflow` does not exist.

- [ ] **Step 3: Implement `app/services/agent_workflow.py`**

Create `app/services/agent_workflow.py`:

```python
"""Evidence-constrained static agent workflow helpers.

These helpers derive deploy-safe agent state, trace, and report critique payloads
from already available ATMR report data. They intentionally do not call LLMs,
RAG, databases, or external services.
"""

from __future__ import annotations

from typing import Any

WORKFLOW_NAME = "evidence_constrained_static_agent"

CLINICAL_TERMS = [
    "抑郁症",
    "焦虑症",
    "躁郁",
    "双相",
    "人格障碍",
    "精神疾病",
    "确诊",
    "诊断为",
    "治疗方案",
]

BOUNDARY_TERMS = ["非临床", "不能替代", "不替代", "仅供参考", "专业诊断", "专业帮助"]


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _count_evidence_items(evidence_chain: dict[str, Any]) -> int:
    modules = evidence_chain.get("modules", {}) if isinstance(evidence_chain, dict) else {}
    count = 0
    if isinstance(modules, dict):
        for payload in modules.values():
            if isinstance(payload, dict):
                evidence = payload.get("evidence", [])
                if isinstance(evidence, list):
                    count += len(evidence)
    return count


def _classify_trust(confidence: float) -> str:
    if confidence >= 0.8:
        return "high"
    if confidence >= 0.6:
        return "medium"
    if confidence > 0:
        return "low"
    return "unknown"


def _classify_evidence(evidence_count: int, module_debate_count: int) -> str:
    if evidence_count >= 40 and module_debate_count >= 4:
        return "available"
    if evidence_count > 0 or module_debate_count > 0:
        return "partial"
    return "missing"


def build_report_critic(report_content: str | None) -> dict[str, Any]:
    """Run a deterministic safety and boundary critique over the report text."""
    if not report_content:
        return {
            "status": "pending",
            "flags": [],
            "notes": ["报告尚未生成，安全审查将在报告可用后执行。"],
        }

    flags: list[str] = []
    notes: list[str] = []
    content = report_content.strip()

    if any(term in content for term in CLINICAL_TERMS):
        flags.append("clinical_language")
        notes.append("报告中出现疑似临床诊断或治疗表述，需要改为非临床人格倾向解释。")

    if not any(term in content for term in BOUNDARY_TERMS):
        flags.append("missing_non_clinical_boundary")
        notes.append("报告建议补充非临床参考边界，说明不能替代专业诊断。")

    strong_phrases = ["一定", "必然", "完全说明", "绝对", "决定了"]
    if any(phrase in content for phrase in strong_phrases):
        flags.append("over_strong_language")
        notes.append("报告中存在较强确定性措辞，建议结合证据置信度降低表达强度。")

    if not flags:
        notes.append("未发现明显诊断化、过强结论或边界缺失问题。")

    return {
        "status": "warning" if flags else "passed",
        "flags": flags,
        "notes": notes,
    }


def build_agent_state(
    *,
    trust_summary: dict[str, Any] | None,
    adaptive_metrics: dict[str, Any] | None,
    evidence_chain: dict[str, Any] | None,
    module_debates: dict[str, str] | None,
    report_content: str | None,
) -> dict[str, Any]:
    trust_summary = trust_summary or {}
    adaptive_metrics = adaptive_metrics or {}
    evidence_chain = evidence_chain or {}
    module_debates = module_debates or {}

    assessment_confidence = _as_float(trust_summary.get("assessment_confidence"), 0.0)
    trust_level = _classify_trust(assessment_confidence)
    anomaly_count = int(trust_summary.get("anomaly_count") or 0)
    coverage_ratio = _as_float(adaptive_metrics.get("coverage_ratio"), 0.0)
    evidence_count = _count_evidence_items(evidence_chain)
    module_debate_count = len([content for content in module_debates.values() if content])
    evidence_status = _classify_evidence(evidence_count, module_debate_count)
    critic_status = build_report_critic(report_content)["status"]

    risk_flags: list[str] = []
    if 0 < assessment_confidence < 0.6:
        risk_flags.append("low_assessment_confidence")
    if anomaly_count >= 3:
        risk_flags.append("multiple_anomalous_answers")
    if 0 < coverage_ratio < 0.8:
        risk_flags.append("low_adaptive_coverage")
    if module_debate_count < 4:
        risk_flags.append("incomplete_module_debate")
    if evidence_status == "missing":
        risk_flags.append("missing_evidence_chain")
    if critic_status == "warning":
        risk_flags.append("critic_warning")

    if not report_content:
        report_policy = "pending"
    elif risk_flags:
        report_policy = "conservative"
    else:
        report_policy = "normal"

    return {
        "workflow": WORKFLOW_NAME,
        "mode": "static_workflow",
        "assessment_confidence": round(assessment_confidence, 3),
        "assessment_trust_level": trust_level,
        "anomaly_count": anomaly_count,
        "adaptive_coverage": round(coverage_ratio, 3),
        "rag_status": "available" if evidence_count > 0 else "unknown",
        "evidence_count": evidence_count,
        "evidence_status": evidence_status,
        "module_debate_count": module_debate_count,
        "critic_status": critic_status,
        "risk_flags": risk_flags,
        "report_policy": report_policy,
    }


def build_agent_trace(state: dict[str, Any]) -> dict[str, Any]:
    """Build a deterministic trace for the controlled static workflow."""
    report_pending = state.get("report_policy") == "pending"
    evidence_status = state.get("evidence_status", "missing")
    critic_status = state.get("critic_status", "pending")

    steps = [
        {
            "key": "observe_assessment",
            "label": "读取测评结果",
            "status": "done",
            "detail": "已读取 ATMR 作答、维度得分与作答可信度。",
        },
        {
            "key": "build_evidence_state",
            "label": "构建证据状态",
            "status": "done" if evidence_status != "missing" else "warning",
            "detail": f"证据状态：{evidence_status}。",
        },
        {
            "key": "multi_agent_analysis",
            "label": "多角色分析",
            "status": "done" if state.get("module_debate_count", 0) >= 4 else "warning",
            "detail": f"已获得 {state.get('module_debate_count', 0)}/4 个模块分析结果。",
        },
        {
            "key": "policy_selection",
            "label": "选择报告策略",
            "status": "pending" if report_pending else "done",
            "detail": f"当前策略：{state.get('report_policy', 'unknown')}。",
        },
        {
            "key": "safety_critic",
            "label": "安全边界审查",
            "status": "pending" if critic_status == "pending" else ("warning" if critic_status == "warning" else "done"),
            "detail": f"审查状态：{critic_status}。",
        },
        {
            "key": "finalize_report",
            "label": "生成最终报告",
            "status": "pending" if report_pending else "done",
            "detail": "报告可用。" if not report_pending else "报告仍在生成中。",
        },
    ]

    return {
        "workflow": WORKFLOW_NAME,
        "mode": "static_workflow",
        "steps": steps,
    }


def build_agent_workflow_payload(
    *,
    trust_summary: dict[str, Any] | None,
    adaptive_metrics: dict[str, Any] | None,
    evidence_chain: dict[str, Any] | None,
    module_debates: dict[str, str] | None,
    report_content: str | None,
) -> dict[str, Any]:
    critic = build_report_critic(report_content)
    state = build_agent_state(
        trust_summary=trust_summary,
        adaptive_metrics=adaptive_metrics,
        evidence_chain=evidence_chain,
        module_debates=module_debates,
        report_content=report_content,
    )
    # Avoid recomputing mismatch if future critic logic becomes more expensive.
    state["critic_status"] = critic["status"]
    trace = build_agent_trace(state)
    return {
        "name": WORKFLOW_NAME,
        "description": "证据约束型静态多 Agent 工作流",
        "state": state,
        "trace": trace,
        "critic": critic,
    }
```

- [ ] **Step 4: Run unit tests for the service**

Run:

```powershell
python -m pytest tests/test_agent_workflow.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 1**

```powershell
git add app/services/agent_workflow.py tests/test_agent_workflow.py
git commit -m "feat: add evidence constrained agent workflow helpers"
```

---

### Task 2: Add Workflow Payload To Report API

**Files:**
- Modify: `app/api/assessment/streaming.py`
- Test: `tests/test_assessment_streaming_api.py`

- [ ] **Step 1: Write failing API test for workflow fields**

Append this test to `tests/test_assessment_streaming_api.py`:

```python
def test_report_response_includes_agent_workflow(monkeypatch):
    client = TestClient(app)

    fake_session = SimpleNamespace(
        id=12,
        user_id=7,
        status="completed",
        title="部署演示测评",
        started_at=None,
        finished_at=None,
        report_content="本报告仅作为非临床参考，不能替代专业诊断。",
        trust_summary={},
        evidence_summary={},
        adaptive_metrics={},
    )
    fake_record = SimpleNamespace(
        exam_no="A1",
        selected_option="符合",
        score=4,
        time_spent=8.0,
        is_anomaly=0,
        ai_follow_up=None,
        user_explanation=None,
        risk_score=0,
        risk_reasons=[],
        answer_confidence=1.0,
        behavior_metrics={},
    )
    fake_question = SimpleNamespace(
        exam_no="A1",
        content="我能欣赏他人的优点",
        dimension_id="6",
        trait_label="欣赏线索",
        is_reverse=False,
    )
    fake_debate = SimpleNamespace(module="A", result_content="模块 A 分析")

    class FakeQuery:
        def __init__(self, items):
            self.items = items

        def filter(self, *args, **kwargs):
            return self

        def first(self):
            return self.items[0] if self.items else None

        def all(self):
            return self.items

    class FakeDB:
        def query(self, model):
            model_name = getattr(model, "__name__", "")
            if model_name == "AssessmentSession":
                return FakeQuery([fake_session])
            if model_name == "AnswerRecord":
                return FakeQuery([fake_record])
            if model_name == "Question":
                return FakeQuery([fake_question])
            if model_name == "ModuleDebateResult":
                return FakeQuery([fake_debate])
            return FakeQuery([])

        def commit(self):
            return None

    from app.core.database import get_db

    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=7, username="tester")
    app.dependency_overrides[get_db] = lambda: FakeDB()

    try:
        response = client.get("/api/v1/assessment/report/12")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["agent_workflow"]["name"] == "evidence_constrained_static_agent"
    assert payload["agent_state"]["workflow"] == "evidence_constrained_static_agent"
    assert payload["agent_trace"]["steps"][0]["key"] == "observe_assessment"
    assert payload["report_critic"]["status"] == "passed"
```

- [ ] **Step 2: Run API test to verify it fails**

Run:

```powershell
python -m pytest tests/test_assessment_streaming_api.py::test_report_response_includes_agent_workflow -q
```

Expected: FAIL because the report response does not include workflow fields.

- [ ] **Step 3: Import workflow builder in `streaming.py`**

In `app/api/assessment/streaming.py`, add this import near the existing service imports:

```python
from app.services.agent_workflow import build_agent_workflow_payload
```

- [ ] **Step 4: Build workflow payload before returning report response**

In `get_report()`, after `debate_results = {md.module: md.result_content for md in module_debates}`, add:

```python
    agent_workflow = build_agent_workflow_payload(
        trust_summary=trust_summary,
        adaptive_metrics=adaptive_metrics,
        evidence_chain=evidence_chain,
        module_debates=debate_results,
        report_content=session.report_content,
    )
```

Then add these keys to the returned dict:

```python
        "agent_workflow": agent_workflow,
        "agent_state": agent_workflow["state"],
        "agent_trace": agent_workflow["trace"],
        "report_critic": agent_workflow["critic"],
```

The final return tail should include:

```python
        "trust_summary": trust_summary,
        "adaptive_metrics": adaptive_metrics,
        "evidence_chain": evidence_chain,
        "agent_workflow": agent_workflow,
        "agent_state": agent_workflow["state"],
        "agent_trace": agent_workflow["trace"],
        "report_critic": agent_workflow["critic"],
    }
```

- [ ] **Step 5: Run targeted API and workflow tests**

Run:

```powershell
python -m pytest tests/test_agent_workflow.py tests/test_assessment_streaming_api.py::test_report_response_includes_agent_workflow -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 2**

```powershell
git add app/api/assessment/streaming.py tests/test_assessment_streaming_api.py
git commit -m "feat: expose agent workflow trace in report API"
```

---

### Task 3: Render Workflow Card In Report Page

**Files:**
- Modify: `frontend/src/components/Report.vue`
- Test: `tests/test_agent_workflow_frontend.py`

- [ ] **Step 1: Write failing frontend static test**

Create `tests/test_agent_workflow_frontend.py`:

```python
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_COMPONENT = PROJECT_ROOT / "frontend" / "src" / "components" / "Report.vue"


def test_report_renders_agent_workflow_card():
    content = REPORT_COMPONENT.read_text(encoding="utf-8")

    assert "智能分析过程" in content
    assert "agentWorkflow" in content
    assert "agentTraceSteps" in content
    assert "reportCritic" in content
    assert "workflow-step" in content
```

- [ ] **Step 2: Run frontend static test to verify it fails**

Run:

```powershell
python -m pytest tests/test_agent_workflow_frontend.py -q
```

Expected: FAIL because `Report.vue` does not render workflow fields yet.

- [ ] **Step 3: Add workflow card template**

In `frontend/src/components/Report.vue`, insert this block after the existing `trust-card` block and before `<!-- 综合心理画像报告（Markdown 渲染） -->`:

```vue
      <div v-if="agentWorkflow" class="report-card agent-workflow-card">
        <div class="agent-workflow-header">
          <div>
            <h2 class="section-title">智能分析过程</h2>
            <p class="section-desc">证据约束型多 Agent 工作流运行摘要</p>
          </div>
          <span :class="['workflow-policy-badge', `policy-${agentState.report_policy || 'pending'}`]">
            {{ workflowPolicyLabel }}
          </span>
        </div>

        <div class="workflow-state-grid">
          <div class="workflow-state-item">
            <span>测评可信度</span>
            <strong>{{ percent(agentState.assessment_confidence || 0) }}%</strong>
          </div>
          <div class="workflow-state-item">
            <span>证据状态</span>
            <strong>{{ evidenceStatusLabel }}</strong>
          </div>
          <div class="workflow-state-item">
            <span>模块分析</span>
            <strong>{{ agentState.module_debate_count || 0 }}/4</strong>
          </div>
          <div class="workflow-state-item">
            <span>安全审查</span>
            <strong>{{ criticStatusLabel }}</strong>
          </div>
        </div>

        <div class="workflow-steps">
          <div v-for="step in agentTraceSteps" :key="step.key" :class="['workflow-step', `step-${step.status}`]">
            <span class="workflow-step-dot"></span>
            <div>
              <strong>{{ step.label }}</strong>
              <p>{{ step.detail }}</p>
            </div>
          </div>
        </div>

        <div v-if="reportCritic.notes?.length" class="critic-notes">
          <strong>审查提示</strong>
          <p v-for="note in reportCritic.notes" :key="note">{{ note }}</p>
        </div>
      </div>
```

- [ ] **Step 4: Add computed helpers**

In the `<script setup>` section of `Report.vue`, after the existing `adaptiveMetrics` computed, add:

```js
const agentWorkflow = computed(() => reportData.value.agent_workflow || null)
const agentState = computed(() => reportData.value.agent_state || agentWorkflow.value?.state || {})
const agentTrace = computed(() => reportData.value.agent_trace || agentWorkflow.value?.trace || {})
const reportCritic = computed(() => reportData.value.report_critic || agentWorkflow.value?.critic || {})
const agentTraceSteps = computed(() => agentTrace.value.steps || [])

const workflowPolicyLabel = computed(() => {
  const policy = agentState.value.report_policy
  if (policy === 'normal') return '正常策略'
  if (policy === 'conservative') return '保守策略'
  return '生成中'
})

const evidenceStatusLabel = computed(() => {
  const status = agentState.value.evidence_status
  if (status === 'available') return '充分'
  if (status === 'partial') return '部分'
  if (status === 'missing') return '缺失'
  return '未知'
})

const criticStatusLabel = computed(() => {
  const status = reportCritic.value.status || agentState.value.critic_status
  if (status === 'passed') return '通过'
  if (status === 'warning') return '需关注'
  return '待审查'
})
```

- [ ] **Step 5: Add scoped CSS for workflow card**

In the `<style scoped>` section of `Report.vue`, after the trust-card styles, add:

```css
.agent-workflow-card {
  border-left: 4px solid #0f766e;
}
.agent-workflow-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 20px;
  margin-bottom: 20px;
}
.workflow-policy-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 88px;
  padding: 8px 12px;
  border-radius: 999px;
  color: #fff;
  font-size: 14px;
  font-weight: 800;
  white-space: nowrap;
}
.policy-normal { background: #059669; }
.policy-conservative { background: #d97706; }
.policy-pending { background: #64748b; }
.workflow-state-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 20px;
}
.workflow-state-item {
  padding: 14px 16px;
  border-radius: 8px;
  background: var(--bg-hover);
}
.workflow-state-item span {
  display: block;
  margin-bottom: 6px;
  color: var(--text-muted);
  font-size: 13px;
}
.workflow-state-item strong {
  color: var(--text-primary);
  font-size: 20px;
}
.workflow-steps {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}
.workflow-step {
  display: flex;
  gap: 10px;
  padding: 14px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.62);
}
.workflow-step-dot {
  width: 10px;
  height: 10px;
  margin-top: 7px;
  border-radius: 999px;
  background: #059669;
  flex: 0 0 auto;
}
.step-warning .workflow-step-dot { background: #d97706; }
.step-pending .workflow-step-dot { background: #64748b; }
.workflow-step strong {
  display: block;
  margin-bottom: 4px;
  color: var(--text-primary);
}
.workflow-step p {
  margin: 0;
  color: var(--text-secondary);
  font-size: 14px;
  line-height: 1.6;
}
.critic-notes {
  margin-top: 16px;
  padding: 14px 16px;
  border-radius: 8px;
  background: rgba(15, 118, 110, 0.08);
  color: var(--text-secondary);
}
.critic-notes strong {
  display: block;
  margin-bottom: 6px;
  color: var(--text-primary);
}
.critic-notes p {
  margin: 0 0 6px;
  line-height: 1.6;
}
```

In the `@media (max-width: 768px)` block, add:

```css
  .agent-workflow-header { flex-direction: column; }
  .workflow-state-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .workflow-steps { grid-template-columns: 1fr; }
```

In the `@media (max-width: 480px)` block, add:

```css
  .workflow-state-grid { grid-template-columns: 1fr; }
```

- [ ] **Step 6: Run frontend static test**

Run:

```powershell
python -m pytest tests/test_agent_workflow_frontend.py -q
```

Expected: PASS.

- [ ] **Step 7: Run frontend build**

Run:

```powershell
Set-Location frontend
npm run build
```

Expected: Vite build succeeds.

- [ ] **Step 8: Commit Task 3**

```powershell
git add frontend/src/components/Report.vue tests/test_agent_workflow_frontend.py
git commit -m "feat: show agent workflow trace on report page"
```

---

### Task 4: Add Deployment-Safe Documentation

**Files:**
- Modify: `docs/开发者日志.md`
- Optional Modify: `README.md`

- [ ] **Step 1: Open current developer log context**

Run:

```powershell
Get-Content -LiteralPath 'docs/开发者日志.md' -Encoding UTF8 -TotalCount 80
```

Expected: file opens and shows recent status entries.

- [ ] **Step 2: Add a dated developer log entry**

Add this entry near the top of `docs/开发者日志.md`, preserving the existing style:

```markdown
## 2026-06-24：证据约束型静态多 Agent 工作流增强

- 在不改变测评主流程和数据库结构的前提下，为 ATMR 报告接口补充 `agent_state`、`agent_trace` 和 `report_critic` 派生字段。
- 当前定位为“证据约束型静态多 Agent 工作流”：测评过程继续使用确定性快速路径，Agent 只在报告生成、证据状态说明和安全边界审查等低频高价值环节体现。
- 报告页新增“智能分析过程”展示区块，用于说明测评结果读取、证据状态构建、多角色分析、策略选择、安全审查和最终报告生成状态。
- 本增强不引入新的 LLM 调用、外部服务、数据库迁移或动态逐题 Agent，便于部署到合作公司网站时保持稳定性。
```

- [ ] **Step 3: Optionally add one README status bullet**

Only if the README is being updated during deployment prep, add one concise bullet under current status:

```markdown
- 报告页新增证据约束型静态多 Agent 工作流摘要，展示证据状态、分析过程与安全边界审查结果；该能力不改变测评作答流程，主要用于提升报告可解释性和部署演示效果。
```

If README currently has encoding or display issues in the editor, skip this optional README change and keep the update only in `docs/开发者日志.md`.

- [ ] **Step 4: Commit Task 4**

```powershell
git add docs/开发者日志.md README.md
git commit -m "docs: document agent workflow deployment enhancement"
```

If README was not modified, use:

```powershell
git add docs/开发者日志.md
git commit -m "docs: document agent workflow deployment enhancement"
```

---

### Task 5: Final Verification For Deployment Safety

**Files:**
- No code changes expected.

- [ ] **Step 1: Run targeted backend tests**

Run:

```powershell
python -m pytest tests/test_agent_workflow.py tests/test_assessment_streaming_api.py tests/test_assessment_trust.py -q
```

Expected: PASS.

- [ ] **Step 2: Run targeted frontend/static tests**

Run:

```powershell
python -m pytest tests/test_agent_workflow_frontend.py tests/test_history_frontend.py tests/test_big_five_report_frontend.py -q
```

Expected: PASS.

- [ ] **Step 3: Run full Python regression if time allows**

Run:

```powershell
python -m pytest -q
```

Expected: PASS. If slow multimodal tests are not practical before deployment, record which targeted tests passed and why full regression was skipped.

- [ ] **Step 4: Build frontend**

Run:

```powershell
Set-Location frontend
npm run build
```

Expected: build succeeds and `frontend/dist/` is generated locally.

- [ ] **Step 5: Smoke check backend report payload manually**

Start backend in a local terminal if needed:

```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Using an authenticated browser session, open an existing completed report and verify the network response for:

```text
GET /api/v1/assessment/report/<session_id>
```

Expected response contains:

```json
{
  "agent_workflow": {"name": "evidence_constrained_static_agent"},
  "agent_state": {"workflow": "evidence_constrained_static_agent"},
  "agent_trace": {"steps": []},
  "report_critic": {"status": "passed"}
}
```

The exact `report_critic.status` may be `warning` if the report lacks a non-clinical boundary statement; that is acceptable and should render as a visible review note.

- [ ] **Step 6: Smoke check frontend report page**

Start frontend if needed:

```powershell
Set-Location frontend
npm run dev
```

Open the report page and verify:

- The existing radar chart, trust card, report body, dimension reports, and answer details still render.
- A new "智能分析过程" card appears after "测评可信度".
- The card does not block or replace the report body.
- Mobile width does not overlap text or controls.

- [ ] **Step 7: Commit any verification-only doc update if needed**

If verification findings are added to `docs/开发者日志.md`, commit them:

```powershell
git add docs/开发者日志.md
git commit -m "docs: record agent workflow verification"
```

---

## Rollback Plan

If the enhancement causes deployment trouble:

1. Hide the frontend card by removing or commenting the `v-if="agentWorkflow"` block in `frontend/src/components/Report.vue`.
2. Keep backend response fields if harmless; clients ignore unknown JSON keys.
3. If backend code causes errors, remove the `build_agent_workflow_payload` import and the four returned workflow fields from `app/api/assessment/streaming.py`.
4. No database rollback is needed because this plan adds no migration and persists no new fields.

## Deployment Narrative

Use this wording for company/demo context:

> 系统采用证据约束型静态多 Agent 工作流。测评作答阶段保持确定性快速路径，报告阶段基于作答可信度、证据状态、多角色分析结果和安全边界审查生成可追踪报告。该设计避免逐题动态 Agent 带来的延迟和不稳定，同时提升报告生成过程的可解释性与可审查性。

## Self-Review

- Spec coverage: This plan covers backend workflow derivation, API exposure, frontend display, tests, docs, and deployment rollback.
- Placeholder scan: No `TBD`, `TODO`, or unspecified implementation steps remain.
- Type consistency: `agent_workflow`, `agent_state`, `agent_trace`, and `report_critic` names are consistent across service, API, frontend, and tests.
- Scope check: The plan is intentionally limited to a deploy-safe static workflow enhancement and does not require schema changes, new frameworks, or new LLM calls.
