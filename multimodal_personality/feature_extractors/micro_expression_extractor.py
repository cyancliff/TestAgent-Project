"""MOL micro-expression feature extraction wrapper."""

from __future__ import annotations

import json
import math
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from multimodal_personality.models.feature_bundle import MICRO_EXPRESSION_DIM


CLASS_ORDER = ["surprise", "positive", "negative"]
CLASS_LABEL_ZH = {
    "surprise": "惊讶",
    "positive": "积极",
    "negative": "消极",
}
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MOL_MODEL_PATH = (
    PROJECT_ROOT
    / "third_party"
    / "MOL"
    / "saved_models"
    / "MOL_HF_TIM20_SAMM3_26subj_fullquick_SAMM_006_3cls.pth"
)


@dataclass
class MicroExpressionExtractionResult:
    """Result summary for one MOL micro-expression extraction."""

    video_name: str
    success: bool
    output_path: str
    errors: list[str]


class MOLMicroExpressionExtractor:
    """Call the reproduced MOL baseline and normalize its output for the main system.

    The wrapper always writes ``micro_expression_feature.json``. A MOL runtime
    failure is represented in the JSON payload instead of raising into the
    multimodal personality service.
    """

    schema_version = "mol-micro-expression-v1"
    class_order = CLASS_ORDER
    feature_dim = MICRO_EXPRESSION_DIM

    def __init__(
        self,
        *,
        enabled: bool = True,
        mol_root_dir: str | Path | None = None,
        mol_model_path: str | Path | None = None,
        python_path: str | Path | None = None,
        device: str = "auto",
        timeout_seconds: int = 60,
    ) -> None:
        self.enabled = enabled
        self.mol_root_dir = Path(mol_root_dir) if mol_root_dir else PROJECT_ROOT / "third_party" / "MOL"
        self.mol_model_path = Path(mol_model_path) if mol_model_path else DEFAULT_MOL_MODEL_PATH
        self.python_path = str(python_path) if python_path else self._discover_python_path()
        self.device = device
        self.timeout_seconds = timeout_seconds

    def _discover_python_path(self) -> str:
        windows_venv_python = self.mol_root_dir / ".venv" / "Scripts" / "python.exe"
        if windows_venv_python.exists():
            return str(windows_venv_python)
        posix_venv_python = self.mol_root_dir / ".venv" / "bin" / "python"
        if posix_venv_python.exists():
            return str(posix_venv_python)
        return sys.executable

    def extract_sample(
        self,
        *,
        video_name: str,
        video_path: str | Path,
        frames_dir: str | Path,
        output_dir: str | Path,
    ) -> MicroExpressionExtractionResult:
        output_root = Path(output_dir).resolve()
        output_root.mkdir(parents=True, exist_ok=True)
        output_path = output_root / "micro_expression_feature.json"
        raw_output_path = output_root / "mol_raw_output.json"
        frames_path = Path(frames_dir).resolve()
        errors: list[str] = []

        if not self.enabled:
            errors.append("MOL micro expression extractor disabled")
            self._write_failure_payload(
                output_path=output_path,
                video_name=video_name,
                video_path=video_path,
                errors=errors,
            )
            return MicroExpressionExtractionResult(video_name, False, str(output_path), errors)

        if not frames_path.exists():
            errors.append(f"frames directory not found: {frames_path}")
        if not self.mol_model_path.exists():
            errors.append(f"MOL model not found: {self.mol_model_path}")

        if errors:
            self._write_failure_payload(
                output_path=output_path,
                video_name=video_name,
                video_path=video_path,
                errors=errors,
            )
            return MicroExpressionExtractionResult(video_name, False, str(output_path), errors)

        try:
            self._run_mol_runner(frames_dir=frames_path, output_path=raw_output_path)
            raw_payload = json.loads(raw_output_path.read_text(encoding="utf-8-sig"))
            payload = self._normalize_runner_payload(
                raw_payload,
                video_name=video_name,
                video_path=video_path,
                errors=[],
            )
        except Exception as exc:
            errors.append(f"MOL micro expression extraction failed: {exc}")
            self._write_failure_payload(
                output_path=output_path,
                video_name=video_name,
                video_path=video_path,
                errors=errors,
            )
            return MicroExpressionExtractionResult(video_name, False, str(output_path), errors)

        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return MicroExpressionExtractionResult(
            video_name=video_name,
            success=bool(payload.get("success", False)),
            output_path=str(output_path),
            errors=list(payload.get("errors", [])),
        )

    def _run_mol_runner(self, *, frames_dir: Path, output_path: Path) -> None:
        runner_path = Path(__file__).with_name("mol_single_infer.py")
        command = [
            self.python_path,
            str(runner_path),
            "--mol-root",
            str(self.mol_root_dir.resolve()),
            "--frames-dir",
            str(frames_dir.resolve()),
            "--model-path",
            str(self.mol_model_path.resolve()),
            "--output",
            str(output_path.resolve()),
            "--device",
            self.device,
            "--cls",
            "3",
        ]
        result = subprocess.run(
            command,
            cwd=str(self.mol_root_dir) if self.mol_root_dir.exists() else None,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=self.timeout_seconds,
        )
        if result.returncode != 0:
            message = result.stderr.strip() or result.stdout.strip() or f"MOL runner exited with {result.returncode}"
            raise RuntimeError(message)

    def _normalize_runner_payload(
        self,
        raw_payload: dict[str, Any],
        *,
        video_name: str,
        video_path: str | Path,
        errors: list[str],
    ) -> dict[str, Any]:
        runner_errors = list(raw_payload.get("errors", []))
        if not raw_payload.get("success", False):
            return self._failure_payload(
                video_name=video_name,
                video_path=video_path,
                errors=errors + runner_errors or ["MOL runner returned an unsuccessful payload"],
                model_version=str(raw_payload.get("model_version", "MOL")),
            )

        probabilities = self._normalize_probabilities(raw_payload.get("probabilities"))
        feature_vector = self._build_feature_vector(probabilities, success=True)
        summary = self._build_summary(probabilities)
        return {
            "video_name": video_name,
            "video_path": str(video_path),
            "success": True,
            "schema_version": self.schema_version,
            "model_version": str(raw_payload.get("model_version", "MOL_HF_TIM20_SAMM3_26subj_fullquick")),
            "class_order": list(self.class_order),
            "probabilities": probabilities,
            "feature_vector": feature_vector,
            "feature_dim": self.feature_dim,
            "summary": summary,
            "summary_text_zh": self._build_summary_text_zh(summary),
            "interpretation_boundary_zh": "微表情只作为短时面部线索，不能直接代表稳定人格标签。",
            "sources": {
                "mol_root_dir": str(self.mol_root_dir),
                "mol_model_path": str(self.mol_model_path),
            },
            "errors": errors + runner_errors,
        }

    def _normalize_probabilities(self, values: Any) -> dict[str, float]:
        if isinstance(values, dict):
            probabilities = {label: float(values.get(label, 0.0)) for label in self.class_order}
        elif isinstance(values, list):
            probabilities = {
                label: float(values[index]) if index < len(values) else 0.0
                for index, label in enumerate(self.class_order)
            }
        else:
            probabilities = {label: 0.0 for label in self.class_order}

        probabilities = {
            label: value if math.isfinite(value) and value > 0 else 0.0
            for label, value in probabilities.items()
        }
        total = sum(probabilities.values())
        if total <= 0:
            return {label: 0.0 for label in self.class_order}
        return {label: round(probabilities[label] / total, 6) for label in self.class_order}

    def _build_feature_vector(self, probabilities: dict[str, float], *, success: bool) -> list[float]:
        surprise = probabilities.get("surprise", 0.0)
        positive = probabilities.get("positive", 0.0)
        negative = probabilities.get("negative", 0.0)
        confidence = max(probabilities.values()) if probabilities else 0.0
        entropy = 0.0
        for value in probabilities.values():
            if value > 0:
                entropy -= value * math.log(value, len(self.class_order))
        feature_vector = [
            surprise,
            positive,
            negative,
            confidence,
            entropy,
            positive - negative,
            surprise - max(positive, negative),
            1.0 if success else 0.0,
        ]
        return [round(float(value), 6) for value in feature_vector]

    def _build_summary(self, probabilities: dict[str, float]) -> dict[str, Any]:
        dominant = max(self.class_order, key=lambda label: probabilities.get(label, 0.0))
        confidence = probabilities.get(dominant, 0.0)
        valence_hint = "positive" if dominant == "positive" else "negative" if dominant == "negative" else "mixed"
        return {
            "dominant_expression": dominant,
            "dominant_label_zh": CLASS_LABEL_ZH.get(dominant, dominant),
            "confidence": confidence,
            "valence_hint": valence_hint,
        }

    def _build_summary_text_zh(self, summary: dict[str, Any]) -> str:
        label = summary.get("dominant_label_zh") or "暂无"
        confidence = float(summary.get("confidence") or 0.0)
        return f"主导微表情为{label}，置信度约 {confidence * 100:.0f}/100。"

    def _failure_payload(
        self,
        *,
        video_name: str,
        video_path: str | Path,
        errors: list[str],
        model_version: str = "MOL",
    ) -> dict[str, Any]:
        probabilities = {label: 0.0 for label in self.class_order}
        return {
            "video_name": video_name,
            "video_path": str(video_path),
            "success": False,
            "schema_version": self.schema_version,
            "model_version": model_version,
            "class_order": list(self.class_order),
            "probabilities": probabilities,
            "feature_vector": self._build_feature_vector(probabilities, success=False),
            "feature_dim": self.feature_dim,
            "summary": {
                "dominant_expression": None,
                "dominant_label_zh": "暂无",
                "confidence": 0.0,
                "valence_hint": "unknown",
            },
            "summary_text_zh": "微表情模块未返回可用结果。",
            "interpretation_boundary_zh": "微表情只作为短时面部线索，不能直接代表稳定人格标签。",
            "sources": {
                "mol_root_dir": str(self.mol_root_dir),
                "mol_model_path": str(self.mol_model_path),
            },
            "errors": errors,
        }

    def _write_failure_payload(
        self,
        *,
        output_path: Path,
        video_name: str,
        video_path: str | Path,
        errors: list[str],
    ) -> None:
        payload = self._failure_payload(video_name=video_name, video_path=video_path, errors=errors)
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
