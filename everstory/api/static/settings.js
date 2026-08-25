const $ = (selector) => document.querySelector(selector);
const PRESETS = {
  deepseek: { name: "DeepSeek", base_url: "https://api.deepseek.com", model: "deepseek-v4-flash" },
  qwen: { name: "Qwen", base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1", model: "qwen-plus" },
  custom: { name: "Custom API", base_url: "https://example.com/v1", model: "model-id" },
};
const TEXT = {
  "zh-CN": {console:"模型控制台",online:"服务正常",back:"返回游戏",overview:"概览",connections:"API 连接",routing:"智能体路由",diagnostics:"调用检测",security:"凭据安全",securityNote:"密钥仅保存在当前服务进程中，接口不会返回完整密钥。",title:"模型与智能体",subtitle:"管理模型连接、角色分配和运行指标。",mode:"运行模式",calls:"调用次数",tokens:"Token 总量",latency:"平均延迟",last200:"最近 200 次调用",failures:"失败调用",connectionsHelp:"连接可被多个智能体复用，密钥不需要重复填写。",addConnection:"添加连接",routingHelp:"为每个运行角色选择独立或共享的模型连接。",agent:"智能体",group:"分组",state:"状态",assigned:"分配连接",model:"模型",diagnosticsHelp:"显示当前会话最近的模型调用、延迟和 Token 使用。",refresh:"刷新",connection:"连接",result:"结果",noCalls:"暂无调用记录。连接测试或开始游戏后会显示数据。",loaded:"配置已载入。",save:"保存并应用"},
  "en-US": {console:"Model Console",online:"Service online",back:"Back to game",overview:"Overview",connections:"API connections",routing:"Agent routing",diagnostics:"Diagnostics",security:"Credential security",securityNote:"Keys stay in the current server process and are never returned by the API.",title:"Models and agents",subtitle:"Manage model connections, role routing, and runtime metrics.",mode:"Runtime mode",calls:"API calls",tokens:"Total tokens",latency:"Average latency",last200:"Last 200 calls",failures:"Failed calls",connectionsHelp:"Connections can be shared by agents; credentials are entered once.",addConnection:"Add connection",routingHelp:"Assign an independent or shared model connection to every runtime role.",agent:"Agent",group:"Group",state:"Status",assigned:"Assigned connection",model:"Model",diagnosticsHelp:"Recent model calls, latency, and token usage for this session.",refresh:"Refresh",connection:"Connection",result:"Result",noCalls:"No calls yet. Run a connection test or start the game.",loaded:"Configuration loaded.",save:"Save and apply"}
};
let settings = null;
let dirty = false;
function t(key){return(TEXT[$("#language").value]||TEXT["zh-CN"])[key]||key;}
function applyLanguage(){const locale=$("#language").value;document.documentElement.lang=locale;localStorage.setItem("everstory_locale",locale);document.querySelectorAll("[data-i18n]").forEach(el=>{el.textContent=t(el.dataset.i18n);});}
function message(text,state=""){const el=$("#save-message");el.textContent=text;el.className=state;}
function markDirty(){dirty=true;message($("#language").value==="zh-CN"?"存在未保存的更改。":"Unsaved changes.");}
function esc(value){const el=document.createElement("div");el.textContent=String(value??"");return el.innerHTML;}
function uniqueId(prefix="api"){let n=1,id;do{id=`${prefix}_${n++}`;}while(settings.connections[id]);return id;}
function connectionOptions(selected){return Object.entries(settings.connections).map(([id,c])=>`<option value="${esc(id)}" ${id===selected?"selected":""}>${esc(c.name)} · ${esc(c.model)}</option>`).join("");}
function renderConnections(){
  const host=$("#connection-list");host.innerHTML="";
  Object.entries(settings.connections).forEach(([id,c])=>{
    const row=document.createElement("div");row.className="connection-row";row.dataset.connection=id;
    row.innerHTML=`<div class="field"><label>Name / ID</label><input data-field="name" value="${esc(c.name)}"/><div class="test-result">${esc(id)}</div></div><div class="field"><label>Base URL</label><input data-field="base_url" value="${esc(c.base_url)}"/></div><div class="field"><label>Model</label><input data-field="model" value="${esc(c.model)}"/></div><div class="field"><label>API key</label><input class="key-input" data-field="api_key" type="password" placeholder="${c.key_configured?esc(c.masked_key):"Enter key"}"/><div class="test-result ${c.key_configured?"ok":""}">${c.key_configured?"Credential configured":"No credential"}</div></div><div class="connection-actions"><button class="secondary" data-test type="button">Test</button><button class="secondary" data-remove type="button">Remove</button></div>`;
    row.querySelectorAll("input").forEach(input=>input.addEventListener("input",markDirty));
    row.querySelector("[data-test]").addEventListener("click",()=>testConnection(id,row));
    row.querySelector("[data-remove]").addEventListener("click",()=>removeConnection(id));
    host.appendChild(row);
  });
}
function renderRoutes(){
  const body=$("#agent-routes");body.innerHTML="";
  settings.agent_catalog.forEach(agent=>{
    const selected=settings.agent_routes[agent.id]||Object.keys(settings.connections)[0];const connection=settings.connections[selected];const row=document.createElement("tr");
    row.innerHTML=`<td><span class="agent-name">${esc(agent.name)}</span><span class="agent-id">${esc(agent.id)}</span></td><td>${esc(agent.group)}</td><td><span class="badge ${agent.active?"":"pending"}">${agent.active?"Active":"Planned"}</span></td><td><select data-agent="${esc(agent.id)}">${connectionOptions(selected)}</select></td><td data-agent-model>${esc(connection?.model||"—")}</td>`;
    row.querySelector("select").addEventListener("change",event=>{settings.agent_routes[agent.id]=event.target.value;row.querySelector("[data-agent-model]").textContent=settings.connections[event.target.value]?.model||"—";markDirty();});body.appendChild(row);
  });
}
function renderDiagnostics(){
  const d=settings.diagnostics||{};$("#metric-calls").textContent=(d.calls||0).toLocaleString();$("#metric-success").textContent=`${d.successful_calls||0} successful`;$("#metric-tokens").textContent=(d.total_tokens||0).toLocaleString();$("#metric-token-detail").textContent=`${d.prompt_tokens||0} in / ${d.completion_tokens||0} out`;$("#metric-latency").textContent=`${d.average_latency_ms||0} ms`;$("#metric-failures").textContent=d.failed_calls||0;$("#metric-health").textContent=d.failed_calls?"Review recent failures":"No failures";
  const body=$("#recent-calls");body.innerHTML="";(d.recent_calls||[]).forEach(call=>{const row=document.createElement("tr");row.innerHTML=`<td>${esc(call.agent)}</td><td>${esc(call.connection_id)}</td><td>${esc(call.model)}</td><td>${call.latency_ms} ms</td><td>${call.prompt_tokens+call.completion_tokens}</td><td><span class="badge ${call.ok?"":"bad"}">${call.ok?"OK":"Failed"}</span></td>`;body.appendChild(row);});$("#empty-calls").hidden=Boolean((d.recent_calls||[]).length);
}
function collectPayload(){
  const connections={};document.querySelectorAll(".connection-row").forEach(row=>{const id=row.dataset.connection;connections[id]={name:row.querySelector('[data-field="name"]').value.trim(),base_url:row.querySelector('[data-field="base_url"]').value.trim(),model:row.querySelector('[data-field="model"]').value.trim()};const key=row.querySelector('[data-field="api_key"]').value.trim();if(key)connections[id].api_key=key;});return{mode:$("#mode").value,connections,agent_routes:{...settings.agent_routes}};
}
async function loadSettings(){try{const response=await fetch("/api/llm/settings");if(!response.ok)throw new Error("Unable to load settings");settings=await response.json();$("#mode").value=settings.mode;renderConnections();renderRoutes();renderDiagnostics();dirty=false;message(t("loaded"),"ok");}catch(error){message(error.message,"bad");$("#service-status").classList.add("bad");}}
async function saveSettings(){const button=$("#save-settings");button.disabled=true;message($("#language").value==="zh-CN"?"正在保存…":"Saving…");try{const response=await fetch("/api/llm/settings",{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify(collectPayload())});const data=await response.json();if(!response.ok)throw new Error(data.error||"Save failed");settings=data.settings;$("#mode").value=settings.mode;renderConnections();renderRoutes();renderDiagnostics();dirty=false;message($("#language").value==="zh-CN"?"配置已保存并应用。":"Configuration saved and applied.","ok");return true;}catch(error){message(error.message,"bad");return false;}finally{button.disabled=false;}}
async function testConnection(id,row){if(dirty&&!(await saveSettings()))return;const button=row.querySelector("[data-test]"),result=row.querySelector('.field [data-field="api_key"] + .test-result');button.disabled=true;result.textContent="Testing…";result.className="test-result";try{const response=await fetch("/api/llm/test",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({connection_id:id})});const data=await response.json();if(!response.ok)throw new Error(data.error||"Test failed");result.textContent=`OK · ${data.latency_ms} ms`;result.className="test-result ok";await loadSettings();}catch(error){result.textContent=error.message;result.className="test-result bad";}finally{button.disabled=false;}}
function removeConnection(id){if(Object.keys(settings.connections).length===1){message("At least one connection is required.","bad");return;}delete settings.connections[id];const fallback=Object.keys(settings.connections)[0];Object.keys(settings.agent_routes).forEach(agent=>{if(settings.agent_routes[agent]===id)settings.agent_routes[agent]=fallback;});renderConnections();renderRoutes();markDirty();}
$("#add-connection").addEventListener("click",()=>{const kind=$("#new-provider").value,preset=PRESETS[kind],id=uniqueId(kind==="custom"?"custom":kind);settings.connections[id]={...preset,key_configured:false,masked_key:""};renderConnections();renderRoutes();markDirty();});
$("#save-settings").addEventListener("click",saveSettings);$("#refresh").addEventListener("click",loadSettings);$("#mode").addEventListener("change",markDirty);$("#language").value=localStorage.getItem("everstory_locale")||"zh-CN";$("#language").addEventListener("change",()=>{applyLanguage();renderRoutes();renderDiagnostics();});document.querySelectorAll(".sidebar a").forEach(link=>link.addEventListener("click",()=>{document.querySelectorAll(".sidebar a").forEach(item=>item.classList.remove("active"));link.classList.add("active");}));applyLanguage();loadSettings();
