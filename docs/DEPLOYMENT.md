# EverStory 公开演示部署指南

## 当前公开环境

- 在线地址：<https://everstory.onrender.com/>
- 部署形态：Render Web Service + PostgreSQL + Redis-compatible Key Value
- 健康检查：<https://everstory.onrender.com/api/health>
- 默认模型模式：`stub`，不会消耗平台模型额度
- 已验证后端：`database.backend=postgresql`、`coordination.backend=redis`

免费 Web Service 闲置后会休眠，因此第一次访问可能需要约一分钟。这个地址适合作品集
评审和面试演示，不应被描述为带 SLA 的商业生产服务。

## 推荐的作品集演示方案

公开演示默认使用 **Stub 模式**。它不需要 API Key、费用可控、行为稳定，也能完整展示
状态机、调查室、证据审批、存档和双语界面。访客如果希望调用真实模型，可以在模型控制台
添加自己的 OpenAI-compatible API（BYOK）；个人连接失败时不会回退消耗平台额度。

### 用 Render Blueprint 上线

1. 把当前分支合并到 GitHub 默认分支。
2. 在 Render 选择 **New → Blueprint**，连接 EverStory 仓库。
3. Render 会读取仓库根目录的 `render.yaml`，使用 `Dockerfile` 构建 Web，并创建同区的
   PostgreSQL 与 Key Value；容器每次启动前都会执行 `alembic upgrade head`。
4. 首次演示保留 `LLM_MODE=stub`；`ARK_ENABLE_CATALOG=true` 只展示目录，未填写密钥的
   模型不会被分配或调用。
5. 等待 `/api/health` 健康检查通过，Render 会生成类似
   `https://everstory-xxxx.onrender.com` 的地址；该平台实际生成的域名才是公开演示地址。
6. 如需自定义域名，在 Render 的 **Settings → Custom Domains** 中绑定域名并按提示配置 DNS。

免费实例可能休眠，首次访问会有冷启动。Blueprint 中 PostgreSQL 是账号、案件、存档、
用量和 BYOK 密文的权威数据源；Key Value 只保存可重建的 TTL、限流桶和短期锁。
Render 免费 PostgreSQL 目前会在创建 30 天后到期，容量为 1 GB、无备份；免费 Key Value
重启会清空。因此这套默认值适合作品集试玩，不适合长期生产。正式公开运营前应把
PostgreSQL 升级为付费实例并开启备份，Key Value 是否付费取决于是否需要缓存持久化。

## 是否启用平台真实模型

公开作品集推荐以下优先级：

1. **默认 Stub + 访客可选 BYOK**：最安全，适合公开链接。
2. **平台赠送小额度**：需要账号或匿名会话限额、请求频率限制、每日预算和熔断。
3. **无限平台 Key**：不建议，公开地址会产生盗刷和账单风险。

如要启用平台模型，把密钥仅放到 Render Environment，不要提交到 Git。`LLM_MODE=api`
会启用真实调用；`PLATFORM_SESSION_TOKEN_LIMIT` 控制单浏览器运行时的平台 Token 上限，
`PLATFORM_ACCOUNT_DAILY_TOKEN_LIMIT` 通过 Redis 控制同一账号跨案件、跨实例的每日总量。
请求前会预留提示词估算加最大输出 Token，完成后按真实 usage 结算；连续供应商故障会触发
冷却熔断。`LIVE_LLM_REQUIRE_ACCOUNT=true` 时，游客不能切换到在线 API。
火山方舟目录还需 `ARK_ENABLE_CATALOG=true`。正式使用前应确认所购套餐允许游戏/智能体
工作负载，Coding Plan 端点不应在未确认条款时直接作为公开游戏后端。

## 当前数据保存方式

- 本地 Python（无 URL）：命名存档写 JSON，实时运行态保存在进程内。
- Docker Compose：默认启动 Web + PostgreSQL 16 + Redis 7；数据库保存实时运行态、
  哈希认证会话、命名存档和 Token 账本，Redis 提供 TTL、限流和会话锁。
- Render Blueprint：自动绑定免费托管 PostgreSQL 的 Internal URL 与 Key Value URL；
  PostgreSQL 保存权威数据，Key Value 仅承担 TTL、限流和运行档锁。
- 玩家 BYOK：游客只在服务进程内保存；注册账号在 PostgreSQL 中保存 AES-256-GCM
  信封密文，完整密钥不返回浏览器，也不进入运行态 JSON、Redis 或用量账本。
- 邮箱登录：本地 `development` 模式可以在账号面板显示测试验证码；公网可使用 SMTP，
  也可设置 `AUTH_EMAIL_MODE=resend`、`AUTH_RESEND_API_KEY` 与 `AUTH_EMAIL_FROM`。
  Render Blueprint 默认 `disabled`，不会意外成为邮件中继。
- 运营控制台：`ADMIN_EMAILS` 配置逗号分隔的管理员邮箱；该邮箱完成验证码登录后可访问
  `/admin`，查看不含 PII 和密钥的灰度用量、供应商就绪与熔断状态。

### 数据库初始化与迁移

开发环境默认 `DATABASE_AUTO_CREATE=true`，便于首次启动。Render Blueprint 设置为
`false`，并通过 Docker 启动命令先执行：

```bash
alembic upgrade head
```

随后设置 `DATABASE_AUTO_CREATE=false`，让 Alembic 成为唯一的 Schema 变更入口。核心变量：

```ini
DATABASE_URL=postgresql+psycopg://user:password@host:5432/everstory
REDIS_URL=redis://host:6379/0
SESSION_TTL_SECONDS=2592000
COOKIE_SECURE=true
CSRF_ENFORCE=true
AUTH_CHALLENGE_SECRET=<至少 32 字节随机值>
AUTH_EMAIL_MODE=smtp
AUTH_SMTP_HOST=smtp.example.com
AUTH_SMTP_PORT=587
AUTH_SMTP_USERNAME=<账号>
AUTH_SMTP_PASSWORD=<密码或应用专用密码>
AUTH_SMTP_FROM=no-reply@example.com
# 或使用 Resend：
# AUTH_EMAIL_MODE=resend
# AUTH_RESEND_API_KEY=<服务端密钥>
# AUTH_EMAIL_FROM=EverStory <login@example.com>
ADMIN_EMAILS=owner@example.com
BYOK_MASTER_KEY=<至少 32 字符的随机值>
BYOK_MASTER_KEY_ID=prod-v1
BYOK_PREVIOUS_MASTER_KEYS={}
RATE_LIMIT_REQUESTS=60
RATE_LIMIT_WINDOW_SECONDS=60
PLATFORM_ACCOUNT_DAILY_TOKEN_LIMIT=20000
PLATFORM_TOKEN_RESERVATION=2048
PLATFORM_CIRCUIT_FAILURE_THRESHOLD=3
PLATFORM_CIRCUIT_COOLDOWN_SECONDS=300
LIVE_LLM_REQUIRE_ACCOUNT=true
INFRA_STRICT=true
```

## 多用户生产版本的后续增强

```text
Browser
  → HTTPS / CDN / WAF
  → FastAPI instances
      → PostgreSQL: users, saves, conversations, tasks, evidence, usage ledger
      → Redis: sessions, rate limits, streaming coordination, short-lived locks
      → KMS/Secret Manager: master key and encrypted BYOK credentials
      → Object storage: screenshots, exports, large replay artifacts
      → Model providers
```

- 身份：游客会话、双 Cookie、租户过滤、邮箱验证码、游客升级/合并、账号案件切换、
  CSRF 与设备撤销已实现；后续可增加 OAuth、数据导出和账号删除流程。
- 数据库：PostgreSQL 持久层已实现游客/注册身份、运行态、存档和用量账本；下一步补充
  备份恢复演练和删除账号的数据生命周期。
- 凭据：已实现本地主密钥提供器的 AES-256-GCM 信封加密、账号 AAD 绑定和旧版本
  Keyring 解密；生产环境建议再接云 KMS/Secret Manager，并做在线批量 rewrap。
- 配额：Redis 原子会话限流、账号每日预算、供应商熔断、PostgreSQL 用量账本与管理员
  聚合面板已实现；生产告警仍建议接入托管监控服务。
- 多实例：SSE 事件、任务锁和会话状态需要共享存储或消息系统，不能依赖单个 Python 进程。
- 运维：结构化日志、错误追踪、调用延迟/失败率、成本告警、数据库备份和删除账号流程。

## 上线前检查

```bash
python -m unittest discover -s tests -v
python -m scripts.test_model_connections       # 仅在配置真实密钥时
docker compose up --build
# 浏览器检查 /、/settings、/api/health
```

公开仓库还应确认 `.env` 未被跟踪、截图没有密钥、README 的图片与 GIF 能直接加载、CI
通过。当前仓库的 `render.yaml` 已把 Stub 设为默认值，避免部署后立即产生模型费用。
