from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
HISTORY_COMPONENT = PROJECT_ROOT / "frontend" / "src" / "components" / "History.vue"


def test_completed_atmr_history_card_has_direct_report_button():
    content = HISTORY_COMPONENT.read_text(encoding="utf-8")

    completed_section_start = content.index('<section v-if="completedSessions.length"')
    big_five_section_start = content.index('<section v-else class="session-section"', completed_section_start)
    completed_section = content[completed_section_start:big_five_section_start]

    assert 'v-if="session.has_report"' in completed_section
    assert '@click="viewReport(session.session_id)"' in completed_section
    assert ">查看报告</button>" in completed_section
