# ATMR 智能心理测评系统

基于 ATMR 问卷、多智能体辩论、RAG 知识检索和视频多模态人格预测的智能心理测评系统。

项目当前已经形成三条主线：

1. 在线 ATMR 主系统：负责注册登录、答题、阶段提交、报告、历史记录和 AI 咨询。
2. 大五人格视频报告线：负责从视频中生成 Big Five 五维分数、AI 解读、历史档案和聊天上下文。
3. 离线多模态子系统：负责从视频中完成预处理、特征提取、AGTN-MTL baseline 训练、评估和推理。

## 当前状态

更新时间：2026-05-18

- 在线主系统已经闭环，可完成 ATMR 主流程演示与日常开发。
- ATMR-CAT 自适应选题、异常作答检测、可信度降权、维度置信度和题目证据链已经接入主流程与报告页。
- 已完成 ATMR-CAT 冷启动校准、多随机种子、异常注入和可信度加权稳健性实验，方法说明与实验表已整理。
- 大五人格已经作为独立报告接入主系统：历史页按 `ATMR 测评` / `大五人格` 分区展示，对话页可同时关联一份 ATMR 报告和一份大五人格报告。
- 大五人格 RAG 知识库已经落到 PageIndex，AI 解读会优先使用大五资料库证据，报告页展示 `综合人格画像 / 优势与潜在卡点 / 行动建议 / 使用边界`，并补充模态质量、预测置信度和 ATMR 一致性提示。
- 多模态离线 baseline 已经跑通 `预处理 -> CLIP -> wav2clip -> bundle -> train -> eval -> infer`。
- 已完成的真实小样本验证：
  - `train 20 / val 5`：`mse=0.004983`，`mae=0.057872`
  - `train 100 / val 20`：`mse=0.016520`，`mae=0.100234`
- 全量多模态 baseline 已完成，旧全量基线产物位于 `reports/full_multimodal_pipeline/`。
- 当前在线默认 checkpoint 已切换为 `reports/night_lr1e4_drop02/agtn_mtl_lr1e4_drop02.pt`：
  - `test mse=0.011543`
  - `test mae=0.086074`
  - `test pcc=0.7062`
  - `test ccc=0.6327`
  - `test r²=0.4881`
- 已完成在线真实推理 smoke 验证，结果位于 `reports/online_multimodal_smoke_20260425/smoke_result.json`，模型版本为 `agtn-mtl-best-lr1e4-drop02`。
- 已完成真实 `bg_features` 全量重训和多模态消融：
  - 三模态 baseline：`MAE=0.0861`，`PCC=0.7062`，`CCC=0.6327`，`R²=0.4881`
  - 三模态 + `bg_features`：`MAE=0.0862`，`PCC=0.7072`，`CCC=0.6324`，`R²=0.4897`
  - 消融结论：视觉单模态贡献最强，音频和文本提供补充，多模态融合主要提升相关性稳定性。
- MOL 微表情模块已经完成本地部署、TIM20/SAMM 风格 quick baseline、批量提取、服务层摘要和消融入口，可作为细粒度非语言视觉线索增强模块。
- 轻量管理端 `/admin` 已完成 V1，用于题库质量、报告质量和实验结果查看。
- 当前仍未完成的关键点：
  - 仍需做完整系统演示走查，准备固定账号、正常/异常 ATMR 报告、大五报告和一致性分析案例。
  - README、部署说明和演示材料需要持续保持同一套谨慎口径：ATMR 为主线，多模态与微表情为辅助证据链。
  - 数据库迁移、后台任务队列、部署交付包和隐私治理说明仍需继续正规化。

## 核心能力

### ATMR 问卷主系统

- 用户注册、登录、头像上传
- 测评草稿、显式恢复、阶段提交
- A / T / M / R 四阶段答题流程
- ATMR-CAT 自适应选题、异常作答检测、可信度降权与题目证据链
- 多智能体辩论与综合报告生成
- 可信度加权参考分、维度置信度、整体可信度和报告解释边界
- 历史记录、报告详情、测评后 AI 咨询
- 与大五人格报告并列关联到同一咨询会话
- 管理端质量治理后台
- Docker 部署、本地 SQLite 开发模式、PostgreSQL 部署模式

### 大五人格报告与 RAG

- 视频上传后生成独立“大五人格”报告，不嵌入 ATMR 测评会话
- 历史页按 `ATMR 测评` / `大五人格` 双标签分区管理
- 大五人格报告页包含雷达图、五维分数条、维度简析、报告来源和 AI 解读
- 大五人格报告页展示模态质量、预测置信度和 ATMR-Big Five 一致性分析
- 大五 AI 解读使用独立 Big Five RAG / PageIndex 知识库，定位为非临床人格倾向解读
- 聊天上下文支持 ATMR 报告和大五人格报告并列读取，不自动融合成单一结论

### 多模态离线子系统

- CFI-V2 manifest 生成
- 视频抽帧、音频提取、Whisper 转写
- CLIP 视觉/文本特征提取
- wav2clip 音频特征提取
- 特征 bundle 组装
- AGTN-MTL baseline 训练、评估、推理脚本
- 工程版 `bg_features` 生成、全量重训和消融实验
- MOL 微表情批量提取、摘要服务和小样本消融入口
- 可恢复的全量长任务脚本
- 在线服务真实 checkpoint 推理与失败回退

## 关键目录

```text
TestAgent/
  app/                             FastAPI 后端
  frontend/                        Vue 3 前端
  docs/                            项目级文档
  PageIndex/                        ATMR 与 Big Five RAG 知识库及索引
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

最近一次本地完整结果见 `CHANGELOG.md`；当前主回归为 `133 passed`，前端 `npm run build` 通过，多模态在线 smoke 已在 `reports/online_multimodal_smoke_20260425/` 归档。

## 当前最值得优先做的事

1. 做完整系统演示走查，固定账号、样例报告和讲解顺序。
2. 将已补入的 ATMR-CAT、可信度、多模态消融和 MOL quick baseline 结果沉淀到项目实验报告和演示材料。
3. 整理本地产物：checkpoint、`reports/` 关键实验结果、smoke 结果和部署说明。
4. 收口数据库迁移、后台任务队列和线上/本地多模态环境说明。

## 相关文档

- `docs/DEPLOY.md`：在线部署与本地多模态运行说明
- `docs/开发者日志.md`：给维护者看的工程状态说明
- `docs/MOL微表情接入说明.md`：MOL 微表情模块接入方式
- `docs/管理端质量治理后台说明.md`：管理端质量治理后台说明
- `multimodal_personality/README.md`：多模态子系统详细使用说明
- `CHANGELOG.md`：按日期整理的变更记录
- `AGENTS.md`：仓库协作与终端约束

## License

项目采用 `CC BY-NC-SA 4.0` 许可协议，允许学习、修改和分享，但禁止商业用途。
