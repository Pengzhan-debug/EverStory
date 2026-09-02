const $ = (selector) => document.querySelector(selector);
const PRESETS = {
  ark: { name: "Ark Model", provider:"volcengine_ark", base_url: "https://ark.cn-beijing.volces.com/api/coding/v3", model: "model-name" },
  deepseek: { name: "DeepSeek", provider:"deepseek", base_url: "https://api.deepseek.com", model: "deepseek-chat" },
  qwen: { name: "Qwen", provider:"qwen", base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1", model: "qwen-plus" },
  custom: { name: "Custom API", provider:"openai_compatible", base_url: "https://example.com/v1", model: "model-id" },
};
const TEXT = {
  "zh-CN": {
    console:"模型控制台", online:"服务正常", back:"返回游戏", overview:"概览", usage:"用量分析",
    connections:"API 平台与模型", routing:"智能体路由", diagnostics:"调用明细",
    title:"模型与智能体", subtitle:"连接 · 路由 · 用量", mode:"运行模式",
    calls:"调用次数", tokens:"Token 总量", platformQuota:"平台额度", personalTokens:"个人 API Token",
    personalOnly:"不占用平台额度", estimatedCost:"估算成本", priceHint:"按连接单价估算", latency:"平均延迟",
    usageHelp:"当前玩家会话", last24h:"最近 24 小时", last7d:"最近 7 天",
    last30d:"最近 30 天", tokenMetric:"Token", requestMetric:"请求数", costMetric:"估算成本", latencyMetric:"延迟",
    bySource:"按 API 来源", byAgent:"按智能体", byModel:"按模型", byConnection:"按连接",
    platformApi:"平台默认 API", platformApiHelp:"受会话与账号每日预算限制", personalApi:"玩家个人 API",
    personalApiHelp:"独立计量，不使用平台密钥", periodUsage:"所选周期", remaining:"剩余", unlimited:"不限制",
    dailyBudget:"账号每日预算", circuitState:"平台熔断", circuitHealthy:"正常", circuitOpen:"个连接冷却中", accountRequired:"登录后可启用在线 API",
    addConnection:"新增 API",
    routingHelp:"选择每个智能体使用的模型", agent:"智能体", group:"分组", state:"状态",
    assigned:"分配连接", model:"模型", diagnosticsHelp:"最近 100 次调用",
    refresh:"刷新", time:"时间", apiSource:"API 来源", connection:"连接 / 模型", result:"结果",
    noCalls:"暂无调用记录。连接测试或开始游戏后会显示数据。", noUsage:"所选时间范围内暂无模型用量。",
    loaded:"配置已载入。", save:"保存并应用", name:"名称", baseUrl:"接口地址", apiKey:"API 密钥",
    inputPrice:"输入价 / 百万", outputPrice:"输出价 / 百万", enterKey:"输入玩家密钥", credentialConfigured:"凭据已配置",
    noCredential:"未配置凭据", platformManaged:"平台托管，不向浏览器暴露", test:"测试", remove:"移除", active:"运行中",
    planned:"待启用", successRate:"成功率", reviewFailures:"检查最近的失败记录", noFailures:"无失败",
    failed:"失败", testing:"检测中…", oneConnection:"至少需要保留一个连接。", loadFailed:"无法载入配置",
    saveFailed:"保存失败", testFailed:"检测失败", investigationTeam:"调查组", gameRuntime:"游戏运行时",
    liveApi:"在线 API", offlineStub:"离线模拟", platform:"平台", personal:"个人", unsaved:"存在未保存的更改。",
    saving:"正在保存…", saved:"配置已保存并应用。", requests:"次请求", sharedUrl:"请求地址",
    modelsConfigured:"个模型", modelApiName:"模型名称", independentCredential:"连接状态", addModel:"添加模型",
    addAvailableModel:"添加选中模型", removePlatform:"移除平台", noActiveModels:"当前未启用模型"
  },
  en: {
    console:"Model Console", online:"Service online", back:"Back to game", overview:"Overview", usage:"Usage",
    connections:"API providers & models", routing:"Agent routing", diagnostics:"Call logs",
    title:"Models and agents", subtitle:"Connections · Routing · Usage", mode:"Runtime mode",
    calls:"API calls", tokens:"Total tokens", platformQuota:"Platform quota", personalTokens:"Personal API tokens",
    personalOnly:"Does not consume platform quota", estimatedCost:"Estimated cost", priceHint:"Based on connection pricing", latency:"Average latency",
    usageHelp:"Current player session", last24h:"Last 24 hours", last7d:"Last 7 days",
    last30d:"Last 30 days", tokenMetric:"Tokens", requestMetric:"Requests", costMetric:"Estimated cost", latencyMetric:"Latency",
    bySource:"By API source", byAgent:"By agent", byModel:"By model", byConnection:"By connection",
    platformApi:"Platform default API", platformApiHelp:"Limited per session and account/day", personalApi:"Player personal API",
    personalApiHelp:"Metered separately; no platform key", periodUsage:"Selected period", remaining:"remaining", unlimited:"Unlimited",
    dailyBudget:"Daily account budget", circuitState:"Platform circuit", circuitHealthy:"Healthy", circuitOpen:"connections cooling down", accountRequired:"Sign in to enable live APIs",
    addConnection:"Add API",
    routingHelp:"Choose the model used by each agent", agent:"Agent", group:"Group", state:"Status",
    assigned:"Assigned connection", model:"Model", diagnosticsHelp:"Latest 100 calls",
    refresh:"Refresh", time:"Time", apiSource:"API source", connection:"Connection / model", result:"Result",
    noCalls:"No calls yet. Run a connection test or start the game.", noUsage:"No model usage in the selected time range.",
    loaded:"Configuration loaded.", save:"Save and apply", name:"Name", baseUrl:"Base URL", apiKey:"API key",
    inputPrice:"Input $ / 1M", outputPrice:"Output $ / 1M", enterKey:"Enter player key", credentialConfigured:"Credential configured",
    noCredential:"No credential", platformManaged:"Platform-managed; never exposed", test:"Test", remove:"Remove", active:"Active",
    planned:"Planned", successRate:"success", reviewFailures:"Review recent failures", noFailures:"No failures",
    failed:"Failed", testing:"Testing…", oneConnection:"At least one connection is required.", loadFailed:"Unable to load settings",
    saveFailed:"Save failed", testFailed:"Test failed", investigationTeam:"Investigation team", gameRuntime:"Game runtime",
    liveApi:"Live API", offlineStub:"Offline Stub", platform:"Platform", personal:"Personal", unsaved:"Unsaved changes.",
    saving:"Saving…", saved:"Configuration saved and applied.", requests:"requests", sharedUrl:"Request URL",
    modelsConfigured:"models", modelApiName:"Model name", independentCredential:"Connection status", addModel:"Add model",
    addAvailableModel:"Add selected model", removePlatform:"Remove provider", noActiveModels:"No active models"
  }
};
const AGENT_ZH = {
  case_director:"案件主管", field_investigator:"现场调查员", case_analyst:"案件分析师", skeptic:"质疑者",
  intent_parser:"意图解析器", consistency_judge:"一致性裁判", narrator:"世界叙事者", npc_dialogue:"角色对话"
};
const COLORS = ["#1769e0", "#13a4a7", "#7a5ce5", "#e18a2b", "#d94f70", "#51a467", "#65758b", "#bf6ab3"];
let settings = null;
let usage = null;
let dirty = false;

function t(key) { return (TEXT[$("#language").value] || TEXT["zh-CN"])[key] || key; }
function isZh() { return $("#language").value === "zh-CN"; }
function esc(value) { const el = document.createElement("div"); el.textContent = String(value ?? ""); return el.innerHTML; }
function message(text, state="") { const el = $("#save-message"); el.textContent = text; el.className = state; }
function markDirty() { dirty = true; message(t("unsaved")); }
function num(value) { return Number(value || 0).toLocaleString(isZh() ? "zh-CN" : "en-US"); }
function agentName(id) { return isZh() ? (AGENT_ZH[id] || id) : (settings?.agent_catalog?.find(a => a.id === id)?.name || id); }
function sourceName(source) { return t(source === "platform" ? "platform" : "personal"); }
function uniqueId(prefix="api") { let n=1, id; do { id=`${prefix}_${n++}`; } while (settings.connections[id]); return id; }
function providerName(provider, baseUrl) {
  if (provider === "volcengine_ark") return isZh() ? "火山方舟 Ark" : "Volcengine Ark";
  try {
    const host = new URL(baseUrl).hostname;
    if (host.includes("deepseek")) return "DeepSeek";
    if (host.includes("dashscope")) return "Qwen / DashScope";
    return host;
  } catch (_) { return provider || "OpenAI Compatible"; }
}

function applyLanguage() {
  const locale = $("#language").value;
  document.documentElement.lang = locale;
  localStorage.setItem("everstory_locale", locale);
  document.querySelectorAll("[data-i18n]").forEach(el => { el.textContent = t(el.dataset.i18n); });
  document.querySelectorAll("[data-i18n-placeholder]").forEach(el => { el.placeholder = t(el.dataset.i18nPlaceholder); });
  if (window.opener && !window.opener.closed) window.opener.EverStoryI18n?.setLocale(locale);
}

function connectionOptions(selected) {
  return Object.entries(settings.connections).map(([id, c]) =>
    `<option value="${esc(id)}" ${id === selected ? "selected" : ""}>${esc(c.provider === "volcengine_ark" ? `${providerName(c.provider, c.base_url)} / ${c.name}` : c.name)} · ${esc(c.model)} · ${sourceName(c.credential_source)}</option>`
  ).join("");
}

function renderConnections() {
  const host = $("#connection-list");
  host.innerHTML = "";
  const entries = Object.entries(settings.connections);
  const catalogEntries = Object.entries(settings.platform_catalog || {}).filter(([, c]) => c.credential_source === "platform");
  const platformGroups = new Map();
  const ensureGroup = c => {
    const key = `${c.provider || "openai_compatible"}::${c.base_url}`;
    if (!platformGroups.has(key)) platformGroups.set(key, {active:[], catalog:[]});
    return platformGroups.get(key);
  };
  catalogEntries.forEach(entry => ensureGroup(entry[1]).catalog.push(entry));
  entries.filter(([, c]) => c.credential_source === "platform").forEach(entry => ensureGroup(entry[1]).active.push(entry));
  platformGroups.forEach(group => {
    const [, first] = group.active[0] || group.catalog[0];
    const available = group.catalog.filter(([id]) => !settings.connections[id]);
    const card = document.createElement("article");
    card.className = "provider-card";
    card.innerHTML = `
      <header class="provider-card-head">
        <div><div class="provider-title"><strong>${esc(providerName(first.provider, first.base_url))}</strong><span class="source-badge">${sourceName("platform")}</span><span class="provider-count">${group.active.length} ${t("modelsConfigured")}</span></div><span class="provider-url-label">${t("sharedUrl")}</span><code class="provider-url">${esc(first.base_url)}</code></div>
        <div class="provider-head-actions"><button class="secondary" data-add-custom type="button">${t("addModel")}</button><button class="secondary danger" data-remove-provider type="button" ${group.active.length ? "" : "disabled"}>${t("removePlatform")}</button></div>
      </header>
      <div class="provider-model-head"><span>${t("modelApiName")}</span><span>${t("independentCredential")}</span><span></span></div>
      <div class="provider-models"></div>
      ${available.length ? `<div class="catalog-add"><select data-available-model>${available.map(([id, c]) => `<option value="${esc(id)}">${esc(c.name)} · ${esc(c.model)}</option>`).join("")}</select><button class="secondary" data-restore type="button">${t("addAvailableModel")}</button></div>` : ""}`;
    const models = card.querySelector(".provider-models");
    if (!group.active.length) models.innerHTML = `<div class="provider-empty">${t("noActiveModels")}</div>`;
    group.active.forEach(([id, c]) => {
      const modelRow = document.createElement("div");
      modelRow.className = "provider-model-row";
      modelRow.dataset.connection = id;
      modelRow.innerHTML = `
        <div class="model-identity"><strong>${esc(c.name)}</strong><code>${esc(c.model)}</code></div>
        <span class="test-result ${c.key_configured ? "ok" : "bad"}" data-key-status>${c.key_configured ? t("credentialConfigured") : t("noCredential")}</span>
        <div class="connection-actions"><button class="secondary" data-test type="button">${t("test")}</button><button class="secondary danger" data-remove type="button">${t("remove")}</button></div>`;
      modelRow.querySelector("[data-test]").addEventListener("click", () => testConnection(id, modelRow));
      modelRow.querySelector("[data-remove]").addEventListener("click", () => removeConnection(id));
      models.appendChild(modelRow);
    });
    card.querySelector("[data-add-custom]").addEventListener("click", () => addPersonalModel({
      name: `${providerName(first.provider, first.base_url)} Model`, provider:first.provider,
      base_url:first.base_url, model:"model-name"
    }, first.provider === "volcengine_ark" ? "ark_model" : "model"));
    card.querySelector("[data-remove-provider]").addEventListener("click", () => removeConnections(group.active.map(([id]) => id)));
    card.querySelector("[data-restore]")?.addEventListener("click", () => {
      const id = card.querySelector("[data-available-model]").value;
      settings.connections[id] = {...settings.platform_catalog[id]};
      renderConnections(); renderRoutes(); markDirty();
    });
    host.appendChild(card);
  });
  entries.filter(([, c]) => c.credential_source !== "platform").forEach(([id, c]) => {
    const platform = c.credential_source === "platform";
    const row = document.createElement("article");
    row.className = `connection-row ${platform ? "platform" : "personal"}`;
    row.dataset.connection = id;
    row.innerHTML = `
      <header class="connection-card-head">
        <div class="connection-identity"><strong>${esc(c.name)}</strong><span class="connection-id">${esc(id)}</span><span class="source-badge ${platform ? "" : "personal"}">${sourceName(c.credential_source)}</span></div>
        <div class="connection-actions"><button class="secondary" data-test type="button">${t("test")}</button><button class="secondary danger" data-remove type="button">${t("remove")}</button></div>
      </header>
      <div class="connection-form">
        <div class="field"><label>${t("name")}</label><input data-field="name" value="${esc(c.name)}"/></div>
        <div class="field"><label>${t("baseUrl")}</label><input data-field="base_url" value="${esc(c.base_url)}"/></div>
        <div class="field"><label>${t("model")}</label><input data-field="model" value="${esc(c.model)}"/></div>
        <div class="field"><label>${t("apiKey")}</label><input class="key-input" data-field="api_key" type="password" ${c.key_configured ? `placeholder="${esc(c.masked_key)}"` : `data-i18n-placeholder="enterKey" placeholder="${t("enterKey")}"`}/><div class="test-result ${c.key_configured ? "ok" : ""}" data-key-status>${c.key_configured ? t("credentialConfigured") : t("noCredential")}</div></div>
        <div class="field"><label>${t("inputPrice")}</label><input data-field="input_cost_per_million" type="number" min="0" step="0.01" value="${Number(c.input_cost_per_million || 0)}"/></div>
        <div class="field"><label>${t("outputPrice")}</label><input data-field="output_cost_per_million" type="number" min="0" step="0.01" value="${Number(c.output_cost_per_million || 0)}"/></div>
      </div>`;
    row.querySelectorAll("input:not(:disabled)").forEach(input => input.addEventListener("input", markDirty));
    row.querySelector("[data-test]").addEventListener("click", () => testConnection(id, row));
    row.querySelector("[data-remove]").addEventListener("click", () => removeConnection(id));
    host.appendChild(row);
  });
}

function renderRoutes() {
  const body = $("#agent-routes");
  body.innerHTML = "";
  settings.agent_catalog.forEach(agent => {
    const selected = settings.agent_routes[agent.id] || Object.keys(settings.connections)[0];
    const connection = settings.connections[selected];
    const group = agent.group === "Investigation team" ? t("investigationTeam") : agent.group === "Game runtime" ? t("gameRuntime") : agent.group;
    const row = document.createElement("tr");
    row.innerHTML = `<td><span class="agent-name">${esc(agentName(agent.id))}</span><span class="agent-id">${esc(agent.id)}</span></td><td>${esc(group)}</td><td><span class="badge ${agent.active ? "" : "pending"}">${agent.active ? t("active") : t("planned")}</span></td><td><select data-agent="${esc(agent.id)}">${connectionOptions(selected)}</select></td><td data-agent-model>${esc(connection?.model || "—")} <span class="badge ${connection?.credential_source || "personal"}">${sourceName(connection?.credential_source)}</span></td>`;
    row.querySelector("select").addEventListener("change", event => {
      settings.agent_routes[agent.id] = event.target.value;
      const next = settings.connections[event.target.value];
      row.querySelector("[data-agent-model]").innerHTML = `${esc(next?.model || "—")} <span class="badge ${next?.credential_source || "personal"}">${sourceName(next?.credential_source)}</span>`;
      markDirty();
    });
    body.appendChild(row);
  });
}

function groupLabel(id) {
  if (id === "platform" || id === "personal") return sourceName(id);
  if (AGENT_ZH[id]) return agentName(id);
  return id;
}
function colorFor(id, index) {
  if (id === "platform") return "#1769e0";
  if (id === "personal") return "#13a4a7";
  let hash = 0;
  for (const char of id) hash = (hash * 31 + char.charCodeAt(0)) >>> 0;
  return COLORS[(hash + index) % COLORS.length];
}
function metricValue(value) {
  const metric = usage?.metric;
  if (metric === "cost") return `$${Number(value).toFixed(value < .01 ? 4 : 2)}`;
  if (metric === "latency") return `${Math.round(value)} ms`;
  return num(Math.round(value));
}

function renderChart() {
  const host = $("#usage-chart");
  const legend = $("#usage-legend");
  const groups = (usage?.groups || []).slice(0, 8);
  const series = usage?.series || [];
  if (!groups.length || !series.some(row => Object.values(row.values || {}).some(value => Number(value) > 0))) {
    host.innerHTML = `<div class="chart-empty">${t("noUsage")}</div>`;
    legend.innerHTML = "";
    return;
  }
  const width = 960, height = 285, left = 50, right = 12, top = 12, bottom = 30;
  const plotWidth = width - left - right, plotHeight = height - top - bottom;
  const totals = series.map(row => groups.reduce((sum, group) => sum + Number(row.values?.[group.id] || 0), 0));
  const maximum = Math.max(...totals, 1);
  const gap = series.length > 24 ? 3 : 7;
  const band = plotWidth / series.length;
  const barWidth = Math.max(3, band - gap);
  let svg = `<svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" aria-hidden="true">`;
  for (let tick = 0; tick <= 4; tick++) {
    const y = top + plotHeight - (plotHeight * tick / 4);
    const value = maximum * tick / 4;
    svg += `<line class="chart-grid" x1="${left}" y1="${y}" x2="${width-right}" y2="${y}"/><text class="chart-axis-label" x="${left-7}" y="${y+3}" text-anchor="end">${esc(metricValue(value))}</text>`;
  }
  series.forEach((row, index) => {
    const x = left + index * band + (band - barWidth) / 2;
    let used = 0;
    groups.forEach((group, groupIndex) => {
      const value = Number(row.values?.[group.id] || 0);
      if (!value) return;
      const h = Math.max(1, value / maximum * plotHeight);
      const y = top + plotHeight - used - h;
      const color = colorFor(group.id, groupIndex);
      svg += `<rect x="${x.toFixed(2)}" y="${y.toFixed(2)}" width="${barWidth.toFixed(2)}" height="${h.toFixed(2)}" rx="2" fill="${color}"><title>${esc(row.label)} · ${esc(groupLabel(group.id))}: ${esc(metricValue(value))}</title></rect>`;
      used += h;
    });
    const labelEvery = Math.max(1, Math.ceil(series.length / 8));
    if (index % labelEvery === 0 || index === series.length - 1) {
      svg += `<text class="chart-axis-label" x="${(x + barWidth/2).toFixed(2)}" y="${height-8}" text-anchor="middle">${esc(row.label)}</text>`;
    }
  });
  svg += "</svg>";
  host.innerHTML = svg;
  legend.innerHTML = groups.map((group, index) => `<span><i style="background:${colorFor(group.id, index)}"></i>${esc(groupLabel(group.id))}</span>`).join("");
}

function renderUsage() {
  const summary = usage?.summary || {};
  const quota = summary.platform_quota || {};
  const guardrails = summary.platform_guardrails || {};
  $("#metric-calls").textContent = num(summary.calls);
  $("#metric-success").textContent = `${summary.success_rate ?? 100}% ${t("successRate")}`;
  $("#metric-tokens").textContent = num(summary.total_tokens);
  $("#metric-token-detail").textContent = isZh() ? `${num(summary.prompt_tokens)} 输入 / ${num(summary.completion_tokens)} 输出` : `${num(summary.prompt_tokens)} in / ${num(summary.completion_tokens)} out`;
  $("#metric-platform").textContent = num(quota.used);
  $("#metric-platform-detail").textContent = quota.limit ? `${t("remaining")} ${num(quota.remaining)}` : t("unlimited");
  $("#metric-personal").textContent = num(summary.personal_tokens);
  $("#metric-cost").textContent = `$${Number(summary.estimated_cost_usd || 0).toFixed(4)}`;
  $("#metric-latency").textContent = `${num(summary.average_latency_ms)} ms`;
  $("#metric-health").textContent = summary.failed_calls ? `${num(summary.failed_calls)} · ${t("reviewFailures")}` : t("noFailures");
  $("#quota-used").textContent = quota.limit ? `${num(quota.used)} / ${num(quota.limit)}` : t("unlimited");
  $("#quota-percent").textContent = quota.limit ? `${quota.percent || 0}%` : "—";
  $("#quota-fill").style.width = `${Math.min(100, quota.percent || 0)}%`;
  $("#daily-budget").textContent = guardrails.daily_token_limit
    ? `${num(guardrails.daily_tokens_used)} / ${num(guardrails.daily_token_limit)}`
    : t("unlimited");
  const openCircuits = Number(guardrails.open_circuits || 0);
  $("#circuit-state").textContent = openCircuits ? `${openCircuits} ${t("circuitOpen")}` : t("circuitHealthy");
  $("#circuit-state").className = openCircuits ? "bad" : "";
  $("#personal-period").textContent = `${num(summary.personal_tokens)} Tokens`;
  renderChart();
  renderLogs();
}

function renderLogs() {
  const body = $("#recent-calls");
  body.innerHTML = "";
  (usage?.logs || []).forEach(call => {
    const source = call.credential_source === "platform" ? "platform" : "personal";
    const time = call.created_at ? new Date(call.created_at).toLocaleString(isZh() ? "zh-CN" : "en-US", {month:"2-digit", day:"2-digit", hour:"2-digit", minute:"2-digit"}) : "—";
    const total = Number(call.total_tokens ?? (Number(call.prompt_tokens || 0) + Number(call.completion_tokens || 0)));
    const row = document.createElement("tr");
    row.innerHTML = `<td>${esc(time)}</td><td>${esc(agentName(call.agent))}</td><td><span class="badge ${source}">${sourceName(source)}</span></td><td>${esc(call.connection_id)}<span class="call-model">${esc(call.model)}</span></td><td>${num(total)}<span class="call-model">${num(call.prompt_tokens)} in · ${num(call.completion_tokens)} out</span></td><td>${num(call.latency_ms)} ms</td><td><span class="badge ${call.ok ? "" : "bad"}">${call.ok ? "OK" : t("failed")}</span>${call.error ? `<div class="call-error" title="${esc(call.error)}">${esc(call.error)}</div>` : ""}</td>`;
    body.appendChild(row);
  });
  $("#empty-calls").hidden = Boolean((usage?.logs || []).length);
}

function collectPayload() {
  const connections = {};
  Object.entries(settings.connections).forEach(([id, current]) => {
    if (current.credential_source === "platform") {
      connections[id] = {
        name: current.name, base_url: current.base_url, model: current.model,
        input_cost_per_million: Number(current.input_cost_per_million || 0),
        output_cost_per_million: Number(current.output_cost_per_million || 0),
      };
      return;
    }
    const row = document.querySelector(`.connection-row[data-connection="${CSS.escape(id)}"]`);
    connections[id] = {
      name: row.querySelector('[data-field="name"]').value.trim(),
      base_url: row.querySelector('[data-field="base_url"]').value.trim(),
      model: row.querySelector('[data-field="model"]').value.trim(),
      provider: current.provider || "openai_compatible",
      input_cost_per_million: Number(row.querySelector('[data-field="input_cost_per_million"]').value || 0),
      output_cost_per_million: Number(row.querySelector('[data-field="output_cost_per_million"]').value || 0),
    };
    const key = row.querySelector('[data-field="api_key"]').value.trim();
    if (key) connections[id].api_key = key;
  });
  return { mode: $("#mode").value, connections, agent_routes: {...settings.agent_routes} };
}

async function loadUsage() {
  const query = new URLSearchParams({range: $("#usage-range").value, metric: $("#usage-metric").value, group_by: $("#usage-group").value});
  const response = await fetch(`/api/llm/usage?${query}`);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || t("loadFailed"));
  usage = data;
  renderUsage();
}

async function loadSettings() {
  try {
    const response = await fetch("/api/llm/settings");
    if (!response.ok) throw new Error(t("loadFailed"));
    settings = await response.json();
    $("#mode").value = settings.mode;
    renderConnections();
    renderRoutes();
    await loadUsage();
    dirty = false;
    message(t("loaded"), "ok");
  } catch (error) {
    message(error.message, "bad");
    $("#service-status").classList.add("bad");
  }
}

async function saveSettings() {
  const button = $("#save-settings");
  button.disabled = true;
  message(t("saving"));
  try {
    const response = await fetch("/api/llm/settings", {method:"PUT", headers:{"Content-Type":"application/json"}, body:JSON.stringify(collectPayload())});
    const data = await response.json();
    if (!response.ok) {
      const error = new Error(data.code === "account_required" ? t("accountRequired") : (data.error || t("saveFailed")));
      error.code = data.code || "";
      throw error;
    }
    settings = data.settings;
    $("#mode").value = settings.mode;
    renderConnections();
    renderRoutes();
    await loadUsage();
    dirty = false;
    message(t("saved"), "ok");
    return true;
  } catch (error) {
    if (error.code === "account_required" && settings) {
      $("#mode").value = settings.mode;
      dirty = false;
    }
    message(error.message, "bad");
    return false;
  } finally {
    button.disabled = false;
  }
}

async function testConnection(id, row) {
  if (dirty && !(await saveSettings())) return;
  const button = row.querySelector("[data-test]");
  const result = row.querySelector("[data-key-status]");
  button.disabled = true;
  result.textContent = t("testing");
  result.className = "test-result";
  try {
    const response = await fetch("/api/llm/test", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({connection_id:id})});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || t("testFailed"));
    result.textContent = `OK · ${data.latency_ms} ms`;
    result.className = "test-result ok";
    await loadSettings();
  } catch (error) {
    result.textContent = error.message;
    result.className = "test-result bad";
  } finally {
    button.disabled = false;
  }
}

function removeConnections(ids) {
  const targets = new Set(ids);
  const remaining = Object.keys(settings.connections).filter(id => !targets.has(id));
  if (!remaining.length) { message(t("oneConnection"), "bad"); return; }
  targets.forEach(id => delete settings.connections[id]);
  const fallback = remaining[0];
  Object.keys(settings.agent_routes).forEach(agent => { if (targets.has(settings.agent_routes[agent])) settings.agent_routes[agent] = fallback; });
  renderConnections();
  renderRoutes();
  markDirty();
}
function removeConnection(id) { removeConnections([id]); }

function addPersonalModel(preset, prefix="api") {
  const id = uniqueId(prefix);
  settings.connections[id] = {...preset, credential_source:"personal", editable:true, key_configured:false, masked_key:"", input_cost_per_million:0, output_cost_per_million:0};
  renderConnections(); renderRoutes(); markDirty();
}

$("#back-to-game").addEventListener("click", event => {
  if (window.opener && !window.opener.closed) { event.preventDefault(); window.opener.focus(); window.close(); }
});
$("#add-connection").addEventListener("click", () => {
  const kind = $("#new-provider").value;
  const preset = PRESETS[kind];
  addPersonalModel(preset, kind === "custom" ? "custom" : kind);
});
$("#save-settings").addEventListener("click", saveSettings);
$("#refresh").addEventListener("click", loadSettings);
$("#mode").addEventListener("change", markDirty);
[$("#usage-range"), $("#usage-metric"), $("#usage-group")].forEach(control => control.addEventListener("change", () => loadUsage().catch(error => message(error.message, "bad"))));
const storedLocale=localStorage.getItem("everstory_locale");
$("#language").value=storedLocale==="en-US"?"en":(storedLocale||"zh-CN");
$("#language").addEventListener("change", () => { applyLanguage(); if (settings) { renderConnections(); renderRoutes(); renderUsage(); } });
window.addEventListener("storage", event => {
  if (event.key === "everstory_locale") {
    const locale = event.newValue === "en-US" ? "en" : event.newValue;
    $("#language").value = locale === "en" ? "en" : "zh-CN";
    applyLanguage();
    if (settings) { renderConnections(); renderRoutes(); renderUsage(); }
  }
});
document.querySelectorAll(".sidebar a").forEach(link => link.addEventListener("click", () => {
  document.querySelectorAll(".sidebar a").forEach(item => item.classList.remove("active"));
  link.classList.add("active");
}));
applyLanguage();
loadSettings();
