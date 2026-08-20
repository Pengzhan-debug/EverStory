# EverStory — 1 分钟演示脚本

> 场景：面试 / 展示。打开 http://127.0.0.1:8123/（`everstory-serve` 启动），
> 页面：左聊天、右世界检视器（地图 / 背包 / 物品 / 任务 / 事件日志）。
> 当前默认 stub 模式，命令句式即可跑通，无需 API key。

## 开场白（约 10 秒）

> "这是一个持久化 AI 世界引擎。核心架构一句话：**LLM 提案，状态机裁决**——
> 玩家用自然语言行动，大模型负责听懂和叙述，但世界的真相（物品、位置、
> 所有权、锁）永远由右侧这个确定性状态图管理，AI 没有改状态的权限。"

## 通关演示（约 60-75 秒，照着敲）

先输入 `move to cave`（故意错误）：

> "从 cottage 直接去海蚀洞——引擎拒绝：'You can't go that way from here.'。
> 注意右侧地图，玩家还在原地。**拒绝原因是状态机算出来的，不是模型编的。**"

```text
move to lighthouse_ground
```

> "地图高亮切到 Lighthouse Ground Floor。看右侧事件日志，这条被接受（绿色）。"

```text
open chest
```

> "箱子是锁着的——引擎拒绝：'The iron chest is locked.'。
> 这就是**幻觉免疫**：模型不能假装打开了箱子，因为状态没变。"

```text
move to cliff_path
move to cave
take rusty key
```

> "拿到钥匙，背包里出现 rusty key。"

```text
move to lighthouse_ground
use rusty key on chest
open chest
take flint
```

> "钥匙解锁（物品状态从 locked 消失），开箱后火石被揭示。整个过程每步都有
> 事件日志，世界是可审计的。"

```text
move to cottage
move to dock
move to boat_shed
take oil can
move to cottage
use oil can on lantern
use flint on lantern
```

> "加油、点火，任务完成——右侧 Quests 变成 [x]。
> **叙述永远基于真实状态变更**，所以 100 回合也不会自相矛盾。"

## 结束语（约 10 秒）

> "评测上我做了一个三方对比：纯 LLM 聊天、摘要记忆、EverStory，用同一批
> 剧本测记忆召回和矛盾率——EverStory 从状态直接回答，准确率由构造保证；
> 而纯 LLM 靠上下文硬记。这个架构模式可以直接迁移到 agent 工具调用、
> 游戏 NPC、虚拟角色这些'必须长期一致'的场景。"

---

## 30 秒精简版（时间不够时）

```text
move to cave          → 展示规则拒绝（地图不动）
open chest            → 展示状态真实（锁着就是锁着）
move to lighthouse_ground → 地图高亮
use rusty key on chest
open chest
take flint
```

只讲两点：**LLM 不持有状态** + **每一步都有事件日志可审计**。

---

## 可能被追问的问题

**Q：为什么不直接把世界状态塞进 prompt 让模型记住？**
> 长上下文里模型会忘、会编。状态机保证确定性：被拒绝就是被拒绝，物品在谁
> 手里就是谁手里。评测的意义就在这里——对比三种架构的长期一致性。

**Q：和传统游戏引擎 / Inform 7 这类文字冒险框架有什么区别？**
> 引擎本身是载体，真正要解决的是 LLM 应用的可靠性：工具调用校验、状态与
> 生成分离、可回滚的事件溯源。这套模式直接适用 agent / NPC / 虚拟角色，
> 不限于文字游戏。

**Q：评测数字怎么来的？会不会自嗨？**
> 同一批脚本剧本跑三种架构；EverStory 的事实答案直接从状态读取（真实值），
> LLM 基线用上下文回答；stub 模式离线可复现，`--mode api` 出真实模型数字。
> 诚实声明：当前仓库里是 stub 占位，配 API key 后才是正式数据。

**Q：下一步想做什么？**
> 三件事：从交互轨迹归纳规则（学到的动力学，往 world model 靠）、NPC 自主
> 行为（LLM 提议世界事件 + 一致性校验）、分支叙事（快照天然支持）。
