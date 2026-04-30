# 智策 — Staging 部署运维手册

> 业主独立可读。从零到 staging 子域名 HTTPS 可访问的全流程；含故障排障与上线闸门。
> 适用版本：M001 S01 之后（MySQL 8.0 + Docker compose + Caddy + GitHub Actions 自动部署）。
> M001 之前的 SQLite 单机部署形态已下线。

---

## 1. 部署架构

```
                       ┌──────────────────────────────┐
   用户浏览器 ──HTTPS──▶│       Caddy（80/443 端口）   │
                       │  自动 Let's Encrypt 证书      │
                       └──────────┬───────────────────┘
                                  │ reverse_proxy
                                  ▼
                       ┌──────────────────────────────┐
                       │   zhice-web（nginx + 静态）   │
                       │   /api → zhice-api 反代       │
                       │   /api/ws → ws upgrade        │
                       │   /  → SPA 静态托管 + fallback│
                       └──────────┬───────────────────┘
                                  │
                                  ▼
                       ┌──────────────────────────────┐
                       │  zhice-api（FastAPI + gunicorn│
                       │  单 worker + alembic upgrade）│
                       │  日志 → /var/log/zhice/api.log│
                       └──────────┬───────────────────┘
                                  │ mysql+pymysql
                                  ▼
                       ┌──────────────────────────────┐
                       │  zhice-db（mysql:8.0）        │
                       │  utf8mb4_0900_ai_ci + UTC     │
                       │  数据卷 mysql-data            │
                       └──────────────────────────────┘
```

四个容器一台主机：

| 服务      | 镜像                  | 端口暴露 | 数据卷                              |
| --------- | --------------------- | -------- | ----------------------------------- |
| caddy     | caddy:2.8-alpine      | 80, 443  | caddy_data, caddy_config            |
| zhice-web | 本地 build (nginx)    | 内部 80  | —                                   |
| zhice-api | 本地 build (python)   | 内部 8000| /var/log/zhice（host bind mount）   |
| zhice-db  | mysql:8.0             | 内部 3306| mysql-data                          |

> **关键决策**（详见 `.gsd/DECISIONS.md`）：
>
> - 单机 4C8G + Docker compose（M001 不上 K8s）；
> - 单 FastAPI worker（限频/缓存在内存，多 worker 需 Redis）；
> - 数据库 MySQL 8.0（避开 M002 收费时再迁一次的成本）；
> - Caddy 自动 HTTPS（Let's Encrypt，业主子域名 ICP 报备完成即用）。

---

## 2. Staging 主机准备

业主可向云厂商租 1 台 4C8G Ubuntu 22.04 LTS 主机（公网带宽 ≥ 5Mbps）。建议提前开放安全组 22/80/443。

### 2.1 安装 Docker 与 docker compose plugin

```bash
# 业主 SSH 登录后执行（一次性）
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
  sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo systemctl enable --now docker
docker --version              # 期望 ≥ 24
docker compose version        # 期望 ≥ 2.20
```

### 2.2 创建专用部署账号（推荐，不用 root）

```bash
sudo useradd -m -s /bin/bash deploy
sudo usermod -aG docker deploy
sudo passwd deploy           # 业主自己设强密码，仅本地终端用，SSH 走 key
# SSH 公钥放进 ~deploy/.ssh/authorized_keys（公钥来自 §4 GitHub Actions 生成的对密钥）
```

### 2.3 主机时区与时间同步（避免 token 时差）

```bash
sudo timedatectl set-timezone UTC
sudo apt-get install -y systemd-timesyncd
sudo systemctl enable --now systemd-timesyncd
timedatectl status
```

### 2.4 防火墙（仅放行 22/80/443）

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status
```

---

## 3. 子域名 ICP 报备（R-DOMAIN-ICP）

> **业主必读**：在中国大陆托管的服务器对外提供 80/443 服务**必须**完成 ICP 备案；备案审核 7-20 个工作日不等。请尽早与服务商确认。

1. 主域名（如 `zhice.example.com`）已在工信部完成备案；
2. 在云厂商控制台为该主域名添加子域名（如 `staging.zhice.example.com`），DNS A 记录解析到 staging 主机公网 IP；
3. 云厂商内的"备案接入主体"页面提交子域名增加申请（部分服务商免审，部分需重新审核）；
4. 备案查询：https://beian.miit.gov.cn/ ；
5. **未完成备案前**，业主可暂用 IP + 自签证书做内部测试（Caddyfile 改 `:80` 即跳过 HTTPS），但不得对外公开访问。

---

## 4. GitHub Actions Secrets 注入

GitHub 仓库 → Settings → Secrets and variables → Actions。

### 4.1 Repository Secrets（值会被 GHA 自动 mask，不会回显日志）

| Secret 名         | 值示例                                | 用途                                  |
| ----------------- | ------------------------------------- | ------------------------------------- |
| `STAGING_HOST`    | `staging.zhice.example.com` 或 IP     | deploy-staging.yml SSH 连接目标       |
| `STAGING_USER`    | `deploy`                              | SSH 登录用户名                        |
| `STAGING_SSH_KEY` | 私钥全文（含 BEGIN/END 头尾）         | SSH 私钥，**仅这台仓库专用**          |
| `STAGING_PORT`    | `22`（可选，默认 22）                 | SSH 端口                              |

业主在本地生成专用密钥对：

```bash
ssh-keygen -t ed25519 -f ~/.ssh/zhice_staging -N "" -C "github-actions-zhice"
# 公钥追加到 staging 主机
ssh-copy-id -i ~/.ssh/zhice_staging.pub deploy@<staging-host>
# 私钥全文复制粘贴到 GHA Secret STAGING_SSH_KEY
cat ~/.ssh/zhice_staging
```

### 4.2 Repository Variables（非敏感）

| Variable 名       | 值          | 含义                                                          |
| ----------------- | ----------- | ------------------------------------------------------------- |
| `DEPLOY_ENABLED`  | `false`/`true` | `false` 时 push main 不触发实跑，仅手动 workflow_dispatch     |

> **首次配置建议流程**：
> 1. 先把 `DEPLOY_ENABLED=false`；
> 2. 在 staging 主机手动跑一次 §5 首次部署流程（拉镜像 + alembic upgrade head 都先成功）；
> 3. 在 Actions 页面手动 workflow_dispatch 跑一次 deploy-staging，确认 SSH/compose/health 全绿；
> 4. 把 `DEPLOY_ENABLED=true`，从此 push main 自动部署。

### 4.3 主机端 .env（不进 git，仅在 staging 主机本地维护）

OpenAI / Anthropic / TuShare / KPL / SMTP 等业务密钥**不**走 GHA secrets，而是直接放在 staging 主机 `/opt/zhice/deploy/.env` 文件（chmod 600，仅 deploy 用户可读）。详见 §5.4。

---

## 5. 首次部署步骤

业主 SSH 到 staging 主机后按顺序执行。预计 30 分钟（含首次镜像构建）。

### 5.1 拉代码

```bash
sudo mkdir -p /opt/zhice
sudo chown deploy:deploy /opt/zhice
cd /opt/zhice
git clone https://github.com/<owner>/zhice.git .
git checkout main
```

### 5.2 创建宿主机日志目录（一次性）

```bash
cd /opt/zhice
make deploy-init        # 等价于 sudo mkdir /var/log/zhice && sudo chown 10001:10001
ls -ld /var/log/zhice   # 期望 drwxr-xr-x deploy/zhice 10001:10001
```

> **MEM012**：日志目录权限不对，zhice-api 启动时写日志会 PermissionError 反复重启。`make deploy-init` 是首次部署不可省略的一步。

### 5.3 准备 .env

```bash
cd /opt/zhice/deploy
cp .env.example .env
chmod 600 .env
$EDITOR .env            # 业主用 vim/nano 编辑，填入下表三类值
```

`.env` 中三类必填：

| 类别              | 字段                                                                              | 备注                                                |
| ----------------- | --------------------------------------------------------------------------------- | --------------------------------------------------- |
| 启动校验三件套    | `ZHICE_JWT_SECRET` / `ZHICE_ADMIN_PASSWORD` / `DATABASE_URL`                      | 缺一启动直接 RuntimeError（T02 已锁定）             |
| MySQL             | `MYSQL_ROOT_PASSWORD`                                                             | `DATABASE_URL` 用 `mysql+pymysql://root:${MYSQL_ROOT_PASSWORD}@zhice-db:3306/zhice` |
| 业务密钥          | `KPL_USER_ID/TOKEN/DEVICE_ID`、`TUSHARE_TOKEN`、`OPENAI_API_KEY`、`ANTHROPIC_API_KEY`、`SMTP_*` | 至少配一个 AI key + 一个数据源 token                |
| Caddy 域名        | `STAGING_DOMAIN`                                                                  | 例 `staging.zhice.example.com`；本地测试可用 `:80`  |

生成示例：

```bash
# JWT secret
openssl rand -hex 32

# Admin 初始密码（首次登录后立刻在管理后台改）
openssl rand -base64 16
```

### 5.4 启动栈

```bash
cd /opt/zhice
make deploy-up          # 等价于 cd deploy && docker compose up -d --build
sleep 60
make deploy-ps          # 期望: 4 个服务 healthy / running
curl -fsS http://localhost/api/health   # 期望: 200 ok（含 db scheme + alembic revision）
```

首次启动期 `zhice-api` 会自动跑 `alembic upgrade head` 建 27 张表（Caddy 申 Let's Encrypt 证书需 1-3 分钟）。

---

## 6. 日常运维

### 6.1 push main 自动部署（DEPLOY_ENABLED=true 时）

业主 / 同事在本地推：

```bash
git push origin main
```

GitHub Actions 流水线：

1. `ci.yml`：python_syntax / lint / web_build / api_contract / no_mock 全部跑通（任一硬阻断红 ✗ 即不进入 deploy）；
2. `deploy-staging.yml` SSH 到 staging：`git pull && docker compose up -d --build && curl /api/health`。

业主在 GitHub 仓库 Actions 页面看实时日志。

### 6.2 手动触发部署（推荐：上线前先手动一遍）

GitHub 仓库 → Actions → deploy-staging → "Run workflow" → 选 main 分支 → Run。

### 6.3 SSH 看日志（首选排障入口）

```bash
ssh deploy@<staging-host>
cd /opt/zhice
make deploy-logs-api    # tail -f zhice-api 容器日志（首选）
make deploy-logs        # tail 所有服务

# 主机文件日志
tail -f /var/log/zhice/api.log         # 应用层错误（gunicorn error log）
tail -f /var/log/zhice/api-access.log  # 接口访问日志
```

### 6.4 升级业务代码（不重启 db）

业主通常不需要手动跑——`make deploy-up` 不会 down 数据库（只 recreate api/web 容器）。如果遇到 schema 变更：

```bash
cd /opt/zhice && git pull
make deploy-up          # zhice-api entrypoint 自动跑 alembic upgrade head
```

### 6.5 数据库备份（业主每周一次手动）

```bash
ssh deploy@<staging-host>
cd /opt/zhice
docker compose -f deploy/docker-compose.yml exec zhice-db \
  mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" zhice > "/opt/zhice/backups/zhice-$(date +%Y%m%d).sql"
```

> 自动备份脚本 + 异地存储是 M008 上线收口范围，M001 阶段业主手动执行。

---

## 7. 故障排障

### 7.1 health endpoint 不返回 200

```bash
curl -i http://localhost/api/health
# 看响应里 components.database 字段：
#   "ok"        — 一切正常
#   "error"     — DB 连接失败 → 看 §7.2
#   "missing"   — DATABASE_URL env 没设 → 看 §7.3
```

### 7.2 database 显示 error

```bash
make deploy-logs-api | head -50            # 应能看到具体异常
make deploy-shell-db                       # 进 mysql client 排查
docker compose ps zhice-db                 # 看 healthcheck 状态
docker compose restart zhice-db            # 极端情况下重启
```

常见原因：

- `MYSQL_ROOT_PASSWORD` 与 `DATABASE_URL` 中的密码不一致 → 改 `.env` 一致 → `make deploy-up`；
- 容器卷损坏 → `make deploy-down-clean`（**会清空数据**）→ `make deploy-up`。

### 7.3 启动校验失败：进程 exit 1

zhice-api 启动 stderr 会写：

```
启动校验失败：以下关键环境变量未设置或为空：ZHICE_JWT_SECRET, DATABASE_URL。
请在 .env / docker-compose env 中设置；ZHICE_JWT_SECRET 可用 openssl rand -hex 32 生成。
```

直接编辑 `/opt/zhice/deploy/.env` 补齐 → `make deploy-up`。

> 启动校验只打 key 名，不会泄露 value（T02 已锁定）。

### 7.4 Alembic 迁移失败

```bash
make deploy-logs-api | grep -i alembic
# 报 revision id（如 0001_initial）+ MySQL 错误码
# 业主可手动回退：
make deploy-shell-api
alembic downgrade -1                       # 退回上一个 revision
exit
```

如果是 fresh DB 第一次 alembic upgrade head 失败：检查 `MYSQL_ROOT_PASSWORD` 是否真的能登录 zhice-db。

### 7.5 Caddy ACME / Let's Encrypt 失败

```bash
docker compose logs caddy --tail=200
# 常见错误：
#   "no DNS A record for staging.zhice.example.com" → §3 DNS 没解析
#   "challenge failed: timeout"                       → 80 端口被防火墙挡 → §2.4 ufw allow 80
#   "rate limited"                                    → 短时间反复重启 Caddy → 等 1h
```

### 7.6 SSH key fingerprint mismatch（部署 job 失败）

业主更换过 staging 主机时会出现：

```
Host key verification failed.
```

GHA 流水线用了 `script_stop: true` 而非 known_hosts 强校验，但仍可能因主机 IP 复用而 mismatch。解决：

1. 业主删除 staging 主机后未删 GHA Secret `STAGING_HOST` → 更新 STAGING_HOST 即可；
2. 主机 IP 不变但 host key 重生成 → SSH 一次接受新 fingerprint，或手动登录主机做 `ssh-keygen -R <host>`。

### 7.7 docker compose pull 失败（镜像源限速）

中国主机有时拉 mysql:8.0 / caddy 等会限速。业主可在 `/opt/zhice/deploy/` 下加 `daemon.json` 镜像加速器（具体看云厂商文档），或：

```bash
# 一次性切换 docker pull 国内镜像
sudo tee /etc/docker/daemon.json <<EOF
{"registry-mirrors": ["https://docker.mirrors.ustc.edu.cn"]}
EOF
sudo systemctl restart docker
make deploy-rebuild
```

---

## 8. 安全检查清单（上线前业主逐项过）

- [ ] `ZHICE_JWT_SECRET` 已设置为 `openssl rand -hex 32` 输出的 64 位随机字符串；
- [ ] `DEBUG=false`；
- [ ] `CORS_ORIGINS` 仅包含生产域名（不含 `*`）；
- [ ] `/opt/zhice/deploy/.env` 文件权限 `chmod 600`；
- [ ] 管理员账户已用 `ZHICE_ADMIN_PASSWORD` 设的强密码登录后**立即修改**为业主自选密码；
- [ ] `ZHICE_ADMIN_PASSWORD` 已设置为强密码，**生产日志不得暴露随机密码**（T02 已锁定）；
- [ ] Swagger 文档已自动关闭（`DEBUG=false` 时）；
- [ ] 确认 `.env` 不在 git 中（已在 `.gitignore`）；
- [ ] 线上支付入口已关闭或接入真实支付回调验签，**禁止展示 mock 支付二维码**；
- [ ] 报告归档已确认权限隔离，用户私有报告不会被全局读取；
- [ ] AI 配额已覆盖所有高成本接口，超限返回 429；
- [ ] GHA Secret `STAGING_SSH_KEY` 仅授权部署用户（不是 root），且未在任何脚本/日志/Issue 里出现过；
- [ ] 业主 staging 主机 ufw 仅放 22/80/443；
- [ ] 业主了解 `make deploy-down-clean` 会清空 mysql-data 卷（误操作前请先备份）。

---

## 9. 商业化上线闸门（与 §8 一同必读）

当前支付系统仍是 mock/占位状态：`/api/payment/order` 仅允许 debug 环境创建本地订单并返回 mock 微信二维码，生产 `DEBUG=false` 时返回 403；`/api/payment/mock-pay` 也仅允许 debug 环境使用。**未接入微信/支付宝真实下单、回调验签、幂等对账前，不得开放真实收款入口**。

商业化公开上线前必须确认：

- 会员开通仅使用邀请码内测，或完成真实支付接入与回调验签；
- VIP 权益不能只停留在前端展示；高成本能力必须在后端使用 `require_vip` 或 `consume_quota`；
- `ZHICE_JWT_SECRET` 缺失时**不得**进入生产服务；否则重启会导致所有 token 失效（T02 已强制阻断启动）；
- 管理员初始密码必须通过 `ZHICE_ADMIN_PASSWORD` 配置，**生产日志不得暴露随机密码**；
- 报告归档、研究池、看板等用户数据必须按 `user_id` 或公开/私有权限隔离；
- 真实支付和高并发商业化上线前应评估 PostgreSQL/Redis 扩容路径（M001 单 worker + 单 MySQL 仅供 50 用户内测）；
- 短线工作台 KPL 数据源 Cookie 续期机制已落地（M001 S03）；
- 5xx 告警邮件已实装（M001 S08）。

详细风险见 `docs/用户与商业化风险清单.md`。

---

## 附录 A：常用 Make 目标速查

| 目标                    | 用途                                                            |
| ----------------------- | --------------------------------------------------------------- |
| `make deploy-init`      | 首次部署创建 `/var/log/zhice`（uid 10001）                       |
| `make deploy-up`        | 启动全栈（首次会 build 镜像）                                    |
| `make deploy-down`      | 停掉全栈（**保留卷数据**）                                       |
| `make deploy-down-clean`| 停掉并清空 mysql + caddy 卷（**会丢数据，谨慎**）                |
| `make deploy-logs`      | tail 所有服务日志                                                |
| `make deploy-logs-api`  | 仅 tail zhice-api（**首选排障入口**）                            |
| `make deploy-ps`        | 看 4 服务 healthy / unhealthy                                    |
| `make deploy-shell-api` | 进 zhice-api 容器 shell（调试 alembic / config 用）              |
| `make deploy-shell-db`  | 进 zhice-db mysql client                                         |
| `make deploy-rebuild`   | 强制 no-cache 重建镜像（依赖变更时用）                           |

## 附录 B：关键路径速查

| 路径                                                  | 用途                                          |
| ----------------------------------------------------- | --------------------------------------------- |
| `/opt/zhice/`                                         | 业主在 staging 主机上的 git checkout          |
| `/opt/zhice/deploy/.env`                              | 业主自己维护的密钥文件（chmod 600）           |
| `/opt/zhice/deploy/docker-compose.yml`                | 4 服务编排                                    |
| `/var/log/zhice/api.log`                              | zhice-api 应用层错误日志                      |
| `/var/log/zhice/api-access.log`                       | zhice-api 接口访问日志                        |
| `.github/workflows/ci.yml`                            | PR / push main 硬阻断 lint + build            |
| `.github/workflows/deploy-staging.yml`                | push main 自动部署到 staging                  |
| `prototype/alembic/versions/0001_initial.py`          | 27 张表初始 schema                            |
| `prototype/apps/api/config.py`                        | 启动校验（缺 env 直接 RuntimeError）          |
