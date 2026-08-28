const $ = (sel) => document.querySelector(sel);

let world = null;
const tr = (key) => window.EverStoryI18n?.t(key) || key;
const tv = (value) => window.EverStoryI18n?.value(value) || value;

function esc(s) {
  const div = document.createElement("div");
  div.textContent = s == null ? "" : String(s);
  return div.innerHTML;
}

const BOT_AVATAR =
  '<span class="avatar bot-avatar named-avatar">ES</span>';

function actionText(kind, label) {
  const localized = tv(label);
  const chinese = window.EverStoryI18n?.locale() === "zh-CN";
  const formats = chinese
    ? { talk: `与 ${localized} 交谈`, take: `拿取${localized}`, open: `打开${localized}`, move: `前往${localized}` }
    : { talk: `Talk to ${localized}`, take: `Take ${localized}`, open: `Open ${localized}`, move: `Travel to ${localized}` };
  return formats[kind] || localized;
}

function displayForCommand(command) {
  const suggestion = world?.scene?.suggestions?.find((item) => item.command === command);
  if (suggestion) return tv(suggestion.label);
  const match = String(command || "").match(/^(talk to|move to|take|open)\s+(.+)$/i);
  if (!match) return command;
  const kind = { "talk to": "talk", "move to": "move", take: "take", open: "open" }[match[1].toLowerCase()];
  const id = match[2];
  const entity = kind === "talk"
    ? world?.characters?.find((item) => item.id === id)
    : kind === "move"
      ? world?.locations?.find((item) => item.id === id)
      : world?.items?.find((item) => item.id === id);
  return entity ? actionText(kind, entity.name) : command;
}
window.displayForCommand = displayForCommand;

function addMessage(role, text) {
  const el = document.createElement("div");
  if (role === "system") {
    el.className = "msg system";
    el.innerHTML = `<div class="sys-pill">${esc(text)}</div>`;
  } else {
    el.className = `msg ${role}`;
    if (role === "user") {
      el.innerHTML = `
        <div class="user-message-content">
          <div class="user-speaker" data-player-speaker="true"><span>${tr("leadInvestigator")}</span><strong>${tr("you")}</strong></div>
          <div class="bubble">${esc(text)}</div>
        </div>
        <span class="avatar user-avatar named-avatar">${tr("youShort")}</span>`;
    } else {
      el.innerHTML = `${BOT_AVATAR}<div class="bubble">${esc(text)}</div>`;
    }
    el.querySelector(".bubble").dataset.rawText = text;
  }
  $("#messages").appendChild(el);
  $("#messages").scrollTop = $("#messages").scrollHeight;
  return el;
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
  $("#mode-chip").textContent = window.EverStoryI18n?.locale() === "zh-CN"
    ? `回合 ${world.turn} · 时间 ${world.time}`
    : `TURN ${world.turn} · TIME ${world.time}`;
  const locChip = $("#loc-chip");
  if (locChip) locChip.textContent = tv(world.player.location_name);
  const banner = $("#ending-banner");
  if (banner) {
    if (world.flags && world.flags.ending) {
      banner.hidden = false;
      banner.innerHTML = window.EverStoryI18n?.locale() === "zh-CN"
        ? `★ 案件终章——破坏者已经认罪，灯塔重新燃起，守塔人的秘密也终于揭晓。共用 <b>${world.turn}</b> 回合完成。`
        : `★ Case closed — the saboteur has confessed, the lighthouse burns again, and the keeper's secret is finally known. Completed in <b>${world.turn}</b> turns.`;
    } else {
      banner.hidden = true;
    }
  }
}

function renderPlayer(player) {
  const chips = (player.inventory || [])
    .map((i) => `<span class="chip inv">${esc(tv(i))}</span>`)
    .join("");
  $("#player-card").innerHTML = `
    <div class="player-row">
      <span class="avatar user-avatar big">${tr("youShort")}</span>
      <div class="player-info">
        <div class="player-name">${esc(tv(player.name))}</div>
        <div class="player-loc">📍 ${esc(tv(player.location_name))}</div>
      </div>
    </div>
    <div class="divider"></div>
    <div class="label">${tr("inventory")}</div>
    <div class="chips">${chips || `<span class="muted">${tr("empty")}</span>`}</div>
  `;
}

function renderFacts(world) {
  const english = window.EverStoryI18n?.locale() === "en";
  const entityName = (id) => {
    if (id === "player") return tv(world.player?.name || "You");
    return tv(world.characters?.find((item) => item.id === id)?.name || id);
  };
  const flags = Object.entries(world.flags || {})
    .map(([k, v]) => {
      const label = english
        ? k.replaceAll("_", " ").replace(/^./, (letter) => letter.toUpperCase())
        : tv(k);
      const value = typeof v === "boolean"
        ? (v ? tr("yes") : tr("no"))
        : entityName(String(v));
      return `<li><b>${esc(label)}</b>: ${esc(value)}</li>`;
    })
    .join("");
  const rels = (world.relationships || [])
    .map((r) => `<li><span class="rel-type">${esc(tv(r.type))}</span> ${esc(entityName(r.from))} → ${esc(entityName(r.to))}</li>`)
    .join("");
  $("#facts-card").innerHTML = `
    <div class="card-head"><h3>${tr("worldState")}</h3><span class="chip mono">${esc(world.state_hash)}</span></div>
    <div class="stat-row">
      <div class="stat"><div class="stat-num">${world.turn}</div><div class="stat-label">${tr("turns")}</div></div>
      <div class="stat"><div class="stat-num">${world.time}</div><div class="stat-label">${tr("time")}</div></div>
      <div class="stat"><div class="stat-num">${(world.history || []).length}</div><div class="stat-label">${tr("events")}</div></div>
    </div>
    ${flags ? `<div class="label">${tr("flags")}</div><ul class="facts">${flags}</ul>` : ""}
    ${rels ? `<div class="label">${tr("relationships")}</div><ul class="facts">${rels}</ul>` : ""}
  `;
}

function renderScene(scene) {
  if (!scene) return;
  const objective = $("#objective-text");
  if (objective) objective.textContent = tv(scene.objective || "Follow the evidence");

  const presence = $("#scene-presence");
  if (presence) {
    const characters = (scene.characters || []).map(
      (character) => `
        <button class="presence-card character" type="button" data-command="talk to ${esc(character.id)}" data-display="${esc(actionText("talk", character.name))}">
          <span class="presence-glyph">${esc(character.name.slice(0, 1))}</span>
          <span><strong>${esc(character.name)}</strong><small>${esc(tv(character.description || tr("someoneWaits")))}</small></span>
        </button>`
    );
    const items = (scene.items || []).map(
      (item) => `
        <button class="presence-card item" type="button" data-command="${item.locked ? `open ${esc(item.id)}` : `take ${esc(item.id)}`}" data-display="${esc(actionText(item.locked ? "open" : "take", item.name))}">
          <span class="presence-glyph">◇</span>
          <span><strong>${esc(tv(item.name))}</strong><small>${esc(tv(item.description || (item.locked ? tr("itIsLocked") : tr("availableInspect"))))}</small></span>
        </button>`
    );
    presence.innerHTML = [...characters, ...items].join("");
  }

  const actions = $("#action-suggestions");
  if (actions) {
    actions.innerHTML = (scene.suggestions || [])
      .map(
        (action, index) => `
          <button class="action-choice" type="button" data-command="${esc(action.command)}" data-display="${esc(tv(action.label))}">
            <span>${index + 1}</span>${esc(tv(action.label))}
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
        <div class="eyebrow" data-i18n="investigationRecord">${tr("investigationRecord")}</div>
        <h2 id="journal-title" data-i18n="keepersJournal">${tr("keepersJournal")}</h2>
        <div id="journal-content"></div>
      </section>`;
    document.body.appendChild(modal);
    modal.querySelector(".modal-backdrop").addEventListener("click", toggleJournal);
    modal.querySelector(".modal-close").addEventListener("click", toggleJournal);
  }
  const opening = !modal.classList.contains("open");
  if (opening && world) {
    const quests = (world.quests || [])
      .map((quest) => `<li class="${quest.done ? "done" : ""}"><span>${quest.done ? "✓" : "○"}</span>${esc(tv(quest.name))}</li>`)
      .join("");
    const history = [...(world.history || [])]
      .reverse()
      .slice(0, 12)
      .map((entry) => `<li><span>#${entry.turn}</span>${esc(tv(entry.message))}</li>`)
      .join("");
    modal.querySelector("#journal-content").innerHTML = `
      <h3>${tr("activeLead")}</h3><p>${esc(tv(world.scene?.objective || "Follow the evidence"))}</p>
      <h3>${tr("quests")}</h3><ul class="journal-quests">${quests || `<li>${tr("none")}</li>`}</ul>
      <h3>${tr("events")}</h3><ul class="journal-history">${history || `<li>${tr("noEvents")}</li>`}</ul>`;
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
        <button class="route-card" type="button" data-command="move to ${esc(location.id)}" data-display="${esc(actionText("move", location.name))}">
          <span class="route-direction">${tr("route")}</span>
          <strong>${esc(tv(location.name))}</strong>
          <span class="route-arrow">→</span>
        </button>`
    )
    .join("");
  const known = locations
    .filter((location) => !location.current && !(current.connections || []).includes(location.id))
    .map((location) => `<li>${esc(tv(location.name))}</li>`)
    .join("");
  host.innerHTML = `
    <div class="case-map">
      <div class="map-current">
        <span class="map-pin">⌖</span>
        <span><small>${tr("currentPosition")}</small><strong>${esc(tv(current.name))}</strong></span>
      </div>
      <div class="map-route-line"></div>
      <div class="map-routes">${routes || `<span class="muted">${tr("noRoute")}</span>`}</div>
      <details class="known-locations">
        <summary>${tr("otherLocations")}</summary>
        <ul>${known || `<li>${tr("none")}</li>`}</ul>
      </details>
    </div>`;
}

function renderEntities(world) {
  const byId = {};
  world.locations.forEach((l) => (byId[l.id] = l.name));
  world.items.forEach((item) => (byId[item.id] = item.name));
  const chars = world.characters
    .map(
      (c) =>
        `<li><span class="dot char"></span><b>${esc(tv(c.name))}</b> <span class="muted">@ ${esc(tv(byId[c.location_id] || "?"))}</span></li>`
    )
    .join("");
  const items = world.items
    .map((it) => {
      let where = "inventory";
      if (it.owner_id) {
        const owner = world.characters.find((c) => c.id === it.owner_id);
        where = `${tr("ownedBy")} ${tv(owner ? owner.name : it.owner_id)}`;
      } else if (it.location_id) {
        where = byId[it.location_id] || it.location_id;
      }
      const tags = [];
      if (it.locked) tags.push(tr("locked"));
      if (it.lit) tags.push(tr("lit"));
      return `<li><span class="dot item"></span><b>${esc(tv(it.name))}</b> <span class="muted">(${esc(tv(where))}${tags.length ? ", " + tags.join(", ") : ""})</span></li>`;
    })
    .join("");
  $("#entities-card").innerHTML = `
    <div class="card-head"><h3>${tr("charactersItems")}</h3></div>
    <div class="label">${tr("characters")}</div>
    <ul class="facts">${chars || `<li class="muted">${tr("none")}</li>`}</ul>
    <div class="label">${tr("items")}</div>
    <ul class="facts">${items || `<li class="muted">${tr("none")}</li>`}</ul>
  `;
}

function renderQuests(quests) {
  const done = (quests || []).filter((q) => q.done).length;
  const total = (quests || []).length || 1;
  const pct = Math.round((done / total) * 100);
  $("#quests-card").innerHTML = `
    <div class="card-head"><h3>${tr("quests")}</h3><span class="chip">${done}/${total}</span></div>
    <div class="progress"><div class="progress-fill" style="width:${pct}%"></div></div>
    <ul class="facts">${(quests || [])
      .map(
        (q) =>
          `<li class="${q.done ? "done" : ""}">${q.done ? "✔" : "◌"} ${esc(tv(q.name))}</li>`
      )
      .join("")}</ul>
  `;
}

function renderLog(history) {
  const rows = [...history]
    .reverse()
    .map(
      (h) =>
        `<li class="log-row ${h.ok ? "ok" : "rej"}"><span class="log-turn">#${h.turn}</span><span class="log-dot ${h.ok ? "ok" : "rej"}"></span>${esc(tv(h.message))}</li>`
    )
    .join("");
  $("#log").innerHTML =
    `<ul class="log-list">${rows || `<li class="muted">${tr("noEvents")}</li>`}</ul>`;
}

document.addEventListener("DOMContentLoaded", () => {
  window.addEventListener("everstory:world", (event) => {
    world = event.detail;
    render();
  });
  window.addEventListener("everstory:locale", () => {
    render();
    document.querySelectorAll("#messages .bubble[data-raw-text]").forEach((bubble) => {
      bubble.textContent = tv(bubble.dataset.rawText);
    });
    document.querySelectorAll('[data-player-speaker="true"]').forEach((speaker) => {
      speaker.querySelector("span").textContent = tr("leadInvestigator");
      speaker.querySelector("strong").textContent = tr("you");
      speaker.closest(".msg.user")?.querySelector(".user-avatar")?.replaceChildren(tr("youShort"));
    });
    document.querySelectorAll("#messages .msg.user[data-command]").forEach((message) => {
      const label = displayForCommand(message.dataset.command);
      const bubble = message.querySelector(".bubble");
      if (bubble) bubble.textContent = label;
    });
    const welcome = $("#messages .msg.system .sys-pill");
    if (welcome) {
      welcome.textContent = window.EverStoryI18n?.locale() === "zh-CN"
        ? "风暴把你冲上盐岩岛。先寻找庇护，并打开联合调查室（G）与调查员建立联系；关键证据必须由团队复核。"
        : "The storm has cast you onto Saltrock Island. Find shelter and open the Investigation Room (G) to contact your team; critical evidence requires team review.";
    }
  });
  $("#game-language")?.addEventListener("change", (event) => {
    window.EverStoryI18n?.setLocale(event.target.value);
  });
  const settingsButton = $("#settings-btn");
  settingsButton?.addEventListener("click", (event) => {
    // Some embedded browsers ignore target=_blank. Keep the normal anchor as
    // a fallback, but explicitly open a named console tab when popups work.
    const consoleWindow = window.open(settingsButton.href, "everstory-api-console");
    if (consoleWindow) {
      event.preventDefault();
      consoleWindow.focus();
    }
  });
  document.addEventListener("click", (event) => {
    const action = event.target.closest("[data-command]");
    if (!action) return;
    const command = action.dataset.command;
    const displayText = action.dataset.display || action.textContent.trim().replace(/^\d+\s*/, "");
    if (command && window.EverStory) window.EverStory.send(command, displayText).catch(() => {});
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
    window.EverStoryI18n?.locale() === "zh-CN"
      ? "风暴把你冲上盐岩岛。先寻找庇护，并打开联合调查室（G）与调查员建立联系；关键证据必须由团队复核。"
      : "The storm has cast you onto Saltrock Island. Find shelter and open the Investigation Room (G) to contact your team; critical evidence requires team review."
  );
});
