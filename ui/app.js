/**
 * HDFC Scheme Terminal — interactive chat client
 */

const EXAMPLE_QUESTIONS = [
  "What is the expense ratio of HDFC Mid Cap Fund Direct Growth?",
  "What is the exit load on HDFC Defence Fund Direct Growth?",
  "Who manages HDFC Gold ETF Fund of Fund Direct Plan Growth?",
];

const TICKER_LABELS = [
  "HDFC MID CAP",
  "HDFC LARGE CAP",
  "HDFC SMALL CAP",
  "HDFC GOLD ETF FOF",
  "HDFC DEFENCE",
  "NIFTY 50",
  "SENSEX",
];

const API_BASE = (window.API_BASE || "").replace(/\/$/, "");

function apiUrl(path) {
  return `${API_BASE}${path}`;
}

async function parseErrorResponse(response) {
  const fallback = `Request failed (${response.status}). Try again.`;
  try {
    const err = await response.json();
    if (typeof err.detail === "string") return err.detail;
    if (Array.isArray(err.detail)) return err.detail.map((d) => d.msg || String(d)).join("; ");
    if (err.message) return err.message;
    return fallback;
  } catch (_) {
    return fallback;
  }
}

const elements = {
  messages: document.getElementById("messages"),
  welcome: document.getElementById("welcome-panel"),
  form: document.getElementById("chat-form"),
  input: document.getElementById("message-input"),
  sendBtn: document.getElementById("send-btn"),
  examples: document.getElementById("example-questions"),
  errorBanner: document.getElementById("error-banner"),
  schemeList: document.getElementById("scheme-list"),
  schemeCount: document.getElementById("scheme-count"),
  ticker: document.getElementById("ticker"),
  clock: document.getElementById("market-clock"),
  activeLabel: document.getElementById("active-scheme-label"),
  quickActions: document.getElementById("quick-actions"),
};

let schemes = [];
let activeScheme = null;

function hideWelcome() {
  elements.welcome?.classList.add("hidden");
}

function showError(message) {
  if (!elements.errorBanner) return;
  elements.errorBanner.textContent = message;
  elements.errorBanner.classList.remove("hidden");
}

function clearError() {
  if (!elements.errorBanner) return;
  elements.errorBanner.textContent = "";
  elements.errorBanner.classList.add("hidden");
}

function setLoading(isLoading) {
  elements.sendBtn.disabled = isLoading;
  elements.input.disabled = isLoading;
  elements.sendBtn.setAttribute("aria-busy", isLoading ? "true" : "false");
  elements.sendBtn.querySelector(".send-label")?.classList.toggle("hidden", isLoading);
  elements.sendBtn.querySelector(".send-loading")?.classList.toggle("hidden", !isLoading);
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

function formatAnswer(text) {
  return escapeHtml(text).replace(/\n/g, "<br />");
}

function shortName(name) {
  return name.replace("HDFC ", "").replace(" Direct Growth", "").replace(" Direct Plan Growth", "");
}

function setActiveScheme(scheme) {
  activeScheme = scheme;
  document.querySelectorAll(".scheme-card").forEach((el) => {
    el.classList.toggle("active", el.dataset.slug === scheme?.slug);
  });
  if (scheme && elements.activeLabel) {
    elements.activeLabel.textContent = shortName(scheme.scheme_name);
    elements.activeLabel.classList.add("text-terminal-green");
  }
  elements.quickActions?.classList.toggle("hidden", !scheme);
}

function buildQueryForScheme(scheme, topic) {
  return `What is the ${topic} of ${scheme.scheme_name}?`;
}

function appendMessage(role, contentHtml) {
  hideWelcome();
  const article = document.createElement("article");
  article.className = role === "user" ? "flex justify-end animate-fade-in" : "flex justify-start animate-fade-in";
  const bubbleClass = role === "user" ? "chat-bubble-user" : "chat-bubble-assistant";
  article.innerHTML = `<div class="${bubbleClass} max-w-[92%] md:max-w-[80%] text-sm">${contentHtml}</div>`;
  elements.messages.appendChild(article);
  elements.messages.scrollTop = elements.messages.scrollHeight;
}

function appendUserMessage(text) {
  appendMessage("user", `<p class="font-mono text-sm leading-relaxed">${formatAnswer(text)}</p>`);
}

function appendAssistantMessage(data) {
  const refusalClass = data.is_refusal ? " refusal-card" : "";
  const badge = data.is_refusal
    ? `<span class="inline-flex items-center gap-1 text-[10px] uppercase tracking-wide text-red-400 bg-red-950/50 border border-red-800 px-2 py-0.5 rounded mb-2 font-mono">Refusal</span>`
    : `<span class="inline-flex items-center gap-1 text-[10px] uppercase tracking-wide text-terminal-green bg-green-950/40 border border-green-800/50 px-2 py-0.5 rounded mb-2 font-mono">Verified fact</span>`;

  const citation = data.citation_url
    ? `<a href="${escapeHtml(data.citation_url)}" target="_blank" rel="noopener noreferrer"
          class="inline-flex items-center gap-1 text-terminal-accent hover:text-blue-400 text-xs font-mono mt-3 transition-colors">
         <span class="material-symbols-outlined text-sm">open_in_new</span> Source
       </a>`
    : "";

  const footer = data.last_updated
    ? `<p class="text-[10px] font-mono text-terminal-muted mt-2">Updated ${escapeHtml(data.last_updated)}</p>`
    : "";

  appendMessage(
    "assistant",
    `<div class="${refusalClass}">${badge}
       <p class="leading-relaxed text-terminal-text">${formatAnswer(data.answer)}</p>
       ${citation}${footer}
     </div>`
  );
}

function appendTypingIndicator() {
  hideWelcome();
  const el = document.createElement("article");
  el.id = "typing-indicator";
  el.className = "flex justify-start animate-fade-in";
  el.innerHTML = `
    <div class="chat-bubble-assistant flex items-center gap-2 px-4 py-3">
      <span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span>
      <span class="text-xs font-mono text-terminal-muted ml-1">Analyzing…</span>
    </div>`;
  elements.messages.appendChild(el);
  elements.messages.scrollTop = elements.messages.scrollHeight;
}

function removeTypingIndicator() {
  document.getElementById("typing-indicator")?.remove();
}

async function sendMessage(text) {
  const message = text.trim();
  if (!message) return;

  clearError();
  appendUserMessage(message);
  elements.input.value = "";
  autoResizeInput();
  setLoading(true);
  appendTypingIndicator();

  try {
    const response = await fetch(apiUrl("/api/chat"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });

    removeTypingIndicator();

    if (!response.ok) {
      let detail = await parseErrorResponse(response);
      if (response.status === 429) detail = "Rate limit hit. Wait a moment.";
      if (response.status === 404 && !API_BASE) {
        detail = "API not connected. Set RAILWAY_API_URL on Vercel and redeploy.";
      }
      showError(detail);
      appendMessage("assistant", `<p class="text-red-400 font-mono text-sm">${escapeHtml(detail)}</p>`);
      return;
    }

    appendAssistantMessage(await response.json());
  } catch (_) {
    removeTypingIndicator();
    const detail = API_BASE
      ? "Server unreachable. Check Railway is running."
      : "Server unreachable. Set RAILWAY_API_URL on Vercel and redeploy.";
    showError(detail);
    appendMessage("assistant", `<p class="text-red-400 font-mono text-sm">${escapeHtml(detail)}</p>`);
  } finally {
    setLoading(false);
    elements.input.focus();
  }
}

function initExamples() {
  if (!elements.examples) return;
  EXAMPLE_QUESTIONS.forEach((question, i) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className =
      "example-chip group text-left text-sm px-3 py-2.5 rounded-lg border border-terminal-border bg-terminal-bg hover:border-terminal-accent hover:bg-blue-950/30 transition-all font-mono";
    const icons = ["payments", "logout", "groups"];
    btn.innerHTML = `
      <span class="flex items-center gap-2">
        <span class="material-symbols-outlined text-terminal-accent text-base group-hover:scale-110 transition-transform">${icons[i] || "help"}</span>
        <span class="text-terminal-muted group-hover:text-terminal-text">${escapeHtml(question)}</span>
      </span>`;
    btn.addEventListener("click", () => sendMessage(question));
    elements.examples.appendChild(btn);
  });
}

function renderSchemeCard(scheme, index) {
  const card = document.createElement("button");
  card.type = "button";
  card.dataset.slug = scheme.slug;
  card.className =
    "scheme-card w-full text-left rounded-lg border border-terminal-border bg-terminal-card p-3";
  const sparkSeed = (index + 1) * 17;
  const pseudoChange = ((sparkSeed % 11) - 5) / 10;
  const changeClass = pseudoChange >= 0 ? "text-terminal-green" : "text-terminal-red";
  const changeSign = pseudoChange >= 0 ? "+" : "";
  card.innerHTML = `
    <div class="flex justify-between items-start gap-2 mb-1">
      <span class="text-xs font-semibold truncate">${escapeHtml(shortName(scheme.scheme_name))}</span>
      <span class="text-[10px] font-mono ${changeClass} shrink-0">${changeSign}${pseudoChange.toFixed(2)}%</span>
    </div>
    <p class="text-[10px] text-terminal-muted truncate mb-2">${escapeHtml(scheme.category || "Equity")}</p>
    <svg viewBox="0 0 80 24" class="w-full h-6 opacity-60" fill="none">
      <polyline stroke="${pseudoChange >= 0 ? "#22c55e" : "#ef4444"}" stroke-width="1.5"
        points="0,${12 + sparkSeed % 8} 16,${8 + sparkSeed % 10} 32,${14 + sparkSeed % 6} 48,${6 + sparkSeed % 12} 64,${10 + sparkSeed % 8} 80,${4 + sparkSeed % 10}" />
    </svg>`;
  card.addEventListener("click", () => {
    setActiveScheme(scheme);
    sendMessage(`Tell me about ${scheme.scheme_name}`);
  });
  return card;
}

async function loadSchemes() {
  try {
    const res = await fetch(apiUrl("/api/corpus"));
    const data = await res.json();
    schemes = data.schemes || [];
    if (elements.schemeCount) elements.schemeCount.textContent = `${schemes.length} funds`;
    if (elements.schemeList) {
      elements.schemeList.innerHTML = "";
      schemes.forEach((s, i) => elements.schemeList.appendChild(renderSchemeCard(s, i)));
    }
  } catch (_) {
    if (elements.schemeList) {
      elements.schemeList.innerHTML = '<p class="text-xs text-red-400 p-2">Could not load watchlist</p>';
    }
  }
}

function initTicker() {
  if (!elements.ticker) return;
  const items = [...TICKER_LABELS, ...TICKER_LABELS].map((label) => {
    const up = Math.random() > 0.45;
    const val = (Math.random() * 2).toFixed(2);
    const cls = up ? "text-terminal-green" : "text-terminal-red";
    const sign = up ? "+" : "-";
    return `<span class="inline-flex items-center gap-2 mx-6"><span class="text-terminal-text">${label}</span><span class="${cls}">${sign}${val}%</span></span>`;
  });
  elements.ticker.innerHTML = items.join("");
}

function initClock() {
  const tick = () => {
    const now = new Date();
    if (elements.clock) {
      elements.clock.textContent = now.toLocaleTimeString("en-IN", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false,
      });
    }
  };
  tick();
  setInterval(tick, 1000);
}

function initQuickActions() {
  elements.quickActions?.querySelectorAll("[data-query]").forEach((btn) => {
    btn.addEventListener("click", () => {
      if (!activeScheme) {
        showError("Select a scheme from the watchlist first.");
        return;
      }
      sendMessage(buildQueryForScheme(activeScheme, btn.dataset.query));
    });
  });
}

function autoResizeInput() {
  const el = elements.input;
  if (!el) return;
  el.style.height = "auto";
  el.style.height = `${Math.min(el.scrollHeight, 112)}px`;
}

elements.form?.addEventListener("submit", (e) => {
  e.preventDefault();
  sendMessage(elements.input.value);
});

elements.input?.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    elements.form?.requestSubmit();
  }
});

elements.input?.addEventListener("input", autoResizeInput);

initExamples();
initTicker();
initClock();
initQuickActions();
loadSchemes();
