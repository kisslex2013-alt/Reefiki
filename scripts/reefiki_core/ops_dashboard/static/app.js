(() => {
  "use strict";

  const LOG_POLL_MS = 3000;
  const PINNED_PROJECTS_KEY = "reefiki.opsDashboard.pinnedProjects";

  const state = {
    snapshot: null,
    selected: null,
    tab: "tab.overview",
    railPanel: "activity",
    language: "en",
    theme: "dark",
    intervalMs: 0,
    i18n: null,
    snapshotTimer: null,
    logTimer: null,
    logsHealth: null,
    logSource: "",
    logCursor: "",
    logEntries: [],
    logState: "not_configured",
    logError: "",
    logSourceInitialized: false,
    logPinnedToBottom: true,
    logForceStickToBottom: true,
    firstRunDismissed: false,
    pinnedProjects: [],
  };

  const els = {
    firstRun: document.getElementById("first-run"),
    firstRunDismiss: document.getElementById("first-run-dismiss"),
    firstRunSteps: document.getElementById("first-run-steps"),
    kpi: document.getElementById("kpi"),
    reefiki: document.getElementById("reefiki-control"),
    currentWork: document.getElementById("current-work"),
    currentWorkSummary: document.getElementById("current-work-summary"),
    railCaption: document.getElementById("rail-caption"),
    activityList: document.getElementById("activity-list"),
    activityCount: document.getElementById("activity-count"),
    projectsTbody: document.getElementById("projects-tbody"),
    projectsCount: document.getElementById("projects-count"),
    inspectorBody: document.getElementById("inspector-body"),
    inspectorClose: document.getElementById("inspector-close"),
    lastRefresh: document.getElementById("last-refresh"),
    refresh: document.getElementById("refresh"),
    lang: document.getElementById("lang"),
    theme: document.getElementById("theme"),
    interval: document.getElementById("interval"),
    panelActivity: document.getElementById("panel-activity"),
    panelLogs: document.getElementById("panel-logs"),
    activityPanel: document.getElementById("activity-panel"),
    logsPanel: document.getElementById("logs-panel"),
    logsSource: document.getElementById("logs-source"),
    logsReconnect: document.getElementById("logs-reconnect"),
    logsStatus: document.getElementById("logs-status"),
    logsMeta: document.getElementById("logs-meta"),
    liveLogs: document.getElementById("live-logs"),
    inspector: document.getElementById("inspector"),
  };

  const customSelects = new Map();

  function t(key) {
    const dict = (state.i18n && state.i18n[state.language]) || {};
    return dict[key] || (state.i18n && state.i18n.en && state.i18n.en[key]) || key;
  }

  function processI18nNodes(root) {
    const scope = root || document;
    const textNodes = [];
    if (scope.matches && scope.matches("[data-i18n]")) textNodes.push(scope);
    if (scope.querySelectorAll) textNodes.push(...scope.querySelectorAll("[data-i18n]"));
    for (const node of textNodes) {
      node.textContent = t(node.dataset.i18n);
    }
    const ariaNodes = [];
    if (scope.matches && scope.matches("[data-i18n-aria-label]")) ariaNodes.push(scope);
    if (scope.querySelectorAll) ariaNodes.push(...scope.querySelectorAll("[data-i18n-aria-label]"));
    for (const node of ariaNodes) {
      node.setAttribute("aria-label", t(node.dataset.i18nAriaLabel));
    }
  }

  function selectLabel(select) {
    const label = select.closest("label");
    const labelNode = select.previousElementSibling;
    if (labelNode && labelNode.tagName === "SPAN") return labelNode.textContent.trim();
    return label ? label.textContent.trim() : "";
  }

  function selectedOption(select) {
    return select.options[select.selectedIndex] || null;
  }

  function closeCustomSelect(select) {
    const control = customSelects.get(select);
    if (!control) return;
    control.wrapper.classList.remove("is-open");
    control.button.setAttribute("aria-expanded", "false");
    control.list.hidden = true;
  }

  function closeAllCustomSelects(exceptSelect) {
    for (const select of customSelects.keys()) {
      if (select !== exceptSelect) closeCustomSelect(select);
    }
  }

  function focusCustomSelectOption(select, index) {
    const control = customSelects.get(select);
    if (!control) return;
    const options = [...control.list.querySelectorAll(".select-ui__option:not(:disabled)")];
    if (!options.length) return;
    const safeIndex = Math.min(Math.max(index, 0), options.length - 1);
    options[safeIndex].focus();
  }

  function openCustomSelect(select, direction) {
    const control = customSelects.get(select);
    if (!control) return;
    closeAllCustomSelects(select);
    syncCustomSelect(select);
    control.wrapper.classList.add("is-open");
    control.button.setAttribute("aria-expanded", "true");
    control.list.hidden = false;
    const options = [...control.list.querySelectorAll(".select-ui__option:not(:disabled)")];
    const selectedIndex = Math.max(0, options.findIndex((option) => option.dataset.value === select.value));
    if (direction) {
      const offset = direction === "previous" ? -1 : 1;
      window.requestAnimationFrame(() => focusCustomSelectOption(select, selectedIndex + offset));
    }
  }

  function setCustomSelectValue(select, value) {
    if (select.value !== value) {
      select.value = value;
      select.dispatchEvent(new Event("change", { bubbles: true }));
    }
    syncCustomSelect(select);
    closeCustomSelect(select);
  }

  function syncCustomSelect(select) {
    const control = customSelects.get(select);
    if (!control) return;
    const option = selectedOption(select);
    const valueText = option ? option.textContent.trim() : "—";
    const label = selectLabel(select);
    control.value.textContent = valueText;
    control.button.setAttribute("aria-label", label ? `${label}: ${valueText}` : valueText);
    control.list.replaceChildren();
    [...select.options].forEach((sourceOption, index) => {
      const item = document.createElement("button");
      item.type = "button";
      item.className = "select-ui__option";
      item.dataset.value = sourceOption.value;
      item.disabled = sourceOption.disabled;
      item.setAttribute("role", "option");
      item.setAttribute("aria-selected", sourceOption.value === select.value ? "true" : "false");
      item.classList.toggle("is-selected", sourceOption.value === select.value);
      item.textContent = sourceOption.textContent;
      item.title = sourceOption.title || sourceOption.textContent;
      item.addEventListener("click", () => setCustomSelectValue(select, sourceOption.value));
      item.addEventListener("keydown", (event) => {
        if (event.key === "ArrowDown") {
          event.preventDefault();
          focusCustomSelectOption(select, index + 1);
        }
        if (event.key === "ArrowUp") {
          event.preventDefault();
          focusCustomSelectOption(select, index - 1);
        }
        if (event.key === "Home") {
          event.preventDefault();
          focusCustomSelectOption(select, 0);
        }
        if (event.key === "End") {
          event.preventDefault();
          focusCustomSelectOption(select, select.options.length - 1);
        }
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          setCustomSelectValue(select, sourceOption.value);
          control.button.focus();
        }
        if (event.key === "Escape") {
          event.preventDefault();
          closeCustomSelect(select);
          control.button.focus();
        }
      });
      control.list.appendChild(item);
    });
  }

  function enhanceSelect(select) {
    if (!select || customSelects.has(select)) return;
    const wrapper = document.createElement("div");
    wrapper.className = "select-ui";
    const button = document.createElement("button");
    button.type = "button";
    button.className = "select-ui__button";
    button.setAttribute("aria-haspopup", "listbox");
    button.setAttribute("aria-expanded", "false");
    const value = document.createElement("span");
    value.className = "select-ui__value";
    const marker = document.createElement("span");
    marker.className = "select-ui__marker";
    marker.setAttribute("aria-hidden", "true");
    marker.textContent = "⌄";
    button.append(value, marker);
    const list = document.createElement("div");
    list.className = "select-ui__list";
    list.setAttribute("role", "listbox");
    list.hidden = true;
    wrapper.append(button, list);
    select.classList.add("native-select-hidden");
    select.setAttribute("aria-hidden", "true");
    select.tabIndex = -1;
    select.after(wrapper);
    customSelects.set(select, { wrapper, button, value, list });
    button.addEventListener("click", () => {
      if (wrapper.classList.contains("is-open")) closeCustomSelect(select);
      else openCustomSelect(select);
    });
    button.addEventListener("keydown", (event) => {
      if (event.key === "ArrowDown" || event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        openCustomSelect(select, "next");
      }
      if (event.key === "ArrowUp") {
        event.preventDefault();
        openCustomSelect(select, "previous");
      }
      if (event.key === "Escape") {
        closeCustomSelect(select);
      }
    });
    select.addEventListener("change", () => syncCustomSelect(select));
    syncCustomSelect(select);
  }

  function enhanceSelects() {
    [els.lang, els.theme, els.interval, els.logsSource].forEach(enhanceSelect);
  }

  function syncCustomSelects() {
    for (const select of customSelects.keys()) syncCustomSelect(select);
  }

  document.addEventListener("pointerdown", (event) => {
    for (const [select, control] of customSelects.entries()) {
      if (!control.wrapper.contains(event.target)) closeCustomSelect(select);
    }
  });

  function relativeTime(iso) {
    if (!iso) return "—";
    const then = new Date(iso);
    if (Number.isNaN(then.getTime())) return "—";
    const sec = Math.max(0, Math.round((Date.now() - then.getTime()) / 1000));
    if (sec < 60) return t("ago.now");
    const min = Math.round(sec / 60);
    if (min < 60) return `${min} ${t("ago.minutes")}`;
    const hr = Math.round(min / 60);
    if (hr < 24) return `${hr} ${t("ago.hours")}`;
    const day = Math.round(hr / 24);
    return `${day} ${t("ago.days")}`;
  }

  function cloneTpl(id) {
    const tpl = document.getElementById(id);
    if (!tpl) throw new Error(`missing template #${id}`);
    return tpl.content.firstElementChild.cloneNode(true);
  }

  function fillFields(node, mapping) {
    for (const [selector, value] of Object.entries(mapping)) {
      const target = node.matches(selector) ? node : node.querySelector(selector);
      if (target) target.textContent = value == null || value === "" ? "—" : String(value);
    }
    return node;
  }

  function countPassedGates(project) {
    const gates = project.gates || {};
    const values = Object.values(gates);
    return {
      passed: values.filter(Boolean).length,
      total: values.length,
    };
  }

  function findProject(name) {
    return (state.snapshot && state.snapshot.projects || []).find((project) => project.name === name) || null;
  }

  function loadPinnedProjects() {
    try {
      const parsed = JSON.parse(localStorage.getItem(PINNED_PROJECTS_KEY) || "[]");
      return Array.isArray(parsed) ? [...new Set(parsed.filter((item) => typeof item === "string" && item.trim()))] : [];
    } catch {
      return [];
    }
  }

  function savePinnedProjects() {
    localStorage.setItem(PINNED_PROJECTS_KEY, JSON.stringify(state.pinnedProjects));
  }

  function isPinnedProject(name) {
    return state.pinnedProjects.includes(name);
  }

  function togglePinnedProject(name) {
    if (!name) return;
    if (isPinnedProject(name)) {
      state.pinnedProjects = state.pinnedProjects.filter((item) => item !== name);
    } else {
      state.pinnedProjects = [...state.pinnedProjects, name];
    }
    savePinnedProjects();
    if (state.snapshot) render(state.snapshot);
  }

  function composeCurrentWork(snapshot) {
    const projects = snapshot.projects || [];
    const byName = new Map(projects.map((project) => [project.name, project]));
    const pinned = state.pinnedProjects.map((name) => byName.get(name)).filter(Boolean);
    const pinnedNames = new Set(pinned.map((project) => project.name));
    const auto = (snapshot.current_work || []).filter((project) => !pinnedNames.has(project.name));
    const limit = Math.max(5, pinned.length);
    const items = [...pinned, ...auto].slice(0, limit);
    return {
      items,
      pinnedCount: pinned.length,
      autoCount: Math.max(0, items.length - pinned.length),
      total: projects.length,
    };
  }

  function mappingStatus(project) {
    return ((project.reefiki_mapping || {}).mapping_status || "missing");
  }

  function mappingTone(status) {
    return status === "connected" ? "accent" : status === "ambiguous" ? "warn" : "neutral";
  }

  function connectCommand(project) {
    return `/connect ${project.path || project.name}`;
  }

  function deriveSafeNextAction(snapshot) {
    const projects = snapshot.projects || [];
    const dirtyCodex = projects.find((project) => project.dirty && project.is_codex_branch);
    if (dirtyCodex) return `${t("next.inspect-dirty")}: ${dirtyCodex.name}`;
    const warningProject = projects.find((project) => (project.warnings || []).length);
    if (warningProject) return `${t("next.review-warning")}: ${warningProject.name}`;
    const disconnected = projects.find((project) => (project.reefiki_mapping || {}).mapping_status === "missing");
    if (disconnected) return `${t("next.connect-project")}: ${disconnected.name}`;
    const current = (snapshot.current_work || [])[0];
    if (current) return `${t("next.continue-lane")}: ${current.name}`;
    return t("next.snapshot-clean");
  }

  function projectReadinessText(project) {
    const gates = project.gates || {};
    const notes = [];
    if (project.dirty) notes.push(t("readiness.dirty"));
    if (gates.agents_md === false) notes.push(t("readiness.missing-agents"));
    if (gates.ci === false) notes.push(t("readiness.missing-ci"));
    if (gates.tests === false) notes.push(t("readiness.missing-tests"));
    if ((project.reefiki_mapping || {}).mapping_status === "connected") notes.push(t("readiness.connected"));
    if ((project.warnings || []).length) notes.push(`${project.warnings.length} ${t("readiness.warnings")}`);
    return notes.join("; ") || t("readiness.ready");
  }

  function projectActionText(project) {
    const gates = project.gates || {};
    if (project.dirty) return t("action.inspect-dirty");
    if ((project.warnings || []).length) return t("action.resolve-warnings");
    if (gates.agents_md === false || gates.ci === false || gates.tests === false) return t("action.restore-readiness");
    return t("action.inspect-project");
  }

  function applyFirstRunVisibility() {
    if (els.firstRun) els.firstRun.hidden = state.firstRunDismissed;
  }

  function tourStatusTone(status) {
    if (status === "done") return "ok";
    if (status === "current") return "accent";
    if (status === "blocked") return "bad";
    return "neutral";
  }

  function renderFirstRunTour(tour) {
    const steps = tour && Array.isArray(tour.steps) ? tour.steps : [];
    if (!els.firstRunSteps || !steps.length) return;
    const frag = document.createDocumentFragment();
    steps.forEach((step, index) => {
      const item = document.createElement("li");
      item.className = `tour-step tour-step--${step.status || "todo"}`;

      const indexNode = document.createElement("span");
      indexNode.className = "step-index";
      indexNode.textContent = String(index + 1).padStart(2, "0");

      const body = document.createElement("div");
      body.className = "tour-step__body";

      const head = document.createElement("div");
      head.className = "tour-step__head";
      const title = document.createElement("strong");
      title.textContent = t(`tour.${step.id}.title`);
      const status = document.createElement("span");
      status.className = `tour-status tone-${tourStatusTone(step.status)}`;
      status.textContent = t(`tour.status.${step.status || "todo"}`);
      head.append(title, status);

      const reason = document.createElement("p");
      reason.className = "tour-reason";
      reason.textContent = t(`tour.${step.id}.body`);

      const command = document.createElement("code");
      command.textContent = step.command || "";

      body.append(head, reason, command);
      item.append(indexNode, body);
      frag.appendChild(item);
    });
    els.firstRunSteps.replaceChildren(frag);
  }

  function toneClass(tone) {
    return `tone-${tone || "neutral"}`;
  }

  function applyBadgeTone(node, tone) {
    node.classList.add(toneClass(tone));
  }

  function setTitle(node, text) {
    if (!node) return;
    node.title = text || "";
    if (text) node.setAttribute("aria-label", text);
  }

  function isLogsNearBottom() {
    const distance = els.liveLogs.scrollHeight - els.liveLogs.scrollTop - els.liveLogs.clientHeight;
    return distance < 28;
  }

  function applyLanguage() {
    document.documentElement.lang = state.language;
    els.lang.value = state.language;
    if (state.snapshot) render(state.snapshot);
    processI18nNodes(document);
    syncCustomSelects();
    renderLogsPanel();
  }

  function renderKpi(kpi) {
    const items = [
      { label: t("kpi.total"), value: kpi.total },
      { label: t("kpi.clean"), value: kpi.clean, tone: kpi.dirty ? null : "ok" },
      { label: t("kpi.dirty"), value: kpi.dirty, tone: kpi.dirty ? "warn" : "ok" },
      { label: t("kpi.codex"), value: kpi.codex_branches, tone: kpi.codex_branches ? "accent" : null },
      { label: t("kpi.connected"), value: kpi.connected },
      { label: t("kpi.warnings"), value: kpi.warnings, tone: kpi.warnings ? "warn" : "ok" },
      { label: t("kpi.no_tests"), value: kpi.no_tests, tone: kpi.no_tests ? "warn" : null },
      { label: t("kpi.no_agents"), value: kpi.no_agents_md, tone: kpi.no_agents_md ? "warn" : null },
    ];
    const frag = document.createDocumentFragment();
    for (const item of items) {
      const node = cloneTpl("tpl-kpi-cell");
      fillFields(node, {
        '[data-field="label"]': item.label,
        '[data-field="value"]': item.value,
      });
      if (item.tone) {
        node.querySelector('[data-field="value"]').classList.add(`tone-${item.tone}`);
      }
      frag.appendChild(node);
    }
    els.kpi.replaceChildren(frag);
  }

  function renderReefiki(control, snapshot) {
    const activeTask = (control.active_tasks || [])[0] || null;
    const nextTask = (control.next_tasks || [])[0] || null;
    const node = cloneTpl("tpl-reefiki");
    fillFields(node, {
      '[data-field="next-action"]': deriveSafeNextAction(snapshot),
      '[data-field="health"]': control.health_outcome || "unknown",
      '[data-field="phase"]': control.roadmap_phase || "—",
      '[data-field="sprint"]': control.current_sprint || "—",
      '[data-field="active-task"]': activeTask ? `${activeTask.id} ${activeTask.title}` : "—",
      '[data-field="next-task"]': nextTask ? `${nextTask.id} ${nextTask.title}` : "—",
      '[data-field="review-top"]': ((control.review_queue_top || [])[0] || {}).queue || "—",
      '[data-field="last-log"]': control.last_log_heading || "—",
    });
    const healthBadge = node.querySelector('[data-field="health"]');
    const healthTone = {
      pass: "ok",
      warn: "warn",
      warning: "warn",
      fail: "bad",
      error: "bad",
      unknown: "unknown",
    }[control.health_outcome || "unknown"] || "unknown";
    healthBadge.classList.add(`tone-${healthTone}`);
    processI18nNodes(node);
    els.reefiki.replaceChildren(node);
  }

  function renderCurrentWork(snapshot) {
    const { items, pinnedCount, autoCount, total } = composeCurrentWork(snapshot);
    if (pinnedCount) {
      els.currentWorkSummary.textContent = `${pinnedCount} ${t("summary.pinned")} · ${autoCount} ${t("summary.auto")}`;
      setTitle(els.currentWorkSummary, t("summary.current-work-mixed-title"));
    } else {
      els.currentWorkSummary.textContent = `${items.length}/${total} ${t("summary.attention-projects")}`;
      setTitle(els.currentWorkSummary, t("summary.current-work-auto-title"));
    }
    els.currentWork.replaceChildren();
    if (!items.length) {
      const p = document.createElement("p");
      p.className = "muted";
      p.textContent = t("current-work-empty");
      els.currentWork.appendChild(p);
      return;
    }
    const frag = document.createDocumentFragment();
    for (const project of items) {
      const card = cloneTpl("tpl-work-card");
      const isSelected = state.selected === project.name;
      if (isSelected) card.classList.add("is-selected");
      const warningCount = (project.warnings || []).length;
      const stateLabel = project.dirty
        ? `${t("state.dirty")} ${project.dirty_paths_count}`
        : warningCount
          ? `${t("state.warning")} ${warningCount}`
          : t("state.clean");
      fillFields(card, {
        '[data-field="name"]': project.name,
        '[data-field="state"]': stateLabel,
        '[data-field="reason"]': projectReadinessText(project) || (project.detected_stack || []).join(", "),
        '[data-field="action"]': projectActionText(project),
      });
      card.querySelector('[data-field="state"]').classList.add(project.dirty ? "tone-warn" : warningCount ? "tone-bad" : "tone-ok");
      card.addEventListener("click", () => select(project.name, "tab.overview"));
      card.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          select(project.name, "tab.overview");
        }
      });
      frag.appendChild(card);
    }
    els.currentWork.appendChild(frag);
  }

  function renderActivity(events) {
    const timelineEvents = events.filter((event) => event.kind !== "dirty" && event.kind !== "warning");
    els.activityCount.textContent = `${timelineEvents.length}`;
    els.railCaption.textContent = t("signals-subtitle");
    if (!timelineEvents.length) {
      const li = document.createElement("li");
      li.className = "muted";
      li.textContent = t("activity-empty");
      els.activityList.replaceChildren(li);
      return;
    }
    const frag = document.createDocumentFragment();
    for (const event of timelineEvents) {
      const node = cloneTpl("tpl-activity-item");
      node.querySelector('[data-field="kind"]').classList.add(`tone-${event.kind}`);
      fillFields(node, {
        '[data-field="kind"]': t(`kind.${event.kind}`),
        '[data-field="title"]': event.title || "—",
        '[data-field="project"]': event.project || "—",
        '[data-field="ago"]': relativeTime(event.iso),
      });
      node.addEventListener("click", () => {
        if (event.project && event.project !== "reefiki") select(event.project, "tab.logs");
      });
      node.addEventListener("keydown", (keyboardEvent) => {
        if ((keyboardEvent.key === "Enter" || keyboardEvent.key === " ") && event.project && event.project !== "reefiki") {
          keyboardEvent.preventDefault();
          select(event.project, "tab.logs");
        }
      });
      frag.appendChild(node);
    }
    els.activityList.replaceChildren(frag);
  }

  function renderProjects(projects) {
    els.projectsCount.textContent = `${projects.length}`;
    const frag = document.createDocumentFragment();
    projects.forEach((project, index) => {
      const row = cloneTpl("tpl-project-row");
      const isSelected = state.selected === project.name;
      row.classList.toggle("is-selected", isSelected);
      const warningCount = (project.warnings || []).length;
      const stateTone = project.dirty ? "warn" : warningCount ? "bad" : "ok";
      const stateText = project.dirty
        ? `${t("state.dirty")} ${project.dirty_paths_count}`
        : warningCount
          ? `${t("state.warning")} ${warningCount}`
          : t("state.clean");
      const gates = countPassedGates(project);
      const gateTone = gates.passed === gates.total ? "ok" : gates.passed === 0 ? "bad" : "warn";
      const projectMappingStatus = mappingStatus(project);
      fillFields(row, {
        '[data-field="index"]': `${index + 1}`,
        '[data-field="name"]': project.name,
        '[data-field="branch"]': project.branch || "—",
        '[data-field="state"]': stateText,
        '[data-field="gates"]': `${gates.passed}/${gates.total}`,
        '[data-field="ago"]': relativeTime(project.last_activity && project.last_activity.iso),
      });
      applyBadgeTone(row.querySelector('[data-field="state"]'), stateTone);
      applyBadgeTone(row.querySelector('[data-field="gates"]'), gateTone);

      const pinButton = row.querySelector('[data-field="pin"]');
      const pinned = isPinnedProject(project.name);
      pinButton.textContent = pinned ? "★" : "☆";
      pinButton.classList.toggle("is-pinned", pinned);
      setTitle(pinButton, `${pinned ? t("unpin-project") : t("pin-project")}: ${project.name}`);
      pinButton.addEventListener("click", (event) => {
        event.stopPropagation();
        togglePinnedProject(project.name);
      });

      const mappingCell = row.querySelector('[data-field="mapping-cell"]');
      const mappingNode = document.createElement(projectMappingStatus === "connected" ? "span" : "button");
      mappingNode.className = `table-badge mapping-action tone-${mappingTone(projectMappingStatus)}`;
      mappingNode.textContent = projectMappingStatus === "connected"
        ? t("mapping.connected")
        : projectMappingStatus === "ambiguous"
          ? t("mapping.check")
          : t("mapping.connect");
      setTitle(mappingNode, projectMappingStatus === "connected" ? t("connect.connected") : t("connect.open-handoff"));
      if (projectMappingStatus !== "connected") {
        mappingNode.type = "button";
        mappingNode.addEventListener("click", (event) => {
          event.stopPropagation();
          select(project.name, "tab.connect", { scrollToConnect: true });
        });
      }
      mappingCell.replaceChildren(mappingNode);

      setTitle(row.querySelector('[data-field="name"]'), project.name);
      setTitle(row.querySelector('[data-field="branch"]'), project.branch || "—");
      setTitle(row.querySelector('[data-field="state"]'), stateText);
      setTitle(row.querySelector('[data-field="gates"]'), `${t("label.readiness")}: ${gates.passed}/${gates.total}`);
      row.addEventListener("click", () => select(project.name, "tab.overview"));
      row.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          select(project.name, "tab.overview");
        }
      });
      frag.appendChild(row);
    });
    els.projectsTbody.replaceChildren(frag);
  }

  function scrollConnectIntoView() {
    const target = els.inspector.querySelector(".connect-handoff") || els.inspector;
    target.scrollIntoView({
      behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
      block: "center",
    });
    if (target instanceof HTMLElement) {
      target.focus({ preventScroll: true });
    }
  }

  function select(name, tab, options = {}) {
    if (!name) {
      state.selected = null;
      state.tab = "tab.overview";
    } else {
      const nextSelected = state.selected === name && !tab ? null : name;
      const switchedProject = Boolean(nextSelected && nextSelected !== state.selected);
      state.selected = nextSelected;
      if (tab) state.tab = tab;
      else if (switchedProject) state.tab = "tab.overview";
    }
    els.inspectorClose.hidden = state.selected == null;
    if (state.snapshot) {
      render(state.snapshot);
    }
    if (options.scrollToConnect) {
      requestAnimationFrame(scrollConnectIntoView);
    }
  }

  function appendKv(parent, label, value) {
    const row = cloneTpl("tpl-detail-kv");
    fillFields(row, {
      '[data-field="label"]': label,
      '[data-field="value"]': value == null || value === "" ? "—" : String(value),
    });
    parent.appendChild(row);
  }

  function renderOverview(project, body) {
    const lastActivity = project.last_activity || {};
    appendKv(body, t("label.branch"), project.branch);
    appendKv(body, t("label.head"), project.head || "—");
    appendKv(body, t("label.dirty"), project.dirty ? `${t("state.dirty")} (${project.dirty_paths_count})` : t("state.clean"));
    appendKv(body, t("label.ahead-behind"), `${project.ahead ?? "—"}/${project.behind ?? "—"}`);
    appendKv(body, t("label.worktrees"), project.worktree_count);
    appendKv(body, t("label.stack"), (project.detected_stack || []).join(", ") || "—");
    appendKv(body, t("label.last"), lastActivity.subject || lastActivity.iso || "—");
    appendKv(
      body,
      t("label.mapping"),
      (project.reefiki_mapping || {}).project
        ? `${t("mapping.connected")}: ${(project.reefiki_mapping || {}).project}`
        : t(`mapping.${((project.reefiki_mapping || {}).mapping_status || "missing")}`)
    );
    appendKv(body, t("label.readiness"), projectReadinessText(project));
  }

  function renderFiles(project, body) {
    const files = project.detected_files || {};
    appendKv(body, t("label.manifests"), (files.manifests || []).length);
    appendKv(body, t("label.ci"), (files.ci || []).length);
    appendKv(body, t("label.tests"), (files.test_markers || []).length);
    appendKv(body, t("label.agents"), (files.agent || []).length);
    appendKv(body, t("label.remotes"), (project.remotes || []).map((remote) => remote.name).join(", ") || "—");
  }

  function renderReadiness(project, body) {
    const gates = project.gates || {};
    appendKv(body, t("label.manifests"), gates.package_manifest ? t("yes") : t("no"));
    appendKv(body, t("label.ci"), gates.ci ? t("yes") : t("no"));
    appendKv(body, t("label.tests"), gates.tests ? t("yes") : t("no"));
    appendKv(body, t("label.agents"), gates.agents_md ? t("yes") : t("no"));
    appendKv(body, t("label.readiness"), projectReadinessText(project));
  }

  function renderProjectLogs(project, body) {
    const entries = (project.latest_log_entries || []).slice().reverse();
    if (!entries.length) {
      const span = document.createElement("span");
      span.className = "muted";
      span.textContent = t("activity-empty");
      body.appendChild(span);
      return;
    }
    const list = document.createElement("ul");
    list.className = "log-list";
    for (const entry of entries) {
      const item = cloneTpl("tpl-log-entry");
      fillFields(item, {
        '[data-field="heading"]': entry.heading || "—",
        '[data-field="body"]': (entry.lines && entry.lines[0]) || "",
      });
      list.appendChild(item);
    }
    body.appendChild(list);
  }

  function renderWarnings(project, body) {
    const warnings = project.warnings || [];
    if (project.dirty_paths_count) appendKv(body, t("label.dirty-paths"), project.dirty_paths_count);
    if (!warnings.length) {
      appendKv(body, t("label.warnings"), t("none"));
      return;
    }
    const details = document.createElement("details");
    details.className = "warn-list";
    const summary = document.createElement("summary");
    summary.textContent = `${t("label.warnings")}: ${warnings.length}`;
    details.appendChild(summary);
    const list = document.createElement("ul");
    for (const warning of warnings) {
      const item = document.createElement("li");
      item.textContent = `${warning.code}: ${warning.message || ""}`;
      list.appendChild(item);
    }
    details.appendChild(list);
    body.appendChild(details);
  }

  function renderConnect(project, body) {
    const status = mappingStatus(project);
    if (status === "connected") {
      appendKv(body, t("label.mapping"), `${t("mapping.connected")}: ${(project.reefiki_mapping || {}).project || project.name}`);
      return;
    }
    const panel = document.createElement("div");
    panel.className = "connect-handoff";
    panel.tabIndex = -1;

    const heading = document.createElement("strong");
    heading.textContent = t("connect.command-title");
    const note = document.createElement("p");
    note.className = "muted";
    note.textContent = t("connect.readonly-note");

    const command = connectCommand(project);
    const commandRow = document.createElement("div");
    commandRow.className = "command-row";
    const code = document.createElement("code");
    code.textContent = command;
    const copyButton = document.createElement("button");
    copyButton.type = "button";
    copyButton.textContent = t("connect.copy");
    copyButton.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(command);
        copyButton.textContent = t("connect.copied");
      } catch {
        copyButton.textContent = t("connect.copy-failed");
      }
    });
    commandRow.append(code, copyButton);

    panel.append(heading, note, commandRow);
    body.appendChild(panel);
    appendKv(body, t("label.mapping"), t(`mapping.${status}`));
    appendKv(body, t("label.path"), project.path || "—");
  }

  function renderInspector(projects) {
    if (!state.selected) {
      els.inspector.classList.add("is-empty");
      els.inspectorBody.replaceChildren();
      const placeholder = document.createElement("p");
      placeholder.className = "muted";
      placeholder.textContent = t("empty");
      els.inspectorBody.appendChild(placeholder);
      return;
    }
    const project = projects.find((item) => item.name === state.selected);
    if (!project) {
      els.inspector.classList.add("is-empty");
      els.inspectorBody.replaceChildren();
      return;
    }
    els.inspector.classList.remove("is-empty");
    const header = document.createElement("div");
    header.className = "inspector-title";
    const heading = document.createElement("strong");
    heading.textContent = project.name;
    const sub = document.createElement("span");
    sub.className = "muted";
    sub.textContent = project.path;
    header.append(heading, sub);

    const tabs = document.createElement("div");
    tabs.className = "tabs";
    const tabIds = ["tab.overview", "tab.files", "tab.readiness", "tab.logs", "tab.warnings"];
    if (mappingStatus(project) !== "connected") tabIds.push("tab.connect");
    if (!tabIds.includes(state.tab)) state.tab = "tab.overview";
    for (const tabId of tabIds) {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = t(tabId);
      button.classList.toggle("is-active", state.tab === tabId);
      button.addEventListener("click", () => {
        state.tab = tabId;
        renderInspector(projects);
      });
      tabs.appendChild(button);
    }

    const body = document.createElement("div");
    body.className = "kv-block";
    if (state.tab === "tab.overview") renderOverview(project, body);
    if (state.tab === "tab.files") renderFiles(project, body);
    if (state.tab === "tab.readiness") renderReadiness(project, body);
    if (state.tab === "tab.logs") renderProjectLogs(project, body);
    if (state.tab === "tab.warnings") renderWarnings(project, body);
    if (state.tab === "tab.connect") renderConnect(project, body);

    els.inspectorBody.replaceChildren(header, tabs, body);
  }

  function render(snapshot) {
    state.snapshot = snapshot;
    renderKpi(snapshot.kpi || {});
    renderFirstRunTour(snapshot.tour || {});
    renderReefiki(snapshot.reefiki || {}, snapshot);
    renderCurrentWork(snapshot);
    renderActivity(snapshot.activity_feed || []);
    renderProjects(snapshot.projects || []);
    renderInspector(snapshot.projects || []);
    const generatedAt = snapshot.generated_at;
    const refreshAge = generatedAt ? relativeTime(generatedAt) : "—";
    els.lastRefresh.textContent = refreshAge;
    els.lastRefresh.title = generatedAt ? `${t("ago-relative-prefix")}${refreshAge}` : "";
    els.lastRefresh.classList.remove("stale");
    processI18nNodes(document);
    syncCustomSelects();
  }

  function renderRailPanel() {
    const activityActive = state.railPanel === "activity";
    els.panelActivity.classList.toggle("is-active", activityActive);
    els.panelLogs.classList.toggle("is-active", !activityActive);
    els.activityPanel.hidden = !activityActive;
    els.logsPanel.hidden = activityActive;
  }

  function renderLogStatus(stateValue) {
    const title = t(`logs-status-title.${stateValue}`);
    els.logsStatus.textContent = t(`logs-status.${stateValue}`);
    setTitle(els.logsStatus, title);
    els.logsStatus.className = "badge";
    if (stateValue === "live") els.logsStatus.classList.add("tone-ok");
    if (stateValue === "stale") els.logsStatus.classList.add("tone-warn");
    if (stateValue === "unavailable" || stateValue === "not_configured") els.logsStatus.classList.add("tone-bad");
  }

  function renderLogsPanel() {
    const shouldStickToBottom = state.logForceStickToBottom || state.logPinnedToBottom;
    state.logForceStickToBottom = false;
    const previousScrollTop = els.liveLogs.scrollTop;
    renderLogStatus(state.logState);
    els.liveLogs.replaceChildren();
    if (state.logState === "not_configured") {
      els.logsMeta.textContent = t("logs-not-configured");
    } else if (state.logError) {
      els.logsMeta.textContent = `${t("logs-error")}: ${state.logError}`;
    } else if (state.logsHealth && state.logSource) {
      const source = (state.logsHealth.sources || []).find((item) => item.id === state.logSource);
      const pathText = source && source.path ? source.path : source && source.label;
      const freshness = source && source.last_modified_iso ? relativeTime(source.last_modified_iso) : t("none");
      els.logsMeta.textContent = `${pathText || "—"} · ${t("logs-last-update")} ${freshness}`;
      setTitle(els.logsMeta, els.logsMeta.textContent);
    } else {
      els.logsMeta.textContent = t("logs-empty");
      setTitle(els.logsMeta, els.logsMeta.textContent);
    }

    if (!state.logEntries.length) {
      const placeholder = document.createElement("div");
      placeholder.className = "log-line log-line--empty";
      placeholder.textContent = state.logState === "unavailable" ? t("logs-unavailable") : state.logState === "stale" ? t("logs-stale") : t("logs-empty");
      els.liveLogs.appendChild(placeholder);
      return;
    }

    const frag = document.createDocumentFragment();
    for (const entry of state.logEntries) {
      const line = cloneTpl("tpl-live-log-line");
      fillFields(line, {
        '[data-field="time"]': entry.time || "—",
        '[data-field="level"]': entry.level || "info",
        '[data-field="text"]': entry.text || entry.raw || "—",
      });
      const level = line.querySelector('[data-field="level"]');
      level.classList.add(entry.level || "info");
      if (entry.redacted) line.classList.add("is-redacted");
      frag.appendChild(line);
    }
    els.liveLogs.appendChild(frag);
    if (shouldStickToBottom) {
      els.liveLogs.scrollTop = els.liveLogs.scrollHeight;
      state.logPinnedToBottom = true;
    } else {
      els.liveLogs.scrollTop = Math.min(previousScrollTop, els.liveLogs.scrollHeight);
      state.logPinnedToBottom = isLogsNearBottom();
    }
  }

  async function fetchJson(url) {
    const response = await fetch(url, { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    return response.json();
  }

  async function refreshSnapshot() {
    const snapshot = await fetchJson("/api/snapshot");
    render(snapshot);
  }

  async function refreshLogsHealth() {
    const payload = await fetchJson("/api/logs/health");
    state.logsHealth = payload;
    const selectedBefore = state.logSource;
    const sources = payload.sources || [];
    const frag = document.createDocumentFragment();
    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = t("logs-source-placeholder");
    frag.appendChild(placeholder);
    for (const source of sources) {
      const option = document.createElement("option");
      option.value = source.id;
      option.textContent = source.label;
      option.title = source.path || source.label;
      frag.appendChild(option);
    }
    els.logsSource.replaceChildren(frag);
    if (selectedBefore && sources.some((source) => source.id === selectedBefore)) {
      state.logSource = selectedBefore;
    } else if (!state.logSourceInitialized && !selectedBefore && payload.default_source_id && sources.some((source) => source.id === payload.default_source_id)) {
      state.logSource = payload.default_source_id;
    } else if (!sources.some((source) => source.id === state.logSource)) {
      state.logSource = "";
    }
    state.logSourceInitialized = true;
    els.logsSource.value = state.logSource;
    syncCustomSelect(els.logsSource);
  }

  function stopSnapshotTimer() {
    if (state.snapshotTimer) clearInterval(state.snapshotTimer);
    state.snapshotTimer = null;
  }

  function startSnapshotTimer(ms) {
    stopSnapshotTimer();
    if (ms > 0) {
      state.snapshotTimer = setInterval(() => {
        refreshSnapshot().catch((error) => {
          els.lastRefresh.classList.add("stale");
          els.lastRefresh.textContent = `${t("fetch-failed")}: ${error.message || error}`;
        });
      }, ms);
    }
  }

  function stopLogPolling() {
    if (state.logTimer) clearInterval(state.logTimer);
    state.logTimer = null;
  }

  async function pollLogs(resetCursor) {
    await refreshLogsHealth();
    if (!state.logSource) {
      state.logState = "not_configured";
      state.logError = "";
      state.logEntries = [];
      renderLogsPanel();
      return;
    }
    const healthSource = (state.logsHealth.sources || []).find((source) => source.id === state.logSource);
    if (!healthSource) {
      state.logState = "not_configured";
      state.logError = t("logs-not-configured");
      state.logEntries = [];
      renderLogsPanel();
      return;
    }
    state.logState = healthSource.state || "not_configured";
    if (!healthSource.available) {
      state.logError = healthSource.error || t("logs-unavailable");
      state.logEntries = [];
      renderLogsPanel();
      return;
    }
    const params = new URLSearchParams({
      source: state.logSource,
      limit: "40",
    });
    if (!resetCursor && state.logCursor) {
      params.set("since", state.logCursor);
    }
    const payload = await fetchJson(`/api/logs/tail?${params.toString()}`);
    state.logState = payload.state || state.logState;
    state.logError = payload.error || "";
    state.logCursor = payload.cursor || "";
    if (resetCursor || payload.cursor_reset) {
      state.logPinnedToBottom = true;
      state.logForceStickToBottom = true;
      state.logEntries = payload.entries || [];
    } else if ((payload.entries || []).length) {
      state.logEntries = [...state.logEntries, ...(payload.entries || [])].slice(-120);
    }
    renderLogsPanel();
  }

  function startLogPolling(resetCursor) {
    stopLogPolling();
    if (resetCursor) {
      state.logCursor = "";
      state.logEntries = [];
      state.logPinnedToBottom = true;
      state.logForceStickToBottom = true;
    }
    pollLogs(Boolean(resetCursor)).catch((error) => {
      state.logError = error.message || String(error);
      state.logState = "unavailable";
      renderLogsPanel();
    });
    if (state.logSource) {
      state.logTimer = setInterval(() => {
        pollLogs(false).catch((error) => {
          state.logError = error.message || String(error);
          state.logState = "unavailable";
          renderLogsPanel();
        });
      }, LOG_POLL_MS);
    } else {
      renderLogsPanel();
    }
  }

  async function refreshAll() {
    await Promise.all([refreshSnapshot(), refreshLogsHealth()]);
    renderLogsPanel();
  }

  async function init() {
    state.theme = localStorage.getItem("reefiki.opsDashboard.theme") === "light" ? "light" : "dark";
    state.language = localStorage.getItem("reefiki.opsDashboard.language") === "ru" ? "ru" : "en";
    state.intervalMs = Number(localStorage.getItem("reefiki.opsDashboard.interval") || 0);
    state.firstRunDismissed = localStorage.getItem("reefiki.opsDashboard.firstRun.dismissed") === "1";
    state.pinnedProjects = loadPinnedProjects();

    document.documentElement.dataset.theme = state.theme;
    els.theme.value = state.theme;
    els.lang.value = state.language;
    els.interval.value = String(state.intervalMs);
    enhanceSelects();

    els.theme.addEventListener("change", (event) => {
      state.theme = event.target.value;
      localStorage.setItem("reefiki.opsDashboard.theme", state.theme);
      document.documentElement.dataset.theme = state.theme;
    });
    els.lang.addEventListener("change", (event) => {
      state.language = event.target.value;
      localStorage.setItem("reefiki.opsDashboard.language", state.language);
      applyLanguage();
    });
    els.interval.addEventListener("change", (event) => {
      state.intervalMs = Number(event.target.value);
      localStorage.setItem("reefiki.opsDashboard.interval", String(state.intervalMs));
      startSnapshotTimer(state.intervalMs);
    });
    els.firstRunDismiss.addEventListener("click", () => {
      state.firstRunDismissed = true;
      localStorage.setItem("reefiki.opsDashboard.firstRun.dismissed", "1");
      applyFirstRunVisibility();
    });
    els.refresh.addEventListener("click", () => {
      refreshAll().catch((error) => {
        els.lastRefresh.classList.add("stale");
        els.lastRefresh.textContent = `${t("fetch-failed")}: ${error.message || error}`;
      });
      startLogPolling(true);
    });
    els.inspectorClose.addEventListener("click", () => select(null));
    els.panelActivity.addEventListener("click", () => {
      state.railPanel = "activity";
      renderRailPanel();
    });
    els.panelLogs.addEventListener("click", () => {
      state.railPanel = "logs";
      renderRailPanel();
    });
    els.logsSource.addEventListener("change", (event) => {
      state.logSource = event.target.value;
      state.logPinnedToBottom = true;
      state.logForceStickToBottom = true;
      startLogPolling(true);
    });
    els.logsReconnect.addEventListener("click", () => {
      state.logPinnedToBottom = true;
      state.logForceStickToBottom = true;
      startLogPolling(true);
    });
    els.liveLogs.addEventListener("scroll", () => {
      state.logPinnedToBottom = isLogsNearBottom();
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && state.selected) select(null);
    });

    try {
      state.i18n = await fetchJson("/static/i18n.json");
    } catch {
      state.i18n = { en: {}, ru: {} };
    }
    applyLanguage();
    applyFirstRunVisibility();
    renderRailPanel();
    await refreshAll();
    startSnapshotTimer(state.intervalMs);
    startLogPolling(true);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
      init().catch((error) => {
        els.lastRefresh.classList.add("stale");
        els.lastRefresh.textContent = `${t("fetch-failed")}: ${error.message || error}`;
      });
    });
  } else {
    init().catch((error) => {
      els.lastRefresh.classList.add("stale");
      els.lastRefresh.textContent = `${t("fetch-failed")}: ${error.message || error}`;
    });
  }
})();
