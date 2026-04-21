"""Minimal end-to-end training helpers for the AGTN-MTL baseline."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset

from multimodal_personality.models import AGTNMTLModel, MultimodalFeatureBundle
from multimodal_personality.models.feature_bundle import TRAIT_ORDER
from multimodal_personality.preprocessing.cfi_v2_dataset import filter_manifest_samples, load_manifest


@dataclass
class ResolvedBundleSet:
    """Resolved bundle file paths plus any samples missing bundle JSON files."""

    bundle_paths: list[Path]
    missing_bundle_names: list[str]


@dataclass
class PredictionRecord:
    """Serializable prediction output for one bundle."""

    video_name: str
    bundle_path: str
    scores: dict[str, float]
    labels: dict[str, float] | None = None


@dataclass
class EvaluationResult:
    """Evaluation summary for a set of bundle files."""

    sample_count: int
    mean_loss: float | None
    metrics: dict[str, object]
    predictions: list[PredictionRecord]


@dataclass
class TrainingRunResult:
    """Training summary for one baseline run."""

    checkpoint_path: Path
    best_epoch: int
    best_loss: float
    history: list[dict[str, object]]


@dataclass
class LoadedCheckpoint:
    """Loaded checkpoint payload and reconstructed model."""

    model: AGTNMTLModel
    checkpoint: dict[str, object]
    device: torch.device


class BundleDataset(Dataset):
    """PyTorch dataset that materializes tensors from feature bundle JSON files."""

    def __init__(
        self,
        bundle_paths: Sequence[str | Path],
        *,
        text_seq_len: int = 13,
        fill_missing_modalities: bool = True,
        require_labels: bool = True,
    ) -> None:
        self.bundle_paths = [Path(path) for path in bundle_paths]
        self.text_seq_len = text_seq_len
        self.fill_missing_modalities = fill_missing_modalities
        self.require_labels = require_labels

    def __len__(self) -> int:
        return len(self.bundle_paths)

    def __getitem__(self, index: int) -> dict[str, object]:
        bundle_path = self.bundle_paths[index]
        bundle = MultimodalFeatureBundle.from_json_file(bundle_path)
        tensors = bundle.to_tensors(
            text_seq_len=self.text_seq_len,
            fill_missing_modalities=self.fill_missing_modalities,
        )
        if self.require_labels and "labels" not in tensors:
            raise ValueError(f"bundle {bundle_path} does not contain labels")

        sample: dict[str, object] = {
            "video_name": bundle.video_name,
            "bundle_path": str(bundle_path),
            "clip_video": tensors["clip_video"],
            "wav2clip": tensors["wav2clip"],
            "clip_text": tensors["clip_text"],
            "bg_features": tensors["bg_features"],
        }
        if "labels" in tensors:
            sample["labels"] = tensors["labels"]
        return sample


def discover_bundle_paths(
    bundle_dir: str | Path,
    *,
    manifest_path: str | Path | None = None,
    limit: int | None = None,
) -> ResolvedBundleSet:
    """Resolve bundle file paths from a directory, optionally filtered by a manifest."""

    bundle_root = Path(bundle_dir)
    if not bundle_root.exists():
        raise FileNotFoundError(f"bundle directory not found: {bundle_root}")

    if manifest_path is None:
        bundle_paths = sorted(bundle_root.glob("*.json"))
        if limit is not None:
            bundle_paths = bundle_paths[:limit]
        return ResolvedBundleSet(bundle_paths=bundle_paths, missing_bundle_names=[])

    manifest = load_manifest(manifest_path)
    samples = filter_manifest_samples(
        manifest,
        require_video=False,
        require_transcript=False,
        limit=limit,
    )
    bundle_paths: list[Path] = []
    missing_bundle_names: list[str] = []
    for sample in samples:
        bundle_path = bundle_root / f"{sample['video_name']}.json"
        if bundle_path.exists():
            bundle_paths.append(bundle_path)
        else:
            missing_bundle_names.append(sample["video_name"])
    return ResolvedBundleSet(bundle_paths=bundle_paths, missing_bundle_names=missing_bundle_names)


def compute_regression_metrics(
    predictions: torch.Tensor,
    targets: torch.Tensor,
    *,
    trait_order: Sequence[str] = TRAIT_ORDER,
) -> dict[str, object]:
    """Compute aggregate and per-trait regression metrics."""

    if predictions.shape != targets.shape:
        raise ValueError(
            f"prediction and target shapes must match, received {tuple(predictions.shape)} vs {tuple(targets.shape)}",
        )
    if predictions.ndim != 2:
        raise ValueError(f"expected 2D predictions, received shape={tuple(predictions.shape)}")
    if predictions.shape[1] != len(trait_order):
        raise ValueError(
            f"prediction width {predictions.shape[1]} does not match trait count {len(trait_order)}",
        )

    diff = predictions - targets
    mse = torch.mean(diff**2).item()
    mae = torch.mean(torch.abs(diff)).item()
    rmse = mse**0.5

    per_trait: dict[str, dict[str, float]] = {}
    for trait_index, trait_name in enumerate(trait_order):
        trait_diff = diff[:, trait_index]
        trait_mse = torch.mean(trait_diff**2).item()
        trait_mae = torch.mean(torch.abs(trait_diff)).item()
        per_trait[trait_name] = {
            "mse": trait_mse,
            "rmse": trait_mse**0.5,
            "mae": trait_mae,
        }

    return {
        "sample_count": int(predictions.shape[0]),
        "mse": mse,
        "rmse": rmse,
        "mae": mae,
        "per_trait": per_trait,
    }


def _build_dataloader(
    bundle_paths: Sequence[str | Path],
    *,
    batch_size: int,
    shuffle: bool,
    text_seq_len: int,
    fill_missing_modalities: bool,
    require_labels: bool,
) -> DataLoader:
    dataset = BundleDataset(
        bundle_paths,
        text_seq_len=text_seq_len,
        fill_missing_modalities=fill_missing_modalities,
        require_labels=require_labels,
    )
    return DataLoader(dataset, batch_size=batch_size, shuffle=shuffle, num_workers=0)


def _move_batch_to_device(batch: dict[str, object], device: torch.device) -> dict[str, object]:
    moved: dict[str, object] = {}
    for key, value in batch.items():
        moved[key] = value.to(device) if isinstance(value, torch.Tensor) else value
    return moved


def _forward_main_prediction(model: AGTNMTLModel, batch: dict[str, object]) -> torch.Tensor:
    outputs = model(
        clip_video=batch["clip_video"],
        wav2clip=batch["wav2clip"],
        clip_text=batch["clip_text"],
        bg=batch["bg_features"],
    )
    return outputs["m"]


def _records_from_batch(batch: dict[str, object], predictions: torch.Tensor) -> list[PredictionRecord]:
    records: list[PredictionRecord] = []
    video_names = list(batch["video_name"])
    bundle_paths = list(batch["bundle_path"])
    label_tensor = batch.get("labels")
    label_rows = label_tensor.detach().cpu() if isinstance(label_tensor, torch.Tensor) else None
    prediction_rows = predictions.detach().cpu()

    for index, video_name in enumerate(video_names):
        scores = {
            trait_name: float(prediction_rows[index, trait_index].item())
            for trait_index, trait_name in enumerate(TRAIT_ORDER)
        }
        labels = None
        if label_rows is not None:
            labels = {
                trait_name: float(label_rows[index, trait_index].item())
                for trait_index, trait_name in enumerate(TRAIT_ORDER)
            }
        records.append(
            PredictionRecord(
                video_name=video_name,
                bundle_path=bundle_paths[index],
                scores=scores,
                labels=labels,
            ),
        )
    return records


def _build_model(*, model_kwargs: dict[str, object], device: torch.device) -> AGTNMTLModel:
    model = AGTNMTLModel(**model_kwargs)
    model.to(device)
    return model


def _save_checkpoint(
    checkpoint_path: str | Path,
    *,
    model: AGTNMTLModel,
    model_kwargs: dict[str, object],
    epoch: int,
    train_loss: float,
    val_result: EvaluationResult | None,
    history: list[dict[str, object]],
    train_bundle_count: int,
    val_bundle_count: int,
) -> Path:
    checkpoint_file = Path(checkpoint_path)
    checkpoint_file.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "model_name": "AGTNMTLModel",
        "trait_order": list(TRAIT_ORDER),
        "model_kwargs": model_kwargs,
        "model_state_dict": model.state_dict(),
        "epoch": epoch,
        "train_loss": train_loss,
        "val_loss": None if val_result is None else val_result.mean_loss,
        "val_metrics": None if val_result is None else val_result.metrics,
        "history": history,
        "train_bundle_count": train_bundle_count,
        "val_bundle_count": val_bundle_count,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    torch.save(payload, checkpoint_file)
    return checkpoint_file


def load_checkpoint_model(checkpoint_path: str | Path, *, device: str | torch.device = "cpu") -> LoadedCheckpoint:
    """Load a saved baseline checkpoint and reconstruct the model."""

    resolved_device = torch.device(device)
    checkpoint = torch.load(Path(checkpoint_path), map_location=resolved_device)
    model_kwargs = dict(checkpoint.get("model_kwargs", {}))
    model = _build_model(model_kwargs=model_kwargs, device=resolved_device)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()
    return LoadedCheckpoint(model=model, checkpoint=checkpoint, device=resolved_device)


def evaluate_bundle_paths(
    model: AGTNMTLModel,
    bundle_paths: Sequence[str | Path],
    *,
    device: str | torch.device = "cpu",
    batch_size: int = 8,
    text_seq_len: int = 13,
    fill_missing_modalities: bool = True,
    require_labels: bool = True,
) -> EvaluationResult:
    """Evaluate or predict a list of bundle files with the baseline model."""

    if not bundle_paths:
        raise ValueError("at least one bundle path is required")

    resolved_device = torch.device(device)
    data_loader = _build_dataloader(
        bundle_paths,
        batch_size=batch_size,
        shuffle=False,
        text_seq_len=text_seq_len,
        fill_missing_modalities=fill_missing_modalities,
        require_labels=require_labels,
    )
    criterion = nn.MSELoss()
    prediction_chunks: list[torch.Tensor] = []
    target_chunks: list[torch.Tensor] = []
    prediction_records: list[PredictionRecord] = []
    total_loss = 0.0
    labeled_sample_count = 0

    model.eval()
    with torch.no_grad():
        for raw_batch in data_loader:
            batch = _move_batch_to_device(raw_batch, resolved_device)
            predictions = _forward_main_prediction(model, batch)
            prediction_chunks.append(predictions.detach().cpu())
            prediction_records.extend(_records_from_batch(raw_batch, predictions))
            labels = batch.get("labels")
            if isinstance(labels, torch.Tensor):
                batch_size_value = int(labels.shape[0])
                target_chunks.append(labels.detach().cpu())
                total_loss += criterion(predictions, labels).item() * batch_size_value
                labeled_sample_count += batch_size_value

    metrics: dict[str, object] = {}
    mean_loss: float | None = None
    if target_chunks:
        all_predictions = torch.cat(prediction_chunks, dim=0)
        all_targets = torch.cat(target_chunks, dim=0)
        metrics = compute_regression_metrics(all_predictions, all_targets)
        mean_loss = total_loss / labeled_sample_count

    return EvaluationResult(
        sample_count=len(prediction_records),
        mean_loss=mean_loss,
        metrics=metrics,
        predictions=prediction_records,
    )


def predict_bundle_paths(
    checkpoint_path: str | Path,
    bundle_paths: Sequence[str | Path],
    *,
    device: str | torch.device = "cpu",
    batch_size: int = 8,
) -> EvaluationResult:
    """Load a checkpoint and run prediction for one or more bundles."""

    loaded = load_checkpoint_model(checkpoint_path, device=device)
    model_kwargs = dict(loaded.checkpoint.get("model_kwargs", {}))
    text_seq_len = int(model_kwargs.get("text_seq_len", 13))
    return evaluate_bundle_paths(
        loaded.model,
        bundle_paths,
        device=loaded.device,
        batch_size=batch_size,
        text_seq_len=text_seq_len,
        fill_missing_modalities=True,
        require_labels=False,
    )


def train_baseline_model(
    train_bundle_paths: Sequence[str | Path],
    *,
    checkpoint_path: str | Path,
    val_bundle_paths: Sequence[str | Path] | None = None,
    epochs: int = 5,
    batch_size: int = 8,
    learning_rate: float = 1e-3,
    weight_decay: float = 0.0,
    device: str | torch.device = "cpu",
    text_seq_len: int = 13,
    fill_missing_modalities: bool = True,
    model_kwargs: dict[str, object] | None = None,
) -> TrainingRunResult:
    """Train the AGTN-MTL baseline on bundle JSON files and save the best checkpoint."""

    if not train_bundle_paths:
        raise ValueError("at least one training bundle path is required")

    resolved_device = torch.device(device)
    model_config = {
        "text_seq_len": text_seq_len,
    }
    if model_kwargs:
        model_config.update(model_kwargs)

    model = _build_model(model_kwargs=model_config, device=resolved_device)
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate, weight_decay=weight_decay)
    criterion = nn.MSELoss()

    train_loader = _build_dataloader(
        train_bundle_paths,
        batch_size=batch_size,
        shuffle=True,
        text_seq_len=text_seq_len,
        fill_missing_modalities=fill_missing_modalities,
        require_labels=True,
    )

    val_paths = list(val_bundle_paths or [])
    history: list[dict[str, object]] = []
    best_epoch = 0
    best_loss = float("inf")
    best_checkpoint_path = Path(checkpoint_path)

    for epoch in range(1, epochs + 1):
        model.train()
        total_train_loss = 0.0
        total_train_samples = 0

        for raw_batch in train_loader:
            batch = _move_batch_to_device(raw_batch, resolved_device)
            labels = batch["labels"]
            optimizer.zero_grad()
            predictions = _forward_main_prediction(model, batch)
            loss = criterion(predictions, labels)
            loss.backward()
            optimizer.step()

            batch_size_value = int(labels.shape[0])
            total_train_loss += loss.item() * batch_size_value
            total_train_samples += batch_size_value

        train_loss = total_train_loss / max(total_train_samples, 1)
        val_result = None
        selected_loss = train_loss
        if val_paths:
            val_result = evaluate_bundle_paths(
                model,
                val_paths,
                device=resolved_device,
                batch_size=batch_size,
                text_seq_len=text_seq_len,
                fill_missing_modalities=fill_missing_modalities,
                require_labels=True,
            )
            if val_result.mean_loss is not None:
                selected_loss = val_result.mean_loss

        epoch_record = {
            "epoch": epoch,
            "train_loss": train_loss,
            "val_loss": None if val_result is None else val_result.mean_loss,
            "val_metrics": None if val_result is None else val_result.metrics,
        }
        history.append(epoch_record)

        if selected_loss <= best_loss:
            best_loss = selected_loss
            best_epoch = epoch
            best_checkpoint_path = _save_checkpoint(
                checkpoint_path,
                model=model,
                model_kwargs=model_config,
                epoch=epoch,
                train_loss=train_loss,
                val_result=val_result,
                history=history,
                train_bundle_count=len(train_bundle_paths),
                val_bundle_count=len(val_paths),
            )

    return TrainingRunResult(
        checkpoint_path=best_checkpoint_path,
        best_epoch=best_epoch,
        best_loss=best_loss,
        history=history,
    )
