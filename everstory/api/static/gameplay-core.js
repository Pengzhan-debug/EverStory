(() => {
  "use strict";

  // Single source-of-truth bridge for the immersive presentation layer.
  // The existing app.js still owns the basic DOM rendering; this module owns
  // resilient persistence, turn lifecycle, scene transitions and recovery UI.
  const $ = (s) => document.querySelector(s);
  const state = { world: null, busy: false, lastTurn: -1, lastLocation: null };

  async function request(path, options = {}) {
    const response = await fetch(path, {
      ...options,
      headers: { Accept: "application/json", "Content-Type": "application/json", ...(options.headers || {}) },
    });
    let data = null;
    try { data = await response.json(); } catch (_) {}
    if (!response.ok) throw new Error(data?.detail || `${path} returned ${response.status}`);
    return data;
  }

  function notify(message, type = "normal") {
    let host = $("#immersive-toasts");
    if (!host) {
      host = document.createElement("div");
      host.id = "immersive-toasts";
      document.body.appendChild(host);
    }
    const el = document.createElement("div");
    el.className = `immersive-toast ${type}`;
    el.textContent = message;
    host.appendChild(el);
    requestAnimationFrame(() => el.classList.add("show"));
    setTimeout(() => { el.classList.remove("show"); setTimeout(() => el.remove(), 400); }, 2600);
  }

  function pulse(className = "world-pulse") {
    document.body.classList.remove(className);
    void document.body.offsetWidth;
    document.body.classList.add(className);
  }

  function announceLocation(world) {
    const location = world?.player?.location_name;
    if (!location || location === state.lastLocation) return;
    if (state.lastLocation !== null) {
      const layer = $("#cinematic-layer");
      if (layer) {
        const title = layer.querySelector(".cinematic-title");
        const sub = layer.querySelector(".cinematic-sub");
        if (title) title.textContent = location;
        if (sub) sub.textContent = "The world rearranges itself around you.";
        layer.classList.remove("show");
        void layer.offsetWidth;
        layer.classList.add("show");
        setTimeout(() => layer.classList.remove("show"), 2400);
      }
      notify(`Entered ${location}`, "gold");
    }
    state.lastLocation = location;
  }

  function syncPresentation(world) {
    if (!world) return;
    const previousTurn = state.lastTurn;
    state.world = world;
    state.lastTurn = Number(world.turn ?? 0);
    announceLocation(world);
    if (previousTurn >= 0 && state.lastTurn !== previousTurn) pulse();
    window.dispatchEvent(new CustomEvent("everstory:world", { detail: world }));
  }

  async function refresh() {
    const world = await request("/api/world");
    syncPresentation(world);
    // Let the original renderer remain authoritative for existing panels.
    if (typeof window.render === "function") window.render();
    return world;
  }

  async function send(text) {
    if (!text || state.busy) return;
    state.busy = true;
    const input = $("#input");
    const form = $("#input-form");
    if (form) form.classList.add("is-processing");
    if (input) input.disabled = true;
    try {
      const data = await request("/api/turn", { method: "POST", body: JSON.stringify({ text }) });
      syncPresentation(data.world);
      if (typeof window.render === "function") window.render();
      notify(`Turn ${data.world?.turn ?? "?"} resolved`, "gold");
      return data;
    } catch (error) {
      notify(`Action failed: ${error.message}`, "error");
      throw error;
    } finally {
      state.busy = false;
      if (form) form.classList.remove("is-processing");
      if (input) input.disabled = false;
    }
  }

  async function save() {
    try {
      const result = await request("/api/save", { method: "POST", body: JSON.stringify({ name: "autosave" }) });
      notify(`World saved · turn ${result.turn ?? state.lastTurn}`, "gold");
      pulse("save-pulse");
      window.dispatchEvent(new CustomEvent("everstory:saved", { detail: result }));
    } catch (error) { notify(`Save failed: ${error.message}`, "error"); }
  }

  async function loadLatest() {
    try {
      const { saves = [] } = await request("/api/saves");
      if (!saves.length) { notify("No saved world yet"); return; }
      await request("/api/load", { method: "POST", body: JSON.stringify({ path: saves[0].path }) });
      await refresh();
      notify("Latest world restored", "gold");
      pulse("load-pulse");
      window.dispatchEvent(new CustomEvent("everstory:loaded", { detail: state.world }));
    } catch (error) { notify(`Load failed: ${error.message}`, "error"); }
  }

  async function reset() {
    try {
      await request("/api/reset", { method: "POST" });
      state.lastLocation = null;
      state.lastTurn = -1;
      await refresh();
      notify("A new world has begun", "gold");
      window.dispatchEvent(new CustomEvent("everstory:reset", { detail: state.world }));
    } catch (error) { notify(`New world failed: ${error.message}`, "error"); }
  }

  function interceptUI() {
    // Capture phase prevents app.js's legacy button listeners from issuing a second request.
    $("#save-btn")?.addEventListener("click", (e) => { e.preventDefault(); e.stopImmediatePropagation(); save(); }, true);
    $("#load-btn")?.addEventListener("click", (e) => { e.preventDefault(); e.stopImmediatePropagation(); loadLatest(); }, true);
    $("#reset-btn")?.addEventListener("click", (e) => { e.preventDefault(); e.stopImmediatePropagation(); reset(); }, true);

    $("#input-form")?.addEventListener("submit", (e) => {
      e.preventDefault();
      e.stopImmediatePropagation();
      const input = $("#input");
      const text = input?.value.trim();
      if (!text || state.busy) return;
      input.value = "";
      send(text).catch(() => {});
    }, true);
  }

  function expose() {
    window.EverStory = Object.freeze({
      get world() { return state.world; },
      refresh,
      send,
      save,
      load: loadLatest,
      reset,
      notify,
    });
  }

  function boot() {
    interceptUI();
    expose();
    refresh().catch((error) => notify(`World connection failed: ${error.message}`, "error"));
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
