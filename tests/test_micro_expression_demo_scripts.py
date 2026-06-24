from __future__ import annotations

import os
import subprocess
import sys
import types

import numpy as np

from multimodal_personality.feature_extractors import mol_single_infer
from scripts.run_micro_expression_demo import format_demo_output
from scripts.prepare_micro_expression_ablation_manifest import build_ablation_manifest


def test_run_micro_expression_demo_prints_summary(tmp_path) -> None:
    script = tmp_path / "fake_demo.py"
    script.write_text(
        "print('微表情提取成功')\nprint('主导微表情为积极，置信度约 70/100。')\n",
        encoding="utf-8",
    )
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )

    assert result.returncode == 0
    assert "微表情提取成功" in result.stdout
    assert "积极" in result.stdout


def test_format_demo_output_contains_path_and_feature_dim(tmp_path) -> None:
    output_path = tmp_path / "micro_expression_feature.json"
    payload = {
        "success": True,
        "summary_text_zh": "主导微表情为积极，置信度约 70/100。",
        "feature_vector": [0.0] * 8,
        "errors": [],
    }

    text = format_demo_output(payload, output_path)

    assert "微表情提取成功" in text
    assert "8 维" in text
    assert str(output_path) in text


def test_mol_video_tensor_repeats_short_frame_sequences(monkeypatch, tmp_path) -> None:
    frame_paths = []
    for index in range(5):
        frame_path = tmp_path / f"frame_{index:03d}.jpg"
        frame_path.write_bytes(b"frame")
        frame_paths.append(frame_path)

    selected_paths = []
    fake_dataset = types.ModuleType("dataset")
    fake_dataset.detector = object()
    fake_dataset.predictor = object()

    def fake_img_pre_dlib(detector, predictor, image_path):
        selected_paths.append(image_path)
        return np.zeros((128, 128, 3), dtype=np.uint8), np.zeros((68, 2), dtype=np.float32)

    fake_dataset.img_pre_dlib = fake_img_pre_dlib
    fake_dataset.crop_img_ldm = lambda gray_img, align_ldm: (
        np.zeros((128, 128, 1), dtype=np.float32),
        align_ldm,
    )
    fake_cv2 = types.ModuleType("cv2")
    fake_cv2.COLOR_BGR2GRAY = 0
    fake_cv2.cvtColor = lambda image, code: np.zeros((128, 128), dtype=np.uint8)
    monkeypatch.setitem(sys.modules, "dataset", fake_dataset)
    monkeypatch.setitem(sys.modules, "cv2", fake_cv2)

    tensor = mol_single_infer._build_video_tensor(frame_paths)

    assert tuple(tensor.shape) == (1, 1, 8, 128, 128)
    assert len(selected_paths) == 8
    assert selected_paths[-1] == str(frame_paths[-1])


def test_build_ablation_manifest_counts_micro_expression_coverage(tmp_path) -> None:
    bundle_dir = tmp_path / "bundles"
    micro_dir = tmp_path / "micro"
    bundle_dir.mkdir()
    micro_dir.mkdir()
    (bundle_dir / "sample-a.json").write_text('{"video_name": "sample-a"}', encoding="utf-8")
    (bundle_dir / "sample-b.json").write_text('{"video_name": "sample-b"}', encoding="utf-8")
    (micro_dir / "sample-a.json").write_text(
        '{"success": true, "feature_vector": [0,0,0,0,0,0,0,1]}',
        encoding="utf-8",
    )

    manifest = build_ablation_manifest(bundle_dir=bundle_dir, micro_expression_dir=micro_dir)

    assert manifest["bundle_count"] == 2
    assert manifest["micro_expression_count"] == 1
    assert manifest["coverage"] == 0.5
    assert manifest["samples"][0]["has_micro_expression"] is True
    assert manifest["samples"][1]["has_micro_expression"] is False
