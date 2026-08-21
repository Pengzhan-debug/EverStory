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
  const banner = $("#ending-banner");
  if (banner) {
    if (world.flags && world.flags.ending) {
      banner.hidden = false;
      banner.innerHTML =
        `★ Ending unlocked — the lighthouse burns again and the keeper's secret is told. ` +
        `Completed in <b>${world.turn}</b> turns.`;
    } else {
      banner.hidden = true;
    }
  }
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

const map3d = {
  canvas: null,
  ctx: null,
  nodes: [],
  edges: [],
  currentId: null,
  yaw: -0.6,
  pitch: 0.35,
  dist: 3.2,
  dragging: false,
  lastX: 0,
  lastY: 0,
  initialized: false,
};

function initMap3D() {
  const host = $("#map");
  host.innerHTML = "";
  const canvas = document.createElement("canvas");
  canvas.className = "map3d";
  host.appendChild(canvas);
  map3d.canvas = canvas;
  map3d.ctx = canvas.getContext("2d");

  const resize = () => {
    const rect = host.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.max(220, Math.round(rect.width * dpr));
    canvas.height = 220 * dpr;
  };
  resize();
  window.addEventListener("resize", resize);

  canvas.addEventListener("pointerdown", (e) => {
    map3d.dragging = true;
    map3d.lastX = e.clientX;
    map3d.lastY = e.clientY;
    canvas.setPointerCapture(e.pointerId);
  });
  canvas.addEventListener("pointermove", (e) => {
    if (!map3d.dragging) return;
    const dx = e.clientX - map3d.lastX;
    const dy = e.clientY - map3d.lastY;
    map3d.lastX = e.clientX;
    map3d.lastY = e.clientY;
    map3d.yaw += dx * 0.008;
    map3d.pitch = Math.max(-1.2, Math.min(1.2, map3d.pitch + dy * 0.008));
  });
  canvas.addEventListener("pointerup", () => {
    map3d.dragging = false;
  });
  canvas.addEventListener("pointerleave", () => {
    map3d.dragging = false;
  });
  canvas.addEventListener(
    "wheel",
    (e) => {
      e.preventDefault();
      map3d.dist = Math.max(2.1, Math.min(5.0, map3d.dist + e.deltaY * 0.002));
    },
    { passive: false }
  );

  map3d.initialized = true;
  requestAnimationFrame(mapLoop);
}

function mapLoop() {
  if (!map3d.dragging) map3d.yaw += 0.003;
  drawMap3D();
  requestAnimationFrame(mapLoop);
}

function renderMap(locations) {
  if (!map3d.initialized) initMap3D();
  const n = locations.length || 1;
  map3d.nodes = locations.map((loc, i) => {
    // Fibonacci sphere: spread locations evenly in 3D space.
    const y = 1 - (2 * (i + 0.5)) / n;
    const r = Math.sqrt(Math.max(0, 1 - y * y));
    const theta = i * 2.399963;
    return {
      id: loc.id,
      name: loc.name,
      current: loc.current,
      x: r * Math.cos(theta),
      y,
      z: r * Math.sin(theta),
    };
  });
  const byId = {};
  locations.forEach((l) => (byId[l.id] = l));
  map3d.edges = [];
  const seen = new Set();
  locations.forEach((loc) => {
    (loc.connections || []).forEach((c) => {
      const key = [loc.id, c].sort().join("|");
      if (seen.has(key) || !byId[c]) return;
      seen.add(key);
      map3d.edges.push([loc.id, c]);
    });
  });
  const current = locations.find((l) => l.current);
  map3d.currentId = current ? current.id : null;
}

function drawMap3D() {
  const canvas = map3d.canvas;
  const ctx = map3d.ctx;
  if (!canvas) return;
  const W = canvas.width;
  const H = canvas.height;
  ctx.clearRect(0, 0, W, H);
  const cx = W / 2;
  const cy = H / 2;
  const R = Math.min(W, H) * 0.36;
  const { yaw, pitch, dist } = map3d;
  const cyaw = Math.cos(yaw);
  const syaw = Math.sin(yaw);
  const cp = Math.cos(pitch);
  const sp = Math.sin(pitch);

  const project = (node) => {
    const x1 = node.x * cyaw + node.z * syaw;
    const z1 = -node.x * syaw + node.z * cyaw;
    const y2 = node.y * cp - z1 * sp;
    const z2 = node.y * sp + z1 * cp;
    const persp = dist / (dist - z2);
    if (persp <= 0) return null;
    return { x: cx + x1 * R * persp, y: cy - y2 * R * persp, z: z2, p: persp };
  };

  const proj = {};
  map3d.nodes.forEach((node) => {
    proj[node.id] = { node, p: project(node) };
  });

  // Edges (connections), drawn as projected lines.
  ctx.lineWidth = 1.3;
  ctx.strokeStyle = "rgba(76,201,240,0.45)";
  map3d.edges.forEach(([a, b]) => {
    const pa = proj[a] && proj[a].p;
    const pb = proj[b] && proj[b].p;
    if (!pa || !pb) return;
    ctx.beginPath();
    ctx.moveTo(pa.x, pa.y);
    ctx.lineTo(pb.x, pb.y);
    ctx.stroke();
  });

  // Nodes far -> near.
  const visible = Object.values(proj)
    .filter((p) => p.p)
    .sort((a, b) => b.p.p - a.p.p);
  visible.forEach(({ node, p }) => {
    const isCurrent = node.id === map3d.currentId;
    const rad = (isCurrent ? 9 : 6) * (0.7 + p.p * 0.35);
    ctx.beginPath();
    ctx.arc(p.x, p.y, rad, 0, Math.PI * 2);
    if (isCurrent) {
      ctx.shadowColor = "rgba(246,195,107,0.9)";
      ctx.shadowBlur = 16;
      ctx.fillStyle = "rgba(246,195,107,0.25)";
      ctx.fill();
      ctx.shadowBlur = 0;
      ctx.strokeStyle = "#f6c36b";
      ctx.lineWidth = 2.2;
    } else {
      ctx.fillStyle = "#0e2b47";
      ctx.strokeStyle = "rgba(76,201,240,0.7)";
      ctx.lineWidth = 1.5;
    }
    ctx.fill();
    ctx.stroke();

    const alpha = Math.max(0.25, Math.min(1, (p.p - 0.7) / 0.6));
    ctx.fillStyle = isCurrent
      ? "#f6c36b"
      : `rgba(243,240,232,${alpha.toFixed(2)})`;
    ctx.font = `600 ${Math.round(10 * p.p)}px "Segoe UI", sans-serif`;
    ctx.textAlign = "center";
    ctx.fillText(
      node.name.length > 18 ? node.name.slice(0, 17) + "…" : node.name,
      p.x,
      p.y - rad - 5
    );
  });
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
  $("#save-btn").addEventListener("click", async () => {
    const res = await api("/api/save", {
      method: "POST",
      body: JSON.stringify({ name: "autosave" }),
    });
    addMessage("system", `Saved — turn ${res.turn}.`);
  });
  $("#load-btn").addEventListener("click", async () => {
    const { saves } = await api("/api/saves");
    if (!saves.length) {
      addMessage("system", "No saves yet — play a little, then Save.");
      return;
    }
    await api("/api/load", {
      method: "POST",
      body: JSON.stringify({ path: saves[0].path }),
    });
    $("#messages").innerHTML = "";
    addMessage("system", "Loaded the latest save.");
    await loadWorld();
  });
  addMessage(
    "system",
    "Welcome to The Lost Lighthouse. Type anything — e.g. “move to the cave”."
  );
  loadWorld();
});
