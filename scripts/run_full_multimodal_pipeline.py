"""Run the full multimodal baseline pipeline with resume support."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.multimodal_personality_service import service
from multimodal_personality.feature_extractors.bg_extractor import BackgroundFeatureExtractor
from multimodal_personality.feature_extractors.clip_extractor import ClipFeatureExtractor
from multimodal_personality.feature_extractors.wav2clip_extractor import Wav2ClipFeatureExtractor
from multimodal_personality.models.feature_bundle import MultimodalFeatureBundle
from multimodal_personality.preprocessing.cfi_v2_dataset import filter_manifest_samples, load_manifest
from multimodal_personality.training import (
    discover_bundle_paths,
    evaluate_bundle_paths,
    load_checkpoint_model,
    train_baseline_model,
)

LOGGER = logging.getLogger("full_multimodal_pipeline")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the full multimodal baseline pipeline with resume support")
    parser.add_argument(
        "--output-root",
        default="reports/full_multimodal_pipeline",
        help="Directory for jobs, features, bundles, checkpoints, and reports",
    )
    parser.add_argument(
        "--artifact-root",
        default="uploads/multimodal_personality/artifacts",
        help="Directory containing preprocessing artifacts",
    )
    parser.add_argument(
        "--train-manifest",
        default="multimodal_personality/data/cfi_v2/manifests/train_manifest.json",
        help="Train manifest path",
    )
    parser.add_argument(
        "--val-manifest",
        default="multimodal_personality/data/cfi_v2/manifests/val_manifest.json",
        help="Validation manifest path",
    )
    parser.add_argument(
        "--test-manifest",
        default="multimodal_personality/data/cfi_v2/manifests/test_manifest.json",
        help="Test manifest path",
    )
    parser.add_argument("--train-limit", type=int, default=None, help="Optional train sample limit")
    parser.add_argument("--val-limit", type=int, default=None, help="Optional validation sample limit")
    parser.add_argument("--test-limit", type=int, default=None, help="Optional test sample limit")
    parser.add_argument("--clip-device", default="cuda", help="Device for CLIP extraction")
    parser.add_argument("--train-device", default="cuda", help="Device for model training/evaluation")
    parser.add_argument("--max-sentences", type=int, default=13, help="Sentence cap for CLIP transcript features")
    parser.add_argument("--epochs", type=int, default=5, help="Training epochs")
    parser.add_argument("--batch-size", type=int, default=8, help="Training/evaluation batch size")
    parser.add_argument("--learning-rate", type=float, default=1e-3, help="Optimizer learning rate")
    parser.add_argument("--weight-decay", type=float, default=0.0, help="Optimizer weight decay")
    parser.add_argument("--hidden-dim", type=int, default=128, help="Fusion hidden dimension")
    parser.add_argument("--attention-heads", type=int, default=1, help="Residual attention heads")
    parser.add_argument("--graph-metric", default="ones", help="Graph metric for AGTN layers")
    parser.add_argument("--dropout", type=float, default=0.2, help="Dropout rate")
    return parser.parse_args()


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_json(path: str | Path, payload: dict[str, Any]) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def resolve_samples(manifest_path: str | Path, limit: int | None) -> list[dict[str, Any]]:
    manifest = load_manifest(manifest_path)
    return filter_manifest_samples(
        manifest,
        require_video=True,
        require_transcript=False,
        limit=limit,
    )


def build_artifact_index(artifact_root: str | Path) -> dict[str, Path]:
    artifact_map: dict[str, Path] = {}
    root = Path(artifact_root)
    if not root.exists():
        return artifact_map

    for manifest_path in root.glob("*/manifest.json"):
        try:
            payload = load_json(manifest_path)
        except Exception:
            continue
        video_path = payload.get("video_path", "")
        if not video_path:
            continue
        artifact_map[Path(video_path).name] = manifest_path.parent
    return artifact_map


def preprocess_missing_samples(
    *,
    split_name: str,
    manifest_path: str | Path,
    limit: int | None,
    artifact_root: str | Path,
) -> None:
    samples = resolve_samples(manifest_path, limit)
    artifact_map = build_artifact_index(artifact_root)
    pending = [sample for sample in samples if sample["video_name"] not in artifact_map]

    LOGGER.info(
        "[%s] preprocess target=%s existing=%s pending=%s",
        split_name,
        len(samples),
        len(samples) - len(pending),
        len(pending),
    )
    for index, sample in enumerate(pending, start=1):
        task = service.create_task(video_path=sample["video_path"])
        task = service.run_task(task.task_id, force_restart=True)
        LOGGER.info(
            "[%s preprocess %s/%s] %s status=%s errors=%s artifact_dir=%s",
            split_name,
            index,
            len(pending),
            sample["video_name"],
            task.status,
            len(task.errors),
            task.artifacts.get("artifact_dir", ""),
        )
        if task.status != "completed":
            raise RuntimeError(f"preprocessing failed for {sample['video_name']}: {task.errors}")


def build_jobs(
    *,
    split_name: str,
    manifest_path: str | Path,
    limit: int | None,
    artifact_root: str | Path,
    output_path: str | Path,
) -> Path:
    samples = resolve_samples(manifest_path, limit)
    artifact_map = build_artifact_index(artifact_root)
    jobs: list[dict[str, Any]] = []
    for sample in samples:
        artifact_dir = artifact_map.get(sample["video_name"])
        frame_dir = ""
        audio_path = ""
        artifact_manifest_path = ""
        if artifact_dir is not None:
            frame_dir = str(artifact_dir / "frames")
            audio_candidate = artifact_dir / "audio.wav"
            if audio_candidate.exists():
                audio_path = str(audio_candidate)
            artifact_manifest_path = str(artifact_dir / "manifest.json")

        jobs.append(
            {
                "video_name": sample["video_name"],
                "video_path": sample["video_path"],
                "transcript": sample.get("transcript", ""),
                "artifact_dir": "" if artifact_dir is None else str(artifact_dir),
                "artifact_manifest_path": artifact_manifest_path,
                "frames_dir": frame_dir,
                "audio_path": audio_path,
                "ready_for_clip": bool(frame_dir),
                "ready_for_wav2clip": bool(audio_path),
            }
        )

    payload = {
        "manifest": str(manifest_path),
        "split": split_name,
        "sample_count": len(jobs),
        "jobs": jobs,
    }
    output_file = write_json(output_path, payload)
    LOGGER.info("[%s] jobs written to %s count=%s", split_name, output_file, len(jobs))
    return output_file


def output_success(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        payload = load_json(path)
    except Exception:
        return False
    return bool(payload.get("success", False))


def extract_clip_features(
    *,
    split_name: str,
    jobs_path: str | Path,
    output_dir: str | Path,
    device: str,
    max_sentences: int,
) -> None:
    jobs_payload = load_json(jobs_path)
    jobs = jobs_payload["jobs"]
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    pending = [
        job
        for job in jobs
        if job.get("ready_for_clip")
        and not output_success(output_root / f"{job['video_name']}.json")
    ]
    LOGGER.info("[%s] clip pending=%s total=%s device=%s", split_name, len(pending), len(jobs), device)
    if not pending:
        return

    extractor = ClipFeatureExtractor(device=device, max_sentences=max_sentences)
    for index, job in enumerate(pending, start=1):
        result = extractor.extract_sample(
            sample=job,
            frames_dir=job["frames_dir"],
            output_dir=output_root,
        )
        LOGGER.info(
            "[%s clip %s/%s] %s success=%s errors=%s",
            split_name,
            index,
            len(pending),
            job["video_name"],
            result.success,
            len(result.errors),
        )
        if not result.success:
            raise RuntimeError(f"clip extraction failed for {job['video_name']}: {result.errors}")


def extract_wav2clip_features(
    *,
    split_name: str,
    jobs_path: str | Path,
    output_dir: str | Path,
) -> None:
    jobs_payload = load_json(jobs_path)
    jobs = jobs_payload["jobs"]
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    pending = [
        job
        for job in jobs
        if job.get("ready_for_wav2clip")
        and not output_success(output_root / f"{job['video_name']}.json")
    ]
    LOGGER.info("[%s] wav2clip pending=%s total=%s", split_name, len(pending), len(jobs))
    if not pending:
        return

    extractor = Wav2ClipFeatureExtractor(segment_count=15, feature_dim=512)
    for index, job in enumerate(pending, start=1):
        result = extractor.extract_sample(
            video_name=job["video_name"],
            audio_path=job["audio_path"],
            output_dir=output_root,
        )
        LOGGER.info(
            "[%s wav2clip %s/%s] %s success=%s errors=%s",
            split_name,
            index,
            len(pending),
            job["video_name"],
            result.success,
            len(result.errors),
        )
        if not result.success:
            raise RuntimeError(f"wav2clip extraction failed for {job['video_name']}: {result.errors}")


def extract_bg_features(
    *,
    split_name: str,
    jobs_path: str | Path,
    clip_dir: str | Path,
    wav2clip_dir: str | Path,
    output_dir: str | Path,
) -> None:
    jobs_payload = load_json(jobs_path)
    jobs = jobs_payload["jobs"]
    clip_root = Path(clip_dir)
    wav_root = Path(wav2clip_dir)
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    pending = [
        job
        for job in jobs
        if output_success(clip_root / f"{job['video_name']}.json")
        and not output_success(output_root / f"{job['video_name']}.json")
    ]
    LOGGER.info("[%s] bg pending=%s total=%s", split_name, len(pending), len(jobs))
    if not pending:
        return

    extractor = BackgroundFeatureExtractor()
    for index, job in enumerate(pending, start=1):
        clip_payload = load_json(clip_root / f"{job['video_name']}.json")
        wav_payload = None
        wav_path = wav_root / f"{job['video_name']}.json"
        if wav_path.exists():
            wav_payload = load_json(wav_path)

        result = extractor.extract_sample(
            video_name=job["video_name"],
            clip_payload=clip_payload,
            wav2clip_payload=wav_payload,
            transcript=str(job.get("transcript", "")),
            output_dir=output_root,
        )
        LOGGER.info(
            "[%s bg %s/%s] %s success=%s errors=%s",
            split_name,
            index,
            len(pending),
            job["video_name"],
            result.success,
            len(result.errors),
        )
        if not result.success:
            raise RuntimeError(f"bg feature extraction failed for {job['video_name']}: {result.errors}")


def build_bundles(
    *,
    split_name: str,
    manifest_path: str | Path,
    limit: int | None,
    clip_dir: str | Path,
    wav2clip_dir: str | Path,
    bg_dir: str | Path,
    output_dir: str | Path,
) -> None:
    samples = resolve_samples(manifest_path, limit)
    clip_root = Path(clip_dir)
    wav_root = Path(wav2clip_dir)
    bg_root = Path(bg_dir)
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    pending = [sample for sample in samples if not (output_root / f"{sample['video_name']}.json").exists()]
    LOGGER.info("[%s] bundles pending=%s total=%s", split_name, len(pending), len(samples))

    for index, sample in enumerate(pending, start=1):
        clip_path = clip_root / f"{sample['video_name']}.json"
        if not clip_path.exists():
            raise FileNotFoundError(f"clip feature file missing for {sample['video_name']}: {clip_path}")

        clip_payload = load_json(clip_path)
        wav_payload = None
        wav_path = wav_root / f"{sample['video_name']}.json"
        if wav_path.exists():
            wav_payload = load_json(wav_path)

        bg_payload = None
        bg_path = bg_root / f"{sample['video_name']}.json"
        if bg_path.exists():
            bg_payload = load_json(bg_path)

        bundle = MultimodalFeatureBundle.from_current_artifacts(
            sample=sample,
            clip_payload=clip_payload,
            wav2clip_payload=wav_payload,
            bg_payload=bg_payload,
        )
        bundle_path = output_root / f"{sample['video_name']}.json"
        bundle.write_json(bundle_path)
        LOGGER.info("[%s bundle %s/%s] %s", split_name, index, len(pending), sample["video_name"])


def train_and_evaluate(
    *,
    output_root: str | Path,
    train_bundle_dir: str | Path,
    val_bundle_dir: str | Path,
    test_bundle_dir: str | Path,
    train_limit: int | None,
    val_limit: int | None,
    test_limit: int | None,
    device: str,
    epochs: int,
    batch_size: int,
    learning_rate: float,
    weight_decay: float,
    hidden_dim: int,
    attention_heads: int,
    graph_metric: str,
    dropout: float,
) -> None:
    output_root = Path(output_root)
    checkpoint_path = output_root / "agtn_mtl_full.pt"
    summary_path = output_root / "train_summary.json"
    val_eval_path = output_root / "val_eval.json"
    test_eval_path = output_root / "test_eval.json"

    train_resolution = discover_bundle_paths(train_bundle_dir, limit=train_limit)
    val_resolution = discover_bundle_paths(val_bundle_dir, limit=val_limit)
    test_resolution = discover_bundle_paths(test_bundle_dir, limit=test_limit)

    LOGGER.info(
        "[train] train=%s val=%s test=%s device=%s",
        len(train_resolution.bundle_paths),
        len(val_resolution.bundle_paths),
        len(test_resolution.bundle_paths),
        device,
    )
    train_result = train_baseline_model(
        train_resolution.bundle_paths,
        checkpoint_path=checkpoint_path,
        val_bundle_paths=val_resolution.bundle_paths,
        epochs=epochs,
        batch_size=batch_size,
        learning_rate=learning_rate,
        weight_decay=weight_decay,
        device=device,
        text_seq_len=13,
        model_kwargs={
            "hidden_dim": hidden_dim,
            "attention_heads": attention_heads,
            "graph_metric": graph_metric,
            "dropout": dropout,
        },
    )
    summary_payload = {
        "checkpoint_path": str(train_result.checkpoint_path),
        "best_epoch": train_result.best_epoch,
        "best_loss": train_result.best_loss,
        "history": train_result.history,
        "train_bundle_count": len(train_resolution.bundle_paths),
        "val_bundle_count": len(val_resolution.bundle_paths),
        "test_bundle_count": len(test_resolution.bundle_paths),
    }
    write_json(summary_path, summary_payload)
    LOGGER.info(
        "[train] complete checkpoint=%s best_epoch=%s best_loss=%.6f",
        train_result.checkpoint_path,
        train_result.best_epoch,
        train_result.best_loss,
    )

    loaded = load_checkpoint_model(train_result.checkpoint_path, device=device)
    text_seq_len = int(loaded.checkpoint.get("model_kwargs", {}).get("text_seq_len", 13))

    val_result = evaluate_bundle_paths(
        loaded.model,
        val_resolution.bundle_paths,
        device=loaded.device,
        batch_size=batch_size,
        text_seq_len=text_seq_len,
        fill_missing_modalities=True,
        require_labels=True,
    )
    write_json(
        val_eval_path,
        {
            "split": "val",
            "checkpoint_path": str(train_result.checkpoint_path),
            "sample_count": val_result.sample_count,
            "mean_loss": val_result.mean_loss,
            "metrics": val_result.metrics,
        },
    )
    LOGGER.info(
        "[val] mse=%.6f mae=%.6f pcc=%.6f ccc=%.6f r2=%.6f",
        val_result.metrics["mse"],
        val_result.metrics["mae"],
        val_result.metrics["pcc"],
        val_result.metrics["ccc"],
        val_result.metrics["r2"],
    )

    test_result = evaluate_bundle_paths(
        loaded.model,
        test_resolution.bundle_paths,
        device=loaded.device,
        batch_size=batch_size,
        text_seq_len=text_seq_len,
        fill_missing_modalities=True,
        require_labels=True,
    )
    write_json(
        test_eval_path,
        {
            "split": "test",
            "checkpoint_path": str(train_result.checkpoint_path),
            "sample_count": test_result.sample_count,
            "mean_loss": test_result.mean_loss,
            "metrics": test_result.metrics,
        },
    )
    LOGGER.info(
        "[test] mse=%.6f mae=%.6f pcc=%.6f ccc=%.6f r2=%.6f",
        test_result.metrics["mse"],
        test_result.metrics["mae"],
        test_result.metrics["pcc"],
        test_result.metrics["ccc"],
        test_result.metrics["r2"],
    )


def main() -> None:
    args = parse_args()
    configure_logging()
    output_root = Path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    splits = [
        ("train", args.train_manifest, args.train_limit),
        ("val", args.val_manifest, args.val_limit),
        ("test", args.test_manifest, args.test_limit),
    ]

    for split_name, manifest_path, limit in splits:
        preprocess_missing_samples(
            split_name=split_name,
            manifest_path=manifest_path,
            limit=limit,
            artifact_root=args.artifact_root,
        )

    jobs_dir = output_root / "jobs"
    clip_root = output_root / "features" / "clip"
    wav_root = output_root / "features" / "wav2clip"
    bg_root = output_root / "features" / "bg"
    bundle_root = output_root / "bundles"

    for split_name, manifest_path, limit in splits:
        jobs_path = build_jobs(
            split_name=split_name,
            manifest_path=manifest_path,
            limit=limit,
            artifact_root=args.artifact_root,
            output_path=jobs_dir / f"{split_name}_jobs.json",
        )
        extract_clip_features(
            split_name=split_name,
            jobs_path=jobs_path,
            output_dir=clip_root / split_name,
            device=args.clip_device,
            max_sentences=args.max_sentences,
        )
        extract_wav2clip_features(
            split_name=split_name,
            jobs_path=jobs_path,
            output_dir=wav_root / split_name,
        )
        extract_bg_features(
            split_name=split_name,
            jobs_path=jobs_path,
            clip_dir=clip_root / split_name,
            wav2clip_dir=wav_root / split_name,
            output_dir=bg_root / split_name,
        )
        build_bundles(
            split_name=split_name,
            manifest_path=manifest_path,
            limit=limit,
            clip_dir=clip_root / split_name,
            wav2clip_dir=wav_root / split_name,
            bg_dir=bg_root / split_name,
            output_dir=bundle_root / split_name,
        )

    train_and_evaluate(
        output_root=output_root,
        train_bundle_dir=bundle_root / "train",
        val_bundle_dir=bundle_root / "val",
        test_bundle_dir=bundle_root / "test",
        train_limit=args.train_limit,
        val_limit=args.val_limit,
        test_limit=args.test_limit,
        device=args.train_device,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        weight_decay=args.weight_decay,
        hidden_dim=args.hidden_dim,
        attention_heads=args.attention_heads,
        graph_metric=args.graph_metric,
        dropout=args.dropout,
    )


if __name__ == "__main__":
    main()
