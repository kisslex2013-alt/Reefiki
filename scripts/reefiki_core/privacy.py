from __future__ import annotations

import fnmatch
import hashlib
import re
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from .project_paths import iter_pages, relative
from .repo_paths import resolve_contained_path


SECRET_PATTERNS = [
    ".env",
    ".env.*",
    "secrets.*",
    "credentials.*",
    "id_rsa",
    "id_rsa.pub",
    "*.pem",
    "*.key",
    "*.pfx",
    "*.p12",
    ".npmrc",
    ".netrc",
]
SECRET_PARTS = {".aws", ".ssh"}
FORBIDDEN_PARTS = {
    ".git",
    "node_modules",
    "vendor",
    "__pycache__",
    "dist",
    "build",
    "target",
    ".next",
    ".cache",
}
BINARY_EXTS = {
    ".exe",
    ".dll",
    ".so",
    ".dylib",
    ".bin",
    ".iso",
    ".img",
    ".dmg",
    ".zip",
    ".tar",
    ".gz",
    ".7z",
    ".rar",
    ".mp4",
    ".mov",
    ".mkv",
    ".mp3",
    ".wav",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".pdf",
    ".docx",
    ".xlsx",
    ".pptx",
}


def classify_path(value: str, project: Path) -> tuple[bool, str]:
    parsed = urlparse(value)
    if parsed.scheme in {"http", "https"}:
        ext = Path(parsed.path).suffix.lower()
        if ext in BINARY_EXTS:
            return False, f"binary-url:{ext}"
        return True, "ok"
    path, reason = resolve_contained_path(project, value)
    if path is None:
        return False, reason
    name = path.name
    lower_parts = {part.lower() for part in path.parts}
    if lower_parts & FORBIDDEN_PARTS:
        return False, "forbidden-directory"
    if lower_parts & SECRET_PARTS:
        return False, "secret-directory"
    for pattern in SECRET_PATTERNS:
        if fnmatch.fnmatch(name.lower(), pattern.lower()):
            return False, "secret-name"
    if path.suffix.lower() in BINARY_EXTS:
        return False, f"binary-file:{path.suffix.lower()}"
    if path.exists() and path.is_file() and path.stat().st_size > 5 * 1024 * 1024:
        return False, "large-file"
    return True, "ok"


def is_url(value: str) -> bool:
    return urlparse(value).scheme in {"http", "https"}


def canonical_url(value: str) -> str:
    parsed = urlparse(value.strip())
    scheme = "https" if parsed.scheme in {"http", "https"} else parsed.scheme.lower()
    host = (parsed.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    port = ""
    if parsed.port and not (
        (scheme == "http" and parsed.port == 80) or (scheme == "https" and parsed.port == 443)
    ):
        port = f":{parsed.port}"
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/")
    query = urlencode(sorted(parse_qsl(parsed.query, keep_blank_values=True)), doseq=True)
    return urlunparse((scheme, f"{host}{port}", path, "", query, ""))


def extract_urls(text: str) -> list[str]:
    raw_urls = re.findall(r"https?://[^\s<>\]\)\"']+", text)
    return [url.rstrip(".,;:!?") for url in raw_urls]


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def iter_project_text_files(project: Path) -> list[Path]:
    files: list[Path] = list(iter_pages(project))
    for root in [project / "inbox", project / "seen"]:
        if root.exists():
            files.extend(path for path in root.rglob("*.md") if path.is_file())
    return sorted(files)


def inbox_items(project: Path) -> list[Path]:
    inbox = project / "inbox"
    if not inbox.exists():
        return []
    return sorted(path for path in inbox.glob("*") if path.is_file() and path.name != ".gitkeep")


def dedup_check(project: Path, source: str) -> int:
    matches: list[str] = []
    if is_url(source):
        source_url = canonical_url(source)
        for path in iter_project_text_files(project):
            text = path.read_text(encoding="utf-8", errors="replace")
            if any(canonical_url(url) == source_url for url in extract_urls(text)):
                matches.append(f"url:{relative(project, path)}")
    else:
        path, reason = resolve_contained_path(project, source)
        if path is None:
            print(f"Refused: {reason}")
            return 2
        if not path.exists() or not path.is_file():
            print(f"Source file not found: {path}")
            return 2
        inbox_same_name = project / "inbox" / path.name
        if inbox_same_name.exists() and inbox_same_name.resolve() != path.resolve():
            matches.append(f"name:{relative(project, inbox_same_name)}")
        source_hash = file_sha256(path)
        for candidate in iter_project_text_files(project):
            if candidate.resolve() == path.resolve():
                continue
            try:
                if file_sha256(candidate) == source_hash:
                    matches.append(f"sha256:{relative(project, candidate)}")
            except OSError:
                continue
    if matches:
        print("Duplicate candidate(s):")
        for match in matches:
            print(f"  {match}")
        return 1
    print("No duplicates found.")
    return 0


def privacy_scan(project: Path) -> int:
    problems: list[str] = []
    for folder in ["inbox", "wiki", "seen"]:
        root = project / folder
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_file():
                ok, reason = classify_path(str(path), project)
                if not ok:
                    problems.append(f"{relative(project, path)}: {reason}")
    if problems:
        print("Privacy guard FAILED:")
        for problem in problems:
            print(f"  x {problem}")
        return 1
    print("Privacy guard OK.")
    return 0
