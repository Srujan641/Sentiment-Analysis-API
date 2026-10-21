/* Sentiment Analysis frontend: plain JS, no build step. Talks to the /api/v1 endpoints. */
(() => {
  "use strict";

  const BATCH_LIMIT = 32; // /api/v1/batch maximum (INFERENCE_BATCH_SIZE)
  const JOB_LIMIT = 1000; // /api/v1/jobs/batch maximum (MAX_JOB_TEXTS)
  const MAX_CHARS = 5000;
  const LOW_CONFIDENCE = 0.75; // fallback only; the API's `uncertain` flag is authoritative

  const SAMPLES = [
    "Best product I have ever bought!",
    "Terrible quality, broke immediately.",
    "This is not what I would call a good product.",
    "Arrived on time and looks nice, but the battery dies in an hour.",
    "Oh great, another charger that stopped working after a week.",
    "Does exactly what it says. No complaints.",
  ];

  const $ = (id) => document.getElementById(id);

  // ---------------------------------------------------------------- storage (best effort)
  const store = {
    get(key, fallback) {
      try {
        const v = localStorage.getItem(key);
        return v === null ? fallback : JSON.parse(v);
      } catch {
        return fallback;
      }
    },
    set(key, value) {
      try {
        localStorage.setItem(key, JSON.stringify(value));
      } catch {
        /* private mode or blocked storage: ignore */
      }
    },
  };

  // ---------------------------------------------------------------- API client
  class ApiError extends Error {
    constructor(message, status) {
      super(message);
      this.status = status;
    }
  }

  async function api(path, { method = "GET", body } = {}) {
    const headers = { Accept: "application/json" };
    const key = store.get("apiKey", "");
    if (key) headers["X-API-Key"] = key;
    if (body !== undefined) headers["Content-Type"] = "application/json";

    let res;
    try {
      res = await fetch(path, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
    } catch {
      throw new ApiError("Can't reach the server. Is the API running?", 0);
    }

    let data = null;
    try {
      data = await res.json();
    } catch {
      /* non-JSON body */
    }
    if (res.ok) return data;

    if (res.status === 429) {
      const wait = res.headers.get("Retry-After");
      throw new ApiError(`Rate limit reached. Try again in ${wait || "a few"} seconds, or add an API key in settings.`, 429);
    }
    if (res.status === 401) throw new ApiError("The API key was rejected. Check it in settings.", 401);
    if (res.status === 503) throw new ApiError("The model is still loading. Try again in a moment.", 503);
    throw new ApiError(describeDetail(data && data.detail) || `Request failed (${res.status}).`, res.status);
  }

  function describeDetail(detail) {
    if (!detail) return "";
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((d) => {
          const msg = String(d.msg || "").replace(/^Value error, /, "");
          const loc = (d.loc || []).filter((p) => p !== "body");
          if (loc[0] === "texts" && typeof loc[1] === "number") return `Line ${loc[1] + 1}: ${msg}`;
          return msg;
        })
        .join(" ");
    }
    return "";
  }

  // ---------------------------------------------------------------- helpers
  const pct = (x, digits = 1) => `${(x * 100).toFixed(digits)}%`;
  const isPos = (label) => label === "POSITIVE";
  const isUnsure = (r) => (typeof r.uncertain === "boolean" ? r.uncertain : r.confidence < LOW_CONFIDENCE);

  function setLoading(btn, on) {
    btn.classList.toggle("is-loading", on);
    btn.disabled = on;
  }

  function showError(el, message) {
    el.textContent = message;
    el.hidden = !message;
  }

  let toastTimer;
  function toast(message) {
    const t = $("toast");
    t.textContent = message;
    t.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => (t.hidden = true), 2600);
  }

  function tag(label, unsure = false) {
    const span = document.createElement("span");
    span.className = `tag ${unsure ? "is-unsure" : isPos(label) ? "is-pos" : "is-neg"}`;
    span.textContent = unsure ? "UNSURE" : label;
    if (unsure) span.title = `Uncertain, leans ${label.toLowerCase()}`;
    return span;
  }

  // ---------------------------------------------------------------- tabs
  const TABS = { analyze: "tab-analyze", batch: "tab-batch", monitor: "tab-monitor" };

  function showTab(name) {
    if (!TABS[name]) name = "analyze";
    for (const [key, id] of Object.entries(TABS)) {
      const tab = $(id);
      const active = key === name;
      tab.setAttribute("aria-selected", String(active));
      $(tab.getAttribute("aria-controls")).hidden = !active;
    }
    if (location.hash !== `#${name}`) history.replaceState(null, "", `#${name}`);
    if (name === "monitor") startMonitoring();
    else stopMonitoring();
  }

  for (const [key, id] of Object.entries(TABS)) $(id).addEventListener("click", () => showTab(key));
  window.addEventListener("hashchange", () => showTab(location.hash.slice(1)));

  // ---------------------------------------------------------------- status
  let modelInfo = null;

  async function refreshStatus() {
    const el = $("status");
    try {
      const res = await fetch("/ready");
      const data = await res.json();
      modelInfo = data;
      el.dataset.state = data.model_loaded ? "ready" : "loading";
      $("status-text").textContent = data.model_loaded ? "Model ready" : "Model loading";
      $("m-source").textContent = data.model_source || "–";
      $("m-version").textContent = data.version || "–";
    } catch {
      el.dataset.state = "down";
      $("status-text").textContent = "API offline";
    }
  }

  // ---------------------------------------------------------------- settings
  const settings = $("settings");
  $("settings-btn").addEventListener("click", (e) => {
    e.stopPropagation();
    settings.hidden = !settings.hidden;
    if (!settings.hidden) {
      $("api-key").value = store.get("apiKey", "");
      $("api-key").focus();
    }
  });
  $("settings-save").addEventListener("click", () => {
    store.set("apiKey", $("api-key").value.trim());
    settings.hidden = true;
    toast($("api-key").value.trim() ? "API key saved" : "API key cleared");
  });
  $("settings-clear").addEventListener("click", () => {
    $("api-key").value = "";
    store.set("apiKey", "");
    settings.hidden = true;
    toast("API key cleared");
  });
  document.addEventListener("click", (e) => {
    if (!settings.hidden && !settings.contains(e.target)) settings.hidden = true;
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") settings.hidden = true;
  });

  // ================================================================ ANALYZE
  const review = $("review");
  const analyzeBtn = $("analyze-btn");

  function updateCount() {
    $("char-count").textContent = `${review.value.length.toLocaleString()} / ${MAX_CHARS.toLocaleString()}`;
  }
  review.addEventListener("input", updateCount);

  for (const text of SAMPLES) {
    const chip = document.createElement("button");
    chip.className = "chip";
    chip.type = "button";
    chip.textContent = text;
    chip.title = text;
    chip.addEventListener("click", () => {
      review.value = text;
      updateCount();
      analyze();
    });
    $("samples").appendChild(chip);
  }

  $("clear-btn").addEventListener("click", () => {
    review.value = "";
    updateCount();
    showError($("analyze-error"), "");
    review.focus();
  });

  review.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      analyze();
    }
  });
  analyzeBtn.addEventListener("click", analyze);

  async function analyze() {
    const text = review.value.trim();
    showError($("analyze-error"), "");
    if (!text) {
      showError($("analyze-error"), "Enter a review to analyze.");
      review.focus();
      return;
    }
    setLoading(analyzeBtn, true);
    try {
      const data = await api("/api/v1/predict", { method: "POST", body: { text, return_probabilities: true } });
      renderResult(data);
      addHistory(data);
    } catch (err) {
      showError($("analyze-error"), err.message);
    } finally {
      setLoading(analyzeBtn, false);
    }
  }

  function renderResult(d) {
    const neg = d.probabilities ? d.probabilities.NEGATIVE : isPos(d.label) ? 1 - d.confidence : d.confidence;
    const pos = 1 - neg;
    $("result-empty").hidden = true;
    const body = $("result-body");
    body.hidden = false;
    // restart the fade-in
    body.style.animation = "none";
    void body.offsetWidth;
    body.style.animation = "";

    const unsure = isUnsure(d);
    const badge = $("r-label");
    badge.textContent = unsure ? "UNSURE" : d.label;
    badge.className = `label-badge ${unsure ? "is-unsure" : isPos(d.label) ? "is-pos" : "is-neg"}`;
    $("r-conf").textContent = (d.confidence * 100).toFixed(1);
    $("r-neg-bar").style.width = pct(neg, 2);
    $("r-pos-bar").style.width = pct(pos, 2);
    $("r-neg").textContent = pct(neg);
    $("r-pos").textContent = pct(pos);
    $("r-bar").setAttribute("aria-label", `Negative ${pct(neg)}, positive ${pct(pos)}`);
    $("r-lowconf").hidden = !unsure;
    $("r-lean").textContent = d.label.toLowerCase();
    $("r-latency").textContent = d.latency_ms.toFixed(1);
    $("r-rid").textContent = d.request_id || "–";
  }

  // ---------------------------------------------------------------- history
  let historyItems = store.get("history", []);

  function addHistory(d) {
    historyItems.unshift({ text: d.text, label: d.label, confidence: d.confidence, uncertain: isUnsure(d) });
    historyItems = historyItems.slice(0, 8);
    store.set("history", historyItems);
    renderHistory();
  }

  function renderHistory() {
    const list = $("history");
    list.replaceChildren();
    $("history-card").hidden = historyItems.length === 0;
    for (const item of historyItems) {
      const li = document.createElement("li");
      li.title = "Analyze again";
      li.appendChild(tag(item.label, isUnsure(item)));
      const text = document.createElement("span");
      text.className = "h-text";
      text.textContent = item.text;
      const conf = document.createElement("span");
      conf.className = "h-conf";
      conf.textContent = pct(item.confidence);
      li.append(text, conf);
      li.addEventListener("click", () => {
        review.value = item.text;
        updateCount();
        window.scrollTo({ top: 0, behavior: "smooth" });
        analyze();
      });
      list.appendChild(li);
    }
  }

  $("history-clear").addEventListener("click", () => {
    historyItems = [];
    store.set("history", historyItems);
    renderHistory();
  });

  // ================================================================ BATCH
  const batchInput = $("batch-input");
  const batchBtn = $("batch-btn");
  let batchRows = [];

  const parseLines = (raw) =>
    raw
      .split(/\r?\n/)
      .map((l) => l.trim())
      .filter(Boolean);

  function updateBatchCount() {
    const n = parseLines(batchInput.value).length;
    $("batch-count").textContent = `${n.toLocaleString()} review${n === 1 ? "" : "s"}`;
    let mode = "";
    if (n > JOB_LIMIT) mode = `Over the ${JOB_LIMIT.toLocaleString()} limit`;
    else if (n > BATCH_LIMIT) mode = "Runs as a background job";
    else if (n > 0) mode = "Single forward pass";
    $("batch-mode").textContent = mode;
  }
  batchInput.addEventListener("input", updateBatchCount);

  $("batch-sample").addEventListener("click", () => {
    batchInput.value = [
      ...SAMPLES,
      "Comfortable to wear all day and the sound is crisp.",
      "Customer support never replied to my emails.",
      "Decent for the price, nothing special.",
      "The zipper broke on the first trip.",
    ].join("\n");
    updateBatchCount();
  });

  $("batch-clear").addEventListener("click", () => {
    batchInput.value = "";
    updateBatchCount();
    showError($("batch-error"), "");
    $("batch-results").hidden = true;
    $("batch-progress").hidden = true;
  });

  // Minimal CSV parser: handles quoted fields with commas, quotes and newlines.
  function parseCsv(text) {
    const rows = [];
    let row = [], field = "", quoted = false;
    for (let i = 0; i < text.length; i++) {
      const c = text[i];
      if (quoted) {
        if (c === '"' && text[i + 1] === '"') { field += '"'; i++; }
        else if (c === '"') quoted = false;
        else field += c;
      } else if (c === '"') quoted = true;
      else if (c === ",") { row.push(field); field = ""; }
      else if (c === "\n" || c === "\r") {
        if (c === "\r" && text[i + 1] === "\n") i++;
        row.push(field); rows.push(row); row = []; field = "";
      } else field += c;
    }
    if (field || row.length) { row.push(field); rows.push(row); }
    return rows.filter((r) => r.some((f) => f.trim()));
  }

  $("batch-file").addEventListener("change", async (e) => {
    const file = e.target.files[0];
    e.target.value = "";
    if (!file) return;
    if (file.size > 5 * 1024 * 1024) {
      showError($("batch-error"), "That file is larger than 5 MB.");
      return;
    }
    const text = await file.text();
    let lines;
    if (/\.csv$/i.test(file.name)) {
      const rows = parseCsv(text);
      const header = rows[0] ? rows[0].map((h) => h.trim().toLowerCase()) : [];
      let col = header.findIndex((h) => ["text", "review", "content", "comment"].includes(h));
      const hasHeader = col !== -1;
      if (!hasHeader) col = 0;
      lines = rows.slice(hasHeader ? 1 : 0).map((r) => (r[col] || "").replace(/\s+/g, " ").trim()).filter(Boolean);
    } else {
      lines = parseLines(text);
    }
    batchInput.value = lines.join("\n");
    updateBatchCount();
    toast(`Loaded ${lines.length.toLocaleString()} reviews from ${file.name}`);
  });

  batchBtn.addEventListener("click", runBatch);

  async function runBatch() {
    const texts = parseLines(batchInput.value);
    showError($("batch-error"), "");
    if (!texts.length) {
      showError($("batch-error"), "Add at least one review, one per line.");
      return;
    }
    if (texts.length > JOB_LIMIT) {
      showError($("batch-error"), `That's ${texts.length.toLocaleString()} reviews; the limit is ${JOB_LIMIT.toLocaleString()} per run.`);
      return;
    }
    const tooLong = texts.findIndex((t) => t.length > MAX_CHARS);
    if (tooLong !== -1) {
      showError($("batch-error"), `Line ${tooLong + 1} is longer than ${MAX_CHARS.toLocaleString()} characters.`);
      return;
    }

    setLoading(batchBtn, true);
    $("batch-results").hidden = true;
    const started = performance.now();
    try {
      let results;
      if (texts.length <= BATCH_LIMIT) {
        const data = await api("/api/v1/batch", { method: "POST", body: { texts } });
        results = data.results;
      } else {
        results = await runJob(texts);
      }
      batchRows = results.map((r, i) => ({ ...r, index: i + 1 }));
      renderBatch((performance.now() - started) / 1000);
    } catch (err) {
      showError($("batch-error"), err.message);
    } finally {
      setLoading(batchBtn, false);
      $("batch-progress").hidden = true;
    }
  }

  async function runJob(texts) {
    const progress = $("batch-progress");
    const fill = $("batch-progress-fill");
    const label = $("batch-progress-text");
    progress.hidden = false;
    fill.style.width = "0";
    label.textContent = "Queued…";

    const job = await api("/api/v1/jobs/batch", { method: "POST", body: { texts } });
    for (;;) {
      await new Promise((r) => setTimeout(r, 500));
      const s = await api(job.status_url);
      const frac = s.total ? s.processed / s.total : 0;
      fill.style.width = pct(frac, 1);
      label.textContent = `${s.status === "queued" ? "Queued" : "Scoring"} ${s.processed.toLocaleString()} / ${s.total.toLocaleString()}`;
      if (s.status === "complete") break;
      if (s.status === "failed") throw new ApiError(`The job failed: ${s.error || "unknown error"}`, 500);
    }
    const res = await api(job.results_url);
    return res.results;
  }

  function renderBatch(seconds) {
    const n = batchRows.length;
    const posN = batchRows.filter((r) => isPos(r.label)).length;
    const avg = batchRows.reduce((s, r) => s + r.confidence, 0) / n;
    $("b-total").textContent = n.toLocaleString();
    $("b-pos").textContent = `${posN.toLocaleString()} (${pct(posN / n, 0)})`;
    $("b-neg").textContent = `${(n - posN).toLocaleString()} (${pct((n - posN) / n, 0)})`;
    $("b-conf").textContent = pct(avg);
    $("b-time").textContent = seconds < 1 ? `${Math.round(seconds * 1000)} ms` : `${seconds.toFixed(1)} s`;
    $("batch-filter").value = "all";
    renderBatchTable();
    $("batch-results").hidden = false;
  }

  function renderBatchTable() {
    const filter = $("batch-filter").value;
    const rows = batchRows.filter((r) =>
      filter === "all" ? true : filter === "low" ? isUnsure(r) : r.label === filter,
    );
    const tbody = $("batch-tbody");
    tbody.replaceChildren();
    if (!rows.length) {
      const tr = tbody.insertRow();
      const td = tr.insertCell();
      td.colSpan = 4;
      td.className = "muted";
      td.textContent = "No reviews match this filter.";
      return;
    }
    const frag = document.createDocumentFragment();
    for (const r of rows) {
      const tr = document.createElement("tr");
      const idx = document.createElement("td");
      idx.className = "num muted";
      idx.textContent = r.index;
      const text = document.createElement("td");
      text.className = "review-cell";
      text.textContent = r.text;
      const lab = document.createElement("td");
      lab.appendChild(tag(r.label, isUnsure(r)));
      const conf = document.createElement("td");
      conf.className = "num";
      const wrap = document.createElement("span");
      wrap.className = "conf-cell";
      const bar = document.createElement("span");
      bar.className = "mini-bar";
      const fill = document.createElement("span");
      fill.style.width = pct(r.confidence, 1);
      fill.style.background = isPos(r.label) ? "var(--pos)" : "var(--neg)";
      bar.appendChild(fill);
      const val = document.createElement("span");
      val.textContent = pct(r.confidence);
      if (isUnsure(r)) {
        val.style.color = "var(--warn)";
        val.title = "Low confidence";
      }
      wrap.append(bar, val);
      conf.appendChild(wrap);
      tr.append(idx, text, lab, conf);
      frag.appendChild(tr);
    }
    tbody.appendChild(frag);
  }

  $("batch-filter").addEventListener("change", renderBatchTable);

  $("batch-export").addEventListener("click", () => {
    const esc = (v) => `"${String(v).replace(/"/g, '""')}"`;
    const lines = ["index,text,label,confidence,uncertain"].concat(
      batchRows.map((r) => [r.index, esc(r.text), r.label, r.confidence.toFixed(6), isUnsure(r)].join(",")),
    );
    const blob = new Blob([lines.join("\n")], { type: "text/csv" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `sentiment-results-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(a.href);
  });

  // ================================================================ MONITORING
  let monitorTimer = null;

  function startMonitoring() {
    if (monitorTimer) return;
    refreshMonitoring();
    monitorTimer = setInterval(refreshMonitoring, 10000);
  }

  function stopMonitoring() {
    clearInterval(monitorTimer);
    monitorTimer = null;
  }

  function parseMetrics(text) {
    const out = [];
    for (const line of text.split("\n")) {
      if (!line || line.startsWith("#")) continue;
      const m = line.match(/^([a-zA-Z_:][\w:]*)(\{([^}]*)\})?\s+([^\s]+)/);
      if (!m) continue;
      const labels = {};
      if (m[3]) for (const kv of m[3].matchAll(/(\w+)="([^"]*)"/g)) labels[kv[1]] = kv[2];
      out.push({ name: m[1], labels, value: parseFloat(m[4]) });
    }
    return out;
  }

  const sum = (metrics, name, pred = () => true) =>
    metrics.filter((m) => m.name === name && pred(m.labels)).reduce((s, m) => s + m.value, 0);

  async function refreshMonitoring() {
    try {
      const res = await fetch("/metrics");
      const metrics = parseMetrics(await res.text());

      const pos = sum(metrics, "sentiment_predictions_total", (l) => l.label === "POSITIVE");
      const neg = sum(metrics, "sentiment_predictions_total", (l) => l.label === "NEGATIVE");
      const total = pos + neg;
      $("m-preds").textContent = total.toLocaleString();
      $("m-posshare").textContent = total ? pct(pos / total) : "–";
      $("m-pos").textContent = pos.toLocaleString();
      $("m-neg").textContent = neg.toLocaleString();
      $("m-mix-pos").style.width = total ? pct(pos / total, 2) : "0";
      $("m-mix-neg").style.width = total ? pct(neg / total, 2) : "0";
      $("m-mix-bar").setAttribute("aria-label", `${pos} positive, ${neg} negative`);

      const confSum = sum(metrics, "sentiment_prediction_confidence_sum");
      const confCount = sum(metrics, "sentiment_prediction_confidence_count");
      $("m-conf").textContent = confCount ? pct(confSum / confCount) : "–";

      const isPredict = (l) => l.path === "/api/v1/predict";
      const latSum = sum(metrics, "http_request_duration_seconds_sum", isPredict);
      const latCount = sum(metrics, "http_request_duration_seconds_count", isPredict);
      $("m-lat").textContent = latCount ? `${((latSum / latCount) * 1000).toFixed(1)} ms` : "–";

      $("m-reqs").textContent = sum(metrics, "http_requests_total").toLocaleString();
      $("m-429").textContent = sum(metrics, "rate_limited_requests_total").toLocaleString();
      $("m-updated").textContent = `Updated ${new Date().toLocaleTimeString()}`;
    } catch {
      $("m-updated").textContent = "Metrics unavailable";
    }

    try {
      renderDrift(await api("/api/v1/monitoring/drift"));
    } catch (err) {
      $("d-summary").textContent = err.message;
    }
  }

  function renderDrift(d) {
    const pill = $("d-status");
    const labels = {
      no_data: "No data",
      no_reference: "No baseline",
      stable: "Stable",
      warning: "Warning",
      drift: "Drift",
    };
    pill.textContent = labels[d.status] || d.status;
    pill.dataset.state = d.status;

    const summary = $("d-summary");
    if (d.status === "no_data") summary.textContent = "No predictions yet. Analyze some reviews to populate the window.";
    else if (d.status === "no_reference") summary.textContent = "No training baseline was found for this model.";
    else {
      const few = d.window_size < (d.min_samples_for_reliable_psi || 200);
      summary.textContent =
        `Last ${d.window_size.toLocaleString()} predictions vs. ${d.reference.n.toLocaleString()} training reviews.` +
        (few ? " Fewer than 200 samples, so treat scores as rough." : "");
    }

    const tbody = $("d-rows");
    tbody.replaceChildren();
    if (!d.psi) {
      const td = tbody.insertRow().insertCell();
      td.colSpan = 3;
      td.className = "muted";
      td.textContent = "No data yet.";
      return;
    }
    const names = { text_length: "Review length", confidence: "Model confidence", label: "Positive / negative mix" };
    for (const [key, value] of Object.entries(d.psi)) {
      const level = value > 0.25 ? "drift" : value > 0.1 ? "warning" : "stable";
      const tr = tbody.insertRow();
      tr.insertCell().textContent = names[key] || key;
      const v = tr.insertCell();
      v.className = "num";
      v.textContent = value.toFixed(3);
      const l = tr.insertCell();
      const span = document.createElement("span");
      span.className = `lvl lvl-${level}`;
      span.textContent = labels[level];
      l.appendChild(span);
    }
  }

  // ---------------------------------------------------------------- init
  updateCount();
  updateBatchCount();
  renderHistory();
  refreshStatus();
  setInterval(refreshStatus, 15000);
  showTab(location.hash.slice(1) || "analyze");
})();
