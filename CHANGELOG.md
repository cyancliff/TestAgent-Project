# 更新日志

所有日期均为北京时间 (UTC+8)。

格式说明：**新增**（新功能）、**修复**（Bug 修复）、**优化**（性能/体验改进）、**重构**（代码结构调整）、**文档**（文档更新）、**其他**（配置/构建/CI 等）。

---

## [2026-04-17] - 启动链路修复、环境兼容增强与前端布局收口

### 新增
- **新增环境与健康检查配置项**：`app/core/config.py` 支持自动加载 `.env`，新增 `AUTO_CREATE_TABLES`、`USE_SQLITE_DEV`、`SQLITE_PATH` 等配置，并提供基于 `DB_USER`、`DB_PASSWORD`、`DB_HOST`、`DB_PORT`、`DB_NAME` 组装数据库连接串与开发态 `SECRET_KEY` 兜底生成逻辑。
- **新增项目健康检查测试**：添加 `tests/test_project_health.py`，覆盖模型导入不触发表结构创建、头像上传目录与静态资源挂载一致、旧头像删除路径不重复拼接，以及数据库连接串拼装使用 `DB_PASSWORD` 等关键行为。

### 修复
- **修复头像上传目录与旧文件清理路径错误**：`app/api/auth.py` 统一改为基于项目根目录定位 `uploads/avatars`，删除旧头像时先剥离已存在的 `avatars/` 前缀，避免拼出错误路径导致旧文件残留。
- **修复跨数据库 JSON 字段兼容问题**：`app/models/assessment.py` 为测评相关 JSON 字段引入 PostgreSQL/SQLite 通用类型适配，解决本地 SQLite 开发环境下 `JSONB` 无法使用的问题。
- **修复恢复答题后阶段内翻题失效问题**：`frontend/src/components/Assessment.vue` 在恢复会话时补齐当前阶段题目缓存，并移除“达到提交条件即禁止下一题”的硬拦截，允许在本阶段已答完后继续通过 `上一题`、`下一题` 浏览已答题目。
- **修复窄屏页面块级区域相互挤压问题**：收敛 `Assessment.vue`、`Chat.vue`、`Report.vue` 与全局样式中的高度、换行与横向溢出规则，避免手机端题目区、聊天头部、报告操作区和底部按钮发生覆盖或挤压。

### 优化
- **优化应用启动与建表链路**：`app/main.py` 改用 FastAPI lifespan，在显式配置 `AUTO_CREATE_TABLES` 时统一执行 `init_db()`；`app/models/__init__.py` 不再在导入时隐式建表，`docker-entrypoint.sh` 同步复用同一初始化入口。
- **优化数据库连接初始化兼容性**：`app/core/database.py` 根据数据库类型拆分引擎参数，SQLite 自动创建目录并设置 `check_same_thread=False`，PostgreSQL 连接池参数仅在非 SQLite 模式下启用。
- **优化环境示例与启动脚本文案**：`.env.example` 补齐完整数据库环境变量、可选 `DATABASE_URL` 与自动建表说明，`docker-entrypoint.sh` 的输出与数据库连通性检测统一切到新的配置读取方式。
- **优化桌面端答题页一屏展示能力**：压缩 `frontend/src/components/Assessment.vue` 桌面端头部、题干、选项区与底部操作区的间距和高度，在未展开题号列表时尽量保证常规答题内容可在电脑端不缩放状态下一屏显示。
- **优化导航与各页面响应式布局**：`frontend/src/App.vue` 调整导航栏品牌、按钮与头像的单行布局及下拉菜单交互；`frontend/src/components/Chat.vue`、`frontend/src/components/Report.vue` 与 `frontend/src/style.css` 同步收紧字号、间距和媒体元素宽度限制，提升桌面端与移动端的显示稳定性。

---

## [2026-04-16] - 前端视觉体验升级与关键 Bug 修复

### 优化
- **前端全局视觉升级**：重构 `App.vue` 样式，引入现代化明亮系毛玻璃 (Bright Glassmorphism) 视觉效果，并为背景添加动态微调的流光动画。全面提升按钮与卡片的交互反馈与阴影质感。
- **专家评审动画体验提升**：将 `Assessment.vue` 模块提交后的加载停顿动画时间从 1.5 秒延长至 5 秒，并且依次展示“唤醒评审团”、“专家分析中”、“生成阶段结论”的模拟流程，增强 AI 测评系统的高级仪式感。

### 修复
- **修复移动端测评报告排版冲突问题**：将 `Report.vue` 中的 Markdown 报告渲染由原来的固定像素 (`px`) 重构为相对层级尺寸 (`em` / `rem`)，彻底解决其在小屏设备上正文字体失真、大过标题字体的排版崩乱 Bug。
- **修复阶段评审加载页无法渲染的问题**：修复了 `Assessment.vue` 中存在的 `v-else-if` 模板判断串台隐藏 Bug，使得提交后被屏蔽的炫酷“阶段加载动画”能够重新正常工作。
- **消除答题模块重复提交与异常穿透隐患**：在前端阶段提交按钮增加了 `debounce` 式的前置防抖检验逻辑，并给按钮本体配备 Loading 图标和封锁状态，杜绝短时间内并发导致的前后端状态紊乱问题。

---

## [2026-04-15] - 构建修复、迁移增强与当前任务整理

### 修复
- **修复 Docker 依赖安装过慢与超时问题**：改为直接安装 PyTorch CPU 版 wheel，避免 `extra-index-url` 拖慢解析；补充 `pip install` 超时参数，提升镜像构建稳定性
- **修复 Debian 安全源镜像替换问题**：分别处理 `http` / `https` 的 `deb.debian.org` 与 `security.debian.org/debian-security`，避免源地址替换错误导致 `apt` 更新失败
- **修复完整依赖缺失**：为 `requirements_full.txt` 补充 `slowapi`，避免服务启动时报缺少限流依赖

### 优化
- **增强数据库迁移脚本兼容性**：迁移脚本启动时先探测现有表结构，支持 `atmr_questions` 字段补齐、`chat_messages.chat_session_id` 列补充，以及缺失时自动创建 `chat_sessions` 表
- **切换辩论模型配置**：将智谱模型从 `glm-4.7` 调整为 `glm-4.7-flash`，降低调用成本并适配当前运行配置
- **优化测评页移动端选项样式**：调整 `Assessment.vue` 中选项按钮、标签尺寸、行高与圆角，提升平板和手机端可读性

### 文档
- **补充 Agent 约束文档**：新增 `Agent.md`，明确中文回复、单作者提交、强推策略以及 Windows/PowerShell 终端约束
- **清理旧文档命名**：移除 `claude.md`
- **重写待完成任务文档**：基于当前代码库和本地测试结果重新梳理优先级，聚焦迁移体系、后台任务、前端渲染安全和自动化测试稳定性

---

## [2026-04-14] - 报告结构重构与后台任务修复

### 重构
- **答题逻辑架构重构**：从旧的「顺序选题+智能自适应选题」重构为「阶段信息+阶段选题」架构
  - 引入 `StageService` 统一管理阶段状态（intro/fixed/A/T/M/R）
  - 新增 `/stage-info` 接口获取当前阶段信息与进度
  - 自适应选题接口从 `AdaptiveQuestionRequest` 简化为仅传 `session_id`
  - 前端 `Assessment.vue` 适配新阶段体系，重构答题流程与状态管理
  - 新增 `scoring.py` 评分服务与 `stage_service.py` 阶段管理服务
  - 统一题目响应格式，新增 `question_stats` 返回题目难度、区分度等元信息

### 新增
- **报告页面重构为分维度展示**：将「证据链溯源」和「模块专家辩论」合并，每个维度（A/T/M/R）独立展示辩论结果与答题明细，新增等级标签与总分可视化

### 修复
- **修复模块 R 不触发辩论的 bug**：`submit-stage` 中模块辩论与最终报告生成的 `if/else` 互斥逻辑拆分为两个独立判断，确保四个模块均正常触发辩论
- **修复报告生成失败时前端永远显示「生成中」**：`generate_report_in_background` 超时或出错时改为向数据库写入错误提示，前端自动停止加载状态
- 报告生成超时从 300s 延长至 600s，适配 autogen 多轮辩论的 API 调用耗时

### 优化
- 移除报告中的「知识库引用」冗余段落，知识库内容仅作为 LLM 内部参考

### 修复
- **修复测评记录页面无记录时布局错位**：动态切换 `page-layout` / `page-layout--no-sidebar` class，侧边栏隐藏时主内容区不再被挤压；优化空状态展示，增加居中按钮与装饰圆圈
- **修复创建测评会话错误提示不具体**：前端 alert 改为显示后端返回的具体错误详情
- **修复模型 DateTime 字段时区不一致**：所有 `datetime.now` 默认值改为 `lambda: datetime.now(timezone.utc)`，解决 PostgreSQL `timestamptz` 列插入报错问题

---

## [2026-04-13] - RAG 检索策略升级

### 新增
- **RAG 检索升级为 LLM 语义评分**：重构 `rag_service.py`，实现三阶段检索架构（关键词粗筛 → LLM 语义批量评分 → 内容提取），新增相关性阈值过滤与兜底机制，提升复杂查询召回准确率

---

## [2026-04-12] - 全面清理与重构 + 文档完善

### 重构
- **拆分 `assessment.py`（1500行）为 5 个模块**：`sessions.py`、`questions.py`、`submissions.py`、`streaming.py`、`schemas.py`
- **PageIndex 模块全面重构**：优化 `page_index.py`、`page_index_md.py`、`client.py`、`retrieve.py`、`utils.py` 等核心文件
- 创建 `app/core/database.py` 统一 `get_db()` 依赖注入
- 创建 `app/core/constants.py` 集中管理 `MODULE_DIM_MAP` 等硬编码常量
- Agent 辩论管理器（`debate_manager.py`）代码优化
- 消除重复代码：删除 `auth.py`/`chat.py` 中重复的 `get_db()`，统一引用共享常量

### 新增
- **全面优化移动端显示效果和响应式设计**：重构 `App.vue`、`Assessment.vue`、`Chat.vue`、`History.vue`、`Login.vue`、路由与 Vite 配置
- **引入 pytest 测试框架**：新增 28 个单元测试覆盖 `ai_detector` 和 `question_selection`
- 用 `pyproject.toml` 替代多份 `requirements.txt` 统一依赖管理
- 配置 pre-commit hooks（ruff lint + format）自动代码格式化

### 其他
- 清理项目根目录废弃文件：移除旧版 `DEPLOY.md`、`README_ADAPTIVE_SYSTEM.md`、`deploy_adaptive_system.py`、`atmr_full_questions.json` 及多个一次性脚本，统一迁移至 `scripts/` 目录
- 新增 `data/`、`scripts/`、`uploads/` 目录结构
- 更新 Dockerfile 与 `docker-entrypoint.sh` 配置
- 迁移部署文档至 `docs/DEPLOY.md`
- 更新 .gitignore 忽略规则、LICENSE 文件
- 规范 README 文档结构与内容
- 更新评分标准文档与项目配置
- 完善待完成任务文档

### 文档
- **新增开发者日志**（`docs/开发者日志.md`）：可直接用于毕设论文的完整系统设计与实现文档
- 完善 CHANGELOG 记录全部 commit，更新 CLAUDE.md 文件管理规则
- 明确禁止在提交中添加 Claude 贡献者信息

### 修复
- 修复 PageIndex 示例代码与 Jupyter Notebook 中的兼容性问题

---

## [2026-04-11] - 任务完成与 CI 修复

### 优化
- **异常检测算法全面升级**：从简单的「时间低于阈值即判定异常」升级为多维风险评分系统
  - 新增时间过快/偏快/过慢/连续快速作答/重复选项等多维度检测
  - 累计风险评分（0-100），阈值 45 触发异常
  - 根据异常类型动态生成差异化追问文本
- **答题接口增强**：`AnswerSubmitResponse` 新增 `risk_score` 和 `risk_reasons` 字段，支持最近答题上下文传递
- **清理废弃接口**：移除旧的 `/submit_explanation` 和重复的 `/finish` 接口
- **聊天持久化**：聊天记录持久化存储，优化 `Chat.vue` 与 `chat.py`
- **前端统一优化**：优化 `History.vue`、`Report.vue`、`App.vue`、`style.css`

### 修复
- 题目列表所有题号可见可点击，未加载的题点击自动加载

### 文档
- 完善项目文档和许可证：添加 `LICENSE`，更新 README、工作日志、微服务任务文档、测试目标文档
- 更新评分标准文档，替换旧版工作记录

### 其他
- 修复 Gitee 同步与 GitHub Actions 工作流配置：将 `,github/` 重命名为 `.github/`，修复工作流路径
- 忽略 Vite 构建缓存目录

---

## [2026-04-10] - 断点续答、辩论动画与 Docker 部署

### 新增
- **断点续答功能**：答题进度实时保存，支持中途退出后继续作答
- **答案修改**：已完成测评支持修改答案并重新提交
- **模块提交按钮**：模块答完后显示手动提交按钮，立即触发该模块辩论
- **可折叠题目导航列表**：点击序号直接跳转到对应题目
- **历史记录新增 ATMR 维度分数**：`/history` 接口批量查询题目维度信息，计算各维度得分百分比

### 优化
- **辩论动画改造**：隐藏辩论过程文字，改为轨道动画显示"专家辩论中"，去掉模块结论截断
- 优化 PC 端页面布局，充分利用屏幕空间
- 优化历史记录 ATMR 维度分数展示
- 模块辩论 prompt 字数限制统一为 400 字，截断长度增至 600

### 修复
- **修复 Docker 依赖管理与构建问题**：PyTorch 源移至 Dockerfile 避免干扰 pip 镜像解析，apt 源替换兼容新旧版 Debian
- autogen 改为可选依赖，缺失时优雅降级
- 恢复完整依赖，torch 改用 CPU 版减小体积
- 优化 Nginx SSE 代理配置，添加长连接必需的 HTTP/1.1 和 Connection 头
- 修复 Decimal 类型无法 JSON 序列化导致辩论服务崩溃的问题

---

## [2026-04-09] - 自适应选题与 Docker 部署

### 新增
- **Docker 一键部署配置**：新建 `Dockerfile`、`docker-compose.yml`、`docker-entrypoint.sh`、`.env.example`
- **Gitee 自动同步**：GitHub Actions 同步工作流，添加自动更新脚本
- 前端 Dockerfile Node 版本升级到 20（Vite 8 要求）
- Docker 构建使用国内镜像源加速
- 添加 agent 模块到 Docker 镜像
- 优化 PC 端页面布局与历史记录分数展示
- 优化服务器部署，去掉 PyTorch 等大依赖

### 修复
- **修复自适应选题流程与 PostgreSQL 兼容性问题**：新建 `question_selection.py`、`rag_service.py`、`security.py`

### 其他
- 清理旧版 SQLite 迁移脚本（`migrate_to_postgresql.py`、`cleanup_database.py` 等）

---

## [2026-04-05] - PageIndex 集成与身份验证

### 新增
- **PageIndex RAG 检索引擎集成**：包含 agentic retrieval、chat quickstart、simple RAG、vision RAG 等 Cookbook 示例
- **身份验证模块**：新建 `auth.py` 及登录页面
- **聊天功能**：新建 `chat.py` 及 `Chat.vue` 组件

---

## [2026-03-27] - SSE 流式架构

### 重构
- **迁移到流式辩论架构，实现 SSE 推送**：重构 `debate_manager.py`、`assessment.py`、`ai_detector.py`、`report_service.py`，支持服务端推送实时辩论结果
- 移除旧同步逻辑，迁移到纯流式辩论架构

### 其他
- 更新 .gitignore，停止跟踪数据库文件（`atmr_data.db`）

---

## [2026-03-26] - 后端答题服务与前端

### 新增
- **后端答题服务**：新建 `app/api/assessment.py`、`app/core/config.py`、`app/main.py`
- **多 LLM 驱动辩论**：新建 `app/services/ai_detector.py`，三个智能体改为不同的 LLM 来驱动
- **题库系统**：新增题库和处理脚本
- **前端网页与答题记录存储**：基于 Vue + Vite 搭建前端，新增 `Assessment.vue` 组件、答题记录模型、报告服务 `report_service.py`

### 优化
- 更新 main 服务器逻辑

---

## [2026-03-12] - 项目文档

### 文档
- 添加毕设项目文档：需求分析和概要设计、开发目标和进度、测试目标和进度

---

## [2026-03-11] - 项目初始化

### 新增
- 初始化毕设项目，搭建多智能体对话实验环境
