# REEFIKI

![REEFIKI：Rifiki 把 AI 会话噪声变成可复用记忆](assets/reefiki-hero-mascot.png)

<p align="center">
  <a href="QUICKSTART.md#中文"><img alt="快速开始" src="https://img.shields.io/badge/快速开始-0B7FCC?style=for-the-badge"></a>
  <a href="LICENSE"><img alt="许可证：Apache 2.0" src="https://img.shields.io/badge/许可证-Apache_2.0-2E7D32?style=for-the-badge"></a>
  <a href="#安全边界"><img alt="本地优先" src="https://img.shields.io/badge/本地优先-默认-3E6B5A?style=for-the-badge"></a>
  <a href="#面向代理"><img alt="面向代理" src="https://img.shields.io/badge/面向代理-Codex_|_Claude_|_Gemini_|_Mimo-6A4BBC?style=for-the-badge"></a>
  <a href="docs/PUBLIC_DEMO.md#中文"><img alt="公开演示" src="https://img.shields.io/badge/公开演示-docs-E07A2F?style=for-the-badge"></a>
  <a href="COMMANDS.md#中文"><img alt="命令" src="https://img.shields.io/badge/命令-参考-455A64?style=for-the-badge"></a>
</p>

AI 代理很快，但不擅长记住项目上下文：决策留在聊天里，有用的方法丢失，下一个代理又从零开始。

**REEFIKI** 把这个问题拆成一个本地的 AI 代理 wiki 记忆层：它不保存全部噪声，只保存以后真的可能再用到的知识。

[Русский](README.md) · [English](README.en.md) · [快速开始](QUICKSTART.md#中文) · [命令](COMMANDS.md#中文)

---

## 问题

AI 代理工作流经常不是因为代码失败，而是因为记忆失败。

几个线程之后，常见问题会重复出现：

- 重要决策留在聊天记录里，之后找不到；
- 新代理不知道项目为什么这样设计；
- 有用方法只被发现一次，没有变成可复用技能；
- 链接、笔记和结论与草稿、噪声混在一起；
- 代理记忆要么太短，要么太脏。

普通笔记系统也不能完全解决这个问题：保存一切很容易，但很难把可复用知识和偶然上下文分开。

## REEFIKI 是什么

REEFIKI 是一个本地 multi-project distillation wiki，面向 AI 代理。

更直接地说：

- 每个项目都有自己的 wiki；
- 代理把决策、技能、结论和来源保存进去；
- 薄弱或临时材料会被延后处理，而不是污染知识库；
- 所有内容都保存在 markdown 文件和 git 历史中；
- 工作规则写在 `AGENTS.md` 中，不同代理都可以遵守。

REEFIKI 不是另一个聊天机器人、云记忆服务，也不是所有消息的仓库。它是一个过滤器，把工作混乱变成简短、可验证、可迁移的项目记忆。

## Project Profiles

并不是所有 REEFIKI 项目都一样。创建或连接项目时，可以告诉代理它属于哪种 profile：

| Profile | 用途 | 示例 |
|---|---|---|
| `agent_surface` | agent/IDE/runtime 环境的规则、skills、adapters、diagnostics 和 recovery | Codex, Claude Code, Gemini, Mimo, Hermes |
| `product` | 产品决策、delivery evidence、UX 和 release knowledge | Metrica |
| `knowledge_domain` | 没有主要 runtime 层的领域知识 | Suno, Instagram, Security Guidance |
| `reefiki_core` | REEFIKI 自身规则和 governance | reefiki |

这是手动 onboarding label，不是必填 schema 字段。详情：[docs/PROJECT_PROFILES.md](docs/PROJECT_PROFILES.md#中文)。

## 为什么需要它

如果你经常和 AI 代理一起工作，并希望代理能够做到这些，REEFIKI 就有用：

- 基于过去的决策继续工作；
- 不重复已经解决过的错误；
- 快速恢复项目上下文；
- 把流程保存成可复用技能；
- 区分 private 记忆和公开材料；
- 在 Codex、Claude Code、Cursor、Windsurf 和其他代理之间交接工作。

核心思想：**代理不应该只是完成任务，还应该留下可复用的痕迹**。

## 工作方式

![REEFIKI 如何把噪声变成记忆](assets/reefiki-architecture.zh-CN.svg)

REEFIKI 使用一个简单循环：

1. **收集**：链接、文件、决策或结论进入项目收件箱。
2. **过滤**：代理检查它以后是否还能再次使用。
3. **保存**：有用内容变成 wiki 页面、技能、决策或 synthesis。
4. **连接**：页面获得链接、索引记录和日志记录。
5. **以后调用**：下一个代理从已有 wiki 回答，而不是靠猜测。

REEFIKI 使用几类 durable memory：

| 类型 | 保存什么 |
|---|---|
| `sources` | 想法或材料来自哪里 |
| `concepts` | 可复用理解 |
| `decisions` | 决策和原因 |
| `skills` | 可复现流程 |
| `synthesis` | 会话或阶段结论 |

## Rifiki

![Rifiki，REEFIKI 的吉祥物](assets/reefiki-mascot.png)

Rifiki 是一只小小的 reef crab archivist：它守护 reef wiki，不把所有沙子都拖进记忆，只挑出有用的贝壳。在 README 里，Rifiki 是一个隐喻：左边是会话噪声，中间是蒸馏，右边是干净的项目记忆。

## 快速开始

最短的安全首次运行路径是 CLI。`reefiki tour` 只显示当前步骤，不写文件；`reefiki onboarding` 会打开终端向导。确定性 demo 可以这样运行：

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

如果还没有全局安装 CLI，也可以从 checkout 运行同样流程：

```powershell
python scripts\reefiki.py tour
python scripts\reefiki.py onboarding
python scripts\reefiki.py onboarding --fixture-root C:\Temp\reefiki-demo
python scripts\reefiki.py --project C:\Temp\reefiki-demo\projects\reefiki-onboarding-demo status
python scripts\reefiki.py ops-dashboard demo --fixture-root C:\Temp\reefiki-dashboard-demo
python scripts\reefiki.py ops-dashboard serve --workspace-root C:\Temp\reefiki-dashboard-demo --port 7310
```

如果你已经有一个代码项目，打开 REEFIKI，然后告诉代理：

```text
把 H:\Projects\MyApp 连接到 wiki
```

代理会创建独立的 wiki 项目，并在代码项目里添加 `_wiki/` 链接。

如果你想从零开始创建新 wiki：

```text
创建一个名为 metrica 的新项目，主题是产品分析
```

之后可以用自然语言工作：

| 你说 | 代理会做什么 |
|---|---|
| “把这个放进收件箱” | 保存材料，之后再处理 |
| “处理收件箱” | 把有用材料变成 wiki 页面 |
| “把这个记为决策” | 保存 durable decision |
| “保存成技能” | 记录可复用流程 |
| “我们对 sync 做过什么决定？” | 只从已有 wiki 回答 |
| “记录本次会话结论” | 保存 synthesis |

完整首次使用说明：[QUICKSTART.md](QUICKSTART.md#中文)。安装细节：[docs/INSTALL.md](docs/INSTALL.md#中文)。

## 现在能做什么

- 在 `projects/<name>/` 下维护独立 wiki 项目。
- 通过 `_wiki` 连接已有代码项目。
- 支持 capture -> process -> query -> harvest 工作流。
- 通过 `AGENTS.md` 提供 agent-agnostic 规则。
- 为 agent/runtime、product 和 knowledge-domain 项目提供手动 project profiles。
- 使用本地 markdown 文件，而不是封闭云存储。
- 维护 wiki 日志和索引。
- 提供 health/lint 检查，避免知识库变成垃圾堆。
- 为下一个代理生成 handoff context。
- 明确区分本地/private 记忆和可以公开分享的材料。

完整能力地图：[COMMANDS.md](COMMANDS.md#中文)。

## REEFIKI 不是什么

REEFIKI 有意不做这些事：

- 保存每条聊天消息；
- 替代 git、Obsidian 或 issue tracker；
- 作为自动云同步服务；
- “以防万一”的向量数据库；
- 没有项目边界就到处写文件的系统。

如果一份材料以后不能再次使用，它就不应该进入 durable wiki memory。

## 安全边界

REEFIKI 默认 local-first：

- 用户 wiki 项目保留在本地；
- `raw/` 被视为不可变 archive；
- secret、binary 和过大文件不会自动保存；
- 公开材料与本地 wiki 项目分离，并在发布前经过检查；
- 代理只修改项目中明确选定的文件。

简短地说：REEFIKI 让记忆有用，但不模糊项目边界。

## 面向代理

代理不需要记住内部命令。它们读取 `AGENTS.md` 并遵守项目契约：

- 在 REEFIKI 根目录，可以创建和连接项目；
- 在 `projects/<name>/` 内，可以保存和处理知识；
- 旧的 `wiki/log.md` 记录不能重写；
- `raw/` 不能编辑；
- 所有 durable writes 都必须可解释、可复现。

这让 REEFIKI 可以在 Codex、Claude Code、Cursor、Windsurf/Cascade、Cline 和其他 LLM 代理之间迁移。

如果项目是 Codex、Claude Code、Gemini、Mimo、Hermes 这类 agent/IDE/runtime 环境，把它作为 `agent_surface` 处理：保存可迁移流程、adapters、diagnostics 和 recovery notes，但不要合并 wikis，也不要自动复制 skills。

## Token 消耗优化

![REEFIKI 如何丢弃噪声并保留有用 token](assets/reefiki-token-economy.png)

REEFIKI 降低 token 浪费，不是靠神奇压缩一切，而是让代理少读垃圾上下文。

- 代理读取简短的 `decisions`、`skills`、`concepts` 和 `synthesis` 页面，而不是整段聊天。
- 项目彼此隔离，无关上下文不会进入当前任务。
- `wiki/index.md` 和日志帮助定位相关页面，不需要重读整个知识库。
- Handoff pack 为下一个代理生成有边界的上下文包。
- 薄弱材料留在收件箱或拒绝路径中，不进入长期记忆。

粗略参考，不是保证：一页简短的 `decision` 或 `skill` 通常约 500-2,000 token，经常可以替代 5,000-30,000 token 的旧聊天上下文。实用的 handoff pack 通常应控制在 2,000-8,000 token 左右，而不是传递数万 token 的历史。

在重复任务中，这通常意味着读取上下文的 token 大约减少 50-90%；回到单个决策或技能时，减少幅度可能达到 70-95%。

详细说明：[docs/TOKEN_ECONOMY.md#中文](docs/TOKEN_ECONOMY.md#中文)。

## 下一步

- [QUICKSTART.md](QUICKSTART.md#中文)：无需了解 CLI 的首次使用。
- [COMMANDS.md](COMMANDS.md#中文)：所有 REEFIKI 操作。
- [docs/TOKEN_ECONOMY.md](docs/TOKEN_ECONOMY.md#中文)：REEFIKI 如何节省 token。
- [docs/INSTALL.md](docs/INSTALL.md#中文)：CLI 安装和 smoke test。
- [docs/obsidian-setup.md](docs/obsidian-setup.md#中文)：安全的 Obsidian 设置。
- [docs/PUBLIC_DEMO.md](docs/PUBLIC_DEMO.md#中文)：公开演示和边界。
- [docs/RECOVERY.md](docs/RECOVERY.md#中文)：故障恢复。

公开 roadmap：[docs/PUBLIC_ROADMAP.md](docs/PUBLIC_ROADMAP.md#中文)。公开 backlog：[docs/PUBLIC_BACKLOG.md](docs/PUBLIC_BACKLOG.md#中文)。

## License

REEFIKI 代码使用 Apache License 2.0 发布。见 [LICENSE](LICENSE)。

Wiki 项目内容属于创建或添加它的用户。

## 致谢与设计来源

REEFIKI 是一个独立实现。下面列出的材料和工具没有作为 REEFIKI 的代码库被导入，也不是被复制的源代码。它们影响的是产品理念、术语、架构模式和操作边界。

- [Karpathy LLM Wiki gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)：紧凑、适合 agent 阅读的 wiki，而不是反复重放聊天记录；重点是 distillation，而不是原始归档。
- REEF protocol：`capture -> distillation -> telemetry` 循环；把低成本保存、认真处理和之后复用分成不同阶段。
- [Vannevar Bush 的 "As We May Think"](https://www.w3.org/History/1945/vbush/vbush.shtml)：Memex、关联路径、长期个人记忆和相互连接的知识，而不是孤立笔记。
- [Markdown wiki 与 Obsidian 风格工作流](https://obsidian.md/help/links)：本地 markdown 文件、wikilinks、graph/viewer 思维，以及不依赖云服务也可阅读的知识。REEFIKI 不是 Obsidian 克隆：source of truth 仍然在仓库和 agent-aware 规则中。
- [Git worktree workflow](https://git-scm.com/docs/git-worktree)：隔离任务、可 review 的变更，以及本地/private 内容与公开 snapshot 的清晰分离。
- [`memoir`](https://www.memoir-ai.dev/)：把短期工作记忆和 preferences 作为单独一层。在 REEFIKI 中它是可选的 short-memory provider；durable truth 仍然是 markdown wiki。
- [Graphify](https://graphify.net/) 与 graph-based retrieval：把代码、文件和文档结构做成图，用作导航和候选上下文选择。REEFIKI 不变成 graph database，而是借用 graph 思路来找关系和压缩上下文。
- [CodeGraph-style navigation](https://github.com/CodeGraphContext/CodeGraphContext)：一次性的 impact/callgraph/relationship 代码查询，用来辅助开发，不作为长期记忆层。
- Agent/IDE runtimes：Codex、Claude Code、Cursor、Windsurf/Cascade、Cline、Gemini、Mimo 和 Hermes 影响了 vendor-neutral `AGENTS.md`、project profiles、portable rules 和 reusable runbooks。
- Local-first security practice：明确的 project boundaries、公开材料检查、append-only logs、immutable `raw/`，以及避免把所有内容一股脑保存下来，构成 REEFIKI 自己的 safety layer。

REEFIKI 的实际目标：把 wiki、agent workflow、short memory、graph navigation 和 Git discipline 合在一个 local-first 流程里，让知识可以被验证、迁移，并且安全发布。
