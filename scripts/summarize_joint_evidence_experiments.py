"""Summarize ATMR trust and multimodal evidence outputs for thesis material."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_optional(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a compact joint evidence summary.")
    parser.add_argument("--atmr", default="reports/atmr_cat_experiments/atmr_cat_experiment.json")
    parser.add_argument("--multimodal", default="reports/agtn_mtl_bg_v1_lr1e4_drop02/multimodal_bg_comparison.json")
    parser.add_argument("--output", default="reports/joint_evidence_summary.md")
    args = parser.parse_args()

    atmr = load_optional(PROJECT_ROOT / args.atmr)
    multimodal = load_optional(PROJECT_ROOT / args.multimodal)
    lines = [
        "# ATMR 与多模态辅助证据链汇总",
        "",
        "## ATMR-CAT",
        "",
        "ATMR 主线提供自适应选题、异常作答降权、测评可信度和证据链解释。",
        "",
    ]
    for row in atmr.get("rows", []):
        lines.append(f"- `{row['strategy']}`：MAE `{row['mae_to_latent']}`，不确定性 `{row['final_uncertainty']}`，覆盖度 `{row['coverage']}`。")
    lines.extend(["", "## 多模态辅助证据", ""])
    for row in multimodal.get("rows", []):
        metrics = row.get("metrics", {})
        lines.append(
            f"- `{row.get('label')}`：MAE `{metrics.get('mae', '-')}`，PCC `{metrics.get('pcc', '-')}`，CCC `{metrics.get('ccc', '-')}`。"
        )
    lines.extend(
        [
            "",
            "写作建议：论文主贡献放在 ATMR；多模态部分表述为辅助证据链与可信度增强，不作为主测评结论来源。",
        ]
    )
    output = PROJECT_ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"saved={output}")


if __name__ == "__main__":
    main()
