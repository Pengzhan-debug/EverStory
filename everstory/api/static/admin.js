(() => {
  "use strict";
  const $ = (selector) => document.querySelector(selector);
  const number = (value) => new Intl.NumberFormat("zh-CN").format(Number(value || 0));

  function setState(text, kind) {
    const host = $("#service-state");
    host.textContent = text;
    host.className = `state ${kind}`;
  }

  function bars(host, rows) {
    const max = Math.max(1, ...rows.map((row) => Number(row.tokens || 0)));
    if (!rows.length) {
      host.innerHTML = '<div class="empty">真实模型开始调用后显示数据。</div>';
      return;
    }
    host.replaceChildren(...rows.map((row) => {
      const item = document.createElement("div");
      item.className = "bar-row";
      item.innerHTML = `<span class="bar-label"></span><span class="bar-track"><i class="bar-fill"></i></span><span class="bar-value"></span>`;
      item.querySelector(".bar-label").textContent = row.id;
      item.querySelector(".bar-fill").style.width = `${Math.max(2, row.tokens / max * 100)}%`;
      item.querySelector(".bar-value").textContent = number(row.tokens);
      return item;
    }));
  }

  function render(data) {
    const usage = data.usage;
    const service = data.service;
    $("#generated-at").textContent = `更新时间 ${new Date(data.generated_at).toLocaleString("zh-CN")}`;
    $("#active-users").textContent = number(data.users.active_24h);
    $("#user-breakdown").textContent = `${number(data.users.registered)} 注册 · ${number(data.users.guests)} 游客`;
    $("#investigations").textContent = number(data.investigations.total);
    $("#session-breakdown").textContent = `${number(data.auth.active_sessions)} 个有效登录会话`;
    $("#tokens-24h").textContent = number(usage.tokens_24h);
    $("#calls-24h").textContent = `${number(usage.calls_24h)} 次调用`;
    $("#success-rate").textContent = `${usage.success_rate_7d}%`;
    $("#failure-breakdown").textContent = `${number(usage.failures_7d)} 次失败 / 7 天`;
    $("#llm-mode").textContent = service.llm_mode === "api" ? "在线 API" : "离线 Stub";
    $("#account-gate").textContent = service.live_requires_account ? "已启用" : "未启用";
    $("#email-mode").textContent = service.email_configured ? `已配置 · ${service.email_mode}` : "待配置";
    $("#daily-limit").textContent = `${number(service.daily_token_limit)} Token`;
    $("#database-backend").textContent = `${service.database.backend} · ${service.database.ok ? "正常" : "异常"}`;
    $("#coordination-backend").textContent = `${service.coordination.backend} · ${service.coordination.ok ? "正常" : "异常"}`;
    $("#platform-tokens").textContent = number(usage.platform_tokens_7d);
    $("#personal-tokens").textContent = number(usage.personal_tokens_7d);
    $("#calls-7d").textContent = number(usage.calls_7d);
    bars($("#agent-chart"), usage.by_agent);
    bars($("#model-chart"), usage.by_model);

    const configured = service.providers.filter((item) => item.configured).length;
    $("#provider-summary").textContent = `${configured} / ${service.providers.length} 已配置`;
    $("#providers").replaceChildren(...service.providers.map((provider) => {
      const row = document.createElement("article");
      row.className = "provider";
      const state = provider.circuit.open ? "open" : provider.configured ? "ok" : "missing";
      const label = provider.circuit.open ? `熔断 ${provider.circuit.retry_after}s` : provider.configured ? "可用" : "未配置";
      row.innerHTML = '<strong></strong><code></code><span class="tag"></span>';
      row.querySelector("strong").textContent = provider.name;
      row.querySelector("code").textContent = provider.model;
      row.querySelector(".tag").className = `tag ${state}`;
      row.querySelector(".tag").textContent = label;
      return row;
    }));
    $("#dashboard").hidden = false;
    setState("服务正常", "ok");
    $("#footer-status").textContent = `EverStory ${service.version} · 灰度监控已连接`;
  }

  async function load() {
    $("#access-denied").hidden = true;
    setState("正在检查", "pending");
    try {
      const response = await fetch("/api/admin/overview", {headers: {Accept: "application/json"}});
      const data = await response.json();
      if (response.status === 403) {
        $("#dashboard").hidden = true;
        $("#access-denied").hidden = false;
        setState("无访问权限", "danger");
        $("#footer-status").textContent = "请使用管理员邮箱登录。";
        return;
      }
      if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
      render(data);
    } catch (error) {
      setState("连接失败", "danger");
      $("#footer-status").textContent = error.message;
    }
  }

  $("#refresh").addEventListener("click", load);
  load();
})();
