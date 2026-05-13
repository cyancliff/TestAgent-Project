from __future__ import annotations

import json

from scripts.write_micro_expression_sample_table import build_sample_rows, render_sample_table_markdown


def test_build_sample_rows_reads_feature_json_for_display_fields(tmp_path) -> None:
    feature_path = tmp_path / "sample" / "micro_expression_feature.json"
    feature_path.parent.mkdir()
    feature_path.write_text(
        json.dumps(
            {
                "feature_dim": 8,
                "probabilities": {"surprise": 0.1, "positive": 0.2, "negative": 0.7},
                "summary_text_zh": "主导微表情为消极，置信度约 70/100。",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    batch_summary = {
        "rows": [
            {
                "video_name": "006_1_2",
                "class_name": "negative",
                "success": True,
                "dominant_expression": "negative",
                "confidence": 0.7,
                "output_path": str(feature_path),
                "error_count": 0,
            }
        ]
    }

    rows = build_sample_rows(batch_summary)

    assert rows == [
        {
            "video_name": "006_1_2",
            "class_name": "negative",
            "success": True,
            "dominant_expression": "negative",
            "confidence": 0.7,
            "feature_dim": 8,
            "surprise": 0.1,
            "positive": 0.2,
            "negative": 0.7,
            "summary_text_zh": "主导微表情为消极，置信度约 70/100。",
            "output_path": str(feature_path),
        }
    ]


def test_render_sample_table_markdown_includes_meeting_table() -> None:
    markdown = render_sample_table_markdown(
        [
            {
                "video_name": "006_1_2",
                "class_name": "negative",
                "success": True,
                "dominant_expression": "negative",
                "confidence": 0.7,
                "feature_dim": 8,
                "surprise": 0.1,
                "positive": 0.2,
                "negative": 0.7,
                "summary_text_zh": "主导微表情为消极，置信度约 70/100。",
                "output_path": "reports/sample.json",
            }
        ]
    )

    assert "# MOL 微表情样本明细表" in markdown
    assert "| 006_1_2 | negative | negative | true | 0.7000 | 8 |" in markdown
    assert "reports/sample.json" in markdown
