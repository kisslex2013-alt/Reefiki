(function () {
  "use strict";

  const SECTION_IDS = ["overview", "projects", "memory", "worktrees", "publish", "review", "sprint", "logs"];
  const SECTION_HOTKEYS = {
    "1": "overview",
    "2": "projects",
    "3": "memory",
    "4": "worktrees",
    "5": "publish",
    "6": "review",
    "7": "sprint",
    "8": "logs",
  };
  const VIEW_SECTIONS = ["projects", "worktrees", "logs"];
  const SAVED_VIEW_LIMIT = 8;
  const WARNING_PANEL_CLOSE_MS = 150;
  const STORAGE = {
    lang: "reefiki.opsBoardNext.lang",
    theme: "reefiki.opsBoardNext.theme",
    interval: "reefiki.opsBoardNext.interval",
    section: "reefiki.opsBoardNext.section",
    savedViews: "reefiki.opsBoardNext.savedViews",
  };

  const state = {
    lang: localStorage.getItem(STORAGE.lang) || "en",
    theme: localStorage.getItem(STORAGE.theme) || "dark",
    interval: localStorage.getItem(STORAGE.interval) || "0",
    section: localStorage.getItem(STORAGE.section) || "overview",
    i18n: { en: {}, ru: {} },
    snapshot: null,
    snapshotError: null,
    logsHealth: null,
    logSource: "",
    logCursor: "",
    logEntries: [],
    projectFilter: "all",
    projectQuery: "",
    worktreeFilter: "all",
    worktreeQuery: "",
    logFilter: "all",
    logQuery: "",
    openLogKey: "",
    expandedWarningKey: "",
    railPayload: null,
    snapshotLoading: true,
    savedViews: loadSavedViews(),
    refreshTimer: null,
  };

  const els = {};

  document.addEventListener("DOMContentLoaded", init);

  async function init() {
    mapElements();
    applyTheme();
    bindEvents();
    await loadI18n();
    processI18nNodes();
    syncControlState();
    await refreshSnapshot();
    await refreshLogsHealth();
    activateSection(SECTION_IDS.includes(state.section) ? state.section : "overview");
    syncInterval();
  }

  function mapElements() {
    [
      "verdict-card", "verdict-dot", "verdict-title", "verdict-note", "meta-branch", "meta-head",
      "meta-sync", "meta-age", "lang", "theme", "interval", "refresh", "gate-continue",
      "gate-publish", "gate-cleanup", "gate-continue-note", "gate-publish-note", "gate-cleanup-note",
      "generated-at", "overview-summary", "kpi-grid", "command-center", "current-work-count", "current-work-list",
      "attention-count", "attention-list", "projects-search", "projects-views", "projects-filters", "projects-table", "memory-notice", "memory-panels", "memory-topology", "memory-insights",
      "worktrees-search", "worktrees-views", "worktrees-filters", "worktrees-table", "publish-summary", "publish-classification", "publish-gates", "publish-commands",
      "review-hygiene", "review-list", "health-list", "sprint-summary", "sprint-burndown",
      "active-tasks", "next-tasks", "log-source", "logs-search", "logs-views", "logs-filters", "logs-refresh", "log-state", "log-view",
      "right-rail", "rail-status", "rail-title", "rail-subtitle", "rail-fields", "rail-actions-list",
      "nav-count-overview", "nav-count-projects", "nav-count-memory", "nav-count-worktrees",
      "nav-count-publish", "nav-count-review", "nav-count-sprint", "nav-count-logs",
    ].forEach((id) => {
      els[id] = document.getElementById(id);
    });
  }

  function bindEvents() {
    bindModeButton("lang", () => {
      state.lang = state.lang === "ru" ? "en" : "ru";
      localStorage.setItem(STORAGE.lang, state.lang);
      processI18nNodes();
      syncControlState();
      renderAll();
    });
    bindModeButton("theme", () => {
      state.theme = state.theme === "dark" ? "light" : "dark";
      localStorage.setItem(STORAGE.theme, state.theme);
      applyTheme();
    });
    bindModeButton("interval", () => {
      state.interval = nextIntervalValue();
      localStorage.setItem(STORAGE.interval, state.interval);
      syncInterval();
    });
    syncControlState();
    els.refresh.addEventListener("click", () => refreshSnapshot());
    makeSelectable(els["verdict-card"], () => setRail(verdictRail()));
    makeSelectable(els["gate-continue"], () => setRail(safetyGateRail("continue")));
    makeSelectable(els["gate-publish"], () => setRail(safetyGateRail("publish")));
    makeSelectable(els["gate-cleanup"], () => setRail(safetyGateRail("cleanup")));
    els["projects-search"].addEventListener("input", () => {
      state.projectQuery = els["projects-search"].value;
      renderProjects();
    });
    els["worktrees-search"].addEventListener("input", () => {
      state.worktreeQuery = els["worktrees-search"].value;
      renderWorktrees();
    });
    els["logs-search"].addEventListener("input", () => {
      state.logQuery = els["logs-search"].value;
      renderLogEntries();
    });
    els["logs-refresh"].addEventListener("click", () => refreshLogTail(false));
    els["log-source"].addEventListener("change", () => {
      state.logSource = els["log-source"].value;
      state.logCursor = "";
      state.logEntries = [];
      refreshLogTail(true);
    });
    document.querySelectorAll("[data-section]").forEach((button) => {
      button.addEventListener("click", () => activateSection(button.dataset.section));
    });
    document.addEventListener("keydown", handleGlobalKeydown);
  }

  function bindModeButton(id, onChange) {
    const node = els[id];
    if (!node) return;
    node.addEventListener("click", onChange);
  }

  function nextIntervalValue() {
    const values = ["0", "30000", "120000"];
    const index = values.indexOf(String(state.interval || "0"));
    return values[(index + 1 + values.length) % values.length];
  }

  function syncControlState() {
    setModeButton("lang", "language", state.lang === "ru" ? "Русский" : "English", state.lang);
    setModeButton("theme", state.theme === "light" ? "sun" : "moon", state.theme === "light" ? t("ui.light") : t("ui.dark"), state.theme);
    const intervalMeta = intervalControlMeta();
    setModeButton("interval", intervalMeta.icon, intervalMeta.label, intervalMeta.value);
  }

  function setModeButton(id, icon, label, value) {
    const node = els[id];
    if (!node) return;
    node.dataset.value = String(value || "");
    node.setAttribute("aria-label", label);
    node.setAttribute("title", label);
    node.innerHTML = iconSvg(icon);
  }

  function intervalControlMeta() {
    const value = String(state.interval || "0");
    if (value === "30000") return { value, icon: "timer-short", label: t("ui.interval30") };
    if (value === "120000") return { value, icon: "timer-long", label: t("ui.interval2m") };
    return { value: "0", icon: "power", label: t("ui.off") };
  }

  function iconSvg(name) {
    const paths = {
      language: '<path d="M4 5h9"/><path d="M9 3v2"/><path d="M6.5 5c.7 2 2 3.6 4.1 4.8"/><path d="M11 5c-.8 2.8-2.4 5-5 6.5"/><path d="M13 19l4-9 4 9"/><path d="M14.5 16h5"/>',
      sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/>',
      moon: '<path d="M20.5 14.5A8.5 8.5 0 0 1 9.5 3.5a7 7 0 1 0 11 11z"/>',
      power: '<path d="M12 2v10"/><path d="M6.3 6.3a8 8 0 1 0 11.4 0"/>',
      "timer-short": '<circle cx="12" cy="13" r="7"/><path d="M12 13V9"/><path d="M12 13l3 2"/><path d="M9 2h6"/><path d="M12 2v3"/>',
      "timer-long": '<circle cx="12" cy="13" r="7"/><path d="M12 13V8"/><path d="M12 13h4"/><path d="M9 2h6"/><path d="M12 2v3"/><path d="M18.5 6.5l1.4-1.4"/>',
    };
    return `<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">${paths[name] || paths.language}</svg>`;
  }

  function handleGlobalKeydown(event) {
    if (event.defaultPrevented || event.ctrlKey || event.metaKey || event.altKey) return;
    if (isTextEntry(event.target)) {
      if (event.key === "Escape") {
        clearCurrentSearch();
        event.preventDefault();
      }
      return;
    }
    if (SECTION_HOTKEYS[event.key]) {
      event.preventDefault();
      activateSection(SECTION_HOTKEYS[event.key]);
      focusActiveNav();
      return;
    }
    if (event.key === "[" || event.key === "]") {
      event.preventDefault();
      activateAdjacentSection(event.key === "]" ? 1 : -1);
      focusActiveNav();
      return;
    }
    const key = event.key.toLowerCase();
    if (key === "/") {
      event.preventDefault();
      focusSectionSearch();
      return;
    }
    if (key === "a") {
      event.preventDefault();
      focusFirstRailAction();
    }
  }

  function isTextEntry(target) {
    if (!target) return false;
    const tag = String(target.tagName || "").toLowerCase();
    return tag === "input" || tag === "textarea" || tag === "select" || Boolean(target.isContentEditable);
  }

  function activateAdjacentSection(step) {
    const current = SECTION_IDS.indexOf(state.section);
    const index = current >= 0 ? current : 0;
    const next = (index + step + SECTION_IDS.length) % SECTION_IDS.length;
    activateSection(SECTION_IDS[next]);
  }

  function focusActiveNav() {
    const button = document.querySelector(`[data-section="${state.section}"]`);
    if (button) button.focus({ preventScroll: true });
  }

  function focusSectionSearch() {
    const search = currentSearchInput();
    if (search) {
      search.focus({ preventScroll: true });
      search.select();
      return;
    }
    focusActiveNav();
  }

  function clearCurrentSearch() {
    const search = currentSearchInput();
    if (!search || !search.value) return;
    search.value = "";
    if (state.section === "projects") {
      state.projectQuery = "";
      renderProjects();
      return;
    }
    if (state.section === "worktrees") {
      state.worktreeQuery = "";
      renderWorktrees();
      return;
    }
    if (state.section === "logs") {
      state.logQuery = "";
      renderLogEntries();
    }
  }

  function currentSearchInput() {
    if (state.section === "projects") return els["projects-search"];
    if (state.section === "worktrees") return els["worktrees-search"];
    if (state.section === "logs") return els["logs-search"];
    return null;
  }

  function focusFirstRailAction() {
    const action = els["rail-actions-list"].querySelector(".rail-action");
    if (action) action.focus({ preventScroll: true });
  }

  function applyTheme() {
    document.documentElement.dataset.theme = state.theme === "light" ? "light" : "dark";
    setModeButton("theme", state.theme === "light" ? "sun" : "moon", state.theme === "light" ? t("ui.light") : t("ui.dark"), state.theme);
  }

  function syncInterval() {
    if (state.refreshTimer) {
      clearInterval(state.refreshTimer);
      state.refreshTimer = null;
    }
    const ms = Number(state.interval || 0);
    if (Number.isFinite(ms) && ms > 0) {
      state.refreshTimer = setInterval(() => refreshSnapshot(), ms);
    }
    const intervalMeta = intervalControlMeta();
    setModeButton("interval", intervalMeta.icon, intervalMeta.label, intervalMeta.value);
  }

  async function loadI18n() {
    try {
      const payload = await fetchJson("/static/i18n.json");
      state.i18n = payload && payload.en && payload.ru ? payload : state.i18n;
    } catch (error) {
      state.i18n.en = state.i18n.en || {};
      state.i18n.ru = state.i18n.ru || {};
    }
  }

  async function refreshSnapshot() {
    if (els.refresh) els.refresh.classList.add("is-busy");
    state.snapshotLoading = true;
    renderLoadingState();
    try {
      state.snapshotError = null;
      state.snapshot = await fetchJson("/api/snapshot");
    } catch (error) {
      state.snapshotError = error instanceof Error ? error.message : String(error);
    } finally {
      state.snapshotLoading = false;
      if (els.refresh) els.refresh.classList.remove("is-busy");
    }
    renderAll();
  }

  async function refreshLogsHealth() {
    try {
      state.logsHealth = await fetchJson("/api/logs/health");
      const sources = Array.isArray(state.logsHealth.sources) ? state.logsHealth.sources : [];
      if (!state.logSource) {
        state.logSource = state.logsHealth.default_source_id || (sources[0] && sources[0].id) || "";
      }
    } catch (error) {
      state.logsHealth = { ok: false, sources: [], error: String(error) };
    }
    renderLogSources();
    if (state.section === "logs") {
      await refreshLogTail(true);
    }
  }

  async function refreshLogTail(reset) {
    if (!state.logSource) {
      renderLogEntries([]);
      setPill(els["log-state"], t("common.na"), "info");
      return;
    }
    const query = new URLSearchParams({ source: state.logSource, limit: "80" });
    if (!reset && state.logCursor) query.set("since", state.logCursor);
    try {
      const payload = await fetchJson(`/api/logs/tail?${query.toString()}`);
      state.logCursor = payload.cursor || state.logCursor;
      setPill(els["log-state"], payload.state || "live", payload.ok ? toneFromState(payload.state) : "block");
      renderLogEntries(payload.entries || [], !reset);
    } catch (error) {
      setPill(els["log-state"], t("common.error"), "block");
      renderLogEntries([{ time: "", level: "error", text: String(error), raw: String(error) }], false);
    }
  }

  async function fetchJson(url) {
    const response = await fetch(url, { cache: "no-store" });
    if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
    return response.json();
  }

  function loadSavedViews() {
    const fallback = { projects: [], worktrees: [], logs: [] };
    try {
      const parsed = JSON.parse(localStorage.getItem(STORAGE.savedViews) || "{}");
      VIEW_SECTIONS.forEach((section) => {
        fallback[section] = Array.isArray(parsed[section]) ? parsed[section].slice(0, SAVED_VIEW_LIMIT) : [];
      });
    } catch (error) {
      return fallback;
    }
    return fallback;
  }

  function saveSavedViews() {
    try {
      localStorage.setItem(STORAGE.savedViews, JSON.stringify(state.savedViews));
    } catch (error) {
      // Browser storage can be disabled; saved views are a convenience layer only.
    }
  }

  function processI18nNodes() {
    document.documentElement.lang = state.lang;
    document.querySelectorAll("[data-i18n]").forEach((node) => {
      node.textContent = t(node.dataset.i18n);
    });
    document.querySelectorAll("[data-i18n-placeholder]").forEach((node) => {
      node.setAttribute("placeholder", t(node.dataset.i18nPlaceholder));
    });
  }

  function t(key) {
    return state.i18n[state.lang][key] || state.i18n.en[key] || key;
  }

  function renderAll() {
    document.body.dataset.snapshotLoading = state.snapshotLoading ? "true" : "false";
    renderTop();
    renderOverview();
    renderProjects();
    renderMemory();
    renderWorktrees();
    renderPublish();
    renderReview();
    renderSprint();
    renderLogSources();
    renderNavCounts();
    const railWasLoading = els["right-rail"]?.dataset.loading === "true";
    if (!els["rail-title"].dataset.bound) {
      setRail(defaultRail());
      els["rail-title"].dataset.bound = "1";
    } else if (railWasLoading) {
      setRail(state.railPayload || defaultRail());
    }
  }

  function snapshot() {
    return state.snapshot || {};
  }

  function renderLoadingState() {
    document.body.dataset.snapshotLoading = "true";
    renderTopSkeleton();
    skeletonList(els["kpi-grid"], 6, "kpi-card skeleton-card");
    skeletonList(els["command-center"], 4, "command-card skeleton-card");
    skeletonList(els["current-work-list"], 5, "work-card skeleton-card");
    skeletonList(els["attention-list"], 5, "attention-card skeleton-card");
    skeletonList(els["projects-table"], 5, "table-skeleton-row", 7);
    skeletonList(els["memory-panels"], 3, "info-card skeleton-card");
    skeletonList(els["worktrees-table"], 5, "table-skeleton-row", 6);
    skeletonList(els["publish-summary"], 3, "info-card skeleton-card");
    skeletonList(els["publish-gates"], 4, "info-card skeleton-card");
    skeletonList(els["review-list"], 4, "info-card skeleton-card");
    skeletonList(els["health-list"], 3, "info-card skeleton-card");
    renderRailSkeleton();
  }

  function renderTopSkeleton() {
    els["verdict-card"].dataset.loading = "true";
    els["verdict-card"].dataset.tone = "info";
    els["verdict-dot"].classList.add("is-skeleton");
    replaceChildren(els["verdict-title"], [skeletonLine("short")]);
    replaceChildren(els["verdict-note"], [skeletonLine("wide")]);

    [
      ["meta-branch", "medium"],
      ["meta-head", "short"],
      ["meta-sync", "short"],
      ["meta-age", "short"],
    ].forEach(([id, size]) => {
      els[id]?.closest(".repo-chip")?.setAttribute("data-loading", "true");
      replaceChildren(els[id], [skeletonLine(size)]);
    });

    [
      ["gate-continue", "gate-continue-note"],
      ["gate-publish", "gate-publish-note"],
      ["gate-cleanup", "gate-cleanup-note"],
    ].forEach(([gateId, noteId]) => {
      const gate = els[gateId];
      gate.dataset.loading = "true";
      gate.dataset.tone = "info";
      gate.querySelector(".gate-icon")?.classList.add("is-skeleton");
      replaceChildren(els[noteId], [skeletonLine("wide")]);
    });

    els["generated-at"]?.closest(".safety-status")?.setAttribute("data-loading", "true");
    replaceChildren(els["generated-at"], [skeletonLine("wide")]);
  }

  function renderRailSkeleton() {
    const rail = els["right-rail"];
    if (!rail) return;
    rail.dataset.loading = "true";
    rail.setAttribute("aria-busy", "true");
    els["rail-status"].textContent = "";
    els["rail-status"].classList.add("is-skeleton");
    replaceChildren(els["rail-title"], [skeletonLine("medium")]);
    replaceChildren(els["rail-subtitle"], [skeletonLine("wide")]);
    replaceChildren(els["rail-fields"], Array.from({ length: 5 }, () => {
      const row = document.createElement("div");
      const dt = document.createElement("dt");
      const dd = document.createElement("dd");
      dt.appendChild(skeletonLine("short"));
      dd.appendChild(skeletonLine("medium"));
      row.append(dt, dd);
      return row;
    }));
    const actions = Array.from({ length: 2 }, () => {
      const node = document.createElement("article");
      node.className = "rail-action skeleton-card";
      node.setAttribute("aria-hidden", "true");
      node.append(skeletonLine("medium"), skeletonLine("short"), skeletonLine("wide"));
      return node;
    });
    replaceChildren(els["rail-actions-list"], actions);
  }

  function skeletonList(node, count, className, cells) {
    if (!node) return;
    const items = Array.from({ length: count }, (_, index) => {
      if (cells) {
        const row = document.createElement("tr");
        row.className = className;
        row.style.setProperty("--i", String(index));
        Array.from({ length: cells }, () => {
          const cell = document.createElement("td");
          const line = document.createElement("span");
          line.className = "skeleton-line";
          cell.appendChild(line);
          row.appendChild(cell);
        });
        return row;
      }
      const item = document.createElement("article");
      item.className = className;
      item.style.setProperty("--i", String(index));
      item.setAttribute("aria-hidden", "true");
      item.append(skeletonLine("wide"), skeletonLine("medium"), skeletonLine("short"));
      return item;
    });
    node.replaceChildren(...items);
  }

  function skeletonLine(size) {
    const line = document.createElement("span");
    line.className = `skeleton-line skeleton-line-${size}`;
    return line;
  }

  function projects() {
    return Array.isArray(snapshot().projects) ? snapshot().projects : [];
  }

  function kpi() {
    return snapshot().kpi || {};
  }

  function reefiki() {
    return snapshot().reefiki || {};
  }

  function rootProject() {
    const root = normalizePath(snapshot().reefiki_root || "");
    return projects().find((project) => normalizePath(project.path || "") === root)
      || projects().find((project) => String(project.name || "").toLowerCase() === "reefiki")
      || null;
  }

  function deriveVerdict() {
    if (state.snapshotError) return { tone: "block", label: t("status.block"), note: state.snapshotError };
    if (!state.snapshot) return { tone: "warn", label: t("status.loading"), note: t("top.loading") };
    const dirty = Number(kpi().dirty || 0);
    const warnings = Number(kpi().warnings || 0);
    const codexBranches = Number(kpi().codex_branches || 0);
    if (dirty > 0) {
      return { tone: "warn", label: t("status.warn"), note: t("verdict.dirty").replace("{count}", dirty) };
    }
    if (warnings > 0 || codexBranches > 0) {
      return { tone: "warn", label: t("status.warn"), note: t("verdict.review").replace("{count}", warnings + codexBranches) };
    }
    return { tone: "pass", label: t("status.pass"), note: t("verdict.clean") };
  }

  function renderTop() {
    const verdict = deriveVerdict();
    els["verdict-card"].dataset.loading = "false";
    els["verdict-card"].dataset.tone = verdict.tone;
    els["verdict-dot"].classList.remove("is-skeleton");
    els["verdict-dot"].dataset.tone = verdict.tone;
    els["verdict-title"].textContent = verdict.label;
    els["verdict-note"].textContent = verdict.note;
    els["verdict-card"].setAttribute("aria-label", `${verdict.label}: ${verdict.note}`);

    const root = rootProject();
    els["meta-branch"].textContent = root && root.branch ? root.branch : t("common.na");
    els["meta-head"].textContent = root && root.head ? `@${root.head}` : "--";
    const ahead = root && Number.isFinite(Number(root.ahead)) ? Number(root.ahead) : 0;
    const behind = root && Number.isFinite(Number(root.behind)) ? Number(root.behind) : 0;
    els["meta-sync"].textContent = `+${ahead} -${behind}`;
    els["meta-age"].textContent = snapshot().generated_at ? ageText(snapshot().generated_at) : "--";
    els["generated-at"].textContent = snapshot().generated_at ? formatLogTimestamp(snapshot().generated_at) : t("common.na");
    ["meta-branch", "meta-head", "meta-sync", "meta-age"].forEach((id) => {
      els[id]?.closest(".repo-chip")?.setAttribute("data-loading", "false");
    });
    els["generated-at"]?.closest(".safety-status")?.setAttribute("data-loading", "false");

    const dirty = Number(kpi().dirty || 0);
    const warnings = Number(kpi().warnings || 0);
    const codexBranches = Number(kpi().codex_branches || 0);
    const continueTone = state.snapshotError ? "block" : dirty || warnings ? "warn" : "pass";
    const publishTone = dirty || warnings || codexBranches ? "block" : "pass";
    const cleanupTone = dirty ? "block" : "info";
    setGate("gate-continue", "gate-continue-note", continueTone, dirty ? t("gate.continueDirty") : t("gate.continueOk"));
    setGate("gate-publish", "gate-publish-note", publishTone, publishTone === "pass" ? t("gate.publishDryRun") : t("gate.publishBlocked"));
    setGate("gate-cleanup", "gate-cleanup-note", cleanupTone, dirty ? t("gate.cleanupBlocked") : t("gate.cleanupEvidence"));
  }

  function setGate(gateId, noteId, tone, note) {
    const gate = els[gateId];
    gate.dataset.loading = "false";
    gate.dataset.tone = tone;
    gate.querySelector(".gate-icon")?.classList.remove("is-skeleton");
    els[noteId].textContent = note;
    const label = gate.querySelector("strong")?.textContent || gateId;
    gate.setAttribute("aria-label", `${label}: ${note}`);
  }

  function renderOverview() {
    const total = Number(kpi().total || 0);
    els["overview-summary"].textContent = state.snapshotError
      ? state.snapshotError
      : t("overview.summary").replace("{total}", total).replace("{dirty}", Number(kpi().dirty || 0));
    replaceChildren(els["kpi-grid"], [
      kpiCard(t("kpi.projects"), total, t("kpi.projectsNote")),
      kpiCard(t("kpi.clean"), Number(kpi().clean || 0), t("kpi.cleanNote")),
      kpiCard(t("kpi.dirty"), Number(kpi().dirty || 0), t("kpi.dirtyNote")),
      kpiCard(t("kpi.codex"), Number(kpi().codex_branches || 0), t("kpi.codexNote")),
      kpiCard(t("kpi.connected"), Number(kpi().connected || 0), t("kpi.connectedNote")),
      kpiCard(t("kpi.warnings"), Number(kpi().warnings || 0), t("kpi.warningsNote")),
    ]);
    renderCommandCenter();

    const current = Array.isArray(snapshot().current_work) ? snapshot().current_work : [];
    els["current-work-count"].textContent = String(current.length);
    replaceChildren(els["current-work-list"], current.length ? current.map(projectCard) : [emptyCard(t("empty.currentWork"))]);

    const attention = projects().filter((project) => project.dirty || (project.warnings || []).length || !project.gates?.tests);
    els["attention-count"].textContent = String(attention.length);
    replaceChildren(els["attention-list"], attention.length ? attention.map(attentionCard) : [emptyCard(t("empty.attention"))]);
  }

  function kpiCard(label, value, note) {
    const node = template("tpl-kpi");
    node.querySelector('[data-field="label"]').textContent = label;
    node.querySelector('[data-field="value"]').textContent = String(value);
    node.querySelector('[data-field="note"]').textContent = note;
    return node;
  }

  function projectCard(project) {
    const tone = projectTone(project);
    const node = cardNode({
      title: project.name || t("common.unnamed"),
      status: statusLabel(tone),
      tone,
      body: readiness(project),
      meta: `${project.branch || t("common.na")} ${project.head ? "@" + project.head : ""}`,
    });
    attachWarningAccordion(node, project, "current");
    makeSelectable(node, () => setRail(projectRail(project)));
    return node;
  }

  function attentionCard(project) {
    const reasons = projectIssues(project).slice(0, 3).map((issue) => issue.title);
    const node = cardNode({
      title: project.name || t("common.unnamed"),
      status: statusLabel(projectTone(project)),
      tone: projectTone(project),
      body: reasons.join("; ") || readiness(project),
      meta: commandConnect(project),
    });
    attachWarningAccordion(node, project, "attention");
    makeSelectable(node, () => setRail(projectRail(project)));
    return node;
  }

  function renderCommandCenter() {
    const verdict = deriveVerdict();
    const dirty = Number(kpi().dirty || 0);
    const warnings = Number(kpi().warnings || 0);
    const codexBranches = Number(kpi().codex_branches || 0);
    const blockers = [];
    if (dirty) blockers.push(t("overview.blockDirty").replace("{count}", dirty));
    if (warnings) blockers.push(t("overview.blockWarnings").replace("{count}", warnings));
    if (codexBranches) blockers.push(t("overview.blockCodex").replace("{count}", codexBranches));
    const root = rootProject();
    const cards = [
      commandCard({
        title: t("overview.nextSafeAction"),
        status: statusLabel(verdict.tone),
        tone: verdict.tone,
        body: nextSafeActionText(dirty, warnings, codexBranches),
        meta: t("overview.nextSafeMeta"),
        section: verdict.tone === "pass" ? "publish" : "projects",
      }),
      commandCard({
        title: t("overview.blockingGates"),
        status: blockers.length ? statusLabel("warn") : statusLabel("pass"),
        tone: blockers.length ? "warn" : "pass",
        body: blockers.join("; ") || t("overview.noBlockers"),
        meta: blockers.length ? t("overview.openAttentionMeta") : t("overview.openPublishMeta"),
        section: blockers.length ? "projects" : "publish",
      }),
      commandCard({
        title: t("overview.snapshotScope"),
        status: t("status.info"),
        tone: "info",
        body: `${snapshot().schema_version || t("common.na")} · ${snapshot().generated_at ? ageText(snapshot().generated_at) : t("common.na")}`,
        meta: root ? `${root.branch || t("common.na")} ${root.head ? "@" + root.head : ""}` : t("common.na"),
        section: "logs",
      }),
      commandCard({
        title: t("overview.worktreeReview"),
        status: statusLabel(worktreeOverallTone()),
        tone: worktreeOverallTone(),
        body: t("overview.worktreeReviewBody").replace("{count}", String(projects().filter(worktreeNeedsReview).length)),
        meta: t("overview.openWorktreesMeta"),
        section: "worktrees",
      }),
    ];
    replaceChildren(els["command-center"], cards);
  }

  function commandCard({ title, status, tone, body, meta, section }) {
    const node = cardNode({ title, status, tone, body, meta });
    node.classList.add("command-card");
    makeSelectable(node, () => activateSection(section));
    return node;
  }

  function nextSafeActionText(dirty, warnings, codexBranches) {
    if (dirty) return t("overview.nextReviewDirty").replace("{count}", dirty);
    if (warnings || codexBranches) {
      return t("overview.nextReviewSignals")
        .replace("{warnings}", warnings)
        .replace("{codex}", codexBranches);
    }
    return t("overview.nextReady");
  }

  function renderProjects() {
    renderProjectViews();
    renderProjectFilters();
    const rows = filteredProjects().map((project) => {
      const row = template("tpl-row");
      row.querySelector('[data-field="name"]').textContent = project.name || t("common.unnamed");
      row.querySelector('[data-field="branch"]').textContent = project.branch || t("common.na");
      row.querySelector('[data-field="state"]').appendChild(pill(project.dirty ? t("state.dirty") : t("state.clean"), project.dirty ? "warn" : "pass"));
      row.querySelector('[data-field="reefiki"]').textContent = project.reefiki_mapping?.mapping_status || t("common.na");
      row.querySelector('[data-field="stack"]').textContent = (project.detected_stack || []).join(", ") || t("common.na");
      row.querySelector('[data-field="last"]').textContent = project.last_activity?.iso ? ageText(project.last_activity.iso) : t("common.na");
      row.querySelector('[data-field="gates"]').textContent = gatesText(project);
      makeSelectable(row, () => setRail(projectRail(project)));
      return row;
    });
    replaceChildren(els["projects-table"], rows.length ? rows : [tableEmptyRow(7, projects().length ? t("empty.projectsFiltered") : t("empty.projects"))]);
  }

  function renderProjectViews() {
    renderViewControls("projects", els["projects-views"], [
      viewDef("all", t("views.projectsAll"), "all", ""),
      viewDef("attention", t("views.projectsAttention"), "attention", ""),
      viewDef("task", t("views.projectsTasks"), "codex", ""),
      viewDef("mapping", t("views.projectsMapping"), "missing", ""),
    ]);
  }

  function renderProjectFilters() {
    const list = projects();
    const defs = [
      filterDef("all", t("filter.all"), list.length, "info"),
      filterDef("attention", t("filter.attention"), list.filter(projectNeedsAttention).length, list.some(projectNeedsAttention) ? "warn" : "pass"),
      filterDef("dirty", t("filter.dirty"), list.filter((project) => project.dirty).length, list.some((project) => project.dirty) ? "warn" : "pass"),
      filterDef("connected", t("filter.connected"), list.filter((project) => project.reefiki_mapping?.mapping_status === "connected").length, "pass"),
      filterDef("missing", t("filter.missing"), list.filter((project) => project.reefiki_mapping?.mapping_status === "missing" || project.reefiki_mapping?.mapping_status === "ambiguous").length, "warn"),
      filterDef("codex", t("filter.codex"), list.filter((project) => String(project.branch || "").startsWith("codex/")).length, "info"),
    ];
    renderFilters(els["projects-filters"], defs, state.projectFilter, (id) => {
      state.projectFilter = id;
      renderProjects();
    });
  }

  function filteredProjects() {
    return projects().filter((project) => {
      if (state.projectFilter === "attention") return projectNeedsAttention(project);
      if (state.projectFilter === "dirty") return project.dirty;
      if (state.projectFilter === "connected") return project.reefiki_mapping?.mapping_status === "connected";
      if (state.projectFilter === "missing") return project.reefiki_mapping?.mapping_status === "missing" || project.reefiki_mapping?.mapping_status === "ambiguous";
      if (state.projectFilter === "codex") return String(project.branch || "").startsWith("codex/");
      return true;
    }).filter((project) => textMatches(projectSearchText(project), state.projectQuery));
  }

  function renderMemory() {
    const snapshotState = memorySnapshotState();
    const memory = memoryPayload();
    renderMemoryNotice(snapshotState);
    renderMemoryTopology(memory, snapshotState);
    renderMemoryInsights(memory, snapshotState);
    if (!snapshotState.available) {
      replaceChildren(els["memory-panels"], memoryFallbackCards(snapshotState));
      return;
    }
    const providers = memory.providers || {};
    const queues = memory.review_queues || {};
    const promotion = memory.promotion_inbox || {};
    const graphify = memory.graphify || {};
    const cards = [
      memoryCard({
        title: "memoir",
        body: t("memory.memoirRole"),
        meta: memoryProviderMeta(providers.memoir),
        tone: memoryProviderTone(providers.memoir),
        fields: memoryProviderFields("memoir", providers.memoir, memory),
      }),
      memoryCard({
        title: "REEFIKI wiki",
        body: t("memory.reefikiRole"),
        meta: `${memoryProviderMeta(providers.reefiki)} · ${t("memory.reviewQueues")}: ${queues.total ?? t("common.na")} · ${t("memory.promotionInbox")}: ${promotion.active ?? t("common.na")} ${t("memory.active")}`,
        tone: memory.has_open ? "warn" : memoryProviderTone(providers.reefiki),
        fields: memoryProviderFields("reefiki", providers.reefiki, memory).concat([
          [t("memory.reviewQueues"), reviewQueueSummary(queues)],
          [t("memory.promotionInbox"), promotionSummary(promotion)],
        ]),
      }),
      memoryCard({
        title: "graphify",
        body: t("memory.graphifyRole"),
        meta: `${memoryProviderMeta(providers.graphify)} · ${t("memory.graphArtifact")}: ${graphify.status || t("common.na")}`,
        tone: graphifyTone(providers.graphify, graphify),
        fields: memoryProviderFields("graphify", providers.graphify, memory).concat([
          [t("memory.graphArtifact"), graphify.status || t("common.na")],
          [t("field.path"), graphify.graph_path || graphify.report_path || t("common.na")],
          [t("memory.nextAction"), graphify.next_action || memory.next_action || t("common.na")],
        ]),
      }),
    ];
    replaceChildren(els["memory-panels"], cards);
  }

  function memorySnapshotState() {
    const memory = snapshot().memory;
    if (!memory) {
      return {
        available: false,
        tone: "warn",
        title: t("memory.snapshotMissingTitle"),
        reason: t("memory.snapshotMissingReason"),
        next: t("memory.snapshotMissingNext"),
      };
    }
    if (memory.outcome !== "pass") {
      return {
        available: false,
        tone: "block",
        title: t("memory.snapshotErrorTitle"),
        reason: memory.error || t("common.error"),
        next: t("memory.snapshotMissingNext"),
      };
    }
    return {
      available: true,
      tone: memoryOverallTone(),
      title: t("memory.statusFromSnapshot"),
      reason: t("memory.statusFromSnapshotDetail"),
      next: memory.payload?.next_action || t("common.na"),
    };
  }

  function memoryPayload() {
    const memory = snapshot().memory || {};
    return memory.outcome === "pass" && memory.payload ? memory.payload : {};
  }

  function renderMemoryNotice(snapshotState) {
    const node = els["memory-notice"];
    if (!node) return;
    node.hidden = snapshotState.available;
    if (snapshotState.available) {
      node.replaceChildren();
      return;
    }
    const title = document.createElement("strong");
    title.textContent = snapshotState.title;
    const reason = document.createElement("p");
    reason.textContent = snapshotState.reason;
    const next = document.createElement("code");
    next.textContent = snapshotState.next;
    node.dataset.tone = snapshotState.tone;
    replaceChildren(node, [title, reason, next]);
  }

  function memoryFallbackCards(snapshotState) {
    return [
      ["memoir", t("memory.memoirRole")],
      ["REEFIKI wiki", t("memory.reefikiRole")],
      ["graphify", t("memory.graphifyRole")],
    ].map(([title, body]) => memoryCard({
      title,
      body,
      meta: snapshotState.title,
      tone: snapshotState.tone,
      fields: [
        [t("field.status"), snapshotState.title],
        [t("memory.reason"), snapshotState.reason],
        [t("memory.nextAction"), snapshotState.next],
        [t("field.snapshot"), snapshot().schema_version || t("common.na")],
      ],
    }));
  }

  function renderMemoryTopology(memory, snapshotState) {
    const node = els["memory-topology"];
    if (!node) return;
    const providers = memory.providers || {};
    const graphify = memory.graphify || {};
    const queues = memory.review_queues || {};
    const promotion = memory.promotion_inbox || {};
    const flow = [
      memoryFlowNode(t("memory.flowCapture"), t("memory.flowCaptureDetail"), "info", [
        [t("field.source"), t("memory.flowCaptureSource")],
        [t("field.execution"), t("memory.noRuntimeCalls")],
      ]),
      memoryFlowNode("memoir", memoryProviderMeta(providers.memoir), snapshotState.available ? memoryProviderTone(providers.memoir) : snapshotState.tone, memoryProviderFields("memoir", providers.memoir, memory)),
      memoryFlowNode("REEFIKI wiki", `${memoryProviderMeta(providers.reefiki)} · ${t("memory.reviewQueues")}: ${queues.total ?? t("common.na")}`, snapshotState.available && memory.has_open ? "warn" : snapshotState.available ? memoryProviderTone(providers.reefiki) : snapshotState.tone, memoryProviderFields("reefiki", providers.reefiki, memory).concat([
        [t("memory.reviewQueues"), reviewQueueSummary(queues)],
        [t("memory.promotionInbox"), promotionSummary(promotion)],
      ])),
      memoryFlowNode("graphify", `${memoryProviderMeta(providers.graphify)} · ${t("memory.graphArtifact")}: ${graphify.status || t("common.na")}`, snapshotState.available ? graphifyTone(providers.graphify, graphify) : snapshotState.tone, memoryProviderFields("graphify", providers.graphify, memory).concat([
        [t("memory.graphArtifact"), graphify.status || t("common.na")],
        [t("memory.changedFiles"), graphify.changed_files_since_build ?? t("common.na")],
      ])),
      memoryFlowNode(t("memory.flowQuery"), t("memory.flowQueryDetail"), "info", [
        [t("field.command"), "memory route / lookup / pack / promote"],
        [t("field.limits"), t("memory.noRuntimeCalls")],
      ]),
    ];
    const card = document.createElement("article");
    card.className = "memory-topology-card";
    const header = document.createElement("div");
    header.className = "memory-block-head";
    const title = document.createElement("strong");
    title.textContent = t("memory.topologyTitle");
    const note = document.createElement("span");
    note.textContent = t("memory.topologyNote");
    header.append(title, note);
    const grid = document.createElement("div");
    grid.className = "memory-flow";
    flow.forEach((item, index) => {
      const flowNode = document.createElement("button");
      flowNode.className = "memory-flow-node";
      flowNode.type = "button";
      flowNode.dataset.tone = item.tone;
      const label = document.createElement("strong");
      label.textContent = item.title;
      const detail = document.createElement("span");
      detail.textContent = item.detail;
      flowNode.append(label, detail);
      makeSelectable(flowNode, () => setRail({
        title: item.title,
        status: item.tone,
        subtitle: item.detail,
        fields: item.fields.concat([
          [t("field.snapshot"), snapshot().schema_version || t("common.na")],
          [t("memory.nextAction"), memory.next_action || snapshotState.next || t("common.na")],
        ]),
        actions: [
          copyAction(t("action.memoryStatus"), t("action.copyOnly"), "python scripts\\reefiki.py memory status --project reefiki --format json"),
        ],
      }));
      grid.appendChild(flowNode);
      if (index < flow.length - 1) {
        const arrow = document.createElement("span");
        arrow.className = "memory-flow-arrow";
        arrow.textContent = ">";
        grid.appendChild(arrow);
      }
    });
    card.append(header, grid);
    replaceChildren(node, [card]);
  }

  function memoryFlowNode(title, detail, tone, fields) {
    return { title, detail, tone, fields: fields || [] };
  }

  function renderMemoryInsights(memory, snapshotState) {
    const node = els["memory-insights"];
    if (!node) return;
    const graphify = memory.graphify || {};
    const queues = memory.review_queues || {};
    const promotion = memory.promotion_inbox || {};
    const limits = memory.dashboard_limits || {};
    const cards = [
      memoryInsightCard(
        t("memory.graphFreshness"),
        graphify.status || snapshotState.title,
        snapshotState.available ? graphifyTone((memory.providers || {}).graphify, graphify) : snapshotState.tone,
        [
          [t("memory.artifactStatus"), graphify.status || t("common.na")],
          [t("memory.builtCommit"), shortSha(graphify.built_at_commit)],
          [t("memory.currentHead"), shortSha(graphify.current_head)],
          [t("memory.changedFiles"), graphify.changed_files_since_build ?? t("common.na")],
          [t("memory.reportPath"), graphify.report_path || t("common.na")],
          [t("memory.graphPath"), graphify.graph_path || t("common.na")],
        ],
        graphify.next_action || memory.next_action || t("common.na"),
      ),
      memoryInsightCard(
        t("memory.wikiHygiene"),
        reviewQueueSummary(queues),
        memory.has_open ? "warn" : "pass",
        [
          [t("memory.reviewQueues"), reviewQueueSummary(queues)],
          [t("memory.promotionInbox"), promotionSummary(promotion)],
          [t("memory.hasOpen"), memory.has_open == null ? t("common.na") : String(Boolean(memory.has_open))],
        ],
        memory.next_action || t("common.na"),
      ),
      memoryInsightCard(
        t("memory.dashboardBoundary"),
        t("memory.noRuntimeCalls"),
        "info",
        [
          [t("memory.dashboardLimits"), limitSummary(limits)],
          [t("memory.providerLookup"), limits.provider_lookup || "skipped"],
          [t("memory.golden"), limits.memory_golden || "skipped"],
          [t("memory.graphifyRebuild"), limits.graphify_rebuild || "skipped"],
        ],
        t("memory.copyOnlyBoundary"),
      ),
    ];
    replaceChildren(node, cards);
  }

  function memoryInsightCard(title, summary, tone, fields, nextAction) {
    const card = document.createElement("article");
    card.className = "memory-insight";
    card.dataset.tone = tone || "info";
    const head = document.createElement("div");
    head.className = "memory-block-head";
    const titleNode = document.createElement("strong");
    titleNode.textContent = title;
    head.append(titleNode, pill(statusLabel(tone), tone));
    const summaryNode = document.createElement("p");
    summaryNode.textContent = summary || t("common.na");
    const list = document.createElement("dl");
    list.className = "memory-field-list";
    fields.forEach(([label, value]) => {
      const wrap = document.createElement("div");
      const dt = document.createElement("dt");
      const dd = document.createElement("dd");
      dt.textContent = label;
      dd.textContent = value == null || value === "" ? t("common.na") : String(value);
      wrap.append(dt, dd);
      list.appendChild(wrap);
    });
    makeSelectable(card, () => setRail({
      title,
      status: tone,
      subtitle: summary,
      fields: fields.concat([[t("memory.nextAction"), nextAction || t("common.na")]]),
      actions: [
        copyAction(t("action.memoryStatus"), t("action.copyOnly"), "python scripts\\reefiki.py memory status --project reefiki --format json"),
      ],
    }));
    card.append(head, summaryNode, list);
    return card;
  }

  function shortSha(value) {
    return value ? String(value).slice(0, 8) : t("common.na");
  }

  function memoryProviderMeta(provider) {
    if (!provider) return t("common.na");
    return `${t("memory.providerStatus")}: ${provider.status || t("common.na")} · ${t("memory.kind")}: ${provider.kind || t("common.na")}`;
  }

  function memoryProviderFields(id, provider, memory) {
    return [
      [t("field.status"), provider?.status || t("common.na")],
      [t("memory.kind"), provider?.kind || t("common.na")],
      [t("memory.capabilities"), listText(provider?.capabilities)],
      [t("field.path"), provider?.root || t("common.na")],
      [t("memory.policy"), memory.policy?.outcome || t("common.na")],
      [t("memory.dashboardLimits"), limitSummary(memory.dashboard_limits)],
    ];
  }

  function memoryProviderTone(provider) {
    const status = normalizeSearch(provider?.status);
    if (status === "available" || status === "pass" || status === "ok") return "pass";
    if (status.includes("error") || status.includes("fail")) return "block";
    if (status.includes("missing") || status.includes("stale") || status.includes("warn")) return "warn";
    return "info";
  }

  function graphifyTone(provider, graphify) {
    const status = normalizeSearch(graphify?.status);
    if (status.includes("stale") || status.includes("missing")) return "warn";
    if (status.includes("error") || status.includes("fail")) return "block";
    return memoryProviderTone(provider);
  }

  function reviewQueueSummary(queues) {
    if (!queues || queues.error) return queues?.error || t("common.na");
    const counts = queues.counts || {};
    const details = Object.entries(counts).map(([key, value]) => `${key}: ${value}`).join("; ");
    return `${t("memory.total")}: ${queues.total ?? 0}${details ? ` · ${details}` : ""}`;
  }

  function promotionSummary(promotion) {
    if (!promotion || promotion.error) return promotion?.error || t("common.na");
    return `${t("memory.active")}: ${promotion.active ?? 0} · ${t("memory.closed")}: ${promotion.closed ?? 0} · ${t("memory.total")}: ${promotion.total ?? 0}`;
  }

  function limitSummary(limits) {
    if (!limits) return t("memory.noRuntimeCalls");
    return Object.entries(limits).map(([key, value]) => `${key}: ${value}`).join("; ");
  }

  function listText(items) {
    return Array.isArray(items) && items.length ? items.join(", ") : t("common.na");
  }

  function memoryCard({ title, body, meta, tone, fields }) {
    const node = cardNode({ title, status: statusLabel(tone), tone, body, meta });
    makeSelectable(node, () => setRail({
      title,
      status: tone,
      subtitle: body,
      fields: fields.concat([
        [t("field.snapshot"), snapshot().schema_version || t("common.na")],
        [t("memory.nextAction"), memoryPayload().next_action || t("common.na")],
      ]),
      actions: [
        copyAction(t("action.memoryStatus"), t("action.copyOnly"), "python scripts\\reefiki.py memory status --project reefiki --format json"),
      ],
    }));
    return node;
  }

  function renderWorktrees() {
    renderWorktreeViews();
    renderWorktreeFilters();
    const list = filteredWorktreeProjects();
    const tasks = list.filter(worktreeIsTaskSignal);
    const shared = list.filter((project) => !worktreeIsTaskSignal(project));
    const rows = [];
    if (shared.length) {
      rows.push(tableGroupRow(t("worktrees.sharedCheckout"), shared.length, "info"));
      rows.push(...shared.map(worktreeRow));
    }
    if (tasks.length) {
      rows.push(tableGroupRow(t("worktrees.taskBranches"), tasks.length, tasks.some((project) => project.dirty) ? "warn" : "info"));
      rows.push(...tasks.map(worktreeRow));
    }
    replaceChildren(els["worktrees-table"], rows.length ? rows : [tableEmptyRow(6, projects().length ? t("empty.worktreesFiltered") : t("empty.worktrees"))]);
  }

  function worktreeRow(project) {
    const row = document.createElement("tr");
    row.dataset.worktreeKind = worktreeIsTaskSignal(project) ? "task" : "shared";
    [
      project.name || t("common.unnamed"),
      String(project.worktree_count ?? t("common.na")),
      project.branch || t("common.na"),
      project.dirty ? `${project.dirty_paths_count || 0}` : "0",
      `+${project.ahead ?? 0} -${project.behind ?? 0}`,
      worktreeRecommendation(project),
    ].forEach((value) => {
      const cell = document.createElement("td");
      cell.textContent = value;
      row.appendChild(cell);
    });
    makeSelectable(row, () => setRail(projectRail(project)));
    return row;
  }

  function tableGroupRow(label, count, tone) {
    const row = document.createElement("tr");
    row.className = "table-group-row";
    const cell = document.createElement("td");
    cell.colSpan = 6;
    cell.append(pill(statusLabel(tone), tone), document.createTextNode(` ${label} · ${count}`));
    row.appendChild(cell);
    return row;
  }

  function renderWorktreeViews() {
    renderViewControls("worktrees", els["worktrees-views"], [
      viewDef("review", t("views.worktreesReview"), "review", ""),
      viewDef("dirty", t("views.worktreesDirty"), "dirty", ""),
      viewDef("tasks", t("views.worktreesTasks"), "task", ""),
      viewDef("clean", t("views.worktreesClean"), "clean", ""),
    ]);
  }

  function renderWorktreeFilters() {
    const list = projects();
    const defs = [
      filterDef("all", t("filter.all"), list.length, "info"),
      filterDef("review", t("filter.review"), list.filter(worktreeNeedsReview).length, list.some(worktreeNeedsReview) ? "warn" : "pass"),
      filterDef("dirty", t("filter.dirty"), list.filter((project) => project.dirty).length, list.some((project) => project.dirty) ? "warn" : "pass"),
      filterDef("task", t("filter.task"), list.filter((project) => String(project.branch || "").startsWith("codex/")).length, "info"),
      filterDef("parallel", t("filter.parallel"), list.filter((project) => Number(project.worktree_count || 0) > 1).length, "info"),
      filterDef("clean", t("filter.clean"), list.filter((project) => !project.dirty).length, "pass"),
    ];
    renderFilters(els["worktrees-filters"], defs, state.worktreeFilter, (id) => {
      state.worktreeFilter = id;
      renderWorktrees();
    });
  }

  function filteredWorktreeProjects() {
    return projects().filter((project) => {
      if (state.worktreeFilter === "review") return worktreeNeedsReview(project);
      if (state.worktreeFilter === "dirty") return project.dirty;
      if (state.worktreeFilter === "task") return String(project.branch || "").startsWith("codex/");
      if (state.worktreeFilter === "parallel") return Number(project.worktree_count || 0) > 1;
      if (state.worktreeFilter === "clean") return !project.dirty;
      return true;
    }).filter((project) => textMatches(worktreeSearchText(project), state.worktreeQuery));
  }

  function renderPublish() {
    renderPublishSummary();
    renderPublishClassification();
    const gates = [
      { title: t("gate.continue"), tone: Number(kpi().dirty || 0) ? "warn" : "pass", body: t("publish.continueBody") },
      { title: t("gate.publish"), tone: Number(kpi().dirty || 0) || Number(kpi().warnings || 0) ? "block" : "pass", body: t("publish.publishBody") },
      { title: t("gate.cleanup"), tone: Number(kpi().dirty || 0) ? "block" : "info", body: t("publish.cleanupBody") },
    ];
    replaceChildren(els["publish-gates"], gates.map((item) => {
      const node = cardNode({ title: item.title, status: statusLabel(item.tone), tone: item.tone, body: item.body, meta: t("publish.dashboardReadOnly") });
      makeSelectable(node, () => setRail(publishRail(item)));
      return node;
    }));
    const commands = [
      ["publish-task --dry-run", "python scripts\\reefiki.py publish-task --dry-run --cleanup --format json"],
      ["guard-staged", "python scripts\\reefiki.py guard-staged --target-project reefiki --mode code/docs --format json"],
      ["secret-scan changed paths", "python scripts\\reefiki.py secret-scan <changed paths> --format json"],
    ];
    replaceChildren(els["publish-commands"], commands.map(([label, command]) => {
      const node = cardNode({ title: label, status: t("common.copy"), tone: "info", body: t("publish.commandBody"), meta: command });
      makeSelectable(node, () => setRail(commandRail(label, command)));
      return node;
    }));
  }

  function renderPublishClassification() {
    const dirty = Number(kpi().dirty || 0);
    const warnings = Number(kpi().warnings || 0);
    const codexBranches = Number(kpi().codex_branches || 0);
    const cards = [
      publishMatrixCard(t("publish.matrixDryRun"), "info", t("publish.matrixDryRunBody"), t("publish.copyOnlyExecution"), copyAction(t("action.publishDryRun"), t("action.copyOnly"), "python scripts\\reefiki.py publish-task --dry-run --cleanup --format json")),
      publishMatrixCard(t("publish.matrixScope"), dirty || warnings || codexBranches ? "warn" : "pass", t("publish.matrixScopeBody").replace("{dirty}", dirty).replace("{warnings}", warnings).replace("{codex}", codexBranches), t("publish.snapshotDerived"), copyAction(t("action.inspectStatus"), t("action.copyOnly"), "git status --short --branch")),
      publishMatrixCard(t("publish.matrixDualRemote"), "info", t("publish.matrixDualRemoteBody"), t("publish.dryRunRequired"), copyAction(t("action.publishDryRun"), t("action.copyOnly"), "python scripts\\reefiki.py publish-task --dry-run --cleanup --format json")),
      publishMatrixCard(t("publish.matrixPublicPrivate"), "info", t("publish.matrixPublicPrivateBody"), t("publish.dryRunRequired"), copyAction(t("action.publishDryRun"), t("action.copyOnly"), "python scripts\\reefiki.py publish-task --dry-run --cleanup --format json")),
    ];
    replaceChildren(els["publish-classification"], cards);
  }

  function publishMatrixCard(title, tone, body, meta, action) {
    const node = cardNode({ title, status: statusLabel(tone), tone, body, meta });
    node.classList.add("signal-card");
    makeSelectable(node, () => setRail({
      title,
      status: tone,
      subtitle: body,
      fields: [
        [t("field.dashboardMode"), t("publish.readOnlyMode")],
        [t("field.status"), meta],
        [t("field.snapshot"), snapshot().schema_version || t("common.na")],
      ],
      actions: action ? [action] : [],
    }));
    return node;
  }

  function renderPublishSummary() {
    const dirty = Number(kpi().dirty || 0);
    const warnings = Number(kpi().warnings || 0);
    const cards = [
      publishSignalCard(
        t("publish.signalDirty"),
        dirty || warnings ? "warn" : "pass",
        dirty || warnings
          ? t("publish.signalDirtyBody").replace("{dirty}", dirty).replace("{warnings}", warnings)
          : t("publish.signalCleanBody"),
        t("publish.snapshotDerived"),
        "projects",
      ),
      publishSignalCard(
        t("publish.signalScope"),
        "info",
        t("publish.signalScopeBody"),
        t("publish.copyOnlyExecution"),
        "publish",
        copyAction(t("action.guardStaged"), t("action.copyOnly"), "python scripts\\reefiki.py guard-staged --target-project reefiki --mode code/docs --format json"),
      ),
      publishSignalCard(
        t("publish.signalSecretScan"),
        "info",
        t("publish.signalSecretScanBody"),
        t("publish.copyOnlyExecution"),
        "publish",
        copyAction(t("action.secretScan"), t("action.copyOnly"), "python scripts\\reefiki.py secret-scan <changed paths> --format json"),
      ),
      publishSignalCard(
        t("publish.signalPublicSnapshot"),
        "info",
        t("publish.signalPublicSnapshotBody"),
        t("publish.copyOnlyExecution"),
        "publish",
        copyAction(t("action.publishDryRun"), t("action.copyOnly"), "python scripts\\reefiki.py publish-task --dry-run --cleanup --format json"),
      ),
    ];
    replaceChildren(els["publish-summary"], cards);
  }

  function publishSignalCard(title, tone, body, meta, section, action) {
    const node = cardNode({ title, status: statusLabel(tone), tone, body, meta });
    node.classList.add("command-card");
    makeSelectable(node, () => setRail({
      title,
      status: tone,
      subtitle: body,
      fields: [
        [t("field.dashboardMode"), t("publish.readOnlyMode")],
        [t("field.snapshot"), snapshot().schema_version || t("common.na")],
        [t("field.section"), section],
      ],
      actions: action ? [action] : [copyAction(t("action.publishDryRun"), t("action.copyOnly"), "python scripts\\reefiki.py publish-task --dry-run --cleanup --format json")],
    }));
    return node;
  }

  function renderReview() {
    renderReviewHygiene();
    const queue = Array.isArray(reefiki().review_queue_top) ? reefiki().review_queue_top : [];
    replaceChildren(els["review-list"], queue.length ? queue.map(reviewQueueCard) : [emptyCard(t("empty.review"))]);

    const health = [
      [t("review.healthOutcome"), reefiki().health_outcome || t("common.na")],
      [t("review.memoryGolden"), reefiki().memory_golden_outcome || t("common.na")],
      [t("review.queueCount"), String(queue.length)],
    ];
    replaceChildren(els["health-list"], health.map(([title, body]) => reviewHealthCard(title, body)));
  }

  function renderReviewHygiene() {
    const memory = memoryPayload();
    const queues = memory.review_queues || {};
    const counts = queues.counts || {};
    const promotion = memory.promotion_inbox || {};
    const cards = [
      reviewHygieneCard(t("review.missingBacklinks"), counts.missing_backlink, "info", t("review.missingBacklinksBody")),
      reviewHygieneCard(t("review.conflicts"), counts.conflict_review, counts.conflict_review ? "block" : "pass", t("review.conflictsBody")),
      reviewHygieneCard(t("review.orphans"), counts.orphan_review, counts.orphan_review ? "warn" : "pass", t("review.orphansBody")),
      reviewHygieneCard(t("review.placeholders"), counts.placeholder_link, counts.placeholder_link ? "warn" : "pass", t("review.placeholdersBody")),
      reviewHygieneCard(t("review.promotionDrafts"), promotion.active, promotion.active ? "warn" : "pass", t("review.promotionDraftsBody")),
      reviewHygieneCard(t("review.noisyPages"), null, "info", t("review.noisyPagesUnavailable")),
    ];
    replaceChildren(els["review-hygiene"], cards);
  }

  function reviewHygieneCard(title, value, tone, body) {
    const label = value == null ? t("common.na") : String(value);
    const node = cardNode({ title, status: label, tone, body, meta: t("review.snapshotOnly") });
    node.classList.add("signal-card");
    makeSelectable(node, () => setRail({
      title,
      status: tone,
      subtitle: body,
      fields: [
        [t("field.status"), label],
        [t("field.source"), "memory status / review queues"],
        [t("field.snapshot"), snapshot().schema_version || t("common.na")],
      ],
      actions: [
        copyAction(t("action.reviewQueues"), t("action.copyOnly"), "python scripts\\reefiki.py --project projects/reefiki review-queues --summary"),
      ],
    }));
    return node;
  }

  function reviewQueueCard(item) {
    const title = item.title || item.page_id || item.path || t("review.item");
    const body = item.reason || item.message || item.type || t("review.noReason");
    const node = cardNode({ title, status: item.type || t("status.info"), tone: "warn", body, meta: item.path || t("common.na") });
    makeSelectable(node, () => setRail({
      title,
      status: "warn",
      subtitle: body,
      fields: [
        [t("field.status"), item.type || t("status.warn")],
        [t("field.path"), item.path || item.page_id || t("common.na")],
        [t("review.reason"), body],
        [t("field.snapshot"), snapshot().schema_version || t("common.na")],
      ],
      actions: [
        copyAction(t("action.reviewQueues"), t("action.copyOnly"), "python scripts\\reefiki.py --project projects/reefiki review-queues --summary"),
        copyAction(t("action.inspectTask"), t("action.copyOnly"), `rg -n "${escapeCommandText(item.path || item.page_id || title)}" projects/reefiki`),
      ],
    }));
    return node;
  }

  function reviewHealthCard(title, body) {
    const node = cardNode({
      title,
      status: t("status.info"),
      tone: "info",
      body,
      meta: t("review.snapshotOnly"),
    });
    makeSelectable(node, () => setRail({
      title,
      status: "info",
      subtitle: body,
      fields: [
        [t("field.status"), body],
        [t("field.snapshot"), snapshot().schema_version || t("common.na")],
        [t("field.source"), t("review.snapshotOnly")],
      ],
      actions: reviewHealthActions(title),
    }));
    return node;
  }

  function reviewHealthActions(title) {
    const normalized = normalizeSearch(title);
    if (normalized.includes("memory")) {
      return [copyAction(t("action.memoryStatus"), t("action.copyOnly"), "python scripts\\reefiki.py memory status --project reefiki --format json")];
    }
    if (normalized.includes("queue")) {
      return [copyAction(t("action.reviewQueues"), t("action.copyOnly"), "python scripts\\reefiki.py --project projects/reefiki review-queues --summary")];
    }
    return [copyAction(t("action.inspectStatus"), t("action.copyOnly"), "python scripts\\reefiki.py --project projects/reefiki status")];
  }

  function escapeCommandText(value) {
    return String(value || "").replace(/"/g, '\\"').slice(0, 120);
  }

  function renderSprint() {
    els["sprint-summary"].textContent = reefiki().current_sprint || t("common.na");
    renderSprintBurndown();
    const active = Array.isArray(reefiki().active_tasks) ? reefiki().active_tasks : [];
    const next = Array.isArray(reefiki().next_tasks) ? reefiki().next_tasks : [];
    replaceChildren(els["active-tasks"], active.length ? active.map(taskCard) : [emptyCard(t("empty.activeTasks"))]);
    replaceChildren(els["next-tasks"], next.length ? next.map(taskCard) : [emptyCard(t("empty.nextTasks"))]);
  }

  function renderSprintBurndown() {
    const counts = reefiki().task_counts || {};
    const done = Number(counts.done || 0);
    const active = Number(counts.active || 0);
    const queued = Number(counts.todo || 0);
    const total = Math.max(1, done + active + queued);
    const wrap = document.createElement("article");
    wrap.className = "sprint-burn-card";

    const head = document.createElement("div");
    head.className = "sprint-burn-head";
    const title = document.createElement("strong");
    title.textContent = t("sprint.burndown");
    const totalText = document.createElement("span");
    totalText.textContent = t("sprint.totalTasks").replace("{count}", String(done + active + queued));
    head.append(title, totalText);

    const bar = document.createElement("div");
    bar.className = "sprint-burn-bar";
    [
      ["done", done, "pass"],
      ["active", active, "warn"],
      ["todo", queued, "info"],
    ].forEach(([key, value, tone]) => {
      const segment = document.createElement("span");
      segment.dataset.tone = tone;
      segment.style.width = `${(Number(value) / total) * 100}%`;
      segment.title = `${t(`sprint.${key}`)}: ${value}`;
      bar.appendChild(segment);
    });

    const legend = document.createElement("div");
    legend.className = "sprint-burn-legend";
    [
      [t("sprint.done"), done, "pass"],
      [t("sprint.activeState"), active, "warn"],
      [t("sprint.queued"), queued, "info"],
    ].forEach(([label, value, tone]) => legend.appendChild(sprintLegendItem(label, value, tone)));

    const evidence = document.createElement("div");
    evidence.className = "sprint-evidence-strip";
    const latest = Array.isArray(reefiki().latest_log_entries) ? reefiki().latest_log_entries.slice(-3).reverse() : [];
    if (latest.length) {
      latest.forEach((entry) => {
        const chip = document.createElement("button");
        chip.type = "button";
        chip.className = "sprint-evidence-chip";
        chip.textContent = entry.heading || t("common.na");
        makeSelectable(chip, () => setRail({
          title: entry.heading || t("sprint.evidence"),
          status: "info",
          subtitle: entry.iso || t("common.na"),
          fields: [
            [t("field.source"), "projects/reefiki/wiki/log.md"],
            [t("field.snapshot"), snapshot().schema_version || t("common.na")],
            [t("sprint.evidence"), (entry.lines || []).join(" ") || t("common.na")],
          ],
          actions: [
            copyAction(t("action.inspectTask"), t("action.copyOnly"), `rg -n "${escapeCommandText(entry.heading || "")}" projects/reefiki/wiki/log.md`),
          ],
        }));
        evidence.appendChild(chip);
      });
    } else {
      const empty = document.createElement("span");
      empty.textContent = t("sprint.noEvidence");
      evidence.appendChild(empty);
    }

    wrap.append(head, bar, legend, evidence);
    replaceChildren(els["sprint-burndown"], [wrap]);
  }

  function sprintLegendItem(label, value, tone) {
    const item = document.createElement("span");
    item.className = "sprint-burn-item";
    item.append(pill(String(value), tone), document.createTextNode(` ${label}`));
    return item;
  }

  function taskCard(task) {
    const node = cardNode({
      title: `${task.id || "T-?"} ${task.title || ""}`.trim(),
      status: task.status || t("status.info"),
      tone: task.status === "done" ? "pass" : task.status === "active" ? "warn" : "info",
      body: (task.progress || task.closeout || [])[0] || t("sprint.taskNoDetail"),
      meta: reefiki().roadmap_phase || t("common.na"),
    });
    makeSelectable(node, () => setRail({
      title: task.id || t("sprint.task"),
      status: task.status === "done" ? "pass" : task.status === "active" ? "warn" : "info",
      subtitle: task.title || "",
      fields: [
        [t("field.status"), task.status || t("common.na")],
        [t("field.progress"), (task.progress || []).join("; ") || t("common.na")],
        [t("field.closeout"), (task.closeout || []).join("; ") || t("common.na")],
      ],
      actions: [
        copyAction(t("action.inspectTask"), t("action.copyOnly"), `rg -n "${task.id || ""}" TASKS.md projects/reefiki/wiki`),
      ],
    }));
    return node;
  }

  function renderLogSources() {
    const sources = state.logsHealth && Array.isArray(state.logsHealth.sources) ? state.logsHealth.sources : [];
    const options = sources.map((source) => {
      const option = document.createElement("option");
      option.value = source.id;
      option.textContent = `${source.label} (${source.state || "unknown"})`;
      return option;
    });
    if (!options.length) {
      const option = document.createElement("option");
      option.value = "";
      option.textContent = t("common.na");
      options.push(option);
    }
    replaceChildren(els["log-source"], options);
    els["log-source"].value = state.logSource || "";
    const source = sources.find((item) => item.id === state.logSource);
    setPill(els["log-state"], source ? source.state : t("common.na"), source ? toneFromState(source.state) : "info");
    renderLogViews();
    renderLogFilters();
  }

  function renderLogViews() {
    renderViewControls("logs", els["logs-views"], [
      viewDef("all", t("views.logsAll"), "all", ""),
      viewDef("errors", t("views.logsErrors"), "error", ""),
      viewDef("warnings", t("views.logsWarnings"), "warn", ""),
      viewDef("publish", t("views.logsPublish"), "all", "publish"),
      viewDef("dashboard", t("views.logsDashboard"), "all", "dashboard"),
    ]);
  }

  function renderLogFilters() {
    const entries = Array.isArray(state.logEntries) ? state.logEntries : [];
    const defs = [
      filterDef("all", t("filter.all"), entries.length, "info"),
      filterDef("error", t("filter.error"), entries.filter((entry) => logLevelBucket(entry) === "error").length, entries.some((entry) => logLevelBucket(entry) === "error") ? "block" : "pass"),
      filterDef("warn", t("filter.warn"), entries.filter((entry) => logLevelBucket(entry) === "warn").length, entries.some((entry) => logLevelBucket(entry) === "warn") ? "warn" : "pass"),
      filterDef("info", t("filter.info"), entries.filter((entry) => logLevelBucket(entry) === "info").length, "info"),
    ];
    renderFilters(els["logs-filters"], defs, state.logFilter, (id) => {
      state.logFilter = id;
      renderLogEntries();
    });
  }

  function renderLogEntries(entries, append) {
    if (Array.isArray(entries)) {
      state.logEntries = append ? state.logEntries.concat(entries).slice(-200) : entries;
    }
    renderLogViews();
    renderLogFilters();
    els["log-view"].replaceChildren();
    const visibleEntries = filteredLogEntries();
    const nodes = visibleEntries.map((entry, index) => logEntryNode(entry, index));
    if (!nodes.length) {
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.textContent = state.logEntries.length ? t("empty.logsFiltered") : t("empty.logs");
      nodes.push(empty);
    }
    els["log-view"].append(...nodes);
    if (Array.isArray(entries) && append) {
      els["log-view"].scrollTop = els["log-view"].scrollHeight;
    }
  }

  function logEntryNode(entry, index) {
    const key = logEntryKey(entry, index);
    const open = state.openLogKey === key;
    const wrap = document.createElement("article");
    wrap.className = "log-entry";
    wrap.dataset.open = open ? "true" : "false";

    const line = document.createElement("button");
    line.type = "button";
    line.className = "log-line";
    const time = document.createElement("span");
    time.textContent = formatLogTimestamp(entry.time || entry.iso);
    const level = document.createElement("span");
    level.className = "log-level-badge";
    level.dataset.level = logLevelBucket(entry);
    level.textContent = entry.level || "info";
    const message = document.createElement("span");
    message.textContent = entry.raw || entry.text || "";
    line.append(time, level, message);
    line.addEventListener("click", () => {
      state.openLogKey = open ? "" : key;
      setRail(logEntryRail(entry));
      renderLogEntries();
    });
    wrap.appendChild(line);

    if (open) {
      const panel = document.createElement("div");
      panel.className = "log-evidence-panel";
      [
        [t("logs.evidenceLevel"), entry.level || "info"],
        [t("logs.evidenceTime"), formatLogTimestamp(entry.time || entry.iso)],
        [t("logs.evidenceSource"), currentLogSourceLabel()],
        [t("logs.evidenceRedacted"), entry.redacted ? t("common.yes") : t("common.no")],
        [t("logs.evidenceRaw"), entry.raw || entry.text || t("common.na")],
      ].forEach(([label, value]) => {
        const row = document.createElement("div");
        row.append(document.createElement("span"), document.createElement("code"));
        row.firstChild.textContent = label;
        row.lastChild.textContent = value;
        panel.appendChild(row);
      });
      wrap.appendChild(panel);
    }
    return wrap;
  }

  function logEntryRail(entry) {
    return {
      title: entry.raw || entry.text || t("logs.entry"),
      status: logLevelBucket(entry) === "error" ? "block" : logLevelBucket(entry) === "warn" ? "warn" : "info",
      subtitle: `${currentLogSourceLabel()} · ${formatLogTimestamp(entry.time || entry.iso)}`,
      fields: [
        [t("logs.evidenceLevel"), entry.level || "info"],
        [t("logs.evidenceTime"), formatLogTimestamp(entry.time || entry.iso)],
        [t("logs.evidenceSource"), currentLogSourceLabel()],
        [t("logs.evidenceRedacted"), entry.redacted ? t("common.yes") : t("common.no")],
        [t("logs.evidenceRaw"), entry.raw || entry.text || t("common.na")],
      ],
      actions: [
        copyAction(t("action.refreshSnapshot"), t("action.copyOnly"), dashboardSnapshotCommand()),
      ],
    };
  }

  function logEntryKey(entry, index) {
    return `${entry.cursor || ""}:${index}:${entry.iso || entry.time || "log"}:${entry.raw || entry.text || ""}`;
  }

  function formatLogTimestamp(value) {
    const raw = String(value || "");
    const match = raw.match(/^(\d{4})-(\d{2})-(\d{2})[T\s](\d{2}):(\d{2})/);
    if (match) {
      return `${match[4]}:${match[5]} | ${match[3]}-${match[2]}-${match[1]}`;
    }
    return raw || t("common.na");
  }

  function currentLogSourceLabel() {
    const sources = state.logsHealth && Array.isArray(state.logsHealth.sources) ? state.logsHealth.sources : [];
    const source = sources.find((item) => item.id === state.logSource);
    return source ? `${source.label || source.id} (${source.state || "unknown"})` : state.logSource || t("common.na");
  }

  function filteredLogEntries() {
    return (Array.isArray(state.logEntries) ? state.logEntries : [])
      .filter((entry) => state.logFilter === "all" ? true : logLevelBucket(entry) === state.logFilter)
      .filter((entry) => textMatches(logSearchText(entry), state.logQuery));
  }

  function textMatches(text, query) {
    const needle = normalizeSearch(query);
    if (!needle) return true;
    return normalizeSearch(text).includes(needle);
  }

  function normalizeSearch(value) {
    return String(value || "").toLowerCase();
  }

  function projectSearchText(project) {
    return [
      project.name,
      project.path,
      project.branch,
      project.head,
      (project.detected_stack || []).join(" "),
      project.reefiki_mapping?.mapping_status,
      project.reefiki_status?.outcome,
      project.readiness?.summary,
      (project.warnings || []).join(" "),
      (project.latest_log_entries || []).map((entry) => entry.text || entry.raw || "").join(" "),
    ].join(" ");
  }

  function worktreeSearchText(project) {
    return [
      project.name,
      project.path,
      project.branch,
      project.head,
      project.dirty ? "dirty" : "clean",
      project.dirty_paths_count,
      project.ahead,
      project.behind,
      project.worktree_count,
      worktreeRecommendation(project),
      (project.remotes || []).join(" "),
    ].join(" ");
  }

  function logSearchText(entry) {
    return [entry.time, entry.iso, entry.level, entry.raw, entry.text].join(" ");
  }

  function logLevelBucket(entry) {
    const level = normalizeSearch(entry.level || entry.raw || entry.text);
    if (level.includes("error") || level.includes("fatal") || level.includes("fail")) return "error";
    if (level.includes("warn")) return "warn";
    if (level.includes("debug") || level.includes("trace")) return "debug";
    return "info";
  }

  function renderNavCounts() {
    const rollups = sectionRollups();
    SECTION_IDS.forEach((section) => setNavRollup(section, rollups[section]));
  }

  function sectionRollups() {
    const reviewQueue = Array.isArray(reefiki().review_queue_top) ? reefiki().review_queue_top : [];
    const activeTasks = Array.isArray(reefiki().active_tasks) ? reefiki().active_tasks : [];
    const sources = state.logsHealth && Array.isArray(state.logsHealth.sources) ? state.logsHealth.sources : [];
    const publishTone = Number(kpi().dirty || 0) || Number(kpi().warnings || 0) || Number(kpi().codex_branches || 0) ? "block" : "pass";
    return {
      overview: { count: Number(kpi().total || 0), tone: deriveVerdict().tone },
      projects: { count: projects().length, tone: rollupTones(projects().map(projectTone)) },
      memory: { count: 3, tone: memoryOverallTone() },
      worktrees: { count: projects().filter(worktreeNeedsReview).length, tone: worktreeOverallTone() },
      publish: { count: Number(kpi().dirty || 0) + Number(kpi().warnings || 0), tone: publishTone },
      review: { count: reviewQueue.length, tone: reviewQueue.length ? "warn" : "pass" },
      sprint: { count: activeTasks.length, tone: activeTasks.length ? "warn" : "info" },
      logs: { count: sources.length, tone: state.logsHealth && state.logsHealth.ok === false ? "block" : sources.length ? "pass" : "info" },
    };
  }

  function setNavRollup(section, payload) {
    const count = els[`nav-count-${section}`];
    const button = document.querySelector(`[data-section="${section}"]`);
    if (!count || !button || !payload) return;
    count.textContent = payload.count ? String(payload.count) : "";
    count.dataset.tone = payload.tone || "info";
    button.dataset.tone = payload.tone || "info";
    button.title = `${t(`nav.${section}`)} · ${statusLabel(payload.tone)} · ${sectionHotkey(section)}`;
  }

  function sectionHotkey(section) {
    const entry = Object.entries(SECTION_HOTKEYS).find(([, target]) => target === section);
    return entry ? entry[0] : "";
  }

  function filterDef(id, label, count, tone) {
    return { id, label, count, tone };
  }

  function viewDef(id, label, filter, query) {
    return { id, label, filter, query };
  }

  function renderViewControls(section, node, presets) {
    const quick = presets.map((view) => viewButton(section, view, "quick"));
    const saved = savedViewsFor(section).map((view) => savedViewChip(section, view));
    const save = document.createElement("button");
    save.className = "view-save-button";
    save.type = "button";
    save.textContent = t("views.saveCurrent");
    save.addEventListener("click", () => saveCurrentView(section));
    replaceChildren(node, quick.concat(saved, [save]));
  }

  function viewButton(section, view, kind) {
    const button = document.createElement("button");
    button.className = "view-button";
    button.type = "button";
    button.dataset.kind = kind || "quick";
    button.dataset.active = viewMatches(section, view) ? "true" : "false";
    button.textContent = view.label;
    button.addEventListener("click", () => applyView(section, view));
    return button;
  }

  function savedViewChip(section, view) {
    const chip = document.createElement("span");
    chip.className = "view-chip";
    chip.dataset.active = viewMatches(section, view) ? "true" : "false";
    chip.appendChild(viewButton(section, view, "saved"));
    const remove = document.createElement("button");
    remove.className = "view-delete";
    remove.type = "button";
    remove.textContent = "x";
    remove.title = t("views.delete");
    remove.setAttribute("aria-label", `${t("views.delete")} ${view.label}`);
    remove.addEventListener("click", () => deleteSavedView(section, view.id));
    chip.appendChild(remove);
    return chip;
  }

  function saveCurrentView(section) {
    const label = sanitizeViewLabel(window.prompt(t("views.promptName"), suggestedViewLabel(section)));
    if (!label) return;
    const view = currentViewState(section);
    view.id = `view-${Date.now()}`;
    view.label = label;
    const existing = savedViewsFor(section).filter((item) => item.label !== label);
    state.savedViews[section] = existing.concat([view]).slice(-SAVED_VIEW_LIMIT);
    saveSavedViews();
    renderSectionViews(section);
  }

  function deleteSavedView(section, id) {
    state.savedViews[section] = savedViewsFor(section).filter((item) => item.id !== id);
    saveSavedViews();
    renderSectionViews(section);
  }

  function applyView(section, view) {
    if (section === "projects") {
      state.projectFilter = view.filter || "all";
      state.projectQuery = view.query || "";
      els["projects-search"].value = state.projectQuery;
      renderProjects();
      return;
    }
    if (section === "worktrees") {
      state.worktreeFilter = view.filter || "all";
      state.worktreeQuery = view.query || "";
      els["worktrees-search"].value = state.worktreeQuery;
      renderWorktrees();
      return;
    }
    if (section === "logs") {
      state.logFilter = view.filter || "all";
      state.logQuery = view.query || "";
      els["logs-search"].value = state.logQuery;
      const sourceChanged = view.source && logSourceAvailable(view.source) && view.source !== state.logSource;
      if (sourceChanged) {
        state.logSource = view.source;
        state.logCursor = "";
        state.logEntries = [];
        els["log-source"].value = state.logSource;
        refreshLogTail(true);
      } else {
        renderLogEntries();
      }
    }
  }

  function renderSectionViews(section) {
    if (section === "projects") renderProjectViews();
    if (section === "worktrees") renderWorktreeViews();
    if (section === "logs") renderLogViews();
  }

  function currentViewState(section) {
    if (section === "projects") return { section, filter: state.projectFilter, query: state.projectQuery };
    if (section === "worktrees") return { section, filter: state.worktreeFilter, query: state.worktreeQuery };
    return { section, filter: state.logFilter, query: state.logQuery, source: state.logSource };
  }

  function viewMatches(section, view) {
    const current = currentViewState(section);
    return current.filter === (view.filter || "all")
      && normalizeSearch(current.query) === normalizeSearch(view.query)
      && (section !== "logs" || !view.source || view.source === current.source);
  }

  function savedViewsFor(section) {
    return Array.isArray(state.savedViews[section]) ? state.savedViews[section] : [];
  }

  function suggestedViewLabel(section) {
    return t("views.defaultName")
      .replace("{section}", t(`nav.${section}`))
      .replace("{count}", String(savedViewsFor(section).length + 1));
  }

  function sanitizeViewLabel(label) {
    return String(label || "").trim().replace(/\s+/g, " ").slice(0, 40);
  }

  function logSourceAvailable(id) {
    const sources = state.logsHealth && Array.isArray(state.logsHealth.sources) ? state.logsHealth.sources : [];
    return sources.some((source) => source.id === id);
  }

  function renderFilters(node, defs, active, onSelect) {
    const buttons = defs.map((item) => {
      const button = document.createElement("button");
      button.className = "filter-button";
      button.type = "button";
      button.dataset.active = item.id === active ? "true" : "false";
      button.dataset.tone = item.tone || "info";
      const label = document.createElement("span");
      const count = document.createElement("strong");
      label.textContent = item.label;
      count.textContent = String(item.count);
      button.append(label, count);
      button.addEventListener("click", () => onSelect(item.id));
      return button;
    });
    replaceChildren(node, buttons);
  }

  function projectNeedsAttention(project) {
    return Boolean(project && (project.dirty || (project.warnings || []).length || !project.gates?.tests || project.reefiki_mapping?.mapping_status === "ambiguous"));
  }

  function worktreeNeedsReview(project) {
    return Boolean(project && (project.dirty || String(project.branch || "").startsWith("codex/") || Number(project.worktree_count || 0) > 1));
  }

  function worktreeIsTaskSignal(project) {
    return Boolean(project && (String(project.branch || "").startsWith("codex/") || Number(project.worktree_count || 0) > 1));
  }

  function worktreeOverallTone() {
    const items = projects();
    if (items.some((project) => project.dirty)) return "warn";
    if (items.some((project) => String(project.branch || "").startsWith("codex/") || Number(project.worktree_count || 0) > 1)) return "info";
    return "pass";
  }

  function rollupTones(tones) {
    if (!tones.length) return "info";
    if (tones.includes("block")) return "block";
    if (tones.includes("warn")) return "warn";
    if (tones.includes("info")) return "info";
    return "pass";
  }

  function memoryOverallTone() {
    const memory = snapshot().memory || {};
    if (memory.outcome === "error") return "block";
    const payload = memoryPayload();
    if (payload.has_open) return "warn";
    const graphify = payload.graphify || {};
    if (normalizeSearch(graphify.status).includes("missing") || normalizeSearch(graphify.status).includes("stale")) {
      return "warn";
    }
    return rollupTones(Object.values(payload.providers || {}).map(memoryProviderTone));
  }

  function activateSection(section) {
    if (!SECTION_IDS.includes(section)) return;
    state.section = section;
    localStorage.setItem(STORAGE.section, section);
    let activePanel = null;
    document.querySelectorAll("[data-section]").forEach((button) => {
      button.classList.toggle("is-active", button.dataset.section === section);
    });
    document.querySelectorAll("[data-section-panel]").forEach((panel) => {
      const active = panel.dataset.sectionPanel === section;
      panel.hidden = !active;
      panel.classList.toggle("is-active", active);
      if (active) activePanel = panel;
    });
    restartAnimation(activePanel, "is-appearing");
    setRail(defaultRail(section));
    if (section === "logs") {
      refreshLogsHealth().then(() => refreshLogTail(true));
    }
  }

  function cardNode({ title, status, tone, body, meta }) {
    const node = template("tpl-card");
    node.querySelector('[data-field="title"]').textContent = title;
    setPill(node.querySelector('[data-field="status"]'), status, tone || "info");
    node.querySelector('[data-field="body"]').textContent = body || "";
    node.querySelector('[data-field="meta"]').textContent = meta || "";
    return node;
  }

  function emptyCard(text) {
    const node = document.createElement("div");
    node.className = "empty-state";
    node.textContent = text;
    return node;
  }

  function tableEmptyRow(colspan, text) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = colspan;
    cell.appendChild(emptyCard(text));
    row.appendChild(cell);
    return row;
  }

  function template(id) {
    const tpl = document.getElementById(id);
    return tpl.content.firstElementChild.cloneNode(true);
  }

  function replaceChildren(node, children) {
    if (!node) return;
    children.forEach((child, index) => {
      if (child && child.style) child.style.setProperty("--i", String(Math.min(index, 12)));
    });
    node.replaceChildren(...children);
  }

  function makeSelectable(node, handler) {
    node.addEventListener("click", handler);
    node.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        handler();
      }
    });
  }

  function pill(label, tone) {
    const node = document.createElement("span");
    node.className = "status-pill";
    setPill(node, label, tone);
    return node;
  }

  function setPill(node, label, tone) {
    if (!node) return;
    node.textContent = label || t("common.na");
    node.dataset.tone = tone || "info";
  }

  function setRail(payload) {
    state.railPayload = payload;
    const rail = els["right-rail"];
    if (rail) {
      rail.dataset.loading = "false";
      rail.setAttribute("aria-busy", "true");
    }
    els["rail-status"].classList.remove("is-skeleton");
    setPill(els["rail-status"], statusLabel(payload.status || "info"), payload.status || "info");
    els["rail-title"].textContent = payload.title || t("rail.title");
    els["rail-subtitle"].textContent = payload.subtitle || t("rail.empty");
    const fieldNodes = (payload.fields || []).map(([label, value]) => {
      const wrap = document.createElement("div");
      const dt = document.createElement("dt");
      const dd = document.createElement("dd");
      dt.textContent = label;
      dd.textContent = value == null || value === "" ? t("common.na") : String(value);
      wrap.append(dt, dd);
      return wrap;
    });
    replaceChildren(els["rail-fields"], fieldNodes);
    const actions = (payload.actions || []).map((action) => actionNode(action));
    replaceChildren(els["rail-actions-list"], actions.length ? actions : [emptyCard(t("rail.noActions"))]);
    restartAnimation(rail, "is-updating");
    window.setTimeout(() => {
      if (rail) rail.setAttribute("aria-busy", "false");
    }, 220);
  }

  function attachWarningAccordion(node, project, surface) {
    const issues = projectIssues(project);
    if (!issues.length) return;
    const key = warningAccordionKey(project, surface);
    const expanded = state.expandedWarningKey === key;
    const wrap = document.createElement("div");
    wrap.className = "card-warning-accordion";
    wrap.dataset.warningKey = key;
    wrap.dataset.warningCount = String(issues.length);
    wrap.addEventListener("click", (event) => event.stopPropagation());
    wrap.addEventListener("keydown", (event) => event.stopPropagation());

    const button = document.createElement("button");
    button.className = "warning-toggle";
    button.type = "button";
    setWarningToggle(button, issues.length, expanded);
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      toggleWarningAccordion(key, issues, button, panel);
    });
    wrap.appendChild(button);

    const panel = document.createElement("div");
    panel.className = "card-warning-panel";
    panel.hidden = !expanded;
    if (expanded) {
      replaceChildren(panel, issues.map(warningNode));
    }
    wrap.appendChild(panel);
    node.appendChild(wrap);
  }

  function toggleWarningAccordion(key, issues, button, panel) {
    const wasExpanded = state.expandedWarningKey === key;
    closeOpenWarningAccordions();
    if (wasExpanded) {
      state.expandedWarningKey = "";
      return;
    }
    state.expandedWarningKey = key;
    setWarningToggle(button, issues.length, true);
    if (!panel.childElementCount) {
      replaceChildren(panel, issues.map(warningNode));
    }
    panel.classList.remove("is-closing");
    panel.hidden = false;
  }

  function closeOpenWarningAccordions() {
    document.querySelectorAll(".card-warning-accordion").forEach((wrap) => {
      const button = wrap.querySelector(".warning-toggle");
      const panel = wrap.querySelector(".card-warning-panel");
      const count = Number(wrap.dataset.warningCount || 0);
      setWarningToggle(button, count, false);
      closeWarningPanel(panel);
    });
  }

  function setWarningToggle(button, count, expanded) {
    if (!button) return;
    button.setAttribute("aria-expanded", expanded ? "true" : "false");
    button.textContent = (expanded ? t("warningAccordion.hide") : t("warningAccordion.show"))
      .replace("{count}", String(count));
  }

  function closeWarningPanel(panel) {
    if (!panel || panel.hidden || panel.classList.contains("is-closing")) return;
    panel.classList.add("is-closing");
    window.setTimeout(() => {
      panel.hidden = true;
      panel.classList.remove("is-closing");
    }, WARNING_PANEL_CLOSE_MS);
  }

  function warningAccordionKey(project, surface) {
    return `${surface}:${project.path || project.name || "unknown"}`;
  }

  function actionNode(action) {
    const node = template("tpl-action");
    const help = action.help || commandHelp(action);
    node.querySelector('[data-field="label"]').textContent = action.label;
    node.querySelector('[data-field="detail"]').textContent = action.detail;
    node.querySelector('[data-field="command"]').textContent = action.command;
    const helpNode = node.querySelector('[data-field="help"]');
    helpNode.dataset.tooltip = help;
    helpNode.title = help;
    node.title = action.command;
    node.setAttribute("aria-label", `${action.label}: ${help}. ${action.command}`);
    node.addEventListener("click", () => copyText(action.command, node));
    return node;
  }

  function copyAction(label, detail, command, help) {
    return { label, detail, command, help };
  }

  function commandHelp(action) {
    const command = String(action.command || "");
    if (command.includes(" /connect ")) return t("commandHelp.connect");
    if (command.includes(" status --short --branch")) return t("commandHelp.status");
    if (command.includes("publish-task --dry-run")) return t("commandHelp.publishDryRun");
    if (command.includes("guard-staged")) return t("commandHelp.guardStaged");
    if (command.includes("secret-scan")) return t("commandHelp.secretScan");
    if (command.includes("memory status")) return t("commandHelp.memoryStatus");
    if (command.includes("review-queues")) return t("commandHelp.reviewQueues");
    if (command.startsWith("rg ")) return t("commandHelp.searchTask");
    if (command.includes("ops-dashboard")) return t("commandHelp.snapshot");
    if (command.includes("worktree list")) return t("commandHelp.worktreeList");
    return t("commandHelp.generic");
  }

  function warningNode(issue) {
    const node = document.createElement("article");
    node.className = "warning-explainer";
    node.dataset.tone = issue.tone || "warn";
    const head = document.createElement("div");
    head.className = "warning-head";
    const title = document.createElement("strong");
    title.textContent = issue.title;
    head.append(title, pill(issue.category || t("warning.category.unknown"), issue.tone || "warn"));
    node.appendChild(head);
    [
      [t("warning.what"), issue.what],
      [t("warning.why"), issue.why],
      [t("warning.next"), issue.next],
    ].forEach(([label, value]) => {
      const line = document.createElement("p");
      const mark = document.createElement("span");
      mark.textContent = label;
      line.append(mark, document.createTextNode(` ${value || t("common.na")}`));
      node.appendChild(line);
    });
    if (issue.source) {
      const source = document.createElement("code");
      source.textContent = issue.source;
      node.appendChild(source);
    }
    return node;
  }

  function projectIssues(project) {
    if (!project) return [];
    const gates = project.gates || {};
    const mapping = project.reefiki_mapping || {};
    const issues = [];
    if (project.dirty) {
      issues.push(issue(
        "dirty_worktree",
        "warn",
        t("warning.dirty.title"),
        t("warning.category.git"),
        t("warning.dirty.what").replace("{count}", String(project.dirty_paths_count || 0)),
        t("warning.dirty.why"),
        t("warning.dirty.next"),
        dirtySample(project),
      ));
    }
    if (!gates.agents_md) {
      issues.push(issue(
        "missing_agents_md",
        "warn",
        t("warning.agents.title"),
        t("warning.category.governance"),
        t("warning.agents.what"),
        t("warning.agents.why"),
        t("warning.agents.next"),
        "gates.agents_md=false",
      ));
    }
    if (!gates.ci) {
      issues.push(issue(
        "missing_ci",
        "warn",
        t("warning.ci.title"),
        t("warning.category.verification"),
        t("warning.ci.what"),
        t("warning.ci.why"),
        t("warning.ci.next"),
        "gates.ci=false",
      ));
    }
    if (!gates.tests) {
      issues.push(issue(
        "missing_tests",
        "warn",
        t("warning.tests.title"),
        t("warning.category.verification"),
        t("warning.tests.what"),
        t("warning.tests.why"),
        t("warning.tests.next"),
        "gates.tests=false",
      ));
    }
    if (mapping.mapping_status === "missing") {
      issues.push(issue(
        "reefiki_mapping_missing",
        "warn",
        t("warning.mappingMissing.title"),
        t("warning.category.reefiki"),
        t("warning.mappingMissing.what"),
        t("warning.mappingMissing.why"),
        t("warning.mappingMissing.next"),
        "reefiki_mapping.mapping_status=missing",
      ));
    }
    if (mapping.mapping_status === "ambiguous") {
      issues.push(issue(
        "reefiki_mapping_ambiguous",
        "block",
        t("warning.mappingAmbiguous.title"),
        t("warning.category.reefiki"),
        asText(mapping.reason) || t("warning.mappingAmbiguous.what"),
        t("warning.mappingAmbiguous.why"),
        t("warning.mappingAmbiguous.next"),
        "reefiki_mapping.mapping_status=ambiguous",
      ));
    }
    if (String(project.branch || "").startsWith("codex/")) {
      issues.push(issue(
        "task_branch",
        "info",
        t("warning.taskBranch.title"),
        t("warning.category.git"),
        t("warning.taskBranch.what"),
        t("warning.taskBranch.why"),
        t("warning.taskBranch.next"),
        `branch=${project.branch}`,
      ));
    }
    (project.warnings || []).forEach((warning) => {
      if (warning && warning.code === "reefiki_mapping_ambiguous" && mapping.mapping_status === "ambiguous") return;
      issues.push(snapshotIssue(warning));
    });
    return issues;
  }

  function issue(code, tone, title, category, what, why, next, source) {
    return { code, tone, title, category, what, why, next, source };
  }

  function snapshotIssue(warning) {
    const code = asText(warning && warning.code) || "unknown";
    const message = asText(warning && warning.message) || t("warning.unknown.what");
    const known = {
      upstream_missing: ["warn", t("warning.upstream.title"), t("warning.category.git"), t("warning.upstream.why"), t("warning.upstream.next")],
      git_status_failed: ["block", t("warning.gitStatus.title"), t("warning.category.git"), t("warning.gitStatus.why"), t("warning.gitStatus.next")],
      git_root_missing: ["block", t("warning.gitRoot.title"), t("warning.category.git"), t("warning.gitRoot.why"), t("warning.gitRoot.next")],
      secret_like_paths_skipped: ["warn", t("warning.secretSkipped.title"), t("warning.category.security"), t("warning.secretSkipped.why"), t("warning.secretSkipped.next")],
      forbidden_dirs_skipped: ["info", t("warning.forbiddenSkipped.title"), t("warning.category.security"), t("warning.forbiddenSkipped.why"), t("warning.forbiddenSkipped.next")],
    };
    const [tone, title, category, why, next] = known[code] || [
      "warn",
      t("warning.unknown.title").replace("{code}", code),
      t("warning.category.unknown"),
      t("warning.unknown.why"),
      t("warning.unknown.next"),
    ];
    return issue(code, tone, title, category, message, why, next, `snapshot warning: ${code}`);
  }

  function dirtySample(project) {
    const sample = Array.isArray(project.dirty_paths_sample) ? project.dirty_paths_sample : [];
    return sample.length ? sample.slice(0, 3).join(", ") : "git status --short";
  }

  function asText(value) {
    return value == null ? "" : String(value);
  }

  async function copyText(text, node) {
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(text);
      } else {
        const area = document.createElement("textarea");
        area.value = text;
        document.body.appendChild(area);
        area.select();
        document.execCommand("copy");
        area.remove();
      }
      restartAnimation(node, "copy-ok");
      node.dataset.copyState = "copied";
      node.querySelector('[data-field="detail"]').textContent = t("action.copied");
      window.setTimeout(() => {
        node.classList.remove("copy-ok");
        delete node.dataset.copyState;
      }, 900);
    } catch (error) {
      node.dataset.copyState = "failed";
      node.querySelector('[data-field="detail"]').textContent = t("action.copyFailed");
    }
  }

  function restartAnimation(node, className) {
    if (!node) return;
    node.classList.remove(className);
    void node.offsetWidth;
    node.classList.add(className);
  }

  function defaultRail(section) {
    return {
      title: t("rail.title"),
      status: "info",
      subtitle: t("rail.empty"),
      fields: [
        [t("field.section"), section || state.section],
        [t("field.snapshot"), snapshot().schema_version || t("common.na")],
        [t("field.source"), "/api/snapshot"],
      ],
      actions: [
        copyAction(t("action.refreshSnapshot"), t("action.copyOnly"), "python scripts\\reefiki.py ops-dashboard --workspace-root <workspace> --format json"),
      ],
    };
  }

  function verdictRail() {
    const verdict = deriveVerdict();
    const root = rootProject();
    return {
      title: t("rail.workspaceVerdict"),
      status: verdict.tone,
      subtitle: verdict.note,
      fields: [
        [t("field.status"), verdict.label],
        [t("field.dirtyProjects"), String(kpi().dirty || 0)],
        [t("field.warnings"), String(kpi().warnings || 0)],
        [t("field.codexBranches"), String(kpi().codex_branches || 0)],
        [t("field.connected"), String(kpi().connected || 0)],
        [t("field.cleanProjects"), String(kpi().clean || 0)],
        [t("field.branch"), root?.branch || t("common.na")],
        [t("field.head"), root?.head || t("common.na")],
        [t("field.sync"), `+${root?.ahead ?? 0} -${root?.behind ?? 0}`],
        [t("field.snapshot"), snapshot().schema_version || t("common.na")],
        [t("field.generated"), snapshot().generated_at || t("common.na")],
      ],
      actions: [
        copyAction(t("action.refreshSnapshot"), t("action.copyOnly"), dashboardSnapshotCommand()),
        copyAction(t("action.inspectStatus"), t("action.copyOnly"), rootStatusCommand()),
      ],
    };
  }

  function safetyGateRail(kind) {
    const dirty = Number(kpi().dirty || 0);
    const warnings = Number(kpi().warnings || 0);
    const codexBranches = Number(kpi().codex_branches || 0);
    const root = rootProject();
    const specs = {
      continue: {
        title: t("gate.continue"),
        status: state.snapshotError ? "block" : dirty || warnings ? "warn" : "pass",
        subtitle: dirty ? t("gate.continueDirty") : t("gate.continueOk"),
        detail: t("gate.continueDetail"),
        actions: [
          copyAction(t("action.refreshSnapshot"), t("action.copyOnly"), dashboardSnapshotCommand()),
          copyAction(t("action.inspectStatus"), t("action.copyOnly"), rootStatusCommand()),
        ],
      },
      publish: {
        title: t("gate.publish"),
        status: dirty || warnings || codexBranches ? "block" : "pass",
        subtitle: dirty || warnings || codexBranches ? t("gate.publishBlocked") : t("gate.publishDryRun"),
        detail: t("gate.publishDetail"),
        actions: [
          copyAction(t("action.publishDryRun"), t("action.copyOnly"), "python scripts\\reefiki.py publish-task --dry-run --cleanup --format json"),
          copyAction(t("action.guardStaged"), t("action.copyOnly"), "python scripts\\reefiki.py guard-staged --target-project reefiki --mode code/docs --format json"),
          copyAction(t("action.secretScan"), t("action.copyOnly"), "python scripts\\reefiki.py secret-scan <changed paths> --format json"),
        ],
      },
      cleanup: {
        title: t("gate.cleanup"),
        status: dirty ? "block" : "info",
        subtitle: dirty ? t("gate.cleanupBlocked") : t("gate.cleanupEvidence"),
        detail: t("gate.cleanupDetail"),
        actions: [
          copyAction(t("action.worktreeList"), t("action.copyOnly"), "git worktree list"),
          copyAction(t("action.publishDryRun"), t("action.copyOnly"), "python scripts\\reefiki.py publish-task --dry-run --cleanup --format json"),
        ],
      },
    };
    const spec = specs[kind] || specs.continue;
    return {
      title: spec.title,
      status: spec.status,
      subtitle: spec.subtitle,
      fields: [
        [t("field.dashboardMode"), t("publish.readOnlyMode")],
        [t("field.role"), spec.detail],
        [t("field.dirtyProjects"), String(dirty)],
        [t("field.warnings"), String(warnings)],
        [t("field.codexBranches"), String(codexBranches)],
        [t("field.branch"), root?.branch || t("common.na")],
        [t("field.head"), root?.head || t("common.na")],
        [t("field.sync"), `+${root?.ahead ?? 0} -${root?.behind ?? 0}`],
        [t("field.snapshot"), snapshot().schema_version || t("common.na")],
        [t("field.generated"), snapshot().generated_at || t("common.na")],
      ],
      actions: spec.actions,
    };
  }

  function projectRail(project) {
    return {
      title: project.name || t("common.unnamed"),
      status: projectTone(project),
      subtitle: readiness(project),
      fields: [
        [t("field.path"), project.path],
        [t("field.branch"), project.branch || t("common.na")],
        [t("field.head"), project.head || t("common.na")],
        [t("field.dirty"), project.dirty ? `${project.dirty_paths_count || 0}` : "0"],
        [t("field.sync"), `+${project.ahead ?? 0} -${project.behind ?? 0}`],
        [t("field.reefiki"), project.reefiki_mapping?.mapping_status || t("common.na")],
        [t("field.stack"), (project.detected_stack || []).join(", ") || t("common.na")],
        [t("field.warnings"), String(projectIssues(project).length)],
      ],
      actions: [
        copyAction(t("action.connect"), t("action.copyOnly"), commandConnect(project)),
        copyAction(t("action.inspectStatus"), t("action.copyOnly"), `git -C "${project.path || ""}" status --short --branch`),
      ],
    };
  }

  function publishRail(item) {
    return {
      title: item.title,
      status: item.tone,
      subtitle: item.body,
      fields: [
        [t("field.dashboardMode"), t("publish.readOnlyMode")],
        [t("field.dirtyProjects"), String(kpi().dirty || 0)],
        [t("field.warnings"), String(kpi().warnings || 0)],
      ],
      actions: [
        copyAction(t("action.publishDryRun"), t("action.copyOnly"), "python scripts\\reefiki.py publish-task --dry-run --cleanup --format json"),
        copyAction(t("action.guardStaged"), t("action.copyOnly"), "python scripts\\reefiki.py guard-staged --target-project reefiki --mode code/docs --format json"),
      ],
    };
  }

  function commandRail(label, command) {
    return {
      title: label,
      status: "info",
      subtitle: t("publish.commandBody"),
      fields: [
        [t("field.command"), command],
        [t("field.execution"), t("publish.copyOnlyExecution")],
      ],
      actions: [copyAction(label, t("action.copyOnly"), command)],
    };
  }

  function projectTone(project) {
    if (!project) return "info";
    if (project.reefiki_mapping?.mapping_status === "ambiguous") return "block";
    if (project.dirty) return "warn";
    if ((project.warnings || []).length) return "warn";
    return "pass";
  }

  function healthTone(value) {
    if (value === "pass") return "pass";
    if (value === "warn") return "warn";
    if (value === "fail") return "block";
    return "info";
  }

  function toneFromState(value) {
    if (value === "live" || value === "pass" || value === "available") return "pass";
    if (value === "stale" || value === "warn") return "warn";
    if (value === "unavailable" || value === "error") return "block";
    return "info";
  }

  function statusLabel(tone) {
    if (tone === "pass") return t("status.pass");
    if (tone === "warn") return t("status.warn");
    if (tone === "block") return t("status.block");
    if (tone === "loading") return t("status.loading");
    return t("status.info");
  }

  function readiness(project) {
    return project.readiness || (project.dirty ? t("state.dirty") : t("state.clean"));
  }

  function gatesText(project) {
    const gates = project.gates || {};
    const parts = [];
    if (gates.agents_md) parts.push("AGENTS");
    if (gates.tests) parts.push("tests");
    if (gates.ci) parts.push("CI");
    if (gates.package_manifest) parts.push("pkg");
    return parts.join(" / ") || t("common.na");
  }

  function worktreeRecommendation(project) {
    if (project.dirty) return t("worktrees.inspectDirty");
    if (project.branch && project.branch.startsWith("codex/")) return t("worktrees.reviewTask");
    if (Number(project.worktree_count || 0) > 1) return t("worktrees.checkParallel");
    return t("worktrees.noAction");
  }

  function commandConnect(project) {
    const path = project && project.path ? project.path : "<project-path>";
    return `reefiki /connect "${path}"`;
  }

  function dashboardSnapshotCommand() {
    const workspace = snapshot().workspace_root || "<workspace>";
    return `python scripts\\reefiki.py ops-dashboard --workspace-root "${workspace}" --format json`;
  }

  function rootStatusCommand() {
    const root = rootProject();
    if (root?.path) return `git -C "${root.path}" status --short --branch`;
    return "git status --short --branch";
  }

  function ageText(iso) {
    if (!iso) return t("common.na");
    const then = Date.parse(iso);
    if (!Number.isFinite(then)) return iso;
    const seconds = Math.max(0, Math.round((Date.now() - then) / 1000));
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.round(seconds / 60);
    if (minutes < 60) return `${minutes}m`;
    const hours = Math.round(minutes / 60);
    if (hours < 48) return `${hours}h`;
    const days = Math.round(hours / 24);
    return `${days}d`;
  }

  function normalizePath(path) {
    return String(path || "").replace(/\\/g, "/").replace(/\/+$/, "").toLowerCase();
  }
})();
