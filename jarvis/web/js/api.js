/* JARVIS API client: token storage, auto-refresh, and typed helpers. */
const API = (() => {
  let access = localStorage.getItem("jarvis_access") || "";
  let refresh = localStorage.getItem("jarvis_refresh") || "";

  function setTokens(a, r) {
    access = a; refresh = r;
    localStorage.setItem("jarvis_access", a);
    localStorage.setItem("jarvis_refresh", r);
  }
  function clearTokens() {
    access = refresh = "";
    localStorage.removeItem("jarvis_access");
    localStorage.removeItem("jarvis_refresh");
  }
  function isAuthed() { return !!access; }

  async function raw(path, opts = {}, retry = true) {
    const headers = opts.headers || {};
    if (access) headers["authorization"] = `Bearer ${access}`;
    if (opts.body && !(opts.body instanceof FormData)) {
      headers["content-type"] = "application/json";
      opts.body = JSON.stringify(opts.body);
    }
    const res = await fetch(path, { ...opts, headers });
    if (res.status === 401 && retry && refresh) {
      const ok = await tryRefresh();
      if (ok) return raw(path, opts, false);
    }
    return res;
  }

  async function tryRefresh() {
    try {
      const res = await fetch("/api/auth/refresh", {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ refresh_token: refresh }),
      });
      if (!res.ok) { clearTokens(); return false; }
      const data = await res.json();
      setTokens(data.access_token, data.refresh_token);
      return true;
    } catch { return false; }
  }

  async function json(path, opts) {
    const res = await raw(path, opts);
    const data = res.status === 204 ? null : await res.json().catch(() => null);
    if (!res.ok) throw new Error((data && data.detail) || `Request failed (${res.status})`);
    return data;
  }

  return {
    isAuthed, setTokens, clearTokens, raw,
    getAccess: () => access,
    // auth
    register: (b) => json("/api/auth/register", { method: "POST", body: b }),
    login: (b) => json("/api/auth/login", { method: "POST", body: b }),
    me: () => json("/api/auth/me"),
    savePrefs: (preferences) => json("/api/auth/preferences", { method: "PUT", body: { preferences } }),
    // chat
    conversations: () => json("/api/chat/conversations"),
    messages: (id) => json(`/api/chat/conversations/${id}/messages`),
    deleteConversation: (id) => json(`/api/chat/conversations/${id}`, { method: "DELETE" }),
    chatStream: (b, signal) => raw("/api/chat/stream", { method: "POST", body: b, signal }),
    // agents
    agents: () => json("/api/agents"),
    agentRuns: () => json("/api/agents/runs"),
    // memory
    memories: (kind) => json(`/api/memory${kind ? `?kind=${kind}` : ""}`),
    memoryStats: () => json("/api/memory/stats"),
    addMemory: (b) => json("/api/memory", { method: "POST", body: b }),
    searchMemory: (b) => json("/api/memory/search", { method: "POST", body: b }),
    deleteMemory: (id) => json(`/api/memory/${id}`, { method: "DELETE" }),
    memoryMaintenance: () => json("/api/memory/maintenance", { method: "POST" }),
    // projects & tasks
    projects: () => json("/api/projects"),
    addProject: (b) => json("/api/projects", { method: "POST", body: b }),
    deleteProject: (id) => json(`/api/projects/${id}`, { method: "DELETE" }),
    tasks: (q = "") => json(`/api/tasks${q}`),
    addTask: (b) => json("/api/tasks", { method: "POST", body: b }),
    updateTask: (id, b) => json(`/api/tasks/${id}`, { method: "PATCH", body: b }),
    deleteTask: (id) => json(`/api/tasks/${id}`, { method: "DELETE" }),
    // workflows
    workflows: () => json("/api/workflows"),
    addWorkflow: (b) => json("/api/workflows", { method: "POST", body: b }),
    updateWorkflow: (id, b) => json(`/api/workflows/${id}`, { method: "PATCH", body: b }),
    deleteWorkflow: (id) => json(`/api/workflows/${id}`, { method: "DELETE" }),
    runWorkflow: (id) => json(`/api/workflows/${id}/run`, { method: "POST" }),
    workflowRuns: (id) => json(`/api/workflows/${id}/runs`),
    // voice
    voiceConfig: () => json("/api/voice/config"),
    tts: (b) => raw("/api/voice/tts", { method: "POST", body: b }),
    // vision (desktop screen analysis)
    analyzeScreen: (image, prompt) => json("/api/vision/analyze", { method: "POST", body: { image, prompt } }),
    // file upload + Q&A
    analyzeFile: async (file, prompt = "") => {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("prompt", prompt);
      const res = await raw("/api/files/analyze", { method: "POST", body: fd });
      const d = await res.json().catch(() => null);
      if (!res.ok) throw new Error((d && d.detail) || `Upload failed (${res.status})`);
      return d;
    },
    // computer control
    computerConfig: () => json("/api/computer/config"),
    computerStep: (messages, width, height) => json("/api/computer/step", { method: "POST", body: { messages, width, height } }),
    // connections
    connections: () => json("/api/connections"),
    connectAuthorize: (provider) => json(`/api/connections/${provider}/authorize`),
    disconnect: (provider) => json(`/api/connections/${provider}`, { method: "DELETE" }),
    // analytics
    overview: () => json("/api/analytics/overview"),
    agentActivity: () => json("/api/analytics/agent-activity"),
    status: () => json("/api/analytics/status"),
  };
})();
