(() => {
  "use strict";

  // Single source-of-truth bridge for the immersive presentation layer.
  // The existing app.js still owns the basic DOM rendering; this module owns
  // resilient persistence, turn lifecycle, scene transitions and recovery UI.
  const $ = (s) => document.querySelector(s);
  const zh = () => window.EverStoryI18n?.locale() === "zh-CN";
  const tv = (value) => window.EverStoryI18n?.value(value) || value;
  const state = { world: null, busy: false, lastTurn: -1, lastLocation: null };

  function setWorldStatus(label, tone = "stable") {
    const status = $(".world-status");
    if (!status) return;
    status.className = `world-status is-${tone}`;
    const translated = zh() ? ({
      "WORLD CONNECTING": "正在连接世界", "WORLD STABLE": "世界状态稳定",
      "WORLD OFFLINE": "世界离线", "WORLD RESOLVING": "世界正在裁决",
    }[label] || label) : label;
    status.innerHTML = '<span class="status-dot"></span>' + translated;
  }

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
        if (title) title.textContent = tv(location);
        if (sub) sub.textContent = zh() ? "世界状态随着你的行动重新排列。" : "The world rearranges itself around you.";
        layer.classList.remove("show");
        void layer.offsetWidth;
        layer.classList.add("show");
        setTimeout(() => layer.classList.remove("show"), 2400);
      }
      notify(zh() ? `已进入${tv(location)}` : `Entered ${location}`, "gold");
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
    setWorldStatus("WORLD CONNECTING", "busy");
    try {
      const world = await request("/api/world");
      syncPresentation(world);
      // Let the original renderer remain authoritative for existing panels.
      if (typeof window.render === "function") window.render();
      setWorldStatus("WORLD STABLE", "stable");
      return world;
    } catch (error) {
      setWorldStatus("WORLD OFFLINE", "offline");
      throw error;
    }
  }

  async function send(text) {
    if (!text || state.busy) return;
    state.busy = true;
    setWorldStatus("WORLD RESOLVING", "busy");
    const input = $("#input");
    const form = $("#input-form");
    if (form) form.classList.add("is-processing");
    if (input) input.disabled = true;

    // Chat feel: show the player's bubble immediately, then stream the reply.
    if (typeof addMessage === "function") {
      addMessage("user", text);
    }
    if (input) input.value = "";
    const bubble = document.createElement("div");
    bubble.className = "msg assistant";
    bubble.innerHTML =
      (typeof BOT_AVATAR !== "undefined" ? BOT_AVATAR : '<span class="avatar bot-avatar">AI</span>') +
      '<div class="bubble"></div>';
    const bubbleText = bubble.querySelector(".bubble");
    $("#messages").appendChild(bubble);
    $("#messages").scrollTop = $("#messages").scrollHeight;

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 120000);
    let full = "";
    try {
      const resp = await fetch("/api/turn/stream", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "text/event-stream",
        },
        body: JSON.stringify({ text }),
        signal: controller.signal,
      });
      if (!resp.ok || !resp.body) {
        let detail = "";
        try {
          detail = (await resp.json()).detail || "";
        } catch (_) {}
        throw new Error(detail || `server returned ${resp.status}`);
      }
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let done = null;
      for (;;) {
        const { done: finished, value } = await reader.read();
        if (finished) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop();
        for (const part of parts) {
          const line = part
            .split("\n")
            .find((l) => l.startsWith("data: "));
          if (!line) continue;
          let ev;
          try {
            ev = JSON.parse(line.slice(6));
          } catch (_) {
            continue;
          }
          if (ev.type === "text") {
            full += ev.delta;
            bubbleText.textContent = full;
            $("#messages").scrollTop = $("#messages").scrollHeight;
          } else if (ev.type === "replace") {
            full = ev.text;
            bubbleText.textContent = full;
          } else if (ev.type === "done") {
            done = ev;
          } else if (ev.type === "error") {
            throw new Error(ev.message || "stream error");
          }
        }
      }
      if (done?.world) syncPresentation(done.world);
      if (typeof window.render === "function") window.render();
      notify(`Turn ${done?.turn ?? "?"} resolved`, "gold");
      return done;
    } catch (error) {
      bubbleText.textContent =
        error.name === "AbortError"
          ? "(⏳ took too long — the world is thinking; try again)"
          : `⚠ ${error.message || "request failed"}`;
      notify(`Action failed: ${error.message}`, "error");
      throw error;
    } finally {
      clearTimeout(timer);
      state.busy = false;
      if (form) form.classList.remove("is-processing");
      if (input) input.disabled = false;
      setWorldStatus(state.world ? "WORLD STABLE" : "WORLD OFFLINE", state.world ? "stable" : "offline");
    }
  }

  async function save() {
    try {
      const result = await request("/api/save", { method: "POST", body: JSON.stringify({ name: "autosave" }) });
      notify(`Case saved · turn ${result.turn ?? state.lastTurn} · ${result.evidence ?? 0} clues`, "gold");
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
      notify(`Latest case restored · ${saves[0].evidence ?? 0} clues`, "gold");
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
    window.addEventListener("everstory:locale", () => {
      if (state.world) {
        state.lastLocation = null;
        announceLocation(state.world);
        setWorldStatus("WORLD STABLE", "stable");
      }
    });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
