(() => {
  "use strict";

  const TEXT = {
    en: {
      enter: "ENTER ›", tagline: "A world that cannot lie", taglineCaps: "A WORLD THAT CANNOT LIE", worldStable: "WORLD STABLE",
      team: "Team", journal: "Journal", inventory: "Inventory", worldTruth: "World truth",
      save: "Save", load: "Load", newWorld: "New world", worldTime: "WORLD TIME", turn: "TURN",
      storm: "STORM APPROACHING", activeLead: "ACTIVE LEAD", liveStory: "LIVE STORY",
      chatHint: "Speak freely · the engine decides what is true", prompt: "WHAT WILL YOU DO?",
      inputPlaceholder: 'Try: "walk toward the lighthouse" or "examine the tide chart"…',
      inputHint: "ENTER to act · FREE TEXT is understood by EverStory", worldInspector: "WORLD INSPECTOR",
      record: "Keepers' Record", live: "LIVE", seaChart: "Sea Chart", caseMap: "CASE MAP",
      mapHint: "select a connected route to travel", shipLog: "Ship's Log", events: "EVENTS",
      secureChannel: "SECURE TEAM CHANNEL", room: "Investigation Room", discussion: "Discussion",
      caseBoard: "Case board", factBoundary: "FACT BOUNDARY", boundaryText: "Agent claims remain hypotheses until confirmed by the world.",
      analyst: "@ Analyst", skeptic: "@ Skeptic", field: "@ Field", send: "Send",
      teamPlaceholder: "Message the investigation team…", leadStatus: "You are the Lead Investigator.",
      turns: "turns", time: "time", flags: "Flags", relationships: "Relationships",
      worldState: "World state", charactersItems: "Characters & items", characters: "Characters",
      items: "Items", quests: "Quests", empty: "empty", yes: "yes", no: "no", currentPosition: "CURRENT POSITION",
      route: "ROUTE", otherLocations: "Other charted locations", noRoute: "No route from here.",
      none: "None", noEvents: "no events yet", ownedBy: "owned by", locked: "locked", lit: "lit",
      someoneWaits: "Someone waits here.", availableInspect: "Available to inspect.", itIsLocked: "It is locked.",
      confirmed: "confirmed", clue: "clue", clues: "clues", awaiting: "awaiting you",
      actionProposal: "ACTION PROPOSAL", approvedResult: "APPROVED RESULT", complete: "complete",
      approve: "Approve", consumesTurn: "consumes 1 turn", caseOnly: "case-board only",
      replyingTo: "replying to", challengeCheck: "challenge / hypothesis check", target: "Target",
      reviewRecorded: "review recorded", confirmedEvidence: "CONFIRMED EVIDENCE", openActions: "OPEN ACTIONS",
      scenes: "Scenes", objects: "Objects", people: "People", approveFromBoard: "Approve from board",
      turnLabel: "TURN", verifiedBy: "Verified by", noDescription: "No additional description recorded.",
      noEvidenceTitle: "No confirmed evidence yet", noEvidenceHelp: "Ask the Field Investigator to inspect the current scene, then approve the proposed action.",
      worldNarrator: "World Narrator", liveNarration: "LIVE NARRATION", characterDialogue: "CHARACTER DIALOGUE",
      you: "You", youShort: "YOU", leadInvestigator: "Lead Investigator",
      composingNarration: "The world is composing its response…", noNarrationReturned: "The world changed without a narration.",
      investigationRecord: "INVESTIGATION RECORD", keepersJournal: "The Keeper's Journal",
      personalEffects: "PERSONAL EFFECTS", closeInventoryHint: "Press I or ESC to close",
      carriedItem: "Carried item", packEmpty: "Your pack is empty.",
      guestAccount: "Guest", accountTitle: "Player account",
      guestAccountHelp: "You are playing as a guest. Verify an email to attach this investigation to your account.",
      emailAddress: "Email address", sendCode: "Send code", verificationCode: "Verification code",
      verifyAndSave: "Verify and save", accountSynced: "This investigation belongs to your verified account.",
      activeSessions: "Active sessions", refresh: "Refresh", logout: "Sign out", revoke: "Revoke",
      accountInvestigations: "Your investigations", resumeInvestigation: "Resume", currentInvestigation: "CURRENT",
    },
    "zh-CN": {
      enter: "进入 ›", tagline: "一个不会说谎的世界", taglineCaps: "一个不会说谎的世界", worldStable: "世界状态稳定",
      team: "调查组", journal: "日志", inventory: "物品", worldTruth: "世界真相",
      save: "存档", load: "读档", newWorld: "新案件", worldTime: "世界时间", turn: "回合",
      storm: "风暴正在逼近", activeLead: "当前线索", liveStory: "实时剧情",
      chatHint: "自由行动 · 由规则引擎决定事实", prompt: "你准备怎么做？",
      inputPlaceholder: "例如：前往灯塔，或检查潮汐图……",
      inputHint: "按 ENTER 行动 · EverStory 支持自然语言", worldInspector: "世界状态检查器",
      record: "守塔人档案", live: "实时", seaChart: "盐岩岛海图", caseMap: "案件地图",
      mapHint: "选择已连通路线即可移动", shipLog: "调查日志", events: "事件",
      secureChannel: "加密调查频道", room: "联合调查室", discussion: "讨论",
      caseBoard: "案件板", factBoundary: "事实边界", boundaryText: "智能体结论在世界状态确认前都只是推测。",
      analyst: "@ 分析师", skeptic: "@ 质疑者", field: "@ 现场调查员", send: "发送",
      teamPlaceholder: "向调查组发送消息……", leadStatus: "你是本案的首席调查员。",
      turns: "回合", time: "时间", flags: "状态标记", relationships: "关系",
      worldState: "世界状态", charactersItems: "角色与物品", characters: "角色",
      items: "物品", quests: "案件目标", empty: "空", yes: "是", no: "否", currentPosition: "当前位置",
      route: "路线", otherLocations: "其他已知地点", noRoute: "当前没有可用路线。",
      none: "无", noEvents: "尚无事件", ownedBy: "持有人", locked: "已锁", lit: "已点亮",
      someoneWaits: "有人正在这里等候。", availableInspect: "可以进一步检查。", itIsLocked: "它被锁住了。",
      confirmed: "已确认", clue: "条线索", clues: "条线索", awaiting: "等待你的批准",
      actionProposal: "行动提案", approvedResult: "批准结果", complete: "已完成",
      approve: "批准", consumesTurn: "消耗 1 回合", caseOnly: "仅写入案件板",
      replyingTo: "回复", challengeCheck: "质疑 / 假设核验", target: "目标",
      reviewRecorded: "复核已记录", confirmedEvidence: "已确认线索", openActions: "待批准行动",
      scenes: "场景", objects: "物品", people: "人物", approveFromBoard: "在案件板中批准",
      turnLabel: "回合", verifiedBy: "核验人", noDescription: "没有记录额外说明。",
      noEvidenceTitle: "尚无已确认线索", noEvidenceHelp: "请现场调查员勘查当前场景，然后批准相应行动。",
      worldNarrator: "世界叙事者", liveNarration: "实时叙事", characterDialogue: "角色对话",
      you: "你", youShort: "我", leadInvestigator: "首席调查员",
      composingNarration: "世界正在组织回应……", noNarrationReturned: "世界已经变化，但没有返回叙事文本。",
      investigationRecord: "调查记录", keepersJournal: "守塔人日志",
      personalEffects: "随身物品", closeInventoryHint: "按 I 或 ESC 关闭",
      carriedItem: "随身携带", packEmpty: "你的背包还是空的。",
      guestAccount: "游客", accountTitle: "玩家账号",
      guestAccountHelp: "你正在以游客身份调查。验证邮箱后，可将当前案件归入你的账号。",
      emailAddress: "邮箱地址", sendCode: "发送验证码", verificationCode: "验证码",
      verifyAndSave: "验证并保存", accountSynced: "当前调查已归属于你的已验证账号。",
      activeSessions: "活跃设备", refresh: "刷新", logout: "退出登录", revoke: "下线",
      accountInvestigations: "你的案件", resumeInvestigation: "继续调查", currentInvestigation: "当前案件",
    },
  };

  const VALUES_ZH = {
    "The Lost Lighthouse": "失落灯塔", "Storm Shore": "风暴海岸", "Keeper's Cottage": "守塔人小屋",
    "Lighthouse Ground Floor": "灯塔底层", "Lighthouse Tower": "灯塔塔身",
    "Lantern Room": "灯室", "Dock": "码头", "Boat Shed": "船棚",
    "Cliff Path": "悬崖小径", "Sea Cave": "海蚀洞",
    "Prove the lighthouse was sabotaged": "证明灯塔遭到人为破坏",
    "Identify and confront the saboteur": "找出并当面对质破坏者",
    "Light the lighthouse": "重新点亮灯塔", "Learn the keeper's secret": "查明守塔人的秘密",
    "Follow the evidence": "沿着证据继续调查",
    "Reach shelter and establish contact with the investigation team": "寻找庇护并与联合调查组建立联系",
    "rusty key": "生锈的钥匙",
    "oil can": "油罐", "lantern": "提灯", "iron chest": "铁箱", "flint": "燧石",
    "logbook": "航海日志", "coiled rope": "盘绳", "severed fuel line": "被切断的燃油管",
    "salvage ledger": "打捞账本", "annotated tide chart": "批注潮汐图",
    "You": "你", "Lead Investigator": "首席调查员", "Case Director": "案件主管",
    "Field Investigator": "现场调查员", "Case Analyst": "案件分析师", "Skeptic": "质疑者",
    "true": "是", "false": "否", "knows": "认识", "player": "玩家",
    "mara": "Mara", "elias": "Elias Ward", "celia": "Dr. Celia Thorne", "inventory": "玩家物品栏",
    "scene": "场景", "item": "物品", "character": "人物", "testimony": "证词", "conclusion": "结论",
    "Severed fuel line examination": "检查被切断的燃油管", "Salvage ledger examination": "检查打捞账本",
    "Annotated tide-chart examination": "检查批注潮汐图", "Elias Ward testimony": "Elias Ward 的证词",
    "Mara testimony": "Mara 的证词", "Dr. Celia Thorne testimony": "Dr. Celia Thorne 的证词",
    "Case Analyst corroboration": "案件分析师复核",
    "current target": "当前目标", "Case record": "案件记录",
    "lighthouse_lit": "灯塔已点亮", "case_solved": "案件已侦破", "accused": "被指控者",
    "gave_oil": "已交付油罐", "learned_secret": "已知晓守塔人秘密", "ending": "结局已触发",
    "interviewed_mara": "已询问 Mara", "interviewed_elias": "已询问 Elias",
    "interviewed_celia": "已询问 Celia", "found_cut_line": "已发现被切断的燃油管",
    "found_salvage_ledger": "已发现打捞账本", "verified_tide_timeline": "已核实潮汐时间线",
    "A castaway who washed up on Saltrock Island.": "一名被海浪冲上盐岩岛的遇难者。",
    "Rain lashes a black-stone beach where the sea has just thrown you ashore. Above the cliffs, a dead lighthouse cuts through the lightning; three paths lead toward shelter, the dock, and the tower.": "暴雨抽打着黑石海滩，海浪刚刚把你抛上岸。悬崖上方，熄灭的灯塔刺入闪电；三条小路分别通往庇护所、码头与塔楼。",
    "The old lighthouse keeper. She knows what happened to the previous keeper.": "年迈的灯塔守护人，她知道前任守塔人身上发生了什么。",
    "The island's harbormaster and salvage broker. His neat coat cannot hide tar beneath his fingernails.": "岛上的港务长兼打捞商。他整洁的外套掩盖不了指甲缝里的焦油。",
    "A coastal researcher stranded by the storm. Her tide records make her a witness—and an early suspect.": "一名被风暴困住的海岸研究员。她的潮汐记录让她既是证人，也是早期嫌疑人。",
    "A damp stone room. A spiral staircase climbs into the tower, and a logbook lies on a table.": "潮湿的石室里，螺旋楼梯通向塔身，一本航海日志摊在桌上。",
    "A narrow stairwell spiralling up to the lantern room.": "狭窄的旋转楼梯一直通往灯室。",
    "The glass-walled top of the lighthouse. The great lantern sits dark and empty.": "灯塔顶部四周环绕着玻璃，巨大的灯具漆黑而空寂。",
    "A tidy cottage with a cold fireplace. A lantern hangs by the door.": "整洁的小屋里壁炉冰冷，一盏提灯挂在门边。",
    "A rotting wooden dock. A rowboat rocks in the surf.": "腐朽的木码头旁，一艘划艇随着海浪摇晃。",
    "A shack smelling of tar and salt. An oil can sits on a shelf.": "棚屋里弥漫着焦油和盐味，架子上放着一罐灯油。",
    "A narrow path along the cliffs, leading down to a sea cave.": "悬崖边的狭窄小径一路通往海蚀洞。",
    "A cold cave that fills with spray at high tide. Something glints in the sand.": "冰冷的洞穴在涨潮时水雾弥漫，沙地里有什么东西正在闪光。",
    "A corroded brass key.": "一把锈蚀的黄铜钥匙。", "A can of lamp oil.": "一罐灯油。",
    "The lighthouse lantern, cold and dark.": "灯塔的灯具冰冷而黑暗。", "A heavy iron chest, locked.": "一只上锁的沉重铁箱。",
    "A steel striker and flint for making sparks.": "一套用来打火的钢片和燧石。",
    "The keeper's logbook. The last entry is dated the night the light went out.": "守塔人的航海日志，最后一页写于灯光熄灭的那一夜。",
    "A strong rope.": "一根结实的绳索。",
    "The lantern's copper fuel line bears a clean tool cut rather than storm damage.": "灯具的铜制燃油管上有整齐的工具切口，并非风暴造成。",
    "A private cargo ledger hidden behind the boat-shed oil shelf.": "一本藏在船棚油架后面的私人货物账本。",
    "Celia's hourly tide observations, written in several inks.": "Celia 用不同墨水逐小时记录的潮汐观测。",
    "A narrow jaw tool cut cleanly through the copper. Tar packed into the opening matches the black residue used around the dock.": "窄口钳干净地剪断了铜管，塞在开口里的焦油与码头附近使用的黑色残留物一致。",
    "The final page lists cargo from the wreck before the lighthouse failed. The entries are initialed E.W., and one margin note reads: lamp dark by eleven.": "最后一页记录了灯塔失效前沉船上的货物，条目署名 E.W.，页边还写着：十一点前让灯熄灭。",
    "The continuous measurements corroborate Celia's timeline: the wind strengthened only after the light had already gone dark.": "连续测量结果印证了 Celia 的时间线：灯光熄灭后，风力才开始增强。",
    "The keeper eyes you wearily. \"The light has been out for a year, and the sea has grown restless.\"": "守塔人疲惫地打量着你。‘灯已经熄灭一年了，海也变得越来越不安。’",
    "She accepts the oil can with trembling hands. \"You'd make a fine keeper... The last one disappeared the night the light failed. His logbook says the lamp was sabotaged.\"": "她双手颤抖着接过油罐。‘你会成为一个好守塔人……上一个守塔人就在灯光熄灭那晚失踪了。他的日志说灯被人破坏了。’",
    "\"Some say the old keeper still walks the cliffs at night. Finish what he started — light the lamp.\"": "‘有人说老守塔人夜里仍在悬崖上游荡。完成他未竟的事——点亮灯塔。’",
    "Elias straightens his cuffs. \"I never entered that lighthouse. The lamp failed in the storm, and every crate I recovered was lawful salvage.\"": "Elias 整了整袖口。‘我从没进过那座灯塔。灯是在风暴中坏掉的，我打捞的每只箱子都合法。’",
    "Celia taps her tide chart. \"The storm arrived after midnight. The lighthouse fuel line was already failing before the first squall—and I saw Elias's launch leave the dock at eleven.\"": "Celia 敲了敲潮汐图。‘风暴午夜后才抵达。第一阵狂风前灯塔燃油管就已经出问题了——而且我在十一点看见 Elias 的汽艇离开码头。’",
    "Faced with the cut fuel line, the salvage ledger, Celia's tide timeline, and all three testimonies, Elias Ward breaks. He extinguished the lighthouse to drive a cargo ship onto Saltrock reef, then hid the wreck's cargo through his salvage office. The sabotage case is solved.": "面对被切断的燃油管、打捞账本、Celia 的潮汐时间线和三份证词，Elias Ward 终于崩溃。他熄灭灯塔，将货船诱向盐岩礁石，再通过打捞所藏匿沉船货物。破坏灯塔案告破。",
    "Team channel is open. Lead Investigator, assign a question or share a hypothesis; the team will challenge assumptions before they become conclusions.": "调查频道已经开启。首席调查员，请分配问题或提出假设；团队会在形成结论前互相质疑。",
    "Move the investigation team along a confirmed route. Approval advances the world turn.": "让调查组沿已确认路线移动；批准后世界回合会推进。",
    "Ask the person who is currently present for their authoritative testimony. Approval advances the world turn.": "询问当前在场人物并记录其权威证词；批准后世界回合会推进。",
    "Closely inspect the visible object and record the engine-confirmed observation. Approval advances the world turn.": "仔细检查可见物品并记录已确认观察；批准后世界回合会推进。",
    "Record only people, objects, routes, and scene details that the world currently exposes.": "只记录当前世界已经展示的人物、物品、路线和场景细节。",
    "Compare the active objective, recorded events, and confirmed evidence without adding a new fact.": "对照当前目标、调查日志和已确认线索，不添加未经确认的新事实。",
    "Check whether the current claim is supported, contradicted, or still unverified by confirmed evidence.": "检查当前说法是得到支持、遭到反驳，还是仍缺乏已确认线索验证。",
    "Use the current scene and case record to recommend one grounded follow-up action.": "根据当前场景和案件记录，提出一项有事实依据的后续行动。",
    "Review the confirmed case record": "复核已确认案件记录",
    "Stress-test the current hypothesis": "审查当前假设",
    "Prepare the next investigation step": "制定下一步调查计划",
    "I can travel to the Dock with the team if you approve. Once there, I’ll look for any clues tied to the tide chart or lantern. What should we prioritize first?": "如果你批准，我可以与调查组一起前往码头。抵达后我会寻找与潮汐图或提灯有关的线索。我们应当优先调查哪一项？",
  };

  const INLINE_ZH = [
    ["Lead Investigator", "首席调查员"], ["Case Director", "案件主管"],
    ["Field Investigator", "现场调查员"], ["Case Analyst", "案件分析师"],
    ["Skeptic", "质疑者"], ["Storm Shore", "风暴海岸"], ["Lighthouse Ground Floor", "灯塔底层"],
    ["Lighthouse Tower", "灯塔塔身"], ["Lantern Room", "灯室"],
    ["Keeper's Cottage", "守塔人小屋"], ["Boat Shed", "船棚"],
    ["Cliff Path", "悬崖小径"], ["Sea Cave", "海蚀洞"], ["Dock", "码头"],
    ["rusty key", "生锈的钥匙"], ["oil can", "油罐"], ["iron chest", "铁箱"],
    ["logbook", "航海日志"], ["coiled rope", "盘绳"], ["severed fuel line", "被切断的燃油管"],
    ["salvage ledger", "打捞账本"], ["annotated tide chart", "批注潮汐图"],
  ];

  function locale() {
    const stored = localStorage.getItem("everstory_locale");
    return stored === "en" || stored === "en-US" ? "en" : "zh-CN";
  }
  function t(key) { return (TEXT[locale()] || TEXT.en)[key] || TEXT.en[key] || key; }
  function value(input) {
    const text = String(input ?? "");
    if (locale() !== "zh-CN") return text;
    if (VALUES_ZH[text]) return VALUES_ZH[text];
    const patterns = [
      [/^Talk to (.+)$/, "与 $1 交谈"], [/^Take (.+)$/, "拿起$1"],
      [/^Go to (.+)$/, "前往$1"], [/^Look around$/, "观察四周"],
      [/^You move to the (.+)\.$/, "你前往了$1。"], [/^You take the (.+)\.$/, "你拿起了$1。"],
      [/^You make your way to the (.+)\.$/, "你来到了$1。"], [/^You pick up the (.+)\.$/, "你捡起了$1。"],
      [/^Time passes\.$/, "时间缓缓流逝。"], [/^Nothing happens\.$/, "什么也没有发生。"],
      [/^The (.+) is locked\.$/, "$1被锁住了。"], [/^The (.+) is already open\.$/, "$1已经打开了。"],
      [/^The (.+) clicks open\.$/, "$1咔哒一声打开了。"], [/^The (.+) blazes to life!$/, "$1猛然亮了起来！"],
      [/^You fill the (.+) with the (.+)\.$/, "你用$2装满了$1。"],
      [/^You open the (.+) and find: (.+)\.$/, "你打开$1，发现了：$2。"],
      [/^You examine the (.+)\. (.+)$/, "你检查了$1。$2"],
      [/^Using the (.+) on the (.+) doesn't seem to do anything\.$/, "对$2使用$1似乎没有任何效果。"],
      [/^I don't know what that refers to\.$/, "我不确定你指的是什么。"],
      [/^Inspect (.+)$/, "勘查$1"], [/^Travel to (.+)$/, "前往$1"],
      [/^Interview (.+)$/, "询问 $1"], [/^Examine (.+)$/, "检查$1"],
      [/^Arrived: (.+)$/, "已抵达：$1"], [/^Testimony: (.+)$/, "证词：$1"],
      [/^Examined: (.+)$/, "已检查：$1"], [/^Accusation: (.+)$/, "指控：$1"],
      [/^Scene inspected: (.+)$/, "已勘查场景：$1"], [/^Observed item: (.+)$/, "已观察物品：$1"],
      [/^Person present: (.+)$/, "在场人物：$1"],
      [/^Approved travel completed at world turn (\d+)\. (.+)$/, "已批准的移动在世界第 $1 回合完成。$2"],
      [/^Approved (.+) completed at world turn (\d+)\. (.+)$/, "已批准的$1在世界第 $2 回合完成。$3"],
      [/^Approved inspection complete at (.+)\. People present: (.+)\. Visible objects: (.+)\. Routes: (.+)\. (\d+) new confirmed evidence record\(s\) added; the world turn did not advance\.$/, "已完成对$1的批准勘查。在场人物：$2。可见物品：$3。路线：$4。新增 $5 条已确认线索；世界回合未推进。"],
      [/^Hypothesis audit complete against (\d+) confirmed evidence record\(s\)\. No unsupported claim was promoted to a fact; further scene evidence is still required\.$/, "已依据 $1 条确认线索完成假设审查。没有把未经支持的说法升级为事实，仍需更多场景证据。"],
    ];
    for (const [pattern, format] of patterns) {
      const match = text.match(pattern);
      if (match) return format.replace(/\$(\d+)/g, (_, index) => value(match[Number(index)]));
    }
    return INLINE_ZH.reduce(
      (result, [source, translated]) => result.split(source).join(translated),
      text
    );
  }
  function apply() {
    document.documentElement.lang = locale();
    document.querySelectorAll("[data-i18n]").forEach((element) => {
      element.textContent = t(element.dataset.i18n);
    });
    document.querySelectorAll("[data-i18n-placeholder]").forEach((element) => {
      element.placeholder = t(element.dataset.i18nPlaceholder);
    });
    const select = document.querySelector("#game-language");
    if (select) select.value = locale();
  }
  function setLocale(next) {
    localStorage.setItem("everstory_locale", next === "en" ? "en" : "zh-CN");
    apply();
    window.dispatchEvent(new CustomEvent("everstory:locale", { detail: locale() }));
  }
  window.EverStoryI18n = Object.freeze({ t, value, locale, setLocale, apply });
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", apply);
  else apply();
})();
