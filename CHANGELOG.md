# 更新日志

本文件基于仓库提交记录整理，格式参考 Keep a Changelog。

- 日期使用北京时间（UTC+8）。
- 当前仓库未维护 Git Tag，因此按发布日期归档，而不是按语义化版本号归档。
- 整理范围覆盖 `3af8f21` 至当前 `HEAD` 提交。

---

## [2026-04-18] - 测评标题持久化、档案页重构与毕设文档重写

### 新增
- 为 `assessment_sessions` 增加 `title` 字段、缺失列自动补齐逻辑和默认标题回填流程，并新增 `PUT /assessment/session/{session_id}` 重命名接口。
- 新增 `frontend/src/config.js` 与 `frontend/.env.development.example`，统一前端 API、SSE 和上传资源的后端地址配置。
- 新增 `docs/中期检查.txt`、`docs/毕业设计（论文）中期检查表-范本1.pdf` 和 `docs/毕设开发目标和进度_改写前备份.md`，补充中期检查与文档改写留档材料。

### 变更
- 重构 `frontend/src/components/History.vue`，引入移动端抽屉侧栏、会话菜单、重命名流程、概览卡片和新的档案卡片布局。
- 调整 `App.vue`、`Chat.vue`、`Report.vue` 与 `frontend/src/api.js`，将聊天入口前置、报告标题切换为测评会话标题，并统一头像与接口地址解析方式。
- 更新 `frontend/vite.config.js` 和 `app/services/debate_manager.py`，支持通过环境变量切换后端代理地址，并同步调整 DashScope/智谱模型配置。

### 修复
- 启动阶段自动修复历史数据库缺失的 `assessment_sessions.title` 列，并为旧测评记录补齐可读标题，避免历史记录和报告页出现空标题。
- 在历史记录和报告接口中为旧数据补充标题回退逻辑，保证未命名会话仍能按开始时间稳定展示。
- 修复 `app/api/auth.py` 删除旧头像时未复用 `UPLOAD_DIR` 的路径错误，保证头像清理逻辑与测试环境、静态目录配置保持一致。

### 文档
- 重写 `docs/开发者日志.md` 和 `docs/毕设开发目标和进度.md`，将项目主线收敛为 ATMR 测评系统与视觉多模态人格测评双线方案。
- 删除 `docs/工作日志.md`、`docs/目前问题.md`、`docs/评分标准.md` 等旧文档入口，并同步移除 `README.md` 中失效的评分标准链接。

---

## [2026-04-18] - 响应式收口、题库清洗与 RAG 容错

### 新增
- 新增 `app/services/question_sanitizer.py`，用于清洗题干中遗留的题号前缀，并在启动阶段修复存量题库内容。
- 新增统一弹窗组件 `frontend/src/components/AppDialog.vue` 与组合式封装 `frontend/src/composables/useAppDialog.js`，统一提示、确认和输入类交互。

### 变更
- 重构 `App.vue`、`Assessment.vue`、`Chat.vue`、`History.vue` 的布局与交互，统一移动端和桌面端的响应式行为。
- 收敛聊天会话、历史记录和报告入口的前端状态处理，补齐空状态、弹窗流程和页面切换细节。

### 修复
- 增强 `app/services/rag_service.py` 对超时重试、JSON fenced code block 解析和异常文案回退的容错能力。
- 优化 `scripts/import_data.py` 的题库导入清洗逻辑，避免题干重复携带编号前缀。

### 测试
- 新增 `tests/test_question_sanitizer.py`，覆盖题干清洗和存量题目修复逻辑。
- 新增 `tests/test_rag_service.py`，覆盖 RAG 评分解析和超时后重试成功路径。

---

## [2026-04-17] - 配置兼容、部署收口与答题流程修复

### 新增
- 增加 `AUTO_CREATE_TABLES`、`USE_SQLITE_DEV`、`SQLITE_PATH` 等配置项，支持 `.env` 自动加载和开发态数据库切换。
- 新增 `tests/test_project_health.py`，覆盖启动副作用、上传目录、数据库连接串和健康检查相关行为。

### 变更
- 将应用启动迁移为 FastAPI lifespan 模式，统一 `init_db()` 的执行入口。
- 更新 `.env.example`、`docker-entrypoint.sh`、`docker-compose.yml`、`docs/DEPLOY.md` 与前端 Nginx 配置，统一本地开发和 Docker 部署说明。
- 调整数据库初始化逻辑，使 SQLite 开发模式与 PostgreSQL 部署模式共用同一套配置入口。

### 修复
- 修复头像上传目录定位和旧头像删除路径错误，避免遗留文件无法清理。
- 修复 `app/models/assessment.py` 中 JSON 字段在 SQLite 开发环境下的兼容性问题。
- 修复恢复会话后阶段内翻题失效、桌面端一屏展示不足和窄屏布局相互挤压的问题。

---

## [2026-04-16] - 前端视觉升级与关键交互修复

### 变更
- 升级全局 Bright Glassmorphism 视觉风格，统一导航、卡片、按钮和背景动效的观感。
- 延长阶段评审加载动画并拆分为更明确的步骤反馈，提升模块提交后的等待体验。

### 修复
- 修复 `Report.vue` 在移动端的 Markdown 排版冲突问题，改用相对字号体系。
- 修复 `Assessment.vue` 中阶段加载动画无法渲染的模板判断问题。
- 修复阶段提交按钮重复点击导致的并发提交和状态穿透风险。

---

## [2026-04-15] - 构建加速、迁移增强与文档整理

### 变更
- 增强 `scripts/migrate_database.py` 对历史表结构和兼容字段的处理能力。
- 将智谱裁决模型切换为 `glm-4.7-flash`，降低调用成本并适配当前运行配置。
- 优化测评页移动端选项样式，提升平板和手机端可读性。

### 修复
- 调整 Docker 依赖安装顺序和超时参数，降低 PyTorch 与其余依赖的构建失败概率。
- 修复 Debian 安全源替换规则，避免 `apt` 更新失败。
- 为 `requirements_full.txt` 补充 `slowapi`，修复限流依赖缺失问题。

### 文档
- 新增 `Agent.md`，明确终端、回复语言和协作约束。
- 移除旧 `claude.md`，并重写 `docs/待完成任务.md`。

---

## [2026-04-14] - 阶段化测评与分维度报告重构

### 新增
- 新增 `/stage-info` 接口和阶段信息模型，支持按 `intro / fixed / A / T / M / R` 管理答题流程。
- 新增分维度报告展示结构，将各模块辩论结果和答题明细分开组织。

### 重构
- 将原有单体 `assessment` 流程重构为阶段化架构，并补充 `scoring.py` 与 `stage_service.py`。
- 统一题目响应格式，新增 `question_stats` 等元数据字段。

### 修复
- 修复 R 模块不触发辩论的问题，确保四个维度都能产出模块结论。
- 修复后台报告生成失败后前端长期停留在“生成中”的问题。
- 修复历史记录页无数据时的布局错位、会话创建错误提示过泛和模型时区默认值不一致的问题。

### 变更
- 延长综合报告生成超时，适配多轮辩论调用耗时。
- 移除报告中对知识库引用的冗余直出，保留 RAG 作为内部推理依据。

---

## [2026-04-13] - RAG 语义评分升级

### 变更
- 将 `rag_service.py` 从关键词匹配升级为“关键词粗筛 + LLM 语义评分 + 正文提取”的三阶段检索流程。
- 增加相关性阈值过滤和兜底机制，提升复杂查询场景下的召回质量与稳定性。

---

## [2026-04-12] - 工程标准化与代码库清理

### 重构
- 将 `app/api/assessment.py` 拆分为 `sessions.py`、`questions.py`、`submissions.py`、`streaming.py`、`schemas.py` 五个模块。
- 重构 PageIndex 相关核心文件，统一索引、检索和工具函数组织方式。
- 新增 `app/core/database.py`、`app/core/constants.py`，收敛数据库依赖注入和全局常量定义。

### 新增
- 引入 `pytest` 测试框架和 `pre-commit`，建立基础工程质量门槛。
- 用 `pyproject.toml` 统一管理 Python 依赖。
- 新增 `data/`、`scripts/`、`uploads/` 目录结构，并补充数据导入、特征向量、迁移和监控脚本。
- 补充移动端响应式改造，覆盖 `App.vue`、`Assessment.vue`、`Chat.vue`、`History.vue`、`Login.vue` 等核心页面。

### 文档
- 新增 `docs/开发者日志.md`。
- 完善 `CHANGELOG.md` 与文档管理规则，明确提交中不引入 Claude 贡献者信息。

### 修复
- 修复 PageIndex 示例代码与 Jupyter Notebook 的兼容性问题。

---

## [2026-04-11] - 异常检测升级与工程收尾

### 变更
- 将异常检测从单一时间阈值升级为多维风险评分模型，增加连续快速作答和重复选项检测。
- 为答题接口增加 `risk_score` 和 `risk_reasons` 字段。
- 清理废弃的 `/submit_explanation` 和重复 `/finish` 接口。
- 落地聊天持久化，统一前端页面的状态和样式表现。

### 修复
- 修复题号列表点击和未加载题目自动补载逻辑。

### 文档
- 更新 README、许可证、测试目标文档和评分标准文档。

### 运维
- 修复 Gitee 同步和 GitHub Actions 工作流目录问题。
- 忽略 Vite 构建缓存目录。

---

## [2026-04-10] - 断点续答、模块提交与 Docker 稳定化

### 新增
- 新增断点续答，支持中途退出后恢复会话。
- 新增已完成测评后的答案修改与重新提交能力。
- 新增模块提交按钮、可折叠题目导航和历史记录 ATMR 维度分数展示。

### 变更
- 将辩论过程改为轨道动画展示，降低等待时的信息噪声。
- 优化 PC 端布局和历史记录展示。
- 统一模块辩论 prompt 长度限制。

### 修复
- 修复 Docker 构建依赖顺序、Nginx SSE 代理和 Decimal JSON 序列化问题。
- 将 `autogen` 调整为可选依赖，并恢复 CPU 版 `torch` 以降低部署门槛。

---

## [2026-04-09] - 自适应选题与容器化部署

### 新增
- 新增 `Dockerfile`、`docker-compose.yml`、`docker-entrypoint.sh` 和 `.env.example`，支持一键部署。
- 新增 Gitee 自动同步工作流和更新脚本。
- 升级前端 Docker 构建所需 Node.js 版本，并支持国内镜像源加速。

### 修复
- 修复自适应选题流程与 PostgreSQL 兼容性问题。

### 运维
- 清理旧版 SQLite 迁移脚本和历史部署残留。

---

## [2026-04-05] - PageIndex、身份验证与聊天能力接入

### 新增
- 接入 PageIndex RAG 检索引擎。
- 新增用户认证模块和登录页面。
- 新增聊天接口与 `Chat.vue` 页面，打通测评后咨询链路。

---

## [2026-03-27] - SSE 流式辩论架构切换

### 重构
- 将辩论执行链路迁移为流式架构，支持 SSE 推送实时辩论结果。
- 重构 `debate_manager.py`、`assessment.py`、`ai_detector.py`、`report_service.py`，移除旧同步逻辑。

### 运维
- 停止跟踪数据库文件和生成产物，更新 `.gitignore`。

---

## [2026-03-26] - 测评主链路初版落地

### 新增
- 新增 FastAPI 后端入口、测评 API、题库与多 LLM 辩论服务。
- 新增 Vue + Vite 前端、测评页面、作答记录存储和报告服务。
- 建立题库处理脚本和基础数据模型。

### 变更
- 调整主服务初始化逻辑，为后续流式架构和前后端联调铺路。

---

## [2026-03-12] - 文档基线建立

### 文档
- 补充毕设项目的需求分析、概要设计、开发目标和测试计划文档。

---

## [2026-03-11] - 项目初始化

### 新增
- 初始化项目仓库，搭建多智能体对话实验环境和毕设开发基础骨架。
