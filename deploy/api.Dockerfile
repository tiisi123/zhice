# T04 (M001/S01) — zhice-api 镜像
#
# Multi-stage：builder 安装依赖，runtime 用 python:3.11-slim 跑 gunicorn+uvicorn worker。
# 构建上下文（docker compose build context）= repo 根（/home/factory/zhice），
# 所以本文件路径用 prototype/ 前缀（构建上下文里就是 ../prototype/）。
#
# 启动顺序：entrypoint.sh -> alembic upgrade head -> gunicorn (apps.api.main:app)
# 依赖 zhice-db healthcheck 通过（compose depends_on: condition: service_healthy），
# alembic 跑完才暴露 8000，curl /api/health 才算 healthy。

# ─────────────────────────────────────────────────────────────────────────────
# Builder stage：编译 wheel，避免 runtime 镜像携带编译器
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

# 镜像默认走 Debian / PyPI 公网；Chinese-region 部署或受限网络可在
# build 时通过 --build-arg APT_MIRROR=mirrors.aliyun.com / PIP_INDEX_URL=...
# 覆盖（compose 里 build.args 注入）。docker-compose.verify.yml 即用此机制
# 让本地 verify 在公网受限环境下也能成功构建。
ARG APT_MIRROR=deb.debian.org
ARG PIP_INDEX_URL=https://pypi.org/simple

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_INDEX_URL=${PIP_INDEX_URL}

WORKDIR /build

# 替换 apt sources（兼容老 sources.list 与 Trixie 起的 .sources 格式）
RUN if [ "$APT_MIRROR" != "deb.debian.org" ]; then \
        sed -i "s|deb.debian.org|${APT_MIRROR}|g" \
            /etc/apt/sources.list.d/*.sources \
            /etc/apt/sources.list 2>/dev/null || true ; \
    fi

# 装编译期依赖（cryptography / pymysql 走纯 Python wheel，但 cryptography 在
# slim 镜像下偶尔需要 build 工具；保留以求稳定）
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
    && rm -rf /var/lib/apt/lists/*

# pyproject.toml 用 hatchling 但未显式声明 [tool.hatch.build.targets.wheel.packages]
# （项目源码在 apps/ + packages/，不是单一 zhice/ 目录），所以 `pip install .` 会失败。
# 不需要把 zhice 打成 wheel — runtime 阶段直接 COPY 源码到 /app；这里只装运行期依赖。
# 依赖列表保持与 prototype/pyproject.toml [project.dependencies] 同步（一份硬编码，
# 升级时两处一起改；future work：M002 切到 lockfile 后改为 pip install -r 锁定文件）。
RUN pip install --prefix=/install \
        "fastapi>=0.110" \
        "uvicorn[standard]>=0.29" \
        "httpx>=0.27" \
        "pydantic>=2.7" \
        "pydantic-settings>=2.2" \
        "apscheduler>=3.10" \
        "python-multipart>=0.0.9" \
        "pypdf>=4.2" \
        "sqlalchemy>=2.0" \
        "alembic>=1.13" \
        "pymysql>=1.1" \
        "cryptography>=42" \
        "gunicorn>=22.0"

# ─────────────────────────────────────────────────────────────────────────────
# Runtime stage：精简镜像
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

ARG APT_MIRROR=deb.debian.org

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/usr/local/bin:${PATH}"

# 同样的 apt 源覆盖（runtime 也要装 curl + ca-certificates）
RUN if [ "$APT_MIRROR" != "deb.debian.org" ]; then \
        sed -i "s|deb.debian.org|${APT_MIRROR}|g" \
            /etc/apt/sources.list.d/*.sources \
            /etc/apt/sources.list 2>/dev/null || true ; \
    fi

# curl 用于 healthcheck；ca-certificates 用于 HTTPS 出站（OpenAI/Anthropic/TuShare）
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -r zhice && useradd -r -g zhice -u 10001 -m -s /bin/bash zhice \
    && mkdir -p /var/log/zhice /app \
    && chown -R zhice:zhice /var/log/zhice /app

# 把 builder 编译好的依赖搬过来
COPY --from=builder /install /usr/local

WORKDIR /app

# 复制运行时需要的源码（prototype 下的 apps / packages / alembic）
COPY --chown=zhice:zhice prototype/apps /app/apps
COPY --chown=zhice:zhice prototype/packages /app/packages
COPY --chown=zhice:zhice prototype/alembic /app/alembic
COPY --chown=zhice:zhice prototype/alembic.ini /app/alembic.ini

# Entrypoint：先跑 alembic upgrade head，再 exec gunicorn
COPY --chown=zhice:zhice deploy/api-entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

USER zhice

EXPOSE 8000

# Healthcheck 由 docker-compose.yml 显式声明，这里保留默认占位
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=6 \
    CMD curl -fsS http://localhost:8000/api/health || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["gunicorn", "apps.api.main:app", \
     "-w", "1", \
     "-k", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", \
     "--timeout", "120", \
     "--access-logfile", "/var/log/zhice/api-access.log", \
     "--error-logfile", "/var/log/zhice/api.log"]
