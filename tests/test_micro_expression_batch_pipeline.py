from __future__ import annotations

import json
from types import SimpleNamespace

from scripts.extract_mol_micro_expression_batch import discover_frame_samples, run_batch_extraction


def test_discover_frame_samples_reads_nested_class_directories(tmp_path) -> None:
    root = tmp_path / "SAMM_data_3"
    positive = root / "positive" / "007_6_1"
    negative = root / "negative" / "006_2_1"
    positive.mkdir(parents=True)
    negative.mkdir(parents=True)
    for index in range(8):
        (positive / f"{index + 1}.jpg").write_bytes(b"frame")
        (negative / f"{index + 1}.jpg").write_bytes(b"frame")

    samples = discover_frame_samples(root, limit=None)

    assert [sample["video_name"] for sample in samples] == ["006_2_1", "007_6_1"]
    assert samples[0]["class_name"] == "negative"
    assert samples[1]["class_name"] == "positive"


def test_run_batch_extraction_writes_summary_json_and_csv(tmp_path) -> None:
    frames_dir = tmp_path / "SAMM_data_3" / "positive" / "007_6_1"
    frames_dir.mkdir(parents=True)
    for index in range(8):
        (frames_dir / f"{index + 1}.jpg").write_bytes(b"frame")

    class FakeExtractor:
        def extract_sample(self, *, video_name, video_path, frames_dir, output_dir):
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / "micro_expression_feature.json"
            output_path.write_text(
                json.dumps(
                    {
                        "success": True,
                        "summary": {
                            "dominant_expression": "positive",
                            "dominant_label_zh": "积极",
                            "confidence": 0.7,
                        },
                        "summary_text_zh": "主导微表情为积极，置信度约 70/100。",
                        "feature_vector": [0.1, 0.7, 0.2, 0.7, 0.8, 0.5, 0.4, 1.0],
                        "errors": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            return SimpleNamespace(success=True, output_path=str(output_path), errors=[])

    summary = run_batch_extraction(
        root_dir=tmp_path / "SAMM_data_3",
        output_dir=tmp_path / "micro_batch",
        extractor=FakeExtractor(),
        limit=None,
        resume=False,
    )

    assert summary["sample_count"] == 1
    assert summary["success_count"] == 1
    assert summary["dominant_counts"] == {"positive": 1}
    assert (tmp_path / "micro_batch" / "summary.json").exists()
    assert (tmp_path / "micro_batch" / "summary.csv").exists()
