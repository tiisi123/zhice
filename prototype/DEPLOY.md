# 智策 — 生产部署指南

## 1. 环境要求

- Python 3.11+
- Node.js 18+
- SQLite 3 (内置)

## 2. 后端部署

### 2.1 安装依赖

```bash
cd zhice
pip install -e ".[dev]"
```

### 2.2 配置环境变量

复制 `.env.example` 为 `.env`，**必须设置以下项**：

```bash
# 安全 — 必须设置（否则启动时会警告）
ZHICE_JWT_SECRET=<64位随机字符串>    # openssl rand -hex 32
ZHICE_ADMIN_PASSWORD=<管理员初始密码>  # 首次启动后请立即修改

# 生产模式
DEBUG=false
CORS_ORIGINS=["https://your-domain.com"]

# 数据源 — 至少配置一个
KPL_USER_ID=<id>
KPL_TOKEN=<token>
KPL_DEVICE_ID=<uuid>
TUSHARE_TOKEN=<token>

# AI — 至少配置一个
ANTHROPIC_API_KEY=<key>
ANTHROPIC_BASE_URL=<url>
# 或
OPENAI_API_KEY=<key>
```

### 2.3 启动

```bash
# 生产环境（gunicorn + uvicorn worker）
gunicorn apps.api.main:app -w 1 -k uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 --timeout 120

# 注意：因使用 SQLite + 内存限频，建议单 worker 运行
# 多 worker 需改用 Redis 做限频和缓存
```

### 2.4 健康检查

```
GET /api/health
返回: {"status": "ok", "components": {"api": "ok", "database": "ok"}}
```

## 3. 前端部署

```bash
cd zhice/apps/web
npm install
npm run build
# 产物在 dist/ 目录，用 nginx 托管
```

### Nginx 配置示例

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location /api {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 120s;
    }

    location /api/ws {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    location / {
        root /path/to/zhice/apps/web/dist;
        try_files $uri $uri/ /index.html;
    }
}
```

## 4. 安全检查清单

- [ ] `ZHICE_JWT_SECRET` 已设置为随机强密码
- [ ] `DEBUG=false`
- [ ] `CORS_ORIGINS` 仅包含生产域名
- [ ] `.env` 文件权限 `chmod 600`
- [ ] 管理员账户已修改默认密码
- [ ] `ZHICE_ADMIN_PASSWORD` 已设置为强密码，首次启动日志未泄露随机密码
- [ ] Swagger 文档已自动关闭（debug=false 时）
- [ ] 确认 `.env` 不在 git 中（已在 .gitignore）
- [ ] 线上支付入口已关闭或接入真实支付回调验签，禁止展示 mock 支付二维码
- [ ] 报告归档已确认权限隔离，用户私有报告不会被全局读取
- [ ] AI 配额已覆盖所有高成本接口，超限返回 429

## 4.1 用户与商业化上线闸门

当前支付系统仍是 mock/占位状态：`/api/payment/order` 仅允许 debug 环境创建本地订单并返回 mock 微信二维码，生产 `DEBUG=false` 时返回 403；`/api/payment/mock-pay` 也仅允许 debug 环境使用。未接入微信/支付宝真实下单、回调验签、幂等对账前，不得开放真实收款入口。

商业化公开上线前必须确认：

- 会员开通仅使用邀请码内测，或完成真实支付接入与回调验签。
- VIP 权益不能只停留在前端展示；高成本能力必须在后端使用 `require_vip` 或 `consume_quota`。
- `ZHICE_JWT_SECRET` 缺失时不得进入生产服务；否则重启会导致所有 token 失效。
- 管理员初始密码必须通过 `ZHICE_ADMIN_PASSWORD` 配置，生产日志不得暴露随机密码。
- 报告归档、研究池、看板等用户数据必须按 `user_id` 或公开/私有权限隔离。
- SQLite 部署保持单 worker；真实支付和高并发商业化上线前应评估 PostgreSQL/Redis。

详细风险见 `docs/用户与商业化风险清单.md`。

## 5. 数据说明

### 功能完成度

| 等级 | 模块 |
|------|------|
| 完全可用 | 复盘、情绪、龙虎榜、产业链、财报、新闻、研报、自选股、看板、策略推荐、板块轮动 |
| 数据源依赖 | 盘中监控（需 KPL）、题材分析（需 KPL）、个股短线画像（需 KPL）、ETF 轮动（需 TuShare）|
| 回测降级 | 策略回测（TuShare 不可用时自动切换蒙特卡洛模拟，页面有标识）|
| Mock 数据 | 成长分析、价值分析、估值（等待接入真实财务数据源）|
| 未就绪 | 支付系统（当前为 mock，需接入微信/支付宝）|

### SQLite 数据库

- 位置: `data/zhice.db`
- 自动创建表和索引
- 建议定期备份: `cp data/zhice.db data/zhice_backup_$(date +%Y%m%d).db`
