(() => {
  "use strict";

  const originalFetch = typeof window.fetch === "function"
    ? window.fetch.bind(window)
    : null;
  const mutationMethods = new Set(["POST", "PUT", "PATCH", "DELETE"]);

  function cookie(name) {
    const prefix = `${name}=`;
    const item = document.cookie.split(";").map((part) => part.trim())
      .find((part) => part.startsWith(prefix));
    return item ? decodeURIComponent(item.slice(prefix.length)) : "";
  }

  if (originalFetch) {
    window.fetch = (input, init = {}) => {
      const method = String(init.method || input?.method || "GET").toUpperCase();
      const rawUrl = typeof input === "string" ? input : input?.url;
      const url = new URL(rawUrl || location.href, location.href);
      if (url.origin === location.origin && mutationMethods.has(method)) {
        const csrf = cookie("everstory_csrf");
        if (csrf) {
          const headers = new Headers(init.headers || input?.headers || {});
          headers.set("X-CSRF-Token", csrf);
          init = {...init, headers};
        }
      }
      return originalFetch(input, init);
    };
  }

  const $ = (selector) => document.querySelector(selector);
  const zh = () => window.EverStoryI18n?.locale() === "zh-CN";
  const text = (en, cn) => zh() ? cn : en;
  let identity = null;
  let challengeId = "";
  let challengeEmail = "";
  let sessions = [];
  let investigations = [];

  async function api(path, options = {}) {
    if (!originalFetch) {
      return new Promise((resolve, reject) => {
        const request = new XMLHttpRequest();
        request.open(options.method || "GET", path);
        request.setRequestHeader("Accept", "application/json");
        request.setRequestHeader("Content-Type", "application/json");
        if (mutationMethods.has(String(options.method || "GET").toUpperCase())) {
          const csrf = cookie("everstory_csrf");
          if (csrf) request.setRequestHeader("X-CSRF-Token", csrf);
        }
        request.onload = () => {
          let data = {};
          try { data = JSON.parse(request.responseText || "{}"); } catch (_) {}
          if (request.status >= 200 && request.status < 300) resolve(data);
          else reject(new Error(data.error || data.detail || `HTTP ${request.status}`));
        };
        request.onerror = () => reject(new Error(text("Network request failed.", "网络请求失败。")));
        request.send(options.body || null);
      });
    }
    const response = await window.fetch(path, {
      ...options,
      headers: {Accept: "application/json", "Content-Type": "application/json", ...(options.headers || {})},
    });
    let data = {};
    try { data = await response.json(); } catch (_) {}
    if (!response.ok) throw new Error(data.error || data.detail || `HTTP ${response.status}`);
    return data;
  }

  function status(message = "", error = false) {
    const host = $("#account-status");
    if (!host) return;
    host.textContent = message;
    host.classList.toggle("error", error);
  }

  function renderIdentity() {
    const button = $("#account-btn");
    if (!button || !identity) return;
    const registered = Boolean(identity.user?.registered);
    button.classList.toggle("is-registered", registered);
    button.textContent = registered
      ? (identity.user.display_name || identity.user.email || text("Account", "账号"))
      : text("Guest", "游客");
    $("#account-guest-view").hidden = registered;
    $("#account-user-view").hidden = !registered;
    if (registered) {
      $("#account-name").textContent = identity.user.display_name || text("Investigator", "调查员");
      $("#account-email-label").textContent = identity.user.email || "";
    }
    const adminLink = $("#account-admin");
    if (adminLink) {
      adminLink.hidden = !Boolean(identity.user.is_admin);
      adminLink.textContent = text("Open operations console", "打开运营控制台");
    }
  }

  async function loadIdentity() {
    identity = await api("/api/auth/session");
    renderIdentity();
    return identity;
  }

  function sessionRow(session) {
    const row = document.createElement("div");
    row.className = "account-session";
    const info = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = session.current ? text("This browser", "当前浏览器") : text("Authorized browser", "已授权浏览器");
    const time = document.createElement("small");
    time.textContent = `${text("Last active", "最近活跃")} · ${new Date(session.last_seen_at).toLocaleString(zh() ? "zh-CN" : "en-US")}`;
    info.append(title, time);
    row.appendChild(info);
    if (!session.current) {
      const revoke = document.createElement("button");
      revoke.type = "button";
      revoke.textContent = text("Revoke", "下线");
      revoke.addEventListener("click", async () => {
        revoke.disabled = true;
        try {
          await api(`/api/auth/sessions/${encodeURIComponent(session.id)}`, {method: "DELETE"});
          await loadSessions();
        } catch (error) {
          status(error.message, true);
          revoke.disabled = false;
        }
      });
      row.appendChild(revoke);
    } else {
      const current = document.createElement("span");
      current.className = "account-current";
      current.textContent = text("CURRENT", "当前");
      row.appendChild(current);
    }
    return row;
  }

  function renderSessions() {
    const host = $("#account-sessions");
    if (!host) return;
    host.replaceChildren(...sessions.map(sessionRow));
  }

  async function loadSessions() {
    const host = $("#account-sessions");
    if (!host || !identity?.user?.registered) return;
    host.textContent = text("Loading sessions…", "正在加载设备……");
    try {
      const data = await api("/api/auth/sessions");
      sessions = data.sessions || [];
      renderSessions();
    } catch (error) {
      host.textContent = error.message;
    }
  }

  function investigationRow(investigation) {
    const row = document.createElement("article");
    row.className = `account-investigation${investigation.current ? " is-current" : ""}`;
    const body = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = window.EverStoryI18n?.value(investigation.title) || investigation.title;
    const locationLabel = window.EverStoryI18n?.value(investigation.location_name) || investigation.location_name || "—";
    const details = document.createElement("small");
    details.textContent = `${locationLabel} · ${text("Turn", "回合")} ${investigation.turn} · ${investigation.evidence} ${text("clues", "条线索")}`;
    const identifier = document.createElement("code");
    identifier.textContent = investigation.id.slice(0, 8);
    body.append(title, details, identifier);
    row.appendChild(body);
    if (investigation.current) {
      const current = document.createElement("span");
      current.className = "account-current";
      current.textContent = text("CURRENT", "当前案件");
      row.appendChild(current);
    } else {
      const resume = document.createElement("button");
      resume.type = "button";
      resume.textContent = text("Resume", "继续调查");
      resume.addEventListener("click", async () => {
        resume.disabled = true;
        status(text("Saving this case and opening the selected investigation…", "正在保存当前案件并打开所选调查……"));
        try {
          await api(`/api/auth/investigations/${encodeURIComponent(investigation.id)}/activate`, {method: "POST", body: "{}"});
          location.reload();
        } catch (error) {
          status(error.message, true);
          resume.disabled = false;
        }
      });
      row.appendChild(resume);
    }
    return row;
  }

  function renderInvestigations() {
    const host = $("#account-investigations");
    if (!host) return;
    host.replaceChildren(...investigations.map(investigationRow));
  }

  async function loadInvestigations() {
    const host = $("#account-investigations");
    if (!host || !identity?.user?.registered) return;
    host.textContent = text("Loading investigations…", "正在加载案件……");
    try {
      const data = await api("/api/auth/investigations");
      investigations = data.investigations || [];
      renderInvestigations();
    } catch (error) {
      host.textContent = error.message;
    }
  }

  async function loadAccountData() {
    await Promise.all([loadInvestigations(), loadSessions()]);
  }

  async function openPanel() {
    $("#account-panel")?.classList.add("open");
    $("#account-backdrop")?.classList.add("open");
    $("#account-panel")?.setAttribute("aria-hidden", "false");
    status();
    try {
      await loadIdentity();
      if (identity.user.registered) await loadAccountData();
      else if (!identity.email_login?.configured) {
        status(text(
          "Email sign-in is not configured on this deployment yet.",
          "当前部署尚未配置邮箱登录服务。"
        ), true);
      } else $("#account-email")?.focus();
    } catch (error) {
      status(error.message, true);
    }
  }

  function closePanel() {
    $("#account-panel")?.classList.remove("open");
    $("#account-backdrop")?.classList.remove("open");
    $("#account-panel")?.setAttribute("aria-hidden", "true");
  }

  function initialize() {
    if (!$("#account-btn")) return;
    loadIdentity().catch(() => {});
    $("#account-btn").addEventListener("click", openPanel);
    $("#account-close").addEventListener("click", closePanel);
    $("#account-backdrop").addEventListener("click", closePanel);
    $("#account-refresh-sessions").addEventListener("click", loadSessions);
    $("#account-refresh-investigations").addEventListener("click", loadInvestigations);

    $("#account-email-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      const button = event.currentTarget.querySelector("button");
      challengeEmail = $("#account-email").value.trim();
      button.disabled = true;
      status(text("Sending a one-time code…", "正在发送一次性验证码……"));
      try {
        const data = await api("/api/auth/email/request", {
          method: "POST",
          body: JSON.stringify({email: challengeEmail, locale: window.EverStoryI18n?.locale() || "en"}),
        });
        challengeId = data.challenge_id;
        $("#account-code-form").hidden = false;
        if (data.development_code) {
          $("#account-code").value = data.development_code;
          status(text(`Development code: ${data.development_code}`, `开发验证码：${data.development_code}`));
        } else {
          status(text("Check your email. The code expires in 10 minutes.", "请检查邮箱，验证码 10 分钟内有效。"));
        }
        $("#account-code").focus();
      } catch (error) {
        status(error.message, true);
      } finally {
        button.disabled = false;
      }
    });

    $("#account-code-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      const button = event.currentTarget.querySelector("button");
      button.disabled = true;
      status(text("Verifying and attaching this investigation…", "正在验证并绑定当前调查……"));
      try {
        const data = await api("/api/auth/email/verify", {
          method: "POST",
          body: JSON.stringify({challenge_id: challengeId, email: challengeEmail, code: $("#account-code").value.trim()}),
        });
        identity = {user: data.user, runtime_id: data.runtime_id};
        renderIdentity();
        status(text("Account verified. Your current investigation is preserved.", "账号验证成功，当前调查进度已保留。"));
        await loadAccountData();
      } catch (error) {
        status(error.message, true);
      } finally {
        button.disabled = false;
      }
    });

    $("#account-logout").addEventListener("click", async () => {
      try {
        await api("/api/auth/logout", {method: "POST", body: "{}"});
        location.reload();
      } catch (error) {
        status(error.message, true);
      }
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && $("#account-panel").classList.contains("open")) closePanel();
    });
    window.addEventListener("everstory:locale", () => {
      status();
      renderIdentity();
      renderInvestigations();
      renderSessions();
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initialize, {once: true});
  } else {
    initialize();
  }
})();
