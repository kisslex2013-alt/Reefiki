const root = document.documentElement;
root.classList.add("is-ready");

const copy = {
  en: {
    skip: "Skip to content",
    "nav.flow": "Flow",
    "nav.tokens": "Tokens",
    "nav.safety": "Safety",
    "hero.eyebrow": "Markdown memory for agent work",
    "hero.subtitle": "Local-first distillation wiki for AI agents.",
    "hero.copy": "Turns chat noise into reusable decisions, skills, and project memory.",
    "cta.getStarted": "Get started",
    "cta.readDocs": "Read docs",
    "cta.github": "View GitHub",
    "trust.markdown": "Markdown files",
    "trust.git": "Git history",
    "trust.agents": "Agent-agnostic",
    "scene.noise": "Chat noise",
    "scene.bubble1": "session drift",
    "scene.bubble2": "lost decision",
    "scene.bubble3": "one-off trick",
    "scene.gate": "Distillation gate",
    "scene.rule": "keep reusable",
    "scene.reefLabel": "Distillation current",
    "scene.reefRule": "noise sinks, reusable memory surfaces",
    "scene.card1": "publish stays guarded",
    "scene.card2": "worktree closeout",
    "scene.card3": "next agent handoff",
    "scene.guide": "Rifiki keeps only the useful trail",
    "problem.eyebrow": "The failure mode",
    "problem.title": "AI agents forget between threads.",
    "problem.caption": "The failure is visible: decisions drift away before they become reusable memory.",
    "problem.item1Title": "Decisions stay in chats.",
    "problem.item1Body": "Nobody knows why the project turned left.",
    "problem.item2Title": "Useful procedures vanish.",
    "problem.item2Body": "A fix becomes a story instead of a reusable skill.",
    "problem.item3Title": "The next agent starts cold.",
    "problem.item3Body": "Context gets reread, guessed, or lost.",
    "flow.eyebrow": "How it works",
    "flow.title": "Capture -> Filter -> Save -> Link -> Recall.",
    "flow.copy": "REEFIKI is not a chat archive. It is a distillation loop that lets an agent leave a precise trail for the next agent.",
    "flow.step1Title": "Capture",
    "flow.step1Body": "Sources, notes and session conclusions enter a project inbox.",
    "flow.step2Title": "Filter",
    "flow.step2Body": "The agent keeps material only when it can be reused later.",
    "flow.step3Title": "Save",
    "flow.step3Body": "Useful knowledge becomes markdown decisions, skills or synthesis.",
    "flow.step4Title": "Link",
    "flow.step4Body": "Index, log and references keep the memory navigable.",
    "flow.step5Title": "Recall",
    "flow.step5Body": "The next agent reads bounded context instead of the whole chat history.",
    "flow.caption": "A repeatable loop: collect, filter, save, link, and recall.",
    "token.eyebrow": "Token economy",
    "token.title": "Less context rereading. More reusable memory.",
    "token.copy": "These are rough ranges, not benchmarks or guarantees. The gain comes from reading selected markdown memory instead of dragging every prior thread forward.",
    "token.metric1": "fewer repeat context reads",
    "token.metric2": "for one decision or skill",
    "token.metric3": "for a bounded handoff",
    "token.metric4": "first pass overhead",
    "token.caption": "Public product proof: the distillation flow is already documented in the repository.",
    "memory.eyebrow": "Memory types",
    "memory.title": "Compact markdown cards, not a giant transcript.",
    "memory.caption": "Each reusable note becomes a small typed card, not another transcript to reread.",
    "memory.decisionType": "decision",
    "memory.skillType": "skill",
    "memory.synthesisType": "synthesis",
    "memory.decisionTitle": "Decisions",
    "memory.decisionBody": "What changed, why it changed, and what future agents should respect.",
    "memory.skillTitle": "Skills",
    "memory.skillBody": "Repeatable procedures that turn one solved problem into an agent habit.",
    "memory.conceptTitle": "Concepts",
    "memory.conceptBody": "Reusable understanding of the project, domain, constraints and vocabulary.",
    "memory.synthesisTitle": "Synthesis",
    "memory.synthesisBody": "Session and stage takeaways distilled into a compact handoff trail.",
    "memory.sourceTitle": "Sources",
    "memory.sourceBody": "Where an idea came from, with enough provenance to check it later.",
    "agents.eyebrow": "Agent-agnostic",
    "agents.title": "One project memory, many agents.",
    "agents.copy": "REEFIKI rules live in markdown contracts, so Codex, Claude Code, Cursor, Windsurf, Cline and other LLM agents can follow the same local trail.",
    "agents.other": "Other LLM agents",
    "agents.caption": "Different agents can follow the same local project trail.",
    "graph.label": "Bounded project graph",
    "safety.eyebrow": "Local-first safety",
    "safety.title": "Markdown files, git history, private boundaries.",
    "safety.copy": "No cloud memory is required. Private wiki projects stay local unless a guarded publish flow explicitly says they are safe to expose.",
    "safety.caption": "Local markdown, git history, and guarded public boundaries stay visible.",
    "comparison.eyebrow": "Positioning",
    "comparison.title": "Not another wiki. Not another cloud memory.",
    "comparison.copy": "Use the other tools for storage and search. Use REEFIKI when the next agent must inherit a clean, reusable trail.",
    "comparison.caption": "REEFIKI collects the useful parts into agent-ready project memory.",
    "comparison.notionName": "Notion / Obsidian",
    "comparison.notionGood": "Great for human notes and long-lived documentation.",
    "comparison.notionReefiki": "REEFIKI keeps agent-ready decisions, skills, indexes and logs.",
    "comparison.agentName": "Cursor / Claude memory",
    "comparison.agentGood": "Convenient memory inside one agent surface.",
    "comparison.agentReefiki": "REEFIKI is portable across Codex, Claude Code, Cursor and other agents.",
    "comparison.ragName": "Vector / RAG stores",
    "comparison.ragGood": "Useful for semantic search at scale.",
    "comparison.ragReefiki": "REEFIKI filters first, then keeps reusable knowledge.",
    "comparison.archiveName": "Chat archives",
    "comparison.archiveGood": "Good for preserving the whole conversation.",
    "comparison.archiveReefiki": "REEFIKI turns the useful part into compact project memory.",
    "final.eyebrow": "Try REEFIKI locally",
    "final.title": "Give the next agent a better starting point.",
    "final.quick": "Quick Start",
    "final.caption": "The next agent starts with a prepared project memory.",
    "theme.dark": "Dark",
    "theme.light": "Light"
  },
  ru: {
    skip: "К содержанию",
    "nav.flow": "Цикл",
    "nav.tokens": "Токены",
    "nav.safety": "Безопасность",
    "hero.eyebrow": "Markdown-память для работы агентов",
    "hero.subtitle": "Локальная distillation wiki для AI-агентов.",
    "hero.copy": "Превращает шум чатов в переиспользуемые решения, навыки и память проекта.",
    "cta.getStarted": "Начать",
    "cta.readDocs": "Документация",
    "cta.github": "GitHub",
    "trust.markdown": "Markdown-файлы",
    "trust.git": "Git-история",
    "trust.agents": "Для разных агентов",
    "scene.noise": "Шум чата",
    "scene.bubble1": "дрейф сессии",
    "scene.bubble2": "потерянное решение",
    "scene.bubble3": "разовый прием",
    "scene.gate": "Фильтр памяти",
    "scene.rule": "оставить полезное",
    "scene.reefLabel": "Поток дистилляции",
    "scene.reefRule": "шум тонет, полезная память всплывает",
    "scene.card1": "publish под guard",
    "scene.card2": "закрытие worktree",
    "scene.card3": "handoff агенту",
    "scene.guide": "Рифик оставляет только полезный след",
    "problem.eyebrow": "Где ломается контекст",
    "problem.title": "AI-агенты забывают контекст между тредами.",
    "problem.caption": "Проблема видна сразу: решения уплывают раньше, чем становятся reusable memory.",
    "problem.item1Title": "Решения остаются в чатах.",
    "problem.item1Body": "Потом непонятно, почему проект свернул именно туда.",
    "problem.item2Title": "Процедуры исчезают.",
    "problem.item2Body": "Один найденный фикс не становится повторяемым навыком.",
    "problem.item3Title": "Следующий агент стартует с нуля.",
    "problem.item3Body": "Контекст перечитывается, угадывается или теряется.",
    "flow.eyebrow": "Как это работает",
    "flow.title": "Собрать -> Отфильтровать -> Сохранить -> Связать -> Вспомнить.",
    "flow.copy": "REEFIKI не архивирует весь чат. Это цикл дистилляции, который оставляет следующему агенту короткий пригодный след.",
    "flow.step1Title": "Собрать",
    "flow.step1Body": "Источники, заметки и выводы попадают в копилку проекта.",
    "flow.step2Title": "Фильтр",
    "flow.step2Body": "Агент оставляет только то, что можно применить снова.",
    "flow.step3Title": "Сохранить",
    "flow.step3Body": "Полезное становится markdown-решением, навыком или synthesis.",
    "flow.step4Title": "Связать",
    "flow.step4Body": "Индекс, журнал и ссылки делают память навигируемой.",
    "flow.step5Title": "Вспомнить",
    "flow.step5Body": "Следующий агент читает ограниченный контекст, а не всю историю чата.",
    "flow.caption": "Повторяемый цикл: собрать, отфильтровать, сохранить, связать и вспомнить.",
    "token.eyebrow": "Экономия токенов",
    "token.title": "Меньше перечитывания. Больше полезной памяти.",
    "token.copy": "Это грубые диапазоны, не бенчмарки и не гарантии. Выигрыш появляется потому, что агент читает выбранную markdown-память, а не тащит всю историю.",
    "token.metric1": "меньше повторного чтения контекста",
    "token.metric2": "для одного решения или навыка",
    "token.metric3": "для bounded handoff",
    "token.metric4": "первичный overhead",
    "token.caption": "Публичное product proof: цикл дистилляции уже описан в репозитории.",
    "memory.eyebrow": "Типы памяти",
    "memory.title": "Короткие markdown-карточки вместо гигантского transcript.",
    "memory.caption": "Каждая полезная заметка становится маленькой typed-карточкой, а не новым transcript для перечитывания.",
    "memory.decisionType": "решение",
    "memory.skillType": "навык",
    "memory.synthesisType": "synthesis",
    "memory.decisionTitle": "Решения",
    "memory.decisionBody": "Что изменилось, почему и что будущий агент должен уважать.",
    "memory.skillTitle": "Навыки",
    "memory.skillBody": "Повторяемые процедуры, превращающие один фикс в привычку агента.",
    "memory.conceptTitle": "Концепты",
    "memory.conceptBody": "Понимание проекта, домена, ограничений и словаря.",
    "memory.synthesisTitle": "Synthesis",
    "memory.synthesisBody": "Выводы сессий и этапов, сжатые в пригодный handoff.",
    "memory.sourceTitle": "Источники",
    "memory.sourceBody": "Откуда пришла идея, с достаточным provenance для проверки.",
    "agents.eyebrow": "Для разных агентов",
    "agents.title": "Одна память проекта, много агентов.",
    "agents.copy": "Правила REEFIKI живут в markdown-контрактах, поэтому Codex, Claude Code, Cursor, Windsurf, Cline и другие агенты могут идти по одному локальному следу.",
    "agents.other": "Другие LLM-агенты",
    "agents.caption": "Разные агенты могут идти по одному локальному следу проекта.",
    "graph.label": "Ограниченный граф проекта",
    "safety.eyebrow": "Local-first safety",
    "safety.title": "Markdown-файлы, git-история, приватные границы.",
    "safety.copy": "Облачная память не нужна. Приватные wiki-проекты остаются локальными, пока guarded publish flow явно не подтвердит безопасную публикацию.",
    "safety.caption": "Локальный markdown, git-история и guarded-публикация остаются видимыми.",
    "comparison.eyebrow": "Позиционирование",
    "comparison.title": "Не ещё одна wiki. Не ещё одна cloud memory.",
    "comparison.copy": "Остальные инструменты хороши для хранения и поиска. REEFIKI нужен, когда следующий агент должен получить чистый переиспользуемый след.",
    "comparison.caption": "REEFIKI собирает полезное в память проекта, пригодную агенту.",
    "comparison.notionName": "Notion / Obsidian",
    "comparison.notionGood": "Хороши для заметок человека и долгой документации.",
    "comparison.notionReefiki": "REEFIKI хранит решения, навыки, индексы и журналы в виде, пригодном агенту.",
    "comparison.agentName": "Cursor / Claude memory",
    "comparison.agentGood": "Удобная память внутри одного агентского интерфейса.",
    "comparison.agentReefiki": "REEFIKI переносится между Codex, Claude Code, Cursor и другими агентами.",
    "comparison.ragName": "Vector / RAG stores",
    "comparison.ragGood": "Полезны для поиска по большой базе источников.",
    "comparison.ragReefiki": "REEFIKI сначала фильтрует, затем хранит только полезное.",
    "comparison.archiveName": "Архивы чатов",
    "comparison.archiveGood": "Подходят, если нужно сохранить весь разговор.",
    "comparison.archiveReefiki": "REEFIKI превращает полезную часть в короткую память проекта.",
    "final.eyebrow": "Попробуй REEFIKI локально",
    "final.title": "Дай следующему агенту лучшую стартовую точку.",
    "final.quick": "Быстрый старт",
    "final.caption": "Следующий агент стартует с подготовленной памятью проекта.",
    "theme.dark": "Тёмная",
    "theme.light": "Светлая"
  }
};

const storedLang = localStorage.getItem("reefiki-lang");
const initialLang = storedLang || (navigator.language.toLowerCase().startsWith("ru") ? "ru" : "en");
const storedTheme = localStorage.getItem("reefiki-theme");
const initialTheme = storedTheme || "light";

function applyLanguage(lang) {
  const dictionary = copy[lang] || copy.en;
  root.lang = lang;

  for (const node of document.querySelectorAll("[data-i18n]")) {
    const value = dictionary[node.dataset.i18n];
    if (value) node.textContent = value;
  }

  for (const link of document.querySelectorAll("[data-href-en]")) {
    link.href = link.dataset[`href${lang[0].toUpperCase()}${lang.slice(1)}`] || link.dataset.hrefEn;
  }

  for (const button of document.querySelectorAll("[data-lang-toggle]")) {
    const active = button.dataset.langToggle === lang;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-pressed", String(active));
  }

  localStorage.setItem("reefiki-lang", lang);
  updateThemeButton();
}

function applyTheme(theme) {
  root.dataset.theme = theme;
  localStorage.setItem("reefiki-theme", theme);
  updateThemeButton();
}

function updateThemeButton() {
  const label = document.querySelector("[data-theme-label]");
  if (!label) return;
  const lang = root.lang === "ru" ? "ru" : "en";
  const nextTheme = root.dataset.theme === "dark" ? "light" : "dark";
  label.textContent = copy[lang][`theme.${nextTheme}`];
}

applyTheme(initialTheme);
applyLanguage(initialLang);

for (const button of document.querySelectorAll("[data-lang-toggle]")) {
  button.addEventListener("click", () => applyLanguage(button.dataset.langToggle));
}

const themeToggle = document.querySelector("[data-theme-toggle]");
if (themeToggle) {
  themeToggle.addEventListener("click", () => {
    applyTheme(root.dataset.theme === "dark" ? "light" : "dark");
  });
}

const revealItems = Array.from(document.querySelectorAll(".reveal"));
let lastScrollY = window.scrollY;
let scrollDirection = "down";
let scrollTicking = false;

function syncScrollDirection() {
  const nextScrollY = window.scrollY;
  if (Math.abs(nextScrollY - lastScrollY) > 4) {
    scrollDirection = nextScrollY > lastScrollY ? "down" : "up";
    root.dataset.scrollDirection = scrollDirection;
    lastScrollY = nextScrollY;
  }
  scrollTicking = false;
}

root.dataset.scrollDirection = scrollDirection;

window.addEventListener(
  "scroll",
  () => {
    if (scrollTicking) return;
    scrollTicking = true;
    window.requestAnimationFrame(syncScrollDirection);
  },
  { passive: true }
);

if ("IntersectionObserver" in window) {
  const observer = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          entry.target.classList.remove("reveal-from-top", "reveal-from-bottom");
          entry.target.classList.add(scrollDirection === "up" ? "reveal-from-top" : "reveal-from-bottom");
          entry.target.classList.add("is-visible");
        } else if (entry.boundingClientRect.top > window.innerHeight || entry.boundingClientRect.bottom < 0) {
          entry.target.classList.remove("is-visible");
        }
      }
    },
    { rootMargin: "-8% 0px -8% 0px", threshold: 0.08 }
  );

  for (const item of revealItems) {
    observer.observe(item);
  }
} else {
  for (const item of revealItems) {
    item.classList.add("is-visible");
  }
}

const reefVideos = Array.from(document.querySelectorAll("[data-reef-video]"));
const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const snapSections = Array.from(document.querySelectorAll("main > section"));
const snapMedia = window.matchMedia("(min-width: 900px) and (min-height: 680px) and (pointer: fine)");
let snapLocked = false;

function currentSnapIndex() {
  const anchor = window.scrollY + window.innerHeight * 0.36;
  let bestIndex = 0;
  let bestDistance = Number.POSITIVE_INFINITY;

  snapSections.forEach((section, index) => {
    const distance = Math.abs(section.offsetTop - anchor);
    if (distance < bestDistance) {
      bestDistance = distance;
      bestIndex = index;
    }
  });

  return bestIndex;
}

function snapToSection(direction) {
  if (!snapSections.length || snapLocked) return;
  const nextIndex = Math.min(snapSections.length - 1, Math.max(0, currentSnapIndex() + direction));
  const target = snapSections[nextIndex];
  if (!target) return;

  snapLocked = true;
  target.scrollIntoView({ block: "start", behavior: reduceMotion ? "auto" : "smooth" });
  window.setTimeout(() => {
    snapLocked = false;
  }, reduceMotion ? 120 : 760);
}

window.addEventListener(
  "wheel",
  (event) => {
    if (!snapMedia.matches || event.ctrlKey || Math.abs(event.deltaY) < 24) return;
    event.preventDefault();
    snapToSection(event.deltaY > 0 ? 1 : -1);
  },
  { passive: false }
);

if (reduceMotion) {
  for (const video of reefVideos) {
    video.pause();
    video.removeAttribute("autoplay");
  }
} else if ("IntersectionObserver" in window) {
  const videoObserver = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        const video = entry.target;
        if (entry.isIntersecting) {
          video.play().catch(() => undefined);
        } else {
          video.pause();
        }
      }
    },
    { rootMargin: "240px", threshold: 0.15 }
  );

  for (const video of reefVideos) {
    videoObserver.observe(video);
  }
}

const scene = document.querySelector(".hero-scene");

if (scene) {
  scene.addEventListener("pointermove", (event) => {
    const rect = scene.getBoundingClientRect();
    const x = (event.clientX - rect.left) / rect.width - 0.5;
    const y = (event.clientY - rect.top) / rect.height - 0.5;
    scene.style.setProperty("--scene-x", `${x * 8}px`);
    scene.style.setProperty("--scene-y", `${y * 8}px`);
  });

  scene.addEventListener("pointerleave", () => {
    scene.style.removeProperty("--scene-x");
    scene.style.removeProperty("--scene-y");
  });
}

const graph = document.querySelector(".graph-proof");
let graphZoom = 1;

function setGraphZoom(nextZoom) {
  graphZoom = Math.min(1.35, Math.max(0.9, nextZoom));
  if (graph) graph.style.setProperty("--graph-zoom", graphZoom.toFixed(2));
}

for (const button of document.querySelectorAll("[data-graph-zoom]")) {
  button.addEventListener("click", () => {
    setGraphZoom(graphZoom + (button.dataset.graphZoom === "in" ? 0.1 : -0.1));
  });
}
