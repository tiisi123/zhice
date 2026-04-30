# T04 (M001/S01) — zhice-web 镜像
#
# Multi-stage：node:20-alpine 构建 React/Vite 产物，nginx:1.27-alpine 作 runtime。
# 构建上下文 = repo 根；npm ci 走 prototype/apps/web/package-lock.json。

# ─────────────────────────────────────────────────────────────────────────────
# Build stage
# ─────────────────────────────────────────────────────────────────────────────
FROM node:20-alpine AS builder

# 公网 npm registry 默认；中国受限网络可 build-arg NPM_REGISTRY=https://registry.npmmirror.com
ARG NPM_REGISTRY=https://registry.npmjs.org

WORKDIR /build

# 先 COPY 锁文件，最大化层缓存命中（依赖未变时跳过 npm ci）
COPY prototype/apps/web/package.json prototype/apps/web/package-lock.json /build/
RUN npm config set registry "${NPM_REGISTRY}" \
    && npm ci --no-audit --no-fund

# 复制源码并构建
COPY prototype/apps/web /build
RUN npm run build

# ─────────────────────────────────────────────────────────────────────────────
# Runtime stage
# ─────────────────────────────────────────────────────────────────────────────
FROM nginx:1.27-alpine AS runtime

# nginx alpine 自带 curl 缺失；装上以便 healthcheck
RUN apk add --no-cache curl

# 替换默认 default.conf
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf

# 拷贝构建产物
COPY --from=builder /build/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=6 \
    CMD curl -fsS http://localhost/ -o /dev/null || exit 1

CMD ["nginx", "-g", "daemon off;"]
