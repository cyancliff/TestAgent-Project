# ATMR 智能心理测评系统

![License](https://img.shields.io/badge/License-MIT-green.svg) ![Python](https://img.shields.io/badge/Python-3.9+-blue.svg) ![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-yellow.svg) ![Vue](https://img.shields.io/badge/Vue-3.3+-brightgreen.svg) ![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-orange.svg)

基于 **多智能体辩论** 和 **自适应题目选择** 的 AI 心理测评系统。系统融合贝叶斯能力估计、异常检测、RAG 知识库检索和大语言模型，实现对被试者态度(A)、情绪(T)、认知(M)、韧性(R) 四维度的智能化心理评估。

- [技术栈](#技术栈)
- [核心功能](#核心功能)
- [测评流程](#测评流程)
- [快速开始](#快速开始)
- [项目结构](#项目结构)
- [API概览](#api概览)
- [环境变量](#环境变量)
- [贡献](#贡献)
- [常见问题](#常见问题)
- [License](#license)

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | FastAPI + Uvicorn + SQLAlchemy 2.0 |
| 前端 | Vue 3 + Vite + Chart.js |
| 数据库 | PostgreSQL 15 |
| AI/ML | DeepSeek API · Sentence-Transformers · AutoGen |
| 知识库 | PageIndex (RAG 语义检索) |
| 部署 | Docker Compose + Nginx |

## 核心功能

### 自适应题目选择
基于贝叶斯能力估计动态选题，综合特征匹配(40%)、难度匹配(30%)、区分度(30%) 三维评分，并引入 Fisher 信息量和覆盖度评估，确保测评的精准性与多样性。

### 异常作答检测
实时监测作答时间、连续快速作答、重复选项等异常模式。触发异常时自动生成追问题，要求被试者补充说明，保障测评数据质量。

### 多智能体辩论
每个维度模块完成后，由三个 AI 智能体展开辩论分析：
- **心理学专家** — 从心理学理论角度分析作答表现
- **风控专家** — 质疑潜在风险与替代解释
- **裁决官** — 综合双方论点得出最终结论

### RAG 知识库
集成 ATMR 心理学理论文档，通过语义检索为辩论、报告生成和 AI 咨询提供循证依据。

### AI 心理咨询师
测评完成后提供基于测评结果的多轮对话咨询，结合 RAG 知识库给出专业建议。

### 断点续答
答题进度实时保存，支持中途退出后继续作答，已完成测评也支持修改答案并重新提交。

## 测评流程

```
注册/登录 → 开始测评 → 固定题(2题)
  → A模块(10题) → 异常检测 → 辩论分析
  → T模块(10题) → 异常检测 → 辩论分析
  → M模块(10题) → 异常检测 → 辩论分析
  → R模块(10题) → 异常检测 → 辩论分析
  → 生成综合报告(雷达图 + 维度分析)
  → AI心理咨询对话
```

## 快速开始

### Docker 部署 (推荐)

```bash
# 1. 克隆项目
git clone <仓库地址>  # 请将 <仓库地址> 替换为实际 URL
cd TestAgent

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，修改 DB_PASSWORD、SECRET_KEY，填写 DEEPSEEK_API_KEY

# 3. 启动服务
docker compose up -d --build

# 访问：http://localhost (前端) | http://localhost:8000/docs (API文档)
```

### 环境变量配置

请复制 `.env.example` 为 `.env` 并填写必要的密钥：

```bash
cp .env.example .env
```

编辑 `.env` 文件，内容示例：

```env
# === 数据库密码（必填，请修改为你自己的密码）===
DB_PASSWORD=your_secure_password

# === JWT 密钥（必填，请修改为一个随机字符串）===
SECRET_KEY=your_random_secret_key

# === AI 功能密钥（选填，不填则 AI 对话功能不可用）===
DEEPSEEK_API_KEY=sk-xxx
DASHSCOPE_API_KEY=
ZHIPU_API_KEY=
```

**注意**：
- `DB_PASSWORD` 和 `SECRET_KEY` 必须填写
- `DEEPSEEK_API_KEY` 可选，但如果不填，多智能体辩论和 AI 咨询功能将无法使用
- 其他 AI 密钥可选，用于备选模型

### 本地开发

```bash
# 后端
pip install -r requirements_full.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 前端 (新终端)
cd frontend
npm install
npm run dev

# 初始化数据
python import_data.py                  # 导入题库
python generate_feature_vectors.py     # 生成特征向量
```

**开发环境访问**：后端 http://127.0.0.1:8000 | 前端 http://127.0.0.1:5173

## 项目结构

```
TestAgent/
├── app/                        # FastAPI 后端
│   ├── api/                    # 路由 (assessment, auth, chat, rag)
│   ├── models/                 # SQLAlchemy 数据模型
│   ├── services/               # 业务逻辑 (选题算法, 异常检测, 报告生成, RAG)
│   ├── schemas/                # Pydantic 数据校验
│   ├── core/                   # 配置与安全 (JWT, bcrypt)
│   └── main.py                 # 应用入口
├── agent/                      # 多智能体辩论系统 (AutoGen)
├── frontend/                   # Vue 3 前端
│   └── src/components/         # Assessment, Report, Chat, History, Login
├── PageIndex/                  # RAG 知识库检索引擎
├── docs/                       # 项目文档
├── docker-compose.yml          # Docker 编排
├── Dockerfile                  # 后端镜像
└── import_data.py              # 题库导入脚本
```

## API 概览

| 模块 | 端点 | 说明 |
|------|------|------|
| 认证 | `POST /api/v1/auth/register` | 用户注册 |
| | `POST /api/v1/auth/login` | 登录获取 JWT |
| 测评 | `POST /api/v1/assessment/start-session` | 创建测评 |
| | `POST /api/v1/assessment/adaptive-question` | 自适应选题 |
| | `POST /api/v1/assessment/save-answer` | 保存答案 |
| | `POST /api/v1/assessment/finish-module` | 完成模块(触发辩论) |
| | `POST /api/v1/assessment/finish-session` | 完成测评(生成报告) |
| 对话 | `POST /api/v1/chat/message` | AI 咨询对话 |
| 知识库 | `POST /api/v1/rag/query` | RAG 语义检索 |

完整 API 文档：启动后端后访问 http://localhost:8000/docs

## 环境变量

| 变量 | 必填 | 说明 |
|------|------|------|
| `DB_PASSWORD` | 是 | PostgreSQL 数据库密码 |
| `SECRET_KEY` | 是 | JWT 签名密钥 |
| `DEEPSEEK_API_KEY` | 否 | DeepSeek API 密钥 (AI 功能) |
| `DASHSCOPE_API_KEY` | 否 | 阿里云通义千问密钥 |
| `ZHIPU_API_KEY` | 否 | 智谱 AI 密钥 |

## 常见问题

### 1. 如果没有 DeepSeek API 密钥，系统还能运行吗？
可以，但多智能体辩论和 AI 咨询功能将无法使用。测评流程、自适应选题、异常检测等核心功能仍可正常工作。

### 2. 如何重置数据库？
停止 Docker 服务后删除 `postgres_data` 目录，重新启动即可。

### 3. 如何导入自定义题库？
修改 `atmr_full_questions.json` 文件后，运行 `python import_data.py` 重新导入。

### 4. 如何修改测评模块的题目数量？
在 `app/services/adaptive_selection.py` 中调整 `MODULE_QUESTION_COUNT` 常量。

## License

本项目采用 [MIT License](LICENSE)。您可以在遵守以下条件的情况下自由使用、修改和分发本软件：

### 主要条款
1. **自由使用** – 允许商用、私用、修改、分发
2. **保留版权声明** – 所有副本必须包含原版权声明和许可声明
3. **免责声明** – 软件按"原样"提供，不承担任何保证责任
4. **责任限制** – 作者不对因使用本软件导致的任何索赔或损害负责

完整的许可证文本请参阅 [LICENSE](LICENSE) 文件。

<!-- GitHub Actions 工作流测试 @ 2026-04-11 -->
