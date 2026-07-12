/* UI helpers: SVG icon injection, DOM builders, toast, escaping. */
const ICONS = {
  grid: "M3 3h7v7H3zM14 3h7v7h-7zM14 14h7v7h-7zM3 14h7v7H3z",
  chat: "M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z",
  mic: "M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3zM19 10v2a7 7 0 0 1-14 0v-2M12 19v4M8 23h8",
  agents: "M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75",
  check: "M9 11l3 3L22 4M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11",
  brain: "M12 2a4 4 0 0 0-4 4 4 4 0 0 0-2 7 3 3 0 0 0 2 5 3 3 0 0 0 4 1 3 3 0 0 0 4-1 3 3 0 0 0 2-5 4 4 0 0 0-2-7 4 4 0 0 0-4-4zM12 2v20",
  bolt: "M13 2L3 14h9l-1 8 10-12h-9z",
  chart: "M3 3v18h18M18 17V9M13 17V5M8 17v-4",
  gear: "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z",
  cmd: "M6 4h4v4H6zM14 4h4v4h-4zM6 12h4v4H6zM14 12h4v4h-4z",
  moon: "M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z",
  menu: "M3 6h18M3 12h18M3 18h18",
  logout: "M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9",
  send: "M22 2L11 13M22 2l-7 20-4-9-9-4z",
  plus: "M12 5v14M5 12h14",
  trash: "M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2m3 0v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6",
  play: "M5 3l14 9-14 9z",
  search: "M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16zM21 21l-4.35-4.35",
  speaker: "M11 5L6 9H2v6h4l5 4V5zM15.54 8.46a5 5 0 0 1 0 7.07M19.07 4.93a10 10 0 0 1 0 14.14",
  speakermute: "M11 5L6 9H2v6h4l5 4V5zM23 9l-6 6M17 9l6 6",
  micmute: "M1 1l22 22M9 9v3a3 3 0 0 0 5.12 2.12M15 9.34V5a3 3 0 0 0-6-.34M17 16.95A7 7 0 0 1 5 12v-1M12 19v3",
};

function icon(name, size = 20) {
  const d = ICONS[name] || "";
  const svg = encodeURIComponent(
    `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='${d}'/></svg>`
  );
  return `width:${size}px;height:${size}px;-webkit-mask-image:url("data:image/svg+xml,${svg}");mask-image:url("data:image/svg+xml,${svg}")`;
}

function injectIcons(root = document) {
  root.querySelectorAll("i[data-i]").forEach((el) => {
    el.style.cssText = icon(el.dataset.i, el.closest(".nav-item, .msg") ? 20 : 18);
  });
}

function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );
}

function el(html) {
  const t = document.createElement("template");
  t.innerHTML = html.trim();
  return t.content.firstElementChild;
}

let toastTimer;
function toast(msg, ms = 2600) {
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (t.hidden = true), ms);
}

function timeAgo(iso) {
  if (!iso) return "—";
  const s = (Date.now() - new Date(iso + (iso.endsWith("Z") ? "" : "Z")).getTime()) / 1000;
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

// Remove any internal tool-call syntax a model may have leaked into its reply
// (e.g. <function_calls>…</function_calls> or a bare {"tool":…} object).
function stripToolArtifacts(text) {
  let t = String(text == null ? "" : text);
  t = t.replace(/<function_calls>[\s\S]*?<\/function_calls>/gi, " ");
  t = t.replace(/<\/?(?:function_calls|function_call|function_results|invoke|parameter)\b[^>]*>/gi, " ");
  t = t.replace(/```(?:json)?\s*\{[\s\S]*?"(?:tool|final)"[\s\S]*?\}\s*```/gi, " ");
  t = t.replace(/\{[^{}]*?"(?:tool|final)"\s*:[\s\S]*?\}/g, " ");
  return t;
}

// Strip markdown symbols, emojis, and URLs so text-to-speech reads the words
// only — not "asterisk asterisk" or emoji/pictograph characters.
function cleanForSpeech(text) {
  let t = stripToolArtifacts(String(text == null ? "" : text));
  t = t.replace(/```[\s\S]*?```/g, " ");          // code blocks
  t = t.replace(/`([^`]+)`/g, "$1");               // inline code
  t = t.replace(/https?:\/\/\S+/g, " ");           // urls
  t = t.replace(/^\s*#{1,6}\s*/gm, "");            // headings
  t = t.replace(/^\s*[-*•]\s+/gm, "");             // list bullets
  t = t.replace(/[*_#>|~`]/g, " ");                // stray markdown symbols
  // Emoji & pictographs (common unicode blocks) and variation selectors.
  t = t.replace(
    /[\u{1F000}-\u{1FAFF}\u{1F300}-\u{1F9FF}\u{2600}-\u{27BF}\u{2190}-\u{21FF}\u{2B00}-\u{2BFF}\u{FE0F}\u{200D}]/gu,
    ""
  );
  return t.replace(/\s+/g, " ").trim();
}

// Minimal, safe markdown: bold, italics, inline code, code blocks, lists.
function mdToHtml(text) {
  let h = esc(stripToolArtifacts(text));
  h = h.replace(/```([\s\S]*?)```/g, (_, c) => `<pre style="background:var(--input-bg);padding:12px;border-radius:8px;overflow-x:auto;font-family:var(--mono);font-size:12.5px;margin:8px 0">${c.trim()}</pre>`);
  h = h.replace(/`([^`]+)`/g, '<code style="background:var(--input-bg);padding:1px 5px;border-radius:4px;font-family:var(--mono);font-size:0.9em">$1</code>');
  h = h.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  h = h.replace(/(^|\s)\*([^*\n]+)\*/g, "$1<em>$2</em>");
  h = h.replace(/^### (.+)$/gm, '<h4 style="margin:10px 0 4px">$1</h4>');
  h = h.replace(/^## (.+)$/gm, '<h3 style="margin:12px 0 6px">$1</h3>');
  h = h.replace(/^# (.+)$/gm, '<h3 style="margin:12px 0 6px;font-family:var(--serif);font-size:22px">$1</h3>');
  h = h.replace(/^[-*] (.+)$/gm, "<li>$1</li>");
  h = h.replace(/(<li>[\s\S]*?<\/li>)/g, '<ul style="margin:6px 0 6px 18px">$1</ul>');
  return h;
}
