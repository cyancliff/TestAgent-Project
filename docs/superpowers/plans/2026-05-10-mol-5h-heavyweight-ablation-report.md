# MOL 微表情 5 小时重量级加固 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用约 5 小时把 MOL 微表情从“已接入”推进到“可批量产出、可在线展示、可跑小样本消融、可写入组会实验结论”的完整演示闭环。

**Architecture:** 保持当前多模态主模型默认兼容旧 checkpoint；MOL 仍作为可选模块运行。新增批量提取脚本负责从已有 MOL/TIM20 帧目录生成微表情 JSON；新增报告摘要工具把 artifact 转成 API 可展示结构；新增消融 runner 复用现有 `train_agtn_mtl.py` 和 `predict/evaluate` 逻辑；新增实验汇总文档生成器，把批量微表情统计和消融结果写成中文 Markdown。

**Tech Stack:** Python、pytest、PyTorch、FastAPI/Pydantic schema、现有 AGTN-MTL training pipeline、MOL subprocess runner、Markdown/JSON/CSV artifacts。

---

## Scope

这不是“再包装一下”的轻任务，而是面向组会的重量级闭环：

1. 批量跑 MOL 微表情，形成可统计的 `micro_expression_feature.json` 集合。
2. 在线报告 API 返回结构化 `micro_expression_summary`，前端不用自己读本地 JSON。
3. 跑一个小样本消融实验 runner，固定输出 no-micro / with-micro 两组结果。
4. 生成中文实验总结，能直接放进组会汇报。
5. 保证全量测试和真实 MOL 冒烟都通过。

不做的事：

- 不重新设计 MOL 网络结构。
- 不改旧线上 checkpoint 的默认推理结构。
- 不把 `third_party/MOL` 大权重纳入主仓库提交。
- 不强迫在线服务等待大规模批量 MOL 任务。

---

## File Structure

- Create: `scripts/extract_mol_micro_expression_batch.py`
  - 批量扫描 MOL 帧目录，调用 `MOLMicroExpressionExtractor`，支持 `--limit`、`--resume`、`--output-dir`，输出 `summary.json` 和 `summary.csv`。
- Create: `scripts/run_micro_expression_ablation.py`
  - 对指定 bundle 目录跑 no-micro / with-micro 两组小样本训练或评估，输出统一 `ablation_summary.json`。
- Create: `scripts/write_micro_expression_experiment_report.py`
  - 读取批量提取 summary 和消融 summary，生成中文 Markdown 实验报告。
- Create: `app/services/micro_expression_summary_service.py`
  - 把 `micro_expression_feature.json` 安全转成结构化摘要。
- Modify: `app/schemas/multimodal_personality.py`
  - 给任务/报告 response 增加可选 `micro_expression_summary` 字段。
- Modify: `app/api/multimodal_personality.py`
  - `_to_response()` / `_to_report_response()` 注入结构化微表情摘要。
- Modify: `app/api/chat.py`
  - 聊天上下文中追加微表情摘要，明确只是短时线索。
- Modify: `multimodal_personality/README.md`
  - 增加“微表情批量提取与消融实验”章节入口。
- Test: `tests/test_micro_expression_batch_pipeline.py`
- Test: `tests/test_micro_expression_ablation_runner.py`
- Test: `tests/test_big_five_reports_api.py`
- Test: `tests/test_chat_api.py`

---

## Time Budget

- Task 1：批量 MOL 微表情提取器，约 75 分钟。
- Task 2：在线 API 结构化微表情摘要，约 70 分钟。
- Task 3：小样本消融 runner，约 85 分钟。
- Task 4：实验报告生成器与中文文档，约 45 分钟。
- Task 5：真实运行、验收、风险清单，约 25 分钟。

总计约 5 小时。真实 MOL 批量跑的耗时取决于样本数，计划里默认用 `--limit 6` 做组会小闭环。

---

### Task 1: 批量 MOL 微表情提取器

**Files:**
- Create: `scripts/extract_mol_micro_expression_batch.py`
- Test: `tests/test_micro_expression_batch_pipeline.py`

- [ ] **Step 1: Write the failing test for frame directory discovery**

Create `tests/test_micro_expression_batch_pipeline.py`:

```python
from __future__ import annotations

import json

from scripts.extract_mol_micro_expression_batch import discover_frame_samples


def test_discover_frame_samples_reads_nested_class_directories(tmp_path) -> None:
    root = tmp_path / "SAMM_data_3"
    positive = root / "positive" / "007_6_1"
    negative = root / "negative" / "006_2_1"
    positive.mkdir(parents=True)
    negative.mkdir(parents=True)
    for index in range(8):
        (positive / f"{index + 1}.jpg").write_bytes(b"frame")
        (negative / f"{index + 1}.jpg").write_bytes(b"frame")

    samples = discover_frame_samples(root, limit=None)

    assert [sample["video_name"] for sample in samples] == ["006_2_1", "007_6_1"]
    assert samples[0]["class_name"] == "negative"
    assert samples[1]["class_name"] == "positive"
```

- [ ] **Step 2: Run the discovery test and verify RED**

Run:

```powershell
python -m pytest tests/test_micro_expression_batch_pipeline.py::test_discover_frame_samples_reads_nested_class_directories -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.extract_mol_micro_expression_batch'`.

- [ ] **Step 3: Implement discovery only**

Create `scripts/extract_mol_micro_expression_batch.py`:

```python
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from multimodal_personality.feature_extractors.micro_expression_extractor import MOLMicroExpressionExtractor

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp"}


def _has_enough_frames(path: Path, min_frames: int = 8) -> bool:
    return sum(1 for child in path.iterdir() if child.suffix.lower() in IMAGE_SUFFIXES) >= min_frames


def discover_frame_samples(root_dir: str | Path, *, limit: int | None = None) -> list[dict[str, str]]:
    root = Path(root_dir)
    samples: list[dict[str, str]] = []
    for class_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        for frame_dir in sorted(path for path in class_dir.iterdir() if path.is_dir()):
            if not _has_enough_frames(frame_dir):
                continue
            samples.append(
                {
                    "video_name": frame_dir.name,
                    "class_name": class_dir.name,
                    "frames_dir": str(frame_dir),
                }
            )
            if limit is not None and len(samples) >= limit:
                return samples
    return sorted(samples, key=lambda item: item["video_name"])
```

- [ ] **Step 4: Run discovery test and verify GREEN**

Run:

```powershell
python -m pytest tests/test_micro_expression_batch_pipeline.py::test_discover_frame_samples_reads_nested_class_directories -q
```

Expected: PASS.

- [ ] **Step 5: Write failing test for batch summary without real MOL**

Append to `tests/test_micro_expression_batch_pipeline.py`:

```python
from types import SimpleNamespace

from scripts.extract_mol_micro_expression_batch import run_batch_extraction


def test_run_batch_extraction_writes_summary_json_and_csv(tmp_path, monkeypatch) -> None:
    frames_dir = tmp_path / "SAMM_data_3" / "positive" / "007_6_1"
    frames_dir.mkdir(parents=True)
    for index in range(8):
        (frames_dir / f"{index + 1}.jpg").write_bytes(b"frame")

    class FakeExtractor:
        def extract_sample(self, *, video_name, video_path, frames_dir, output_dir):
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / "micro_expression_feature.json"
            output_path.write_text(
                json.dumps(
                    {
                        "success": True,
                        "summary": {"dominant_expression": "positive", "dominant_label_zh": "积极", "confidence": 0.7},
                        "summary_text_zh": "主导微表情为积极，置信度约 70/100。",
                        "feature_vector": [0.1, 0.7, 0.2, 0.7, 0.8, 0.5, 0.4, 1.0],
                        "errors": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            return SimpleNamespace(success=True, output_path=str(output_path), errors=[])

    summary = run_batch_extraction(
        root_dir=tmp_path / "SAMM_data_3",
        output_dir=tmp_path / "micro_batch",
        extractor=FakeExtractor(),
        limit=None,
        resume=False,
    )

    assert summary["sample_count"] == 1
    assert summary["success_count"] == 1
    assert summary["dominant_counts"] == {"positive": 1}
    assert (tmp_path / "micro_batch" / "summary.json").exists()
    assert (tmp_path / "micro_batch" / "summary.csv").exists()
```

- [ ] **Step 6: Run batch summary test and verify RED**

Run:

```powershell
python -m pytest tests/test_micro_expression_batch_pipeline.py::test_run_batch_extraction_writes_summary_json_and_csv -q
```

Expected: FAIL with `ImportError` or `AttributeError` for `run_batch_extraction`.

- [ ] **Step 7: Implement batch extraction and summary writing**

Append to `scripts/extract_mol_micro_expression_batch.py`:

```python
def _load_payload(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _write_summary_csv(rows: list[dict[str, object]], output_path: Path) -> None:
    fieldnames = [
        "video_name",
        "class_name",
        "success",
        "dominant_expression",
        "dominant_label_zh",
        "confidence",
        "output_path",
        "error_count",
    ]
    with output_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def run_batch_extraction(
    *,
    root_dir: str | Path,
    output_dir: str | Path,
    extractor: MOLMicroExpressionExtractor,
    limit: int | None,
    resume: bool,
) -> dict[str, object]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    samples = discover_frame_samples(root_dir, limit=limit)
    rows: list[dict[str, object]] = []
    dominant_counts: dict[str, int] = {}
    success_count = 0

    for sample in samples:
        sample_output_dir = output_root / sample["video_name"]
        output_path = sample_output_dir / "micro_expression_feature.json"
        if resume and output_path.exists():
            payload = _load_payload(output_path)
        else:
            result = extractor.extract_sample(
                video_name=sample["video_name"],
                video_path=sample["frames_dir"],
                frames_dir=sample["frames_dir"],
                output_dir=sample_output_dir,
            )
            payload = _load_payload(result.output_path)

        summary = payload.get("summary") or {}
        success = bool(payload.get("success", False))
        if success:
            success_count += 1
        dominant = str(summary.get("dominant_expression") or "unknown")
        dominant_counts[dominant] = dominant_counts.get(dominant, 0) + 1
        rows.append(
            {
                "video_name": sample["video_name"],
                "class_name": sample["class_name"],
                "success": success,
                "dominant_expression": dominant,
                "dominant_label_zh": summary.get("dominant_label_zh") or "暂无",
                "confidence": float(summary.get("confidence") or 0.0),
                "output_path": str(output_path),
                "error_count": len(payload.get("errors") or []),
            }
        )

    summary_payload = {
        "root_dir": str(root_dir),
        "output_dir": str(output_root),
        "sample_count": len(samples),
        "success_count": success_count,
        "failure_count": len(samples) - success_count,
        "dominant_counts": dominant_counts,
        "rows": rows,
    }
    (output_root / "summary.json").write_text(json.dumps(summary_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_summary_csv(rows, output_root / "summary.csv")
    return summary_payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch extract MOL micro-expression features")
    parser.add_argument("--root-dir", required=True)
    parser.add_argument("--output-dir", default="reports/mol_micro_batch")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--timeout-seconds", type=int, default=60)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    extractor = MOLMicroExpressionExtractor(device=args.device, timeout_seconds=args.timeout_seconds)
    summary = run_batch_extraction(
        root_dir=args.root_dir,
        output_dir=args.output_dir,
        extractor=extractor,
        limit=args.limit,
        resume=args.resume,
    )
    print(
        f"samples={summary['sample_count']} "
        f"success={summary['success_count']} "
        f"failure={summary['failure_count']} "
        f"output={summary['output_dir']}"
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 8: Run Task 1 tests**

Run:

```powershell
python -m pytest tests/test_micro_expression_batch_pipeline.py -q
```

Expected: PASS.

- [ ] **Step 9: Run real batch extraction with a small limit**

Run:

```powershell
python scripts/extract_mol_micro_expression_batch.py --root-dir third_party/MOL/data/SAMM_data_3 --output-dir reports/mol_micro_batch_samm_limit6 --limit 6 --resume --device cpu --timeout-seconds 60
```

Expected: exits 0, prints `samples=6`, and writes:

- `reports/mol_micro_batch_samm_limit6/summary.json`
- `reports/mol_micro_batch_samm_limit6/summary.csv`

---

### Task 2: 在线报告 API 结构化微表情摘要

**Files:**
- Create: `app/services/micro_expression_summary_service.py`
- Modify: `app/schemas/multimodal_personality.py`
- Modify: `app/api/multimodal_personality.py`
- Modify: `app/api/chat.py`
- Test: `tests/test_big_five_reports_api.py`
- Test: `tests/test_chat_api.py`

- [ ] **Step 1: Write failing service test for summary loading**

Append to `tests/test_big_five_reports_api.py`:

```python
from app.services.micro_expression_summary_service import load_micro_expression_summary_from_artifacts


def test_load_micro_expression_summary_from_artifacts_returns_display_payload(tmp_path):
    micro_path = tmp_path / "micro_expression_feature.json"
    micro_path.write_text(
        json.dumps(
            {
                "success": True,
                "summary": {"dominant_expression": "positive", "dominant_label_zh": "积极", "confidence": 0.72},
                "summary_text_zh": "主导微表情为积极，置信度约 72/100。",
                "interpretation_boundary_zh": "微表情只作为短时面部线索，不能直接代表稳定人格标签。",
                "probabilities": {"surprise": 0.1, "positive": 0.72, "negative": 0.18},
                "errors": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    summary = load_micro_expression_summary_from_artifacts({"micro_expression_feature_path": str(micro_path)})

    assert summary["available"] is True
    assert summary["dominant_label_zh"] == "积极"
    assert summary["confidence"] == 0.72
    assert "短时面部线索" in summary["interpretation_boundary_zh"]
```

- [ ] **Step 2: Run service summary test and verify RED**

Run:

```powershell
python -m pytest tests/test_big_five_reports_api.py::test_load_micro_expression_summary_from_artifacts_returns_display_payload -q
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement summary service**

Create `app/services/micro_expression_summary_service.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _empty_summary(reason: str) -> dict[str, Any]:
    return {
        "available": False,
        "dominant_expression": None,
        "dominant_label_zh": "暂无",
        "confidence": 0.0,
        "summary_text_zh": reason,
        "interpretation_boundary_zh": "微表情只作为短时面部线索，不能直接代表稳定人格标签。",
        "probabilities": {},
        "errors": [reason],
    }


def load_micro_expression_summary_from_artifacts(artifacts: dict | None) -> dict[str, Any] | None:
    artifacts = artifacts or {}
    path_value = artifacts.get("micro_expression_feature_path")
    if not path_value:
        return None
    try:
        payload = json.loads(Path(path_value).read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return _empty_summary(f"微表情结果读取失败：{exc}")

    summary = payload.get("summary") or {}
    if not payload.get("success", False):
        errors = payload.get("errors") or ["微表情模块未返回可用结果"]
        return _empty_summary("；".join(str(error) for error in errors[:2]))

    return {
        "available": True,
        "dominant_expression": summary.get("dominant_expression"),
        "dominant_label_zh": summary.get("dominant_label_zh") or "暂无",
        "confidence": float(summary.get("confidence") or 0.0),
        "summary_text_zh": payload.get("summary_text_zh") or "暂无可用微表情摘要。",
        "interpretation_boundary_zh": payload.get("interpretation_boundary_zh")
        or "微表情只作为短时面部线索，不能直接代表稳定人格标签。",
        "probabilities": payload.get("probabilities") or {},
        "errors": payload.get("errors") or [],
    }
```

- [ ] **Step 4: Run service summary test and verify GREEN**

Run:

```powershell
python -m pytest tests/test_big_five_reports_api.py::test_load_micro_expression_summary_from_artifacts_returns_display_payload -q
```

Expected: PASS.

- [ ] **Step 5: Write failing API response test**

Append to `tests/test_big_five_reports_api.py`:

```python
from app.api.multimodal_personality import _to_report_response


def test_report_response_includes_micro_expression_summary(tmp_path):
    micro_path = tmp_path / "micro_expression_feature.json"
    micro_path.write_text(
        json.dumps(
            {
                "success": True,
                "summary": {"dominant_expression": "negative", "dominant_label_zh": "消极", "confidence": 0.51},
                "summary_text_zh": "主导微表情为消极，置信度约 51/100。",
                "probabilities": {"surprise": 0.3, "positive": 0.18, "negative": 0.52},
                "errors": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    report = BigFivePersonalityReport(
        id=9,
        task_id="task-micro-response",
        user_id=1,
        title="视频人格报告",
        status="completed",
        message="done",
        original_filename="demo.mp4",
        video_path="demo.mp4",
        model_version="agtn-mtl-best-lr1e4-drop02",
        scores=BigFiveScores().model_dump(),
        artifacts={"micro_expression_feature_path": str(micro_path)},
        is_real_result=True,
    )

    response = _to_report_response(report)

    assert response.micro_expression_summary is not None
    assert response.micro_expression_summary["dominant_label_zh"] == "消极"
```

- [ ] **Step 6: Run API response test and verify RED**

Run:

```powershell
python -m pytest tests/test_big_five_reports_api.py::test_report_response_includes_micro_expression_summary -q
```

Expected: FAIL because schema has no `micro_expression_summary`.

- [ ] **Step 7: Add schema field and response injection**

Modify `app/schemas/multimodal_personality.py`:

```python
class MultimodalTaskResponse(BaseModel):
    ...
    micro_expression_summary: dict | None = None


class BigFiveReportResponse(BaseModel):
    ...
    micro_expression_summary: dict | None = None
```

Modify `app/api/multimodal_personality.py` imports:

```python
from app.services.micro_expression_summary_service import load_micro_expression_summary_from_artifacts
```

Modify `_to_response(task)`:

```python
micro_expression_summary=load_micro_expression_summary_from_artifacts(task.artifacts),
```

Modify `_to_report_response(report)`:

```python
micro_expression_summary=load_micro_expression_summary_from_artifacts(report.artifacts or {}),
```

- [ ] **Step 8: Run API response test and verify GREEN**

Run:

```powershell
python -m pytest tests/test_big_five_reports_api.py::test_report_response_includes_micro_expression_summary -q
```

Expected: PASS.

- [ ] **Step 9: Write failing chat context test**

Inspect `tests/test_chat_api.py` existing Big Five context tests, then add:

```python
def test_big_five_context_includes_micro_expression_summary(tmp_path):
    micro_path = tmp_path / "micro_expression_feature.json"
    micro_path.write_text(
        json.dumps(
            {
                "success": True,
                "summary": {"dominant_expression": "positive", "dominant_label_zh": "积极", "confidence": 0.64},
                "summary_text_zh": "主导微表情为积极，置信度约 64/100。",
                "errors": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    report = SimpleNamespace(
        scores={"openness": 0.6},
        interpretation_content=None,
        artifacts={"micro_expression_feature_path": str(micro_path)},
    )

    context = chat.get_big_five_context(report)

    assert "微表情线索" in context
    assert "积极" in context
    assert "短时面部线索" in context
```

Use the existing helper style in `tests/test_chat_api.py`; if function signature differs, adapt the object to the current test pattern.

- [ ] **Step 10: Run chat context test and verify RED**

Run:

```powershell
python -m pytest tests/test_chat_api.py::test_big_five_context_includes_micro_expression_summary -q
```

Expected: FAIL because chat context does not include micro-expression yet.

- [ ] **Step 11: Implement chat context injection**

Modify `app/api/chat.py`:

```python
from app.services.micro_expression_summary_service import load_micro_expression_summary_from_artifacts
```

Inside `get_big_five_context(report)`, after scores/interpretation content:

```python
micro_summary = load_micro_expression_summary_from_artifacts(getattr(report, "artifacts", {}) or {})
if micro_summary and micro_summary.get("available"):
    lines.extend(
        [
            "微表情线索：",
            micro_summary["summary_text_zh"],
            micro_summary["interpretation_boundary_zh"],
        ]
    )
```

- [ ] **Step 12: Run Task 2 tests**

Run:

```powershell
python -m pytest tests/test_big_five_reports_api.py tests/test_chat_api.py -q
```

Expected: PASS.

---

### Task 3: 小样本微表情消融 Runner

**Files:**
- Create: `scripts/run_micro_expression_ablation.py`
- Test: `tests/test_micro_expression_ablation_runner.py`

- [ ] **Step 1: Write failing test for ablation command planning**

Create `tests/test_micro_expression_ablation_runner.py`:

```python
from __future__ import annotations

from scripts.run_micro_expression_ablation import build_ablation_plan


def test_build_ablation_plan_creates_two_runs(tmp_path) -> None:
    plan = build_ablation_plan(
        train_bundle_dir=tmp_path / "train",
        val_bundle_dir=tmp_path / "val",
        output_dir=tmp_path / "ablation",
        epochs=1,
        batch_size=2,
        device="cpu",
        hidden_dim=16,
    )

    assert [run["name"] for run in plan["runs"]] == ["no_micro", "with_micro"]
    assert plan["runs"][0]["model_kwargs"]["use_micro_expression_features"] is False
    assert plan["runs"][1]["model_kwargs"]["use_micro_expression_features"] is True
```

- [ ] **Step 2: Run plan test and verify RED**

Run:

```powershell
python -m pytest tests/test_micro_expression_ablation_runner.py::test_build_ablation_plan_creates_two_runs -q
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement ablation plan function**

Create `scripts/run_micro_expression_ablation.py`:

```python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from multimodal_personality.training import discover_bundle_paths, evaluate_bundle_paths, load_checkpoint_model, train_baseline_model
from multimodal_personality.models.feature_bundle import MICRO_EXPRESSION_DIM


def build_ablation_plan(
    *,
    train_bundle_dir: str | Path,
    val_bundle_dir: str | Path,
    output_dir: str | Path,
    epochs: int,
    batch_size: int,
    device: str,
    hidden_dim: int,
) -> dict[str, object]:
    output_root = Path(output_dir)
    base_kwargs = {"hidden_dim": hidden_dim, "attention_heads": 1, "dropout": 0.1}
    return {
        "train_bundle_dir": str(train_bundle_dir),
        "val_bundle_dir": str(val_bundle_dir),
        "output_dir": str(output_root),
        "epochs": epochs,
        "batch_size": batch_size,
        "device": device,
        "runs": [
            {
                "name": "no_micro",
                "checkpoint": str(output_root / "no_micro.pt"),
                "summary": str(output_root / "no_micro.summary.json"),
                "model_kwargs": {**base_kwargs, "use_micro_expression_features": False},
            },
            {
                "name": "with_micro",
                "checkpoint": str(output_root / "with_micro.pt"),
                "summary": str(output_root / "with_micro.summary.json"),
                "model_kwargs": {
                    **base_kwargs,
                    "use_micro_expression_features": True,
                    "micro_expression_dim": MICRO_EXPRESSION_DIM,
                },
            },
        ],
    }
```

- [ ] **Step 4: Run plan test and verify GREEN**

Run:

```powershell
python -m pytest tests/test_micro_expression_ablation_runner.py::test_build_ablation_plan_creates_two_runs -q
```

Expected: PASS.

- [ ] **Step 5: Write failing integration test with monkeypatched training**

Append to `tests/test_micro_expression_ablation_runner.py`:

```python
from types import SimpleNamespace

import scripts.run_micro_expression_ablation as ablation


def test_run_ablation_writes_summary(tmp_path, monkeypatch) -> None:
    train_dir = tmp_path / "train"
    val_dir = tmp_path / "val"
    train_dir.mkdir()
    val_dir.mkdir()
    (train_dir / "train-a.json").write_text("{}", encoding="utf-8")
    (val_dir / "val-a.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        ablation,
        "discover_bundle_paths",
        lambda path: SimpleNamespace(bundle_paths=[path / "x.json"], missing_bundle_names=[]),
    )
    monkeypatch.setattr(
        ablation,
        "train_baseline_model",
        lambda *args, **kwargs: SimpleNamespace(checkpoint_path=kwargs["checkpoint_path"], best_epoch=1, best_loss=0.1, history=[]),
    )
    monkeypatch.setattr(
        ablation,
        "load_checkpoint_model",
        lambda checkpoint_path, device: SimpleNamespace(model=object(), checkpoint={"model_kwargs": {}}, device="cpu"),
    )
    monkeypatch.setattr(
        ablation,
        "evaluate_bundle_paths",
        lambda *args, **kwargs: SimpleNamespace(sample_count=1, mean_loss=0.1, metrics={"mae": 0.2}, predictions=[]),
    )

    summary = ablation.run_ablation(
        train_bundle_dir=train_dir,
        val_bundle_dir=val_dir,
        output_dir=tmp_path / "ablation",
        epochs=1,
        batch_size=1,
        device="cpu",
        hidden_dim=16,
    )

    assert summary["runs"][0]["name"] == "no_micro"
    assert summary["runs"][1]["name"] == "with_micro"
    assert (tmp_path / "ablation" / "ablation_summary.json").exists()
```

- [ ] **Step 6: Run integration test and verify RED**

Run:

```powershell
python -m pytest tests/test_micro_expression_ablation_runner.py::test_run_ablation_writes_summary -q
```

Expected: FAIL with missing `run_ablation`.

- [ ] **Step 7: Implement run_ablation and CLI**

Append to `scripts/run_micro_expression_ablation.py`:

```python
def _evaluation_payload(result) -> dict[str, object]:
    return {
        "sample_count": result.sample_count,
        "mean_loss": result.mean_loss,
        "metrics": result.metrics,
    }


def run_ablation(
    *,
    train_bundle_dir: str | Path,
    val_bundle_dir: str | Path,
    output_dir: str | Path,
    epochs: int,
    batch_size: int,
    device: str,
    hidden_dim: int,
) -> dict[str, object]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    plan = build_ablation_plan(
        train_bundle_dir=train_bundle_dir,
        val_bundle_dir=val_bundle_dir,
        output_dir=output_root,
        epochs=epochs,
        batch_size=batch_size,
        device=device,
        hidden_dim=hidden_dim,
    )
    train_resolution = discover_bundle_paths(train_bundle_dir)
    val_resolution = discover_bundle_paths(val_bundle_dir)
    run_summaries = []
    for run in plan["runs"]:
        train_result = train_baseline_model(
            train_resolution.bundle_paths,
            checkpoint_path=run["checkpoint"],
            val_bundle_paths=val_resolution.bundle_paths,
            epochs=epochs,
            batch_size=batch_size,
            learning_rate=1e-3,
            device=device,
            text_seq_len=13,
            model_kwargs=run["model_kwargs"],
        )
        loaded = load_checkpoint_model(run["checkpoint"], device=device)
        eval_result = evaluate_bundle_paths(
            loaded.model,
            val_resolution.bundle_paths,
            device=loaded.device,
            batch_size=batch_size,
            text_seq_len=13,
            fill_missing_modalities=True,
            require_labels=True,
        )
        run_summaries.append(
            {
                "name": run["name"],
                "checkpoint": str(train_result.checkpoint_path),
                "best_epoch": train_result.best_epoch,
                "best_loss": train_result.best_loss,
                "evaluation": _evaluation_payload(eval_result),
                "model_kwargs": run["model_kwargs"],
            }
        )
    summary = {
        **{key: value for key, value in plan.items() if key != "runs"},
        "train_bundle_count": len(train_resolution.bundle_paths),
        "val_bundle_count": len(val_resolution.bundle_paths),
        "runs": run_summaries,
    }
    summary_path = output_root / "ablation_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run no-micro vs with-micro AGTN-MTL ablation")
    parser.add_argument("--train-bundle-dir", required=True)
    parser.add_argument("--val-bundle-dir", required=True)
    parser.add_argument("--output-dir", default="reports/micro_expression_ablation")
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--hidden-dim", type=int, default=16)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = run_ablation(
        train_bundle_dir=args.train_bundle_dir,
        val_bundle_dir=args.val_bundle_dir,
        output_dir=args.output_dir,
        epochs=args.epochs,
        batch_size=args.batch_size,
        device=args.device,
        hidden_dim=args.hidden_dim,
    )
    for run in summary["runs"]:
        metrics = run["evaluation"]["metrics"]
        print(f"{run['name']} best_loss={run['best_loss']:.6f} mae={metrics.get('mae', 0.0):.6f}")
    print(f"saved={Path(args.output_dir) / 'ablation_summary.json'}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 8: Run ablation runner tests**

Run:

```powershell
python -m pytest tests/test_micro_expression_ablation_runner.py -q
```

Expected: PASS.

- [ ] **Step 9: Run a synthetic real mini ablation**

If there are no ready CFI bundles with labels, create a tiny temporary bundle set using existing `tests/test_multimodal_training_pipeline.py` helper style manually in a short script, or reuse existing bundle dirs if present. Use:

```powershell
python scripts/run_micro_expression_ablation.py --train-bundle-dir <small_train_bundle_dir> --val-bundle-dir <small_val_bundle_dir> --output-dir reports/micro_expression_ablation_smoke --epochs 1 --batch-size 1 --device cpu --hidden-dim 16
```

Expected: exits 0 and writes `reports/micro_expression_ablation_smoke/ablation_summary.json`.

---

### Task 4: 中文实验报告生成器

**Files:**
- Create: `scripts/write_micro_expression_experiment_report.py`
- Create or Update: `reports/MOL微表情组会实验总结.md`
- Test: `tests/test_micro_expression_ablation_runner.py`

- [ ] **Step 1: Write failing test for report rendering**

Append to `tests/test_micro_expression_ablation_runner.py`:

```python
from scripts.write_micro_expression_experiment_report import render_report_markdown


def test_render_report_markdown_includes_batch_and_ablation_results() -> None:
    batch_summary = {
        "sample_count": 6,
        "success_count": 6,
        "failure_count": 0,
        "dominant_counts": {"negative": 4, "positive": 2},
    }
    ablation_summary = {
        "runs": [
            {"name": "no_micro", "best_loss": 0.2, "evaluation": {"metrics": {"mae": 0.3, "pcc": 0.4}}},
            {"name": "with_micro", "best_loss": 0.18, "evaluation": {"metrics": {"mae": 0.28, "pcc": 0.45}}},
        ]
    }

    markdown = render_report_markdown(batch_summary=batch_summary, ablation_summary=ablation_summary)

    assert "# MOL 微表情组会实验总结" in markdown
    assert "批量提取" in markdown
    assert "no_micro" in markdown
    assert "with_micro" in markdown
    assert "解释边界" in markdown
```

- [ ] **Step 2: Run report rendering test and verify RED**

Run:

```powershell
python -m pytest tests/test_micro_expression_ablation_runner.py::test_render_report_markdown_includes_batch_and_ablation_results -q
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement report generator**

Create `scripts/write_micro_expression_experiment_report.py`:

```python
from __future__ import annotations

import argparse
import json
from pathlib import Path


def _load_json(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _metric(run: dict, key: str) -> str:
    value = ((run.get("evaluation") or {}).get("metrics") or {}).get(key)
    if value is None:
        return "暂无"
    return f"{float(value):.4f}"


def render_report_markdown(*, batch_summary: dict, ablation_summary: dict) -> str:
    lines = [
        "# MOL 微表情组会实验总结",
        "",
        "## 1. 当前接入状态",
        "",
        "- MOL 已作为可选微表情模块接入在线多模态服务。",
        "- 在线 artifact 会保存 `micro_expression_feature.json`。",
        "- 大五报告和 API response 可以读取结构化微表情摘要。",
        "",
        "## 2. 批量提取结果",
        "",
        f"- 样本数：{batch_summary.get('sample_count', 0)}",
        f"- 成功数：{batch_summary.get('success_count', 0)}",
        f"- 失败数：{batch_summary.get('failure_count', 0)}",
        f"- 主导微表情分布：{batch_summary.get('dominant_counts', {})}",
        "",
        "## 3. 小样本消融结果",
        "",
        "| Run | Best Loss | MAE | PCC |",
        "| --- | ---: | ---: | ---: |",
    ]
    for run in ablation_summary.get("runs", []):
        lines.append(f"| {run.get('name')} | {float(run.get('best_loss', 0.0)):.4f} | {_metric(run, 'mae')} | {_metric(run, 'pcc')} |")
    lines.extend(
        [
            "",
            "## 4. 初步结论",
            "",
            "- 这次结果用于验证接入链路和消融入口，不作为最终结论。",
            "- 若 with_micro 在 MAE/PCC 上优于 no_micro，可作为后续扩大样本实验的动机。",
            "- 若指标差异不明显，也可以说明微表情作为短时线索需要更强的数据对齐或更大样本。",
            "",
            "## 5. 解释边界",
            "",
            "微表情只作为短时面部线索，不能直接代表稳定人格标签；最终人格解释仍以多模态主模型和报告边界为准。",
        ]
    )
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write a Chinese MOL micro-expression experiment report")
    parser.add_argument("--batch-summary", required=True)
    parser.add_argument("--ablation-summary", required=True)
    parser.add_argument("--output", default="reports/MOL微表情组会实验总结.md")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    markdown = render_report_markdown(
        batch_summary=_load_json(args.batch_summary),
        ablation_summary=_load_json(args.ablation_summary),
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")
    print(f"saved={output_path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run report rendering test and verify GREEN**

Run:

```powershell
python -m pytest tests/test_micro_expression_ablation_runner.py::test_render_report_markdown_includes_batch_and_ablation_results -q
```

Expected: PASS.

- [ ] **Step 5: Generate real report from produced artifacts**

After Task 1 and Task 3 real runs exist, run:

```powershell
python scripts/write_micro_expression_experiment_report.py --batch-summary reports/mol_micro_batch_samm_limit6/summary.json --ablation-summary reports/micro_expression_ablation_smoke/ablation_summary.json --output reports/MOL微表情组会实验总结.md
```

Expected: writes `reports/MOL微表情组会实验总结.md`.

---

### Task 5: Final Verification and 5-Hour Deliverable Checklist

**Files:**
- Modify if needed: `multimodal_personality/README.md`
- No new tests unless a verification fails.

- [ ] **Step 1: Run focused tests**

Run:

```powershell
python -m pytest tests/test_micro_expression_batch_pipeline.py tests/test_micro_expression_ablation_runner.py tests/test_micro_expression_demo_scripts.py tests/test_big_five_reports_api.py tests/test_chat_api.py -q
```

Expected: PASS.

- [ ] **Step 2: Run full test suite**

Run:

```powershell
python -m pytest tests -q
```

Expected: PASS.

- [ ] **Step 3: Real MOL demo command**

Run:

```powershell
python scripts/run_micro_expression_demo.py --frames-dir third_party/MOL/data/SAMM_data_3/positive/007_6_1 --device cpu --timeout-seconds 60
```

Expected output includes:

```text
微表情提取成功
特征维度：8 维
```

- [ ] **Step 4: Real batch extraction check**

Run:

```powershell
python scripts/extract_mol_micro_expression_batch.py --root-dir third_party/MOL/data/SAMM_data_3 --output-dir reports/mol_micro_batch_samm_limit6 --limit 6 --resume --device cpu --timeout-seconds 60
```

Expected output includes:

```text
samples=6
```

- [ ] **Step 5: Verify generated report exists**

Run:

```powershell
Test-Path reports/MOL微表情组会实验总结.md
```

Expected: `True`.

- [ ] **Step 6: Inspect git changes**

Run:

```powershell
git status --short
git diff --stat
```

Expected:

- Code/test/docs changes are limited to this MOL micro-expression plan and existing micro-expression integration.
- `third_party/` may remain untracked from prior MOL work; do not stage or delete it unless explicitly requested.
- Generated `reports/` artifacts can remain local unless the user asks to preserve them in git.

---

## Acceptance Criteria

- [ ] At least 6 real SAMM frame folders have MOL micro-expression JSON outputs.
- [ ] `summary.json` and `summary.csv` exist for the batch run.
- [ ] Report/task API response can expose `micro_expression_summary`.
- [ ] Chat Big Five context can mention micro-expression as a bounded short-term clue.
- [ ] no_micro / with_micro ablation runner exists and has tests.
- [ ] A Chinese Markdown experiment report can be generated from produced artifacts.
- [ ] Full test suite passes.
- [ ] No MOL weight/data files are modified.
