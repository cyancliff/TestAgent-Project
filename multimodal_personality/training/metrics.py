"""Regression metrics used by multimodal personality experiments."""

from __future__ import annotations

from typing import Sequence

import torch

from multimodal_personality.models.feature_bundle import TRAIT_ORDER


def _safe_scalar(value: torch.Tensor) -> float:
    result = float(value.item())
    if result != result or result in (float("inf"), float("-inf")):
        return 0.0
    return result


def _pearson_correlation(predictions: torch.Tensor, targets: torch.Tensor) -> float:
    pred_centered = predictions - torch.mean(predictions)
    target_centered = targets - torch.mean(targets)
    denominator = torch.sqrt(torch.sum(pred_centered**2) * torch.sum(target_centered**2))
    if float(denominator.item()) <= 1e-12:
        return 0.0
    return _safe_scalar(torch.sum(pred_centered * target_centered) / denominator)


def _concordance_correlation_coefficient(predictions: torch.Tensor, targets: torch.Tensor) -> float:
    pred_mean = torch.mean(predictions)
    target_mean = torch.mean(targets)
    covariance = torch.mean((predictions - pred_mean) * (targets - target_mean))
    pred_variance = torch.mean((predictions - pred_mean) ** 2)
    target_variance = torch.mean((targets - target_mean) ** 2)
    denominator = pred_variance + target_variance + (pred_mean - target_mean) ** 2
    if float(denominator.item()) <= 1e-12:
        return 0.0
    return _safe_scalar((2 * covariance) / denominator)


def _r2_score(predictions: torch.Tensor, targets: torch.Tensor) -> float:
    residual_sum = torch.sum((predictions - targets) ** 2)
    total_sum = torch.sum((targets - torch.mean(targets)) ** 2)
    if float(total_sum.item()) <= 1e-12:
        return 0.0
    return _safe_scalar(1 - residual_sum / total_sum)


def _bounded_regression_accuracy(mae: float) -> float:
    """Personality regression ACC commonly uses 1 - MAE for scores in [0, 1]."""

    return max(0.0, min(1.0, 1.0 - mae))


def _metric_block(predictions: torch.Tensor, targets: torch.Tensor) -> dict[str, float]:
    diff = predictions - targets
    mse = torch.mean(diff**2).item()
    mae = torch.mean(torch.abs(diff)).item()
    rmse = mse**0.5
    return {
        "mse": float(mse),
        "rmse": float(rmse),
        "mae": float(mae),
        "acc": _bounded_regression_accuracy(float(mae)),
        "pcc": _pearson_correlation(predictions, targets),
        "ccc": _concordance_correlation_coefficient(predictions, targets),
        "r2": _r2_score(predictions, targets),
    }


def compute_regression_metrics(
    predictions: torch.Tensor,
    targets: torch.Tensor,
    *,
    trait_order: Sequence[str] = TRAIT_ORDER,
) -> dict[str, object]:
    """Compute aggregate and per-trait regression metrics.

    The aggregate PCC/CCC/R2 are computed on the flattened five-trait score matrix.
    Per-trait values are kept separately for paper tables and error analysis.
    """

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

    aggregate = _metric_block(predictions.flatten(), targets.flatten())
    per_trait = {
        trait_name: _metric_block(predictions[:, trait_index], targets[:, trait_index])
        for trait_index, trait_name in enumerate(trait_order)
    }

    return {
        "sample_count": int(predictions.shape[0]),
        **aggregate,
        "per_trait": per_trait,
    }

