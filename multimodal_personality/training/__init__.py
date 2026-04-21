"""Training and checkpoint helpers for the multimodal personality baseline."""

from multimodal_personality.training.baseline import (
    BundleDataset,
    EvaluationResult,
    LoadedCheckpoint,
    PredictionRecord,
    ResolvedBundleSet,
    TRAIT_ORDER,
    TrainingRunResult,
    compute_regression_metrics,
    discover_bundle_paths,
    evaluate_bundle_paths,
    load_checkpoint_model,
    predict_bundle_paths,
    train_baseline_model,
)

__all__ = [
    "BundleDataset",
    "EvaluationResult",
    "LoadedCheckpoint",
    "PredictionRecord",
    "ResolvedBundleSet",
    "TRAIT_ORDER",
    "TrainingRunResult",
    "compute_regression_metrics",
    "discover_bundle_paths",
    "evaluate_bundle_paths",
    "load_checkpoint_model",
    "predict_bundle_paths",
    "train_baseline_model",
]
