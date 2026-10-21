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

**EverStory｜多智能体 AI 调查游戏与可验证世界引擎**

**技术栈：** Python、FastAPI、SSE、Multi-Agent、PostgreSQL、Redis、SQLAlchemy、Docker Compose

**测试工具：** pytest、Requests/HTTPX、Playwright、Allure、Locust、GitHub Actions

- 独立开发多智能体 AI 调查游戏，支持自然语言行动、团队讨论与证据推理；采用“LLM 提案、状态机裁决”架构，将位置、物品、任务与证据存入结构化状态图，约束模型幻觉与越权写入。
- 构建案件主管、现场调查员、分析师、质疑者等 8 类角色，支持点名回复、相互质疑、结构化任务提案与玩家审批；为证据关联来源、任务和回合，支持过期任务拒绝与案件追溯。
- 基于 FastAPI + SSE 实现流式交互与中英文界面，按角色接入多模型路由；提供 Token、延迟、成本、错误率与熔断状态诊断，支持模型配置和质量问题定位。
- 基于 PostgreSQL / SQLAlchemy 持久化世界、调查记忆、存档及幂等用量账本，结合 Redis 实现会话 TTL、接口限流与跨进程锁；使用 Alembic 管理迁移，Docker Compose 编排部署。
- 实现游客与账号运行档隔离、邮箱验证码登录及设备会话管理；使用 AES-256-GCM 信封加密与账号绑定 AAD 保存 BYOK 凭据，避免明文密钥进入运行态及前端响应。
- 使用 pytest + Requests/HTTPX 构建接口回归，新增 63 项参数化用例并修复 3 类问题；结合 Playwright + Allure 验证 10 个页面流程，覆盖审批、存取档、会话隔离与异常恢复，接入 GitHub Actions。
- 使用 Locust 验证并发下的回合与状态一致性，本地 Stub/SQLite 环境 7 轮 CSV 记录 8,537 次请求、0 次失败；结合固定案例检查 Agent 提案、权限与证据来源，并复核历史模型评分。

### 技能栏表述

- **测试基础与用例设计：**能够使用等价类、边界值和场景法设计用例，开展功能与回归测试，完成缺陷记录、复现和跟踪。
- **计算机网络基础：**了解 TCP/IP、HTTP/HTTPS、DNS，能够分析请求与响应、常见状态码及 Cookie/Session 机制。
- **接口自动化测试：**能够使用 Python、pytest、Requests/HTTPX 编写接口自动化脚本，结合 fixture、参数化和 Mock 组织用例，完成请求发送、响应断言和异常场景测试。
- **Web 与性能测试：**能够使用 Playwright 编写 Web 自动化测试，使用 Allure 生成测试报告；使用 Locust 进行并发测试，分析响应时间、吞吐量和错误率。
- **数据库基础：**能够使用 SQL 完成常用查询和数据核对，了解 PostgreSQL、Redis 的基础使用。
- **环境部署与问题定位：**能够使用 Linux 查看日志和检查服务，使用 Git 管理代码、Docker Compose 搭建测试环境，并通过 GitHub Actions 执行自动化测试。
- **AI 应用与模型测试：**能够围绕 LLM/Agent、RAG 和工具调用编写测试与评测脚本，整理测试数据、分析输出结果；使用 PyTorch 完成模型训练、调试和指标评估。
- **编程与开发工具：**熟悉 Python、C，能够使用 FastAPI、Node.js、JavaScript 开发接口和自动化脚本，并使用 VS Code、PyCharm 及 AI 编程工具完成编码与调试。

<details>
<summary>测试补充材料与证据</summary>


| 简历数字 | 统计范围 | 证据 |
| --- | --- | --- |
| 63 项、3 类问题 | 新增 pytest 参数化回归；错误输入与超时处理 | [接口用例](../tests/pytest_api/test_contracts.py)、[实验说明](../reports/autumn-qa/测试实验与评测说明.md) |
| 6 项 HTTP、10 项页面流程 | 独立于原有回归套件；本地通过，Linux CI 通过 | [Requests](../qa/http/test_requests.py)、[Playwright](../qa/browser/test_game.py)、[系统实验](../reports/system-qa/测试技术栈与实验.md) |
| 8,537 次、0 失败、P95 1.0–1.2 秒 | 7 轮本机 Stub/SQLite 负载 CSV 快照；P95 为 30 用户两轮结果 | [完整分接口数据](../reports/system-qa/results.json)、[Locust 脚本](../qa/performance/locustfile.py) |
| 8/8、未授权修改 0 | 固定离线 Agent 场景的审批及权限检查 | [离线评测](../reports/autumn-qa/offline-evaluation.md) |
| 69 份、98.8% | 历史输出重新评分；在相同 3 个固定案例上选路由，尚无独立测试集验证 | [评分复核](../reports/autumn-qa/historical-rescored.md) |
| 222 项、16 项 | 回归通过数与 HTTP/页面通过数分别统计；本地另有 3 项基础设施用例跳过，由 CI 使用真实 PostgreSQL/Redis 验证 | [CI 配置](../.github/workflows/ci.yml) |

性能数据仅作为本机 Stub/SQLite 基线；120 秒为短时持续测试。窄视口用例验证交互可用性，尚未完成真实手机或全部浏览器的兼容性测试。复现命令、Allure 查看方式与面试说明见[系统测试实验](../reports/system-qa/测试技术栈与实验.md)。

</details>

本段与测试岗 Word 简历的技能及项目措辞保持一致。公开仓库仅包含项目文案与实验结果。投递前应自行复现关键用例并能够解释断言和指标。

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
