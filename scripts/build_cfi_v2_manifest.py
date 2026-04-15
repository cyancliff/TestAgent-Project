"""Build normalized manifests for CFI-V2 dataset phases."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from multimodal_personality.preprocessing.cfi_v2_dataset import build_phase_manifest, load_yaml_config


def main() -> None:
    parser = argparse.ArgumentParser(description="Build CFI-V2 manifests from pickle annotations and transcripts")
    parser.add_argument(
        "--config",
        default="multimodal_personality/configs/cfi_v2.example.yaml",
        help="Path to the CFI-V2 dataset YAML config",
    )
    parser.add_argument(
        "--phase",
        choices=["train", "val", "test", "all"],
        default="all",
        help="Dataset phase to process",
    )
    args = parser.parse_args()

    config = load_yaml_config(Path(args.config))
    phases = ["train", "val", "test"] if args.phase == "all" else [args.phase]

    for phase in phases:
        _, summary = build_phase_manifest(config=config, phase=phase)
        print(
            f"[{summary.phase}] samples={summary.sample_count} "
            f"missing_videos={summary.missing_videos} "
            f"missing_transcripts={summary.missing_transcripts} "
            f"output={summary.output_path}"
        )


if __name__ == "__main__":
    main()
