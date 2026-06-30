# REEFIKI project profiles

Languages: [Русский](#русский) · [English](#english) · [中文](#中文)

## Русский

Project profiles — это ручные onboarding labels, которые помогают человеку и агенту понять, какую память вести в новом REEFIKI-проекте. Это не обязательное поле схемы и не автоматический классификатор.

| Profile | Когда использовать | Примеры |
|---|---|---|
| `reefiki_core` | Правила REEFIKI, memory control plane, governance, publish/worktree/process gates. | `reefiki` |
| `agent_surface` | Agent/IDE/runtime проект: правила, skills, adapters, diagnostics, provider routing, recovery runbooks, eval evidence. | Codex, Claude Code, Gemini, Mimo, Hermes |
| `product` | Пользовательский продукт или приложение: delivery decisions, specs, release evidence, UX/product knowledge. | Metrica |
| `knowledge_domain` | Предметная область без основного runtime/control-plane слоя. | Suno, Instagram, Security Guidance |

### Как сказать агенту

```text
Создай проект codex как agent/runtime surface.
Подключи H:\Projects\CODEX к REEFIKI как agent surface.
Создай проект metrica как product/app knowledge base.
```

### Правила для агентов

- Сначала читай `AGENTS.md` и project-level `projects/<name>/AGENTS.md`; vendor-specific stubs только указывают на этот контракт.
- Для `agent_surface` сохраняй переносимые процедуры и проверенные runbooks, но не копируй skills между проектами автоматически.
- Не объединяй wikis разных проектов: Codex, Claude, Gemini, Mimo и Hermes могут быть похожими surfaces, но durable knowledge остается в своих project boundaries.
- Не добавляй `project_kind` в schema/index/validators до отдельного решения. Триггер: минимум 3 реальных manual transfer decisions, где profile помог принять решение.

## English

Project profiles are manual onboarding labels that help a person and an agent decide what kind of memory a REEFIKI project should keep. They are not a required schema field and not an automatic classifier.

| Profile | Use when | Examples |
|---|---|---|
| `reefiki_core` | REEFIKI rules, memory control plane, governance, publish/worktree/process gates. | `reefiki` |
| `agent_surface` | Agent/IDE/runtime project: rules, skills, adapters, diagnostics, provider routing, recovery runbooks, eval evidence. | Codex, Claude Code, Gemini, Mimo, Hermes |
| `product` | User-facing product or app: delivery decisions, specs, release evidence, UX/product knowledge. | Metrica |
| `knowledge_domain` | Topic/domain knowledge without a primary runtime/control-plane layer. | Suno, Instagram, Security Guidance |

### What to tell the agent

```text
Create a codex project as an agent/runtime surface.
Connect H:\Projects\CODEX to REEFIKI as an agent surface.
Create a metrica project as a product/app knowledge base.
```

### Agent rules

- Read `AGENTS.md` and the project-level `projects/<name>/AGENTS.md` first; vendor-specific stubs only point to that contract.
- For `agent_surface`, preserve portable procedures and verified runbooks, but do not copy skills between projects automatically.
- Do not merge project wikis: Codex, Claude, Gemini, Mimo, and Hermes may be similar surfaces, but durable knowledge stays inside project boundaries.
- Do not add `project_kind` to schema/index/validators until a separate decision. Trigger: at least 3 real manual transfer decisions where the profile helped make the call.

## 中文

Project profiles 是手动的 onboarding labels，用来帮助用户和代理判断一个 REEFIKI 项目应该保存哪类记忆。它不是必填 schema 字段，也不是自动分类器。

| Profile | 何时使用 | 示例 |
|---|---|---|
| `reefiki_core` | REEFIKI 规则、memory control plane、governance、publish/worktree/process gates。 | `reefiki` |
| `agent_surface` | Agent/IDE/runtime 项目：规则、skills、adapters、diagnostics、provider routing、recovery runbooks、eval evidence。 | Codex, Claude Code, Gemini, Mimo, Hermes |
| `product` | 面向用户的产品或应用：delivery decisions、specs、release evidence、UX/product knowledge。 | Metrica |
| `knowledge_domain` | 没有主要 runtime/control-plane 层的领域知识。 | Suno, Instagram, Security Guidance |

### 可以这样告诉代理

```text
把 codex 创建为 agent/runtime surface 项目。
把 H:\Projects\CODEX 作为 agent surface 接入 REEFIKI。
把 metrica 创建为 product/app knowledge base。
```

### 代理规则

- 先读取 `AGENTS.md` 和项目级 `projects/<name>/AGENTS.md`；vendor-specific stubs 只指向这个统一契约。
- 对 `agent_surface`，保存可迁移流程和已验证 runbooks，但不要自动在项目之间复制 skills。
- 不要合并不同项目的 wikis：Codex、Claude、Gemini、Mimo、Hermes 可以是相似 surfaces，但 durable knowledge 仍保持项目边界。
- 不要把 `project_kind` 加入 schema/index/validators，除非有单独决策。触发条件：至少 3 次真实的 manual transfer decisions，并且 profile 确实帮助了判断。
