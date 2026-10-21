# EverStory 简历与面试模板

以下内容按真实实现范围编写，可直接裁剪后放入中文或英文简历。PostgreSQL/Redis
运行路径、游客身份隔离、邮箱验证码登录和本地主密钥信封加密已经实现，但云 KMS 托管和完整多实例无状态化仍属于后续工作。

## 中文简历模板

**EverStory｜状态一致的多智能体 AI 调查游戏**
`Python` `FastAPI` `SSE` `SQLAlchemy 2.0` `PostgreSQL` `Redis` `Alembic` `Vanilla JavaScript` `LLM Agent` `OpenAI-compatible API` `Docker Compose` `CI`

- 设计“**LLM 提案、状态机裁决**”的混合架构，将自然语言解析为类型化动作；由确定性
  引擎统一管理位置、物品、任务、时间、证据和结局，隔离大模型幻觉与权威状态写入。
- 构建案件主管、现场调查员、分析师、质疑者等多智能体协作流程，支持点名回复、相互
  质疑、结构化任务提案、玩家审批、过期任务拒绝及带来源链的证据板。
- 实现 FastAPI + SSE 流式交互、世界与调查记忆存档、中英文界面、按角色模型路由、
  玩家 BYOK 隔离，以及 Token、延迟、成本和错误诊断控制台。
- 基于 SQLAlchemy 2.0 + PostgreSQL 持久化游客会话、实时世界快照、命名存档与幂等
  Token 用量账本；用 Redis 实现会话 TTL、固定窗口限流及跨进程会话锁，并由 Alembic
  管理 Schema、Docker Compose 编排 Web/PostgreSQL/Redis 三服务。
- 将用户身份与游戏运行档拆分为双 HttpOnly Cookie，数据库仅保存认证令牌哈希；所有
  运行态、存档与用量查询均以 `user_id + runtime_id` 进行租户隔离，并兼容旧游客存档。
- 实现邮箱一次性验证码登录、游客原地升级/账号合并、登录令牌轮换、双提交 CSRF 和
  设备会话撤销；验证码以服务端密钥 HMAC 保存，并按 IP/邮箱实施 Redis 限频。
- 为注册账号实现 AES-256-GCM 信封加密 BYOK：每次写入使用随机 data key，账号 ID
  绑定 AAD，主密钥按版本轮换；密钥不进入运行态 JSON、Redis、用量账本和前端响应。
- 建立 pytest 参数化接口回归与故障注入测试，离线回归本地 222 项通过；补充
  Requests 真实 HTTP 用例 6 项、Playwright 浏览器流程 10 项及 Allure 报告。
- 复核 8 类角色、23 个角色—模型组合的历史原始输出；所选路由在原有 3 个固定
  案例上的平均分为 98.8%。该分数来自同一评测集上的路由选择，尚未验证独立测试集泛化。

如简历空间较小，保留前 3 条；如果投递 AI 应用工程师，优先保留第 1、2、4 条。

## 软件测试 / AI 测试投递版本

**技术栈：** Python、pytest、Requests、HTTPX、Playwright、Allure、Locust、GitHub Actions。

- 基于等价类与边界值设计 63 项 pytest 接口用例，覆盖非法输入、CSRF、会话隔离、
  重复审批、限流、模型超时与持久化冲突；通过 Mock 故障注入定位并修复 3 类接口问题。
- 使用 Requests Session 对真实本地 HTTP 服务验证 Cookie、CSRF、JSON 请求、
  SSE 完成事件及存档隔离；使用 Playwright Page Object 验证行动、审批、存取档、
  刷新恢复、语言切换、网络失败恢复等 10 个页面流程，生成含截图的 Allure 报告。
- 使用 Locust 设计 5/15/30 用户分级负载和 15 用户短时持续测试，分析吞吐量、
  P95、失败率，并校验各会话的回合数和状态哈希；具体实测值与环境边界见
  [系统测试实验](../reports/system-qa/测试技术栈与实验.md)。
- 对 AI Agent 检查提案正确性、审批前越权修改、过期任务拒绝、证据来源和案件完成情况；
  对模型历史输出重新评分，区分规则指标、固定案例结果与独立测试集泛化。

**技能栏可裁剪为：** 能够使用 pytest + Requests/HTTPX 编写接口自动化用例，运用
fixture、参数化、Mock 和边界值设计验证异常处理及状态一致性；使用 Playwright 编写
页面流程测试，使用 Allure 生成报告，使用 Locust 进行并发负载测试并分析 P95、吞吐量
与失败率；了解基于固定样本和规则断言的 AI Agent 评测流程。

以上是项目已经实现的能力范围；投递前应自行复现并能够讲解关键用例及断言。

## 一句话介绍

我做了一个多智能体 AI 破案游戏：大模型负责提出行动、辩论和叙述，确定性状态机负责
世界真相、权限校验、证据来源和结局，因此智能体可以互相质疑，但不能凭空改写案件。

## 30 秒技术讲解

项目的核心边界是“LLM proposes, state machine decides”。智能体输出先解析为结构化
任务，关键检查和指控需要玩家批准；规则引擎重新校验并执行动作，记录事件和状态快照，
随后模型只能根据已发生的状态增量生成叙述。一致性裁判再次检查叙述，所以幻觉控制不只
依赖提示词，而是可以通过拒绝率、来源保留率和案件完成率进行测试。

## 适合面试展示的顺序

1. 用 15 秒展示游戏主界面和自然语言操作。
2. 打开联合调查室，让一个智能体提出任务、另一个智能体质疑。
3. 玩家批准检查，展示只有引擎确认的事实才进入证据板。
4. 打开模型控制台，展示不同角色的路由和 Token/延迟统计。
5. 用架构图解释权威状态边界，再展示 pytest、系统测试报告与历史模型评测范围。

## English version

**EverStory — State-consistent multi-agent AI investigation game**

- Designed a hybrid LLM/state-machine architecture that converts natural
  language into typed actions and prevents models from directly mutating
  authoritative entities, inventory, locations, quests, time, and evidence.
- Built a human-in-the-loop investigation workflow with named routed agents,
  mutual challenges, structured task approval, stale-task rejection, and
  provenance-preserving evidence gates for deterministic case resolution.
- Implemented FastAPI/SSE streaming, per-agent OpenAI-compatible routing,
  bilingual UI, persistent world/conversation saves, isolated player BYOK,
  and token, latency, cost, and failure diagnostics.
- Added SQLAlchemy/PostgreSQL persistence for guest sessions, runtime snapshots,
  saves, and an idempotent usage ledger, plus Redis-backed TTL, rate limiting,
  and cross-process session locks with Alembic migrations and Docker Compose.
- Split guest identity from game runtimes with separate HttpOnly cookies,
  server-issued hashed auth tokens, and user/runtime tenant filters on every
  durable runtime, save, and usage query.
- Added email-code guest upgrades/account merges, auth rotation, double-submit
  CSRF, device revocation, HMAC-protected challenges, and scoped Redis limits.
- Added account-scoped BYOK persistence with random data keys, AES-256-GCM
  envelope encryption, account-bound AAD, and versioned master-key rotation.
- Added parametrized pytest contracts and fault injection (222 local regression
  passes), plus six real HTTP and ten browser journeys with Allure reporting.
  Rescored archived outputs for 23 role/model combinations; selected routes
  averaged 98.8% on the same three fixed cases, without held-out validation.

## 诚实的项目边界

EverStory v1.3 是可运行、可测试、可部署的作品集版本，不是已经商业化的多人在线服务。
PostgreSQL/Redis 生产路径、游客隔离和邮箱登录已经实现并覆盖自动化测试；实际发送邮件
仍需部署者配置 SMTP；当前主密钥来自服务端环境。正式多实例环境仍需云 KMS/Secret Manager、IP/账号级
预算、缓存失效、监控和备份恢复。详细方案见 [DEPLOYMENT.md](DEPLOYMENT.md)。
