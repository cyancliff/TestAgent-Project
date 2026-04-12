# 更新日志

所有日期均为北京时间 (UTC+8)。

---

## [2026-04-13] - RAG 检索策略升级

### Feat
- RAG 检索从关键词匹配升级为 LLM 语义评分：重构 `rag_service.py`，实现三阶段检索架构（关键词粗筛 → LLM 语义批量评分 → 内容提取），新增相关性阈值过滤与兜底机制，提升复杂查询召回准确率

---

## [2026-03-11] - 项目初始化

### Feat
- 初始化毕设项目，搭建多智能体对话实验环境

---

## [2026-03-12] - 项目文档

### Docs
- 添加毕设项目文档：需求分析和概要设计、测试目标和进度

---

## [2026-03-26] - 后端答题服务与前端

### Feat
- 实现后端答题服务、题库与多 LLM 驱动辩论：新建 `app/api/assessment.py`、`app/core/config.py`、`app/main.py`、`app/models/question.py`、`app/schemas/payload.py`、`app/services/ai_detector.py`
- 新增前端网页与答题记录存储：基于 Vue + Vite 搭建前端，新增 `Assessment.vue` 组件、答题记录模型 `record.py`、报告服务 `report_service.py`

---

## [2026-03-27] - SSE 流式架构

### Refactor
- 迁移到流式辩论架构，实现 SSE 推送：重构 `debate_manager.py`、`assessment.py`、`ai_detector.py`、`report_service.py`，支持服务端推送实时辩论结果

### Chore
- 更新 .gitignore，停止跟踪数据库文件 (`atmr_data.db`)

---

## [2026-04-05] - PageIndex 集成与身份验证

### Feat
- 添加 PageIndex 集成：引入 PageIndex RAG 检索引擎，包含 agentic retrieval、chat quickstart、simple RAG、vision RAG 等 Cookbook 示例
- 新增身份验证、聊天功能及前端组件：新建 `auth.py`、`chat.py`、登录页面等

---

## [2026-04-09] - 自适应选题与 Docker 部署

### Fix
- 修复自适应选题流程与 PostgreSQL 兼容性问题：新建 `question_selection.py`、`rag_service.py`、`security.py`，修复认证与选题逻辑

### Feat
- 优化 PC 端页面布局与历史记录分数展示：完善 `App.vue`、`History.vue`、`Report.vue`、`Login.vue` 等组件
- 添加 Docker 部署配置与 Gitee 自动同步：新建 `Dockerfile`、`docker-compose.yml`、`docker-entrypoint.sh`、`.env.example`、GitHub Actions 同步工作流

### Fix
- 修复 Docker 依赖管理与构建问题：优化 `Dockerfile`、`requirements_full.txt`、同步工作流
- 优化 Nginx SSE 代理配置，修复 Decimal 序列化问题：修复 `report_service.py` 中的数据类型转换

---

## [2026-04-10] - 断点续答与辩论动画

### Feat
- 隐藏辩论过程，改为轨道动画显示专家辩论：重构前端 `Assessment.vue`、`App.vue`，以可视化轨道动画替代文字直播
- 实现断点续答、答案修改、模块提交与题目导航：支持用户暂停后继续作答、修改已提交答案、按模块提交
- 任务完成 - 聊天持久化、异常检测补强、前端统一优化：新建 `docs/工作日志.md`，优化 `ai_detector.py`、`Chat.vue`、`History.vue`、`Report.vue`、`style.css`

### Fix
- 题目列表所有题号可见可点击，未加载的题点击自动加载：优化 `Assessment.vue` 题号渲染逻辑

---

## [2026-04-11] - 文档完善与 CI 修复

### Docs
- 完善项目文档和许可证：添加 `LICENSE`，更新 README、工作日志、微服务任务文档、测试目标文档

### Fix
- 修复 Gitee 同步与 GitHub Actions 工作流配置：将 `,github/` 重命名为 `.github/`，修复工作流路径错误

---

## [2026-04-12] - 全面清理与重构

### Feat
- 全面优化移动端显示效果和响应式设计：重构 `App.vue`、`Assessment.vue`、`Chat.vue`、`History.vue`、`Login.vue`、路由与 Vite 配置
- 规范化 README 文档结构与内容
- 更新评分标准文档与项目配置
- 完善待完成任务文档

### Refactor
- PageIndex 模块全面重构：优化 `page_index.py`、`page_index_md.py`、`client.py`、`retrieve.py`、`utils.py` 等核心文件
- Agent 辩论管理器 (`debate_manager.py`) 代码优化
- 拆分 `assessment.py` (1500行) 为 5 个模块化文件：`sessions.py`、`questions.py`、`submissions.py`、`streaming.py`、`schemas.py`
- 创建 `app/core/database.py` 统一 `get_db()` 依赖注入
- 创建 `app/core/constants.py` 集中管理 `MODULE_DIM_MAP` 等硬编码常量
- 用 `pyproject.toml` 替代多份 `requirements.txt` 统一依赖管理
- 引入 pytest 测试框架，新增 28 个单元测试覆盖 `ai_detector` 和 `question_selection`
- 配置 pre-commit hooks (ruff lint + format) 自动代码格式化
- 消除重复代码：删除 `auth.py`/`chat.py` 中重复的 `get_db()`，统一引用共享常量

### Chore
- 清理废弃脚本，迁移至 `scripts/` 目录：`check_feature_status.py`、`deploy_adaptive_system.py`、`generate_feature_vectors.py`、`import_data.py`、`migrate_database.py`、`monitor_selection.py`、`test_adaptive_selection.py`
- 新增 `data/`、`scripts/`、`uploads/` 目录结构
- 更新 Dockerfile 与 `docker-entrypoint.sh` 配置
- 迁移部署文档至 `docs/DEPLOY.md`
- 更新 .gitignore 忽略规则、LICENSE 文件
- 创建 CHANGELOG.md 更新日志
- 更新 CLAUDE.md 明确提交者规范

### Fix
- 修复 PageIndex 示例代码与 Jupyter Notebook 中的兼容性问题
