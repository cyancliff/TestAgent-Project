from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BIG_FIVE_REPORT_COMPONENT = PROJECT_ROOT / "frontend" / "src" / "components" / "BigFiveReport.vue"
HISTORY_COMPONENT = PROJECT_ROOT / "frontend" / "src" / "components" / "History.vue"


def test_big_five_report_does_not_render_processing_records():
    content = BIG_FIVE_REPORT_COMPONENT.read_text(encoding="utf-8")

    assert 'v-if="report.errors?.length"' not in content
    assert "v-for=\"error in report.errors\"" not in content
    assert ".error-list" not in content


def test_big_five_report_does_not_render_atmr_consistency():
    content = BIG_FIVE_REPORT_COMPONENT.read_text(encoding="utf-8")

    assert "ATMR 一致性" not in content
    assert "ATMR 辅助证据链" not in content
    assert "consistencySummary" not in content
    assert "consistencyItems" not in content
    assert ".consistency-" not in content


def test_big_five_report_hides_fallback_scores_from_main_sections():
    content = BIG_FIVE_REPORT_COMPONENT.read_text(encoding="utf-8")

    assert "const hasUsableScores = computed" in content
    assert "report.value.is_real_result" in content
    assert 'v-if="hasUsableScores" class="report-card radar-section"' in content
    assert 'v-if="hasUsableScores" class="report-card evidence-card"' in content
    assert "const canUseInChat = computed(() => hasUsableScores.value)" in content
    assert "CLIP" in content


def test_history_hides_fallback_big_five_scores():
    content = HISTORY_COMPONENT.read_text(encoding="utf-8")

    assert "const isBigFiveReady = (report) => report.status === 'completed' && report.is_real_result && report.scores" in content
    assert "if (!isBigFiveReady(report)) return '--'" in content
