"""Run MOL micro-expression extraction for a frame directory."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from multimodal_personality.feature_extractors.micro_expression_extractor import MOLMicroExpressionExtractor


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run MOL micro-expression extraction for a frame directory")
    parser.add_argument("--frames-dir", required=True, help="Directory containing extracted face/video frames")
    parser.add_argument("--video-name", default=None, help="Display name for this sample")
    parser.add_argument("--video-path", default=None, help="Original video path, optional")
    parser.add_argument(
        "--output-dir",
        default="uploads/multimodal_personality/artifacts/mol_demo/features/micro_expression",
        help="Directory that will receive micro_expression_feature.json",
    )
    parser.add_argument("--device", default="cpu", help="Use cpu for stable demos, or cuda:0 when available")
    parser.add_argument("--timeout-seconds", type=int, default=60)
    return parser.parse_args()


def format_demo_output(payload: dict, output_path: str | Path) -> str:
    status = "微表情提取成功" if payload.get("success") else "微表情提取未成功"
    summary = payload.get("summary_text_zh") or "暂无可用摘要。"
    feature_dim = len(payload.get("feature_vector") or [])
    errors = payload.get("errors") or []
    lines = [
        status,
        summary,
        f"特征维度：{feature_dim} 维",
        f"结果文件：{output_path}",
    ]
    if errors:
        lines.append("错误信息：" + "；".join(str(error) for error in errors[:3]))
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    frames_dir = Path(args.frames_dir)
    video_name = args.video_name or frames_dir.name
    extractor = MOLMicroExpressionExtractor(device=args.device, timeout_seconds=args.timeout_seconds)
    result = extractor.extract_sample(
        video_name=video_name,
        video_path=args.video_path or frames_dir,
        frames_dir=frames_dir,
        output_dir=args.output_dir,
    )
    payload = json.loads(Path(result.output_path).read_text(encoding="utf-8-sig"))
    print(format_demo_output(payload, result.output_path))


if __name__ == "__main__":
    main()
