(() => {
  "use strict";

  const $ = (s, root = document) => root.querySelector(s);
  let lastWorld = null;
  let audioCtx = null;
  let ambience = null;
  let sceneCanvas = null;
  let sceneCtx = null;
  const particles = [];

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

  function initSceneCanvas() {
    const host = $(".world-backdrop");
    if (!host) return;
    sceneCanvas = document.createElement("canvas");
    sceneCanvas.className = "immersive-scene-canvas";
    sceneCanvas.setAttribute("aria-hidden", "true");
    host.prepend(sceneCanvas);
    sceneCtx = sceneCanvas.getContext("2d");
    for (let i = 0; i < 90; i++) particles.push(makeParticle(true));
    resizeScene();
    window.addEventListener("resize", resizeScene);
    requestAnimationFrame(drawScene);
  }

  function makeParticle(initial = false) {
    return {
      x: Math.random(),
      y: initial ? Math.random() : -0.02,
      speed: 0.0008 + Math.random() * 0.0022,
      drift: (Math.random() - 0.5) * 0.00045,
      size: 0.5 + Math.random() * 1.7,
      alpha: 0.08 + Math.random() * 0.35,
      rain: Math.random() < 0.18,
    };
  }

  function resizeScene() {
    if (!sceneCanvas) return;
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    sceneCanvas.width = Math.round(innerWidth * dpr);
    sceneCanvas.height = Math.round(innerHeight * dpr);
    sceneCanvas.style.width = `${innerWidth}px`;
    sceneCanvas.style.height = `${innerHeight}px`;
    sceneCtx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  function drawScene() {
    if (!sceneCtx) return;
    const w = innerWidth, h = innerHeight;
    sceneCtx.clearRect(0, 0, w, h);
    const storm = document.body.classList.contains("weather-storm");
    for (const p of particles) {
      p.y += p.speed * (storm ? 2.2 : 1);
      p.x += p.drift;
      if (p.y > 1.03 || p.x < -0.03 || p.x > 1.03) Object.assign(p, makeParticle());
      const x = p.x * w, y = p.y * h;
      sceneCtx.beginPath();
      sceneCtx.fillStyle = `rgba(220,232,233,${p.alpha * (storm ? 0.8 : 0.45)})`;
      if (p.rain) {
        sceneCtx.moveTo(x, y);
        sceneCtx.lineTo(x - 1, y + 7 + p.size * 4);
        sceneCtx.strokeStyle = `rgba(150,198,208,${p.alpha * 0.45})`;
        sceneCtx.lineWidth = 0.6;
        sceneCtx.stroke();
      } else {
        sceneCtx.arc(x, y, p.size, 0, Math.PI * 2);
        sceneCtx.fill();
      }
    }
    requestAnimationFrame(drawScene);
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

  function updateAtmosphere(world) {
    if (!world) return;
    const location = String(world.player?.location_name || "").toLowerCase();
    const weather = String(world.weather || world.flags?.weather || "storm").toLowerCase();
    document.body.classList.toggle("weather-storm", weather.includes("storm") || weather.includes("rain"));
    document.body.classList.toggle("location-cave", location.includes("cave"));
    document.body.classList.toggle("location-lighthouse", location.includes("light"));
    document.body.classList.toggle("location-harbor", location.includes("harbor") || location.includes("port"));
    const title = $(".scene-title");
    if (title && world.player?.location_name) title.textContent = world.player.location_name;
    const time = $("#hud-time");
    const turn = $("#hud-turn");
    if (time) time.textContent = world.time ?? "—";
    if (turn) turn.textContent = world.turn ?? "—";
    const chip = $("#mode-chip");
    if (chip) chip.textContent = `TURN ${world.turn ?? 0} · TIME ${world.time ?? 0}`;
  }

  function createInventory() {
    if ($("#inventory-modal")) return;
    const modal = document.createElement("div");
    modal.id = "inventory-modal";
    modal.innerHTML = `<div class="modal-backdrop"></div><section class="inventory-sheet"><button class="modal-close" aria-label="Close">×</button><div class="eyebrow">PERSONAL EFFECTS</div><h2>Inventory</h2><div id="inventory-grid"></div><div class="modal-footer">Press <b>I</b> or <b>ESC</b> to close</div></section>`;
    document.body.appendChild(modal);
    $(".modal-backdrop", modal).addEventListener("click", closeInventory);
    $(".modal-close", modal).addEventListener("click", closeInventory);
  }

  function openInventory() {
    createInventory();
    const grid = $("#inventory-grid");
    const items = lastWorld?.player?.inventory || [];
    grid.innerHTML = items.length ? items.map((item, i) => `<div class="inventory-item"><div class="item-glyph">${["◈","✦","◇","†","○"][i % 5]}</div><div><strong>${safe(item)}</strong><small>Carried item</small></div></div>`).join("") : '<div class="inventory-empty">Your pack is empty.</div>';
    $("#inventory-modal").classList.add("open");
  }

  function closeInventory() {
    $("#inventory-modal")?.classList.remove("open");
  }

  function toggleInspector() {
    const inspector = $("#inspector");
    if (!inspector) return;
    inspector.classList.toggle("inspector-focus");
    toast(inspector.classList.contains("inspector-focus") ? "World State focused" : "World State restored");
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

  async function pollWorld() {
    try {
      const res = await fetch("/api/world", { headers: { "Accept": "application/json" } });
      if (!res.ok) return;
      const world = await res.json();
      const previous = lastWorld;
      lastWorld = world;
      updateAtmosphere(world);
      if (previous && previous.player?.location_name !== world.player?.location_name) {
        cinematic(world.player.location_name || "Unknown Waters", "The world has changed around you.");
        toast(`Entered ${world.player.location_name}`, "gold");
        actionTone(true);
      }
      if (previous && previous.turn !== world.turn) {
        document.body.classList.remove("world-pulse");
        void document.body.offsetWidth;
        document.body.classList.add("world-pulse");
      }
    } catch (_) {}
    setTimeout(pollWorld, 2200);
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
              if (node.classList.contains("assistant")) cinematic("A new chapter unfolds", "EverStory is resolving the consequences…");
            }
          }
        }
      }
    });
    observer.observe(messages, { childList: true });
  }

  function bindShortcuts() {
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") closeInventory();
      if (e.key.toLowerCase() === "i" && !/input|textarea/i.test(document.activeElement?.tagName || "")) {
        e.preventDefault(); openInventory();
      }
      if (e.key === "Tab") {
        e.preventDefault(); toggleInspector();
      }
      if (e.key === "Enter" && document.activeElement === document.body) $("#input")?.focus();
    });
    ["pointerdown", "keydown"].forEach((event) => window.addEventListener(event, () => { initAudio(); }, { once: true }));
    const send = $("#input-form");
    send?.addEventListener("submit", () => setTimeout(() => actionTone(true), 50));
    $("#save-btn")?.addEventListener("click", () => toast("World snapshot saved", "gold"));
    $("#load-btn")?.addEventListener("click", () => toast("Latest world snapshot loaded"));
    $("#reset-btn")?.addEventListener("click", () => cinematic("A New World", "The story begins again."));
  }

  function boot() {
    initSceneCanvas();
    observeMessages();
    bindShortcuts();
    createInventory();
    cinematic("The Lost Lighthouse", "A world that cannot lie.");
    pollWorld();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
