from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_COMPONENT = PROJECT_ROOT / "frontend" / "src" / "components" / "Report.vue"
ASSESSMENT_COMPONENT = PROJECT_ROOT / "frontend" / "src" / "components" / "Assessment.vue"


def test_report_renders_agent_workflow_card():
    content = REPORT_COMPONENT.read_text(encoding="utf-8")

    assert "智能分析过程" in content
    assert "agentWorkflow" in content
    assert "agentTraceSteps" in content
    assert "reportCritic" in content
    assert "workflow-step" in content


def test_assessment_skips_draft_save_before_session_exists():
    content = ASSESSMENT_COMPONENT.read_text(encoding="utf-8")

    assert "if (sessionId.value) {\n      api.post('/assessment/save-answer'" in content
