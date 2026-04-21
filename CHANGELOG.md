# 更新日志

本文档遵循 Keep a Changelog 风格，按北京时间记录关键变更。

## [2026-04-21] - 全量基线落地、在线真实推理接入与多模态服务收口

### 新增

- 新增 `multimodal_personality/models/__init__.py`、`multimodal_personality/models/agtn_layers.py`、`multimodal_personality/models/agtn_mtl.py` 与 `multimodal_personality/models/feature_bundle.py`，补齐 AGTN-MTL 模型、图卷积融合层和统一特征 bundle 契约。
- 新增 `multimodal_personality/feature_extractors/wav2clip_extractor.py`，将音频模态补齐到离线训练和在线推理链路中。
- 新增 `scripts/build_multimodal_feature_bundles.py`、`scripts/extract_wav2clip_features.py`、`scripts/train_agtn_mtl.py`、`scripts/eval_agtn_mtl.py`、`scripts/infer_agtn_mtl.py` 与 `scripts/run_full_multimodal_pipeline.py`，形成从预处理、特征提取、bundle 组装到训练评估的一站式命令入口。
- 新增 `multimodal_personality/training/` 训练辅助模块，支持 checkpoint 加载、bundle 评估、最小 baseline 训练与离线推理复用。
- 新增 `tests/test_multimodal_feature_extractors.py`、`tests/test_multimodal_models.py`、`tests/test_multimodal_training_pipeline.py` 与 `tests/test_multimodal_service.py`，覆盖特征提取、模型输入输出、训练链路和服务回退逻辑。

### 变更

- 将 [app/services/multimodal_personality_service.py](/D:/PythonCode/TestAgent/app/services/multimodal_personality_service.py) 从 `scaffold-v1` 占位实现升级为“预处理 -> CLIP -> wav2clip -> bundle -> checkpoint 推理”的真实在线服务，并保留不可用时自动回退到占位分数的安全兜底。
- 在 [app/core/config.py](/D:/PythonCode/TestAgent/app/core/config.py) 中新增 `MULTIMODAL_CHECKPOINT_PATH` 与 `MULTIMODAL_DEVICE` 配置项，使在线服务默认指向 `reports/full_multimodal_pipeline/agtn_mtl_full.pt`，同时支持 CPU/GPU 自适应切换。
- 调整 `scripts/build_clip_feature_jobs.py`、`scripts/extract_clip_features.py` 和 `multimodal_personality/feature_extractors/clip_extractor.py`，让特征提取链路与当前 manifest、artifact 结构和句子级文本特征保持一致。
- 更新 `.gitignore`，补充 `test_artifacts/` 与 `.ai/refs/` 等本地产物忽略规则，降低多轮实验对仓库状态的污染。
- 重写 `README.md`、`docs/DEPLOY.md`、`docs/毕设开发目标和进度.md`、`docs/待完成任务.md`、`docs/开发者日志.md`、`Agent.md` 与 `multimodal_personality/README.md`，把项目口径统一到“在线 ATMR 主系统 + 离线/在线可接的多模态人格模块”。

### 修复

- 修复 `wav2clip` 在新版 `librosa` 环境下的兼容问题，避免音频特征提取因 `frame()` 参数签名变化而失败。
- 修复 AGTN-MTL 中融合维度与 `hidden_dim` 绑定错误的问题，使模型不再只能在默认隐藏维度下正常训练。
- 修复在线多模态健康检查长期返回 `model_ready=False` 的问题，现在会显式检查 `ffmpeg / whisper / torch / transformers / PIL / wav2clip / checkpoint / CUDA`。

### 实验结果

- 完成全量基线训练与评估，数据规模为 `train 6000 / val 2000 / test 2000`。
- 全量基线 checkpoint 已产出为 `reports/full_multimodal_pipeline/agtn_mtl_full.pt`。
- 全量结果为：
  - `best_epoch = 1`
  - `val mse = 0.019289`
  - `val mae = 0.110833`
  - `test mse = 0.019945`
  - `test mae = 0.113552`
- 在线服务 smoke run 已使用真实样本成功返回 `agtn-mtl-full-baseline` 分数，不再固定输出 `0.50`。

### 测试

- 执行 `python -m pytest -q tests/test_multimodal_service.py tests/test_multimodal_training_pipeline.py`，结果为 `4 passed`。
- 已完成一次真实服务端到端烟雾验证：输入本地样本视频后成功产出真实 Big Five 分数与完整 artifact 路径。

## [2026-04-20] - 多模态闭环、全量 runner 与文档收口

### 新增

- 新增 `multimodal_personality/training/baseline.py`，补齐离线 baseline 训练入口。
- 新增 `scripts/train_agtn_mtl.py`、`scripts/eval_agtn_mtl.py`、`scripts/infer_agtn_mtl.py`，支持基于 bundle 的训练、评估和推理。
- 新增 `scripts/run_full_multimodal_pipeline.py`，支持从预处理到训练评估的一条龙全量长任务，并支持断点恢复。
- 新增 `wav2clip` 特征提取与对应训练测试覆盖。

### 变更

- 修正 `multimodal_personality/models/agtn_mtl.py` 中融合维度与 `hidden_dim` 绑定不正确的问题，使模型不再只能在默认隐藏维度下工作。
- 将多模态文档从“接口脚手架阶段”更新为“离线 baseline 已跑通、在线真实接入待完成”的口径。
- 对齐 `README.md`、`docs/DEPLOY.md`、`docs/毕设开发目标和进度.md`、`docs/待完成任务.md`、`docs/开发者日志.md`、`Agent.md` 与 `requirements_multimodal.txt`。

### 修复

- 修复 `wav2clip` 与 `librosa 0.11` 的兼容问题，避免音频特征提取在当前环境下失败。
- 明确区分在线 Web 服务部署和离线多模态训练环境，避免部署说明误导后续开发。

### 测试与结果

- 最近一次本地完整回归结果为 `69 passed`。
- 已完成两档真实小样本多模态验证：
  - `train 20 / val 5`
  - `train 100 / val 20`

### 备注

- 在线服务中的多模态接口仍为 `scaffold-v1` 占位分数。
- 全量多模态长任务已具备本地运行条件并已开始进入正式长跑阶段。

## [2026-04-20] - 安全与交互收口

### 新增

- 新增统一 Markdown 清洗能力，降低富文本渲染安全风险。
- 新增认证、聊天、RAG 与 assessment streaming 相关测试覆盖。

### 变更

- 优化聊天关联测评后的会话切换逻辑。
- 调整报告页、历史页和登录页的状态文案与交互反馈。

### 测试

- 当日主系统回归测试稳定通过。

## [2026-04-20] - 草稿态阶段提交与历史复制改答

### 新增

- 将测评草稿改为“阶段提交时首入库”的状态模型。
- `resume-session` 支持按 `session_id` 精确恢复。
- 已完成测评支持复制为新的普通测评会话继续修改答案。

### 变更

- 重构 assessment 提交与恢复逻辑。
- 综合报告层改为主要消费模块层裁决总结，减少上下文重复。

### 修复

- 修复已完成测评直接重开导致历史报告被覆盖的问题。
- 修复阶段题目回填错位与异常检测误报过多的问题。

## [2026-04-19] - 部署依赖拆分与前端状态收口

### 新增

- 新增 `requirements_feature.txt` 与更清晰的部署参数入口。

### 变更

- 重构 Docker 构建流程，拆分在线服务与特征向量相关依赖。
- 调整评审等待态、历史页和部署脚本的交互与安装策略。

### 修复

- 修复前端部分等待态、轮询和重定向残留问题。

## [2026-04-18] - 历史会话标题与文档重写

### 新增

- 为测评会话增加标题与重命名支持。
- 引入统一前端配置入口。

### 变更

- 重构历史页布局和测评档案展示。
- 重写项目级开发文档与毕设进度文档。

### 修复

- 修复旧数据缺失标题时的兼容问题。
- 修复头像路径与旧数据展示问题。

## [2026-04-17] - 配置兼容与 SQLite 开发模式

### 新增

- 新增 `AUTO_CREATE_TABLES`、`USE_SQLITE_DEV`、`SQLITE_PATH` 等配置项。
- 新增项目健康检查测试。

### 变更

- 将应用启动迁移到 FastAPI lifespan 模式。
- 统一本地 SQLite 与部署 PostgreSQL 的配置入口。

### 修复

- 修复 SQLite 兼容性、头像路径与恢复会话时的若干问题。

## [2026-04-14] - 阶段化测评与分维度报告

### 新增

- 新增 `/stage-info` 接口与阶段信息模型。
- 新增按维度组织的报告展示结构。

### 变更

- 将 assessment 流程重构为 `intro / fixed / A / T / M / R` 阶段模型。
- 拆出 `scoring.py` 与 `stage_service.py`。

### 修复

- 修复 R 模块不触发辩论、报告长时间停留在生成中等问题。

## [2026-04-05] - PageIndex、认证与聊天能力接入

### 新增

- 接入 PageIndex RAG 检索能力。
- 增加用户认证与登录页。
- 打通测评后聊天咨询链路。

## [2026-03-26] - 测评主链路初版落地

### 新增

- 搭建 FastAPI 后端与 Vue 前端基本框架。
- 接入题库、测评 API、报告服务与大模型辩论能力。

## [2026-03-11] - 项目初始化

### 新增

- 初始化仓库与毕设项目基础文档。
