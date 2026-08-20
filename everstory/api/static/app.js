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

function addMessage(role, text) {
  const el = document.createElement("div");
  el.className = `msg ${role}`;
  el.innerHTML = `<span class="bubble">${esc(text)}</span>`;
  $("#messages").appendChild(el);
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
  try {
    const data = await api("/api/turn", {
      method: "POST",
      body: JSON.stringify({ text }),
    });
    world = data.world;
    addMessage("assistant", data.reply);
    render();
  } finally {
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
}

function renderPlayer(player) {
  const chips = (player.inventory || [])
    .map((i) => `<span class="chip inv">${esc(i)}</span>`)
    .join("");
  $("#player-card").innerHTML = `
    <h3>${esc(player.name)}</h3>
    <p class="muted">At: ${esc(player.location_name)}</p>
    <p class="muted">Inventory:</p>
    <div class="chips">${chips || '<span class="muted">empty</span>'}</div>
  `;
}

function renderFacts(world) {
  const flags = Object.entries(world.flags || {})
    .map(([k, v]) => `<li><b>${esc(k)}</b>: ${esc(String(v))}</li>`)
    .join("");
  const rels = (world.relationships || [])
    .map((r) => `<li>${esc(r.type)}: ${esc(r.from)} → ${esc(r.to)}</li>`)
    .join("");
  $("#facts-card").innerHTML = `
    <h3>World state</h3>
    <ul>
      <li>turn <b>${world.turn}</b> · time <b>${world.time}</b></li>
      <li>hash <code>${esc(world.state_hash)}</code></li>
    </ul>
    ${flags ? `<h3>Flags</h3><ul>${flags}</ul>` : ""}
    ${rels ? `<h3>Relationships</h3><ul>${rels}</ul>` : ""}
  `;
}

function renderMap(locations) {
  const svgNS = "http://www.w3.org/2000/svg";
  const W = 320, H = 230, cx = 160, cy = 115, R = 88;
  const svg = document.createElementNS(svgNS, "svg");
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
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
    circle.setAttribute("r", loc.current ? 15 : 11);
    circle.setAttribute("class", loc.current ? "node current" : "node");
    const label = document.createElementNS(svgNS, "text");
    label.setAttribute("x", p.x);
    label.setAttribute("y", p.y + 4);
    label.setAttribute("text-anchor", "middle");
    label.setAttribute("class", "nodelabel");
    label.textContent = loc.name.length > 18 ? loc.name.slice(0, 17) + "…" : loc.name;
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
    .map((c) => `<li><b>${esc(c.name)}</b> <span class="muted">@ ${esc(byId[c.location_id] || "?")}</span></li>`)
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
      return `<li><b>${esc(it.name)}</b> <span class="muted">(${esc(where)}${tags.length ? ", " + tags.join(", ") : ""})</span></li>`;
    })
    .join("");
  $("#entities-card").innerHTML = `
    <h3>Characters</h3>
    <ul>${chars || '<li class="muted">none here</li>'}</ul>
    <h3>Items</h3>
    <ul>${items || '<li class="muted">none</li>'}</ul>
  `;
}

function renderQuests(quests) {
  $("#quests-card").innerHTML =
    "<h3>Quests</h3><ul>" +
    quests
      .map(
        (q) =>
          `<li class="${q.done ? "done" : ""}">${q.done ? "[x]" : "[ ]"} ${esc(q.name)}</li>`
      )
      .join("") +
    "</ul>";
}

function renderLog(history) {
  const rows = [...history]
    .reverse()
    .map(
      (h) =>
        `<li class="${h.ok ? "ok" : "rej"}"><span class="muted">#${h.turn}</span> ${esc(h.message)}</li>`
    )
    .join("");
  $("#log").innerHTML = `<ul>${rows || '<li class="muted">no events yet</li>'}</ul>`;
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
  addMessage("system", "Welcome to The Lost Lighthouse. Type anything — e.g. \"move to the cave\".");
  loadWorld();
});
