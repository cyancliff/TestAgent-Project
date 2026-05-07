# 项目优化建议

基于对整个项目的全面审查，以下按优先级从高到低列出优化建议。

---

## 高优先级

### 1. 移除硬编码的数据库密码

[alembic.ini](alembic.ini) 第 3 行明文写死了数据库连接字符串 `postgresql://postgres:123456@localhost:5432/atmr_db`。应改为从环境变量读取：

```ini
sqlalchemy.url = %(DATABASE_URL)s
```

### 2. 生产环境收紧 CORS 配置

[app/core/config.py](app/core/config.py) 中 `ALLOWED_ORIGINS = ["*"]` 在生产环境过于宽松。建议按环境区分：

```python
ALLOWED_ORIGINS: list[str] = ["*"] if APP_ENV != "production" else ["https://your-domain.com"]
```

### 3. 用 Alembic 替代启动时自动迁移

[app/models/__init__.py](app/models/__init__.py) 中的 8 个 `_ensure_*_column()` 函数在每次应用启动时运行 `ALTER TABLE`，这种方式脆弱且不可追溯。应：

- 为每项 schema 变更创建 Alembic 迁移脚本
- 在部署流程中执行 `alembic upgrade head`，而不是启动时自动检测
- 删除 `_ensure_*_column()` 函数

---

## 中优先级

### 4. 拆分巨型前端组件

四个 Vue 组件超过 1500 行，严重影响可维护性：

| 文件 | 行数 | 建议 |
|------|------|------|
| [History.vue](frontend/src/components/History.vue) | 2,413 | 拆出 `HistoryCard`、`HistoryFilter`、`HistoryChart` 子组件 |
| [Chat.vue](frontend/src/components/Chat.vue) | 1,934 | 拆出 `ChatMessage`、`ChatInput`、`ChatSidebar` 子组件 |
| [Assessment.vue](frontend/src/components/Assessment.vue) | 1,773 | 拆出 `QuestionCard`、`ProgressBar`、`OptionSelector` 子组件 |
| [BigFiveReport.vue](frontend/src/components/BigFiveReport.vue) | 1,541 | 拆出 `RadarChart`、`TraitDetail`、`EvidenceList` 子组件 |

### 5. 拆分 `chat.py` 路由文件

[app/api/chat.py](app/api/chat.py) 共 981 行，同时承担了聊天 CRUD、报告加载、流式 LLM 调用和 RAG 上下文构建。建议：

- 提取报告加载逻辑到 `app/services/chat_report_service.py`
- 提取流式响应构建到 `app/services/chat_stream_service.py`
- 路由文件只保留端点定义和参数校验

### 6. 统一并发模型

[app/services/debate_manager.py](app/services/debate_manager.py) 同时使用了 `threading.Thread`、`asyncio.run()`、`concurrent.futures.ThreadPoolExecutor` 和 `queue.Queue`，四种并发原语交织在一起。建议：

- 统一为 `asyncio` + `TaskGroup`（Python 3.11+）模式
- 或统一使用 `concurrent.futures` 线程池，将 asyncio 调用隔离到单独模块
- 至少将 LLM 调用抽取为可测试的异步函数，而非嵌套的 `asyncio.run()`

### 7. 修复异常作为控制流的写法

[app/main.py](app/main.py) 中用 `try/except Exception` 包裹 `multimodal_personality` 的导入（会吞掉语法错误、缺失依赖、权限错误等）。建议：

```python
# 用 importlib 精确检查，仅捕获 ImportError
try:
    from importlib.util import find_spec
    if find_spec("multimodal_personality"):
        from multimodal_personality.api import router as mp_router
        app.include_router(mp_router, ...)
except ImportError:
    pass
```

---

## 低优先级

### 8. 增加前端测试

前端约 9,500 行代码完全没有测试。建议至少：

- 引入 Vitest 做组件单元测试
- 对 `Assessment.vue`（核心答题流程）和 `Report.vue`（报告展示）优先补充测试
- 引入 Playwright 做关键路径的 E2E 测试

### 9. 增加后端集成测试

当前 19 个测试文件全部使用 mock，没有真正的数据库或 HTTP 测试。建议：

- 使用 SQLite 内存数据库做服务层集成测试
- 使用 `TestClient` + `pytest-asyncio` 做 API 层集成测试
- 优先覆盖：答题提交流程、报告生成流程、认证流程

### 10. 启用 unused-import 检查

[pyproject.toml](pyproject.toml) 中 Ruff 配置了 `"F401"` 忽略规则，会放过死代码。建议移除该忽略项，清理现有未用导入后重新启用。

### 11. 整理实验脚本和报告目录

`scripts/`（42 个脚本，5,041 行）和 `reports/`（20 个实验运行目录）缺乏组织。建议：

- 将活跃使用的脚本与一次性实验脚本分开
- 为脚本添加 `if __name__ == "__main__"` 入口和使用说明
- 将不再需要的实验报告归档或删除

---

## 总结

| 优先级 | 建议 | 影响范围 |
|--------|------|---------|
| 高 | 移除硬编码密码 | 安全 |
| 高 | 收紧 CORS | 安全 |
| 高 | 用 Alembic 替代自动迁移 | 可靠性 |
| 中 | 拆分巨型前端组件 | 可维护性 |
| 中 | 拆分 chat.py | 可维护性 |
| 中 | 统一并发模型 | 可维护性/可靠性 |
| 中 | 修复异常控制流 | 可靠性 |
| 低 | 前端测试 | 质量保障 |
| 低 | 后端集成测试 | 质量保障 |
| 低 | 启用 unused-import 检查 | 代码质量 |
| 低 | 整理实验脚本 | 工程规范 |
