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
      items: "Items", quests: "Quests", empty: "empty", currentPosition: "CURRENT POSITION",
      route: "ROUTE", otherLocations: "Other charted locations", noRoute: "No route from here.",
      none: "None", noEvents: "no events yet", ownedBy: "owned by", locked: "locked", lit: "lit",
      someoneWaits: "Someone waits here.", availableInspect: "Available to inspect.", itIsLocked: "It is locked.",
      confirmed: "confirmed", clue: "clue", clues: "clues", awaiting: "awaiting you",
      actionProposal: "ACTION PROPOSAL", approvedResult: "APPROVED RESULT", complete: "complete",
      approve: "Approve", consumesTurn: "consumes 1 turn", caseOnly: "case-board only",
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
      items: "物品", quests: "案件目标", empty: "空", currentPosition: "当前位置",
      route: "路线", otherLocations: "其他已知地点", noRoute: "当前没有可用路线。",
      none: "无", noEvents: "尚无事件", ownedBy: "持有人", locked: "已锁", lit: "已点亮",
      someoneWaits: "有人正在这里等候。", availableInspect: "可以进一步检查。", itIsLocked: "它被锁住了。",
      confirmed: "已确认", clue: "条线索", clues: "条线索", awaiting: "等待你的批准",
      actionProposal: "行动提案", approvedResult: "批准结果", complete: "已完成",
      approve: "批准", consumesTurn: "消耗 1 回合", caseOnly: "仅写入案件板",
    },
  };

  const VALUES_ZH = {
    "The Lost Lighthouse": "失落灯塔", "Keeper's Cottage": "守塔人小屋",
    "Lighthouse Ground Floor": "灯塔底层", "Lighthouse Tower": "灯塔塔身",
    "Lantern Room": "灯室", "Dock": "码头", "Boat Shed": "船棚",
    "Cliff Path": "悬崖小径", "Sea Cave": "海蚀洞",
    "Prove the lighthouse was sabotaged": "证明灯塔遭到人为破坏",
    "Identify and confront the saboteur": "找出并当面对质破坏者",
    "Light the lighthouse": "重新点亮灯塔", "Learn the keeper's secret": "查明守塔人的秘密",
    "Follow the evidence": "沿着证据继续调查", "rusty key": "生锈的钥匙",
    "oil can": "油罐", "lantern": "提灯", "iron chest": "铁箱", "flint": "燧石",
    "logbook": "航海日志", "coiled rope": "盘绳", "severed fuel line": "被切断的燃油管",
    "salvage ledger": "打捞账本", "annotated tide chart": "批注潮汐图",
  };

  function locale() { return localStorage.getItem("everstory_locale") || "zh-CN"; }
  function t(key) { return (TEXT[locale()] || TEXT.en)[key] || TEXT.en[key] || key; }
  function value(input) {
    const text = String(input ?? "");
    if (locale() !== "zh-CN") return text;
    if (VALUES_ZH[text]) return VALUES_ZH[text];
    const patterns = [
      [/^Talk to (.+)$/, "与 $1 交谈"], [/^Take (.+)$/, "拿起$1"],
      [/^Go to (.+)$/, "前往$1"], [/^Look around$/, "观察四周"],
    ];
    for (const [pattern, format] of patterns) {
      const match = text.match(pattern);
      if (match) return format.replace("$1", value(match[1]));
    }
    return text;
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
