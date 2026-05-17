from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from multimodal_personality.models.feature_bundle import MICRO_EXPRESSION_DIM
from scripts import run_micro_expression_ablation as runner
from scripts.write_micro_expression_experiment_report import render_report_markdown


def _write_bundle(path: Path) -> None:
    path.write_text("{}", encoding="utf-8")


def test_build_ablation_plan_creates_no_micro_and_with_micro_runs(tmp_path) -> None:
    train_dir = tmp_path / "train"
    val_dir = tmp_path / "val"
    output_dir = tmp_path / "ablation"
    train_dir.mkdir()
    val_dir.mkdir()
    _write_bundle(train_dir / "train-a.json")
    _write_bundle(val_dir / "val-a.json")

    plan = runner.build_ablation_plan(
        train_bundle_dir=train_dir,
        val_bundle_dir=val_dir,
        output_dir=output_dir,
        epochs=3,
        batch_size=2,
        device="cpu",
        hidden_dim=32,
    )

    assert [run.name for run in plan] == ["no_micro", "with_micro"]
    assert plan[0].model_kwargs["use_micro_expression_features"] is False
    assert plan[1].model_kwargs["use_micro_expression_features"] is True
    assert plan[1].model_kwargs["micro_expression_dim"] == MICRO_EXPRESSION_DIM
    assert plan[0].checkpoint_path == output_dir / "no_micro" / "checkpoint.pt"
    assert plan[1].checkpoint_path == output_dir / "with_micro" / "checkpoint.pt"
    assert plan[0].train_bundle_paths == [train_dir / "train-a.json"]
    assert plan[1].val_bundle_paths == [val_dir / "val-a.json"]


def test_run_ablation_writes_summary_after_training_and_eval(monkeypatch, tmp_path) -> None:
    train_dir = tmp_path / "train"
    val_dir = tmp_path / "val"
    output_dir = tmp_path / "ablation"
    train_dir.mkdir()
    val_dir.mkdir()
    _write_bundle(train_dir / "train-a.json")
    _write_bundle(val_dir / "val-a.json")
    calls: list[dict[str, object]] = []

    def fake_train_baseline_model(train_bundle_paths, **kwargs):
        calls.append(
            {
                "name": Path(kwargs["checkpoint_path"]).parent.name,
                "train_bundle_paths": list(train_bundle_paths),
                "val_bundle_paths": list(kwargs["val_bundle_paths"]),
                "epochs": kwargs["epochs"],
                "batch_size": kwargs["batch_size"],
                "device": kwargs["device"],
                "model_kwargs": kwargs["model_kwargs"],
            }
        )
        checkpoint_path = Path(kwargs["checkpoint_path"])
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        checkpoint_path.write_text("checkpoint", encoding="utf-8")
        return SimpleNamespace(
            checkpoint_path=checkpoint_path,
            best_epoch=kwargs["epochs"],
            best_loss=0.25,
            history=[{"epoch": kwargs["epochs"], "train_loss": 0.5}],
        )

    def fake_load_checkpoint_model(checkpoint_path, *, device):
        return SimpleNamespace(model=f"model:{Path(checkpoint_path).parent.name}", device=device)

    def fake_evaluate_bundle_paths(model, val_bundle_paths, **kwargs):
        return SimpleNamespace(
            sample_count=len(val_bundle_paths),
            mean_loss=0.125,
            metrics={"mae": 0.1, "acc": 1.0},
            predictions=[],
        )

    monkeypatch.setattr(runner, "train_baseline_model", fake_train_baseline_model)
    monkeypatch.setattr(runner, "load_checkpoint_model", fake_load_checkpoint_model)
    monkeypatch.setattr(runner, "evaluate_bundle_paths", fake_evaluate_bundle_paths)

    summary = runner.run_ablation(
        train_bundle_dir=train_dir,
        val_bundle_dir=val_dir,
        output_dir=output_dir,
        epochs=2,
        batch_size=4,
        device="cpu",
        hidden_dim=16,
    )

    summary_path = output_dir / "ablation_summary.json"
    assert summary_path.exists()
    written = json.loads(summary_path.read_text(encoding="utf-8"))
    assert written == summary
    assert [run["name"] for run in summary["runs"]] == ["no_micro", "with_micro"]
    assert summary["runs"][0]["uses_micro_expression_features"] is False
    assert summary["runs"][1]["uses_micro_expression_features"] is True
    assert summary["runs"][1]["eval_metrics"] == {"mae": 0.1, "acc": 1.0}
    assert [call["name"] for call in calls] == ["no_micro", "with_micro"]
    assert calls[1]["model_kwargs"]["use_micro_expression_features"] is True


def test_render_report_markdown_includes_batch_and_ablation_results() -> None:
    batch_summary = {
        "sample_count": 6,
        "success_count": 6,
        "failure_count": 0,
        "dominant_counts": {"negative": 4, "positive": 2},
    }
    ablation_summary = {
        "runs": [
            {"name": "no_micro", "best_loss": 0.2, "eval_metrics": {"mae": 0.3, "pcc": 0.4}},
            {"name": "with_micro", "best_loss": 0.18, "eval_metrics": {"mae": 0.28, "pcc": 0.45}},
        ]
    }

    markdown = render_report_markdown(batch_summary=batch_summary, ablation_summary=ablation_summary)

    assert "# MOL 微表情组会实验总结" in markdown
    assert "批量提取" in markdown
    assert "no_micro" in markdown
    assert "with_micro" in markdown
    assert "解释边界" in markdown
