FROM python:3.10-slim

WORKDIR /app

# 替换 apt 源为阿里云镜像
RUN sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 配置 pip 使用阿里云镜像
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/ && \
    pip config set global.trusted-host mirrors.aliyun.com

# 先复制依赖文件，利用 Docker 缓存
COPY requirements_server.txt .
RUN pip install --no-cache-dir -r requirements_server.txt

# 复制应用代码
COPY app/ ./app/
COPY import_data.py .
COPY generate_feature_vectors.py .
COPY atmr_full_questions.json .
COPY PageIndex/ ./PageIndex/
COPY agent/ ./agent/

# 复制启动脚本
COPY docker-entrypoint.sh .
RUN chmod +x docker-entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["./docker-entrypoint.sh"]
