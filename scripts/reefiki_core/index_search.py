from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from pathlib import Path

from .file_utils import slugify
from .markdown import as_text, extract_heading_chunks, extract_wiki_links, parse_frontmatter
from .project_paths import db_path, iter_pages, relative
from .storage import index_lock, sqlite_connection


def build_index(project: Path) -> int:
    with index_lock(project):
        return _build_index_unlocked(project)


def _build_index_unlocked(project: Path) -> int:
    database = db_path(project)
    count = 0
    known_ids: set[str] = set()
    pending_links: list[dict[str, object]] = []
    with sqlite_connection(database) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(
            """
            DROP TABLE IF EXISTS pages;
            DROP TABLE IF EXISTS pages_fts;
            DROP TABLE IF EXISTS chunks;
            DROP TABLE IF EXISTS chunks_fts;
            DROP TABLE IF EXISTS links;
            CREATE TABLE pages (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                type TEXT NOT NULL,
                tags TEXT NOT NULL,
                useful_when TEXT NOT NULL,
                abstract TEXT NOT NULL,
                sources TEXT NOT NULL,
                file TEXT NOT NULL,
                date_added TEXT NOT NULL,
                use_count INTEGER NOT NULL,
                last_used TEXT,
                body TEXT NOT NULL,
                sha256 TEXT NOT NULL
            );
            CREATE VIRTUAL TABLE pages_fts USING fts5(
                id,
                title,
                tags,
                useful_when,
                abstract,
                body,
                content='pages',
                content_rowid='rowid'
            );
            CREATE TABLE chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                page_id TEXT NOT NULL,
                heading_path TEXT NOT NULL,
                content TEXT NOT NULL,
                file TEXT NOT NULL,
                start_line INTEGER NOT NULL
            );
            CREATE VIRTUAL TABLE chunks_fts USING fts5(
                page_id,
                heading_path,
                content,
                content='chunks',
                content_rowid='id'
            );
            CREATE TABLE links (
                source_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                resolved INTEGER NOT NULL,
                file TEXT NOT NULL,
                line INTEGER NOT NULL
            );
            CREATE INDEX idx_links_source ON links(source_id);
            CREATE INDEX idx_links_target ON links(target_id);
            CREATE INDEX idx_chunks_page ON chunks(page_id);
            """
        )
        for page in iter_pages(project):
            text = page.read_text(encoding="utf-8")
            fm, body = parse_frontmatter(text)
            page_id = str(fm.get("id") or page.stem)
            known_ids.add(page_id)
            row = {
                "id": page_id,
                "title": as_text(fm.get("title")) or page_id,
                "type": as_text(fm.get("type")) or page.parent.name.rstrip("s"),
                "tags": as_text(fm.get("tags")),
                "useful_when": as_text(fm.get("useful_when")),
                "abstract": as_text(fm.get("abstract")),
                "sources": as_text(fm.get("sources")),
                "file": relative(project, page),
                "date_added": as_text(fm.get("date_added")),
                "use_count": int(fm.get("use_count") or 0),
                "last_used": as_text(fm.get("last_used")) or None,
                "body": body.strip(),
                "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            }
            conn.execute(
                """
                INSERT INTO pages VALUES (
                    :id, :title, :type, :tags, :useful_when, :abstract, :sources,
                    :file, :date_added, :use_count, :last_used, :body, :sha256
                )
                """,
                row,
            )
            rowid = conn.execute("SELECT rowid FROM pages WHERE id = ?", (page_id,)).fetchone()[0]
            conn.execute(
                "INSERT INTO pages_fts(rowid, id, title, tags, useful_when, abstract, body) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (rowid, page_id, row["title"], row["tags"], row["useful_when"], row["abstract"], row["body"]),
            )
            for chunk in extract_heading_chunks(body):
                cursor = conn.execute(
                    """
                    INSERT INTO chunks(page_id, heading_path, content, file, start_line)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (page_id, chunk["heading_path"], chunk["content"], row["file"], chunk["start_line"]),
                )
                conn.execute(
                    "INSERT INTO chunks_fts(rowid, page_id, heading_path, content) VALUES (?, ?, ?, ?)",
                    (cursor.lastrowid, page_id, chunk["heading_path"], chunk["content"]),
                )
            for link in extract_wiki_links(body):
                pending_links.append(
                    {
                        "source_id": page_id,
                        "target_id": link["target_id"],
                        "kind": link["kind"],
                        "resolved": 0,
                        "file": row["file"],
                        "line": link["line"],
                    }
                )
            count += 1
        for link in pending_links:
            link["resolved"] = 1 if as_text(link["target_id"]) in known_ids else 0
            conn.execute(
                """
                INSERT INTO links(source_id, target_id, kind, resolved, file, line)
                VALUES (:source_id, :target_id, :kind, :resolved, :file, :line)
                """,
                link,
            )
    return count


def escape_fts(query: str) -> str:
    # Keep FTS queries in plain token mode; raw hyphens can be parsed as FTS syntax
    # and make user text like "anti-daily-log" fail with "no such column".
    tokens = re.findall(r"\w+", query, flags=re.UNICODE)
    return " OR ".join(f'"{token}"' for token in tokens)


def search(
    project: Path,
    query: str,
    limit: int,
    page_type: str | None = None,
    tag: str | None = None,
    link_to: str | None = None,
    linked_by: str | None = None,
    orphan: bool = False,
    chunked: bool = False,
) -> list[sqlite3.Row]:
    database = db_path(project)
    if not database.exists():
        build_index(project)
    return search_existing(
        project,
        database,
        query,
        limit,
        page_type=page_type,
        tag=tag,
        link_to=link_to,
        linked_by=linked_by,
        orphan=orphan,
        chunked=chunked,
    )


def search_existing(
    project: Path,
    database: Path,
    query: str,
    limit: int,
    page_type: str | None = None,
    tag: str | None = None,
    link_to: str | None = None,
    linked_by: str | None = None,
    orphan: bool = False,
    chunked: bool = False,
) -> list[sqlite3.Row]:
    try:
        with sqlite_connection(database, row_factory=True) as conn:
            fts_query = escape_fts(query)
            filters: list[str] = []
            params: list[object] = []
            if page_type:
                filters.append("p.type = ?")
                params.append(page_type)
            if tag:
                filters.append("p.tags LIKE ?")
                params.append(f"%{tag}%")
            if link_to:
                filters.append(
                    "EXISTS (SELECT 1 FROM links l WHERE l.source_id = p.id AND l.target_id = ?)"
                )
                params.append(slugify(link_to))
            if linked_by:
                filters.append(
                    "EXISTS (SELECT 1 FROM links l WHERE l.target_id = p.id AND l.source_id = ?)"
                )
                params.append(slugify(linked_by))
            if orphan:
                filters.append(
                    "NOT EXISTS (SELECT 1 FROM links l WHERE l.target_id = p.id AND l.resolved = 1)"
                )
            where_sql = " AND ".join(filters)
            if query.strip():
                if not fts_query:
                    return []
                fts_table = "chunks_fts" if chunked else "pages_fts"
                where_sql = (f"{fts_table} MATCH ?" + (f" AND {where_sql}" if where_sql else ""))
                params = [fts_query, *params]
                if chunked:
                    from_sql = "chunks_fts JOIN chunks c ON c.id = chunks_fts.rowid JOIN pages p ON p.id = c.page_id"
                    score_sql = "bm25(chunks_fts, 2.0, 4.0, 5.0) AS score, c.heading_path AS heading_path, c.content AS snippet"
                else:
                    from_sql = "pages_fts JOIN pages p ON p.rowid = pages_fts.rowid"
                    score_sql = "bm25(pages_fts, 6.0, 5.0, 3.0, 4.0, 5.0, 1.0) AS score, '' AS heading_path, '' AS snippet"
                order_sql = "score"
            else:
                where_sql = where_sql or "1=1"
                from_sql = "pages p"
                score_sql = "0.0 AS score, '' AS heading_path, '' AS snippet"
                order_sql = "p.title"
            rows = conn.execute(
                f"""
                SELECT p.*, {score_sql}
                FROM {from_sql}
                WHERE {where_sql}
                ORDER BY {order_sql}
                LIMIT ?
                """,
                (*params, limit * 3 if chunked else limit),
            ).fetchall()
            if chunked:
                seen_ids: set[str] = set()
                deduped: list[sqlite3.Row] = []
                for row in rows:
                    row_id = as_text(row["id"])
                    if row_id in seen_ids:
                        continue
                    seen_ids.add(row_id)
                    deduped.append(row)
                    if len(deduped) >= limit:
                        break
                return deduped
            return rows
    except sqlite3.OperationalError as exc:
        if "no such table" not in str(exc):
            raise
    build_index(project)
    return search_existing(
        project,
        database,
        query,
        limit,
        page_type=page_type,
        tag=tag,
        link_to=link_to,
        linked_by=linked_by,
        orphan=orphan,
        chunked=chunked,
    )


def print_search(
    project: Path,
    query: str,
    limit: int,
    fmt: str,
    output: str,
    page_type: str | None,
    tag: str | None,
    link_to: str | None,
    linked_by: str | None,
    orphan: bool,
    chunked: bool,
) -> int:
    rows = search(
        project,
        query,
        limit,
        page_type=page_type,
        tag=tag,
        link_to=link_to,
        linked_by=linked_by,
        orphan=orphan,
        chunked=chunked,
    )
    if fmt == "json":
        if output == "compact":
            print(json.dumps([compact_search_row(row) for row in rows], ensure_ascii=False, indent=2))
            return 0
        if output == "files":
            print(json.dumps(search_files_payload(query, rows), ensure_ascii=False, indent=2))
            return 0
        print(json.dumps([dict(row) for row in rows], ensure_ascii=False, indent=2))
        return 0
    for idx, row in enumerate(rows, 1):
        print(f"{idx}. {row['title']} ({row['file']})")
        print(f"   type: {row['type']} | tags: {row['tags']}")
        if row["abstract"]:
            print(f"   abstract: {row['abstract']}")
        print(f"   useful_when: {row['useful_when']}")
        if row["heading_path"]:
            print(f"   heading: {row['heading_path']}")
        print(f"   provenance: page={row['file']} sources={row['sources'] or '-'} sha256={row['sha256'][:12]}")
    if not rows:
        print("No matches.")
    return 0


def compact_search_row(row: sqlite3.Row) -> dict[str, object]:
    return {
        "id": row["id"],
        "title": row["title"],
        "type": row["type"],
        "tags": row["tags"],
        "useful_when": row["useful_when"],
        "abstract": row["abstract"],
        "sources": row["sources"],
        "file": row["file"],
        "date_added": row["date_added"],
        "use_count": row["use_count"],
        "last_used": row["last_used"],
        "score": row["score"],
        "heading_path": row["heading_path"],
        "snippet": row["snippet"],
        "sha256": row["sha256"],
    }


def search_files_payload(query: str, rows: list[sqlite3.Row]) -> dict[str, object]:
    return {
        "query": query,
        "count": len(rows),
        "files": [
            {
                "docid": row["id"],
                "path": row["file"],
                "title": row["title"],
                "type": row["type"],
                "score": row["score"],
                "heading_path": row["heading_path"],
                "snippet": row["snippet"],
            }
            for row in rows
        ],
    }


def project_local_lookup(project: Path, query: str, limit: int) -> list[dict[str, object]]:
    hits: list[dict[str, object]] = []
    for row in search(project, query, limit):
        chunk_context = best_chunk_context(project, query, as_text(row["id"]))
        hits.append(
            {
                "project": project.name,
                "id": row["id"],
                "title": row["title"],
                "type": row["type"],
                "file": row["file"],
                "useful_when": row["useful_when"],
                "matched_heading": chunk_context["heading_path"],
                "matched_chunk": chunk_context["snippet"],
                "score": row["score"],
            }
        )
    return hits


def best_chunk_context(project: Path, query: str, page_id: str) -> dict[str, str]:
    if not query.strip():
        return {"heading_path": "", "snippet": ""}
    database = db_path(project)
    if not database.exists():
        build_index(project)
    try:
        with sqlite_connection(database, row_factory=True) as conn:
            row = conn.execute(
                """
                SELECT c.heading_path, c.content AS snippet, bm25(chunks_fts, 2.0, 4.0, 5.0) AS score
                FROM chunks_fts
                JOIN chunks c ON c.id = chunks_fts.rowid
                WHERE chunks_fts MATCH ? AND c.page_id = ?
                ORDER BY score
                LIMIT 1
                """,
                (escape_fts(query), page_id),
            ).fetchone()
    except sqlite3.OperationalError as exc:
        if "no such table" not in str(exc):
            raise
        build_index(project)
        return best_chunk_context(project, query, page_id)
    if not row:
        return {"heading_path": "", "snippet": ""}
    return {"heading_path": as_text(row["heading_path"]), "snippet": as_text(row["snippet"])}
