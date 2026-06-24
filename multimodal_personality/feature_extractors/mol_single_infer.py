"""Standalone MOL inference runner for one extracted frame directory.

This file is intentionally lightweight: it runs in a subprocess so the main
online service can keep working even when MOL dependencies fail.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from types import SimpleNamespace


CLASS_ORDER = ["surprise", "positive", "negative"]
CLIP_LENGTH = 8


def _sort_frame_paths(frames_dir: Path) -> list[Path]:
    image_paths = [
        path
        for path in frames_dir.iterdir()
        if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp"}
    ]

    def key(path: Path) -> tuple[int, str]:
        numbers = re.findall(r"\d+", path.stem)
        return (int(numbers[-1]) if numbers else 0, path.name)

    return sorted(image_paths, key=key)


def _write_payload(output_path: Path, payload: dict[str, object]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _build_video_tensor(frame_paths: list[Path]):
    import cv2
    import numpy as np
    import torch
    import dataset as mol_dataset

    if not frame_paths:
        raise RuntimeError("MOL needs at least 1 frame, received 0")

    sample_interval = max(len(frame_paths) // CLIP_LENGTH, 1)
    sample_count = max(min(sample_interval, len(frame_paths) - CLIP_LENGTH + 1), 1)
    samples = []
    for offset in range(sample_count):
        frames = []
        for frame_index in range(CLIP_LENGTH):
            selected_index = min(frame_index * sample_interval + offset, len(frame_paths) - 1)
            align_img, align_ldm = mol_dataset.img_pre_dlib(
                mol_dataset.detector,
                mol_dataset.predictor,
                str(frame_paths[selected_index]),
            )
            gray_img = cv2.cvtColor(align_img, cv2.COLOR_BGR2GRAY)[..., None]
            crop_img, _ = mol_dataset.crop_img_ldm(gray_img, align_ldm)
            frames.append(crop_img)

        video_array = np.asarray(frames, dtype=np.float32)
        video_array = np.rollaxis(video_array, 3, 0)
        samples.append(video_array)

    video_array = np.asarray(samples, dtype=np.float32)
    video_array -= np.mean(video_array)
    max_value = float(np.max(np.abs(video_array)))
    if max_value > 1e-12:
        video_array /= max_value
    return torch.tensor(video_array, dtype=torch.float32)


def _run(args: argparse.Namespace) -> dict[str, object]:
    import torch
    import torch.nn.functional as F

    mol_root = Path(args.mol_root).resolve()
    os.chdir(mol_root)
    sys.path.insert(0, str(mol_root))

    from MOL_model import MOL

    device_name = args.device
    if device_name == "auto":
        device_name = "cuda:0" if torch.cuda.is_available() else "cpu"
    force_cpu = device_name == "cpu"
    if force_cpu:
        torch.cuda.is_available = lambda: False
    if device_name.startswith("cuda") and not torch.cuda.is_available():
        device_name = "cpu"
    device = torch.device(device_name)

    frame_paths = _sort_frame_paths(Path(args.frames_dir))
    video = _build_video_tensor(frame_paths).to(device)

    model_args = SimpleNamespace(cls=args.cls, neighbor_num=args.neighbor_num)
    model = MOL(model_args).to(device)
    weights = torch.load(Path(args.model_path), map_location=device)
    if isinstance(weights, dict) and "model_state_dict" in weights:
        weights = weights["model_state_dict"]
    model.load_state_dict(weights, strict=False)
    model.eval()

    with torch.no_grad():
        logits, _, _ = model(video)
        probabilities = F.softmax(logits, dim=1).mean(dim=0).detach().cpu().tolist()

    return {
        "success": True,
        "model_version": Path(args.model_path).stem,
        "class_order": CLASS_ORDER[: args.cls],
        "probabilities": {
            label: float(probabilities[index]) if index < len(probabilities) else 0.0
            for index, label in enumerate(CLASS_ORDER[: args.cls])
        },
        "sample_count": int(video.shape[0]),
        "frame_count": len(frame_paths),
        "errors": [],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run MOL micro-expression inference for one frame directory")
    parser.add_argument("--mol-root", required=True)
    parser.add_argument("--frames-dir", required=True)
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--cls", type=int, default=3)
    parser.add_argument("--neighbor-num", type=int, default=4)
    args = parser.parse_args()

    output_path = Path(args.output)
    try:
        payload = _run(args)
    except Exception as exc:
        payload = {
            "success": False,
            "model_version": Path(args.model_path).stem,
            "class_order": CLASS_ORDER[: args.cls],
            "probabilities": {label: 0.0 for label in CLASS_ORDER[: args.cls]},
            "errors": [str(exc)],
        }
    _write_payload(output_path, payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
