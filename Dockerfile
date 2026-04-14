FROM python:3.10-slim

WORKDIR /app

# 替换 apt 源为阿里云镜像
RUN if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
        sed -i 's|https://deb.debian.org|https://mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources; \
        sed -i 's|http://deb.debian.org|http://mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources; \
        sed -i 's|https://security.debian.org/debian-security|https://mirrors.aliyun.com/debian-security|g' /etc/apt/sources.list.d/debian.sources; \
        sed -i 's|http://security.debian.org/debian-security|http://mirrors.aliyun.com/debian-security|g' /etc/apt/sources.list.d/debian.sources; \
    elif [ -f /etc/apt/sources.list ]; then \
        sed -i 's|https://deb.debian.org|https://mirrors.aliyun.com|g' /etc/apt/sources.list; \
        sed -i 's|http://deb.debian.org|http://mirrors.aliyun.com|g' /etc/apt/sources.list; \
        sed -i 's|https://security.debian.org/debian-security|https://mirrors.aliyun.com/debian-security|g' /etc/apt/sources.list; \
        sed -i 's|http://security.debian.org/debian-security|http://mirrors.aliyun.com/debian-security|g' /etc/apt/sources.list; \
    fi

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 配置 pip 使用阿里云镜像
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/ && \
    pip config set global.trusted-host mirrors.aliyun.com

# 先复制依赖文件，利用 Docker 缓存
COPY requirements_full.txt .

# 先直接下载 torch CPU 版 wheel 安装，再装其余依赖（全部走阿里云镜像）
RUN pip install --no-cache-dir --timeout=300 https://download.pytorch.org/whl/cpu/torch-2.1.0%2Bcpu-cp310-cp310-linux_x86_64.whl && \
    grep -v '^torch==' requirements_full.txt > requirements.txt && \
    pip install --no-cache-dir --timeout=300 -r requirements.txt

# 复制应用代码
COPY app/ ./app/
COPY scripts/ ./scripts/
COPY data/ ./data/
COPY PageIndex/ ./PageIndex/

# 复制启动脚本
COPY docker-entrypoint.sh .
RUN chmod +x docker-entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["./docker-entrypoint.sh"]
