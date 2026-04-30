#!/usr/bin/env bash
# T04 (M001/S01) — zhice-api 启动入口
#
# 流程：
#   1. depends_on: zhice-db.condition=service_healthy 已保证 MySQL 就绪
#   2. 跑 alembic upgrade head（首次部署建表，后续部署自动应用 revision）
#      - alembic 失败：写 stderr，进程 exit 1，container restart 策略接管
#   3. exec 到 CMD（gunicorn）—— 用 exec 让 gunicorn 成为 PID 1，正确响应 SIGTERM
#
# 故障可观察：
#   - alembic stderr 直接进入 docker compose logs zhice-api
#   - gunicorn 日志写 /var/log/zhice/api.log（compose 卷挂载到宿主机）
set -euo pipefail

echo "[zhice-api] entrypoint start: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "[zhice-api] DATABASE_URL scheme: ${DATABASE_URL%%://*}"

# Alembic 走 prototype/alembic.ini -> alembic/env.py -> settings.database_url
echo "[zhice-api] running: alembic upgrade head"
alembic -c /app/alembic.ini upgrade head

echo "[zhice-api] alembic done; exec: $*"
exec "$@"
