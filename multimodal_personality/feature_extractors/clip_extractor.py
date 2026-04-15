"""CLIP-based feature extraction helpers for image and transcript inputs."""

from __future__ import annotations

import json
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

    def __init__(self, model_name: str = "openai/clip-vit-large-patch14-336", device: str = "cpu") -> None:
        self.model_name = model_name
        self.device = device
        self._processor = None
        self._model = None

    def availability(self) -> dict[str, bool]:
        """Report whether the local environment can run CLIP extraction."""
        return {
            "transformers": importlib.util.find_spec("transformers") is not None,
            "torch": importlib.util.find_spec("torch") is not None,
            "pil": importlib.util.find_spec("PIL") is not None,
        }

    def _load_model(self) -> None:
        """Lazy-load the processor and model."""
        if self._processor is not None and self._model is not None:
            return
        from transformers import CLIPModel, CLIPProcessor

        self._processor = CLIPProcessor.from_pretrained(self.model_name)
        self._model = CLIPModel.from_pretrained(self.model_name)
        self._model.to(self.device)
        self._model.eval()

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
            if hasattr(image_features, "cpu"):
                return image_features.cpu().tolist()
            if hasattr(image_features, "image_embeds"):
                return image_features.image_embeds.cpu().tolist()
            if hasattr(image_features, "pooler_output"):
                return image_features.pooler_output.cpu().tolist()
            raise TypeError(f"Unsupported image feature output type: {type(image_features)!r}")

    def _encode_text(self, transcript: str) -> list[float]:
        """Encode transcript text into a CLIP text embedding."""
        import torch

        self._load_model()
        inputs = self._processor(text=[transcript or ""], return_tensors="pt", padding=True, truncation=True)
        inputs = {key: value.to(self.device) for key, value in inputs.items()}
        with torch.no_grad():
            text_features = self._model.get_text_features(
                input_ids=inputs["input_ids"],
                attention_mask=inputs.get("attention_mask"),
            )
            if hasattr(text_features, "cpu"):
                return text_features.squeeze(0).cpu().tolist()
            if hasattr(text_features, "text_embeds"):
                return text_features.text_embeds.squeeze(0).cpu().tolist()
            if hasattr(text_features, "pooler_output"):
                return text_features.pooler_output.squeeze(0).cpu().tolist()
            raise TypeError(f"Unsupported text feature output type: {type(text_features)!r}")

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
            output_path.write_text(
                json.dumps(
                    {
                        "video_name": sample["video_name"],
                        "success": False,
                        "errors": errors,
                        "availability": availability,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            return FeatureExtractionResult(
                video_name=sample["video_name"],
                success=False,
                output_path=str(output_path),
                errors=errors,
            )

        frame_root = Path(frames_dir)
        frame_paths = sorted(frame_root.glob("*.jpg"))
        if not frame_paths:
            errors.append(f"no frames found in {frame_root}")
            output_path.write_text(
                json.dumps(
                    {
                        "video_name": sample["video_name"],
                        "success": False,
                        "errors": errors,
                        "availability": availability,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            return FeatureExtractionResult(
                video_name=sample["video_name"],
                success=False,
                output_path=str(output_path),
                errors=errors,
            )

        image_features = self._encode_images(frame_paths)
        text_features = self._encode_text(sample.get("transcript", ""))
        payload = {
            "video_name": sample["video_name"],
            "success": True,
            "model_name": self.model_name,
            "frame_count": len(frame_paths),
            "image_feature_dim": len(image_features[0]) if image_features else 0,
            "text_feature_dim": len(text_features),
            "image_features": image_features,
            "text_features": text_features,
        }
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return FeatureExtractionResult(
            video_name=sample["video_name"],
            success=True,
            output_path=str(output_path),
            errors=[],
        )
