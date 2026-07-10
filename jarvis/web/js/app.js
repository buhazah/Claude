/* JARVIS app controller: auth flow, routing, and every view renderer. */
(() => {
  const state = { user: null, view: "dashboard", conversation: null, agents: [], convos: [] };

  // ------------------------------------------------------------- boot
  document.addEventListener("DOMContentLoaded", async () => {
    injectIcons();
    setupTheme();
    setupAuth();
    setupShell();
    if (API.isAuthed()) {
      try { await enterApp(); } catch { showAuth(); }
    } else showAuth();
  });

  // ------------------------------------------------------------- theme
  function setupTheme() {
    const saved = localStorage.getItem("jarvis_theme") || "dark";
    document.documentElement.dataset.theme = saved;
    document.getElementById("theme-toggle").onclick = () => {
      const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
      document.documentElement.dataset.theme = next;
      localStorage.setItem("jarvis_theme", next);
    };
  }

  // ------------------------------------------------------------- auth UI
  let authMode = "login";
  function setupAuth() {
    const form = document.getElementById("auth-form");
    const link = document.getElementById("auth-toggle-link");
    link.onclick = (e) => { e.preventDefault(); toggleAuthMode(); };
    form.onsubmit = async (e) => {
      e.preventDefault();
      const fd = new FormData(form);
      const btn = document.getElementById("auth-submit");
      const errBox = document.getElementById("auth-error");
      errBox.hidden = true;
      btn.disabled = true; btn.textContent = "…";
      try {
        const body = { email: fd.get("email"), password: fd.get("password") };
        let data;
        if (authMode === "register") { body.name = fd.get("name") || ""; data = await API.register(body); }
        else data = await API.login(body);
        API.setTokens(data.access_token, data.refresh_token);
        await enterApp();
      } catch (err) {
        errBox.textContent = err.message; errBox.hidden = false;
      } finally {
        btn.disabled = false; btn.textContent = authMode === "register" ? "Create account" : "Sign in";
      }
    };
  }
  function toggleAuthMode() {
    authMode = authMode === "login" ? "register" : "login";
    document.getElementById("name-field").hidden = authMode !== "register";
    document.getElementById("auth-submit").textContent = authMode === "register" ? "Create account" : "Sign in";
    document.getElementById("auth-toggle-text").textContent = authMode === "register" ? "Already have an account?" : "New here?";
    document.getElementById("auth-toggle-link").textContent = authMode === "register" ? "Sign in" : "Create an account";
  }
  function showAuth() {
    document.getElementById("auth-screen").hidden = false;
    document.getElementById("app").hidden = true;
  }

  async function enterApp() {
    state.user = await API.me();
    document.getElementById("auth-screen").hidden = true;
    document.getElementById("app").hidden = false;
    const initial = (state.user.name || state.user.email || "U")[0].toUpperCase();
    document.getElementById("avatar").textContent = initial;
    document.getElementById("user-name").textContent = state.user.name || state.user.email.split("@")[0];
    try { state.agents = (await API.agents()).agents; } catch { state.agents = []; }
    checkSystem();
    navigate("dashboard");
  }

  async function checkSystem() {
    try {
      const s = await API.status();
      const pill = document.getElementById("system-pill");
      const txt = document.getElementById("system-text");
      if (s.llm_available) { pill.classList.remove("offline"); txt.textContent = `${s.llm_providers.length} provider(s)`; }
      else { pill.classList.add("offline"); txt.textContent = "no LLM key"; }
    } catch {}
  }

  // ------------------------------------------------------------- shell
  function setupShell() {
    document.querySelectorAll(".nav-item").forEach((b) =>
      (b.onclick = () => navigate(b.dataset.view))
    );
    document.getElementById("logout-btn").onclick = () => { API.clearTokens(); location.reload(); };
    document.getElementById("menu-btn").onclick = () =>
      document.getElementById("sidebar").classList.toggle("open");
    setupCommandPalette();
  }

  const TITLES = {
    dashboard: "Dashboard", chat: "Chat", voice: "Voice", agents: "Agents",
    tasks: "Tasks & Projects", memory: "Memory", workflows: "Automations",
    analytics: "Analytics", settings: "Settings",
  };

  function navigate(view) {
    state.view = view;
    document.querySelectorAll(".nav-item").forEach((b) => b.classList.toggle("active", b.dataset.view === view));
    document.querySelectorAll(".view").forEach((v) => (v.hidden = v.id !== `view-${view}`));
    document.getElementById("view-title").textContent = TITLES[view] || view;
    document.getElementById("sidebar").classList.remove("open");
    RENDER[view] && RENDER[view]();
  }

  // ------------------------------------------------------------- renderers
  const RENDER = {};

  RENDER.dashboard = async () => {
    const v = document.getElementById("view-dashboard");
    const hour = new Date().getHours();
    const greetWord = hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
    const first = (state.user.name || "").split(" ")[0];
    v.innerHTML = `
      <div class="hero">
        <div class="orb" id="hero-orb">${orbMarkup()}</div>
        <div class="sub">At your service</div>
        <div class="greeting">“${greetWord}${first ? ", " + esc(first) : ""}. How may I help?”</div>
        <div class="chips" id="hero-chips"></div>
      </div>
      <div class="grid cols-4" id="stat-row"></div>
      <div class="grid cols-2" style="margin-top:16px">
        <div class="panel"><div class="section-title">Recent agent activity</div><div id="dash-runs"><div class="empty">Loading…</div></div></div>
        <div class="panel"><div class="section-title">Quick actions</div><div id="dash-actions"></div></div>
      </div>`;
    const chips = document.getElementById("hero-chips");
    [
      ["Brief me on today", "Give me a short briefing on my day: open tasks and top priorities."],
      ["Draft something", "Help me draft a message — ask me what it's for."],
      ["Do some research", "What would you like me to research?"],
      ["Plan a project", "Help me break a project into tasks."],
    ].forEach(([label, prompt]) => {
      const c = el(`<button class="chip-btn">${label}</button>`);
      c.onclick = () => { navigate("chat"); setTimeout(() => { const i = document.getElementById("composer-input"); if (i) { i.value = prompt; i.focus(); } }, 150); };
      chips.appendChild(c);
    });
    const actions = document.getElementById("dash-actions");
    [["chat", "Start a conversation"], ["voice", "Talk to JARVIS"], ["tasks", "Plan a project"], ["workflows", "Create an automation"]].forEach(([view, label]) => {
      const b = el(`<button class="btn" style="width:100%;justify-content:flex-start;margin-bottom:8px">${label}</button>`);
      b.onclick = () => navigate(view);
      actions.appendChild(b);
    });
    try {
      const o = await API.overview();
      const row = document.getElementById("stat-row");
      const cards = [
        ["Conversations", o.conversations, false], ["Memories", o.memories, true],
        ["Open tasks", o.open_tasks, false], ["Agent runs", o.agent_runs_total, true],
      ];
      row.innerHTML = cards.map(([l, n, a]) =>
        `<div class="panel stat"><div class="n ${a ? "accent" : ""}">${n}</div><div class="l">${l}</div></div>`
      ).join("");
      const runs = await API.agentRuns();
      const box = document.getElementById("dash-runs");
      box.innerHTML = runs.runs.length
        ? runs.runs.slice(0, 6).map((r) =>
            `<div class="row" style="padding:9px 0;border-bottom:1px solid var(--panel-border)">
               <span class="agent-badge" style="width:30px;height:30px;font-size:12px">${agentInitial(r.agent)}</span>
               <div style="flex:1;min-width:0"><div style="font-size:13px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(r.goal)}</div>
               <div class="muted" style="font-size:11px">${esc(agentName(r.agent))} · ${timeAgo(r.started_at)}</div></div>
               <span class="badge ${r.status}">${r.status}</span></div>`
          ).join("")
        : `<div class="empty">No activity yet. Start a conversation to see JARVIS at work.</div>`;
    } catch (e) { toast(e.message); }
  };

  // ---- Chat ----
  RENDER.chat = async () => {
    const v = document.getElementById("view-chat");
    if (!v.dataset.built) {
      v.innerHTML = `<div class="chat-wrap">
        <div style="display:flex;flex-direction:column;gap:10px;min-height:0">
          <button class="btn solid" id="new-chat"><i data-i="plus"></i>New chat</button>
          <div class="chat-list" id="chat-list"></div>
        </div>
        <div class="chat-main">
          <div class="messages" id="messages"></div>
          <div class="composer">
            <select class="agent-select" id="agent-select"></select>
            <textarea id="composer-input" rows="1" placeholder="Ask JARVIS anything…"></textarea>
            <button class="send-btn" id="send-btn"><i data-i="send"></i></button>
          </div>
        </div></div>`;
      v.dataset.built = "1";
      injectIcons(v);
      const sel = document.getElementById("agent-select");
      sel.innerHTML = `<option value="">Auto-route</option>` +
        state.agents.map((a) => `<option value="${a.key}">${esc(a.name)}</option>`).join("");
      document.getElementById("new-chat").onclick = () => { state.conversation = null; document.getElementById("messages").innerHTML = ""; renderConvos(); };
      const input = document.getElementById("composer-input");
      input.addEventListener("input", () => { input.style.height = "auto"; input.style.height = Math.min(input.scrollHeight, 160) + "px"; });
      input.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); } });
      document.getElementById("send-btn").onclick = sendMessage;
    }
    renderConvos();
  };

  async function renderConvos() {
    try {
      state.convos = await API.conversations();
      const list = document.getElementById("chat-list");
      if (!list) return;
      list.innerHTML = state.convos.map((c) =>
        `<div class="convo ${c.id === state.conversation ? "active" : ""}" data-id="${c.id}">${esc(c.title)}</div>`
      ).join("") || `<div class="muted" style="padding:8px">No conversations yet.</div>`;
      list.querySelectorAll(".convo").forEach((el2) => (el2.onclick = () => openConversation(el2.dataset.id)));
    } catch {}
  }

  async function openConversation(id) {
    state.conversation = id;
    renderConvos();
    const msgs = await API.messages(id);
    const box = document.getElementById("messages");
    box.innerHTML = "";
    msgs.forEach((m) => addMessage(m.role, m.content, m.agent));
    box.scrollTop = box.scrollHeight;
  }

  function addMessage(role, content, agent) {
    const box = document.getElementById("messages");
    const initial = role === "user" ? (state.user.name || "U")[0].toUpperCase() : "J";
    const label = role === "assistant" && agent && agent !== "orchestrator"
      ? `<div class="msg-agent-label">${esc(agentName(agent))}</div>` : "";
    const node = el(`<div class="msg ${role}"><div class="msg-avatar">${initial}</div>
      <div><div class="msg-bubble">${label}<span class="body">${role === "assistant" ? mdToHtml(content) : esc(content)}</span></div></div></div>`);
    box.appendChild(node);
    box.scrollTop = box.scrollHeight;
    return node.querySelector(".body");
  }

  let sending = false;
  async function sendMessage() {
    if (sending) return;
    const input = document.getElementById("composer-input");
    const text = input.value.trim();
    if (!text) return;
    const agent = document.getElementById("agent-select").value;
    input.value = ""; input.style.height = "auto";
    sending = true;
    document.getElementById("send-btn").disabled = true;
    addMessage("user", text);
    const box = document.getElementById("messages");
    const thinking = el(`<div class="msg assistant"><div class="msg-avatar">J</div><div><div class="thinking"><span class="spinner"></span><span id="think-text">Thinking…</span></div><div id="trace-box"></div></div></div>`);
    box.appendChild(thinking);
    box.scrollTop = box.scrollHeight;

    try {
      const res = await API.chatStream({ message: text, conversation_id: state.conversation, agent: agent || null });
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "", finalBody = null, finalAgent = agent;
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const events = buffer.split("\n\n");
        buffer = events.pop();
        for (const chunk of events) {
          const ev = parseSSE(chunk);
          if (!ev) continue;
          handleChatEvent(ev, thinking, (b, a) => { finalBody = b; finalAgent = a; });
        }
      }
      thinking.remove();
      const target = addMessage("assistant", finalBody || "(no response)", finalAgent);
      if (!state.conversation) renderConvos();
    } catch (e) {
      thinking.remove();
      addMessage("assistant", `⚠️ ${e.message}`);
    } finally {
      sending = false;
      document.getElementById("send-btn").disabled = false;
    }
  }

  function handleChatEvent(ev, thinking, setFinal) {
    const thinkText = thinking.querySelector("#think-text");
    const traceBox = thinking.querySelector("#trace-box");
    if (ev.event === "open" && ev.data.conversation_id) state.conversation = ev.data.conversation_id;
    else if (ev.event === "status" && thinkText) thinkText.textContent = ev.data.message || "Working…";
    else if (ev.event === "plan" && thinkText) {
      thinkText.textContent = ev.data.mode === "complex"
        ? `Planning ${(ev.data.tasks || []).length} steps…` : `Routing to ${agentName(ev.data.agent)}…`;
    } else if (ev.event === "task_start" && traceBox) {
      traceBox.appendChild(el(`<div class="trace">▸ ${esc(agentName(ev.data.agent))}: ${esc((ev.data.instruction || "").slice(0, 80))}</div>`));
    } else if (ev.event === "task_done" && traceBox) {
      traceBox.appendChild(el(`<div class="trace">✓ ${esc(agentName(ev.data.agent))} finished</div>`));
    } else if (ev.event === "final") {
      setFinal(ev.data.text, ev.data.agent);
    } else if (ev.event === "error" && thinkText) {
      thinkText.textContent = ev.data.message || "error";
    }
  }

  function parseSSE(chunk) {
    const lines = chunk.split("\n");
    let event = "message", data = "";
    for (const l of lines) {
      if (l.startsWith("event: ")) event = l.slice(7);
      else if (l.startsWith("data: ")) data += l.slice(6);
    }
    if (!data) return null;
    try { return { event, data: JSON.parse(data) }; } catch { return null; }
  }

  // ---- Voice ----
  RENDER.voice = async () => {
    const v = document.getElementById("view-voice");
    v.innerHTML = `<div class="voice-view">
      <div class="orb" id="voice-orb">${orbMarkup()}</div>
      <div class="voice-status" id="voice-status">Tap the orb and speak</div>
      <div class="voice-transcript" id="voice-transcript">“Good evening. How may I help?”</div>
    </div>`;
    setupVoice();
  };

  function setupVoice() {
    const orb = document.getElementById("voice-orb");
    const status = document.getElementById("voice-status");
    const transcript = document.getElementById("voice-transcript");
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) { status.textContent = "Your browser doesn't support speech recognition. Try Chrome/Edge."; }
    let listening = false, recog = null;

    orb.onclick = async () => {
      if (listening) { recog && recog.stop(); return; }
      if (!SR) { toast("Speech recognition unavailable in this browser."); return; }
      recog = new SR();
      recog.lang = "en-US"; recog.interimResults = true; recog.continuous = false;
      listening = true; orb.classList.add("listening"); status.textContent = "Listening…"; transcript.textContent = "";
      recog.onresult = (e) => {
        let text = "";
        for (const r of e.results) text += r[0].transcript;
        transcript.textContent = text;
      };
      recog.onerror = () => { status.textContent = "Didn't catch that. Tap to retry."; };
      recog.onend = async () => {
        listening = false; orb.classList.remove("listening");
        const text = transcript.textContent.trim();
        if (!text) { status.textContent = "Tap the orb and speak"; return; }
        status.textContent = "Thinking…";
        await voiceRespond(text, status, transcript);
      };
      recog.start();
    };
  }

  async function voiceRespond(text, status, transcript) {
    try {
      const res = await API.chatStream({ message: text, conversation_id: state.conversation, agent: null });
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "", final = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n"); buffer = parts.pop();
        for (const c of parts) { const ev = parseSSE(c); if (ev && ev.event === "final") final = ev.data.text; if (ev && ev.event === "open") state.conversation = ev.data.conversation_id; }
      }
      transcript.textContent = final;
      status.textContent = "Speaking…";
      await speak(final);
      status.textContent = "Tap the orb and speak";
    } catch (e) { status.textContent = e.message; }
  }

  async function speak(text) {
    try {
      const res = await API.tts({ text });
      if (res.ok) {
        const blob = await res.blob();
        const audio = new Audio(URL.createObjectURL(blob));
        await audio.play();
        return new Promise((r) => (audio.onended = r));
      }
    } catch {}
    // Fallback: browser speech synthesis.
    if (window.speechSynthesis) {
      const u = new SpeechSynthesisUtterance(text);
      window.speechSynthesis.speak(u);
      return new Promise((r) => (u.onend = r));
    }
  }

  // ---- Agents ----
  RENDER.agents = async () => {
    const v = document.getElementById("view-agents");
    v.innerHTML = `<div class="grid cols-3" id="agent-grid"></div>`;
    const grid = document.getElementById("agent-grid");
    grid.innerHTML = state.agents.map((a) =>
      `<div class="panel agent-card"><div class="head"><div class="agent-badge">${agentInitial(a.key)}</div><div><h4>${esc(a.name)}</h4></div></div>
       <div class="role">${esc(a.role)}</div>
       <div class="agent-tools">${a.tools.map((t) => `<span class="chip">${esc(t)}</span>`).join("")}</div></div>`
    ).join("");
  };

  // ---- Tasks ----
  RENDER.tasks = async () => {
    const v = document.getElementById("view-tasks");
    v.innerHTML = `<div class="row" style="margin-bottom:16px">
        <button class="btn solid" id="add-task"><i data-i="plus"></i>New task</button>
        <button class="btn" id="add-project"><i data-i="plus"></i>New project</button>
        <div class="spacer"></div><span class="muted" id="proj-count"></span></div>
      <div class="kanban" id="kanban"></div>`;
    injectIcons(v);
    document.getElementById("add-task").onclick = addTaskFlow;
    document.getElementById("add-project").onclick = addProjectFlow;
    await renderKanban();
    try { const p = await API.projects(); document.getElementById("proj-count").textContent = `${p.length} project(s)`; } catch {}
  };

  const COLS = [["todo", "To do"], ["in_progress", "In progress"], ["blocked", "Blocked"], ["done", "Done"]];
  async function renderKanban() {
    const tasks = await API.tasks();
    const kb = document.getElementById("kanban");
    kb.innerHTML = COLS.map(([key, label]) => {
      const items = tasks.filter((t) => t.status === key);
      return `<div class="kanban-col" data-status="${key}"><h4>${label}<span>${items.length}</span></h4>
        ${items.map(taskCard).join("") || '<div class="muted" style="font-size:12px">—</div>'}</div>`;
    }).join("");
    kb.querySelectorAll(".task-card").forEach((c) => {
      c.onclick = () => cycleTask(c.dataset.id, tasks.find((t) => t.id === c.dataset.id));
    });
  }
  function taskCard(t) {
    return `<div class="task-card" data-id="${t.id}"><div class="t">${esc(t.title)}</div>
      <div class="meta"><span class="prio p${t.priority}"></span>P${t.priority}${t.assignee_agent ? " · " + esc(agentName(t.assignee_agent)) : ""}</div></div>`;
  }
  async function cycleTask(id, t) {
    const order = ["todo", "in_progress", "blocked", "done"];
    const next = order[(order.indexOf(t.status) + 1) % order.length];
    await API.updateTask(id, { status: next });
    renderKanban();
  }
  async function addTaskFlow() {
    const title = prompt("Task title:");
    if (!title) return;
    const agentList = ["", ...state.agents.map((a) => a.key)];
    await API.addTask({ title, priority: 3 });
    toast("Task added");
    renderKanban();
  }
  async function addProjectFlow() {
    const name = prompt("Project name:");
    if (!name) return;
    await API.addProject({ name });
    toast("Project created");
    RENDER.tasks();
  }

  // ---- Memory ----
  RENDER.memory = async () => {
    const v = document.getElementById("view-memory");
    v.innerHTML = `<div class="row" style="margin-bottom:16px">
        <input class="field" style="flex:1;margin:0" id="mem-search" placeholder="Semantic search across your memory…"/>
        <button class="btn" id="mem-search-btn"><i data-i="search"></i>Search</button>
        <button class="btn solid" id="mem-add"><i data-i="plus"></i>Add</button>
        <button class="btn" id="mem-maint" title="Consolidate & reflect">Maintain</button></div>
      <div class="grid cols-4" id="mem-stats" style="margin-bottom:16px"></div>
      <div id="mem-list"></div>`;
    injectIcons(v);
    document.getElementById("mem-search-btn").onclick = doMemSearch;
    document.getElementById("mem-search").addEventListener("keydown", (e) => e.key === "Enter" && doMemSearch());
    document.getElementById("mem-add").onclick = async () => {
      const content = prompt("What should JARVIS remember?");
      if (!content) return;
      await API.addMemory({ content, kind: "fact" });
      toast("Memory saved"); RENDER.memory();
    };
    document.getElementById("mem-maint").onclick = async () => {
      toast("Running consolidation & reflection…");
      const r = await API.memoryMaintenance();
      toast(`Consolidated ${r.consolidated} memories`); RENDER.memory();
    };
    try {
      const stats = await API.memoryStats();
      document.getElementById("mem-stats").innerHTML =
        `<div class="panel stat"><div class="n accent">${stats.total}</div><div class="l">Total memories</div></div>` +
        Object.entries(stats.by_kind).slice(0, 3).map(([k, c]) =>
          `<div class="panel stat"><div class="n">${c}</div><div class="l">${esc(k)}</div></div>`).join("");
    } catch {}
    renderMemList(await API.memories());
  };
  async function doMemSearch() {
    const q = document.getElementById("mem-search").value.trim();
    if (!q) return renderMemList(await API.memories());
    const results = await API.searchMemory({ query: q, limit: 20 });
    renderMemList(results, true);
  }
  function renderMemList(items, scored) {
    const box = document.getElementById("mem-list");
    if (!items.length) { box.innerHTML = `<div class="empty">No memories yet. JARVIS learns as you talk to it.</div>`; return; }
    box.innerHTML = items.map((m) =>
      `<div class="mem-item"><div class="imp-bar"><span style="width:${Math.round(m.importance * 100)}%"></span></div>
        <div class="body"><div class="content">${esc(m.content)}</div>
        <div class="sub"><span class="tag">${esc(m.kind)}</span>${scored && m.score != null ? `<span>score ${m.score}</span>` : ""}<span>${timeAgo(m.created_at)}</span></div></div>
        <button class="icon-btn" data-del="${m.id}"><i data-i="trash"></i></button></div>`
    ).join("");
    injectIcons(box);
    box.querySelectorAll("[data-del]").forEach((b) => (b.onclick = async () => {
      await API.deleteMemory(b.dataset.del); RENDER.memory();
    }));
  }

  // ---- Workflows ----
  RENDER.workflows = async () => {
    const v = document.getElementById("view-workflows");
    v.innerHTML = `<div class="row" style="margin-bottom:16px"><button class="btn solid" id="wf-add"><i data-i="plus"></i>New automation</button>
      <div class="spacer"></div><span class="muted">Cron-scheduled autonomous workflows</span></div>
      <div id="wf-list"></div>`;
    injectIcons(v);
    document.getElementById("wf-add").onclick = addWorkflowFlow;
    const wfs = await API.workflows();
    const box = document.getElementById("wf-list");
    if (!wfs.length) { box.innerHTML = `<div class="empty">No automations yet. Create one to have JARVIS work while you're away — e.g. a daily briefing at 8am.</div>`; return; }
    box.innerHTML = wfs.map((w) =>
      `<div class="panel" style="margin-bottom:12px"><div class="row">
        <div style="flex:1"><h4 style="font-size:15px">${esc(w.name)}</h4>
        <div class="muted">${esc(w.description || w.prompt.slice(0, 80))}</div>
        <div class="sub" style="margin-top:6px"><span class="tag">${esc(w.schedule)}</span> <span class="tag">${esc(agentName(w.agent))}</span>
        ${w.next_run_at ? `<span class="muted" style="font-size:11px">next ${new Date(w.next_run_at + "Z").toLocaleString()}</span>` : ""}</div></div>
        <button class="btn" data-run="${w.id}"><i data-i="play"></i>Run</button>
        <button class="icon-btn" data-del="${w.id}"><i data-i="trash"></i></button></div></div>`
    ).join("");
    injectIcons(box);
    box.querySelectorAll("[data-run]").forEach((b) => (b.onclick = async () => {
      b.textContent = "Running…"; b.disabled = true;
      try { const r = await API.runWorkflow(b.dataset.run); toast("Workflow ran — check results"); alert(r.output.slice(0, 1200)); }
      catch (e) { toast(e.message); } finally { RENDER.workflows(); }
    }));
    box.querySelectorAll("[data-del]").forEach((b) => (b.onclick = async () => {
      await API.deleteWorkflow(b.dataset.del); RENDER.workflows();
    }));
  };
  async function addWorkflowFlow() {
    const name = prompt("Automation name (e.g. Morning briefing):");
    if (!name) return;
    const promptText = prompt("What should JARVIS do each run?", "Summarize my open tasks and suggest today's top 3 priorities.");
    if (!promptText) return;
    const schedule = prompt("Cron schedule (min hour dom mon dow), or 'manual':", "0 8 * * *") || "manual";
    try { await API.addWorkflow({ name, prompt: promptText, schedule, agent: "orchestrator" }); toast("Automation created"); RENDER.workflows(); }
    catch (e) { toast(e.message); }
  }

  // ---- Analytics ----
  RENDER.analytics = async () => {
    const v = document.getElementById("view-analytics");
    v.innerHTML = `<div class="grid cols-4" id="an-stats"></div>
      <div class="grid cols-2" style="margin-top:16px">
        <div class="panel"><div class="section-title">Agent utilization</div><div id="an-agents"></div></div>
        <div class="panel"><div class="section-title">Token & cost</div><div id="an-cost"></div></div></div>`;
    try {
      const o = await API.overview();
      document.getElementById("an-stats").innerHTML = [
        ["Total runs", o.agent_runs_total], ["This week", o.agent_runs_week],
        ["Tokens in", fmt(o.tokens_in)], ["Est. cost", "$" + o.total_cost_usd.toFixed(4)],
      ].map(([l, n]) => `<div class="panel stat"><div class="n accent">${n}</div><div class="l">${l}</div></div>`).join("");
      const act = await API.agentActivity();
      const max = Math.max(1, ...act.agents.map((a) => a.runs));
      document.getElementById("an-agents").innerHTML = act.agents.length
        ? act.agents.map((a) => `<div class="bar-row"><span class="label">${esc(agentName(a.agent))}</span>
            <div class="bar-track"><div class="bar-fill" style="width:${(a.runs / max) * 100}%"></div></div><span class="val">${a.runs}</span></div>`).join("")
        : `<div class="empty">No runs yet.</div>`;
      document.getElementById("an-cost").innerHTML =
        `<div class="stat" style="margin-bottom:14px"><div class="n">${fmt(o.tokens_in + o.tokens_out)}</div><div class="l">Total tokens processed</div></div>
         <div class="stat"><div class="n accent">$${o.total_cost_usd.toFixed(4)}</div><div class="l">Estimated spend across all providers</div></div>`;
    } catch (e) { toast(e.message); }
  };

  // ---- Settings ----
  RENDER.settings = async () => {
    const v = document.getElementById("view-settings");
    const s = await API.status().catch(() => ({}));
    v.innerHTML = `<div class="grid cols-2">
      <div class="panel"><div class="section-title">Account</div>
        <div class="field"><label>Name</label><input id="set-name" value="${esc(state.user.name)}"/></div>
        <div class="field"><label>Email</label><input value="${esc(state.user.email)}" disabled/></div>
        <div class="field"><label>Role</label><input value="${esc(state.user.role)}" disabled/></div>
        <button class="btn solid" id="save-account">Save</button></div>
      <div class="panel"><div class="section-title">System status</div>
        <table><tbody>
          <tr><td>Version</td><td>${esc(s.version || "—")}</td></tr>
          <tr><td>LLM providers</td><td>${(s.llm_providers || []).join(", ") || '<span style="color:var(--warn)">none configured</span>'}</td></tr>
          <tr><td>Embedding backend</td><td>${esc(s.embedding_backend || "—")}</td></tr>
          <tr><td>Voice (ElevenLabs)</td><td>${s.voice_configured ? "✓ configured" : "browser fallback"}</td></tr>
          <tr><td>Shell/code tools</td><td>${s.shell_enabled ? "enabled" : "disabled"}</td></tr>
        </tbody></table>
        <p class="muted" style="margin-top:12px">Configure provider keys via environment variables. See docs/ENVIRONMENT.md.</p></div>
    </div>`;
    document.getElementById("save-account").onclick = async () => {
      await API.savePrefs({ display_name: document.getElementById("set-name").value });
      toast("Saved");
    };
  };

  // ------------------------------------------------------------- command palette
  const COMMANDS = [
    ["Go to Dashboard", () => navigate("dashboard")],
    ["Go to Chat", () => navigate("chat")],
    ["Voice mode", () => navigate("voice")],
    ["View Agents", () => navigate("agents")],
    ["Tasks & Projects", () => navigate("tasks")],
    ["Memory browser", () => navigate("memory")],
    ["Automations", () => navigate("workflows")],
    ["Analytics", () => navigate("analytics")],
    ["Settings", () => navigate("settings")],
    ["Toggle theme", () => document.getElementById("theme-toggle").click()],
    ["Sign out", () => document.getElementById("logout-btn").click()],
  ];
  function setupCommandPalette() {
    const palette = document.getElementById("cmd-palette");
    const input = document.getElementById("cmd-input");
    const results = document.getElementById("cmd-results");
    let sel = 0;
    const open = () => { palette.hidden = false; input.value = ""; render(""); input.focus(); };
    const close = () => (palette.hidden = true);
    const render = (q) => {
      const matches = COMMANDS.filter(([l]) => l.toLowerCase().includes(q.toLowerCase()));
      sel = 0;
      results.innerHTML = matches.map(([l], i) => `<div class="cmd-result ${i === 0 ? "sel" : ""}" data-i="${i}">${esc(l)}</div>`).join("")
        || `<div class="cmd-result">Press Enter to ask JARVIS "${esc(q)}"</div>`;
      results.querySelectorAll(".cmd-result").forEach((r) => (r.onclick = () => { const m = matches[+r.dataset.i]; if (m) { m[1](); close(); } }));
      return matches;
    };
    document.getElementById("cmd-open").onclick = open;
    document.addEventListener("keydown", (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") { e.preventDefault(); palette.hidden ? open() : close(); }
      else if (!palette.hidden && e.key === "Escape") close();
    });
    input.addEventListener("input", () => render(input.value));
    input.addEventListener("keydown", (e) => {
      const items = results.querySelectorAll(".cmd-result");
      if (e.key === "ArrowDown") { sel = Math.min(sel + 1, items.length - 1); }
      else if (e.key === "ArrowUp") { sel = Math.max(sel - 1, 0); }
      else if (e.key === "Enter") {
        const q = input.value.trim();
        const matches = COMMANDS.filter(([l]) => l.toLowerCase().includes(q.toLowerCase()));
        if (matches[sel]) { matches[sel][1](); close(); }
        else if (q) { navigate("chat"); close(); setTimeout(() => { document.getElementById("composer-input").value = q; sendMessage(); }, 200); }
        return;
      } else return;
      items.forEach((it, i) => it.classList.toggle("sel", i === sel));
    });
    palette.addEventListener("click", (e) => { if (e.target === palette) close(); });
  }

  // ------------------------------------------------------------- utils
  function orbMarkup() {
    return `<div class="ring-pulse"></div><div class="ring-a"></div><div class="ring-b"></div>` +
      `<div class="core"><div class="wave"><i></i><i></i><i></i><i></i><i></i></div></div>`;
  }
  function agentName(key) { const a = state.agents.find((x) => x.key === key); return a ? a.name : (key === "orchestrator" ? "JARVIS" : key); }
  function agentInitial(key) { return agentName(key).replace(/Agent|Assistant/g, "").trim()[0] || "J"; }
  function fmt(n) { return n >= 1000 ? (n / 1000).toFixed(1) + "k" : String(n); }
})();
