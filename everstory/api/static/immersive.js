(() => {
  "use strict";

  const $ = (s, root = document) => root.querySelector(s);
  const zh = () => window.EverStoryI18n?.locale() === "zh-CN";
  const t = (key) => window.EverStoryI18n?.t(key) || key;
  const tv = (value) => window.EverStoryI18n?.value(value) || value;
  let lastWorld = null;
  let audioCtx = null;
  let ambience = null;
  let activeSceneUrl = "";
  let sceneRequest = 0;

  const LOCATION_SCENES = [
    { match: ["storm shore", "shore"], url: "/static/img/scenes/dock.webp" },
    { match: ["keeper's cottage", "cottage"], url: "/static/img/scenes/cottage.webp" },
    { match: ["boat shed", "dock"], url: "/static/img/scenes/dock.webp" },
    { match: ["sea cave", "cliff path", "cave", "cliff"], url: "/static/img/scenes/cliff-cave.webp" },
    { match: ["lighthouse ground", "lighthouse tower", "lantern room"], url: "/static/img/scenes/lighthouse-interior.webp" },
  ];

  const safe = (v) => String(v ?? "").replace(/[&<>\"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]));

  function toast(message, tone = "normal") {
    let host = $("#immersive-toasts");
    if (!host) {
      host = document.createElement("div");
      host.id = "immersive-toasts";
      document.body.appendChild(host);
    }
    const item = document.createElement("div");
    item.className = `immersive-toast ${tone}`;
    item.textContent = message;
    host.appendChild(item);
    requestAnimationFrame(() => item.classList.add("show"));
    setTimeout(() => {
      item.classList.remove("show");
      setTimeout(() => item.remove(), 450);
    }, 2800);
  }

  function cinematic(text, subtitle = "") {
    let layer = $("#cinematic-layer");
    if (!layer) {
      layer = document.createElement("div");
      layer.id = "cinematic-layer";
      layer.innerHTML = '<div class="cinematic-kicker">EVERSTORY</div><div class="cinematic-title"></div><div class="cinematic-sub"></div>';
      document.body.appendChild(layer);
    }
    $(".cinematic-title", layer).textContent = text;
    $(".cinematic-sub", layer).textContent = subtitle;
    layer.classList.remove("show");
    void layer.offsetWidth;
    layer.classList.add("show");
    setTimeout(() => layer.classList.remove("show"), 3000);
  }

  function sceneUrlFor(location) {
    const name = String(location || "").toLowerCase();
    return LOCATION_SCENES.find((scene) => scene.match.some((part) => name.includes(part)))?.url
      || "/static/img/lighthouse-investigation-v3.png";
  }

  function updateLocationScene(location) {
    const scene = $("#world-scene");
    if (!scene) return;
    const url = sceneUrlFor(location);
    if (url === activeSceneUrl) return;
    const request = ++sceneRequest;
    const image = new Image();
    image.decoding = "async";
    image.onload = () => {
      if (request !== sceneRequest) return;
      scene.classList.add("scene-switching");
      setTimeout(() => {
        if (request !== sceneRequest) return;
        scene.style.setProperty("--scene-image", `url("${url}")`);
        scene.dataset.scene = url.split("/").pop().replace(/\.[^.]+$/, "");
        activeSceneUrl = url;
        requestAnimationFrame(() => scene.classList.remove("scene-switching"));
      }, 180);
    };
    image.src = url;
  }

  function updateAtmosphere(world) {
    if (!world) return;
    const location = String(world.player?.location_name || "").toLowerCase();
    const weather = String(world.weather || world.flags?.weather || "storm").toLowerCase();
    document.body.classList.toggle("weather-storm", weather.includes("storm") || weather.includes("rain"));
    document.body.classList.toggle("location-cave", location.includes("cave"));
    document.body.classList.toggle("location-lighthouse", location.includes("light"));
    document.body.classList.toggle("location-harbor", location.includes("harbor") || location.includes("port"));
    document.body.classList.toggle("lighthouse-lit", Boolean(world.flags?.lighthouse_lit));
    updateLocationScene(world.player?.location_name);
    const title = $(".scene-title");
    if (title && world.player?.location_name) title.textContent = tv(world.player.location_name);
    const time = $("#hud-time");
    const turn = $("#hud-turn");
    if (time) time.textContent = world.time ?? "—";
    if (turn) turn.textContent = world.turn ?? "—";
    const chip = $("#mode-chip");
    if (chip) chip.textContent = zh()
      ? `回合 ${world.turn ?? 0} · 时间 ${world.time ?? 0}`
      : `TURN ${world.turn ?? 0} · TIME ${world.time ?? 0}`;
  }

  function createInventory() {
    if ($("#inventory-modal")) return;
    const modal = document.createElement("div");
    modal.id = "inventory-modal";
    modal.innerHTML = `<div class="modal-backdrop"></div><section class="inventory-sheet"><button class="modal-close" aria-label="Close">×</button><div class="eyebrow" data-i18n="personalEffects">${t("personalEffects")}</div><h2 data-i18n="inventory">${t("inventory")}</h2><div id="inventory-grid"></div><div class="modal-footer" data-i18n="closeInventoryHint">${t("closeInventoryHint")}</div></section>`;
    document.body.appendChild(modal);
    window.EverStoryI18n?.apply();
    $(".modal-backdrop", modal).addEventListener("click", closeInventory);
    $(".modal-close", modal).addEventListener("click", closeInventory);
  }

  function openInventory() {
    createInventory();
    const grid = $("#inventory-grid");
    const items = lastWorld?.player?.inventory || [];
    grid.innerHTML = items.length
      ? items.map((item, i) => `<div class="inventory-item"><div class="item-glyph">${["◈","✦","◇","†","○"][i % 5]}</div><div><strong>${safe(tv(item))}</strong><small>${t("carriedItem")}</small></div></div>`).join("")
      : `<div class="inventory-empty">${t("packEmpty")}</div>`;
    $("#inventory-modal").classList.add("open");
  }

  function closeInventory() {
    $("#inventory-modal")?.classList.remove("open");
  }

  function toggleInspector() {
    const inspector = $("#inspector");
    if (!inspector) return;
    const open = document.body.classList.toggle("truth-open");
    $("#debug-btn")?.setAttribute("aria-expanded", String(open));
    $("#truth-backdrop")?.setAttribute("aria-hidden", String(!open));
    toast(open
      ? (zh() ? "世界真相档案已展开" : "World truth revealed")
      : (zh() ? "世界真相档案已收起" : "World truth concealed"));
  }

  function initAudio() {
    if (audioCtx) return;
    try {
      audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      const master = audioCtx.createGain();
      master.gain.value = 0.035;
      master.connect(audioCtx.destination);
      const osc = audioCtx.createOscillator();
      osc.type = "sine";
      osc.frequency.value = 55;
      const gain = audioCtx.createGain();
      gain.gain.value = 0.05;
      osc.connect(gain).connect(master);
      osc.start();
      ambience = { osc, master };
    } catch (_) {}
  }

  function actionTone(ok = true) {
    if (!audioCtx) return;
    const o = audioCtx.createOscillator();
    const g = audioCtx.createGain();
    o.type = "sine";
    o.frequency.value = ok ? 330 : 130;
    g.gain.setValueAtTime(0.0001, audioCtx.currentTime);
    g.gain.exponentialRampToValueAtTime(0.035, audioCtx.currentTime + 0.01);
    g.gain.exponentialRampToValueAtTime(0.0001, audioCtx.currentTime + 0.28);
    o.connect(g).connect(ambience?.master || audioCtx.destination);
    o.start(); o.stop(audioCtx.currentTime + 0.3);
  }

  function watchWorld() {
    // Driven by the shared everstory:world event (world-sync + gameplay-core),
    // so there is only ONE poller instead of two.
    window.addEventListener("everstory:world", (e) => {
      const world = e.detail;
      if (!world) return;
      const previous = lastWorld;
      lastWorld = world;
      updateAtmosphere(world);
      if (previous && previous.turn !== world.turn) {
        document.body.classList.remove("world-pulse");
        void document.body.offsetWidth;
        document.body.classList.add("world-pulse");
        actionTone(true);
      }
    });
  }

  function observeMessages() {
    const messages = $("#messages");
    if (!messages) return;
    const observer = new MutationObserver((mutations) => {
      for (const m of mutations) {
        if (m.addedNodes.length) {
          for (const node of m.addedNodes) {
            if (node.nodeType === 1 && node.classList.contains("msg")) {
              node.classList.add("story-arrive");
            }
          }
        }
      }
    });
    observer.observe(messages, { childList: true });
  }

  function bindShortcuts() {
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        closeInventory();
        if (document.body.classList.contains("truth-open")) toggleInspector();
      }
      if (e.key.toLowerCase() === "i" && !/input|textarea/i.test(document.activeElement?.tagName || "")) {
        e.preventDefault(); openInventory();
      }
      if (e.key.toLowerCase() === "v" && !/input|textarea/i.test(document.activeElement?.tagName || "")) {
        e.preventDefault(); toggleInspector();
      }
      if (e.key === "Enter" && document.activeElement === document.body) $("#input")?.focus();
    });
    ["pointerdown", "keydown"].forEach((event) => window.addEventListener(event, () => { initAudio(); }, { once: true }));
    const send = $("#input-form");
    send?.addEventListener("submit", () => setTimeout(() => actionTone(true), 50));
    $("#save-btn")?.addEventListener("click", () => toast(zh() ? "世界快照已保存" : "World snapshot saved", "gold"));
    $("#load-btn")?.addEventListener("click", () => toast(zh() ? "最近的世界快照已读取" : "Latest world snapshot loaded"));
    $("#reset-btn")?.addEventListener("click", () => cinematic(zh() ? "新的案件" : "A New World", zh() ? "故事再次开始。" : "The story begins again."));
    $("#inventory-btn")?.addEventListener("click", openInventory);
    $("#debug-btn")?.addEventListener("click", toggleInspector);
    $("#inspector-close")?.addEventListener("click", toggleInspector);
    $("#truth-backdrop")?.addEventListener("click", toggleInspector);
  }

  function introCinematic() {
    const layer = $("#intro-layer");
    if (!layer) return;
    const returning = new URLSearchParams(window.location.search).get("resume") === "1";
    if (returning || sessionStorage.getItem("everstory-intro-seen") === "1") {
      sessionStorage.setItem("everstory-intro-seen", "1");
      if (returning) history.replaceState({}, "", "/");
      layer.remove();
      return;
    }
    const finish = () => {
      sessionStorage.setItem("everstory-intro-seen", "1");
      layer.classList.add("done");
      setTimeout(() => layer.remove(), 1200);
    };
    const skip = $("#intro-skip");
    if (skip) skip.addEventListener("click", (e) => { e.stopPropagation(); finish(); });
    layer.addEventListener("click", finish);
    setTimeout(finish, 3600);
  }

  function boot() {
    observeMessages();
    bindShortcuts();
    createInventory();
    introCinematic();
    if (sessionStorage.getItem("everstory-intro-seen") !== "1") {
      cinematic(zh() ? "失落灯塔" : "The Lost Lighthouse", zh() ? "一个不会说谎的世界。" : "A world that cannot lie.");
    }
    watchWorld();
    window.addEventListener("everstory:locale", () => lastWorld && updateAtmosphere(lastWorld));
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
