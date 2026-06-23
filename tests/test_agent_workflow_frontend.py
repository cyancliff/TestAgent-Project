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
