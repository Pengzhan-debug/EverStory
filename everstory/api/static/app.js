const $ = (sel) => document.querySelector(sel);

let world = null;

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

function render() {
  if (!world) return;
  renderPlayer(world.player);
  renderFacts(world);
  renderMap(world.locations);
  renderEntities(world);
  renderQuests(world.quests);
  renderLog(world.history);
  renderScene(world.scene);
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

function renderScene(scene) {
  if (!scene) return;
  const objective = $("#objective-text");
  if (objective) objective.textContent = scene.objective || "Follow the evidence";

  const presence = $("#scene-presence");
  if (presence) {
    const characters = (scene.characters || []).map(
      (character) => `
        <button class="presence-card character" type="button" data-command="talk to ${esc(character.id)}">
          <span class="presence-glyph">${esc(character.name.slice(0, 1))}</span>
          <span><strong>${esc(character.name)}</strong><small>${esc(character.description || "Someone waits here.")}</small></span>
        </button>`
    );
    const items = (scene.items || []).map(
      (item) => `
        <button class="presence-card item" type="button" data-command="${item.locked ? `open ${esc(item.id)}` : `take ${esc(item.id)}`}">
          <span class="presence-glyph">◇</span>
          <span><strong>${esc(item.name)}</strong><small>${esc(item.description || (item.locked ? "It is locked." : "Available to inspect."))}</small></span>
        </button>`
    );
    presence.innerHTML = [...characters, ...items].join("");
  }

  const actions = $("#action-suggestions");
  if (actions) {
    actions.innerHTML = (scene.suggestions || [])
      .map(
        (action, index) => `
          <button class="action-choice" type="button" data-command="${esc(action.command)}">
            <span>${index + 1}</span>${esc(action.label)}
          </button>`
      )
      .join("");
  }
}

function toggleJournal() {
  let modal = $("#journal-modal");
  if (!modal) {
    modal = document.createElement("div");
    modal.id = "journal-modal";
    modal.innerHTML = `
      <div class="modal-backdrop"></div>
      <section class="journal-sheet" role="dialog" aria-modal="true" aria-labelledby="journal-title">
        <button class="modal-close" type="button" aria-label="Close journal">×</button>
        <div class="eyebrow">INVESTIGATION RECORD</div>
        <h2 id="journal-title">The Keeper's Journal</h2>
        <div id="journal-content"></div>
      </section>`;
    document.body.appendChild(modal);
    modal.querySelector(".modal-backdrop").addEventListener("click", toggleJournal);
    modal.querySelector(".modal-close").addEventListener("click", toggleJournal);
  }
  const opening = !modal.classList.contains("open");
  if (opening && world) {
    const quests = (world.quests || [])
      .map((quest) => `<li class="${quest.done ? "done" : ""}"><span>${quest.done ? "✓" : "○"}</span>${esc(quest.name)}</li>`)
      .join("");
    const history = [...(world.history || [])]
      .reverse()
      .slice(0, 12)
      .map((entry) => `<li><span>#${entry.turn}</span>${esc(entry.message)}</li>`)
      .join("");
    modal.querySelector("#journal-content").innerHTML = `
      <h3>Current lead</h3><p>${esc(world.scene?.objective || "Follow the evidence")}</p>
      <h3>Case objectives</h3><ul class="journal-quests">${quests || "<li>No objectives recorded.</li>"}</ul>
      <h3>Recent findings</h3><ul class="journal-history">${history || "<li>The investigation has just begun.</li>"}</ul>`;
  }
  modal.classList.toggle("open", opening);
}

function renderMap(locations) {
  const host = $("#map");
  const current = locations.find((location) => location.current);
  if (!host || !current) return;
  const byId = Object.fromEntries(locations.map((location) => [location.id, location]));
  const routes = (current.connections || [])
    .map((id) => byId[id])
    .filter(Boolean)
    .map(
      (location) => `
        <button class="route-card" type="button" data-command="move to ${esc(location.id)}">
          <span class="route-direction">ROUTE</span>
          <strong>${esc(location.name)}</strong>
          <span class="route-arrow">→</span>
        </button>`
    )
    .join("");
  const known = locations
    .filter((location) => !location.current && !(current.connections || []).includes(location.id))
    .map((location) => `<li>${esc(location.name)}</li>`)
    .join("");
  host.innerHTML = `
    <div class="case-map">
      <div class="map-current">
        <span class="map-pin">⌖</span>
        <span><small>CURRENT POSITION</small><strong>${esc(current.name)}</strong></span>
      </div>
      <div class="map-route-line"></div>
      <div class="map-routes">${routes || '<span class="muted">No route from here.</span>'}</div>
      <details class="known-locations">
        <summary>Other charted locations</summary>
        <ul>${known || '<li>None</li>'}</ul>
      </details>
    </div>`;
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
  window.addEventListener("everstory:world", (event) => {
    world = event.detail;
    render();
  });
  document.addEventListener("click", (event) => {
    const action = event.target.closest("[data-command]");
    if (!action) return;
    const command = action.dataset.command;
    if (command && window.EverStory) window.EverStory.send(command).catch(() => {});
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && $("#journal-modal")?.classList.contains("open")) {
      toggleJournal();
      return;
    }
    if (/input|textarea/i.test(document.activeElement?.tagName || "")) return;
    const number = Number(event.key);
    if (number >= 1 && number <= 6) {
      const choice = document.querySelectorAll(".action-choice")[number - 1];
      if (choice) {
        event.preventDefault();
        choice.click();
      }
    }
  });
  $("#journal-btn")?.addEventListener("click", toggleJournal);
  addMessage(
    "system",
    "Welcome to The Lost Lighthouse. Type anything — e.g. “move to the cave”."
  );
});
