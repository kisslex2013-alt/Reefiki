"""Run bounded prompts through approved local/VPS agent adapters.

The script is intentionally conservative:
- Hermes is available only through the VPS SSH adapter.
- Odysseus is listed as a planned API adapter but cannot run yet.
- Read-only/plan mode is the default for CLIs that support it.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import json
import os
import shlex
import shutil
import subprocess
import time
from pathlib import Path
from typing import Sequence


DEFAULT_HERMES_KEY = ""
DEFAULT_HERMES_HOST = ""
DEFAULT_HERMES_USER = ""
DEFAULT_HERMES_REMOTE_CWD = "/srv/projects"
DEFAULT_HERMES_EXECUTABLE = "hermes"
IS_WINDOWS = os.name == "nt"


@dataclasses.dataclass(frozen=True)
class Adapter:
    name: str
    transport: str
    description: str
    enabled: bool = True


@dataclasses.dataclass(frozen=True)
class Invocation:
    agent: str
    command: tuple[str, ...]
    stdin: str | None = None
    cwd: Path | None = None
    env: dict[str, str] | None = None

    def redacted_command(self) -> list[str]:
        if self.agent == "mimo" and "run" in self.command:
            redacted = list(self.command)
            prompt_index = redacted.index("run") + 1
            if prompt_index < len(redacted):
                redacted[prompt_index] = "<redacted>"
            return redacted
        redacted: list[str] = []
        skip_next = False
        for item in self.command:
            if skip_next:
                redacted.append("<redacted>")
                skip_next = False
                continue
            redacted.append(item)
            if item in {"-p", "--prompt", "-q", "--query", "-i", "--identity-file"}:
                skip_next = True
        return redacted


ADAPTERS: dict[str, Adapter] = {
    "claude": Adapter(
        name="claude",
        transport="local-cli",
        description="Claude Code non-interactive print mode.",
    ),
    "mimo": Adapter(
        name="mimo",
        transport="local-cli",
        description="Mimo Code run mode with JSON event output.",
    ),
    "gemini": Adapter(
        name="gemini",
        transport="local-cli",
        description="Gemini CLI headless prompt mode.",
    ),
    "hermes-vps": Adapter(
        name="hermes-vps",
        transport="ssh",
        description="Hermes Agent on the VPS over SSH. Local Hermes is intentionally unsupported.",
    ),
    "odysseus-api": Adapter(
        name="odysseus-api",
        transport="http-api",
        description="Planned Odysseus web/API adapter; disabled until auth and endpoint flow are verified.",
        enabled=False,
    ),
}


def parse_agents(raw: str) -> list[str]:
    agents = [part.strip() for part in raw.split(",") if part.strip()]
    if not agents:
        raise SystemExit("No agents selected.")
    unknown = [agent for agent in agents if agent not in ADAPTERS]
    if unknown:
        raise SystemExit(f"Unknown adapter(s): {', '.join(unknown)}")
    disabled = [agent for agent in agents if not ADAPTERS[agent].enabled]
    if disabled:
        raise SystemExit(f"Disabled adapter(s): {', '.join(disabled)}")
    return agents


def _validate_remote_cwd(remote_cwd: str) -> str:
    if not remote_cwd.startswith("/"):
        raise SystemExit("Hermes remote cwd must be an absolute POSIX path.")
    if any(ch in remote_cwd for ch in "\r\n\0"):
        raise SystemExit("Hermes remote cwd contains unsupported control characters.")
    return remote_cwd


def _require_hermes_option(name: str, value: str) -> str:
    value = value.strip()
    if not value:
        raise SystemExit(
            f"Hermes VPS requires {name}; pass the CLI option or set the matching HERMES_VPS_* environment variable."
        )
    if any(ch in value for ch in "\r\n\0"):
        raise SystemExit(f"Hermes {name} contains unsupported control characters.")
    return value


def _validate_hermes_executable(value: str) -> str:
    value = value.strip()
    if not value:
        raise SystemExit("Hermes VPS requires a non-empty --hermes-executable.")
    if any(ch in value for ch in "\r\n\0"):
        raise SystemExit("Hermes executable contains unsupported control characters.")
    if "/" in value and not value.startswith("/"):
        raise SystemExit("Hermes executable path must be absolute POSIX path or a bare command name.")
    return value


def _resolve_local_command(name: str) -> tuple[str, ...]:
    if not IS_WINDOWS:
        return (shutil.which(name) or name,)

    root, suffix = os.path.splitext(name)
    candidates = [name] if suffix else [f"{name}.exe", f"{name}.cmd", f"{name}.bat", f"{name}.ps1", name]
    for candidate in candidates:
        resolved = shutil.which(candidate)
        if not resolved:
            continue
        if resolved.lower().endswith(".ps1"):
            return ("powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", resolved)
        return (resolved,)
    return (name,)


def build_invocation(
    agent: str,
    prompt: str,
    cwd: Path,
    *,
    title: str,
    hermes_key: str = DEFAULT_HERMES_KEY,
    hermes_host: str = DEFAULT_HERMES_HOST,
    hermes_user: str = DEFAULT_HERMES_USER,
    hermes_remote_cwd: str = DEFAULT_HERMES_REMOTE_CWD,
    hermes_executable: str = DEFAULT_HERMES_EXECUTABLE,
) -> Invocation:
    if agent not in ADAPTERS:
        raise SystemExit(f"Unknown adapter: {agent}")
    if not ADAPTERS[agent].enabled:
        raise SystemExit(f"Adapter is disabled: {agent}")

    if agent == "claude":
        return Invocation(
            agent=agent,
            command=(*_resolve_local_command("claude"), "-p", prompt, "--output-format", "json", "--permission-mode", "plan"),
            cwd=cwd,
        )
    if agent == "mimo":
        return Invocation(
            agent=agent,
            command=(*_resolve_local_command("mimo"), "run", prompt, "--pure", "--dir", str(cwd), "--format", "json", "--title", title),
            cwd=cwd,
        )
    if agent == "gemini":
        return Invocation(
            agent=agent,
            command=(*_resolve_local_command("gemini"), "-p", prompt, "--skip-trust", "--output-format", "json", "--approval-mode", "plan"),
            cwd=cwd,
            env={"GEMINI_CLI_TRUST_WORKSPACE": "true"},
        )
    if agent == "hermes-vps":
        hermes_key = _require_hermes_option("--hermes-key", hermes_key)
        hermes_host = _require_hermes_option("--hermes-host", hermes_host)
        hermes_user = _require_hermes_option("--hermes-user", hermes_user)
        remote_cwd = _validate_remote_cwd(hermes_remote_cwd)
        remote_executable = _validate_hermes_executable(hermes_executable)
        pycode = (
            "import subprocess, sys; "
            "prompt = sys.stdin.read(); "
            "raise SystemExit(subprocess.run("
            f"[{remote_executable!r}, 'chat', '-q', prompt, '-Q', '--source', 'tool']"
            ").returncode)"
        )
        remote_command = f"cd {shlex.quote(remote_cwd)} && python3 -c {shlex.quote(pycode)}"
        return Invocation(
            agent=agent,
            command=(
                "ssh",
                "-i",
                hermes_key,
                "-o",
                "IdentitiesOnly=yes",
                "-o",
                "BatchMode=yes",
                f"{hermes_user}@{hermes_host}",
                remote_command,
            ),
            stdin=prompt,
            cwd=cwd,
        )

    raise SystemExit(f"Adapter has no runnable implementation yet: {agent}")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def _status_path_from_porcelain(line: str) -> str:
    if len(line) <= 3:
        return ""
    path = line[3:]
    if " -> " in path:
        path = path.split(" -> ", 1)[1]
    return path.strip().strip('"').replace("\\", "/")


def _ignored_status_paths(cwd: Path, out_dir: Path) -> list[str]:
    try:
        relative = out_dir.resolve().relative_to(cwd.resolve())
    except ValueError:
        return []
    return [relative.as_posix().rstrip("/")]


def _filter_status_lines(lines: Sequence[str], ignored_paths: Sequence[str]) -> list[str]:
    if not ignored_paths:
        return list(lines)
    filtered: list[str] = []
    for line in lines:
        path = _status_path_from_porcelain(line)
        if any(path == ignored or path.startswith(f"{ignored}/") for ignored in ignored_paths):
            continue
        filtered.append(line)
    return filtered


def _git_status_lines(cwd: Path) -> tuple[list[str] | None, str | None]:
    env = {**os.environ, "GIT_OPTIONAL_LOCKS": "0"}
    completed = subprocess.run(
        ["git", "-C", str(cwd), "status", "--porcelain=v1", "--untracked-files=all"],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        env=env,
        check=False,
    )
    if completed.returncode != 0:
        message = (completed.stderr or completed.stdout or "").strip()
        return None, message or f"git status failed with code {completed.returncode}"
    return [line for line in completed.stdout.splitlines() if line.strip()], None


def _snapshot_mutation_state(cwd: Path, out_dir: Path) -> dict[str, object]:
    ignored_paths = _ignored_status_paths(cwd, out_dir)
    lines, error = _git_status_lines(cwd)
    if lines is None:
        return {
            "available": False,
            "strategy": "git-status",
            "status": "unavailable",
            "ignored_paths": ignored_paths,
            "error": error,
        }
    filtered = _filter_status_lines(lines, ignored_paths)
    return {
        "available": True,
        "strategy": "git-status",
        "status": "clean" if not filtered else "dirty",
        "ignored_paths": ignored_paths,
        "entries": filtered,
    }


def _mutation_result(
    *,
    agent: str,
    before: dict[str, object],
    after: dict[str, object],
) -> dict[str, object]:
    coverage = {
        "scope": "local_cwd",
        "remote_cwd": "not_applicable",
    }
    if ADAPTERS.get(agent, Adapter(agent, "unknown", "")).transport == "ssh":
        coverage["remote_cwd"] = "not_checked"
        coverage["note"] = "Hermes VPS remote cwd mutation is outside this local git-status detector."

    if not before.get("available") or not after.get("available"):
        return {
            "status": "needs_review",
            "coverage": coverage,
            "reason": "mutation_detector_unavailable",
            "before": before,
            "after": after,
        }

    before_entries = [str(item) for item in before.get("entries", [])]
    after_entries = [str(item) for item in after.get("entries", [])]
    if before_entries:
        return {
            "status": "needs_review",
            "coverage": coverage,
            "reason": "baseline_dirty",
            "before_entries": before_entries,
            "after_entries": after_entries,
            "changed_entries": sorted(set(after_entries) - set(before_entries)),
            "ignored_paths": after.get("ignored_paths", []),
        }

    changed_entries = after_entries
    if changed_entries:
        return {
            "status": "mutated",
            "coverage": coverage,
            "reason": "post_run_git_status_dirty",
            "before_entries": before_entries,
            "after_entries": after_entries,
            "changed_entries": changed_entries,
            "ignored_paths": after.get("ignored_paths", []),
        }

    return {
        "status": "clean",
        "coverage": coverage,
        "reason": None,
        "before_entries": [],
        "after_entries": [],
        "changed_entries": [],
        "ignored_paths": after.get("ignored_paths", []),
    }


def _run_invocation(invocation: Invocation, out_dir: Path, timeout: int) -> dict[str, object]:
    agent_dir = out_dir / invocation.agent
    agent_dir.mkdir(parents=True, exist_ok=True)
    started = _now_iso()
    t0 = time.monotonic()
    stdout_path = agent_dir / "stdout.txt"
    stderr_path = agent_dir / "stderr.txt"
    result_path = agent_dir / "result.json"
    mutation_before = _snapshot_mutation_state(invocation.cwd or Path.cwd(), out_dir)

    try:
        completed = subprocess.run(
            invocation.command,
            input=invocation.stdin,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            cwd=invocation.cwd,
            env={**os.environ, **invocation.env} if invocation.env else None,
            timeout=timeout,
            check=False,
        )
        status = "pass" if completed.returncode == 0 else "fail"
        stdout = completed.stdout
        stderr = completed.stderr
        returncode: int | None = completed.returncode
        error = None
    except subprocess.TimeoutExpired as exc:
        status = "timeout"
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        returncode = None
        error = f"timeout after {timeout}s"
    except FileNotFoundError as exc:
        status = "missing"
        stdout = ""
        stderr = str(exc)
        returncode = None
        error = str(exc)

    duration = round(time.monotonic() - t0, 3)
    _write_text(stdout_path, stdout or "")
    _write_text(stderr_path, stderr or "")
    mutation_after = _snapshot_mutation_state(invocation.cwd or Path.cwd(), out_dir)
    mutation = _mutation_result(agent=invocation.agent, before=mutation_before, after=mutation_after)
    adapter_status = status
    if mutation["status"] in {"mutated", "needs_review"}:
        status = str(mutation["status"])
    payload: dict[str, object] = {
        "agent": invocation.agent,
        "status": status,
        "adapter_status": adapter_status,
        "returncode": returncode,
        "started_at": started,
        "duration_seconds": duration,
        "command": invocation.redacted_command(),
        "stdout": str(stdout_path),
        "stderr": str(stderr_path),
        "mutation": mutation,
    }
    if error:
        payload["error"] = error
    _write_json(result_path, payload)
    payload["result"] = str(result_path)
    return payload


def list_adapters(*, json_output: bool) -> int:
    payload = {
        "adapters": {
            name: {
                "transport": adapter.transport,
                "description": adapter.description,
                "enabled": adapter.enabled,
            }
            for name, adapter in ADAPTERS.items()
        }
    }
    if json_output:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        for name, adapter in ADAPTERS.items():
            state = "enabled" if adapter.enabled else "disabled"
            print(f"{name}\t{state}\t{adapter.transport}\t{adapter.description}")
    return 0


def build_plan(args: argparse.Namespace) -> dict[str, object]:
    prompt_file = Path(args.prompt_file)
    prompt = prompt_file.read_text(encoding="utf-8")
    cwd = Path(args.cwd).resolve()
    agents = parse_agents(args.agents)
    invocations = [
        build_invocation(
            agent,
            prompt,
            cwd,
            title=args.title,
            hermes_key=args.hermes_key,
            hermes_host=args.hermes_host,
            hermes_user=args.hermes_user,
            hermes_remote_cwd=args.hermes_remote_cwd,
            hermes_executable=args.hermes_executable,
        )
        for agent in agents
    ]
    return {
        "mode": args.mode,
        "cwd": str(cwd),
        "prompt_file": str(prompt_file),
        "output_dir": str(Path(args.output_dir)),
        "agents": [
            {
                "agent": invocation.agent,
                "transport": ADAPTERS[invocation.agent].transport,
                "command": invocation.redacted_command(),
                "stdin": bool(invocation.stdin),
                "env": sorted((invocation.env or {}).keys()),
            }
            for invocation in invocations
        ],
    }


def run(args: argparse.Namespace) -> int:
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    plan = build_plan(args)
    _write_json(out_dir / "manifest.json", {**plan, "started_at": _now_iso()})

    prompt = Path(args.prompt_file).read_text(encoding="utf-8")
    cwd = Path(args.cwd).resolve()
    results = []
    for agent in parse_agents(args.agents):
        invocation = build_invocation(
            agent,
            prompt,
            cwd,
            title=args.title,
            hermes_key=args.hermes_key,
            hermes_host=args.hermes_host,
            hermes_user=args.hermes_user,
            hermes_remote_cwd=args.hermes_remote_cwd,
            hermes_executable=args.hermes_executable,
        )
        results.append(_run_invocation(invocation, out_dir, args.timeout))

    summary = {"finished_at": _now_iso(), "results": results}
    _write_json(out_dir / "summary.json", summary)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if all(item["status"] == "pass" for item in results) else 1


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--agents", required=True, help="Comma-separated adapters, e.g. claude,mimo,gemini,hermes-vps")
    parser.add_argument("--prompt-file", required=True)
    parser.add_argument("--cwd", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--title", default="local-agent-delegation")
    parser.add_argument("--mode", choices=["read-only"], default="read-only")
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--hermes-key", default=os.environ.get("HERMES_VPS_KEY", ""))
    parser.add_argument("--hermes-host", default=os.environ.get("HERMES_VPS_HOST", ""))
    parser.add_argument("--hermes-user", default=os.environ.get("HERMES_VPS_USER", ""))
    parser.add_argument("--hermes-remote-cwd", default=os.environ.get("HERMES_VPS_CWD", DEFAULT_HERMES_REMOTE_CWD))
    parser.add_argument("--hermes-executable", default=os.environ.get("HERMES_VPS_EXECUTABLE", DEFAULT_HERMES_EXECUTABLE))


def main(argv: Sequence[str] | None = None) -> int:
    root = argparse.ArgumentParser(description=__doc__)
    sub = root.add_subparsers(dest="command", required=True)

    list_parser = sub.add_parser("list-adapters")
    list_parser.add_argument("--format", choices=["text", "json"], default="text")

    plan_parser = sub.add_parser("plan")
    add_common_args(plan_parser)

    run_parser = sub.add_parser("run")
    add_common_args(run_parser)

    args = root.parse_args(argv)
    if args.command == "list-adapters":
        return list_adapters(json_output=args.format == "json")
    if args.command == "plan":
        print(json.dumps(build_plan(args), indent=2, ensure_ascii=False))
        return 0
    if args.command == "run":
        return run(args)
    raise SystemExit(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
