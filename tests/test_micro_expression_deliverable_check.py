from __future__ import annotations

import json

from scripts.check_micro_expression_deliverables import check_deliverables, render_markdown_report


def test_check_deliverables_reports_ready_when_required_artifacts_exist(tmp_path) -> None:
    batch_summary = tmp_path / "batch" / "summary.json"
    batch_summary.parent.mkdir()
    batch_summary.write_text(
        json.dumps(
            {
                "sample_count": 6,
                "success_count": 6,
                "failure_count": 0,
                "dominant_counts": {"negative": 6},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    ablation_summary = tmp_path / "ablation" / "ablation_summary.json"
    ablation_summary.parent.mkdir()
    ablation_summary.write_text(
        json.dumps(
            {
                "runs": [
                    {"name": "no_micro", "eval_metrics": {"mae": 0.1}},
                    {"name": "with_micro", "eval_metrics": {"mae": 0.2}},
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    report_path = tmp_path / "report.md"
    report_path.write_text("# MOL 微表情组会实验总结\n", encoding="utf-8")
    docs = [tmp_path / "交付包.md", tmp_path / "命令清单.md"]
    for doc in docs:
        doc.write_text("# MOL 微表情\n", encoding="utf-8")

    result = check_deliverables(
        batch_summary_path=batch_summary,
        ablation_summary_path=ablation_summary,
        report_path=report_path,
        doc_paths=docs,
    )

    assert result["ready"] is True
    assert result["batch"]["success_count"] == 6
    assert [run["name"] for run in result["ablation"]["runs"]] == ["no_micro", "with_micro"]
    assert result["missing_paths"] == []


def test_render_markdown_report_includes_status_and_paths() -> None:
    markdown = render_markdown_report(
        {
            "ready": True,
            "checked_paths": ["reports/a.json"],
            "missing_paths": [],
            "batch": {"sample_count": 6, "success_count": 6, "failure_count": 0},
            "ablation": {"runs": [{"name": "no_micro"}, {"name": "with_micro"}]},
        }
    )

    assert "# MOL 微表情交付包自检报告" in markdown
    assert "状态：通过" in markdown
    assert "no_micro" in markdown
    assert "with_micro" in markdown
