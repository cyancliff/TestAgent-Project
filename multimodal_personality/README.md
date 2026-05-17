# 多模态人格子系统说明

更新时间：2026-04-27

这个目录负责“视频多模态人格预测”的离线工程闭环。它和在线 ATMR 主系统并列存在，但当前主要作用是：

1. 完成数据预处理与特征提取
2. 跑通 AGTN-MTL baseline
3. 产出真实 checkpoint 与真实 Big Five 分数
4. 为在线主系统提供可调用的真实推理入口，并沉淀为独立的大五人格报告

## 1. 当前真实状态

当前仓库里，多模态部分已经不是单纯的预处理脚手架，而是已经具备以下能力：

- CFI-V2 manifest 构建
- 视频抽帧、音频提取、Whisper 转写
- CLIP 视觉特征与文本特征提取
- wav2clip 音频特征提取
- feature bundle 组装
- AGTN-MTL baseline 训练、评估、推理
- 可恢复的全量长任务 runner
- 在线 `run` 流程可调用真实 checkpoint，并保留失败回退
- 在线主系统已经能把真实完成的结果落成“大五人格”报告，进入历史页、报告页和聊天上下文
- 大五人格报告的 AI 解读已经接入独立 Big Five RAG / PageIndex 知识库

还没有完成的部分：

- `bg_features` 已有工程版 256 维实现，后续可基于新 bundle 重新训练并做对照实验
- `PCC / CCC / R²` 等论文级评价指标已经接入评估与结果汇总脚本
- 后台任务体系和数据库迁移仍可继续正规化

## 2. 目录结构

```text
multimodal_personality/
  checkpoints/             模型权重
  configs/                 数据集配置
  data/                    CFI-V2 数据与中间文件
  docs/                    多模态专题文档
  evaluation/              评估占位目录
  feature_extractors/      CLIP / wav2clip 提取器
  inference/               推理管线
  models/                  AGTN 层、AGTN-MTL、feature bundle
  preprocessing/           数据预处理
  training/                baseline 训练逻辑
  README.md
```

## 3. 已验证环境

截至 2026-04-25，本仓库已经在下列环境上验证：

- Windows + PowerShell
- Python `3.14`
- `ffmpeg` 可用
- `torch 2.11.0+cu126`
- `torchvision 0.26.0+cu126`
- `torchaudio 2.11.0+cu126`
- `torch.cuda.is_available() == True`
- GPU：`NVIDIA GeForce RTX 4060 Laptop GPU`

建议安装：

```powershell
python -m pip install -r requirements_multimodal.txt
```

## 4. 数据准备

CFI-V2 的目录规范见：

- `multimodal_personality/data/cfi_v2/README.md`

manifest 构建命令：

```powershell
python scripts/build_cfi_v2_manifest.py --config multimodal_personality/configs/cfi_v2.example.yaml --phase all
```

这一步会生成：

- `train_manifest.json`
- `val_manifest.json`
- `test_manifest.json`

## 5. 推荐工作流

### 5.1 先跑最小闭环

推荐从 `train 100 / val 20` 开始。

```powershell
python scripts/preprocess_cfi_v2_from_manifest.py --manifest multimodal_personality/data/cfi_v2/manifests/train_manifest.json --limit 100
python scripts/preprocess_cfi_v2_from_manifest.py --manifest multimodal_personality/data/cfi_v2/manifests/val_manifest.json --limit 20

python scripts/build_clip_feature_jobs.py --manifest multimodal_personality/data/cfi_v2/manifests/train_manifest.json

python scripts/extract_clip_features.py --jobs multimodal_personality/data/cfi_v2/train_feature_jobs.json --device cuda
python scripts/extract_wav2clip_features.py --jobs multimodal_personality/data/cfi_v2/train_feature_jobs.json

python scripts/build_multimodal_feature_bundles.py --manifest multimodal_personality/data/cfi_v2/manifests/train_manifest.json --limit 100
python scripts/build_multimodal_feature_bundles.py --manifest multimodal_personality/data/cfi_v2/manifests/val_manifest.json --limit 20

python scripts/train_agtn_mtl.py --train-manifest multimodal_personality/data/cfi_v2/manifests/train_manifest.json --val-manifest multimodal_personality/data/cfi_v2/manifests/val_manifest.json --train-limit 100 --val-limit 20 --device cuda --checkpoint multimodal_personality/checkpoints/agtn_mtl_baseline.pt
python scripts/eval_agtn_mtl.py --checkpoint multimodal_personality/checkpoints/agtn_mtl_baseline.pt --bundle-dir <val_bundle_dir> --device cuda
```

### 5.2 再跑全量长任务

```powershell
python scripts/run_full_multimodal_pipeline.py --train-device cuda --clip-device cuda
```

这个脚本会自动串起：

1. 缺失样本预处理
2. 特征任务构建
3. CLIP 特征提取
4. wav2clip 特征提取
5. bundle 生成
6. baseline 训练
7. `val / test` 评估

而且它支持断点恢复。

## 6. 当前已得到的真实结果

### 小样本验证

1. `train 20 / val 5`
   - `mse=0.004983`
   - `mae=0.057872`
2. `train 100 / val 20`
   - `mse=0.016520`
   - `mae=0.100234`

这些结果说明：

- 工程链路已经成立
- 模型可以输出真实分数
- 但当前仍属于 baseline 阶段，不应直接视作论文最终结果

### 产物目录示例

- `reports/multimodal_live_run/`
- `reports/multimodal_live_run_100/`
- `reports/full_multimodal_pipeline/`
- `reports/night_lr1e4_drop02/`
- `reports/online_multimodal_smoke_20260425/`

### 全量与调参结果

当前在线默认 checkpoint 为：

- `reports/night_lr1e4_drop02/agtn_mtl_lr1e4_drop02.pt`

该版本在全量测试集上的结果为：

- `test mse=0.011543`
- `test mae=0.086074`
- `test pcc=0.7062`
- `test ccc=0.6327`
- `test r²=0.4881`

在线真实推理 smoke 已通过，归档位置：

- `reports/online_multimodal_smoke_20260425/smoke_result.json`

## 7. 关键脚本说明

### 数据与特征

- `scripts/build_cfi_v2_manifest.py`
- `scripts/preprocess_cfi_v2_from_manifest.py`
- `scripts/build_clip_feature_jobs.py`
- `scripts/extract_clip_features.py`
- `scripts/extract_wav2clip_features.py`
- `scripts/build_multimodal_feature_bundles.py`
- MOL 微表情接入与消融说明：`docs/MOL微表情接入说明.md`

### 训练与评估

- `scripts/train_agtn_mtl.py`
- `scripts/eval_agtn_mtl.py`
- `scripts/infer_agtn_mtl.py`
- `scripts/run_full_multimodal_pipeline.py`

## 8. 当前工程边界

### 已完成

- 离线 baseline 闭环
- 小样本真实训练结果
- 全量 runner
- 当前环境 GPU 可用
- 全量 baseline 与一轮调参结果
- 在线真实 checkpoint 推理 smoke 验证
- 大五人格报告接入主系统历史页、详情页和聊天上下文
- 大五人格 RAG / PageIndex 知识库与 AI 解读链路

### 未完成

- 使用新 `bg_features` 重新生成 bundle、重训并做对照实验
- 更系统的随机种子、单模态/多模态消融实验
- 更正式的后台任务队列与数据库迁移治理

## 9. 与在线系统的关系

当前多模态模块和主系统之间的关系是：

- 主系统已经有接口和 service 边界
- 离线模块已经能产出真实 checkpoint 和真实分数
- 在线服务已经能调用真实 checkpoint 返回 Big Five 分数
- 大五人格结果已经作为独立报告进入主系统报告页、历史记录和聊天会话上下文

所以现阶段最合理的推进顺序是：

1. 基于已补齐的论文级评价指标整理实验表格
2. 继续打磨大五报告解释质量和演示文案
3. 视时间用新 `bg_features` 重新训练一版对照模型

## 10. 运行中的注意事项

如果正在跑全量长任务：

- 查看 `reports/full_multimodal_pipeline/stderr.log`
- 不要删除 `uploads/multimodal_personality/artifacts`
- 不要删除 `reports/full_multimodal_pipeline`
- 不要随意关闭黑色 `python.exe` 宿主窗口
