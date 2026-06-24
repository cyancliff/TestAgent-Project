"""CLIP-based feature extraction helpers for image and transcript inputs."""

from __future__ import annotations

import os
import json
import re
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import importlib.util


@dataclass
class FeatureExtractionResult:
    """Result summary for one sample extraction."""

    video_name: str
    success: bool
    output_path: str
    errors: list[str]


class ClipFeatureExtractor:
    """Feature extraction wrapper using Hugging Face CLIP components."""

    _REQUIRED_CACHE_FILES = (
        "config.json",
        "preprocessor_config.json",
        "tokenizer_config.json",
        "vocab.json",
        "merges.txt",
    )
    _WEIGHT_CACHE_FILES = (
        "model.safetensors",
        "model.safetensors.index.json",
        "pytorch_model.bin",
        "pytorch_model.bin.index.json",
    )

    def __init__(
        self,
        model_name: str = "openai/clip-vit-large-patch14-336",
        device: str = "cpu",
        max_sentences: int | None = None,
    ) -> None:
        self.model_name = model_name
        self.device = device
        self.max_sentences = max_sentences if max_sentences and max_sentences > 0 else None
        self._processor = None
        self._model = None

    @contextmanager
    def _suppress_model_loading_output(self):
        """Silence third-party progress output that can fail in detached servers."""
        with open(os.devnull, "w", encoding="utf-8") as sink:
            with redirect_stdout(sink), redirect_stderr(sink):
                yield

    def availability(self) -> dict[str, bool]:
        """Report whether the local environment can run CLIP extraction."""
        return {
            "transformers": importlib.util.find_spec("transformers") is not None,
            "torch": importlib.util.find_spec("torch") is not None,
            "pil": importlib.util.find_spec("PIL") is not None,
        }

    @staticmethod
    def _path_exists(path: str | Path | None) -> bool:
        return bool(path and Path(path).exists())

    def _local_directory_model_available(self) -> bool:
        model_path = Path(self.model_name).expanduser()
        if not model_path.is_dir():
            return False

        has_required_files = all((model_path / filename).exists() for filename in self._REQUIRED_CACHE_FILES)
        has_weight_file = any((model_path / filename).exists() for filename in self._WEIGHT_CACHE_FILES)
        return has_required_files and has_weight_file

    def _huggingface_cache_model_available(self) -> bool:
        try:
            from huggingface_hub import try_to_load_from_cache
        except Exception:
            return False

        def cached(filename: str) -> bool:
            try:
                return self._path_exists(try_to_load_from_cache(self.model_name, filename))
            except Exception:
                return False

        return all(cached(filename) for filename in self._REQUIRED_CACHE_FILES) and any(
            cached(filename) for filename in self._WEIGHT_CACHE_FILES
        )

    def local_model_available(self) -> bool:
        """Return whether all required CLIP files are already available offline."""
        if not all(self.availability().values()):
            return False
        return self._local_directory_model_available() or self._huggingface_cache_model_available()

    def _load_model(self) -> None:
        """Lazy-load the processor and model."""
        if self._processor is not None and self._model is not None:
            return
        from transformers import CLIPModel, CLIPProcessor

        try:
            with self._suppress_model_loading_output():
                self._processor = CLIPProcessor.from_pretrained(
                    self.model_name,
                    local_files_only=True,
                )
                self._model = CLIPModel.from_pretrained(
                    self.model_name,
                    local_files_only=True,
                )
                self._model.to(self.device)
                self._model.eval()
        except Exception:
            self._processor = None
            self._model = None
            raise

    @staticmethod
    def _feature_tensor_to_list(features: Any) -> list[list[float]]:
        if hasattr(features, "cpu"):
            tensor = features
        elif hasattr(features, "text_embeds"):
            tensor = features.text_embeds
        elif hasattr(features, "image_embeds"):
            tensor = features.image_embeds
        elif hasattr(features, "pooler_output"):
            tensor = features.pooler_output
        else:
            raise TypeError(f"Unsupported feature output type: {type(features)!r}")

        tensor = tensor.detach().cpu()
        if tensor.ndim == 1:
            tensor = tensor.unsqueeze(0)
        return tensor.tolist()

    def _encode_images(self, frame_paths: list[Path]) -> list[list[float]]:
        """Encode extracted frames into CLIP image embeddings."""
        from PIL import Image
        import torch

        self._load_model()
        images = [Image.open(path).convert("RGB") for path in frame_paths]
        inputs = self._processor(images=images, return_tensors="pt")
        inputs = {key: value.to(self.device) for key, value in inputs.items()}
        with torch.no_grad():
            image_features = self._model.get_image_features(pixel_values=inputs["pixel_values"])
            return self._feature_tensor_to_list(image_features)

    def _encode_texts(self, texts: list[str]) -> list[list[float]]:
        """Encode one or more text spans into CLIP text embeddings."""
        import torch

        if not texts:
            return []

        self._load_model()
        inputs = self._processor(text=texts, return_tensors="pt", padding=True, truncation=True)
        inputs = {key: value.to(self.device) for key, value in inputs.items()}
        with torch.no_grad():
            text_features = self._model.get_text_features(
                input_ids=inputs["input_ids"],
                attention_mask=inputs.get("attention_mask"),
            )
            return self._feature_tensor_to_list(text_features)

    def _encode_text(self, transcript: str) -> list[float]:
        """Encode the full transcript into a single CLIP text embedding."""
        embeddings = self._encode_texts([transcript or ""])
        return embeddings[0] if embeddings else []

    def split_transcript_sentences(self, transcript: str) -> list[str]:
        """Split a transcript into sentence-like segments for sequence modeling."""
        normalized = transcript.replace("\r\n", "\n").replace("\r", "\n").strip()
        if not normalized:
            return []

        parts = re.split(r"(?<=[.!?])\s+|\n+", normalized)
        sentences: list[str] = []
        for part in parts:
            sentence = " ".join(part.strip().split())
            if sentence:
                sentences.append(sentence)

        if self.max_sentences is not None:
            sentences = sentences[: self.max_sentences]
        return sentences

    @staticmethod
    def _write_payload(output_path: Path, payload: dict[str, Any]) -> None:
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _write_failure(
        self,
        *,
        output_path: Path,
        video_name: str,
        errors: list[str],
        availability: dict[str, bool],
    ) -> FeatureExtractionResult:
        self._write_payload(
            output_path,
            {
                "video_name": video_name,
                "success": False,
                "errors": errors,
                "availability": availability,
            },
        )
        return FeatureExtractionResult(
            video_name=video_name,
            success=False,
            output_path=str(output_path),
            errors=errors,
        )

    def extract_sample(
        self,
        sample: dict[str, Any],
        frames_dir: str | Path,
        output_dir: str | Path,
    ) -> FeatureExtractionResult:
        """Extract CLIP features for a single manifest sample."""
        output_root = Path(output_dir)
        output_root.mkdir(parents=True, exist_ok=True)
        output_path = output_root / f"{sample['video_name']}.json"
        errors: list[str] = []

        availability = self.availability()
        if not all(availability.values()):
            missing = [name for name, ok in availability.items() if not ok]
            errors.append(f"missing dependencies: {', '.join(missing)}")
            return self._write_failure(
                output_path=output_path,
                video_name=sample["video_name"],
                errors=errors,
                availability=availability,
            )

        frame_root = Path(frames_dir)
        frame_paths = sorted(frame_root.glob("*.jpg"))
        if not frame_paths:
            errors.append(f"no frames found in {frame_root}")
            return self._write_failure(
                output_path=output_path,
                video_name=sample["video_name"],
                errors=errors,
                availability=availability,
            )

        try:
            transcript = sample.get("transcript", "")
            sentences = self.split_transcript_sentences(transcript)
            image_features = self._encode_images(frame_paths)
            text_features = self._encode_text(transcript)
            text_sequence_features = self._encode_texts(sentences)
        except Exception as exc:
            errors.append(f"clip feature extraction failed: {exc}")
            return self._write_failure(
                output_path=output_path,
                video_name=sample["video_name"],
                errors=errors,
                availability=availability,
            )

        payload = {
            "video_name": sample["video_name"],
            "success": True,
            "model_name": self.model_name,
            "frame_count": len(frame_paths),
            "image_feature_dim": len(image_features[0]) if image_features else 0,
            "text_feature_dim": len(text_features),
            "text_sequence_count": len(text_sequence_features),
            "text_sequence_feature_dim": len(text_sequence_features[0]) if text_sequence_features else 0,
            "text_sentences": sentences,
            "image_features": image_features,
            "text_features": text_features,
            "text_sequence_features": text_sequence_features,
            "errors": [],
        }
        self._write_payload(output_path, payload)
        return FeatureExtractionResult(
            video_name=sample["video_name"],
            success=True,
            output_path=str(output_path),
            errors=[],
        )
