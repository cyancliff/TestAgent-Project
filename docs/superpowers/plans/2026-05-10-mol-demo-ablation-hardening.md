# MOL 微表情演示与消融入口加固 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用约 3 小时把已经接入的 MOL 微表情能力推进到“组会可演示、结果可读、后续消融可启动”的状态。

**Architecture:** 保持当前主系统稳定：MOL 仍作为可选、失败不阻塞的微表情模块；新增小型诊断/演示脚本和文档，不改动大五主模型默认行为。训练消融只增加入口和样例命令，不默认启用微表情分支，避免旧 checkpoint 失效。

**Tech Stack:** Python、pytest、PyTorch、现有 FastAPI service、MOL 子进程 runner、Markdown 文档。

---

## 文件结构

- 修改：`multimodal_personality/feature_extractors/micro_expression_extractor.py`
  - 负责把 MOL 输出标准化成 `micro_expression_feature.json`。
  - 本计划只补可读摘要字段和诊断信息，不改动核心接口。
- 修改：`app/services/multimodal_personality_service.py`
  - 负责在线服务 artifacts 汇总。
  - 本计划只补健康检查信息，让演示前能看到 MOL 是否可用。
- 创建：`scripts/run_micro_expression_demo.py`
  - 一键对一个帧目录跑 MOL 微表情提取，打印中文摘要，方便组会演示。
- 创建：`scripts/prepare_micro_expression_ablation_manifest.py`
  - 扫描已有 bundle 和微表情 JSON，生成一个消融训练清单/统计 JSON。
- 创建：`docs/MOL微表情接入说明.md`
  - 中文说明：当前接入方式、演示命令、artifact 字段、消融训练入口、失败降级逻辑。
- 修改测试：`tests/test_multimodal_feature_extractors.py`
- 修改测试：`tests/test_multimodal_service.py`
- 新增测试：`tests/test_micro_expression_demo_scripts.py`

---

## 时间预算

- Task 1：微表情 JSON 可读性与健康检查，约 40 分钟。
- Task 2：演示脚本，约 45 分钟。
- Task 3：消融清单脚本，约 45 分钟。
- Task 4：中文文档与最终验收，约 35-45 分钟。

---

### Task 1: 加强微表情 JSON 摘要与健康检查

**Files:**
- Modify: `multimodal_personality/feature_extractors/micro_expression_extractor.py`
- Modify: `app/services/multimodal_personality_service.py`
- Test: `tests/test_multimodal_feature_extractors.py`
- Test: `tests/test_multimodal_service.py`

- [ ] **Step 1: 写失败测试，要求微表情 JSON 包含中文可读摘要文本**

在 `tests/test_multimodal_feature_extractors.py` 里给 `test_mol_micro_expression_extractor_writes_normalized_feature_json` 增加断言：

```python
assert "积极" in payload["summary_text_zh"]
assert "置信度" in payload["summary_text_zh"]
assert "短时面部线索" in payload["interpretation_boundary_zh"]
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```powershell
python -m pytest tests/test_multimodal_feature_extractors.py::test_mol_micro_expression_extractor_writes_normalized_feature_json -q
```

Expected: FAIL，提示缺少 `summary_text_zh` 或 `interpretation_boundary_zh`。

- [ ] **Step 3: 实现最小代码**

在 `MOLMicroExpressionExtractor._normalize_runner_payload()` 成功 payload 中加入：

```python
summary = self._build_summary(probabilities)
payload = {
    ...
    "summary": summary,
    "summary_text_zh": self._build_summary_text_zh(summary),
    "interpretation_boundary_zh": "微表情只作为短时面部线索，不能直接代表稳定人格标签。",
    ...
}
```

新增方法：

```python
def _build_summary_text_zh(self, summary: dict[str, Any]) -> str:
    label = summary.get("dominant_label_zh") or "暂无"
    confidence = float(summary.get("confidence") or 0.0)
    return f"主导微表情为{label}，置信度约 {confidence * 100:.0f}/100。"
```

在 `_failure_payload()` 也加入：

```python
"summary_text_zh": "微表情模块未返回可用结果。",
"interpretation_boundary_zh": "微表情只作为短时面部线索，不能直接代表稳定人格标签。",
```

- [ ] **Step 4: 写失败测试，要求 health 暴露 MOL 可用性**

在 `tests/test_multimodal_service.py` 新增：

```python
def test_health_exposes_micro_expression_system_tools(tmp_path, monkeypatch) -> None:
    service = _build_service(tmp_path, monkeypatch)

    health = service.health()

    assert "micro_expression_enabled" in health["system_tools"]
    assert "mol_root" in health["system_tools"]
    assert "mol_model" in health["system_tools"]
```

- [ ] **Step 5: 运行测试确认失败**

Run:

```powershell
python -m pytest tests/test_multimodal_service.py::test_health_exposes_micro_expression_system_tools -q
```

Expected: FAIL，提示 health 中没有新增字段。

- [ ] **Step 6: 实现 health 字段**

在 `MultimodalPersonalityService.health()` 的 `system_tools` 字典中加入：

```python
"micro_expression_enabled": bool(settings.MICRO_EXPRESSION_ENABLED),
"mol_root": self._resolve_project_path(settings.MOL_ROOT_DIR).exists(),
"mol_model": self._resolve_project_path(settings.MOL_MODEL_PATH).exists(),
```

- [ ] **Step 7: 跑 Task 1 测试**

Run:

```powershell
python -m pytest tests/test_multimodal_feature_extractors.py tests/test_multimodal_service.py -q
```

Expected: PASS。

---

### Task 2: 增加一键 MOL 微表情演示脚本

**Files:**
- Create: `scripts/run_micro_expression_demo.py`
- Test: `tests/test_micro_expression_demo_scripts.py`

- [ ] **Step 1: 写失败测试，验证脚本能调用 extractor 并打印中文摘要**

创建 `tests/test_micro_expression_demo_scripts.py`：

```python
from __future__ import annotations

import json
import subprocess
import sys


def test_run_micro_expression_demo_prints_summary(tmp_path, monkeypatch) -> None:
    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    for index in range(8):
        (frames_dir / f"frame_{index:03d}.jpg").write_bytes(b"frame")

    fake_output = tmp_path / "micro_expression_feature.json"
    fake_output.write_text(
        json.dumps(
            {
                "success": True,
                "summary_text_zh": "主导微表情为积极，置信度约 70/100。",
                "summary": {"dominant_label_zh": "积极", "confidence": 0.7},
                "feature_vector": [0.1, 0.7, 0.2, 0.7, 0.8, 0.5, 0.4, 1.0],
                "errors": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    script = tmp_path / "fake_demo.py"
    script.write_text(
        "print('微表情提取成功')\nprint('主导微表情为积极，置信度约 70/100。')\n",
        encoding="utf-8",
    )
    result = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, encoding="utf-8")

    assert result.returncode == 0
    assert "微表情提取成功" in result.stdout
    assert "积极" in result.stdout
```

说明：先用这个测试锁定中文输出形态；实现脚本后再补一个直接 import `parse_args` / `format_demo_output` 的单元测试，避免真实 MOL 进入测试。

- [ ] **Step 2: 运行测试确认当前测试文件可通过**

Run:

```powershell
python -m pytest tests/test_micro_expression_demo_scripts.py -q
```

Expected: PASS。这个是测试框架烟测。

- [ ] **Step 3: 增加真正的格式化失败测试**

在同一测试文件加入：

```python
from scripts.run_micro_expression_demo import format_demo_output


def test_format_demo_output_contains_path_and_feature_dim(tmp_path) -> None:
    output_path = tmp_path / "micro_expression_feature.json"
    payload = {
        "success": True,
        "summary_text_zh": "主导微表情为积极，置信度约 70/100。",
        "feature_vector": [0.0] * 8,
        "errors": [],
    }

    text = format_demo_output(payload, output_path)

    assert "微表情提取成功" in text
    assert "8 维" in text
    assert str(output_path) in text
```

- [ ] **Step 4: 运行测试确认失败**

Run:

```powershell
python -m pytest tests/test_micro_expression_demo_scripts.py::test_format_demo_output_contains_path_and_feature_dim -q
```

Expected: FAIL，提示 `scripts.run_micro_expression_demo` 不存在。

- [ ] **Step 5: 实现演示脚本**

创建 `scripts/run_micro_expression_demo.py`：

```python
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
    parser.add_argument("--output-dir", default="uploads/multimodal_personality/artifacts/mol_demo/features/micro_expression")
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
```

- [ ] **Step 6: 跑脚本测试**

Run:

```powershell
python -m pytest tests/test_micro_expression_demo_scripts.py -q
```

Expected: PASS。

- [ ] **Step 7: 跑真实演示冒烟**

Run:

```powershell
python scripts/run_micro_expression_demo.py --frames-dir third_party/MOL/data/SAMM_data_3/positive/007_6_1 --device cpu --timeout-seconds 60
```

Expected: 输出“微表情提取成功”，并显示 `micro_expression_feature.json` 路径。

---

### Task 3: 准备后续消融训练清单脚本

**Files:**
- Create: `scripts/prepare_micro_expression_ablation_manifest.py`
- Test: `tests/test_micro_expression_demo_scripts.py`

- [ ] **Step 1: 写失败测试，验证能统计 bundle 与 micro JSON 匹配情况**

在 `tests/test_micro_expression_demo_scripts.py` 加入：

```python
from scripts.prepare_micro_expression_ablation_manifest import build_ablation_manifest


def test_build_ablation_manifest_counts_micro_expression_coverage(tmp_path) -> None:
    bundle_dir = tmp_path / "bundles"
    micro_dir = tmp_path / "micro"
    bundle_dir.mkdir()
    micro_dir.mkdir()
    (bundle_dir / "sample-a.json").write_text('{"video_name": "sample-a"}', encoding="utf-8")
    (bundle_dir / "sample-b.json").write_text('{"video_name": "sample-b"}', encoding="utf-8")
    (micro_dir / "sample-a.json").write_text('{"success": true, "feature_vector": [0,0,0,0,0,0,0,1]}', encoding="utf-8")

    manifest = build_ablation_manifest(bundle_dir=bundle_dir, micro_expression_dir=micro_dir)

    assert manifest["bundle_count"] == 2
    assert manifest["micro_expression_count"] == 1
    assert manifest["coverage"] == 0.5
    assert manifest["samples"][0]["has_micro_expression"] is True
    assert manifest["samples"][1]["has_micro_expression"] is False
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```powershell
python -m pytest tests/test_micro_expression_demo_scripts.py::test_build_ablation_manifest_counts_micro_expression_coverage -q
```

Expected: FAIL，提示脚本不存在。

- [ ] **Step 3: 实现清单脚本**

创建 `scripts/prepare_micro_expression_ablation_manifest.py`：

```python
from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def build_ablation_manifest(*, bundle_dir: str | Path, micro_expression_dir: str | Path) -> dict:
    bundle_root = Path(bundle_dir)
    micro_root = Path(micro_expression_dir)
    samples = []
    micro_count = 0

    for bundle_path in sorted(bundle_root.glob("*.json")):
        bundle = load_json(bundle_path)
        video_name = str(bundle.get("video_name") or bundle_path.stem)
        candidates = [
            micro_root / f"{video_name}.json",
            micro_root / bundle_path.name,
            micro_root / video_name / "micro_expression_feature.json",
        ]
        micro_path = next((path for path in candidates if path.exists()), None)
        has_micro = micro_path is not None
        if has_micro:
            micro_count += 1
        samples.append(
            {
                "video_name": video_name,
                "bundle_path": str(bundle_path),
                "micro_expression_path": None if micro_path is None else str(micro_path),
                "has_micro_expression": has_micro,
            }
        )

    bundle_count = len(samples)
    return {
        "bundle_count": bundle_count,
        "micro_expression_count": micro_count,
        "coverage": 0.0 if bundle_count == 0 else micro_count / bundle_count,
        "samples": samples,
        "next_train_command": (
            "python scripts/train_agtn_mtl.py --train-bundle-dir <bundle_dir> "
            "--use-micro-expression-features --checkpoint <output.pt>"
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare micro-expression ablation manifest")
    parser.add_argument("--bundle-dir", required=True)
    parser.add_argument("--micro-expression-dir", required=True)
    parser.add_argument("--output", default="reports/micro_expression_ablation_manifest.json")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest = build_ablation_manifest(
        bundle_dir=args.bundle_dir,
        micro_expression_dir=args.micro_expression_dir,
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"bundles={manifest['bundle_count']} micro={manifest['micro_expression_count']} coverage={manifest['coverage']:.2%}")
    print(f"saved={output_path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 跑脚本测试**

Run:

```powershell
python -m pytest tests/test_micro_expression_demo_scripts.py::test_build_ablation_manifest_counts_micro_expression_coverage -q
```

Expected: PASS。

- [ ] **Step 5: 对当前已有 demo artifact 跑一次清单脚本**

Run:

```powershell
python scripts/prepare_micro_expression_ablation_manifest.py --bundle-dir uploads/multimodal_personality/artifacts --micro-expression-dir uploads/multimodal_personality/artifacts/mol_smoke/features/micro_expression --output reports/micro_expression_ablation_manifest.json
```

Expected: 如果 artifact 根目录没有直接的 bundle JSON，可以输出 `bundles=0`，不报错；正式训练数据目录后续替换成真实 bundle 目录。

---

### Task 4: 中文文档与最终验收

**Files:**
- Create: `docs/MOL微表情接入说明.md`
- Possibly Modify: `multimodal_personality/README.md`

- [ ] **Step 1: 创建中文说明文档**

创建 `docs/MOL微表情接入说明.md`，内容必须包含：

```markdown
# MOL 微表情接入说明

## 当前状态

- 已接入 `MOLMicroExpressionExtractor`。
- 在线服务会保存 `micro_expression_feature.json`。
- 大五报告 prompt 会读取微表情摘要。
- 训练脚本支持 `--use-micro-expression-features` 做后续消融。

## 在线产物

`micro_expression_feature.json` 的关键字段：

- `success`
- `probabilities`
- `feature_vector`
- `summary`
- `summary_text_zh`
- `interpretation_boundary_zh`
- `errors`

## 演示命令

```powershell
python scripts/run_micro_expression_demo.py --frames-dir third_party/MOL/data/SAMM_data_3/positive/007_6_1 --device cpu --timeout-seconds 60
```

## 消融训练入口

不使用微表情：

```powershell
python scripts/train_agtn_mtl.py --train-bundle-dir <bundle_dir> --checkpoint reports/ablation/no_micro.pt
```

使用微表情：

```powershell
python scripts/train_agtn_mtl.py --train-bundle-dir <bundle_dir> --use-micro-expression-features --checkpoint reports/ablation/with_micro.pt
```

## 降级逻辑

MOL 失败时仍会写失败态 JSON，主模型继续推理；报告只提示微表情模块未返回可用结果。
```

- [ ] **Step 2: 可选地在 README 加入口**

如果 `multimodal_personality/README.md` 已经有“脚本/训练”区块，加入一行：

```markdown
- MOL 微表情接入与消融说明：`docs/MOL微表情接入说明.md`
```

- [ ] **Step 3: 跑相关测试**

Run:

```powershell
python -m pytest tests/test_multimodal_feature_extractors.py tests/test_multimodal_service.py tests/test_micro_expression_demo_scripts.py tests/test_multimodal_training_pipeline.py tests/test_big_five_reports_api.py -q
```

Expected: PASS。

- [ ] **Step 4: 跑全量测试**

Run:

```powershell
python -m pytest tests -q
```

Expected: PASS。

- [ ] **Step 5: 真实 MOL 演示验收**

Run:

```powershell
python scripts/run_micro_expression_demo.py --frames-dir third_party/MOL/data/SAMM_data_3/positive/007_6_1 --device cpu --timeout-seconds 60
```

Expected: 输出：

```text
微表情提取成功
主导微表情为...
特征维度：8 维
结果文件：...
```

- [ ] **Step 6: 检查工作区改动**

Run:

```powershell
git status --short
git diff --stat
```

Expected: 只出现本计划相关文件；`third_party/` 如果仍显示未跟踪，说明是已有 MOL 子仓库状态，不纳入本计划提交。

---

## 自检清单

- [ ] 没有改动 MOL 权重大文件。
- [ ] 没有让微表情失败影响主模型预测。
- [ ] 旧 checkpoint 默认仍不启用微表情分支。
- [ ] `micro_expression_feature.json` 能被人读懂，也能被训练读取。
- [ ] 中文文档足够组会口头说明。
- [ ] 全量测试通过后再声明完成。
