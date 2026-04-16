# TestAgent 部署教程（当前版本）

本文基于仓库当前的 `docker-compose.yml`、`Dockerfile`、`docker-entrypoint.sh` 和前端 `nginx.conf` 编写，适用于把项目部署到一台 Linux 服务器上。

## 1. 先看当前项目的部署方式

当前项目默认通过 Docker Compose 启动 3 个服务：

- `db`：PostgreSQL 15，数据保存在 Docker 卷 `pgdata`
- `backend`：FastAPI，容器内监听 `8000`
- `frontend`：Nginx + Vue 静态文件，对外暴露 `80`

访问链路如下：

```text
浏览器
  -> frontend (Nginx:80)
  -> /api 反向代理到 backend:8000
  -> backend 连接 db:5432
```

这意味着：

- 服务器对外默认只开放 `80` 端口即可
- 后端 `8000` 端口默认不会暴露到宿主机
- 首次启动时，后端会自动等待数据库、自动建表、并在题库为空时自动导入 `data/atmr_full_questions.json`
- 当前项目不会自动创建测试账号，首次使用请在登录页自行注册

## 2. 当前版本的注意事项

这些是现在这份代码的真实行为，部署前建议先知道：

1. `.env.example` 里虽然还有 `APP_ENV`、`DATABASE_URL`、`ALLOWED_ORIGINS` 等变量，但按照当前 `docker-compose.yml`，默认部署时真正会被用到的主要是：
   - `DB_PASSWORD`
   - `SECRET_KEY`
   - `DEEPSEEK_API_KEY`
   - `DASHSCOPE_API_KEY`
   - `ZHIPU_API_KEY`
2. 不配置 AI Key 也能把系统启动起来，但依赖大模型的功能会不可用或降级，比如 AI 辩论、RAG、咨询对话。
3. 数据库是持久化的，因为用了 Docker 卷 `pgdata`。
4. `uploads/` 目录已经挂载到独立 Docker 卷 `uploads`，重建 `backend` 容器后，头像和上传文件会保留。
5. 前端 Nginx 已经代理 `/api` 和 `/uploads`，上传文件可以通过前端入口统一访问。

## 3. 服务器准备

建议准备一台 Linux 服务器，并确保：

- 已开放 SSH 端口（通常是 `22`）
- 已开放 HTTP 端口 `80`
- 已安装 Git
- 已安装 Docker 和 Docker Compose v2

下面以 Ubuntu / Debian 为例：

```bash
sudo apt update
sudo apt install -y git ca-certificates curl
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
newgrp docker

docker --version
docker compose version
```

如果服务器里已经装好了 Docker 和 Git，可以直接跳到下一步。

## 4. 让服务器拿到代码

最简单的方式是先把当前项目推到一个远程 Git 仓库，然后在服务器上拉取。

如果你的代码已经在远程仓库中，直接执行：

```bash
sudo mkdir -p /opt
cd /opt
sudo git clone <你的仓库地址> TestAgent
sudo chown -R $USER:$USER /opt/TestAgent
cd /opt/TestAgent
```

例如：

```bash
git clone https://github.com/<your-name>/TestAgent.git
```

如果代码现在只在本地电脑，还没有远程仓库，先把它推到 GitHub、Gitee 或你自己的 Git 服务，再继续本教程。

## 5. 配置环境变量

在项目根目录执行：

```bash
cp .env.example .env
nano .env
```

至少修改这几项：

```env
DB_PASSWORD=请改成你自己的数据库密码
SECRET_KEY=请改成一串足够长的随机字符串
DEEPSEEK_API_KEY=
DASHSCOPE_API_KEY=
ZHIPU_API_KEY=
```

说明：

- `DB_PASSWORD`：PostgreSQL 的密码，必须修改
- `SECRET_KEY`：JWT 签名密钥，必须修改
- 三个 AI Key 都是可选项，但不填的话 AI 相关功能不可用
- 使用当前自带的 `docker-compose.yml` 时，不需要手工填写 `DATABASE_URL`

如果你想快速生成一个随机密钥，可以用：

```bash
openssl rand -hex 32
```

## 6. 启动服务

在项目根目录执行：

```bash
docker compose up -d --build
```

首次启动通常会比后续慢很多，原因包括：

- 拉取 PostgreSQL、Nginx、Python、Node 镜像
- 构建前端静态资源
- 安装后端 Python 依赖
- 下载 CPU 版 PyTorch wheel

第一次部署时，等待 5 到 15 分钟都算正常。

## 7. 启动后会自动做什么

当前版本启动 `backend` 容器时，会自动完成下面这些动作：

1. 等待数据库可连接
2. 执行 `init_db()` 自动建表
3. 检查题库是否为空
4. 如果题库为空，自动运行 `scripts/import_data.py` 导入 `data/atmr_full_questions.json`
5. 最后启动 `uvicorn app.main:app --host 0.0.0.0 --port 8000`

所以在默认部署流程里：

- 不需要手工执行建表脚本
- 不需要手工执行题库导入脚本

## 8. 检查服务是否正常

先看容器状态：

```bash
docker compose ps
```

正常情况下，应该看到：

- `db` 已启动并通过健康检查
- `backend` 为 `Up`
- `frontend` 为 `Up`

再看后端日志：

```bash
docker compose logs --tail=100 backend
```

重点看这些信息：

- 数据库连接成功
- 自动建表完成
- 题库已导入，或显示题库已存在并跳过导入
- `Uvicorn running on http://0.0.0.0:8000`

再看前端日志：

```bash
docker compose logs --tail=50 frontend
```

## 9. 访问系统

浏览器访问：

```text
http://你的服务器公网IP/
```

如果你绑定了域名，也可以直接访问：

```text
http://你的域名/
```

注意：

- 当前项目默认没有预置账号
- 第一次进入系统后，请直接在登录页注册一个新账号

## 10. 可选：启用完整的自适应选题能力

当前系统即使没有题目特征向量，也可以运行；这时自适应选题会回退为顺序选题。

如果你想启用更完整的自适应选题逻辑，可以在部署完成后手工生成题目特征向量：

```bash
docker compose exec backend python scripts/generate_feature_vectors.py
```

这一步不是首启必需项，但要注意：

- 会额外吃 CPU 和内存
- 首次运行耗时可能较长
- 更适合在服务器空闲时执行

## 11. 可选：直接暴露后端 Swagger 文档

按当前 `docker-compose.yml`，后端 `8000` 端口不会直接暴露，所以你默认不能从宿主机直接访问：

```text
http://服务器IP:8000/docs
```

如果你确实需要直接查看 Swagger，可以在 `docker-compose.yml` 的 `backend` 服务里增加：

```yaml
backend:
  ports:
    - "8000:8000"
```

然后重新部署：

```bash
docker compose up -d --build backend frontend
```

之后就可以访问：

```text
http://你的服务器IP:8000/docs
```

## 12. 常用运维命令

```bash
cd /opt/TestAgent

# 查看状态
docker compose ps

# 查看后端日志
docker compose logs -f backend

# 查看前端日志
docker compose logs -f frontend

# 查看数据库日志
docker compose logs -f db

# 重启全部服务
docker compose restart

# 停止服务（保留数据库卷）
docker compose down

# 停止并删除数据库卷（会清空数据库）
docker compose down -v

# 拉取新代码后重新部署
git pull
docker compose up -d --build
```

如果执行了 `docker compose down -v`，下次再启动时，系统会重新建库并重新导入题库。

## 13. 常见问题

### 13.1 打不开首页

按这个顺序检查：

1. 安全组或防火墙是否已放行 `80` 端口
2. `docker compose ps` 里 `frontend` 是否为 `Up`
3. `docker compose logs frontend` 是否有 Nginx 报错
4. 服务器公网 IP 或域名是否正确

### 13.2 后端一直重启

先看日志：

```bash
docker compose logs -f backend
```

常见原因：

- `.env` 里 `DB_PASSWORD` 配错
- 本机 Docker 环境异常，数据库容器没起来
- 首次安装依赖较慢，看起来像卡住，实际上仍在构建

### 13.3 AI 功能不可用

先确认 `.env` 已填写至少一个可用的 AI Key，例如：

```env
DEEPSEEK_API_KEY=你的真实密钥
```

然后重启后端：

```bash
docker compose restart backend
```

### 13.4 自适应选题没有生效

这是当前版本的预期行为之一：如果题库还没有特征向量，系统会回退到顺序选题。

手工补全特征向量：

```bash
docker compose exec backend python scripts/generate_feature_vectors.py
```

### 13.5 上传文件或头像访问异常

当前版本已经支持通过前端 Nginx 转发 `/uploads`，如果访问异常，按这个顺序检查：

1. `docker compose ps` 中 `frontend` 和 `backend` 是否都为 `Up`
2. `docker compose logs frontend` 是否有 Nginx 报错
3. `docker compose logs backend` 是否有静态文件或上传相关报错
4. 访问路径是否以 `/uploads/...` 开头

### 13.6 重建容器后头像或上传文件丢失

当前版本已经通过 Docker 卷持久化 `uploads/`，正常重建 `backend` 容器不会丢失文件。

只有在你执行 `docker compose down -v`，或者手工删除 `uploads` 卷时，这些文件才会被清空。

## 14. 建议的部署完成检查清单

部署结束后，至少确认下面几件事：

- 可以正常打开首页
- 可以注册新账号并登录
- 可以开始测评并正常提交答案
- `docker compose ps` 中三个服务都稳定运行
- 后端日志里没有持续报错
- 如果需要 AI 功能，确认对应模型密钥已生效
