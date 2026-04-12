# 更新日志

## [Unreleased] - 2026-04-12

### Refactor
- PageIndex 模块全面重构：优化 `page_index.py`、`page_index_md.py`、`client.py`、`retrieve.py`、`utils.py` 等核心文件
- 清理废弃脚本：移除 `atmr_full_questions.json`、`check_feature_status.py`、`deploy_adaptive_system.py`、`generate_feature_vectors.py`、`import_data.py`、`migrate_database.py`、`monitor_selection.py`、`test_adaptive_selection.py`
- Agent 辩论管理器 (`debate_manager.py`) 代码优化

### Docs
- 更新 README.md 项目说明
- 更新 Claude 配置文档 (CLAUDE.md)
- 迁移部署文档至 `docs/DEPLOY.md`
- 更新微服务任务文档与设计开发文档

### Chore
- 更新 Dockerfile 与 docker-entrypoint.sh 配置
- 更新 .gitignore 忽略规则
- 更新 LICENSE 文件
- 新增 `data/`、`scripts/`、`uploads/` 目录

### Fix
- 修复 PageIndex 示例代码与 Jupyter Notebook 中的兼容性问题
