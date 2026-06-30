import json
from pathlib import Path

from scripts.reefiki_core.link_confidence import (
    link_confidence_payload,
    print_link_confidence,
    write_link_confidence_report,
)


def write_page(project: Path, relative_path: str, page_id: str, body: str) -> None:
    path = project / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""---
id: {page_id}
type: concept
title: "{page_id}"
tags: [links]
useful_when:
  - "testing link confidence"
sources: [current-test]
date_added: 2026-06-14
use_count: 0
last_used: null
---
{body}
""",
        encoding="utf-8",
    )


def write_fixture_project(root: Path) -> Path:
    project = root / "projects" / "reefiki"
    write_page(
        project,
        "wiki/concepts/extracted-a.md",
        "extracted-a",
        """## Related

[[extracted-b]] - explicit reciprocal relation.
""",
    )
    write_page(
        project,
        "wiki/concepts/extracted-b.md",
        "extracted-b",
        """## Related

[[extracted-a]] - explicit reciprocal relation.
""",
    )
    write_page(
        project,
        "wiki/concepts/inferred-a.md",
        "inferred-a",
        """The prose mentions [[inferred-b]] without a Related edge.
""",
    )
    write_page(
        project,
        "wiki/concepts/inferred-b.md",
        "inferred-b",
        """The prose mentions [[inferred-a]] without a Related edge.
""",
    )
    write_page(
        project,
        "wiki/concepts/ambiguous-broken.md",
        "ambiguous-broken",
        """This page points at [[missing-target]].
""",
    )
    write_page(
        project,
        "wiki/concepts/ambiguous-source.md",
        "ambiguous-source",
        """## Related

[[ambiguous-target]] - one-way relation without target backlink.
""",
    )
    write_page(
        project,
        "wiki/concepts/ambiguous-target.md",
        "ambiguous-target",
        """Target page with no backlink.
""",
    )
    return project


def test_link_confidence_payload_classifies_wikilinks_and_recommendation(tmp_path: Path) -> None:
    project = write_fixture_project(tmp_path)

    payload = link_confidence_payload(project, stale_days=999, limit=5, ambiguity_threshold=2)

    assert payload["read_only"] is True
    assert payload["totals"]["wikilinks"] == 6
    assert payload["class_counts"]["extracted-looking"] == 2
    assert payload["class_counts"]["inferred-looking"] == 2
    assert payload["class_counts"]["ambiguous-looking"] == 2
    assert payload["review_queue_counts"]["placeholder_link"] == 1
    assert payload["review_queue_counts"]["missing_backlink"] >= 1
    assert payload["confidence_tagging"]["needed"] is True
    assert "smallest_next_slice" in payload["confidence_tagging"]
    assert payload["classes"]["ambiguous-looking"][0]["reason"] in {
        "broken_target",
        "missing_backlink",
    }


def test_link_confidence_payload_respects_related_confidence_markers(tmp_path: Path) -> None:
    project = tmp_path / "projects" / "reefiki"
    write_page(
        project,
        "wiki/concepts/marked-source.md",
        "marked-source",
        """## Related

[[marked-extracted]] [EXTRACTED] - source states this relation, backlink is optional.
[[marked-inferred]] [INFERRED] - useful agent inference without source wording.
[[marked-ambiguous]] [AMBIGUOUS] - relation needs human review.
[[missing-marker-target]] [EXTRACTED] - marker must not hide a broken target.

## Notes

[[non-related-target]] [AMBIGUOUS] should stay heuristic-only outside Related.
""",
    )
    for page_id in [
        "marked-extracted",
        "marked-inferred",
        "marked-ambiguous",
        "non-related-target",
    ]:
        write_page(
            project,
            f"wiki/concepts/{page_id}.md",
            page_id,
            f"{page_id} target page with no reciprocal backlink.\n",
        )

    payload = link_confidence_payload(project, stale_days=999, limit=10, ambiguity_threshold=1)

    assert payload["explicit_marker_counts"] == {
        "EXTRACTED": 2,
        "INFERRED": 1,
        "AMBIGUOUS": 1,
    }
    assert payload["class_counts"]["extracted-looking"] == 1
    assert payload["class_counts"]["inferred-looking"] == 1
    assert payload["class_counts"]["ambiguous-looking"] == 3

    extracted = payload["classes"]["extracted-looking"][0]
    assert extracted["target_id"] == "marked-extracted"
    assert extracted["confidence_marker"] == "EXTRACTED"
    assert extracted["reason"] == "explicit_marker_extracted"

    inferred = payload["classes"]["inferred-looking"][0]
    assert inferred["target_id"] == "marked-inferred"
    assert inferred["confidence_marker"] == "INFERRED"

    ambiguous_reasons = {
        item["target_id"]: item["reason"] for item in payload["classes"]["ambiguous-looking"]
    }
    assert ambiguous_reasons["marked-ambiguous"] == "explicit_marker_ambiguous"
    assert ambiguous_reasons["missing-marker-target"] == "broken_target"
    assert ambiguous_reasons["non-related-target"] == "missing_backlink"

    report_text = write_link_confidence_report(tmp_path, payload).read_text(encoding="utf-8")
    assert "`marked-source` -> `marked-extracted` [EXTRACTED]" in report_text
    assert "- EXTRACTED: 2" in report_text


def test_print_link_confidence_json_and_write_report(capsys, tmp_path: Path) -> None:
    write_fixture_project(tmp_path)

    assert print_link_confidence(tmp_path, "reefiki", 999, 5, 2, "json", write_report=False) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["project"] == "reefiki"
    assert payload["confidence_tagging"]["needed"] is True

    path = write_link_confidence_report(tmp_path, payload)
    text = path.read_text(encoding="utf-8")
    assert path.as_posix().endswith(
        f"docs/link-confidence/link-confidence-reefiki-{payload['generated_on']}.md"
    )
    assert "# Link Confidence Report" in text
    assert "Confidence tagging needed: yes" in text
