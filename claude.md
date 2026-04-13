# 最关键的注意事项
- 你的所有回答都要使用中文
- git 提交只允许一个作者 `cyancliff <213222750@seu.edu.cn>`，不要出现 `authored and X committed` 的双人格式
- 禁止在提交信息中包含 `Co-Authored-By` 或任何 co-author 行
- 如需 force push（如 rebase 修改了历史），推送时直接 `git push --force`
- CHANGELOG.md 保持在项目根目录，不要移动到 docs/
- CLAUDE.md 需要提交到仓库，不要加入 .gitignore
# 操作系统与终端规则 (OS & Terminal Rules)
- **IMPORTANT**: 本项目运行在 Windows 环境下。
- **NEVER**: 绝对不要使用 Linux/Unix 命令（如 `ls`, `grep`, `cat`, `find`, `2>/dev/null`）。
- 如果需要执行终端命令，必须且只能使用 Windows PowerShell 语法。
- 如果需要查找或读取文件内容，请直接使用 PyCharm/Agent 内置的文件读取能力，不要试图通过终端命令（如 `cat` 或 `Get-Content`）输出文件内容。