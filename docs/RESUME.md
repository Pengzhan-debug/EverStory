# EverStory 简历与面试模板

以下内容按真实实现范围编写，可直接裁剪后放入中文或英文简历。不要把“规划中的
PostgreSQL、登录和多实例部署”写成已完成。

## 中文简历模板

**EverStory｜状态一致的多智能体 AI 调查游戏**
`Python` `FastAPI` `SSE` `Vanilla JavaScript` `LLM Agent` `OpenAI-compatible API` `Docker` `CI`

- 设计“**LLM 提案、状态机裁决**”的混合架构，将自然语言解析为类型化动作；由确定性
  引擎统一管理位置、物品、任务、时间、证据和结局，隔离大模型幻觉与权威状态写入。
- 构建案件主管、现场调查员、分析师、质疑者等多智能体协作流程，支持点名回复、相互
  质疑、结构化任务提案、玩家审批、过期任务拒绝及带来源链的证据板。
- 实现 FastAPI + SSE 流式交互、世界与调查记忆存档、中英文界面、按角色模型路由、
  玩家 BYOK 隔离，以及 Token、延迟、成本和错误诊断控制台。
- 建立 102 项离线自动化测试与可断点恢复的真实模型评测；覆盖 8 类角色、23 个
  角色—模型组合、6 条跨智能体交换链和 3 个完整案件，推荐路由平均分 98.8%，
  信息传递、来源保留、污染拒绝、证据落地与完整破案均为 100%。

如简历空间较小，保留前 3 条；如果投递 AI 应用工程师，优先保留第 1、2、4 条。

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
5. 用架构图解释权威状态边界，再展示 102 项测试和真实模型评测报告。

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
- Created 102 offline tests and a checkpointed live-model benchmark covering
  23 role/model combinations, six cross-agent exchange chains, and three full
  cases; selected routes averaged 98.8% with 100% transfer, provenance,
  poison rejection, evidence grounding, and completion.

## 诚实的项目边界

EverStory v1.1 是可运行、可测试、可部署的单机/单实例作品集版本，不是已经商业化的
多人在线服务。当前匿名会话和 BYOK 凭据保存在服务进程中；多实例生产环境仍需账号体系、
PostgreSQL、Redis、KMS/Secret Manager、统一限流与监控。详细方案见
[DEPLOYMENT.md](DEPLOYMENT.md)。
