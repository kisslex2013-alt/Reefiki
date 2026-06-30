# Agent Readiness / Skill Recommendation Spec

Цель функции: проанализировать git-репозиторий и выдать стабильный, объяснимый план того, какие skills, rules, adapters и hooks нужны этому repo, чтобы AI-агенты работали безопасно и предсказуемо.

Функция не является paid feature в MVP. Она должна быть надёжным бесплатным ядром, которое создаёт доверие: REEFIKI понимает форму repo, видит agent risks и предлагает конкретные меры без silent mutation.

## Summary

Рабочие имена:

- `agent-readiness`
- `skills recommend`
- `Agent Readiness Plan`
- `Repo Skill Advisor`

Рекомендуемый CLI:

```powershell
python scripts\reefiki.py agent-readiness --repo <path>
python scripts\reefiki.py skills recommend --repo <path>
```

Обе команды должны вести к одному движку. `agent-readiness` — основной пользовательский entrypoint. `skills recommend` — более конкретный alias для людей, которые ищут именно skills.

## Design Principles

1. **Read-only by default.** MVP ничего не меняет в анализируемом repo.
2. **Deterministic first.** Первая версия работает на file/git signals и rule mapping, без LLM.
3. **Explain every recommendation.** Каждая рекомендация имеет evidence, risk и confidence.
4. **One scan, four blocks.** Пользователь запускает один анализ, а REEFIKI раскладывает результат на skills, rules, adapters и hooks.
5. **No auto-install.** Любое применение идёт только через separate install plan и explicit confirmation.
6. **Portable core.** Skills описываются как markdown workflows, adapters подключают их к конкретным runtimes.
7. **No new memory runtime.** Функция не создаёт новый durable memory layer.

## Output Model

После анализа repo REEFIKI должен выдавать:

```text
Agent Readiness Plan
├── verdict
├── detected repo shape
├── risks
├── recommended skills
├── recommended rules
├── recommended adapters
├── recommended hooks
├── custom skill drafts
├── install plan
└── blocked / do-not-auto-apply actions
```

## Four Recommendation Blocks

### Skills

Skills отвечают на вопрос: **какие reusable workflows нужны агенту?**

Примеры:

- `safe-task-worktree-bootstrap`
- `source-of-truth-diagnostics`
- `staged-scope-and-publish-guard`
- `reefiki-experience-monitor`
- `durable-harvest-closeout`
- `browser-runtime-smoke-gate`
- `security-best-practices`
- `release-readiness-gates`

### Rules

Rules отвечают на вопрос: **какие постоянные инструкции должны быть видны агенту в этом repo?**

Примеры:

- одна задача = один worktree;
- base branch = `origin/main`;
- не трогать `raw/`, `.env*`, generated dirs;
- publish только через approved flow;
- test command перед completion;
- source-of-truth docs читать первыми.

### Adapters

Adapters отвечают на вопрос: **как подключить skills/rules к конкретной среде?**

Примеры:

- Codex: `AGENTS.md`, local skills, `.codex/hooks.json`;
- Claude Code: `CLAUDE.md`, `.claude/commands`, skills;
- Cursor: `.cursor/rules/*.mdc`, `.cursorrules`;
- Qwen/DeepSeek wrappers: `AGENTS.md` + markdown skill folders;
- Hermes: runtime prompt + tool policy + REEFIKI wiki bridge.

### Hooks

Hooks отвечают на вопрос: **что нужно enforce-ить автоматически?**

Примеры:

- block `git add -A`, `git add .`, `git add ..`;
- block manual `git push`;
- check staged paths before commit;
- run secret scan;
- block public snapshot if private inventory is incomplete;
- block publish from dirty worktree.

Hooks не должны заменять reasoning. Они нужны только для deterministic enforcement.

## Input Signals

### Git Signals

Собирать:

- current branch;
- dirty status;
- staged paths;
- untracked files;
- remotes;
- public/private remotes;
- worktrees;
- ahead/behind against base;
- long-lived/diverged branches;
- merge/rebase state;
- `.gitignore`.

Risk examples:

| Signal | Risk |
|---|---|
| Dirty shared checkout | Agent may capture unrelated files. |
| Many worktrees | Parallel-agent collision risk. |
| Public remote present | Private/public leak risk. |
| Branch behind base | Publish/merge conflict risk. |
| Staged broad diff | Unsafe commit risk. |

### Repo Shape Signals

Собирать:

- languages;
- package managers;
- frontend/backend/library/CLI/docs classification;
- monorepo markers;
- test/build scripts;
- CI workflows;
- deploy configs;
- database/migration configs;
- auth/security/payment folders;
- generated dirs;
- docs and source-of-truth files.

Examples:

| Files | Repo shape |
|---|---|
| `package.json`, `src/app`, `next.config.*` | frontend / Next.js |
| `pyproject.toml`, `pytest.ini` | Python project |
| `Cargo.toml` | Rust project |
| `.github/workflows/*` | CI present |
| `vercel.json`, `wrangler.toml`, `Dockerfile` | deploy surface |
| `migrations/`, `schema.prisma` | database/migration risk |

### Agent Surface Signals

Собирать:

- `AGENTS.md`;
- `CLAUDE.md`;
- `.claude/commands/**`;
- `.claude/skills/**`;
- `.codex/**`;
- `.cursor/rules/**`;
- `.cursorrules`;
- `.windsurf/**`;
- `.clinerules`;
- local `skills/**`;
- existing hooks.

Risk examples:

| Signal | Risk |
|---|---|
| No `AGENTS.md` | Agent lacks repo contract. |
| Rules exist but no test commands | Incomplete completion criteria. |
| Hooks exist but undocumented | Hidden enforcement risk. |
| Multiple agent rule files diverge | Conflicting instructions. |

## Risk Model

Each risk should have:

- `id`;
- `severity`: `P0`, `P1`, `P2`;
- `confidence`: `high`, `medium`, `low`;
- `evidence`;
- `recommended_blocks`: skills/rules/adapters/hooks;
- `do_not_auto_apply` boolean.

Severity guide:

| Severity | Meaning | Examples |
|---|---|---|
| P0 | Can cause data leak, destructive git action, or unsafe publish. | Public/private leak, manual push risk, dirty publish, secrets. |
| P1 | Can cause bad agent work or false completion. | No `AGENTS.md`, missing tests, missing worktree rule. |
| P2 | Improves ergonomics or adoption. | Cursor adapter, richer closeout format, optional dashboards. |

Confidence guide:

| Confidence | Evidence |
|---|---|
| high | Direct file/git signal. |
| medium | Path/name pattern or common framework structure. |
| low | Weak inference requiring user review. |

## Recommendation Mapping

Initial deterministic mapping:

| Risk / Signal | Skills | Rules | Adapters | Hooks |
|---|---|---|---|---|
| Dirty shared checkout | `safe-task-worktree-bootstrap` | one task = one worktree | generic/Codex/Claude | optional broad staging blocker |
| No agent contract | `source-of-truth-diagnostics` | add `AGENTS.md` | generic agents | none |
| Public/private remotes | `staged-scope-and-publish-guard` | publish only through approved flow | Codex/Claude commands | publish preflight, secret scan |
| Frontend app | `browser-runtime-smoke-gate` | browser-visible changes require smoke | Codex browser adapter | none by default |
| Auth/security/payment | `security-best-practices` | security review before completion | generic | optional secret scan |
| DB migrations | `legacy-migration-audit` | migration rollback/backup rules | generic | block unreviewed migration apply |
| Release/deploy config | `release-readiness-gates` | deploy checklist | CI adapter | optional release gate |
| Existing REEFIKI wiki | `reefiki-experience-monitor` | read wiki before non-trivial work | REEFIKI bridge | none |
| Valuable session outcomes | `durable-harvest-closeout` | harvest after decisions/fixes | REEFIKI bridge | none |

## Ready Skill vs Custom Skill

Recommendation types:

### Use existing base skill

Use when:

- risk maps cleanly to an existing base skill;
- skill covers workflow without repo-specific changes.

Output:

```json
{
  "type": "use_existing_skill",
  "skill": "safe-task-worktree-bootstrap",
  "priority": "P0",
  "reason": "dirty shared checkout risk"
}
```

### Use optional skill

Use when:

- risk is task-specific or project-shape-specific;
- skill should not become always-on.

Output:

```json
{
  "type": "use_optional_skill",
  "skill": "browser-runtime-smoke-gate",
  "trigger": "frontend route/component/form changes"
}
```

### Create custom skill draft

Use when:

- repo has custom deploy/release/support/security workflow;
- existing skill is too generic;
- evidence is strong enough to draft but not auto-apply.

Output:

```json
{
  "type": "create_custom_skill_draft",
  "name": "myapp-deploy-guard",
  "write_allowed": false,
  "reason": "custom deploy workflow detected without agent-facing safety rules"
}
```

### Adapter-only recommendation

Use when:

- workflow exists, but agent runtime cannot see it;
- e.g. `AGENTS.md` exists but Cursor rules do not.

Output:

```json
{
  "type": "adapter_only",
  "adapter": "cursor",
  "reason": "project has AGENTS.md but no Cursor rules surface"
}
```

## CLI Spec

### Text report

```powershell
python scripts\reefiki.py agent-readiness --repo D:\Projects\MyApp
```

### JSON

```powershell
python scripts\reefiki.py agent-readiness --repo D:\Projects\MyApp --format json
```

### Write report

```powershell
python scripts\reefiki.py agent-readiness --repo D:\Projects\MyApp --write-report
```

Output path:

```text
reports/agent-readiness-YYYY-MM-DD.md
```

### Future install plan

Not MVP:

```powershell
python scripts\reefiki.py agent-readiness plan-install --repo D:\Projects\MyApp
python scripts\reefiki.py agent-readiness apply-plan --plan <path> --yes
```

`apply-plan` must not exist until report-only behavior is stable.

## JSON Schema Draft

```json
{
  "schema_version": "agent-readiness.v1",
  "repo": {
    "path": "D:/Projects/MyApp",
    "root": "D:/Projects/MyApp",
    "branch": "main"
  },
  "summary": {
    "risk_level": "P1",
    "repo_types": ["frontend", "typescript"],
    "agent_surfaces": ["AGENTS.md"],
    "recommendation_count": 5
  },
  "signals": [],
  "risks": [],
  "recommendations": {
    "skills": [],
    "rules": [],
    "adapters": [],
    "hooks": []
  },
  "custom_skill_drafts": [],
  "install_plan": [],
  "blocked_actions": []
}
```

## Markdown Report Format

```md
# Agent Readiness Report

## Verdict

## Detected Repo Shape

## Risks

## Recommended Skills

## Recommended Rules

## Recommended Adapters

## Recommended Hooks

## Custom Skill Drafts

## Install Plan

## Do Not Auto-Apply
```

## Safety Requirements

MVP must:

- never modify analyzed repo;
- never run package scripts;
- never read secrets content beyond safe filename/path checks;
- never scan `.git/`, `node_modules/`, `dist/`, `build`, `.next`, `target` deeply;
- never auto-install hooks/adapters;
- never write reports inside target repo unless explicitly requested;
- resolve paths safely and reject traversal outside target root;
- treat symlinks/junctions conservatively;
- mark low-confidence findings as review-needed.

## Stability Requirements

The engine must be:

- deterministic;
- testable with synthetic repos;
- schema-versioned;
- independent from external network;
- usable without LLM;
- tolerant of missing git, detached HEAD, no remotes, and non-git folders;
- readable in both text and JSON.

## Conflict Handling

### Existing files

If `AGENTS.md`, `.cursor/rules`, `.codex/hooks.json`, or `.claude/commands` already exist:

- do not overwrite;
- report current presence;
- recommend review/merge;
- future install plan must produce patch/diff, not blind replace.

### Dirty repo

If target repo is dirty:

- still allow read-only scan;
- flag dirty state;
- do not recommend applying changes until clean or isolated worktree exists.

### Conflicting rules

If multiple agent rule files conflict:

- flag as `conflicting_agent_contracts`;
- recommend source-of-truth consolidation;
- do not pick winner automatically.

### Public/private ambiguity

If public remote exists but private inventory is missing:

- severity P0;
- recommend dual-remote/publication pack;
- block auto-apply in future install plan.

### Monorepo

If multiple projects are detected:

- report per-package signals;
- avoid one global rule unless root conventions are clear;
- recommend scoped adapters.

## Internal Architecture

Suggested module layout:

```text
scripts/reefiki_agent_readiness/
  __init__.py
  inventory.py
  git_signals.py
  repo_classifier.py
  agent_surfaces.py
  risk_rules.py
  skill_catalog.py
  recommenders/
    skills.py
    rules.py
    adapters.py
    hooks.py
  report_markdown.py
  report_json.py
  schemas.py
```

`scripts/reefiki.py` should only wire CLI commands.

## Test Plan

Create synthetic fixture repos:

1. Empty git repo without `AGENTS.md`.
2. Dirty repo with unrelated untracked files.
3. Frontend repo with `package.json` and no browser smoke docs.
4. Repo with public remote and private folders.
5. Repo with auth/payment/security paths.
6. Repo with migrations.
7. Monorepo with multiple packages.
8. Repo with existing Codex/Claude/Cursor surfaces.
9. Repo with conflicting rule files.
10. Non-git folder.

Assertions:

- signals detected correctly;
- risks have expected severity/confidence;
- recommendations map to correct blocks;
- JSON schema stable;
- markdown report includes evidence;
- command does not mutate target repo.

## MVP Acceptance Criteria

MVP is ready when:

- `agent-readiness --repo <path>` works on git and non-git folders;
- JSON output is schema-versioned;
- markdown report is readable;
- at least 10 synthetic fixtures pass;
- no target repo files are modified;
- core recommendations cover base skills, rules, adapters and hooks;
- every recommendation has reason and evidence;
- low-confidence suggestions are marked as review-needed.

## Future Phases

### Phase 2: Draft generation

- write custom skill drafts only with `--write-draft`;
- write reports outside target repo by default;
- no auto-install.

### Phase 3: Install plan

- generate patch plan;
- show exact files to create/update;
- require explicit `--yes`;
- reject dirty target unless safe worktree exists.

### Phase 4: External catalog

- scan local/remote skill registries;
- external skills are reference-only until audited;
- no wholesale install.

### Phase 5: Paid/custom layer

- repo adaptation checklist;
- custom pack generation;
- team workflow setup.

Paid features remain secondary until the free core is stable.
