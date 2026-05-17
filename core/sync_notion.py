"""
Notion ↔ Local Knowledge Base sync engine.

Supports:
  pull  — fetch Notion pages/databases → local Bug知识库/*.md
  push  — upload local .md changes → Notion
  sync  — one-shot bidirectional sync (pull then push)
  log_to_notion — write a log entry to Notion database

Requires: NOTION_API_KEY in environment or .vscode/settings.json
"""
import os, json, time, hashlib
from pathlib import Path
from typing import Any
from core.logger import log
from core.config import CFG


def _proxies() -> dict | None:
    proxy = CFG.NOTION_PROXY
    if proxy:
        return {"http": proxy, "https": proxy}
    return None


def _get_api_key() -> str:
    key = CFG.NOTION_KEY
    if not key:
        settings = CFG.ROOT / ".vscode" / "settings.json"
        if settings.exists():
            try:
                data = json.loads(settings.read_text(encoding="utf-8"))
                key = data.get("notion.apiKey", "")
            except (json.JSONDecodeError, OSError):
                pass
    return key


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {_get_api_key()}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    }


def _find_database(name: str) -> str | None:
    """Search for a Notion database by name. Returns database ID or None."""
    import requests
    resp = requests.post(
        "https://api.notion.com/v1/search",
        headers=_headers(),
        json={"query": name, "page_size": 20},
        timeout=30, proxies=_proxies(),
    )
    if resp.status_code != 200:
        return None
    # Priority 1: actual databases
    for r in resp.json().get("results", []):
        if r.get("object") == "database":
            title = "".join(t.get("plain_text", "") for t in (r.get("title") or []))
            if name.lower() in title.lower() or "riycol" in title.lower():
                return r["id"]
    # Priority 2: pages that might be databases (fallback)
    for r in resp.json().get("results", []):
        if r.get("object") != "database":
            title_blocks = r.get("title") or r.get("properties", {}).get("title", {}).get("title") or []
            title = "".join(t.get("plain_text", "") for t in title_blocks)
            if title and (name.lower() in title.lower() or "riycol" in title.lower()):
                return r["id"]
    return None


def _find_page_by_title(db_id: str, title: str) -> str | None:
    """Check if a page with the given title already exists in the database."""
    import requests
    qresp = requests.post(
        f"https://api.notion.com/v1/databases/{db_id}/query",
        headers=_headers(),
        json={"page_size": 100},
        timeout=30, proxies=_proxies(),
    )
    if qresp.status_code != 200:
        return None
    for p in qresp.json().get("results", []):
        for prop_key, prop_val in p.get("properties", {}).items():
            if prop_val.get("type") == "title":
                existing = "".join(t.get("plain_text", "") for t in (prop_val.get("title") or []))
                if existing == title:
                    return p["id"]
    return None


def _create_page_in_db(db_id: str, title: str, content: str, extra_props: dict | None = None) -> str | None:
    """Create a page in a Notion database. Returns page ID or None.

    Skips creation if a page with the same title already exists.
    """
    import requests
    # Dedup: skip if page with same title already exists
    existing = _find_page_by_title(db_id, title)
    if existing:
        log.info(f"Notion dedup: '{title}' already exists ({existing[:8]}...), skipping")
        return existing

    properties = {
        "名称": {"title": [{"text": {"content": title[:100]}}]},
    }
    if extra_props:
        properties.update(extra_props)

    body = {
        "parent": {"database_id": db_id},
        "properties": properties,
        "children": [
            {"object": "block", "type": "paragraph", "paragraph": {
                "rich_text": [{"type": "text", "text": {"content": content[:2000]}}]
            }}
        ],
    }
    resp = requests.post(
        "https://api.notion.com/v1/pages",
        headers=_headers(),
        json=body, timeout=30, proxies=_proxies(),
    )
    if resp.status_code == 200:
        return resp.json().get("id")
    log.warn(f"Notion create page failed: {resp.status_code} {resp.text[:200]}")
    return None


def _safe_filename(title: str) -> str:
    """Sanitize title to a safe filename."""
    return "".join(c for c in title if c not in r'\/:*?"<>|' and ord(c) >= 32).strip() or "untitled"


def _extract_text(blocks: list[dict]) -> str:
    """Recursively extract plain text from Notion blocks."""
    lines = []
    for b in blocks:
        btype = b.get("type", "")
        content = b.get(btype, {})
        rich = content.get("rich_text") or content.get("title") or []
        text = "".join(t.get("plain_text", "") for t in rich)
        if text.strip():
            if btype.startswith("heading_"):
                level = int(btype.split("_")[1])
                lines.append("#" * level + " " + text)
            elif btype == "bulleted_list_item":
                lines.append("- " + text)
            elif btype == "numbered_list_item":
                lines.append("1. " + text)
            elif btype == "code":
                lang = content.get("language", "")
                lines.append(f"```{lang}\n{text}\n```")
            elif btype == "quote":
                lines.append("> " + text)
            else:
                lines.append(text)
        if b.get("has_children"):
            children = _get_blocks(b["id"])
            lines.append(_extract_text(children))
    return "\n\n".join(lines)


def _get_blocks(block_id: str) -> list[dict]:
    import requests
    url = f"https://api.notion.com/v1/blocks/{block_id}/children?page_size=100"
    resp = requests.get(url, headers=_headers(), timeout=30, proxies=_proxies())
    if resp.status_code != 200:
        log.warn(f"Notion blocks fetch failed: {resp.status_code}")
        return []
    return resp.json().get("results", [])


def pull(notion_db_name: str = "riycol agent 库(知识 数据)",
         local_dir: str | None = None) -> int:
    """Pull all pages from a Notion database into local .md files.

    Returns count of files written.
    """
    import requests

    if local_dir is None:
        local_dir = str(CFG.ROOT / "Bug知识库")
    Path(local_dir).mkdir(parents=True, exist_ok=True)

    # Search for the database
    search_resp = requests.post(
        "https://api.notion.com/v1/search",
        headers=_headers(),
        json={"query": notion_db_name, "page_size": 10},
        timeout=30, proxies=_proxies(),
    )
    if search_resp.status_code != 200:
        log.error(f"Notion search failed: {search_resp.status_code}")
        return 0

    db_id = None
    for r in search_resp.json().get("results", []):
        if r.get("object") == "database":
            db_id = r["id"]
            break
        # Also check pages that might be databases
        if r.get("title"):
            title = "".join(t.get("plain_text", "") for t in r.get("title", []) or [])
            if title == notion_db_name:
                db_id = r["id"]
                break

    if not db_id:
        log.warn(f"Notion database '{notion_db_name}' not found")
        return 0

    # Query all pages in the database
    pages_resp = requests.post(
        f"https://api.notion.com/v1/databases/{db_id}/query",
        headers=_headers(),
        json={"page_size": 100},
        timeout=30, proxies=_proxies(),
    )
    if pages_resp.status_code != 200:
        log.error(f"Notion query failed: {pages_resp.status_code}")
        return 0

    count = 0
    for page in pages_resp.json().get("results", []):
        page_id = page["id"]
        # Find title property dynamically (any property with type="title")
        title_prop = None
        for prop_key, prop_val in page.get("properties", {}).items():
            if prop_val.get("type") == "title":
                title_prop = prop_val
                break
        if title_prop is None:
            title_prop = page.get("properties", {}).get("Name") or page.get("properties", {}).get("title")
        title = ""
        if title_prop:
            title_parts = title_prop.get("title", []) or []
            title = "".join(t.get("plain_text", "") for t in title_parts)

        if not title:
            title = f"untitled-{page_id[:8]}"

        # Get full page content
        blocks = _get_blocks(page_id)
        content = _extract_text(blocks)

        # Build markdown with frontmatter
        last_edited = page.get("last_edited_time", time.strftime("%Y-%m-%dT%H:%M:%SZ"))
        md = f"""---
title: "{title}"
notion_id: "{page_id}"
last_synced: "{time.strftime('%Y-%m-%dT%H:%M:%S')}"
notion_edited: "{last_edited}"
status: "synced"
---

{content}
"""
        filename = _safe_filename(title)
        filepath = Path(local_dir) / f"{filename}.md"
        filepath.write_text(md, encoding="utf-8")
        log.info(f"Notion sync: pulled '{title}' → {filepath.name}")
        count += 1

    return count


def push(local_dir: str | None = None,
         target_db_name: str = "riycol agent 库(知识 数据)") -> int:
    """Push local .md files marked 'unsynced' or 'new' to Notion database.

    Returns count of pages created.
    """
    if local_dir is None:
        local_dir = str(CFG.ROOT / "Bug知识库")
    local_path = Path(local_dir)
    if not local_path.exists():
        return 0

    db_id = _find_database(target_db_name)
    if not db_id:
        log.warn(f"Notion push: database '{target_db_name}' not found")
        return 0

    count = 0
    for md_file in local_path.rglob("*.md"):
        try:
            text = md_file.read_text(encoding="utf-8")
        except Exception:
            continue

        # Parse frontmatter for unsynced/new status
        is_new = False
        if text.startswith("---"):
            end = text.find("---", 3)
            if end > 0:
                for line in text[3:end].splitlines():
                    if line.startswith("status:") and ('"unsynced"' in line or '"new"' in line or "'unsynced'" in line or "'new'" in line):
                        is_new = True
                        break

        if not is_new:
            continue

        title = md_file.stem
        body = text[text.find("---", 3) + 3:].strip() if text.startswith("---") else text
        page_id = _create_page_in_db(db_id, title, body[:2000])
        if page_id:
            # Update local file with notion_id and synced status
            try:
                synced_text = text.replace('status: "unsynced"', 'status: "synced"').replace("status: 'unsynced'", 'status: "synced"')
                synced_text = synced_text.replace('status: "new"', 'status: "synced"').replace("status: 'new'", 'status: "synced"')
                md_file.write_text(synced_text, encoding="utf-8")
            except Exception:
                pass
            log.info(f"Notion push: '{title}' → Notion ({page_id[:8]}...)")
            count += 1

    return count


def log_to_notion(title: str, content: str = "",
                  tags: list[str] | None = None,
                  db_name: str = "riycol agent 库(知识 数据)") -> bool:
    """Write a log entry to a Notion database.

    Args:
        title: Entry title (appears as page title in Notion)
        content: Entry body/content
        tags: Optional tags for categorization
        db_name: Target database name

    Returns True if successfully written.
    """
    db_id = _find_database(db_name)
    if not db_id:
        log.warn(f"Notion log: database '{db_name}' not found")
        return False

    extra = {}
    if tags:
        extra["标签"] = {"multi_select": [{"name": t[:20]} for t in tags]}

    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    full_content = f"[{ts}]\n{content}" if content else f"[{ts}]"
    page_id = _create_page_in_db(db_id, title, full_content, extra)
    if page_id:
        log.info(f"Notion log: '{title}' written ({page_id[:8]}...)")
        return True
    return False


def log_agent_activity(agent_name: str, action: str, detail: str = "") -> bool:
    """Log agent activity to Notion."""
    return log_to_notion(
        f"[Agent] {agent_name}: {action}",
        detail,
        tags=["agent", agent_name, "activity"],
    )


def log_eval_result(suite: str, passed: int, total: int, detail: str = "") -> bool:
    """Log eval result to Notion."""
    return log_to_notion(
        f"[Eval] {suite}: {passed}/{total} passed",
        detail,
        tags=["eval", suite, "result"],
    )


def sync(local_dir: str | None = None,
         notion_db_name: str = "riycol agent 库(知识 数据)") -> dict:
    """Full bidirectional sync: pull from Notion, then push local changes.

    Returns {"pulled": int, "pushed": int}
    """
    log.info("Notion sync: starting bidirectional sync...")
    pulled = pull(notion_db_name, local_dir)
    pushed = push(local_dir, notion_db_name)
    log.info(f"Notion sync: done (pulled={pulled}, pushed={pushed})")
    return {"pulled": pulled, "pushed": pushed}


def deduplicate(db_name: str = "riycol agent 库(知识 数据)") -> int:
    """Remove duplicate pages from a Notion database (keep most recent).

    Returns count of duplicates removed (archived).
    """
    import requests

    db_id = _find_database(db_name)
    if not db_id:
        log.warn(f"Notion dedup: database '{db_name}' not found")
        return 0

    qresp = requests.post(
        f"https://api.notion.com/v1/databases/{db_id}/query",
        headers=_headers(),
        json={"page_size": 100},
        timeout=30, proxies=_proxies(),
    )
    if qresp.status_code != 200:
        log.warn(f"Notion dedup: query failed {qresp.status_code}")
        return 0

    # Group pages by title
    from collections import defaultdict
    groups: dict[str, list[dict]] = defaultdict(list)
    for p in qresp.json().get("results", []):
        title_text = ""
        for k, v in p.get("properties", {}).items():
            if v.get("type") == "title":
                title_text = "".join(t.get("plain_text", "") for t in (v.get("title") or []))
                break
        groups[title_text].append(p)

    removed = 0
    for title, pages in groups.items():
        if len(pages) <= 1:
            continue
        # Sort by last_edited_time descending, keep first
        pages.sort(key=lambda p: p.get("last_edited_time", ""), reverse=True)
        for dup in pages[1:]:
            page_id = dup["id"]
            resp = requests.patch(
                f"https://api.notion.com/v1/pages/{page_id}",
                headers=_headers(),
                json={"archived": True},
                timeout=30, proxies=_proxies(),
            )
            if resp.status_code == 200:
                log.info(f"Notion dedup: archived '{title}' ({page_id[:8]}...)")
                removed += 1
            else:
                log.warn(f"Notion dedup: failed to archive {page_id[:8]}...: {resp.status_code}")
    return removed


def setup_hook(interval_minutes: int = 15):
    """Create a PostToolUse hook script for automatic sync after Notion-related changes.

    This generates a PowerShell hook that triggers sync when Notion MCP tools are used.
    """
    hook_script = CFG.ROOT / ".claude" / "hooks" / "notion-sync.ps1"
    hook_script.parent.mkdir(parents=True, exist_ok=True)
    hook_script.write_text(f'''# Auto-generated Notion sync hook
# Triggers after Notion-related tool use
python -c "from core.sync_notion import sync; sync()"
''', encoding="utf-8")
    log.info(f"Notion sync hook created: {hook_script}")
    return str(hook_script)
