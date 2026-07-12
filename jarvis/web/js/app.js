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
    setupScreenVision();
    navigate("dashboard");
  }

  // ---- Screen vision: "let JARVIS look at my screen" ----------------------
  function screenCaptureAvailable() {
    return !!(window.jarvisDesktop && window.jarvisDesktop.isDesktop) ||
      !!(navigator.mediaDevices && navigator.mediaDevices.getDisplayMedia);
  }

  function setupScreenVision() {
    if (!screenCaptureAvailable()) return;
    if (window.jarvisDesktop && window.jarvisDesktop.isDesktop) document.body.classList.add("is-desktop");
    if (document.getElementById("screen-eye")) return;
    const btn = el(`<button id="screen-eye" title="Let JARVIS look at your screen">👁</button>`);
    document.body.appendChild(btn);
    btn.onclick = lookAtScreen;
  }

  async function captureScreen() {
    if (window.jarvisDesktop && window.jarvisDesktop.isDesktop) {
      return window.jarvisDesktop.captureScreen(); // instant, silent
    }
    // Browser fallback: the user picks a screen/window to share.
    const stream = await navigator.mediaDevices.getDisplayMedia({ video: true });
    const video = document.createElement("video");
    video.srcObject = stream;
    await video.play();
    await new Promise((r) => setTimeout(r, 200));
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth; canvas.height = video.videoHeight;
    canvas.getContext("2d").drawImage(video, 0, 0);
    stream.getTracks().forEach((t) => t.stop());
    return canvas.toDataURL("image/png");
  }

  let looking = false;
  async function lookAtScreen() {
    if (looking) return;
    looking = true;
    const btn = document.getElementById("screen-eye");
    if (btn) btn.classList.add("busy");
    try {
      unlockAudio();
      toast("Looking at your screen…", 2000);
      const img = await captureScreen();
      if (!img) { toast("Couldn't capture the screen."); return; }
      const { text } = await API.analyzeScreen(img, "");
      showScreenResult(text);
      try { await speak(text); } catch (e) {}
    } catch (e) {
      toast(e && e.message ? e.message : "Screen analysis failed.", 4000);
    } finally {
      looking = false;
      const b = document.getElementById("screen-eye");
      if (b) b.classList.remove("busy");
    }
  }

  function showScreenResult(text) {
    const old = document.getElementById("screen-modal");
    if (old) old.remove();
    const m = el(
      `<div id="screen-modal"><div class="sm-card">` +
      `<div class="sm-head"><span>👁 What JARVIS sees</span><button id="sm-close">✕</button></div>` +
      `<div class="sm-body">${mdToHtml(text)}</div></div></div>`
    );
    document.body.appendChild(m);
    document.getElementById("sm-close").onclick = () => m.remove();
    m.onclick = (e) => { if (e.target === m) m.remove(); };
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
    if (state.view === "voice" && view !== "voice") stopVoiceEngine();
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
  // Wake words JARVIS listens for in hands-free mode (English + Arabic + common
  // mis-hearings). Matched case-insensitively as whole/near words.
  const WAKE_WORDS = [
    "jarvis", "hey jarvis", "ok jarvis", "hi jarvis", "jervis", "jarvous",
    "travis", "جارفيس", "جارفس", "يا جارفيس", "هاي جارفيس",
  ];

  RENDER.voice = async () => {
    const v = document.getElementById("view-voice");
    v.innerHTML = `<div class="voice-view">
      <div class="orb" id="voice-orb">${orbMarkup()}</div>
      <div class="voice-status" id="voice-status">Tap the orb to talk — or turn on hands-free</div>
      <div class="voice-transcript" id="voice-transcript">“Good evening. How may I help?”</div>
      <button class="btn" id="handsfree-toggle" style="margin-top:6px"><i data-i="mic"></i><span>Enable hands-free — say “Jarvis”</span></button>
    </div>`;
    injectIcons(v);
    setupVoice();
  };

  // Stops any active microphone when leaving the Voice view. Set by setupVoice.
  let stopVoiceEngine = () => {};

  function setupVoice() {
    const orb = document.getElementById("voice-orb");
    const status = document.getElementById("voice-status");
    const transcript = document.getElementById("voice-transcript");
    const toggle = document.getElementById("handsfree-toggle");
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) {
      status.textContent = "Your browser doesn't support voice. Try Chrome or Edge.";
      if (toggle) toggle.style.display = "none";
      return;
    }

    const langName = (state.user.preferences || {}).response_language || "English";
    const recLang = SPEECH_LANG[langName] || "en-US";
    const idleText = "Tap the orb to talk — or turn on hands-free";
    const waitText = "Listening… say “Jarvis”";

    const eng = { mode: "off", handsFree: false, speaking: false, recog: null, restart: null };
    stopVoiceEngine = () => {
      eng.handsFree = false; eng.mode = "off"; eng.speaking = false;
      clearTimeout(eng.restart);
      try { eng.recog && eng.recog.abort(); } catch (e) {}
      orb.classList.remove("listening");
    };

    const setStatus = (t) => (status.textContent = t);

    function wakeIndex(text) {
      const t = " " + text.toLowerCase().replace(/[.,!؟?،]/g, " ").replace(/\s+/g, " ") + " ";
      for (const w of WAKE_WORDS) {
        const i = t.indexOf(" " + w + " ");
        if (i >= 0) return i + 1 + w.length;
      }
      for (const w of WAKE_WORDS) {
        const i = t.indexOf(w);
        if (i >= 0) return i + w.length;
      }
      return -1;
    }

    function newRecog(continuous) {
      const r = new SR();
      r.lang = recLang; r.interimResults = true; r.continuous = continuous;
      return r;
    }

    function startWaiting() {
      if (eng.recog) { try { eng.recog.abort(); } catch (e) {} }
      const r = newRecog(true);
      eng.recog = r;
      r.onresult = (ev) => {
        if (eng.mode !== "waiting" && eng.mode !== "capturing") return;
        let finalText = "", interim = "";
        for (const res of ev.results) (res.isFinal ? (finalText += res[0].transcript) : (interim += res[0].transcript));
        const combined = (finalText + " " + interim).trim();
        if (eng.mode === "waiting") {
          const idx = wakeIndex(combined);
          if (idx >= 0) {
            const after = combined.slice(idx).trim();
            orb.classList.add("listening");
            if (after.replace(/[^\p{L}\p{N}]/gu, "").length >= 2) { handle(after); }
            else { eng.mode = "capturing"; setStatus("نعم؟ · Yes? I’m listening…"); }
          }
        } else if (eng.mode === "capturing" && finalText.trim().replace(/[^\p{L}\p{N}]/gu, "").length >= 2) {
          handle(finalText.trim());
        }
      };
      r.onerror = (ev) => {
        // Mic permission blocked — stop hands-free entirely, don't loop.
        if (ev && (ev.error === "not-allowed" || ev.error === "service-not-allowed")) {
          stopVoiceEngine();
          toggle.classList.remove("solid");
          toggle.querySelector("span").textContent = "Enable hands-free — say “Jarvis”";
          setStatus("Microphone blocked. Allow mic access, then try again.");
          return;
        }
        // Transient errors (no-speech, network, aborted): back off, then retry.
        eng.backoff = Math.min((eng.backoff || 300) * 2, 5000);
      };
      r.onend = () => {
        if ((eng.mode === "waiting" || eng.mode === "capturing") && !eng.speaking) {
          clearTimeout(eng.restart);
          // Chrome ends continuous sessions periodically; restart with backoff.
          const delay = eng.backoff || 350;
          eng.restart = setTimeout(() => { eng.backoff = 300; startWaiting(); }, delay);
        }
      };
      try { r.start(); } catch (e) {}
    }

    async function handle(command) {
      eng.mode = "busy";
      try { eng.recog && eng.recog.stop(); } catch (e) {}
      orb.classList.add("listening");
      transcript.textContent = command;
      setStatus("Thinking…");
      try {
        const final = await streamChat(command);
        transcript.innerHTML = mdToHtml(final);
        setStatus("Speaking…");
        eng.speaking = true;
        await speak(final);
      } catch (e) { setStatus(e.message || "Something went wrong."); }
      eng.speaking = false;
      orb.classList.remove("listening");
      if (eng.handsFree) { eng.mode = "waiting"; setStatus(waitText); startWaiting(); }
      else { eng.mode = "off"; setStatus(idleText); }
    }

    // Tap-to-talk (single utterance) — always available.
    orb.onclick = () => {
      unlockAudio();
      if (eng.handsFree || eng.mode === "busy") return;
      eng.mode = "capturing-tap"; orb.classList.add("listening"); setStatus("Listening…"); transcript.textContent = "";
      const r = newRecog(false);
      let text = "";
      r.onresult = (e) => { text = ""; for (const res of e.results) text += res[0].transcript; transcript.textContent = text; };
      r.onerror = () => {};
      r.onend = () => {
        orb.classList.remove("listening");
        const t = text.trim();
        if (!t) { eng.mode = "off"; setStatus(idleText); return; }
        handle(t);
      };
      try { r.start(); } catch (e) {}
    };

    // Hands-free toggle.
    toggle.onclick = () => {
      unlockAudio(); // gesture unlocks audio so replies can auto-play
      eng.handsFree = !eng.handsFree;
      const label = toggle.querySelector("span");
      if (eng.handsFree) {
        eng.mode = "waiting"; toggle.classList.add("solid");
        label.textContent = "Hands-free is ON — say “Jarvis”";
        setStatus(waitText); startWaiting();
      } else {
        stopVoiceEngine();
        toggle.classList.remove("solid");
        label.textContent = "Enable hands-free — say “Jarvis”";
        setStatus(idleText);
      }
    };
  }

  async function streamChat(message) {
    const res = await API.chatStream({ message, conversation_id: state.conversation, agent: null });
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "", final = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split("\n\n"); buffer = parts.pop();
      for (const c of parts) {
        const ev = parseSSE(c);
        if (ev && ev.event === "final") final = ev.data.text;
        if (ev && ev.event === "open") state.conversation = ev.data.conversation_id;
      }
    }
    return final;
  }

  // --- audio playback (unlocked on a user tap so ElevenLabs can auto-play) ---
  const SILENT_WAV = "data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAgD4AAAB9AAACABAAZGF0YQAAAAA=";
  const SPEECH_LANG = {
    English: "en-US", Arabic: "ar-SA", French: "fr-FR", Spanish: "es-ES",
    German: "de-DE", Italian: "it-IT", Portuguese: "pt-PT", Hindi: "hi-IN",
    Urdu: "ur-PK", Turkish: "tr-TR", Russian: "ru-RU", Chinese: "zh-CN",
    Japanese: "ja-JP", Korean: "ko-KR", Dutch: "nl-NL",
  };
  let voiceAudio = null;
  function unlockAudio() {
    if (!voiceAudio) voiceAudio = new Audio();
    try { voiceAudio.src = SILENT_WAV; voiceAudio.play().catch(() => {}); } catch (e) {}
  }

  async function speak(text) {
    const clean = cleanForSpeech(text);
    if (!clean) return;
    try {
      const res = await API.tts({ text: clean });
      if (res.ok) {
        const blob = await res.blob();
        if (blob && blob.size > 0) {
          if (!voiceAudio) voiceAudio = new Audio();
          voiceAudio.src = URL.createObjectURL(blob);
          await voiceAudio.play();
          return new Promise((r) => (voiceAudio.onended = r));
        }
      } else {
        let detail = "";
        try { detail = (await res.json()).detail || ""; } catch {}
        toast("Voice: " + (detail || "TTS unavailable (" + res.status + ")") + " — using browser voice.", 5000);
      }
    } catch (e) { /* fall through to browser speech */ }
    // Fallback: browser speech synthesis, in the user's chosen language.
    if (window.speechSynthesis) {
      const u = new SpeechSynthesisUtterance(clean);
      const langName = (state.user.preferences || {}).response_language || "English";
      u.lang = SPEECH_LANG[langName] || "en-US";
      const match = window.speechSynthesis.getVoices().find((v) => v.lang && v.lang.startsWith(u.lang.split("-")[0]));
      if (match) u.voice = match;
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
        <div class="field"><label>Response language — JARVIS always replies (and speaks) in this</label>
          <select id="set-lang">${LANGUAGES.map((l) => `<option ${((state.user.preferences || {}).response_language || "English") === l ? "selected" : ""}>${l}</option>`).join("")}</select></div>
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
    </div>
    <div class="panel" style="margin-top:16px">
      <div class="section-title">Connections — your accounts</div>
      <div class="muted" style="margin-bottom:14px">Link accounts so JARVIS can act on them. Weather &amp; news work with no setup.</div>
      <div id="conn-list"><div class="muted">Loading…</div></div>
    </div>`;
    document.getElementById("save-account").onclick = async () => {
      const updated = await API.savePrefs({
        display_name: document.getElementById("set-name").value,
        response_language: document.getElementById("set-lang").value,
      });
      state.user = updated;
      toast("Saved — JARVIS will reply in " + updated.preferences.response_language + ".");
    };
    renderConnections();
  };

  async function renderConnections() {
    const box = document.getElementById("conn-list");
    if (!box) return;
    try {
      const { connections } = await API.connections();
      box.innerHTML = connections.map((c) => `
        <div class="row" style="padding:12px 0;border-bottom:1px solid var(--border-soft)">
          <div style="flex:1">
            <div style="font-size:15px">${esc(c.name)}
              ${c.connected ? `<span class="tag" style="margin-left:8px">connected${c.account ? " · " + esc(c.account) : ""}</span>` : ""}</div>
            ${!c.configured ? `<div class="muted" style="font-size:12px;margin-top:3px">Needs one-time server setup — see the Integrations guide.</div>` : ""}
          </div>
          ${c.connected
            ? `<button class="btn danger" data-disc="${c.provider}">Disconnect</button>`
            : `<button class="btn ${c.configured ? "solid" : ""}" data-conn="${c.provider}" ${c.configured ? "" : "disabled"}>Connect</button>`}
        </div>`).join("");
      box.querySelectorAll("[data-conn]").forEach((b) => (b.onclick = () => connectAccount(b.dataset.conn)));
      box.querySelectorAll("[data-disc]").forEach((b) => (b.onclick = async () => {
        await API.disconnect(b.dataset.disc); toast("Disconnected"); renderConnections();
      }));
    } catch (e) { box.innerHTML = `<div class="muted">${esc(e.message)}</div>`; }
  }

  async function connectAccount(provider) {
    try {
      const { url, error } = await API.connectAuthorize(provider);
      if (error) { toast(error, 5000); return; }
      // Open the provider's consent screen; user returns and we refresh.
      window.open(url, "jarvis_oauth", "width=520,height=680");
      toast("Approve access in the popup, then come back.", 5000);
      // Poll for connection completion for a short while.
      let tries = 0;
      const iv = setInterval(async () => {
        tries++;
        const { connections } = await API.connections();
        if (connections.find((c) => c.provider === provider && c.connected) || tries > 40) {
          clearInterval(iv); renderConnections();
        }
      }, 3000);
    } catch (e) { toast(e.message); }
  }

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
  const LANGUAGES = [
    "English", "Arabic", "French", "Spanish", "German", "Italian",
    "Portuguese", "Hindi", "Urdu", "Turkish", "Russian", "Chinese",
    "Japanese", "Korean", "Dutch",
  ];
  function orbMarkup() {
    return `<div class="ring-pulse"></div><div class="ring-a"></div><div class="ring-b"></div>` +
      `<div class="core"><div class="wave"><i></i><i></i><i></i><i></i><i></i></div></div>`;
  }
  function agentName(key) { const a = state.agents.find((x) => x.key === key); return a ? a.name : (key === "orchestrator" ? "JARVIS" : key); }
  function agentInitial(key) { return agentName(key).replace(/Agent|Assistant/g, "").trim()[0] || "J"; }
  function fmt(n) { return n >= 1000 ? (n / 1000).toFixed(1) + "k" : String(n); }
})();
