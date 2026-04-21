# ATMR 智能心理测评系统

基于 ATMR 问卷、多智能体辩论、RAG 知识检索和视频多模态人格预测的智能心理测评系统。

项目当前已经形成两条主线：

1. 在线 ATMR 主系统：负责注册登录、答题、阶段提交、报告、历史记录和 AI 咨询。
2. 离线多模态子系统：负责从视频中完成预处理、特征提取、AGTN-MTL baseline 训练、评估和推理。

## 当前状态

更新时间：2026-04-20

- 在线主系统已经闭环，可完成 ATMR 主流程演示与日常开发。
- 多模态离线 baseline 已经跑通 `预处理 -> CLIP -> wav2clip -> bundle -> train -> eval -> infer`。
- 已完成的真实小样本验证：
  - `train 20 / val 5`：`mse=0.004983`，`mae=0.057872`
  - `train 100 / val 20`：`mse=0.016520`，`mae=0.100234`
- 全量多模态长任务已经具备可恢复 runner，日志位于 `reports/full_multimodal_pipeline/`。
- 最近一次本地回归测试结果为 `69 passed`。
- 当前仍未完成的关键点：
  - `app/services/multimodal_personality_service.py` 仍返回 `scaffold-v1` 占位分数，尚未接入真实 checkpoint
  - 多模态结果尚未正式落到主系统报告页和测评会话中
  - `bg_features` 仍未实现

## 核心能力

### ATMR 问卷主系统

- 用户注册、登录、头像上传
- 测评草稿、显式恢复、阶段提交
- A / T / M / R 四阶段答题流程
- 自适应选题与异常作答检测
- 多智能体辩论与综合报告生成
- 历史记录、报告详情、测评后 AI 咨询
- Docker 部署、本地 SQLite 开发模式、PostgreSQL 部署模式

### 多模态离线子系统

- CFI-V2 manifest 生成
- 视频抽帧、音频提取、Whisper 转写
- CLIP 视觉/文本特征提取
- wav2clip 音频特征提取
- 特征 bundle 组装
- AGTN-MTL baseline 训练、评估、推理脚本
- 可恢复的全量长任务脚本

## 关键目录

```text
TestAgent/
  app/                             FastAPI 后端
  frontend/                        Vue 3 前端
  docs/                            项目级文档
  multimodal_personality/          多模态复现与训练目录
  scripts/                         构建、训练、评估、部署脚本
  tests/                           Python 测试
  reports/                         运行报告与实验产物
  uploads/                         上传文件与多模态工件
  requirements_full.txt            在线主系统完整依赖
  requirements_server.txt          在线主系统轻量部署依赖
  requirements_feature.txt         题目特征向量依赖
  requirements_multimodal.txt      多模态离线依赖
```

## 快速开始

### 1. 本地启动在线主系统

```powershell
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements_full.txt
python -m pip install -r requirements_feature.txt

Copy-Item .env.example .env

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

新开一个终端启动前端：

```powershell
Set-Location frontend
npm install
npm run dev
```

默认访问地址：

- 后端：`http://127.0.0.1:8000`
- 前端：`http://127.0.0.1:5173`

### 2. Docker 启动在线主系统

```powershell
Copy-Item .env.example .env
docker compose up -d --build
```

默认只暴露前端入口；如果需要直接查看 Swagger，请按 `docs/DEPLOY.md` 中的方法显式暴露 `8000` 端口。

### 3. 跑多模态最小闭环

注意：多模态训练环境和在线主系统部署环境不是同一件事。离线多模态推荐单独安装 `requirements_multimodal.txt`，并保证系统已安装 `ffmpeg`。

```powershell
python -m pip install -r requirements_multimodal.txt

python scripts/build_cfi_v2_manifest.py --config multimodal_personality/configs/cfi_v2.example.yaml --phase all

python scripts/preprocess_cfi_v2_from_manifest.py --manifest multimodal_personality/data/cfi_v2/manifests/train_manifest.json --limit 100
python scripts/preprocess_cfi_v2_from_manifest.py --manifest multimodal_personality/data/cfi_v2/manifests/val_manifest.json --limit 20

python scripts/build_clip_feature_jobs.py --manifest multimodal_personality/data/cfi_v2/manifests/train_manifest.json
python scripts/extract_clip_features.py --jobs multimodal_personality/data/cfi_v2/train_feature_jobs.json --device cuda
python scripts/extract_wav2clip_features.py --jobs multimodal_personality/data/cfi_v2/train_feature_jobs.json

python scripts/build_multimodal_feature_bundles.py --manifest multimodal_personality/data/cfi_v2/manifests/train_manifest.json --limit 100
python scripts/build_multimodal_feature_bundles.py --manifest multimodal_personality/data/cfi_v2/manifests/val_manifest.json --limit 20

python scripts/train_agtn_mtl.py --train-manifest multimodal_personality/data/cfi_v2/manifests/train_manifest.json --val-manifest multimodal_personality/data/cfi_v2/manifests/val_manifest.json --train-limit 100 --val-limit 20 --device cuda --checkpoint multimodal_personality/checkpoints/agtn_mtl_baseline.pt
python scripts/eval_agtn_mtl.py --checkpoint multimodal_personality/checkpoints/agtn_mtl_baseline.pt --bundle-dir <val_bundle_dir> --device cuda
python scripts/infer_agtn_mtl.py --checkpoint multimodal_personality/checkpoints/agtn_mtl_baseline.pt --bundle <bundle_json_path> --device cuda
```

推荐先从 `100 / 20` 开始，不要一上来直接反复跑全量 `6000 / 2000 / 2000`。

### 4. 跑多模态全量长任务

```powershell
python scripts/run_full_multimodal_pipeline.py --train-device cuda --clip-device cuda
```

长任务支持断点恢复，关键日志：

- `reports/full_multimodal_pipeline/stderr.log`
- `reports/full_multimodal_pipeline/stdout.log`

## 测试

常用测试命令：

```powershell
python -m pytest -q
```

最近一次本地完整结果：`69 passed`。

## 当前最值得优先做的事

1. 跑完全量多模态 baseline，并记录最终 `val / test` 指标。
2. 将真实 checkpoint 接入 `app/services/multimodal_personality_service.py`，替换 `0.50` 占位分数。
3. 将多模态结果挂到测评会话、报告页和历史记录中。
4. 在论文里补齐多模态实验、融合分析和系统工程实现说明。

## 相关文档

- `docs/DEPLOY.md`：在线部署与本地多模态运行说明
- `docs/毕设开发目标和进度.md`：毕设整体路线与当前阶段进度
- `docs/待完成任务.md`：当前优先级最高的待办事项
- `docs/开发者日志.md`：给维护者看的工程状态说明
- `multimodal_personality/README.md`：多模态子系统详细使用说明
- `CHANGELOG.md`：按日期整理的变更记录
- `Agent.md`：仓库协作与终端约束

## License

项目采用 `CC BY-NC-SA 4.0` 许可协议，允许学习、修改和分享，但禁止商业用途。
