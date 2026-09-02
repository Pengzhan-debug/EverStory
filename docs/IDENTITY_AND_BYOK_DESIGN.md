# EverStory 多用户身份、BYOK 与多实例设计

> 状态：v1.3 分阶段实施中。Phase A 游客身份核心与 Phase B1 邮箱登录已经实现；
> BYOK 密文持久化和多实例版本控制仍是后续阶段，不应视为已上线。

### 已实现的 Phase A

- 首次访问创建游客用户、认证会话和游戏运行档，旧 `everstory_session` 可无损继承。
- `everstory_auth` 与 `everstory_runtime` 分离；未知或过期认证令牌由服务端强制换发。
- PostgreSQL 只保存 SHA-256 令牌哈希，原始认证令牌只存在于 HttpOnly Cookie。
- 运行态、命名存档和 Token 用量查询均同时约束 `user_id + runtime_id`。
- `GET /api/auth/session` 返回最小游客身份摘要，健康检查和静态资源不会制造游客记录。
- Alembic `20260901_0002` 完成旧数据回填，并有空库迁移、跨用户伪造和重启恢复测试。

### 已实现的 Phase B1

- 邮箱六位一次性验证码可将游客原地升级，或把游客运行档事务性合并到已有账号。
- `login_challenges` 只保存邮箱 SHA-256 和带服务端密钥的验证码 HMAC；10 分钟过期、
  最多尝试 5 次，Redis 同时限制邮箱哈希与 IP 哈希的请求频率。
- 登录成功轮换认证与 CSRF 令牌，当前案件无需刷新即可继续；支持活跃会话列表、下线和退出。
- Cookie 认证写接口强制校验 `everstory_csrf` 与 `X-CSRF-Token` 双提交值。
- 开发模式可显式显示验证码；生产模式通过 SMTP 发送，Render 默认关闭邮件功能。

## 1. 目标

下一阶段不是简单增加一个登录框，而是把目前的匿名浏览器会话升级为可长期运营的
多用户数据边界：

- 游客无需注册即可开始游戏，不破坏当前试玩转化率。
- 游客注册后，当前案件、存档、调查记录和用量自动归入账号。
- 注册用户可跨浏览器、跨设备恢复存档和模型路由。
- 玩家 API Key 以密文持久化，前端和日志永远拿不到完整 Key。
- 平台额度与 BYOK 用量分账，并支持用户/IP/日预算限制。
- 两个以上 FastAPI 实例同时运行时，同一案件不会重复执行或覆盖新状态。

本阶段不包含付费订阅、好友系统、实时多人共同操作同一案件，也不把邮箱验证码系统
扩展成通用 IAM 产品。

## 2. 推荐产品方案

采用“游客优先、需要同步时再登录”：

1. 首次访问立即创建 `guest user + auth session + game runtime`，玩家直接开始。
2. 首页和控制台只显示轻量的“游客 / 保存到账号”入口，不强制弹窗。
3. 玩家首次保存 BYOK、跨设备同步或完成关键案件时，引导邮箱验证码登录。
4. 验证成功后原游客用户原地升级为注册用户，已有数据不复制、不丢失。
5. 已有账号的玩家登录时，在一个事务中把当前游客运行档转移到目标账号。

首版推荐邮箱一次性验证码，而不是自建密码：它没有密码重置和弱密码存储问题，移动端
体验也更直接。后续可在相同身份模型上增加 GitHub/Google OAuth。

## 3. 三层身份边界

```text
User（谁拥有数据）
  └── AuthSession（哪个浏览器已被授权）
        └── PlayerSession（正在玩的哪一局案件）
              ├── SaveGame
              ├── Team / conversation runtime
              └── LLM usage events

User
  ├── ApiConnection（加密 BYOK）
  └── AgentRouteAssignment（每个智能体使用哪个连接）
```

必须停止用同一个 Cookie 同时表示用户和游戏局。建议使用：

- `everstory_auth`：256-bit 随机不透明令牌，只在浏览器 Cookie 中出现；数据库只保存
  SHA-256 哈希。`HttpOnly + Secure + SameSite=Lax`。
- `everstory_runtime`：当前游戏局 UUID。它只能访问 `everstory_auth` 所属用户的数据。
- CSRF：所有 Cookie 认证的写接口使用双提交 Token；前端统一请求层添加请求头。

Cookie 轮换发生在登录、提权和账号合并之后，避免 session fixation。

## 4. PostgreSQL 数据模型

### users

| 字段 | 说明 |
| --- | --- |
| `id UUID PK` | 永久用户 ID |
| `kind` | `guest` / `registered` / `disabled` |
| `email` | 标准化邮箱；游客为空，注册后唯一 |
| `email_verified_at` | 邮箱验证时间 |
| `display_name` | 玩家显示名 |
| `created_at / updated_at / last_seen_at` | 生命周期 |
| `deleted_at` | 软删除与删除流程 |

### auth_sessions

| 字段 | 说明 |
| --- | --- |
| `id UUID PK`, `user_id FK` | 登录会话归属 |
| `token_hash BYTEA UNIQUE` | 原始令牌绝不入库 |
| `csrf_hash BYTEA` | 写请求校验 |
| `expires_at / revoked_at` | 过期与主动下线 |
| `user_agent_hash / ip_prefix` | 风险检测，不保存完整指纹 |

### login_challenges

PostgreSQL 保存邮箱哈希、验证码 HMAC、尝试次数、过期和消费时间；Redis 保存邮箱/IP
限频计数。验证码 10 分钟过期、最多 5 次尝试，数据库不保存验证码或挑战邮箱明文。

### player_sessions

沿用现有表，但改为真正的游戏运行档：

- `user_id` 不再等于 session id。
- 增加 `world_key`、`status`、`state_version BIGINT`、`last_event_id`。
- `runtime_payload JSONB` 继续保存版本化世界/群聊快照。
- 写入使用 `UPDATE ... WHERE state_version = :expected_version` 乐观锁。

### save_games / llm_usage_events

保留 `session_id`，同时增加直接 `user_id`，让每个查询都可以先执行租户过滤；数据库
约束或应用层断言必须保证 `save.user_id == player_session.user_id`。用量表增加 provider、
credential source、request id 和计费状态列，原始响应正文不入库。

### api_connections

| 字段 | 说明 |
| --- | --- |
| `id UUID PK`, `user_id FK` | 用户隔离 |
| `connection_key` | 用户范围内稳定 ID |
| `name/provider/base_url/model` | 非敏感连接元数据 |
| `credential_ciphertext BYTEA` | AES-256-GCM 密文 |
| `wrapped_data_key BYTEA` | KMS 加密后的数据密钥 |
| `nonce BYTEA / key_version` | 解密与轮换信息 |
| `credential_fingerprint` | 仅用于识别是否更换，不可还原 |
| `created_at / updated_at / last_tested_at` | 生命周期 |

`UNIQUE(user_id, connection_key)`；平台连接仍来自服务端环境，不写进玩家表。

### agent_route_assignments

`UNIQUE(user_id, agent_id)`，指向玩家连接或平台目录 connection key。路由与 Key 分开，
因此更换凭据不会修改智能体配置。

## 5. BYOK 信封加密

```text
玩家提交 API Key（HTTPS）
        |
        v
服务端生成随机 data key + nonce
        |
        +-- AES-256-GCM(API Key, AAD=user_id|connection_id|version)
        |
        `-- KMS.encrypt(data key)
               |
               v
PostgreSQL: ciphertext + wrapped_data_key + nonce + key_version
```

读取设置时只返回 `key_configured` 和固定长度掩码。模型调用前按需解开 data key，在本次
请求内构造客户端；不得把明文写入 runtime JSONB、Redis、异常、trace、评测结果或前端。

开发环境可以用 `BYOK_MASTER_KEY` 驱动本地 AES-GCM key provider，但生产环境必须使用
云 KMS/Secret Manager。两者实现统一 `KeyProvider.wrap/unwrap` 接口，便于测试和迁移。

密钥轮换流程：新增 master key version → 后台逐条解包并重新包装 data key → 验证完成后
禁用旧版本。删除连接时同时删除密文；删除账号进入短暂恢复期后物理清理。

## 6. API 设计

### 身份

```text
GET    /api/auth/session             当前用户、游客状态和 CSRF 信息
POST   /api/auth/email/request       请求邮箱验证码
POST   /api/auth/email/verify        验证并升级/合并游客数据
POST   /api/auth/logout              撤销当前 auth session
GET    /api/auth/sessions            已登录设备列表
DELETE /api/auth/sessions/{id}       下线指定设备
DELETE /api/account                  启动账号删除流程
```

响应不区分“邮箱是否存在”，避免账号枚举。登录与验证码接口按 IP、邮箱哈希和设备三层限流。

### 模型连接

```text
GET    /api/model-connections
POST   /api/model-connections
PUT    /api/model-connections/{id}
DELETE /api/model-connections/{id}
POST   /api/model-connections/{id}/test
PUT    /api/agent-routes
```

现有 `/api/llm/settings` 在一个兼容周期内保留，内部转调新服务，之后再移除。所有连接查询
必须从认证上下文取得 `user_id`，不接受浏览器传入 user id。

### 游戏运行档

```text
GET  /api/runtimes
POST /api/runtimes
PUT  /api/runtimes/{id}/activate
```

原 `/api/world`、`/api/turn`、调查室和存档接口继续工作，但由 `everstory_runtime` 解析
当前局，并在数据库中同时校验用户归属。

## 7. Redis 与多实例一致性

Redis key 建议：

```text
auth:session:{token_hash}                 -> user/session 摘要，TTL
auth:otp:{email_hash}                     -> 验证码哈希、attempts，TTL 10m
rate:{scope}:{subject}:{window}           -> 原子计数
lock:runtime:{runtime_id}                 -> 短锁
budget:platform:{user_id}:{yyyy-mm-dd}    -> 当日平台预算
runtime:version:{runtime_id}              -> 最新 state_version
```

Redis 锁只用于减少冲突，不能作为唯一正确性来源。权威写入仍依赖 PostgreSQL
`state_version` 乐观锁：冲突时加载最新状态，并只对幂等请求进行一次重试。每个写请求携带
`Idempotency-Key`，对应结果进入短期 Redis/长期事件记录，防止断线重发导致重复回合。

FastAPI 的进程内 `RuntimeSlot` 只能作为热缓存。每次写前比较 Redis/数据库版本；版本不符
就丢弃本地缓存并重载。这样不要求粘性会话，也不会因为请求落到另一实例而回档。

## 8. 配额与计费边界

- 平台 API：请求前原子预留估算 Token，完成后按真实 usage 结算；失败释放未使用部分。
- 玩家 BYOK：不消耗平台 Token 预算，但仍受请求频率、并发和最大上下文限制。
- PostgreSQL `llm_usage_events` 是审计账本，Redis 是实时额度计数；定时任务核对二者。
- 限制层级：IP 防滥用 → auth session → user → provider → 平台每日总预算。
- 超额时明确返回 429/402 风格业务错误，不允许 BYOK 失败后回退平台密钥。

## 9. 前端设计

当前 Vanilla JS 足以实现这一阶段，不建议把身份系统和 React 重构绑在同一个版本里。

- 主游戏右上角显示“游客”或头像/名称，点击打开标准账号面板。
- 登录采用窄幅独立页或对话框：邮箱 → 验证码 → 成功后返回原页面，不重载游戏。
- 游客可以临时使用 BYOK；点击“加密保存到账号”时触发登录，未登录 Key 仍只在进程内。
- 控制台显示“仅本设备”或“已加密同步”，不展示安全实现宣传文字占据主界面。
- 账号页提供游戏档列表、活跃设备、用量、导出数据和删除账号。

## 10. 迁移顺序

1. [已完成] `0002_identity_core`：扩展 users，创建 auth_sessions，给业务表补 user_id。
2. [已完成] 回填现有数据：旧 `player_sessions.user_id` 保持指向对应 guest user，不丢档。
3. [兼容期] 接受旧会话 Cookie，同时签发新 auth/runtime Cookie，观察一个版本。
4. [已完成] `0003_account_auth`、游客升级/账号合并、CSRF 校验和设备撤销。
5. [待实现] `encrypted_connections`：创建 api_connections/agent_route_assignments。
6. [待实现] 控制台改用连接 CRUD；确认日志和响应没有密钥后再启用持久 BYOK。
7. [待实现] `runtime_versioning`：增加 state_version、幂等键和缓存失效。
8. [待实现] 删除旧 Cookie 兼容层和进程内连接配置。

任何数据库迁移都必须支持滚动部署：先加 nullable 字段并双写，回填完成后再加 NOT NULL
与唯一约束，不能让旧实例在发布过程中失效。

## 11. 测试与验收标准

### 身份与租户隔离

- 游客不登录可完成当前完整案件。
- 游客注册后，运行档、存档、调查证据和用量数量完全一致。
- 用户 A 无法通过猜测 runtime/save/connection id 读取或修改用户 B 数据。
- 登录后必须轮换 Cookie；退出和设备撤销立即失效。
- CSRF、账号枚举、验证码暴力尝试和开放重定向测试通过。

### 密钥安全

- 数据库、Redis、API 响应、日志、异常快照中搜索不到测试明文 Key。
- 错误 KMS key、篡改 nonce/ciphertext/AAD 时必须解密失败，不能降级明文。
- Key 轮换前后连接测试结果一致；删除连接后无法恢复密文。
- 个人连接失败时平台 Token 用量保持不变。

### 多实例

- 两个 API 实例并发提交同一 runtime，最多一个状态版本成功。
- 同一 Idempotency-Key 重试不会增加回合、证据或 Token 账本记录。
- 任一实例重启后可从 PostgreSQL 恢复；Redis 清空后不丢权威数据。
- 100 个并发游客下记录 p50/p95 延迟、数据库连接池、锁等待和错误率。

## 12. 分阶段交付

| 阶段 | 交付内容 | 可在简历上声明 |
| --- | --- | --- |
| A | 身份上下文、游客账号、双 Cookie、租户查询 | 游客隔离与持久会话 |
| B1 | 邮箱验证码、游客升级、账号归属 | 注册与匿名数据迁移 |
| B2 | 账号案件列表、运行档切换 | 显式跨设备恢复 |
| C | AES-GCM + KMS provider、连接 CRUD | 加密 BYOK 与密钥轮换 |
| D | 用户/IP/预算限流、幂等请求 | 多层配额与成本防护 |
| E | state_version、缓存失效、双实例压测 | 可验证的水平扩展 |

推荐下一次编码先完成 B2，并维持 Stub 为公开演示默认值。C 阶段涉及真实秘密，必须在
测试覆盖、日志脱敏和 KMS 配置全部完成后再上线。
