import pytest

from scripts.reefiki_core.memory_reflect import (
    print_memory_reflect_result,
    read_only_pack_quality,
    reflection_candidate_actions,
)


def test_reflection_candidate_actions_prefers_largest_review_queue() -> None:
    payload = {
        "project": "reefiki",
        "task": "memory reflection",
        "since": "HEAD",
        "included": {
            "health": {"outcome": "warn"},
            "review_queues": {
                "queues": [
                    {"queue_type": "orphan_review", "count": 2},
                    {"queue_type": "missing_backlink", "count": 76},
                ]
            },
            "promotion_inbox": {},
            "pack_quality": {"strict": {"outcome": "pass"}},
            "changed_paths": {"total": 0},
        },
    }

    actions = reflection_candidate_actions(payload, limit=5)

    assert actions[0] == {
        "action": "run review-queues --type missing_backlink --limit 5",
        "reason": "largest open review queue",
        "risk": "low",
    }


def test_reflection_candidate_actions_returns_noop_without_signals() -> None:
    assert reflection_candidate_actions({"included": {}}, limit=5) == [
        {"action": "no action", "reason": "no open reflection signals", "risk": "none"}
    ]


def test_print_memory_reflect_result_reports_text(capsys: pytest.CaptureFixture[str]) -> None:
    payload = {
        "project": "reefiki",
        "since": "HEAD",
        "outcome": "review",
        "candidate_actions": [
            {"action": "no action", "reason": "no open reflection signals", "risk": "none"}
        ],
        "blocked_actions": [
            {"action": "auto-apply wiki changes", "reason": "reflection is report-only"}
        ],
    }

    assert print_memory_reflect_result(payload, "text") == 0
    assert capsys.readouterr().out == (
        "# Memory Reflection: reefiki\n"
        "- since: HEAD\n"
        "- outcome: review\n"
        "\n"
        "## Candidate Actions\n"
        "- no action (no open reflection signals; risk: none)\n"
        "\n"
        "## Blocked Actions\n"
        "- auto-apply wiki changes - reflection is report-only\n"
    )


def test_read_only_pack_quality_reports_missing_index(tmp_path) -> None:
    project = tmp_path / "projects" / "reefiki"
    project.mkdir(parents=True)

    result = read_only_pack_quality(tmp_path, project, "memory reflection", 5, pack_fn=lambda *_args, **_kwargs: {})

    assert result == {
        "quality": None,
        "golden": None,
        "strict": {
            "outcome": "fail",
            "blocking_reasons": ["index:missing"],
        },
        "open_queues": [],
        "error": "search index missing; run project index before strict pack reflection",
    }


def test_read_only_pack_quality_summarizes_pack_with_minimum_limit(tmp_path) -> None:
    project = tmp_path / "projects" / "reefiki"
    (project / ".reefiki").mkdir(parents=True)
    (project / ".reefiki" / "index.sqlite").write_bytes(b"")
    calls = []

    def fake_pack(root, project_name, task, limit):
        calls.append((root, project_name, task, limit))
        return {
            "quality": {"outcome": "pass"},
            "golden": {"failed": 0},
            "open_queues": [{"queue_type": "missing_backlink", "count": 1}],
            "safety_outcome": "pass",
            "lookup_error": None,
            "diff": {},
        }

    result = read_only_pack_quality(tmp_path, project, "memory reflection", 2, pack_fn=fake_pack)

    assert calls == [(tmp_path, "reefiki", "memory reflection", 8)]
    assert result == {
        "quality": {"outcome": "pass"},
        "golden": {"failed": 0},
        "strict": {"outcome": "pass", "blocking_reasons": []},
        "open_queues": [{"queue_type": "missing_backlink", "count": 1}],
    }
