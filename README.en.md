# REEFIKI

![REEFIKI: Rifiki turns AI-session noise into useful memory](assets/reefiki-hero-mascot.png)

<p align="center">
  <a href="QUICKSTART.md#english"><img alt="Quick Start" src="https://img.shields.io/badge/Quick_Start-0B7FCC?style=for-the-badge"></a>
  <a href="LICENSE"><img alt="License: Apache 2.0" src="https://img.shields.io/badge/License-Apache_2.0-2E7D32?style=for-the-badge"></a>
  <a href="#safety"><img alt="Local first" src="https://img.shields.io/badge/Local_First-by_default-3E6B5A?style=for-the-badge"></a>
  <a href="#for-agents"><img alt="For agents" src="https://img.shields.io/badge/For_Agents-Codex_|_Claude_|_Gemini_|_Mimo-6A4BBC?style=for-the-badge"></a>
  <a href="docs/PUBLIC_DEMO.md#english"><img alt="Public demo" src="https://img.shields.io/badge/Public_Demo-docs-E07A2F?style=for-the-badge"></a>
  <a href="COMMANDS.md#english"><img alt="Commands" src="https://img.shields.io/badge/Commands-reference-455A64?style=for-the-badge"></a>
</p>

AI agents are fast, but they are bad at remembering project context: decisions stay buried in chats, useful procedures disappear, and the next agent starts from zero again.

**REEFIKI** solves that problem as a local wiki memory for AI agents: it keeps only the knowledge that is likely to be useful again, not the whole session noise.

[Русский](README.md) · [中文](README.zh-CN.md) · [Quick Start](QUICKSTART.md#english) · [Commands](COMMANDS.md#english)

---

## The Problem

AI-agent work often breaks not because of code, but because of memory.

After a few threads, the same issues appear:

- an important decision is stuck in a chat and cannot be found;
- a new agent does not know why the project is shaped this way;
- a useful trick was discovered once but never became a reusable skill;
- links, notes, and conclusions get mixed with drafts and noise;
- agent memory becomes either too short or too dirty.

A normal note-taking system does not fully solve this either: it is easy to save everything, but hard to separate reusable knowledge from accidental context.

## What REEFIKI Is

REEFIKI is a local multi-project distillation wiki for AI agents.

In practice:

- every project has its own wiki;
- the agent saves decisions, skills, conclusions, and sources there;
- weak or temporary material is deferred instead of polluting the base;
- everything is stored as markdown files with git history;
- workflow rules live in `AGENTS.md`, so different agents can follow them.

REEFIKI is not another chatbot, cloud memory service, or archive of every message. It is a filter that turns working chaos into short, verifiable, portable project memory.

## Project Profiles

Not every REEFIKI project is the same. When creating or connecting a project, you can tell the agent which profile it is:

| Profile | Use for | Examples |
|---|---|---|
| `agent_surface` | rules, skills, adapters, diagnostics, and recovery for agent/IDE/runtime environments | Codex, Claude Code, Gemini, Mimo, Hermes |
| `product` | product decisions, delivery evidence, UX, and release knowledge | Metrica |
| `knowledge_domain` | topic/domain knowledge without a primary runtime layer | Suno, Instagram, Security Guidance |
| `reefiki_core` | REEFIKI rules and governance | reefiki |

This is a manual onboarding label, not a required schema field. Details: [docs/PROJECT_PROFILES.md](docs/PROJECT_PROFILES.md#english).

## Why It Exists

REEFIKI is useful when you work with AI agents regularly and want them to:

- continue with awareness of past decisions;
- avoid repeating mistakes that were already solved;
- recover project context quickly;
- save procedures as reusable skills;
- separate private memory from public material;
- hand work off between Codex, Claude Code, Cursor, Windsurf, and other agents.

The core idea: **an agent should not only finish a task, but also leave a reusable trace behind**.

## How It Works

![How REEFIKI turns noise into memory](assets/reefiki-architecture.svg)

REEFIKI follows a simple cycle:

1. **Capture**: a link, file, decision, or conclusion enters the project inbox.
2. **Filter**: the agent checks whether it can be applied again.
3. **Save**: useful material becomes a wiki page, skill, decision, or synthesis.
4. **Link**: pages get links, an index entry, and a log record.
5. **Recall later**: the next agent answers from the accumulated wiki, not from guesses.

REEFIKI uses a few durable memory types:

| Type | What it stores |
|---|---|
| `sources` | where an idea or material came from |
| `concepts` | reusable understanding |
| `decisions` | a decision and its reason |
| `skills` | a reproducible procedure |
| `synthesis` | conclusions from a session or project stage |

## Rifiki

![Rifiki, the REEFIKI mascot](assets/reefiki-mascot.png)

Rifiki is a small reef crab archivist: a keeper of the reef wiki who does not drag every grain of sand into memory, but selects the useful shells. In the README, Rifiki is a metaphor: session noise on the left, distillation in the center, clean project memory on the right.

## Quick Start

The shortest safe first run uses the CLI. `reefiki tour` shows the current step without writing files, and `reefiki onboarding` opens the guided terminal wizard. For a deterministic demo:

```powershell
pipx install git+https://github.com/kisslex2013-alt/reefiki.git
pipx ensurepath
reefiki --help
reefiki tour
reefiki onboarding
reefiki onboarding --fixture-root C:\Temp\reefiki-demo
reefiki --project C:\Temp\reefiki-demo\projects\reefiki-onboarding-demo status
reefiki ops-dashboard demo --fixture-root C:\Temp\reefiki-dashboard-demo
reefiki ops-dashboard serve --workspace-root C:\Temp\reefiki-dashboard-demo --port 7310
```

If the CLI is not installed yet, the same first-run flow works from a checkout:

```powershell
python scripts\reefiki.py tour
python scripts\reefiki.py onboarding
python scripts\reefiki.py onboarding --fixture-root C:\Temp\reefiki-demo
python scripts\reefiki.py --project C:\Temp\reefiki-demo\projects\reefiki-onboarding-demo status
python scripts\reefiki.py ops-dashboard demo --fixture-root C:\Temp\reefiki-dashboard-demo
python scripts\reefiki.py ops-dashboard serve --workspace-root C:\Temp\reefiki-dashboard-demo --port 7310
```

If you already have a code project, open REEFIKI and tell the agent:

```text
Connect H:\Projects\MyApp to the wiki
```

The agent will create a separate wiki project and add a `_wiki/` link to the code project.

If you want to start a new wiki from scratch:

```text
Create a new project metrica about product analytics
```

Then work with plain phrases:

| You say | The agent does |
|---|---|
| "put this in the inbox" | saves material for later processing |
| "process the inbox" | turns useful material into wiki pages |
| "remember this as a decision" | saves a durable decision |
| "save this as a skill" | records a reusable procedure |
| "what did we decide about sync?" | answers only from the accumulated wiki |
| "capture the session conclusions" | saves a synthesis |

Full first-run guide: [QUICKSTART.md](QUICKSTART.md#english). Install details: [docs/INSTALL.md](docs/INSTALL.md#english).

## What It Can Do Today

- Separate wiki projects under `projects/<name>/`.
- Connect an existing code project through `_wiki`.
- Capture -> process -> query -> harvest workflow.
- Agent-agnostic rules through `AGENTS.md`.
- Manual project profiles for agent/runtime, product, and knowledge-domain projects.
- Local markdown files instead of closed cloud storage.
- Wiki log and index.
- Health/lint checks to keep the base from becoming a dump.
- Handoff context for the next agent.
- Clear boundaries between local/private memory and material that can be shared publicly.

Full capability map: [COMMANDS.md](COMMANDS.md#english).

## What REEFIKI Is Not

REEFIKI is intentionally not:

- a storage system for every chat message;
- a replacement for git, Obsidian, or an issue tracker;
- an automatic cloud sync service;
- a vector database "just in case";
- a system that writes anywhere without project boundaries.

If material cannot be applied again, it should not become durable wiki memory.

## Safety

REEFIKI is local-first by default:

- user wiki projects stay local;
- `raw/` is treated as an immutable archive;
- secrets, binaries, and oversized files are not saved automatically;
- public material is separated from local wiki projects and checked before publishing;
- the agent changes only explicitly selected project files.

In short: REEFIKI makes memory useful without blurring project boundaries.

## For Agents

Agents do not need to remember internal commands. They read `AGENTS.md` and follow the project contract:

- from the REEFIKI root, they can create and connect projects;
- inside `projects/<name>/`, they can save and process knowledge;
- old `wiki/log.md` entries are never rewritten;
- `raw/` is not edited;
- all durable writes must be explainable and reproducible.

That makes REEFIKI portable across Codex, Claude Code, Cursor, Windsurf/Cascade, Cline, and other LLM agents.

If a project is an agent/IDE/runtime environment such as Codex, Claude Code, Gemini, Mimo, or Hermes, treat it as an `agent_surface`: preserve portable procedures, adapters, diagnostics, and recovery notes, but do not merge wikis or copy skills automatically.

## Token Economy

![How REEFIKI discards noise and keeps useful tokens](assets/reefiki-token-economy.png)

REEFIKI reduces token waste not by magically compressing everything, but by making the agent read less junk.

- Instead of the whole chat, the agent recalls short `decisions`, `skills`, `concepts`, and `synthesis` pages.
- Projects are isolated, so unrelated context does not leak into the current task.
- `wiki/index.md` and the log help find relevant pages without rereading the whole base.
- The handoff pack builds a bounded context bundle for the next agent.
- Weak material stays in the inbox or refusal path instead of becoming permanent memory.

Rule of thumb, not a guarantee: one short `decision` or `skill` page is often around 500-2,000 tokens and can replace 5,000-30,000 tokens of old chat context. A practical handoff pack usually stays around 2,000-8,000 tokens instead of tens of thousands of history tokens.

On repeat tasks, this often means roughly 50-90% fewer context-reading tokens; for returning to one decision or skill, the reduction can be 70-95%.

Details: [docs/TOKEN_ECONOMY.md#english](docs/TOKEN_ECONOMY.md#english).

## Next

- [QUICKSTART.md](QUICKSTART.md#english): first run without knowing the CLI.
- [COMMANDS.md](COMMANDS.md#english): all REEFIKI operations.
- [docs/TOKEN_ECONOMY.md](docs/TOKEN_ECONOMY.md#english): how REEFIKI saves tokens.
- [docs/INSTALL.md](docs/INSTALL.md#english): CLI install and smoke test.
- [docs/obsidian-setup.md](docs/obsidian-setup.md#english): safe Obsidian setup.
- [docs/PUBLIC_DEMO.md](docs/PUBLIC_DEMO.md#english): public demo and boundaries.
- [docs/RECOVERY.md](docs/RECOVERY.md#english): recovery after failures.

Public roadmap: [docs/PUBLIC_ROADMAP.md](docs/PUBLIC_ROADMAP.md#english). Public backlog: [docs/PUBLIC_BACKLOG.md](docs/PUBLIC_BACKLOG.md#english).

## License

REEFIKI code is distributed under Apache License 2.0. See [LICENSE](LICENSE).

Wiki-project content belongs to the user who created or added it.

## Acknowledgements and design influences

REEFIKI is an independent implementation. The materials and tools below are not imported as REEFIKI codebases and are not copied source code. They influenced the product as ideas, vocabulary, architecture patterns, and operating constraints.

- [Karpathy's LLM Wiki gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f): the idea of a compact, agent-readable wiki instead of repeatedly replaying chat history; distillation over raw archiving.
- REEF protocol: the `capture -> distillation -> telemetry` loop; cheap capture, deliberate processing, and later reuse as separate stages.
- [Vannevar Bush's "As We May Think"](https://www.w3.org/History/1945/vbush/vbush.shtml): Memex, associative trails, durable personal memory, and connected knowledge instead of isolated notes.
- [Markdown wiki and Obsidian-style workflows](https://obsidian.md/help/links): local markdown files, wikilinks, graph/viewer thinking, and readable knowledge without a cloud service. REEFIKI is not an Obsidian clone: its source of truth stays in the repository and agent-aware rules.
- [Git worktree workflow](https://git-scm.com/docs/git-worktree): isolated task work, reviewable changes, and careful separation between local/private content and the public snapshot.
- [`memoir`](https://www.memoir-ai.dev/): short working memory and preferences as a separate layer. In REEFIKI it is an optional short-memory provider; durable truth remains in the markdown wiki.
- [Graphify](https://graphify.net/) and graph-based retrieval: a graph of code, files, and documents as a navigation and candidate-selection layer. REEFIKI does not become a graph database; it uses graph ideas for relationships and compact context.
- [CodeGraph-style navigation](https://github.com/CodeGraphContext/CodeGraphContext): disposable impact/callgraph/relationship queries over code as a developer aid, not as durable memory.
- Agent/IDE runtimes: Codex, Claude Code, Cursor, Windsurf/Cascade, Cline, Gemini, Mimo, and Hermes influenced the vendor-neutral `AGENTS.md`, project profiles, portable rules, and reusable runbooks.
- Local-first security practice: explicit project boundaries, public-material checks, append-only logs, immutable `raw/`, and avoiding broad save-everything behavior as REEFIKI-specific safety infrastructure.

The practical goal of REEFIKI is to combine wiki, agent workflow, short memory, graph navigation, and Git discipline into one local-first process where knowledge can be verified, transferred, and published safely.
