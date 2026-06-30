# REEFIKI Token Economy

Languages: [Русский](#русский) · [English](#english) · [中文](#中文)

## Русский

REEFIKI экономит токены не тем, что сжимает всё подряд. Он уменьшает объём контекста, который агенту приходится читать повторно.

Обычный AI-workflow часто тратит токены на одно и то же:

- перечитывание длинных чатов;
- повторное объяснение уже принятых решений;
- поиск нужного вывода среди черновиков;
- загрузку нерелевантных файлов и соседних проектов;
- передачу следующему агенту слишком большого handoff-контекста.

REEFIKI меняет это на distillation workflow:

| Механизм | Как экономит токены |
|---|---|
| Project isolation | агент читает память текущего проекта, а не весь workspace |
| Typed pages | короткие `decisions`, `skills`, `concepts`, `synthesis` заменяют длинную переписку |
| `useful_when` | слабые заметки не попадают в durable memory |
| `wiki/index.md` | агент сначала смотрит карту страниц, а не весь vault |
| `harvest` | итог сессии сохраняется как короткий reusable artifact |
| `memory pack` | следующий агент получает bounded context bundle |
| `seen/` quarantine | отказанные или повторные материалы не возвращаются в prompt снова и снова |

Ориентировочные числа:

| Сценарий | Без REEFIKI | С REEFIKI |
|---|---:|---:|
| Вернуться к одному решению | 5 000-30 000 токенов старого чата | 500-1 500 токенов `decision`-страницы |
| Повторить найденную процедуру | 10 000+ токенов старой отладки | 800-2 000 токенов `skill`-страницы |
| Передать задачу следующему агенту | 20 000-80 000 токенов истории или summary | 2 000-8 000 токенов `memory pack` |
| Найти нужный проектный контекст | десятки страниц подряд | 1 000-3 000 токенов index/log + выбранные страницы |

Примерная экономия в процентах:

| Где появляется экономия | Типичный диапазон |
|---|---:|
| Повторное чтение старого контекста | 50-90% меньше токенов |
| Возврат к одному решению или навыку | 70-95% меньше токенов |
| Handoff следующему агенту | 60-90% меньше токенов |
| Первый разбор новой темы | 0-20% меньше токенов |

Это не benchmark и не обещание процента экономии. Это порядок величин для планирования: точные числа зависят от tokenizer, модели, агента, длины старых тредов и качества wiki-страниц. На первом проходе REEFIKI может даже стоить немного дороже, потому что агент тратит токены на distillation; выигрыш появляется на повторных запросах, handoff и возвращении к решениям.

Практический результат: меньше повторного чтения, меньше мусорного контекста, меньше “начинаем с нуля”.

Честные ограничения:

- REEFIKI не гарантирует фиксированную экономию в процентах.
- Экономия зависит от модели, агента, размера проекта и дисциплины записи.
- Цель не минимальный prompt любой ценой, а полезный контекст с меньшим шумом.
- Важные проверки, source-of-truth диагностика и safety gates всё равно требуют токенов.

Хороший критерий: если следующий агент может понять решение по одной короткой wiki-странице вместо чтения старого треда, REEFIKI сработал.

## English

REEFIKI saves tokens not by compressing everything blindly, but by reducing the amount of context an agent has to reread.

A typical AI workflow spends tokens on the same things repeatedly:

- rereading long chats;
- re-explaining decisions that were already made;
- searching for conclusions among drafts;
- loading irrelevant files and neighboring projects;
- handing off too much context to the next agent.

REEFIKI replaces that with a distillation workflow:

| Mechanism | How it saves tokens |
|---|---|
| Project isolation | the agent reads memory for the current project, not the whole workspace |
| Typed pages | short `decisions`, `skills`, `concepts`, and `synthesis` replace long chats |
| `useful_when` | weak notes do not enter durable memory |
| `wiki/index.md` | the agent starts from a page map, not the whole vault |
| `harvest` | session output becomes a short reusable artifact |
| `memory pack` | the next agent gets a bounded context bundle |
| `seen/` quarantine | rejected or duplicate material does not return to the prompt again and again |

Rough planning numbers:

| Scenario | Without REEFIKI | With REEFIKI |
|---|---:|---:|
| Returning to one decision | 5,000-30,000 tokens of old chat | 500-1,500 tokens of a `decision` page |
| Reusing a discovered procedure | 10,000+ tokens of old debugging context | 800-2,000 tokens of a `skill` page |
| Handing work to the next agent | 20,000-80,000 tokens of history or summary | 2,000-8,000 tokens of a `memory pack` |
| Finding relevant project context | dozens of pages read in sequence | 1,000-3,000 tokens for index/log plus selected pages |

Approximate percentage savings:

| Where savings appear | Typical range |
|---|---:|
| Rereading old context | 50-90% fewer tokens |
| Returning to one decision or skill | 70-95% fewer tokens |
| Handing off to the next agent | 60-90% fewer tokens |
| First pass over a new topic | 0-20% fewer tokens |

This is not a benchmark and not a savings promise. It is an order-of-magnitude planning guide: exact numbers depend on the tokenizer, model, agent, old thread length, and the quality of the wiki pages. On the first pass, REEFIKI can even cost a little more because the agent spends tokens on distillation; the savings show up on repeat queries, handoffs, and returning to past decisions.

Practical result: less rereading, less junk context, fewer restarts from zero.

Honest limits:

- REEFIKI does not promise a fixed percentage of token savings.
- Savings depend on the model, agent, project size, and writing discipline.
- The goal is not the smallest possible prompt at any cost, but useful context with less noise.
- Important verification, source-of-truth diagnostics, and safety gates still cost tokens.

A good test: if the next agent can understand a decision from one short wiki page instead of rereading an old thread, REEFIKI worked.

## 中文

REEFIKI 节省 token，不是盲目压缩一切，而是减少代理需要反复阅读的上下文。

典型 AI workflow 会反复把 token 花在这些地方：

- 重读很长的聊天；
- 重新解释已经做过的决策；
- 在草稿中寻找结论；
- 加载无关文件和相邻项目；
- 给下一个代理传递过大的 handoff 上下文。

REEFIKI 用 distillation workflow 替代这种方式：

| 机制 | 如何节省 token |
|---|---|
| Project isolation | 代理只读取当前项目记忆，而不是整个 workspace |
| Typed pages | 简短的 `decisions`、`skills`、`concepts`、`synthesis` 替代长聊天 |
| `useful_when` | 薄弱笔记不会进入 durable memory |
| `wiki/index.md` | 代理先看页面地图，而不是整个 vault |
| `harvest` | 会话输出变成简短的 reusable artifact |
| `memory pack` | 下一个代理获得有边界的 context bundle |
| `seen/` quarantine | 被拒绝或重复的材料不会一次次回到 prompt |

粗略参考数字：

| 场景 | 没有 REEFIKI | 使用 REEFIKI |
|---|---:|---:|
| 回到一个决策 | 5,000-30,000 token 的旧聊天 | 500-1,500 token 的 `decision` 页面 |
| 复用一个已发现流程 | 10,000+ token 的旧调试上下文 | 800-2,000 token 的 `skill` 页面 |
| 把任务交给下一个代理 | 20,000-80,000 token 的历史或 summary | 2,000-8,000 token 的 `memory pack` |
| 找到相关项目上下文 | 连续读取几十页 | 1,000-3,000 token 的 index/log 加选中页面 |

大致节省比例：

| 节省出现在哪里 | 常见范围 |
|---|---:|
| 重读旧上下文 | 减少 50-90% token |
| 回到一个决策或技能 | 减少 70-95% token |
| 交接给下一个代理 | 减少 60-90% token |
| 第一次处理新主题 | 减少 0-20% token |

这不是 benchmark，也不是节省比例承诺。它只是数量级参考：准确数字取决于 tokenizer、模型、代理、旧线程长度以及 wiki 页面的质量。第一次处理时，REEFIKI 甚至可能稍微更贵，因为代理要花 token 做 distillation；收益主要出现在重复查询、handoff 和回到过去决策时。

实际结果：少重读，少垃圾上下文，少从零开始。

真实限制：

- REEFIKI 不承诺固定百分比的 token 节省。
- 节省效果取决于模型、代理、项目规模和写入纪律。
- 目标不是不惜一切代价做最小 prompt，而是用更少噪声提供有用上下文。
- 重要验证、source-of-truth diagnostics 和 safety gates 仍然会消耗 token。

一个好的判断标准：如果下一个代理可以通过一页简短 wiki 理解决策，而不需要重读旧线程，REEFIKI 就发挥了作用。
