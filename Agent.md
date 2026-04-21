# 仓库协作规则

## 基本要求

- 所有对用户的回复都使用中文。
- Git 提交只允许一个作者：`cyancliff <213222750@seu.edu.cn>`。
- 提交信息中不要出现 `Co-Authored-By` 或任何 co-author 行。
- `CHANGELOG.md` 必须保留在仓库根目录，不要移动到 `docs/`。

## Windows / PowerShell 约束

- 本项目默认运行在 Windows 环境下。
- 如需执行终端命令，只能使用 Windows PowerShell 语法。
- 不要假设存在 Linux / Unix 命令。
- 做路径、脚本和部署说明时，优先给出 PowerShell 版本命令。

## 文档协作要求

- 修改功能时，优先同步以下文档是否需要更新：
  - `README.md`
  - `CHANGELOG.md`
  - `docs/毕设开发目标和进度.md`
  - `docs/待完成任务.md`
  - 对应子系统自己的 `README`
- 文档中要明确区分：
  - 已完成
  - 已跑通 baseline
  - 正在运行
  - 尚未接入主系统

## 多模态特别说明

- 多模态离线链路和在线主系统不是同一条运行路径。
- 当前在线多模态服务仍是 `scaffold-v1` 占位分数，真实 checkpoint 还没有接入。
- 如果仓库里存在正在运行的全量多模态长任务：
  - 不要删除 `uploads/multimodal_personality/artifacts`
  - 不要删除 `reports/full_multimodal_pipeline`
  - 不要随意关闭对应的黑色 `python.exe` 宿主窗口

## Git 与历史

- 如需强推，直接使用 `git push --force`。
- 不要在提交历史里制造双作者格式。
- 变更较大时，先保证文档与代码状态一致，再提交。
