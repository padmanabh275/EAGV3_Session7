const $ = (id) => document.getElementById(id);
const HISTORY_KEY = "pricecompare_history_v1";
const THEME_KEY = "pricecompare_theme";

/** Last Q&A available for "Add to RAG" */
const session = {
  query: "",
  answerPlain: "",
  answerMode: "",
  compareRan: false,
  comparePlain: "",
  compareRag: "",
};

const COMPARE_PLACEHOLDER_RAG = "Run A/B compare from the sidebar.";
const COMPARE_PLACEHOLDER_PLAIN = "Model general knowledge only.";

function activeTabName() {
  return document.querySelector(".tab.active")?.dataset.tab || "answer";
}

function isCompareEmpty() {
  const rag = $("compare-rag").textContent.trim();
  const plain = $("compare-plain").textContent.trim();
  return (
    rag === COMPARE_PLACEHOLDER_RAG ||
    plain === COMPARE_PLACEHOLDER_PLAIN ||
    rag.startsWith("Loading ")
  );
}

function isIndexableAnswer(text) {
  if (!text || text.length < 10) return false;
  const t = text.trim();
  if (t === COMPARE_PLACEHOLDER_RAG || t === COMPARE_PLACEHOLDER_PLAIN) return false;
  if (/^loading /i.test(t)) return false;
  return true;
}

/* ── API ───────────────────────────────────────────────────────────── */
async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || res.statusText);
  return data;
}

/* ── Theme ───────────────────────────────────────────────────────── */
function initTheme() {
  const saved = localStorage.getItem(THEME_KEY);
  const theme = saved || (window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark");
  document.documentElement.setAttribute("data-theme", theme);
}

function toggleTheme() {
  const next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", next);
  localStorage.setItem(THEME_KEY, next);
}

/* ── Toast ───────────────────────────────────────────────────────── */
let toastTimer;
function toast(msg) {
  const el = $("toast");
  el.textContent = msg;
  el.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove("show"), 2800);
}

/* ── Tabs ──────────────────────────────────────────────────────────── */
function initTabs() {
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
      document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
      tab.classList.add("active");
      $(`tab-${tab.dataset.tab}`).classList.add("active");
    });
  });
}

function switchTab(name) {
  document.querySelector(`.tab[data-tab="${name}"]`)?.click();
}

/* ── Health & stats ────────────────────────────────────────────────── */
function setHealth(health) {
  const pill = $("status-pill");
  const text = $("status-text");
  pill.classList.remove("ok", "warn", "loading");

  $("stat-products").textContent = health.products ?? "—";
  $("stat-chunks").textContent = health.indexed_chunks ?? "—";
  $("stat-gateway").textContent = health.gateway_ok ? "Online" : "Offline";

  if (health.gateway_ok && health.index_ready) {
    pill.classList.add("ok");
    text.textContent = `Live · ${health.indexed_chunks} chunks`;
  } else if (health.gateway_ok) {
    pill.classList.add("warn");
    text.textContent = "Index empty — run indexer";
  } else {
    pill.classList.add("warn");
    text.textContent = "Start gateway :8107";
  }
}

async function loadHealth() {
  try {
    setHealth(await api("/api/health"));
  } catch {
    $("status-pill").classList.add("warn");
    $("status-text").textContent = "API unreachable";
  }
}

/* ── Samples ───────────────────────────────────────────────────────── */
async function loadSamples() {
  try {
    const samples = await api("/api/samples");
    const list = $("sample-list");
    list.innerHTML = samples
      .map(
        (s, i) => `
      <button type="button" class="sample-item" data-q="${escapeAttr(s.query)}">
        <span class="sample-type ${s.type}">${s.type}</span>
        <p>Q${i + 1}: ${escapeHtml(s.query)}</p>
      </button>`
      )
      .join("");
    list.querySelectorAll(".sample-item").forEach((btn) => {
      btn.addEventListener("click", () => {
        $("query").value = btn.dataset.q;
        updateCharCount();
        $("query").focus();
      });
    });
  } catch {
    $("sample-list").innerHTML = '<p class="empty-state compact">Could not load samples.</p>';
  }
}

/* ── History ───────────────────────────────────────────────────────── */
function loadHistory() {
  let items = [];
  try {
    items = JSON.parse(localStorage.getItem(HISTORY_KEY) || "[]");
  } catch {
    items = [];
  }
  const ul = $("history-list");
  if (!items.length) {
    ul.innerHTML = '<li style="cursor:default; opacity:0.6">No history yet</li>';
    return;
  }
  ul.innerHTML = items
    .slice(0, 8)
    .map((q) => `<li title="${escapeAttr(q)}">${escapeHtml(q)}</li>`)
    .join("");
  ul.querySelectorAll("li").forEach((li) => {
    if (li.style.cursor === "default") return;
    li.addEventListener("click", () => {
      $("query").value = li.textContent;
      updateCharCount();
    });
  });
}

function pushHistory(query) {
  let items = [];
  try {
    items = JSON.parse(localStorage.getItem(HISTORY_KEY) || "[]");
  } catch {
    items = [];
  }
  items = [query, ...items.filter((q) => q !== query)].slice(0, 12);
  localStorage.setItem(HISTORY_KEY, JSON.stringify(items));
  loadHistory();
}

/* ── Render ────────────────────────────────────────────────────────── */
function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function escapeAttr(s) {
  return escapeHtml(s).replace(/'/g, "&#39;");
}

function highlightPrices(text) {
  return escapeHtml(text).replace(
    /(₹\s?[\d,]+(?:\.\d{1,2})?)/g,
    '<span class="price">$1</span>'
  );
}

function setAnswerLoading() {
  const el = $("answer");
  el.className = "answer loading";
  el.innerHTML = '<div class="skeleton"></div><div class="skeleton"></div><div class="skeleton"></div>';
}

function setAnswer(text, mode) {
  const el = $("answer");
  const tag = $("answer-mode");
  tag.textContent = mode;
  tag.className = `mode-tag ${mode === "RAG" ? "rag" : mode === "Search" ? "search" : "plain"}`;

  session.answerMode = mode;

  if (!text) {
    el.className = "answer empty";
    el.innerHTML = `<div class="empty-state"><p>No answer returned.</p></div>`;
    $("btn-copy").disabled = true;
    updateIndexButtons();
    return;
  }
  el.className = "answer";
  session.answerPlain = text;
  el.innerHTML = highlightPrices(text);
  $("btn-copy").disabled = false;
  $("btn-copy").dataset.copy = text;
  updateIndexButtons();
  showIndexHint(text, mode);
}

function showIndexHint(text, mode) {
  const hint = $("index-hint");
  const notInCatalog = /not in catalog index/i.test(text);
  if (mode === "Plain" || notInCatalog) {
    hint.classList.remove("hidden", "success");
    hint.innerHTML =
      notInCatalog || mode === "Plain"
        ? "This answer is <strong>not in your catalog</strong> yet. Click <strong>Add to RAG</strong> to save it, then <strong>Retry with RAG</strong>."
        : "";
    if (mode === "Plain" && !notInCatalog) {
      hint.innerHTML =
        "General-knowledge answer. Use <strong>Add to RAG</strong> to store it in your index for future queries.";
    }
  } else {
    hint.classList.add("hidden");
  }
}

function updateIndexButtons() {
  const plainForCompare =
    session.compareRan && isIndexableAnswer(session.comparePlain)
      ? session.comparePlain
      : "";
  const answerForIndex =
    activeTabName() === "compare" && plainForCompare
      ? plainForCompare
      : session.answerPlain;
  const canIndex =
    session.query.length >= 2 &&
    isIndexableAnswer(answerForIndex) &&
    session.answerMode !== "Search" &&
    (activeTabName() !== "compare" || session.compareRan);
  $("btn-index-answer").disabled = !canIndex;
  const canIndexPlain =
    session.compareRan && isIndexableAnswer(session.comparePlain) && session.query.length >= 2;
  $("btn-index-plain").disabled = !canIndexPlain;
  $("btn-refresh-rag").classList.toggle("hidden", !session.compareRan);
}

async function refreshCompareRag() {
  const query = session.query || getQuery();
  if (!query) return;
  const ragEl = $("compare-rag");
  ragEl.className = "compare-body loading";
  ragEl.textContent = "Refreshing with RAG…";
  try {
    const withRag = await api("/api/ask", {
      method: "POST",
      body: JSON.stringify({ query, use_index: true, top_k: getTopK() }),
    });
    const ragText = withRag.answer || "(empty)";
    session.compareRag = ragText;
    ragEl.className = "compare-body";
    ragEl.innerHTML = highlightPrices(ragText);
    renderSources(withRag.sources || []);
    return ragText;
  } catch (e) {
    ragEl.className = "compare-body";
    ragEl.textContent = `Error: ${e.message}`;
    throw e;
  }
}

async function refreshAfterIndex(fromCompare) {
  $("use-index").checked = true;
  const tab = activeTabName();
  if (fromCompare || tab === "compare") {
    switchTab("compare");
    if (session.compareRan && !isCompareEmpty()) {
      await refreshCompareRag();
      toast("With RAG column updated from catalog");
    } else {
      await doCompare();
    }
  } else {
    switchTab("answer");
    await doAsk();
  }
}

async function indexCurrentAnswer(sourceLabel) {
  const fromCompare = sourceLabel === "compare-plain";
  const query = session.query || getQuery();
  if (!query) {
    toast("Enter a question first");
    return;
  }
  if (fromCompare && !session.compareRan) {
    toast("Run A/B Compare first — the Without column needs a real answer");
    return;
  }
  const answer = fromCompare
    ? session.comparePlain
    : session.answerPlain;
  if (!isIndexableAnswer(answer)) {
    toast("Nothing to index yet — get an answer first (A/B or Get answer)");
    return;
  }
  $("btn-index-answer").disabled = true;
  $("btn-index-plain").disabled = true;
  setBusy(true);
  try {
    const res = await api("/api/index-answer", {
      method: "POST",
      body: JSON.stringify({
        query,
        answer,
        title: query.slice(0, 120),
      }),
    });
    await loadHealth();
    const hint = $("index-hint");
    hint.classList.remove("hidden");
    hint.classList.add("success");
    hint.innerHTML = `Indexed <strong>${res.chunks_indexed}</strong> chunk(s). Refreshing <strong>With RAG</strong>…`;
    $("btn-rag-again").classList.remove("hidden");
    $("use-index").checked = true;
    toast(`Added to catalog (+${res.chunks_indexed} chunks)`);
    await refreshAfterIndex(fromCompare);
    hint.innerHTML = `Indexed <strong>${res.chunks_indexed}</strong> chunk(s). <strong>With RAG</strong> panel updated — check Sources tab for retrieved chunks.`;
  } catch (e) {
    toast(`Index failed: ${e.message}`);
  } finally {
    setBusy(false);
    updateIndexButtons();
  }
}

function renderSources(results) {
  const el = $("sources");
  $("source-count").textContent = String(results.length);

  if (!results.length) {
    el.innerHTML = '<div class="empty-state compact"><p>No chunks retrieved.</p></div>';
    return;
  }

  el.innerHTML = results
    .map((r, idx) => {
      const path = (r.source || "").replace("sandbox:corpus/products/", "").replace("sandbox:", "");
      const userNote = r.indexed_from === "without_rag";
      return `
      <article class="source-card ${idx === 0 ? "expanded" : ""} ${userNote ? "user-note" : ""}" data-idx="${idx}">
        <div class="source-header">
          <div class="source-rank">
            <span class="rank-num">${r.rank}</span>
            ${userNote ? '<span class="sample-type semantic">user note</span>' : ""}
            <span class="source-path">${escapeHtml(path || "unknown")}</span>
          </div>
          <svg class="source-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 9l6 6 6-6"/></svg>
        </div>
        <div class="source-body">${escapeHtml(r.chunk || "")}</div>
      </article>`;
    })
    .join("");

  el.querySelectorAll(".source-header").forEach((hdr) => {
    hdr.addEventListener("click", () => hdr.closest(".source-card").classList.toggle("expanded"));
  });
}

/* ── Actions ───────────────────────────────────────────────────────── */
function setBusy(busy) {
  $("btn-ask").disabled = busy;
  $("btn-search").disabled = busy;
  $("btn-compare").disabled = busy;
}

function getQuery() {
  return $("query").value.trim();
}

function getTopK() {
  return Number($("top-k").value) || 6;
}

async function doSearch() {
  const query = getQuery();
  if (!query) return toast("Enter a question first");
  session.query = query;
  setBusy(true);
  setAnswerLoading();
  switchTab("sources");
  try {
    const data = await api("/api/search", {
      method: "POST",
      body: JSON.stringify({ query, top_k: getTopK() }),
    });
    renderSources(data.results);
    setAnswer("Search-only — see retrieved sources in the Sources tab.", "Search");
    $("meta").textContent = `${data.results.length} chunks retrieved`;
    pushHistory(query);
  } catch (e) {
    setAnswer(`Error: ${e.message}`, "plain");
  } finally {
    setBusy(false);
  }
}

async function doAsk() {
  const query = getQuery();
  if (!query) return toast("Enter a question first");
  session.query = query;
  setBusy(true);
  setAnswerLoading();
  switchTab("answer");
  $("btn-rag-again").classList.add("hidden");
  try {
    const data = await api("/api/ask", {
      method: "POST",
      body: JSON.stringify({
        query,
        use_index: $("use-index").checked,
        top_k: getTopK(),
      }),
    });
    const mode = data.use_index ? "RAG" : "Plain";
    setAnswer(data.answer, mode);
    $("meta").textContent = `${mode} · ${data.provider || "?"} / ${data.model || "?"} · ${(data.sources || []).length} sources`;
    renderSources(data.sources || []);
    pushHistory(query);
    toast("Answer ready");
  } catch (e) {
    setAnswer(`Error: ${e.message}`, "plain");
    $("meta").textContent = "";
  } finally {
    setBusy(false);
  }
}

async function doCompare() {
  const query = getQuery();
  if (!query) return toast("Enter a question first");
  session.query = query;
  setBusy(true);
  switchTab("compare");
  $("btn-rag-again").classList.add("hidden");
  const ragEl = $("compare-rag");
  const plainEl = $("compare-plain");
  ragEl.className = "compare-body loading";
  plainEl.className = "compare-body loading";
  ragEl.textContent = "Loading with RAG…";
  plainEl.textContent = "Loading without index…";

  try {
    const [withRag, without] = await Promise.all([
      api("/api/ask", {
        method: "POST",
        body: JSON.stringify({ query, use_index: true, top_k: getTopK() }),
      }),
      api("/api/ask", {
        method: "POST",
        body: JSON.stringify({ query, use_index: false, top_k: getTopK() }),
      }),
    ]);
    ragEl.className = "compare-body";
    plainEl.className = "compare-body";
    const ragText = withRag.answer || "(empty)";
    const plainText = without.answer || "(empty)";
    ragEl.innerHTML = highlightPrices(ragText);
    plainEl.innerHTML = highlightPrices(plainText);
    session.compareRan = true;
    session.compareRag = ragText;
    session.comparePlain = plainText;
    session.answerPlain = plainText;
    session.answerMode = "Plain";
    renderSources(withRag.sources || []);
    updateIndexButtons();
    showIndexHint(plainText, "Plain");
    if (/not in catalog index/i.test(ragText)) {
      $("index-hint").classList.remove("hidden");
    }
    pushHistory(query);
    toast("A/B compare complete — index the Without column if needed");
  } catch (e) {
    ragEl.className = "compare-body";
    plainEl.className = "compare-body";
    ragEl.textContent = `Error: ${e.message}`;
    plainEl.textContent = "—";
  } finally {
    setBusy(false);
  }
}

function updateCharCount() {
  const n = $("query").value.length;
  $("char-count").textContent = n;
}

/* ── Init ──────────────────────────────────────────────────────────── */
initTheme();
initTabs();

$("btn-theme").addEventListener("click", toggleTheme);
$("btn-ask").addEventListener("click", doAsk);
$("btn-search").addEventListener("click", doSearch);
$("btn-compare").addEventListener("click", doCompare);
$("btn-clear").addEventListener("click", () => {
  $("query").value = "";
  updateCharCount();
});
$("btn-clear-history").addEventListener("click", () => {
  localStorage.removeItem(HISTORY_KEY);
  loadHistory();
  toast("History cleared");
});

$("btn-copy").addEventListener("click", async () => {
  const text = $("btn-copy").dataset.copy;
  if (!text) return;
  try {
    await navigator.clipboard.writeText(text);
    toast("Copied to clipboard");
  } catch {
    toast("Copy failed");
  }
});

$("btn-index-answer").addEventListener("click", () => indexCurrentAnswer("answer"));
$("btn-index-plain").addEventListener("click", () => indexCurrentAnswer("compare-plain"));

$("btn-rag-again").addEventListener("click", async () => {
  $("use-index").checked = true;
  if (activeTabName() === "compare" && session.compareRan) {
    setBusy(true);
    try {
      await refreshCompareRag();
      toast("With RAG updated");
    } finally {
      setBusy(false);
    }
  } else {
    doAsk();
  }
});

$("btn-refresh-rag").addEventListener("click", async () => {
  if (!session.compareRan) return toast("Run A/B Compare first");
  $("use-index").checked = true;
  setBusy(true);
  try {
    await refreshCompareRag();
    toast("With RAG refreshed");
  } finally {
    setBusy(false);
  }
});

$("query").addEventListener("input", updateCharCount);
$("query").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
    e.preventDefault();
    doAsk();
  }
});

$("top-k").addEventListener("input", () => {
  $("top-k-val").textContent = $("top-k").value;
});

updateCharCount();
loadHealth();
loadSamples();
loadHistory();

// Refresh health every 30s
setInterval(loadHealth, 30000);
