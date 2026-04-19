# ATMR 智能心理测评系统

![License](https://img.shields.io/badge/License-CC%20BY--NC--SA%204.0-orange.svg)
![Python](https://img.shields.io/badge/Python-3.10-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-yellow.svg)
![Vue](https://img.shields.io/badge/Vue-3.5+-brightgreen.svg)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-orange.svg)

基于 **多智能体辩论** 和 **自适应题目选择** 的 AI 心理测评系统。系统融合贝叶斯能力估计、异常作答检测、RAG 知识库检索和大语言模型，实现对被试者 **态度(A)**、**情绪(T)**、**认知(M)**、**韧性(R)** 四个维度的智能化心理评估。

## 目录

- [技术栈](#技术栈)
- [核心功能](#核心功能)
- [测评流程](#测评流程)
- [快速开始](#快速开始)
  - [Docker 部署](#docker-部署推荐)
  - [本地开发](#本地开发)
- [环境变量](#环境变量)
- [项目结构](#项目结构)
- [API 概览](#api-概览)
- [评分机制](#评分机制)
- [常见问题](#常见问题)
- [部署教程](#部署教程)
- [License](#license)

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | FastAPI + Uvicorn + SQLAlchemy 2.0 |
| 前端 | Vue 3 + Vite + Vue Router + Chart.js |
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
  → AI 心理咨询对话
```

## 快速开始

### 前置要求

- Python 3.10+
- Node.js 18+
- PostgreSQL 15 (或使用 Docker)
- Docker & Docker Compose (推荐部署方式)

### Docker 部署 (推荐)

```bash
# 1. 克隆项目
git clone <仓库地址>
cd TestAgent

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，至少修改 DB_PASSWORD 和 SECRET_KEY

# 3. 启动服务
docker compose up -d --build
```
Note: Docker defaults to `requirements_full.txt`, then installs
`requirements_feature.txt` in a second step. This keeps general packages
on the main mirror and only lets Torch CPU use the PyTorch extra index.
If you only want a lighter first deployment, you can manually switch
`REQUIREMENTS_FILE` to `requirements_server.txt`.

如果你的服务器拉取 `postgres:15-alpine` 很慢，可在 `.env` 中把 `POSTGRES_IMAGE` 改成你自己的镜像仓库地址。当前 Docker 默认先安装 `requirements_full.txt`，再单独安装 `requirements_feature.txt`，这样普通依赖仍走主镜像，`torch` 才会使用 PyTorch CPU 额外索引。如果你只想先部署在线服务、暂时不生成题目特征向量，也可以手动把 `REQUIREMENTS_FILE` 改成 `requirements_server.txt`。

启动后会自动完成：
- 等待 PostgreSQL 就绪
- 自动建表
- 题库为空时自动导入 `data/atmr_full_questions.json`

启动后访问：
- 前端：<http://localhost>
- 上传文件：`/uploads/...` 将通过前端 Nginx 反向代理到后端

默认情况下，后端 `8000` 端口不会暴露到宿主机，所以不能直接访问 Swagger。
如果你需要直接查看 API 文档，请在 `docker-compose.yml` 的 `backend` 服务中添加：

```yaml
ports:
  - "8000:8000"
```

然后重新执行：

```bash
docker compose up -d --build backend frontend
```

此时可访问：
- 后端 API 文档：<http://localhost:8000/docs>
- 后端健康检查：<http://localhost:8000/health>

> 首次构建需要 5-15 分钟（下载镜像 + 安装依赖），请耐心等待。
> 当前项目没有预置测试账号，首次使用请在登录页自行注册。

### 本地开发

```bash
# 1. 安装后端依赖
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements_full.txt
python -m pip install -r requirements_feature.txt

# `requirements_feature.txt` 这一层会补充 `sentence-transformers` 和 `torch==...+cpu`
# 并把 PyTorch 额外索引限制在这一步，避免常规依赖解析到非主镜像

# 2. 准备环境变量
cp .env.example .env

# 3. 启动后端
# 默认开发环境会使用 SQLite：data/testagent_dev.db
# 如果题库为空，后端启动后会自动建表并导入题库
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 4. 新终端中启动前端
cd frontend
npm install
npm run dev
```

如需启用更完整的自适应选题能力，可在项目根目录额外执行：

```bash
python scripts/generate_feature_vectors.py
```

开发环境地址：
- 后端：<http://127.0.0.1:8000>
- 前端：<http://127.0.0.1:5173>

## 环境变量

复制 `.env.example` 为 `.env` 后填写：

```env
# === 数据库密码（必填）===
DB_PASSWORD=your_secure_password

# === Docker 镜像与依赖源（可选）===
POSTGRES_IMAGE=postgres:15-alpine
PYTHON_IMAGE=python:3.10-slim
PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/
REQUIREMENTS_FILE=requirements_full.txt

# === JWT 签名密钥（必填）===
SECRET_KEY=your_random_secret_key

# === AI 功能密钥（选填）===
DEEPSEEK_API_KEY=sk-xxx
DASHSCOPE_API_KEY=
ZHIPU_API_KEY=
```

| 变量 | 必填 | 说明 |
|------|------|------|
| `DB_PASSWORD` | 是 | PostgreSQL 数据库密码 |
| `SECRET_KEY` | 是 | JWT 签名密钥 |
| `DEEPSEEK_API_KEY` | 否 | DeepSeek API 密钥，用于多智能体辩论和 AI 咨询 |
| `DASHSCOPE_API_KEY` | 否 | 阿里云通义千问密钥（备选模型） |
| `ZHIPU_API_KEY` | 否 | 智谱 AI 密钥（备选模型） |
| `POSTGRES_IMAGE` | 否 | 覆盖 PostgreSQL 镜像地址，适合替换成自建或内网镜像仓库 |
| `PYTHON_IMAGE` | 否 | 覆盖后端基础镜像地址，适合替换成自建或内网镜像仓库 |
| `PIP_INDEX_URL` | 否 | 普通 Python 依赖使用的索引地址 |
| `REQUIREMENTS_FILE` | 否 | Docker 后端镜像安装的依赖文件，默认 `requirements_full.txt` |

补充说明：

- 默认 Docker 部署不需要手工填写 `DATABASE_URL`，`docker-compose.yml` 会自动注入容器内连接串
- 默认本地开发环境会走 SQLite，数据库文件位于 `data/testagent_dev.db`
- `uploads/` 在 Docker 部署中已通过独立卷持久化，重建 `backend` 容器后仍会保留上传文件
- `REQUIREMENTS_FILE` 默认是 `requirements_full.txt`，包含当前后端启动所需的完整依赖
- `requirements_feature.txt` 单独承载 `sentence-transformers` 与 `torch==...+cpu`，用于避免常规依赖解析到 PyTorch 额外索引
- `requirements_server.txt` 是可选的轻量运行时依赖集合，包含 API、RAG、限流和多智能体辩论依赖，但不会安装题目特征向量生成所需的 `torch/sentence-transformers`

## 项目结构

```
TestAgent/
├── app/                          # FastAPI 后端
│   ├── main.py                   # 应用入口
│   ├── api/                      # 路由层
│   │   ├── auth.py               #   用户注册/登录 (JWT)
│   │   ├── assessment.py         #   测评流程 (选题/答题/完成)
│   │   ├── chat.py               #   AI 心理咨询对话
│   │   └── rag.py                #   RAG 语义检索接口
│   ├── models/                   # SQLAlchemy 数据模型
│   │   └── question.py           #   题目/用户/测评记录等
│   ├── schemas/                  # Pydantic 数据校验
│   │   └── payload.py            #   请求/响应结构定义
│   ├── services/                 # 业务逻辑层
│   │   ├── question_selection.py #   自适应选题算法
│   │   ├── ai_detector.py        #   异常作答检测
│   │   ├── report_service.py     #   测评报告生成
│   │   ├── rag_service.py        #   RAG 检索服务
│   │   ├── stage_service.py      #   阶段管理服务
│   │   ├── debate_manager.py     #   AutoGen 三方辩论编排
│   │   └── scoring.py            #   评分计算服务
│   ├── models/                   # ORM 模型
│   │   ├── user.py               #   用户模型
│   │   ├── assessment.py         #   测评相关模型
│   │   └── chat.py               #   聊天相关模型
│   └── core/                     # 配置与安全
│       ├── config.py             #   环境变量与全局配置
│       ├── security.py           #   JWT 认证 + 密码加密
│       ├── database.py           #   数据库连接与会话管理
│       └── limiter.py            #   API 限流
│
├── PageIndex/                    # RAG 知识库检索引擎
│   ├── pageindex/                # 核心模块
│   │   ├── page_index.py         #   语义索引构建
│   │   ├── page_index_md.py      #   Markdown 文档索引
│   │   ├── retrieve.py           #   语义检索
│   │   └── client.py             #   检索客户端
│   ├── ask.py                    # 问答接口
│   └── run_pageindex.py          # 独立运行入口
│
├── frontend/                     # Vue 3 前端
│   ├── src/
│   │   ├── App.vue               # 根组件
│   │   ├── main.js               # 应用入口
│   │   ├── api.js                # Axios API 封装
│   │   ├── router/index.js       # 路由配置
│   │   ├── style.css             # 全局样式
│   │   └── components/
│   │       ├── Login.vue         #   登录/注册页
│   │       ├── Assessment.vue    #   测评答题页
│   │       ├── Report.vue        #   测评报告页 (雷达图)
│   │       ├── Chat.vue          #   AI 心理咨询对话页
│   │       └── History.vue       #   历史测评记录页
│   ├── vite.config.js            # Vite 构建配置
│   ├── index.html                # HTML 入口
│   └── package.json              # 前端依赖
│
├── docs/                         # 项目文档
│   ├── 评分标准.md               # 测评评分规则
│   ├── 毕设开发目标和进度.md      # 开发计划
│   ├── 待完成任务.md             # TODO 清单
│   ├── 工作日志.md               # 开发日志
│   └── DEPLOY.md                 # 从零部署详细教程
│
├── data/                         # 数据文件
│   └── atmr_full_questions.json  # ATMR 四维题库
│
├── scripts/                      # 工具脚本
│   ├── import_data.py            # 题库导入脚本
│   ├── generate_feature_vectors.py # Sentence-Transformers 特征向量生成
│   ├── migrate_database.py       # 数据库迁移脚本
│   ├── check_feature_status.py   # 特征向量状态检查
│   ├── monitor_selection.py      # 选题过程监控
│   └── test_adaptive_selection.py # 自适应选题单元测试
│
├── uploads/                      # 静态文件 (RAG 上传文档等)
│
├── requirements_full.txt         # Python 完整依赖
├── requirements_server.txt       # Python 服务器精简依赖
├── requirements_feature.txt      # Python 特征向量依赖
│
├── Dockerfile                    # 后端 Docker 镜像
├── docker-compose.yml            # 服务编排 (db + backend + frontend + uploads 卷)
├── docker-entrypoint.sh          # 后端容器启动脚本
├── README.md                     # 本文件
└── LICENSE                       # MIT 许可证
```

## API 概览

| 模块 | 端点 | 说明 |
|------|------|------|
| 认证 | `POST /api/v1/auth/register` | 用户注册 |
| | `POST /api/v1/auth/login` | 用户登录，返回 JWT |
| 测评 | `POST /api/v1/assessment/start-session` | 创建测评会话 |
| | `POST /api/v1/assessment/adaptive-question` | 获取自适应选题 |
| | `POST /api/v1/assessment/save-answer` | 保存作答答案 |
| | `POST /api/v1/assessment/finish-module` | 完成模块，触发辩论分析 |
| | `POST /api/v1/assessment/finish-session` | 完成测评，生成报告 |
| 对话 | `POST /api/v1/chat/message` | AI 心理咨询对话 |
| 知识库 | `POST /api/v1/rag/query` | RAG 语义检索查询 |

> 完整 API 文档：仅在后端 `8000` 端口已暴露时访问 <http://localhost:8000/docs>

## 评分机制

系统采用 **1-5 分李克特量表**，每个维度 10 道题，基础满分 50 分。

| 等级 | 分数区间 | 含义 |
|------|----------|------|
| 偏低（潜伏特质） | 10 - 23 分 | 该维度特征表现不明显 |
| 中等（情境特质） | 24 - 37 分 | 具备基础特征，特定情境下展现 |
| 偏高（显性主导） | 38 - 50 分 | 典型行为模式，表现强烈稳定 |

前两道固定题作为**加权调节机制**，根据作答组合对对应维度加 2 分（总分不超过 50 分封顶显示）。




## 部署教程

当前版本的服务器部署说明、端口暴露策略、自动初始化行为和运维命令，请参阅 [docs/DEPLOY.md](docs/DEPLOY.md)。

## License

本项目采用 [CC BY-NC-SA 4.0](LICENSE) 许可证 — 允许学习、修改和分享，但**禁止商业用途**，修改后的作品也必须使用相同许可证。
