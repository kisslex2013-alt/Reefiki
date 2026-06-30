# AGENTS.md - Project: reefiki-demo

This project is the public-safe REEFIKI demo project. It exists so the public
repository can run wiki, memory, doctor, and review-queue checks without private
project data.

Rules:

- Keep every file public-safe.
- Do not add private user logs, raw customer data, secrets, credentials, or local machine paths.
- Keep `wiki/log.md` append-only.
- Keep `raw/` immutable after a source is captured.
- Prefer small pages that demonstrate one clear REEFIKI behavior.

Use this project for public CI, public snapshot smoke tests, and first-run
examples only.
