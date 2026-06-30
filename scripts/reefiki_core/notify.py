from __future__ import annotations

import hashlib
import json

from .markdown import as_text


NOTIFY_EVENTS = ("review_ready", "blocked", "failed")


def _normalize_event(value: str) -> str:
    event = as_text(value).lower().replace("-", "_")
    if event not in NOTIFY_EVENTS:
        raise SystemExit(f"notify event must be one of: {', '.join(NOTIFY_EVENTS)}")
    return event


def _severity_for_event(event: str) -> str:
    return {
        "review_ready": "info",
        "blocked": "warning",
        "failed": "error",
    }[event]


def _required(value: str, field: str) -> str:
    text = as_text(value)
    if not text:
        raise SystemExit(f"notify requires --{field.replace('_', '-')}.")
    return text


def _fingerprint(parts: list[str]) -> str:
    material = "\n".join(parts).encode("utf-8")
    return hashlib.sha256(material).hexdigest()[:16]


def notify_payload(
    event: str,
    source_artifact: str,
    reason: str,
    next_action: str,
    evidence_pointer: str,
    task_id: str = "",
    previous_fingerprints: list[str] | None = None,
    adapter_config: str = "",
) -> dict[str, object]:
    normalized_event = _normalize_event(event)
    source = _required(source_artifact, "source_artifact")
    normalized_reason = _required(reason, "reason")
    normalized_next_action = _required(next_action, "next_action")
    evidence = _required(evidence_pointer, "evidence_pointer")
    normalized_task_id = as_text(task_id) or None
    normalized_adapter_config = as_text(adapter_config) or None

    fingerprint = _fingerprint(
        [
            normalized_event,
            normalized_task_id or "",
            source,
            normalized_reason,
            normalized_next_action,
            evidence,
        ]
    )
    previous = {as_text(item) for item in previous_fingerprints or [] if as_text(item)}
    already_reported = fingerprint in previous

    return {
        "schema_version": 1,
        "read_only": True,
        "status": "already_reported" if already_reported else "ready",
        "notification": {
            "event": normalized_event,
            "severity": _severity_for_event(normalized_event),
            "task_id": normalized_task_id,
            "source_artifact": source,
            "reason": normalized_reason,
            "next_action": normalized_next_action,
            "evidence_pointer": evidence,
            "fingerprint": fingerprint,
        },
        "dedupe": {
            "already_reported": already_reported,
            "fingerprint": fingerprint,
            "previous_count": len(previous),
        },
        "delivery": {
            "mode": "dry_run",
            "network": "disabled",
            "sent": False,
            "adapter_config": normalized_adapter_config,
            "limits": [
                "No network call is made by the core notify command.",
                "Adapters must be configured explicitly outside this dry-run contract.",
                "Repeated unchanged statuses should pass their previous fingerprint to mark already_reported.",
            ],
        },
        "actions": [],
    }


def _print_notify_text(payload: dict[str, object]) -> None:
    notification = payload["notification"]
    delivery = payload["delivery"]
    print(f"notify: {payload['status']}")
    print(f"- event: {notification['event']}")
    print(f"- severity: {notification['severity']}")
    if notification.get("task_id"):
        print(f"- task: {notification['task_id']}")
    print(f"- source: {notification['source_artifact']}")
    print(f"- reason: {notification['reason']}")
    print(f"- next_action: {notification['next_action']}")
    print(f"- evidence: {notification['evidence_pointer']}")
    print(f"- fingerprint: {notification['fingerprint']}")
    print(f"- delivery: {delivery['mode']} ({delivery['network']})")
    if payload["dedupe"]["already_reported"]:
        print("- already_reported: true")


def print_notify(
    event: str,
    source_artifact: str,
    reason: str,
    next_action: str,
    evidence_pointer: str,
    task_id: str,
    previous_fingerprints: list[str],
    adapter_config: str,
    fmt: str,
) -> int:
    payload = notify_payload(
        event=event,
        source_artifact=source_artifact,
        reason=reason,
        next_action=next_action,
        evidence_pointer=evidence_pointer,
        task_id=task_id,
        previous_fingerprints=previous_fingerprints,
        adapter_config=adapter_config,
    )
    if fmt == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        _print_notify_text(payload)
    return 0
