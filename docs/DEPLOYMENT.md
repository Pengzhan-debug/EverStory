# EverStory 公开演示部署指南

## 推荐的作品集演示方案

公开演示默认使用 **Stub 模式**。它不需要 API Key、费用可控、行为稳定，也能完整展示
状态机、调查室、证据审批、存档和双语界面。访客如果希望调用真实模型，可以在模型控制台
添加自己的 OpenAI-compatible API（BYOK）；个人连接失败时不会回退消耗平台额度。

### 用 Render Blueprint 上线

1. 把当前分支合并到 GitHub 默认分支。
2. 在 Render 选择 **New → Blueprint**，连接 EverStory 仓库。
3. Render 会读取仓库根目录的 `render.yaml`，使用 `Dockerfile` 构建服务。
4. 首次演示保留 `LLM_MODE=stub` 和 `ARK_ENABLE_CATALOG=false`，无需填写模型密钥。
5. 等待 `/api/health` 健康检查通过，Render 会生成类似
   `https://everstory-xxxx.onrender.com` 的地址；该平台实际生成的域名才是公开演示地址。
6. 如需自定义域名，在 Render 的 **Settings → Custom Domains** 中绑定域名并按提示配置 DNS。

免费实例可能休眠，首次访问会有冷启动；本地文件和进程内会话也可能随重启丢失。因此它
适合作品集试玩，不适合宣称为持久化多人生产服务。

## 是否启用平台真实模型

公开作品集推荐以下优先级：

1. **默认 Stub + 访客可选 BYOK**：最安全，适合公开链接。
2. **平台赠送小额度**：需要账号或匿名会话限额、请求频率限制、每日预算和熔断。
3. **无限平台 Key**：不建议，公开地址会产生盗刷和账单风险。

如要启用平台模型，把密钥仅放到 Render Environment，不要提交到 Git。`LLM_MODE=api`
会启用真实调用；`PLATFORM_SESSION_TOKEN_LIMIT` 控制单浏览器运行时的平台 Token 上限。
火山方舟目录还需 `ARK_ENABLE_CATALOG=true`。正式使用前应确认所购套餐允许游戏/智能体
工作负载，Coding Plan 端点不应在未确认条款时直接作为公开游戏后端。

## 当前数据保存方式

- 本地/Compose：存档写入 `everstory_saves` 卷，容器重启后可恢复。
- 当前公开单实例：浏览器以匿名运行时 Cookie 识别会话；路由和 BYOK 密钥只在服务进程
  内存中保存，完整密钥不返回浏览器。
- Render 免费实例：进程重启后内存会话会丢失，普通本地磁盘也不应视为永久存储。

## 多用户生产版本应增加

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

- 登录：邮箱验证码或 OAuth；游客可先试玩，注册后再绑定永久存档。
- 数据库：PostgreSQL 作为权威持久层；每张业务表带 `user_id`/`runtime_id` 做租户隔离。
- 凭据：只保存密文，使用 KMS envelope encryption；日志、异常和前端响应永不包含完整 Key。
- 配额：Redis 原子限流 + PostgreSQL 用量账本，同时设置单用户、单 IP、单日平台预算。
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
