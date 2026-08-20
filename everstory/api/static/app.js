const $ = (sel) => document.querySelector(sel);

let world = null;
let busy = false;

async function api(path, options = {}) {
  const resp = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!resp.ok) throw new Error(`${path}: ${resp.status}`);
  return resp.json();
}

function esc(s) {
  const div = document.createElement("div");
  div.textContent = s == null ? "" : String(s);
  return div.innerHTML;
}

const BOT_AVATAR =
  '<span class="avatar bot-avatar">' +
  '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
  '<rect x="4" y="8" width="16" height="12" rx="2"/><path d="M12 8V4M8 4h8"/><circle cx="9" cy="13" r="1" fill="currentColor"/><circle cx="15" cy="13" r="1" fill="currentColor"/></svg>' +
  "</span>";

function addMessage(role, text) {
  const el = document.createElement("div");
  if (role === "system") {
    el.className = "msg system";
    el.innerHTML = `<div class="sys-pill">${esc(text)}</div>`;
  } else {
    el.className = `msg ${role}`;
    const avatar =
      role === "assistant"
        ? BOT_AVATAR
        : '<span class="avatar user-avatar">YOU</span>';
    el.innerHTML = `${avatar}<div class="bubble">${esc(text)}</div>`;
  }
  $("#messages").appendChild(el);
  $("#messages").scrollTop = $("#messages").scrollHeight;
}

function setTyping(on) {
  let t = $("#typing");
  if (on && !t) {
    t = document.createElement("div");
    t.id = "typing";
    t.className = "msg assistant";
    t.innerHTML =
      BOT_AVATAR +
      '<div class="bubble typing-bubble"><span class="dot"></span><span class="dot"></span><span class="dot"></span></div>';
    $("#messages").appendChild(t);
  }
  if (t) t.style.display = on ? "" : "none";
  $("#messages").scrollTop = $("#messages").scrollHeight;
}

async function loadWorld() {
  world = await api("/api/world");
  render();
}

async function sendTurn(text) {
  if (busy) return;
  busy = true;
  addMessage("user", text);
  $("#input").value = "";
  setTyping(true);
  try {
    const data = await api("/api/turn", {
      method: "POST",
      body: JSON.stringify({ text }),
    });
    world = data.world;
    setTyping(false);
    addMessage("assistant", data.reply);
    render();
  } finally {
    setTyping(false);
    busy = false;
  }
}

function render() {
  renderPlayer(world.player);
  renderFacts(world);
  renderMap(world.locations);
  renderEntities(world);
  renderQuests(world.quests);
  renderLog(world.history);
  $("#mode-chip").textContent = `turn ${world.turn} · time ${world.time}`;
  const locChip = $("#loc-chip");
  if (locChip) locChip.textContent = world.player.location_name;
}

function renderPlayer(player) {
  const chips = (player.inventory || [])
    .map((i) => `<span class="chip inv">${esc(i)}</span>`)
    .join("");
  $("#player-card").innerHTML = `
    <div class="player-row">
      <span class="avatar user-avatar big">YOU</span>
      <div class="player-info">
        <div class="player-name">${esc(player.name)}</div>
        <div class="player-loc">📍 ${esc(player.location_name)}</div>
      </div>
    </div>
    <div class="divider"></div>
    <div class="label">Inventory</div>
    <div class="chips">${chips || '<span class="muted">empty</span>'}</div>
  `;
}

function renderFacts(world) {
  const flags = Object.entries(world.flags || {})
    .map(([k, v]) => `<li><b>${esc(k)}</b>: ${esc(String(v))}</li>`)
    .join("");
  const rels = (world.relationships || [])
    .map((r) => `<li><span class="rel-type">${esc(r.type)}</span> ${esc(r.from)} → ${esc(r.to)}</li>`)
    .join("");
  $("#facts-card").innerHTML = `
    <div class="card-head"><h3>World state</h3><span class="chip mono">${esc(world.state_hash)}</span></div>
    <div class="stat-row">
      <div class="stat"><div class="stat-num">${world.turn}</div><div class="stat-label">turns</div></div>
      <div class="stat"><div class="stat-num">${world.time}</div><div class="stat-label">time</div></div>
      <div class="stat"><div class="stat-num">${(world.history || []).length}</div><div class="stat-label">events</div></div>
    </div>
    ${flags ? `<div class="label">Flags</div><ul class="facts">${flags}</ul>` : ""}
    ${rels ? `<div class="label">Relationships</div><ul class="facts">${rels}</ul>` : ""}
  `;
}

function renderMap(locations) {
  const svgNS = "http://www.w3.org/2000/svg";
  const W = 340, H = 250, cx = 170, cy = 125, R = 95;
  const svg = document.createElementNS(svgNS, "svg");
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.setAttribute("class", "map");
  const pos = {};
  locations.forEach((loc, i) => {
    const a = (i / locations.length) * 2 * Math.PI - Math.PI / 2;
    pos[loc.id] = { x: cx + R * Math.cos(a), y: cy + R * Math.sin(a) };
  });
  const seen = new Set();
  locations.forEach((loc) => {
    (loc.connections || []).forEach((c) => {
      const key = [loc.id, c].sort().join("|");
      if (seen.has(key) || !pos[c]) return;
      seen.add(key);
      const line = document.createElementNS(svgNS, "line");
      line.setAttribute("x1", pos[loc.id].x);
      line.setAttribute("y1", pos[loc.id].y);
      line.setAttribute("x2", pos[c].x);
      line.setAttribute("y2", pos[c].y);
      line.setAttribute("class", "edge");
      svg.appendChild(line);
    });
  });
  locations.forEach((loc) => {
    const p = pos[loc.id];
    const g = document.createElementNS(svgNS, "g");
    const circle = document.createElementNS(svgNS, "circle");
    circle.setAttribute("cx", p.x);
    circle.setAttribute("cy", p.y);
    circle.setAttribute("r", loc.current ? 16 : 12);
    circle.setAttribute("class", loc.current ? "node current" : "node");
    const label = document.createElementNS(svgNS, "text");
    label.setAttribute("x", p.x);
    label.setAttribute("y", p.y + 4);
    label.setAttribute("text-anchor", "middle");
    label.setAttribute("class", "nodelabel");
    label.textContent = loc.name.length > 20 ? loc.name.slice(0, 19) + "…" : loc.name;
    g.appendChild(circle);
    g.appendChild(label);
    svg.appendChild(g);
  });
  $("#map").innerHTML = "";
  $("#map").appendChild(svg);
}

function renderEntities(world) {
  const byId = {};
  world.locations.forEach((l) => (byId[l.id] = l.name));
  const chars = world.characters
    .map(
      (c) =>
        `<li><span class="dot char"></span><b>${esc(c.name)}</b> <span class="muted">@ ${esc(byId[c.location_id] || "?")}</span></li>`
    )
    .join("");
  const items = world.items
    .map((it) => {
      let where = "inventory";
      if (it.owner_id) {
        const owner = world.characters.find((c) => c.id === it.owner_id);
        where = `owned by ${owner ? owner.name : it.owner_id}`;
      } else if (it.location_id) {
        where = byId[it.location_id] || it.location_id;
      }
      const tags = [];
      if (it.locked) tags.push("locked");
      if (it.lit) tags.push("lit");
      return `<li><span class="dot item"></span><b>${esc(it.name)}</b> <span class="muted">(${esc(where)}${tags.length ? ", " + tags.join(", ") : ""})</span></li>`;
    })
    .join("");
  $("#entities-card").innerHTML = `
    <div class="card-head"><h3>Characters & items</h3></div>
    <div class="label">Characters</div>
    <ul class="facts">${chars || '<li class="muted">none</li>'}</ul>
    <div class="label">Items</div>
    <ul class="facts">${items || '<li class="muted">none</li>'}</ul>
  `;
}

function renderQuests(quests) {
  const done = (quests || []).filter((q) => q.done).length;
  const total = (quests || []).length || 1;
  const pct = Math.round((done / total) * 100);
  $("#quests-card").innerHTML = `
    <div class="card-head"><h3>Quests</h3><span class="chip">${done}/${total}</span></div>
    <div class="progress"><div class="progress-fill" style="width:${pct}%"></div></div>
    <ul class="facts">${(quests || [])
      .map(
        (q) =>
          `<li class="${q.done ? "done" : ""}">${q.done ? "✔" : "◌"} ${esc(q.name)}</li>`
      )
      .join("")}</ul>
  `;
}

function renderLog(history) {
  const rows = [...history]
    .reverse()
    .map(
      (h) =>
        `<li class="log-row ${h.ok ? "ok" : "rej"}"><span class="log-turn">#${h.turn}</span><span class="log-dot ${h.ok ? "ok" : "rej"}"></span>${esc(h.message)}</li>`
    )
    .join("");
  $("#log").innerHTML =
    `<ul class="log-list">${rows || '<li class="muted">no events yet</li>'}</ul>`;
}

document.addEventListener("DOMContentLoaded", () => {
  $("#input-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const t = $("#input").value.trim();
    if (t) sendTurn(t);
  });
  $("#reset-btn").addEventListener("click", async () => {
    await api("/api/reset", { method: "POST" });
    $("#messages").innerHTML = "";
    addMessage("system", "A new world begins…");
    await loadWorld();
  });
  addMessage(
    "system",
    "Welcome to The Lost Lighthouse. Type anything — e.g. “move to the cave”."
  );
  loadWorld();
});
