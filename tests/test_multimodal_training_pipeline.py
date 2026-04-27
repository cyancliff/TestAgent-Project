from __future__ import annotations

import json

import torch

from multimodal_personality.models import MultimodalFeatureBundle
from multimodal_personality.training import (
    TRAIT_ORDER,
    compute_regression_metrics,
    discover_bundle_paths,
    evaluate_bundle_paths,
    load_checkpoint_model,
    predict_bundle_paths,
    train_baseline_model,
)


def _write_bundle(path, *, video_name: str, label_seed: float) -> None:
    labels = [min(label_seed + index * 0.05, 0.95) for index in range(5)]
    bundle = MultimodalFeatureBundle(
        video_name=video_name,
        video_path=video_name,
        labels=labels,
        clip_video=[[label_seed + frame_index * 0.001] * 768 for frame_index in range(15)],
        clip_text=[[label_seed + sentence_index * 0.01] * 768 for sentence_index in range(4)],
        wav2clip=[[label_seed + frame_index * 0.002] * 512 for frame_index in range(15)],
        bg_features=[label_seed] * 256,
    )
    bundle.write_json(path)


def _write_manifest(path, names: list[str]) -> None:
    payload = {
        "dataset_name": "synthetic",
        "phase": "train",
        "sample_count": len(names),
        "missing_videos": 0,
        "missing_transcripts": 0,
        "samples": [
            {
                "video_name": name,
                "video_path": name,
                "transcript": "",
                "labels": {},
                "has_video": True,
                "has_transcript": False,
            }
            for name in names
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_discover_bundle_paths_uses_manifest_filter(tmp_path) -> None:
    bundle_dir = tmp_path / "bundles"
    bundle_dir.mkdir()
    _write_bundle(bundle_dir / "sample-a.json", video_name="sample-a", label_seed=0.1)
    _write_bundle(bundle_dir / "sample-b.json", video_name="sample-b", label_seed=0.2)

    manifest_path = tmp_path / "manifest.json"
    _write_manifest(manifest_path, ["sample-a", "sample-missing", "sample-b"])

    resolved = discover_bundle_paths(bundle_dir, manifest_path=manifest_path)

    assert [path.name for path in resolved.bundle_paths] == ["sample-a.json", "sample-b.json"]
    assert resolved.missing_bundle_names == ["sample-missing"]


def test_compute_regression_metrics_includes_paper_metrics() -> None:
    targets = torch.tensor(
        [
            [0.1, 0.2, 0.3, 0.4, 0.5],
            [0.2, 0.3, 0.4, 0.5, 0.6],
            [0.3, 0.4, 0.5, 0.6, 0.7],
        ],
        dtype=torch.float32,
    )
    predictions = targets.clone()

    metrics = compute_regression_metrics(predictions, targets)

    assert metrics["mse"] == 0.0
    assert metrics["mae"] == 0.0
    assert metrics["acc"] == 1.0
    assert metrics["pcc"] > 0.999
    assert metrics["ccc"] > 0.999
    assert metrics["r2"] > 0.999
    assert set(metrics["per_trait"]) == set(TRAIT_ORDER)


def test_train_eval_and_infer_minimal_loop(tmp_path) -> None:
    train_dir = tmp_path / "train_bundles"
    val_dir = tmp_path / "val_bundles"
    train_dir.mkdir()
    val_dir.mkdir()

    for index in range(4):
        _write_bundle(train_dir / f"train-{index}.json", video_name=f"train-{index}", label_seed=0.1 + index * 0.05)
    for index in range(2):
        _write_bundle(val_dir / f"val-{index}.json", video_name=f"val-{index}", label_seed=0.35 + index * 0.05)

    checkpoint_path = tmp_path / "baseline.pt"
    result = train_baseline_model(
        sorted(train_dir.glob("*.json")),
        checkpoint_path=checkpoint_path,
        val_bundle_paths=sorted(val_dir.glob("*.json")),
        epochs=1,
        batch_size=2,
        learning_rate=1e-3,
        device="cpu",
        text_seq_len=13,
        model_kwargs={"hidden_dim": 32, "attention_heads": 1, "dropout": 0.1},
    )

    assert result.checkpoint_path.exists()
    assert result.best_epoch == 1
    assert len(result.history) == 1

    loaded = load_checkpoint_model(checkpoint_path, device="cpu")
    assert loaded.checkpoint["model_name"] == "AGTNMTLModel"
    assert loaded.checkpoint["trait_order"] == list(TRAIT_ORDER)

    eval_result = evaluate_bundle_paths(
        loaded.model,
        sorted(val_dir.glob("*.json")),
        device="cpu",
        batch_size=2,
        text_seq_len=13,
        require_labels=True,
    )
    assert eval_result.sample_count == 2
    assert eval_result.mean_loss is not None
    assert set(eval_result.metrics["per_trait"]) == set(TRAIT_ORDER)
    assert {"acc", "pcc", "ccc", "r2"}.issubset(eval_result.metrics)

    infer_result = predict_bundle_paths(checkpoint_path, sorted(val_dir.glob("*.json")), device="cpu", batch_size=2)
    assert infer_result.sample_count == 2
    assert len(infer_result.predictions) == 2
    assert infer_result.predictions[0].labels is not None
    assert set(infer_result.predictions[0].scores) == set(TRAIT_ORDER)
