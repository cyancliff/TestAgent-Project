# 多模态人格子系统说明

更新时间：2026-04-20

这个目录负责“视频多模态人格预测”的离线工程闭环。它和在线 ATMR 主系统并列存在，但当前主要作用是：

1. 完成数据预处理与特征提取
2. 跑通 AGTN-MTL baseline
3. 产出真实 checkpoint 与真实 Big Five 分数
4. 为后续在线接入提供稳定输入输出契约

## 1. 当前真实状态

当前仓库里，多模态部分已经不是单纯的预处理脚手架，而是已经具备以下能力：

- CFI-V2 manifest 构建
- 视频抽帧、音频提取、Whisper 转写
- CLIP 视觉特征与文本特征提取
- wav2clip 音频特征提取
- feature bundle 组装
- AGTN-MTL baseline 训练、评估、推理
- 可恢复的全量长任务 runner

还没有完成的部分：

- 在线服务仍返回 `scaffold-v1` 占位分数
- `bg_features` 仍未实现
- 多模态结果尚未正式接入主系统报告页

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

截至 2026-04-20，本仓库已经在下列环境上验证：

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

## 7. 关键脚本说明

### 数据与特征

- `scripts/build_cfi_v2_manifest.py`
- `scripts/preprocess_cfi_v2_from_manifest.py`
- `scripts/build_clip_feature_jobs.py`
- `scripts/extract_clip_features.py`
- `scripts/extract_wav2clip_features.py`
- `scripts/build_multimodal_feature_bundles.py`

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

### 未完成

- 在线 `run` 接口接入真实 checkpoint
- 报告页展示 Big Five 结果
- `bg_features`
- 更系统的调参与论文级对比实验

## 9. 与在线系统的关系

当前多模态模块和主系统之间的关系是：

- 主系统已经有接口和 service 边界
- 离线模块已经能产出真实 checkpoint 和真实分数
- 但二者还没有正式合并到同一条在线推理链上

所以现阶段最合理的推进顺序是：

1. 跑完全量 baseline
2. 固定 checkpoint
3. 再接回 `app/services/multimodal_personality_service.py`

## 10. 运行中的注意事项

如果正在跑全量长任务：

- 查看 `reports/full_multimodal_pipeline/stderr.log`
- 不要删除 `uploads/multimodal_personality/artifacts`
- 不要删除 `reports/full_multimodal_pipeline`
- 不要随意关闭黑色 `python.exe` 宿主窗口
