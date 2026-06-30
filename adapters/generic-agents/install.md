# Generic agents adapter

This adapter is a copy/paste contract for agents that read repository instructions but do not support native skills.

## Install

1. Keep `skills/base/*/SKILL.md` in the repository.
2. After explicit approval, add the contents of `AGENTS.md.fragment` to the project instruction file that the agent already reads.
3. Do not add hooks, daemon processes or global config as part of this adapter.

## Verification

- Ask the agent which base skill applies to a dirty checkout task.
- Ask the agent which base skill applies to a config/version question.
- Confirm it references `skills/base/*/SKILL.md` instead of inventing a new workflow.

## Uninstall

Remove the fragment from the project instruction file. The canonical skills can remain as documentation.
