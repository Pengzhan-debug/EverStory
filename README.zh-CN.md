# EverStory —— 状态一致的持久化 AI 世界引擎

> **LLM 提案，状态机裁决。** 世界状态由确定性引擎管理，AI 永远没有改状态的权限。

[![CI](https://github.com/Pengzhan-debug/EverStory/actions/workflows/ci.yml/badge.svg)](https://github.com/Pengzhan-debug/EverStory/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12-3776AB?logo=python&logoColor=white)
![测试](https://img.shields.io/badge/tests-128%20passing-22C55E)
![License](https://img.shields.io/badge/license-MIT-0F172A)

[English README](README.md) · [系统架构](docs/architecture.md) · [真实模型评测](reports/agent-routing-evaluation-zh.md) · [公开部署](docs/DEPLOYMENT.md) · [身份与 BYOK 设计](docs/IDENTITY_AND_BYOK_DESIGN.md) · [面试演示](docs/DEMO.md) · [简历模板](docs/RESUME.md)

EverStory 是一个解决 **LLM 长程交互不可靠**（遗忘、自相矛盾、编造状态）问题的
混合架构项目：玩家用自然语言行动，大模型负责"听懂"和"叙述"，但世界的真相——
物品、位置、所有权、锁、时间——全部存放在结构化、版本化的状态图里。

它同时是一个**多人格式的 AI 协作破案游戏**：玩家担任首席调查员，现场调查员、
案件分析师和怀疑论者会在群聊中互相质疑；智能体只能提出任务，必须由玩家批准，
才能把确定性世界中的观察写入证据板。世界、群聊、任务和证据都支持存档恢复。

## 界面展示

![EverStory 产品演示](docs/assets/readme/everstory-demo.gif)

这张动图由仓库中的四张实机截图生成，可运行 `python scripts/build_demo_gif.py`
重新构建，GitHub 首页无需外链就能直接播放。

### 沉浸式游戏主界面

![EverStory 游戏主界面](docs/assets/readme/gameplay-overview.png)

场景图占据主要视觉空间，同时展示当前位置、案件目标、可见物品、建议行动、世界时间
和回合数。玩家可以直接使用自然语言行动。

### 有身份的多智能体调查群聊

![调查智能体互相质疑并提出任务](docs/assets/readme/agent-team-chat.png)

每个智能体拥有名称、职责和独立模型路由，可以回复并质疑其他角色；结构化任务必须等待玩家批准。

### 由引擎确认的案件证据板

![带来源和回合记录的案件证据](docs/assets/readme/case-evidence-board.png)

只有经过批准并由世界状态确认的观察才能进入证据板，同时记录地点、来源智能体、关联任务和确认回合。

### 多模型路由控制台

![EverStory 模型控制台](docs/assets/readme/model-control-console.png)

控制台将服务端平台连接与玩家 BYOK 连接明确分开：平台连接只读，个人连接失败时不会
偷偷回退到平台密钥。用量页提供当前玩家会话的额度、Token / 请求数 / 成本 / 延迟
堆叠柱状图，以及带智能体和 API 来源的调用明细。

调查智能体和游戏运行角色可以分别选择独立或共享的兼容 API，并集中查看连接状态、
延迟、Token 和失败诊断；完整密钥不会返回浏览器。

## 核心架构

```text
玩家自然语言
   ↓
① 意图解析      LLM 把 "捡起生锈的钥匙" 转成结构化动作
   ↓
② 规则校验      引擎对照真实世界状态检查前置条件
   ↓
③ 状态更新      确定性转移（位置/所有权/旗帜/时间）
   ↓
④ 叙述生成      基于*实际发生的状态变更*写叙述（grounded）
   ↓
⑤ 事实核查      一致性裁判复查叙述与状态增量，矛盾则重写
   ↓
⑥ 快照          世界状态版本化（哈希 + 回滚）
```

**为什么这样设计**：让 LLM 自己"记住"世界，100 回合后必然崩。把记忆放进确定性
数据结构，LLM 每回合只拿到当前状态的渲染——它不需要记住，也不会编造。

## 项目特色

1. **记忆不依赖模型**：状态即真相；实体卡 + 滚动摘要 + 事件日志每回合现算。
2. **可验证、可审计**：每回合内容哈希快照、回滚、事件日志；拒绝理由由状态机
   给出，不是模型编的。
3. **评测驱动**：同一批剧本跑三种架构（纯 LLM / 摘要记忆 / EverStory），
   实测数据见下。
4. **从轨迹学习世界动力学**：规则归纳器从 `(状态, 动作, 结果状态)` 自动学出
   规则（如"move 需要两地点连通"、"钥匙能解锁"），留出法 100% 准确。
5. **纯声明式世界**：世界是 TOML 数据（实体/地点/物品/对话/任务），加内容
   不用改引擎。
6. **强/弱模型可混厂商**：意图解析/裁判与叙述生成可分别用不同厂商的模型。
7. **多智能体协作但不越权**：角色拥有独立名称、头像、职责和 API 路由；群聊结论
   默认只是“假设”，智能体之间可以点名质疑。
8. **玩家审批 + 证据板**：智能体可提出前往、询问、检查和指控等结构化行动；关键
   物证检查和正式指控无法绕开联合调查室，审批后仍由状态机再次校验并执行。
9. **模型控制台**：在 `/settings` 配置多个兼容 API、按角色分配连接，并查看延迟、
   Token、失败率和调用状态。
10. **完整破案闭环**：玩家从风暴海岸醒来，取得三份证词、三条物理/时间线证据，
    再由分析师复核；缺少任一环节时案件主管都不能完成正式指控。
11. **游戏与控制台共享中英文语言**：主界面的 HUD、地图、案件目标、已知物品和调查
    群聊会即时切换，并与设置页共用语言偏好；底层实体 ID 和状态规则不受影响。

## 评测数据（DeepSeek deepseek-v4-flash 实测）

| 架构 | 平均记忆召回 | 说明 |
| --- | --- | --- |
| **EverStory（结构化状态）** | **100%** | 事实答案直接从状态读取（构造保证） |
| 纯 LLM（全文上下文） | 38.9% | 靠上下文硬记，回合一长就漏 |
| 摘要记忆 | 11.1% | 快模型压缩摘要时丢失关键事实 |

长程记忆衰减曲线（60 回合，20/40/60 检查点）见 `docs/eval-report-long.md`。

最新火山方舟多模型评测覆盖 **8 类角色、23 个角色—模型组合、69 个固定角色案例、
6 条跨智能体信息交换链和 3 个完整案件**。最终推荐路由平均分 **98.8%**、最低角色分
**93.3%**；信息传递、来源保留、污染拒绝、提案准确率、证据落地与完整破案均为
**100%**。最终可比较数据集共 123 次真实调用、118,513 Token。详见
[`reports/agent-routing-evaluation-zh.md`](reports/agent-routing-evaluation-zh.md)，原始 JSON
和阶段检查点也已随仓库保存；离线 CI 不消耗 API。

| 指标 | 结果 |
| --- | ---: |
| 推荐路由平均分 | **98.8%** |
| 最低角色分 | **93.3%** |
| 信息传递 / 来源保留 / 污染拒绝 | **100% / 100% / 100%** |
| 提案准确 / 证据落地 / 完整破案 | **100% / 100% / 100%** |
| 可比较真实调用 | **123 次** |
| 真实 Token | **118,513** |

## 快速开始

最省事的方式：

```bash
docker compose up --build
# 打开 http://127.0.0.1:8123
```

或使用本地 Python：

```bash
python -m venv everstory-env
everstory-env\Scripts\activate        # Windows
pip install -e ".[web]"

everstory             # 终端玩
everstory-serve       # Web UI → http://127.0.0.1:8123
everstory-eval --mode stub    # 离线评测
everstory-learn       # 规则归纳报告
python -m unittest discover -s tests -v   # 测试
```

当前包含 **128 项**无需 API Key 的自动化测试，完整验收路径覆盖智能体提议移动、
三次证人询问、三项证据检查、分析师复核以及受证据链约束的最终指控。

## 配置真实模型（.env）

```ini
LLM_MODE=api

# 每个浏览器运行时的平台 Token 额度；私有部署可设为 0 取消限制
PLATFORM_SESSION_TOKEN_LIMIT=50000

# 强模型：意图解析 + 一致性裁判
LLM_STRONG_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_STRONG_API_KEY=
LLM_STRONG_MODEL=qwen-plus

# 弱模型：叙述生成（可与强模型不同厂商）
LLM_CHEAP_BASE_URL=https://api.deepseek.com
LLM_CHEAP_API_KEY=
LLM_CHEAP_MODEL=deepseek-v4-flash
```

### 火山方舟多模型路由

设置 `ARK_ENABLE_CATALOG=true` 后，控制台会加载 7 个共享同一方舟凭据的模型端点；
方舟模型共用一个 Base URL，但每个模型使用独立的 API 凭据。填写 `.env.example` 中对应模型的 `ARK_*_API_KEY` 并重启后，已配置的模型会按能力启用以下路由：

| 智能体 | 模型 | 选择依据 |
| --- | --- | --- |
| 案件主管 | DeepSeek V4 Pro | 关键推理与全局决策 |
| 现场调查员 | Doubao Seed 2.0 Lite | 同分候选中现场响应延迟更低 |
| 案件分析师 | GLM 5.3 | 结构化归纳与证据分析 |
| 质疑者 | Kimi K2.7 Code | 长上下文交叉审视 |
| 意图解析器 | Doubao Seed 2.0 Lite | 低成本结构化解析 |
| 一致性裁判 | DeepSeek V4 Flash | 事实约束满分且延迟更低 |
| 世界叙事者 | MiniMax M3 | 剧情与风格表达 |
| NPC 对话 | Doubao Seed 2.0 Lite | 对话任务满分且 Token/延迟更低 |

可用 `python -m scripts.test_model_connections` 对全部方舟连接做不输出密钥的最小
健康检查；用 `python -m scripts.run_full_agent_evaluation` 运行可恢复的完整评测，或加
`--refresh-team` 复用角色/交换检查点，仅重跑最终路由的三个案件。Coding Plan 官方
定位主要是 AI 编程工具场景；将它用于游戏运行前应确认
套餐规则，通用线上游戏更适合使用常规方舟模型 API 或面向智能体的套餐。

服务端 `.env` 中的密钥属于平台默认连接，玩家只能查看脱敏状态，不能在页面修改或
取回。玩家可在 `/settings` 新增自己的 OpenAI 兼容连接；密钥只留在当前服务进程，
用量独立统计，调用失败也不会切换到平台密钥。

v1.3 身份系统已在 v1.2 持久层之上拆分 `everstory_auth` 与 `everstory_runtime`：PostgreSQL
只保存认证令牌哈希，并以 `user_id + runtime_id` 隔离实时世界、调查记忆、命名存档和
幂等 Token 用量账本；邮箱一次性验证码支持游客原地升级或合并到已有账号，验证后当前
案件不刷新、不丢失；账号面板可以列出名下案件并在不同浏览器间恢复。写接口使用双提交
CSRF，账号面板支持设备会话查看、下线和退出。
Redis 管理会话 TTL、写请求限流与跨进程
会话锁。未配置 `DATABASE_URL` / `REDIS_URL` 时仍可使用原来的本地模式。数据库迁移由
Alembic 管理，Docker Compose 会直接启动 Web、PostgreSQL 16、Redis 7 三个服务。
玩家 BYOK 目前仍不写入数据库；正式商业部署还需 KMS 信封加密与密钥轮换。

## 目录结构

```text
everstory/
  engine.py        确定性规则引擎 + WorldSession（快照/回滚/对话/结局）
  trajectory.py    轨迹记录 + 角色抽象化事实提取
  pipeline.py      回合管道：意图 → 引擎 → 叙述 → 事实核查
  llm/             供应商客户端（强/弱双端点）、意图解析、叙述、裁判
  memory/          实体卡、滚动摘要、上下文构建
  persistence.py   版本化存档/读档（世界 + 调查记忆）
  storage.py       SQLAlchemy 持久层（PostgreSQL/SQLite）与本地回退
  redis_runtime.py Redis 会话 TTL、限流、分布式锁与内存回退
  agents/          调查团队、互相质疑、任务提案与证据记录
  api/             FastAPI + 游戏 UI + 群聊证据板 + 模型控制台
  eval/            三架构评测 + 长程记忆衰减 + 报告
  learn/           规则归纳（符号世界模型）
  worlds/          声明式世界：失落灯塔、幽灵列车
docs/              架构文档、演示脚本、评测报告
```

## 演示与面试

见 [docs/DEMO.md](docs/DEMO.md) —— 90 秒演示脚本 + 高频追问回答；简历项目描述见
[docs/RESUME.md](docs/RESUME.md)，公开演示部署步骤见 [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)。

## License

MIT
