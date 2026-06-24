# 更新日志

本文档遵循 Keep a Changelog 风格，按北京时间记录关键变更。

## [2026-06-24] - 多模态部署健康检查与 fallback 展示收口

### 修复

- CLIP 特征提取不再在运行时自动联网下载 `openai/clip-vit-large-patch14-336`，避免公司部署环境因外网超时导致后台任务长时间卡住后回退。
- CLIP 本地缓存仅包含 `pytorch_model.bin` 时，加载过程会显式禁用 safetensors 自动转换探测，避免 Transformers 后台线程再次访问 Hugging Face 并打印连接超时。
- 多模态 `health` 增加 `system_tools.clip_model`，并将本地 CLIP 权重可用性纳入 `model_ready` 判断。
- 大五人格报告详情页仅在 `is_real_result=true` 时展示雷达图、质量证据和维度简析；fallback 占位分数不再被当作正式人格报告展示。

### 文档

- 更新部署说明，明确真实视频人格推理必须满足 `model_ready=true` 且 `system_tools.clip_model=true`，并提醒部署机提前缓存 CLIP 权重。

## [2026-05-18] - 仓库可见内容与本地产物治理

### 变更

- 清理 GitHub 可见文档中的本地产物、临时稿和演示交付痕迹，统一改为项目、实验、部署和维护口径。
- 将历史本地写作工作区、导出文件和阶段材料移出 Git 跟踪范围，保留在本机忽略目录中。
- 删除未提交的临时生成脚本，避免后续继续把一次性产物写回仓库。
- 将 `Agent.md` 统一为 `AGENTS.md`，保留中文回复、PowerShell、单作者提交和文档同步约定。

### 验证

- 使用 `rg` 扫描 GitHub 可见区域，确认不再出现本地产物相关旧路径和交付语境。
- 对改动过的 Python 汇总脚本执行 `py_compile`，语法检查通过。
- 已提交并推送仓库治理提交 `4ad17bb` 到 `main`。

## [2026-05-18] - 实验方法、结果表与项目口径收口

### 变更

- 补齐 ATMR-CAT 自适应选题变量定义、贝叶斯近似更新、综合评分公式、异常作答检测、可信度建模、MOL 微表情辅助线索和关键实现文件对应关系。
- 整理 ATMR-CAT 校准实验、多随机种子稳定性实验、异常注入实验、可信度加权稳健性实验、多模态调参、单模态/多模态消融、`bg_features` 对照和 MOL 批量提取 smoke 表格。
- 更新 [README.md](/D:/PythonCode/TestAgent/README.md) 与 [docs/DEPLOY.md](/D:/PythonCode/TestAgent/docs/DEPLOY.md)，把项目状态同步为 2026-05-18 口径：`bg_features` 重训、消融实验、MOL quick baseline、管理端和实验说明收口均已完成 V1。
- 同步更新项目进度说明，明确当前重点从“继续证明能跑”转为“演示走查、本地产物和部署说明收口”。

### 当前说明口径

- ATMR-CAT 和可信度模型是项目主线，应描述为“面向 ATMR 的自适应题目选择与测评质量控制机制”。
- 视频 Big Five 与 MOL 微表情均作为辅助证据链，不替代问卷、访谈或临床评估。
- `bg_features` 与微表情结果应保守表达：`bg_features` 有有限正向补充，MOL quick baseline 证明链路可用，不宣称完整复现官方数据结果。

## [2026-04-27] - 实验指标、bg_features 与历史页体验收口

### 新增

- 新增 [multimodal_personality/training/metrics.py](/D:/PythonCode/TestAgent/multimodal_personality/training/metrics.py)，统一计算 `MSE / RMSE / MAE / ACC / PCC / CCC / R²` 及五维度分项指标。
- 新增 [multimodal_personality/feature_extractors/bg_extractor.py](/D:/PythonCode/TestAgent/multimodal_personality/feature_extractors/bg_extractor.py)，实现工程版 256 维 `bg_features`，基于 CLIP 画面特征、文本特征、音频特征和转写统计构建场景关联描述。
- 新增 [scripts/summarize_multimodal_experiments.py](/D:/PythonCode/TestAgent/scripts/summarize_multimodal_experiments.py)，可从评估 JSON 中补算关键指标并生成实验汇总表。

### 变更

- 扩展 [scripts/eval_agtn_mtl.py](/D:/PythonCode/TestAgent/scripts/eval_agtn_mtl.py)、[scripts/run_full_multimodal_pipeline.py](/D:/PythonCode/TestAgent/scripts/run_full_multimodal_pipeline.py) 和训练评估链路，使后续评估默认输出 `PCC / CCC / R²` 等关键指标。
- 将 `bg_features` 接入 bundle 构建和全量 pipeline；同时在线服务会根据 checkpoint 中的 feature contract 判断是否启用显式 `bg_features`，避免旧零填充 checkpoint 在未重训时被强行改变输入分布。
- 历史页大五人格侧栏按 `进行中 / 已完成 / 需要处理` 分组，并在大五人格卡片上直接提供“查看报告”和“重新生成”操作。
- 更新 [README.md](/D:/PythonCode/TestAgent/README.md)、[docs/DEPLOY.md](/D:/PythonCode/TestAgent/docs/DEPLOY.md)、[docs/开发者日志.md](/D:/PythonCode/TestAgent/docs/开发者日志.md) 和 [multimodal_personality/README.md](/D:/PythonCode/TestAgent/multimodal_personality/README.md)，把当前口径同步为“关键指标已补齐，bg_features 已有工程版实现，后续可重训做对照”。

### 实验结果

- 已补齐当前主要多模态实验的关键指标：
  - 初始全量 baseline：`MSE=0.0199`，`MAE=0.1136`，`ACC=0.8864`，`PCC=0.3422`，`CCC=0.1925`，`R²=0.1154`
  - `lr1e-4 / dropout 0.2`：`MSE=0.0115`，`MAE=0.0861`，`ACC=0.9139`，`PCC=0.7062`，`CCC=0.6327`，`R²=0.4881`
  - `lr1e-4 / dropout 0.3`：`MSE=0.0122`，`MAE=0.0885`，`ACC=0.9115`，`PCC=0.7062`，`CCC=0.5776`，`R²=0.4609`
  - `lr2e-4 / dropout 0.3`：`MSE=0.0131`，`MAE=0.0916`，`ACC=0.9084`，`PCC=0.6684`，`CCC=0.5410`，`R²=0.4196`

### 测试

- 执行 `python -m pytest -q`，结果为 `89 passed, 3 warnings`。
- 执行 `npm run build`，前端构建通过。
- 执行关键 Python 脚本语法检查，新增与修改脚本均通过。

## [2026-04-27] - 大五人格报告、RAG 知识库与双报告接入

### 新增

- 新增独立的大五人格报告模型与接口链路，支持视频上传生成报告、后台分析、列表/详情、失败重试、删除和 AI 解读重试。
- 新增大五人格 RAG 知识库：[PageIndex/BigFive_Personality_Knowledge.md](/D:/PythonCode/TestAgent/PageIndex/BigFive_Personality_Knowledge.md)，并写入 PageIndex 索引文件，供大五 AI 解读和 RAG 查询使用。
- 新增大五人格 AI 解读服务：[app/services/big_five_report_service.py](/D:/PythonCode/TestAgent/app/services/big_five_report_service.py)，基于五维分数、模型版本和 PageIndex 检索证据生成用户友好的详细解读。
- 新增大五人格报告详情页：[frontend/src/components/BigFiveReport.vue](/D:/PythonCode/TestAgent/frontend/src/components/BigFiveReport.vue)，提供雷达图、五维分数、维度简析、AI 解读和报告来源展示。
- 新增统一时间格式工具：[frontend/src/utils/dateTime.js](/D:/PythonCode/TestAgent/frontend/src/utils/dateTime.js)，修复前端把后端时间误按本地时区解释导致的显示偏差。
- 新增 [scripts/build_big_five_pageindex.py](/D:/PythonCode/TestAgent/scripts/build_big_five_pageindex.py)，用于重新构建大五人格 PageIndex 索引。

### 变更

- 历史记录页改为 `ATMR 测评` / `大五人格` 双标签分区，两类报告的列表、统计、侧栏和操作互不混排。
- 聊天会话支持同时关联一份 ATMR 报告和一份大五人格报告，创建/更新会话时可分别选择，并在系统上下文中并列呈现两类依据。
- 大五人格报告页对齐 ATMR 报告阅读体验，同时将 AI 正文收敛为 `综合人格画像`、`优势与潜在卡点`、`行动建议`、`使用边界`，五维速览改由前端固定渲染。
- 统一优化 ATMR 与大五人格报告页雷达图视觉，去除刻度数字，调整颜色、容器比例和移动端展示，避免默认图表感和黑色分数条。
- 大五人格报告在历史页中的文案统一为“大五人格”，将“AI 解读可查看”调整为“报告可查看”，并精简状态卡片展示。
- 大五 RAG 接口扩展为独立能力，新增 `big-five` 查询、检索和状态接口，同时保持 ATMR RAG 行为兼容。
- 多模态报告接口改为报告导向，底层任务能力保留兼容，前端不再暴露“多模态任务”这类技术概念。

### 修复

- 修复大五人格 AI 解读重试接口前端路径不匹配导致的 `not found` 问题。
- 修复大五人格报告长时间显示“生成中”时缺少状态同步和失败展示的问题。
- 修复历史页大五人格状态卡片中过度展示视频文件名、时间位置拥挤和日期显示不准的问题。
- 修复聊天报告选择列表中失败或 fallback 大五报告仍可能被作为对话依据的问题。

### 测试

- 执行 `npm run build`，前端构建通过。
- 执行 `python -m pytest -q`，结果为 `86 passed, 3 warnings`。
- 新增 [tests/test_big_five_reports_api.py](/D:/PythonCode/TestAgent/tests/test_big_five_reports_api.py)，覆盖大五报告上传、权限隔离、AI 解读生成和提示词结构。
- 扩展 [tests/test_chat_api.py](/D:/PythonCode/TestAgent/tests/test_chat_api.py)、[tests/test_rag_api.py](/D:/PythonCode/TestAgent/tests/test_rag_api.py) 和 [tests/test_rag_service.py](/D:/PythonCode/TestAgent/tests/test_rag_service.py)，覆盖大五报告聊天上下文和 Big Five RAG 检索链路。

## [2026-04-25] - DeepSeek V4 调用切换、多模态 smoke 与文档收口

### 新增

- 新增 [tests/test_deepseek_config.py](/D:/PythonCode/TestAgent/tests/test_deepseek_config.py)，覆盖 DeepSeek V4 默认模型、链式覆盖和 `thinking` 模式兜底逻辑，避免后续配置回退到旧模型名。
- 新增本轮多模态在线 smoke 归档：[smoke_result.json](/D:/PythonCode/TestAgent/reports/online_multimodal_smoke_20260425/smoke_result.json)、[smoke_summary.json](/D:/PythonCode/TestAgent/reports/online_multimodal_smoke_20260425/smoke_summary.json)，确认真实视频样本已通过 `agtn-mtl-best-lr1e4-drop02` 返回非占位 Big Five 分数。

### 变更

- 在 [app/core/config.py](/D:/PythonCode/TestAgent/app/core/config.py) 中统一收口 DeepSeek 配置，新增 `DEEPSEEK_BASE_URL`、`DEEPSEEK_CHAT_MODEL`、`DEEPSEEK_ANALYSIS_MODEL`、`DEEPSEEK_RAG_MODEL`、`DEEPSEEK_RAG_RETRIEVE_MODEL` 以及对应的 `thinking` 配置项，默认切换到 `deepseek-v4-flash` 并显式关闭 thinking，保证线上行为平滑升级。
- 将 [app/api/chat.py](/D:/PythonCode/TestAgent/app/api/chat.py)、[app/api/assessment/streaming.py](/D:/PythonCode/TestAgent/app/api/assessment/streaming.py)、[app/services/debate_manager.py](/D:/PythonCode/TestAgent/app/services/debate_manager.py) 和 [app/services/rag_service.py](/D:/PythonCode/TestAgent/app/services/rag_service.py) 中散落的 `deepseek-chat`、`https://api.deepseek.com/v1` 调用改为统一读取配置，彻底切到 DeepSeek V4 调用入口。
- 调整 [app/services/rag_service.py](/D:/PythonCode/TestAgent/app/services/rag_service.py) 的 PageIndex 模型映射逻辑，使检索和回答链路也同步跟随 DeepSeek V4 配置，不再出现“表面切换、底层仍旧模型”的不一致。
- 更新 [.env.example](/D:/PythonCode/TestAgent/.env.example)，补齐 DeepSeek V4 的默认环境变量和说明，后续如需将报告/辩论单独切到 `deepseek-v4-pro`，仅需修改环境变量即可。
- 调整 [multimodal_personality/feature_extractors/clip_extractor.py](/D:/PythonCode/TestAgent/multimodal_personality/feature_extractors/clip_extractor.py)，加载 CLIP 时优先使用本地 Hugging Face 缓存，缺缓存时再走正常下载，避免在线 smoke 因网络解析失败而回退到占位分数。
- 同步更新 [README.md](/D:/PythonCode/TestAgent/README.md)、[docs/DEPLOY.md](/D:/PythonCode/TestAgent/docs/DEPLOY.md)、[docs/开发者日志.md](/D:/PythonCode/TestAgent/docs/开发者日志.md) 和 [multimodal_personality/README.md](/D:/PythonCode/TestAgent/multimodal_personality/README.md)，将当前口径统一为“真实 checkpoint 已接入并通过 smoke，下一步接报告页和补完整指标”。

### 测试

- 执行 `python -m pytest -q`，结果为 `74 passed, 3 warnings`。
- 执行 `python -m pytest -q tests/test_deepseek_config.py tests/test_rag_service.py tests/test_chat_api.py`，结果为 `9 passed, 1 warning`。
- 执行 `python -m pytest -q tests/test_multimodal_feature_extractors.py tests/test_multimodal_models.py tests/test_multimodal_service.py tests/test_multimodal_training_pipeline.py`，结果为 `9 passed`。
- 执行多模态在线真实推理 smoke，结果 `passed=true`，模型版本为 `agtn-mtl-best-lr1e4-drop02`。

## [2026-04-24] - 切换多模态最佳模型并完成在线验证
### 变更

- 将 [app/core/config.py](/D:/PythonCode/TestAgent/app/core/config.py) 中的 `MULTIMODAL_CHECKPOINT_PATH` 默认值从 `reports/full_multimodal_pipeline/agtn_mtl_full.pt` 切换为 `reports/night_lr1e4_drop02/agtn_mtl_lr1e4_drop02.pt`，使在线服务默认使用当前最优的多模态 checkpoint。
- 将 [app/services/multimodal_personality_service.py](/D:/PythonCode/TestAgent/app/services/multimodal_personality_service.py) 中的真实模型版本标识更新为 `agtn-mtl-best-lr1e4-drop02`，便于后续接口、报告和排错时判断当前实际在用的模型版本。

### 实验结果

- 当前最优 checkpoint 为 `reports/night_lr1e4_drop02/agtn_mtl_lr1e4_drop02.pt`。
- 该版本全量测试结果为：
  - `test mse = 0.011543`
  - `test mae = 0.086074`
- 与此前线上候选 `night_lr1e4_drop03` 相比，新模型在验证集和测试集上都更优，并继续领先旧的全量 baseline。

### 测试

- 执行 `python -m pytest -q tests/test_multimodal_service.py tests/test_multimodal_training_pipeline.py`，结果为 `4 passed`。
- 执行 `python -m pytest -q`，结果为 `71 passed, 3 warnings`。
- 基于本地真实样本视频完成一次 service smoke，结果已写入 [smoke_result.json](/D:/PythonCode/TestAgent/reports/overnight_service_switch_verify/smoke_result.json)，任务状态为 `completed`，已成功返回真实 Big Five 分数，而不是占位分数。

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
- 重写 `README.md`、`docs/DEPLOY.md`、`docs/开发者日志.md`、`Agent.md` 与 `multimodal_personality/README.md`，把项目口径统一到“在线 ATMR 主系统 + 离线/在线可接的多模态人格模块”。

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
- 对齐 `README.md`、`docs/DEPLOY.md`、`docs/开发者日志.md`、`Agent.md` 与 `requirements_multimodal.txt`。

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
- 重写项目级开发文档与进度文档。

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

- 初始化仓库与项目基础文档。
