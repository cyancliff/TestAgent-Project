# Agent 特殊要求

本文件只记录本仓库区别于通用开发流程的特殊要求。项目介绍、启动方式和普通开发说明不要写在这里，放到 `README.md` 或 `docs/` 中。

## 回复与终端

- 所有对用户的回复都使用中文。
- 默认工作环境是 Windows + PowerShell。
- 给出终端命令时优先使用 PowerShell 写法。
- 不要假设存在 Linux / Unix 命令。

## Git 提交

- Git 提交只允许一个作者：`cyancliff <213222750@seu.edu.cn>`。
- 提交信息中不要出现 `Co-Authored-By` 或任何 co-author 行。
- 不要制造双作者、共同作者或 AI 署名格式。
- 如维护者明确要求强推，按仓库约定使用 `git push --force`。
- 提交前先区分已有改动和本次改动，不要回退他人尚未提交的修改。

## 文档位置

- 功能或状态变化时，检查是否需要同步：
  - `CHANGELOG.md`
  - `README.md`
  - `docs/开发者日志.md`
  - `multimodal_personality/README.md`
