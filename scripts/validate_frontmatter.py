#!/usr/bin/env python3
"""
REEFIKI frontmatter validator.
Runs as a pre-commit hook on wiki/**/*.md files.
Exit code 1 if any violations found.
"""
import sys
import re
import json
from pathlib import Path

REQUIRED_FIELDS = {
    "id",
    "type",
    "title",
    "tags",
    "useful_when",
    "date_added",
    "use_count",
    "last_used",
}
ALLOWED_TYPES = {"source", "entity", "concept", "synthesis", "decision", "skill"}
FORBIDDEN_FIELDS = {"importance"}
REQUIRED_BY_TYPE = {
    "source": {"sources"},
    "synthesis": {"sources"},
    "skill": {"verified"},
}
SKILL_ONLY_FIELDS = {"verified", "source_url", "license", "status", "scope", "validation", "risks"}
SKILL_STATUS_VALUES = {"candidate", "sandboxed", "accepted", "rejected", "deprecated"}
CURRENT_SCHEMA_VERSION = "1.0"

BODY_REQUIRED = {
    "skill": [r"^## .*(Шаги|Steps)"],
}

# Body checks that emit warnings (non-blocking) rather than errors.
# decision pages may use ADR format OR a list-of-decisions format.
BODY_WARN = {
    "decision": [r"^## .*(Контекст|Context|Решение|Decision|Варианты|Options)"],
}

SKIP_FILENAMES = {"_schema.md", "log.md", "_dashboard.md", "_domain.md", "_overview.md"}
SKIP_DIRNAMES = {"logs"}

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL | re.MULTILINE)
FIELD_RE       = re.compile(r"^([a-z_]+)\s*:", re.MULTILINE)


def error(
    path: Path,
    code: str,
    message: str,
    line: int | None = None,
    column: int | None = None,
    expected: object | None = None,
    actual: object | None = None,
) -> dict[str, object]:
    return {
        "path": str(path),
        "code": code,
        "message": message,
        "line": line,
        "column": column,
        "expected": expected,
        "actual": actual,
    }


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    fields, body, _locations = parse_frontmatter_with_locations(text)
    return fields, body


def parse_frontmatter_with_locations(text: str) -> tuple[dict[str, str], str, dict[str, dict[str, object]]]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}, text, {}
    raw = match.group(1)
    body = text[match.end():]
    fields: dict[str, str] = {}
    locations: dict[str, dict[str, object]] = {}
    for offset, line in enumerate(raw.splitlines(), 2):
        m = re.match(r"^([a-z_]+)\s*:", line)
        if m:
            field = m.group(1)
            fields[field] = line
            locations[field] = {
                "line": offset,
                "column": 1,
                "value": line.split(":", 1)[1].strip().strip('"\''),
            }
    return fields, body, locations


def validate_file(path: Path) -> list[str]:
    return [item["message"] for item in validate_file_report(path)]


def should_skip_wiki_file(path: Path) -> bool:
    return path.name in SKIP_FILENAMES or any(part in SKIP_DIRNAMES for part in path.parts)


def validate_file_report(path: Path) -> list[dict[str, str]]:
    if path.name == "index.md":
        return validate_index_report(path)
    if should_skip_wiki_file(path):
        return []
    errors: list[dict[str, str]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="utf-8", errors="replace")

    fields, body, locations = parse_frontmatter_with_locations(text)

    if not fields:
        first_line = text.splitlines()[0] if text.splitlines() else ""
        errors.append(
            error(
                path,
                "frontmatter.missing",
                f"{path}: no frontmatter found",
                line=1,
                column=1,
                expected="frontmatter block",
                actual=first_line,
            )
        )
        return errors

    if "id" in fields:
        page_id = str(locations.get("id", {}).get("value") or "").strip()
        expected_id = path.stem
        if page_id != expected_id:
            errors.append(
                error(
                    path,
                    "frontmatter.id_filename_mismatch",
                    f"{path}: id '{page_id}' must match filename '{expected_id}'",
                    line=locations.get("id", {}).get("line"),
                    column=locations.get("id", {}).get("column"),
                    expected=expected_id,
                    actual=page_id,
                )
            )

    missing = REQUIRED_FIELDS - set(fields.keys())
    if missing:
        errors.append(
            error(
                path,
                "frontmatter.required_fields",
                f"{path}: missing required fields: {sorted(missing)}",
                line=1,
                column=1,
                expected=sorted(missing),
                actual=sorted(fields.keys()),
            )
        )

    found_forbidden = FORBIDDEN_FIELDS & set(fields.keys())
    if found_forbidden:
        errors.append(
            error(
                path,
                "frontmatter.forbidden_fields",
                f"{path}: forbidden deprecated fields: {sorted(found_forbidden)}",
                line=locations.get(sorted(found_forbidden)[0], {}).get("line"),
                column=locations.get(sorted(found_forbidden)[0], {}).get("column"),
                expected="field absent",
                actual=sorted(found_forbidden),
            )
        )

    page_type = None
    for line in text.splitlines():
        m = re.match(r"^type\s*:\s*(.+)", line)
        if m:
            page_type = m.group(1).strip().strip('"\'')
            break

    if page_type and page_type not in ALLOWED_TYPES:
        errors.append(
            error(
                path,
                "frontmatter.unknown_type",
                f"{path}: unknown type '{page_type}', allowed: {sorted(ALLOWED_TYPES)}",
                line=locations.get("type", {}).get("line"),
                column=locations.get("type", {}).get("column"),
                expected=sorted(ALLOWED_TYPES),
                actual=page_type,
            )
        )

    if page_type in REQUIRED_BY_TYPE:
        missing_type_fields = REQUIRED_BY_TYPE[page_type] - set(fields.keys())
        if missing_type_fields:
            errors.append(
                error(
                    path,
                    "frontmatter.type_required_fields",
                    f"{path}: type '{page_type}' missing required fields: {sorted(missing_type_fields)}",
                    line=locations.get("type", {}).get("line"),
                    column=locations.get("type", {}).get("column"),
                    expected=sorted(missing_type_fields),
                    actual=sorted(fields.keys()),
                )
            )

    if page_type != "skill":
        skill_only_found = SKILL_ONLY_FIELDS & set(fields.keys())
        if skill_only_found:
            errors.append(
                error(
                    path,
                    "frontmatter.skill_only_fields",
                    f"{path}: fields {sorted(skill_only_found)} are only allowed for type 'skill'",
                    line=locations.get(sorted(skill_only_found)[0], {}).get("line"),
                    column=locations.get(sorted(skill_only_found)[0], {}).get("column"),
                    expected="type skill",
                    actual=page_type,
                )
            )

    if page_type == "skill" and "status" in fields:
        status_raw = fields["status"].split(":", 1)[1].strip().strip('"\'')
        if status_raw and status_raw not in SKILL_STATUS_VALUES:
            errors.append(
                error(
                    path,
                    "frontmatter.skill_status",
                    f"{path}: field 'status' must be one of {sorted(SKILL_STATUS_VALUES)}",
                    line=locations.get("status", {}).get("line"),
                    column=locations.get("status", {}).get("column"),
                    expected=sorted(SKILL_STATUS_VALUES),
                    actual=status_raw,
                )
            )

    if page_type == "skill" and "status" in fields:
        if fields["status"].split(":", 1)[1].strip().strip('"\'') == "accepted" and "validation" not in fields:
            errors.append(
                error(
                    path,
                    "frontmatter.skill_validation",
                    f"{path}: accepted skill must include 'validation'",
                    line=locations.get("status", {}).get("line"),
                    column=locations.get("status", {}).get("column"),
                    expected="validation field",
                    actual="missing",
                )
            )

    if page_type in BODY_REQUIRED:
        patterns = BODY_REQUIRED[page_type]
        for pattern in patterns:
            if not re.search(pattern, body, re.MULTILINE):
                errors.append(
                    error(
                        path,
                        "body.required_section",
                        f"{path}: type '{page_type}' requires section matching '{pattern}'",
                        expected=pattern,
                        actual="missing",
                    )
                )

    if page_type in BODY_WARN:
        patterns = BODY_WARN[page_type]
        # At least one of the patterns must match (OR logic)
        if not any(re.search(p, body, re.MULTILINE) for p in patterns):
            # Print warning but don't add to errors (non-blocking)
            print(f"  WARN {path}: type '{page_type}' has no ADR sections "
                  f"(## Контекст/Решение/Варианты) — consider migrating to ADR format")

    useful_when_raw = ""
    in_uw = False
    for line in text.splitlines():
        if re.match(r"^useful_when\s*:", line):
            in_uw = True
            useful_when_raw += line
            continue
        if in_uw:
            if line.startswith("  ") or line.startswith("\t") or line.strip().startswith("-"):
                useful_when_raw += line
            else:
                break
    if "useful_when" in fields and len(useful_when_raw.strip()) <= len("useful_when:"):
        errors.append(
            error(
                path,
                "frontmatter.useful_when_empty",
                f"{path}: 'useful_when' must contain at least one item",
                line=locations.get("useful_when", {}).get("line"),
                column=locations.get("useful_when", {}).get("column"),
                expected="non-empty item",
                actual="",
            )
        )

    return errors


def validate_index(path: Path) -> list[str]:
    return [item["message"] for item in validate_index_report(path)]


def validate_index_report(path: Path) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="utf-8", errors="replace")

    if re.search(r"^- importance\s*:", text, re.MULTILINE):
        errors.append(
            error(path, "index.forbidden_importance", f"{path}: index contains forbidden deprecated field 'importance'")
        )

    required_sections = [
        "## Sources",
        "## Entities",
        "## Concepts",
        "## Synthesis",
        "## Decisions",
        "## Skills",
    ]
    for section in required_sections:
        if section not in text:
            errors.append(error(path, "index.missing_section", f"{path}: missing required section '{section}'"))

    wiki_root = path.parent
    actual_pages = [
        p for p in wiki_root.glob("*/*.md")
        if p.name != "index.md" and not should_skip_wiki_file(p)
    ]

    total_match = re.search(r"^Total pages:\s*(\d+)", text, re.MULTILINE)
    if total_match:
        declared_total = int(total_match.group(1))
        if declared_total != len(actual_pages):
            errors.append(
                error(path, "index.total_pages", f"{path}: Total pages is {declared_total}, expected {len(actual_pages)}")
            )
    else:
        errors.append(error(path, "index.total_pages_missing", f"{path}: missing 'Total pages' header"))

    indexed_files = re.findall(r"^- file:\s*(wiki/.+\.md)\s*$", text, re.MULTILINE)
    indexed_set = set(indexed_files)
    actual_set = {f"wiki/{p.relative_to(wiki_root).as_posix()}" for p in actual_pages}

    missing_from_index = sorted(actual_set - indexed_set)
    missing_on_disk = sorted(indexed_set - actual_set)
    if missing_from_index:
        errors.append(error(path, "index.files_missing", f"{path}: files missing from index: {missing_from_index}"))
    if missing_on_disk:
        errors.append(error(path, "index.files_missing_on_disk", f"{path}: index references missing files: {missing_on_disk}"))

    return errors



def project_root_for_wiki_file(path: Path) -> Path | None:
    for parent in path.parents:
        if parent.name == "wiki":
            return parent.parent
    return None


def validate_schema_version_report(project: Path) -> list[dict[str, object]]:
    domain_path = project / "_domain.md"
    if not domain_path.exists():
        return [
            error(
                domain_path,
                "schema_version.domain_missing",
                f"{domain_path}: missing _domain.md with schema_version",
                expected=CURRENT_SCHEMA_VERSION,
                actual="missing",
            )
        ]
    text = domain_path.read_text(encoding="utf-8")
    fields, _body, locations = parse_frontmatter_with_locations(text)
    if "schema_version" not in fields:
        return [
            error(
                domain_path,
                "schema_version.missing",
                f"{domain_path}: missing schema_version in _domain.md frontmatter",
                line=1,
                column=1,
                expected=CURRENT_SCHEMA_VERSION,
                actual="missing",
            )
        ]
    actual = str(locations.get("schema_version", {}).get("value") or "").strip()
    if actual != CURRENT_SCHEMA_VERSION:
        return [
            error(
                domain_path,
                "schema_version.unsupported",
                f"{domain_path}: schema_version '{actual}' is not supported; expected '{CURRENT_SCHEMA_VERSION}'",
                line=locations.get("schema_version", {}).get("line"),
                column=locations.get("schema_version", {}).get("column"),
                expected=CURRENT_SCHEMA_VERSION,
                actual=actual,
            )
        ]
    return []

def main(argv: list[str]) -> int:
    fmt = "text"
    if "--format" in argv:
        idx = argv.index("--format")
        if idx + 1 >= len(argv):
            print("--format requires text or json")
            return 2
        fmt = argv[idx + 1]
        argv = argv[:idx] + argv[idx + 2:]
    if fmt not in {"text", "json"}:
        print("--format must be text or json")
        return 2
    files = [Path(f) for f in argv if f.endswith(".md")]
    wiki_files = [
        f
        for f in files
        if re.search(r"[/\\]wiki[/\\]", str(f)) and not any(part in SKIP_DIRNAMES for part in f.parts)
    ]

    if not wiki_files:
        return 0

    all_errors: list[dict[str, str]] = []
    project_roots: set[Path] = set()
    for f in wiki_files:
        if not f.exists():
            continue
        project_root = project_root_for_wiki_file(f)
        if project_root is not None:
            project_roots.add(project_root)
        errs = validate_file_report(f)
        all_errors.extend(errs)

    for project_root in sorted(project_roots):
        all_errors.extend(validate_schema_version_report(project_root))

    if fmt == "json":
        print(
            json.dumps(
                {
                    "outcome": "fail" if all_errors else "pass",
                    "checked": len(wiki_files),
                    "errors": all_errors,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1 if all_errors else 0

    if all_errors:
        print("REEFIKI frontmatter validation FAILED:\n")
        for e in all_errors:
            print(f"  x {e['message']}")
        print(f"\n{len(all_errors)} error(s). Fix before committing.")
        return 1

    print(f"REEFIKI: {len(wiki_files)} wiki file(s) validated OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
