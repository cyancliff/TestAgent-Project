# 阶段1: 构建前端
FROM node:20-alpine AS builder

WORKDIR /app
# 配置 npm 使用淘宝镜像
RUN npm config set registry https://registry.npmmirror.com
COPY package.json package-lock.json* ./
RUN npm install
COPY . .
RUN npm run build

# 阶段2: Nginx 托管静态文件
FROM nginx:alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
