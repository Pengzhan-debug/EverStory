(() => {
  const panel = document.querySelector("#team-panel");
  const backdrop = document.querySelector("#team-backdrop");
  const openButton = document.querySelector("#team-btn");
  const closeButton = document.querySelector("#team-close");
  const membersHost = document.querySelector("#team-members");
  const messagesHost = document.querySelector("#team-messages");
  const form = document.querySelector("#team-form");
  const input = document.querySelector("#team-input");
  const status = document.querySelector("#team-status");
  const evidenceCount = document.querySelector("#team-evidence-count");
  const boardCount = document.querySelector("#team-board-count");
  const evidenceHost = document.querySelector("#team-evidence-board");
  const viewButtons = document.querySelectorAll("[data-team-view]");
  let chat = { participants: [], messages: [], tasks: [], evidence: [] };
  let loaded = false;

  function esc(value) {
    const node = document.createElement("div");
    node.textContent = value == null ? "" : String(value);
    return node.innerHTML;
  }

  function setStatus(text, error = false) {
    status.textContent = text;
    status.classList.toggle("error", error);
  }

  function renderMembers() {
    membersHost.innerHTML = chat.participants
      .filter((member) => !member.human)
      .map(
        (member) => `
          <div class="team-member" title="${esc(member.role)}">
            <span class="team-avatar ${esc(member.color)}">${esc(member.initials)}</span>
            <span><span class="team-member-name">${esc(member.name)}</span><small>${esc(member.role)}</small></span>
          </div>`
      )
      .join("");
  }

  function timeLabel(value) {
    const date = new Date(value);
    return Number.isNaN(date.valueOf())
      ? ""
      : date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }

  function renderTask(task) {
    if (!task) return "";
    const complete = task.status === "completed";
    const changesWorld = Boolean(task.action);
    const evidence = task.evidence_ids?.length || 0;
    return `
      <section class="team-task-card ${complete ? "completed" : "proposed"}" data-task-id="${esc(task.id)}">
        <div class="team-task-kicker"><span>${complete ? "APPROVED RESULT" : "ACTION PROPOSAL"}</span><b>${complete ? "complete" : "awaiting you"}</b></div>
        <strong class="team-task-title">${esc(task.title)}</strong>
        <p>${esc(task.description)}</p>
        <div class="team-task-foot">
          <span>Target · ${esc(task.target)}${changesWorld ? " · consumes 1 turn" : " · case-board only"}</span>
          ${complete
            ? `<span class="team-task-done">✓ ${evidence ? `${evidence} new evidence` : "review recorded"}</span>`
            : `<button type="button" class="team-task-approve" data-approve-task="${esc(task.id)}" aria-label="Approve task ${esc(task.title)}">Approve</button>`}
        </div>
      </section>`;
  }

  function renderMessages() {
    const byId = Object.fromEntries(chat.messages.map((message) => [message.id, message]));
    const tasksById = Object.fromEntries((chat.tasks || []).map((task) => [task.id, task]));
    messagesHost.innerHTML = chat.messages
      .map((message) => {
        const replied = message.reply_to ? byId[message.reply_to] : null;
        const reply = replied
          ? `<div class="team-message-reply">↳ replying to ${esc(replied.sender_name)}</div>`
          : "";
        return `
          <article class="team-message ${message.human ? "player" : ""} ${esc(message.kind)}">
            <span class="team-avatar ${esc(message.color)}">${esc(message.initials)}</span>
            <div class="team-message-body">
              <div class="team-message-meta"><strong>${esc(message.sender_name)}</strong><span>${esc(message.sender_role)} · ${esc(timeLabel(message.created_at))}</span></div>
              ${reply}
              <div class="team-bubble">${esc(message.text)}</div>
              ${message.kind === "challenge" ? '<span class="team-kind">challenge / hypothesis check</span>' : ""}
              ${message.task_id && message.kind !== "task_result" ? renderTask(tasksById[message.task_id]) : ""}
            </div>
          </article>`;
      })
      .join("");
    messagesHost.scrollTop = messagesHost.scrollHeight;
  }

  function renderEvidence() {
    const evidence = chat.evidence || [];
    const tasks = chat.tasks || [];
    const membersById = Object.fromEntries(chat.participants.map((member) => [member.id, member]));
    const tasksById = Object.fromEntries(tasks.map((task) => [task.id, task]));
    const pending = tasks.filter((task) => task.status === "proposed");
    const counts = evidence.reduce((result, item) => {
      result[item.type] = (result[item.type] || 0) + 1;
      return result;
    }, {});
    const summary = `
      <div class="evidence-summary">
        <div><strong>${evidence.length}</strong><span>Confirmed</span></div>
        <div><strong>${counts.scene || 0}</strong><span>Scenes</span></div>
        <div><strong>${counts.item || 0}</strong><span>Objects</span></div>
        <div><strong>${counts.character || 0}</strong><span>People</span></div>
      </div>`;
    const pendingHtml = pending.length
      ? `<section class="case-board-section"><div class="case-board-heading"><span>OPEN ACTIONS</span><b>${pending.length}</b></div>${pending.map((task) => `
          <article class="case-lead-card">
            <span>${esc(task.agent_name)} · ${esc(task.target)}</span>
            <strong>${esc(task.title)}</strong>
            <button type="button" data-approve-task="${esc(task.id)}">Approve from board</button>
          </article>`).join("")}</section>`
      : "";
    const evidenceHtml = evidence.length
      ? evidence.map((item) => {
          const task = tasksById[item.task_id];
          const member = membersById[item.source_agent_id];
          return `
            <article class="evidence-card ${esc(item.type)}">
              <div class="evidence-card-top"><span>${esc(item.type)} · CONFIRMED</span><b>TURN ${esc(item.confirmed_at_turn)}</b></div>
              <strong>${esc(item.title)}</strong>
              <p>${esc(item.detail || "No additional description recorded.")}</p>
              <div class="evidence-source"><span>${member ? esc(member.initials) : "AI"}</span><div>Verified by ${esc(member?.name || item.source_agent_id)}<small>${esc(item.location_name)}${task ? ` · ${esc(task.title)}` : ""}</small></div></div>
            </article>`;
        }).join("")
      : `<div class="evidence-empty"><span>◇</span><strong>No confirmed evidence yet</strong><p>Ask the Field Investigator to inspect the current scene, then approve the proposed action.</p></div>`;
    evidenceHost.innerHTML = `${summary}${pendingHtml}<section class="case-board-section"><div class="case-board-heading"><span>CONFIRMED EVIDENCE</span><b>${evidence.length}</b></div>${evidenceHtml}</section>`;
  }

  function setView(view) {
    const selected = view === "evidence" ? "evidence" : "chat";
    panel.dataset.view = selected;
    viewButtons.forEach((button) => {
      const active = button.dataset.teamView === selected;
      button.classList.toggle("active", active);
      button.setAttribute("aria-selected", String(active));
    });
    if (selected === "evidence") {
      renderEvidence();
      setStatus("Case board · only engine-confirmed observations appear here.");
    } else {
      setStatus("You are the Lead Investigator. Agent claims remain hypotheses.");
      input.focus();
    }
  }

  function render() {
    renderMembers();
    renderMessages();
    renderEvidence();
    const count = (chat.evidence || []).length;
    evidenceCount.textContent = `${count} confirmed clue${count === 1 ? "" : "s"}`;
    boardCount.textContent = String(count);
  }

  async function loadChat() {
    setStatus("Loading team channel…");
    try {
      const response = await fetch("/api/agents/chat");
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Unable to load team chat.");
      chat = data;
      loaded = true;
      render();
      setStatus(
        panel.dataset.view === "evidence"
          ? "Case board · only engine-confirmed observations appear here."
          : "You are the Lead Investigator. Agent claims remain hypotheses."
      );
    } catch (error) {
      setStatus(error.message, true);
    }
  }

  async function openChat() {
    panel.classList.add("open");
    backdrop.classList.add("open");
    panel.setAttribute("aria-hidden", "false");
    openButton.setAttribute("aria-expanded", "true");
    if (!loaded) await loadChat();
    input.focus();
  }

  function closeChat() {
    panel.classList.remove("open");
    backdrop.classList.remove("open");
    panel.setAttribute("aria-hidden", "true");
    openButton.setAttribute("aria-expanded", "false");
  }

  async function sendMessage(text) {
    const sendButton = form.querySelector('button[type="submit"]');
    sendButton.disabled = true;
    input.disabled = true;
    setStatus("Team is reviewing facts and challenging assumptions…");
    try {
      const response = await fetch("/api/agents/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Team response failed.");
      chat = data;
      render();
      input.value = "";
      const proposed = (data.tasks || []).filter((task) => task.status === "proposed").length;
      setStatus(`${data.new_messages.length - 1} agent responses · ${proposed} action${proposed === 1 ? "" : "s"} awaiting approval`);
    } catch (error) {
      setStatus(error.message, true);
    } finally {
      sendButton.disabled = false;
      input.disabled = false;
      input.focus();
    }
  }

  async function approveTask(taskId, button) {
    button.disabled = true;
    setStatus("Running approved check against the authoritative world state…");
    try {
      const response = await fetch(`/api/agents/tasks/${encodeURIComponent(taskId)}/approve`, {
        method: "POST",
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Task approval failed.");
      chat = data;
      render();
      if (data.world && window.EverStory) await window.EverStory.refresh();
      const added = data.evidence?.length || 0;
      const turnStatus = data.world ? `world advanced to turn ${data.world.turn}` : "world turn unchanged";
      setStatus(`Approved result returned · ${added} total confirmed clue${added === 1 ? "" : "s"} · ${turnStatus}`);
    } catch (error) {
      button.disabled = false;
      setStatus(error.message, true);
    }
  }

  openButton.addEventListener("click", () => {
    if (panel.classList.contains("open")) closeChat();
    else openChat();
  });
  closeButton.addEventListener("click", closeChat);
  backdrop.addEventListener("click", closeChat);
  messagesHost.addEventListener("click", (event) => {
    const button = event.target.closest("[data-approve-task]");
    if (button) approveTask(button.dataset.approveTask, button);
  });
  evidenceHost.addEventListener("click", (event) => {
    const button = event.target.closest("[data-approve-task]");
    if (button) approveTask(button.dataset.approveTask, button);
  });
  viewButtons.forEach((button) => {
    button.addEventListener("click", () => setView(button.dataset.teamView));
  });
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const text = input.value.trim();
    if (text) sendMessage(text);
  });
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      form.requestSubmit();
    }
  });
  document.querySelectorAll("[data-mention]").forEach((button) => {
    button.addEventListener("click", () => {
      const mention = `${button.dataset.mention} `;
      if (!input.value.includes(mention)) input.value = mention + input.value;
      input.focus();
    });
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && panel.classList.contains("open")) closeChat();
    if (event.key.toLowerCase() === "g" && !event.ctrlKey && !event.metaKey && document.activeElement?.tagName !== "INPUT" && document.activeElement?.tagName !== "TEXTAREA") openChat();
  });
  window.addEventListener("everstory:loaded", () => loadChat());
  window.addEventListener("everstory:reset", () => loadChat());
})();
