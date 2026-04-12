# TestAgent 部署教程（从零开始）

> 适合完全没有部署经验的同学，按步骤操作即可。

---

## 总览

你需要做 3 件事：
1. 把代码上传到 Gitee（码云）
2. 在服务器上把代码拉下来
3. 一键启动

总耗时约 20-30 分钟。

---

## 第一步：把代码上传到 Gitee

### 1.1 注册 Gitee 账号

打开 https://gitee.com ，注册一个账号（如果已有跳过）。

### 1.2 创建仓库

1. 登录后，点右上角 **「+」→「新建仓库」**
2. 仓库名填：`TestAgent`
3. **不要勾选** "使用Readme文件初始化仓库"
4. 选择 **私有**（你的代码不公开）
5. 点 **创建**

### 1.3 在本地电脑推送代码

打开你电脑的终端（PowerShell 或 Git Bash），在项目目录下执行：

```bash
cd D:\PythonCode\TestAgent

# 添加 Gitee 远程仓库（把下面的 你的用户名 替换成你的 Gitee 用户名）
git remote add gitee https://gitee.com/你的用户名/TestAgent.git

# 推送代码
git add -A
git commit -m "准备部署"
git push gitee main
```

系统会提示输入 Gitee 的用户名和密码，输入即可。

> 如果提示 `remote gitee already exists`，先执行 `git remote remove gitee` 再重试。

---

## 第二步：登录服务器并拉取代码

### 2.1 登录服务器

1. 打开阿里云控制台：https://ecs.console.aliyun.com
2. 找到你的服务器实例，点击 **「远程连接」**
3. 选择 **「通过Workbench远程连接」** → 输入密码 → 连接

现在你已经进入服务器的终端了。

### 2.2 确认系统和 Docker

```bash
# 看看是什么系统
cat /etc/os-release

# 确认 Docker 已安装
docker --version
docker compose version
```

如果 `docker compose` 命令找不到，试试：
```bash
docker-compose --version
```

> 如果显示 `docker-compose` 但没有 `docker compose`（没有横杠），
> 后面所有命令把 `docker compose` 替换成 `docker-compose` 即可。

### 2.3 安装 Git（如果没有的话）

```bash
# Ubuntu/Debian 系统
apt update && apt install -y git

# CentOS/Alibaba Cloud Linux 系统
yum install -y git
```

### 2.4 拉取代码到服务器

```bash
# 创建项目目录
mkdir -p /opt
cd /opt

# 从 Gitee 拉取代码（替换为你的用户名）
git clone https://gitee.com/你的用户名/TestAgent.git

# 进入项目目录
cd TestAgent
```

系统会提示输入 Gitee 用户名和密码。

### 2.5 创建环境变量文件

```bash
cp .env.example .env
```

然后编辑 `.env` 文件：
```bash
vi .env
```

> **vi 编辑器极简用法：**
> - 按 `i` 进入编辑模式
> - 用方向键移动光标，修改内容
> - 修改完按 `Esc`，然后输入 `:wq` 回车保存退出

需要改的内容：
```
DB_PASSWORD=设一个你自己的密码
SECRET_KEY=随便打一串字符比如 abc123xyz456
DEEPSEEK_API_KEY=你的key（没有就留空）
```

---

## 第三步：一键启动

```bash
cd /opt/TestAgent
docker compose up -d --build
```

**首次构建需要 5-15 分钟**（下载镜像 + 安装依赖），耐心等待。

看到类似下面的输出就成功了：
```
✔ Container testagent-db-1        Started
✔ Container testagent-backend-1   Started
✔ Container testagent-frontend-1  Started
```

### 3.1 确认服务是否正常

```bash
# 查看容器状态（三个都应该是 Up）
docker compose ps

# 查看后端日志（确认题库导入成功）
docker compose logs backend
```

后端日志中看到 `导入完成` 和 `Uvicorn running` 就表示成功。

### 3.2 开放 80 端口（重要！）

回到阿里云控制台：

1. 找到你的 ECS 实例
2. 点击 **「安全组」** 标签
3. 点击安全组 ID → **「手动添加」**
4. 添加一条规则：
   - 授权策略：**允许**
   - 优先级：**1**
   - 协议类型：**自定义TCP**
   - 端口范围：**80/80**
   - 授权对象：**0.0.0.0/0**
5. 点 **保存**

### 3.3 访问你的网站

打开浏览器，输入：
```
http://你的服务器公网IP
```

> 公网 IP 在阿里云控制台的实例详情页可以看到。

测试账号：
- 用户名：`adaptive_test_user`
- 密码：`test123456`

---

## 常用运维命令

```bash
cd /opt/TestAgent

# 查看运行状态
docker compose ps

# 查看后端日志
docker compose logs -f backend

# 查看前端日志
docker compose logs -f frontend

# 重启所有服务
docker compose restart

# 停止所有服务
docker compose down

# 更新代码后重新部署
git pull gitee main
docker compose up -d --build

# 进入后端容器（调试用）
docker compose exec backend bash

# 手动生成特征向量（可选，占内存较大）
docker compose exec backend python scripts/generate_feature_vectors.py
```

---

## 常见问题

### Q: 浏览器访问白屏/无法连接？
1. 确认安全组已放行 80 端口
2. 检查容器是否都在运行：`docker compose ps`
3. 检查后端日志有无报错：`docker compose logs backend`

### Q: 后端启动失败，数据库连不上？
```bash
# 查看数据库容器日志
docker compose logs db
# 重启数据库
docker compose restart db
```

### Q: 如何更换域名？
购买域名后，到域名解析处添加一条 A 记录，指向你的服务器公网 IP 即可。

### Q: AI 对话功能不工作？
在 `.env` 文件中填入你的 DEEPSEEK_API_KEY，然后重启：
```bash
docker compose restart backend
```
