# TestAgent 部署与运行说明

更新时间：2026-04-27

这份文档专门解决一件事：把“在线 Web 服务部署”和“离线多模态训练/推理”彻底分开讲清楚。

当前仓库有两种常见运行方式：

1. 在线主系统：FastAPI + Vue + PostgreSQL，主要用于答题、ATMR 报告、大五人格报告、历史记录和 AI 咨询。
2. 离线多模态：围绕 CFI-V2 数据集的本地预处理、特征提取、训练和评估，更适合在带 GPU 的 Windows 开发机上长期运行。

## 1. 先明确边界

### 在线主系统负责什么

- 用户注册和登录
- ATMR 问卷答题主流程
- 自适应选题、异常作答检测
- 多智能体辩论与综合报告
- 历史记录与 AI 咨询
- 大五人格视频报告、Big Five RAG 解读和双报告聊天上下文

### 离线多模态负责什么

- CFI-V2 数据集 manifest 构建
- 视频抽帧、音频提取、Whisper 转写
- CLIP 和 wav2clip 特征提取
- AGTN-MTL baseline 训练、评估、推理
- 全量长任务的可恢复执行

### 当前最重要的现实限制

- 本地多模态环境已经可以使用真实 checkpoint 完成在线 service 推理，当前默认模型为 `agtn-mtl-best-lr1e4-drop02`。
- 真实完成的视频结果会在主系统中保存为独立“大五人格”报告，失败或 fallback 结果不会作为聊天依据。
- 大五人格 AI 解读依赖 DeepSeek 分析模型和本地 PageIndex 大五知识库；缺少模型密钥时报告仍可展示五维分数，但无法生成正式 AI 解读。
- 真实推理依赖 `ffmpeg / whisper / torch / transformers / PIL / wav2clip / librosa` 和本地 checkpoint，不等同于轻量 Web 部署环境。
- 如果在线部署环境没有安装多模态依赖或没有挂载 checkpoint，服务仍会通过回退机制返回占位分数；演示真实多模态结果时应使用已验证的本地 GPU 环境。

## 2. 在线主系统部署

### 2.1 推荐方式

推荐优先使用 Docker Compose 部署在线主系统。

当前默认容器包含：

- `db`：PostgreSQL 15
- `backend`：FastAPI
- `frontend`：Nginx + Vue 静态站点

默认访问链路：

```text
浏览器
  -> frontend:80
  -> /api 反向代理到 backend:8000
  -> backend 连接 db:5432
```

### 2.2 最低准备

- 已安装 Docker 与 Docker Compose v2
- 已复制 `.env.example` 为 `.env`
- 至少填写以下环境变量：
  - `DB_PASSWORD`
  - `SECRET_KEY`
  - `DEEPSEEK_API_KEY` 或其它你实际使用的模型密钥

### 2.3 启动命令

```powershell
Copy-Item .env.example .env
docker compose up -d --build
```

### 2.4 启动后检查

```powershell
docker compose ps
docker compose logs --tail=100 backend
docker compose logs --tail=50 frontend
```

至少确认：

- `db` 正常启动
- `backend` 和 `frontend` 都是 `Up`
- 后端日志里没有持续报错
- 浏览器能打开首页

### 2.5 可选：暴露 Swagger

默认情况下只暴露前端 `80` 端口，后端 `8000` 不直接对宿主机开放。

如果你需要直接访问 Swagger，请在 `docker-compose.yml` 的 `backend` 服务中增加：

```yaml
ports:
  - "8000:8000"
```

然后重新启动：

```powershell
docker compose up -d --build backend frontend
```

### 2.6 关于依赖文件

在线服务相关依赖有三层：

- `requirements_server.txt`：更轻的在线服务依赖
- `requirements_full.txt`：完整在线服务依赖
- `requirements_feature.txt`：题目特征向量相关依赖

如果你只是先把在线服务跑起来，而不是在服务器上生成题目特征向量，可以考虑把 `REQUIREMENTS_FILE` 改成 `requirements_server.txt`。

## 3. 本地多模态运行

### 3.1 适用场景

这条线不建议直接塞进 Docker 在线部署里。更适合：

- Windows 本地开发机
- 带 NVIDIA GPU
- 有较大磁盘空间
- 允许长时间跑预处理和特征提取

### 3.2 当前已经验证过的本地环境

截至 2026-04-25，本仓库已经在下面这套环境上验证通过：

- Windows + PowerShell
- Python `3.14`
- `ffmpeg` 已安装并可从 PATH 调用
- `torch 2.11.0+cu126`
- `torchvision 0.26.0+cu126`
- `torchaudio 2.11.0+cu126`
- `torch.cuda.is_available() == True`
- GPU：`NVIDIA GeForce RTX 4060 Laptop GPU`

这套环境支持同一份代码在 `cuda` 和 `cpu` 之间自动切换。

### 3.3 安装多模态依赖

```powershell
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements_multimodal.txt
```

此外还需要系统级依赖：

- `ffmpeg`

### 3.4 验证 GPU

```powershell
python -c "import torch; print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'no-gpu')"
```

### 3.5 跑最小闭环

推荐先跑 `100 / 20`，不要直接全量。

```powershell
python scripts/build_cfi_v2_manifest.py --config multimodal_personality/configs/cfi_v2.example.yaml --phase all

python scripts/preprocess_cfi_v2_from_manifest.py --manifest multimodal_personality/data/cfi_v2/manifests/train_manifest.json --limit 100
python scripts/preprocess_cfi_v2_from_manifest.py --manifest multimodal_personality/data/cfi_v2/manifests/val_manifest.json --limit 20

python scripts/build_clip_feature_jobs.py --manifest multimodal_personality/data/cfi_v2/manifests/train_manifest.json
python scripts/extract_clip_features.py --jobs multimodal_personality/data/cfi_v2/train_feature_jobs.json --device cuda
python scripts/extract_wav2clip_features.py --jobs multimodal_personality/data/cfi_v2/train_feature_jobs.json

python scripts/build_multimodal_feature_bundles.py --manifest multimodal_personality/data/cfi_v2/manifests/train_manifest.json --limit 100
python scripts/build_multimodal_feature_bundles.py --manifest multimodal_personality/data/cfi_v2/manifests/val_manifest.json --limit 20

python scripts/train_agtn_mtl.py --train-manifest multimodal_personality/data/cfi_v2/manifests/train_manifest.json --val-manifest multimodal_personality/data/cfi_v2/manifests/val_manifest.json --train-limit 100 --val-limit 20 --device cuda
```

### 3.6 跑全量长任务

```powershell
python scripts/run_full_multimodal_pipeline.py --train-device cuda --clip-device cuda
```

这个脚本会依次执行：

1. 预处理 train / val / test 缺失样本
2. 构建特征任务
3. 提取 CLIP 特征
4. 提取 wav2clip 特征
5. 生成 bundles
6. 训练 baseline
7. 输出 val / test 评估结果

而且它支持断点恢复。

### 3.7 日志与产物

默认输出目录：

- `reports/full_multimodal_pipeline/`
- `reports/night_lr1e4_drop02/`
- `reports/online_multimodal_smoke_20260425/`

重点查看：

- `reports/full_multimodal_pipeline/stderr.log`
- `reports/full_multimodal_pipeline/stdout.log`
- `reports/night_lr1e4_drop02/test_eval.json`
- `reports/online_multimodal_smoke_20260425/smoke_result.json`

不要在任务运行时删除这些目录：

- `uploads/multimodal_personality/artifacts`
- `reports/full_multimodal_pipeline`

## 4. Windows 黑色 python.exe 窗口说明

如果你看到一个黑色终端窗口，标题像 `C:\Python314\python.exe`，大概率不是异常，而是本地长任务的宿主窗口。

常见原因：

- 你启动的是 Python 长任务
- 输出被重定向到了日志文件
- 所以窗口本身可能几乎不显示内容

如果长任务还在跑：

- 不要关闭这个窗口
- 优先看日志判断任务进度

## 5. 当前部署策略建议

### 如果你现在要演示系统

优先做：

1. 用 Docker 跑在线主系统
2. 用当前前后端主流程做演示
3. 如果要演示真实多模态分数，使用本地已验证环境跑在线 service smoke 或展示 `reports/online_multimodal_smoke_20260425/smoke_result.json`

### 如果你现在要做论文实验

优先做：

1. 基于 `reports/night_lr1e4_drop02/` 整理当前最优全量结果
2. 补齐 `PCC / CCC / R²` 等论文指标
3. 继续评估 `bg_features`、多任务损失和更多随机种子的必要性

## 6. 仍需注意的事情

- 在线部署成功不代表部署环境具备完整多模态依赖；真实推理要看 `health` 中的 `model_ready` 和 `system_tools`。
- 当前仓库已完成本地在线真实推理 smoke，归档为 `reports/online_multimodal_smoke_20260425/smoke_result.json`。
- 真正的多模态研究结果，应以 `reports/` 目录中的训练、评估和推理产物为准。
