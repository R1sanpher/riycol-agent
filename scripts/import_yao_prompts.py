r"""Import prompts from D:\AI Prompt\yao-open-prompts-main into the Riycol prompt system.
Usage: python scripts/import_yao_prompts.py [--dry-run]
"""
import sys, os, re, json
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from pathlib import Path
from core.logger import log

SOURCE = Path("D:/AI Prompt/yao-open-prompts-main/prompts")
OUTPUT = Path("data/prompts.json")

SKIP_FILES = {"README.md", "CATALOG.md", "CHANGELOG.md", "CONTRIBUTING.md",
              ".gitignore", "LICENSE"}

# Map source directory names to riycol categories
CATEGORY_MAP = {
    "01-ai-methods": "marketing",    # 元提示词/反编译方法
    "02-ai-work": "marketing",       # 生产力/企业场景
    "03-ai-learning": "marketing",   # 学习方法
    "04-ai-life": "marketing",       # 生活场景
    "05-ai-education": "marketing",  # 儿童教育
    "06-ai-content": "marketing",    # 内容创作
    "07-ai-coding": "chat",          # 编程
    "08-ai-marketing": "marketing",  # GEO营销
    "09-ai-thinking": "chat",        # 思维方法
}


def extract_frontmatter(text: str) -> dict:
    """Extract YAML-like frontmatter. Returns dict or {}."""
    m = re.match(r'^---\s*\n(.*?)\n---\s*\n', text, re.DOTALL)
    if not m:
        return {}
    fm = {}
    for line in m.group(1).split("\n"):
        if ":" in line:
            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            fm[key] = val
    return fm


def extract_prompt_body(text: str) -> str:
    """Extract the actual prompt from the markdown code block."""
    # Find content after "## Prompt" or "# Prompt"
    m = re.search(r'#{1,3}\s*Prompt\s*\n', text)
    if not m:
        return ""
    after = text[m.end():]
    # Extract from markdown code block
    code_match = re.search(r'````?markdown\s*\n(.*?)````', after, re.DOTALL)
    if not code_match:
        code_match = re.search(r'```(?:markdown)?\s*\n(.*?)```', after, re.DOTALL)
    if code_match:
        return code_match.group(1).strip()
    # Fallback: everything after "## Prompt"
    return after.strip()


def make_prompt_name(title: str, subcategory: str) -> str:
    """Generate a clean, short name from title and subcategory."""
    # Remove special characters and spaces
    name = re.sub(r'[：:：\s]+', '_', title)
    name = re.sub(r'[^\w一-鿿_-]', '', name)
    # Truncate long names
    if len(name) > 40:
        name = name[:40]
    return name or "untitled"


def main():
    dry_run = "--dry-run" in sys.argv
    imported = []
    skipped = []
    errors = []

    # Walk prompts directory
    for md_file in sorted(SOURCE.rglob("*.md")):
        if md_file.name in SKIP_FILES:
            continue

        rel = md_file.relative_to(SOURCE)
        category_dir = str(rel.parts[0]) if len(rel.parts) > 1 else "general"

        try:
            text = md_file.read_text(encoding="utf-8")
        except Exception as e:
            errors.append(f"Read error {md_file}: {e}")
            continue

        fm = extract_frontmatter(text)
        title = fm.get("title", md_file.stem)
        subcat = fm.get("subcategory", "")
        status = fm.get("status", "active")
        tags = fm.get("tags", "")

        # Skip non-active prompts
        if status != "active":
            skipped.append(f"{rel} — status={status}")
            continue

        body = extract_prompt_body(text)
        if not body or len(body) < 50:
            skipped.append(f"{rel} — no prompt body (or too short: {len(body)} chars)")
            continue

        riycol_cat = CATEGORY_MAP.get(category_dir, "marketing")
        name = make_prompt_name(title, subcat)

        imported.append({
            "category": riycol_cat,
            "name": name,
            "template": body,
            "version": 1,
            "description": f"{title} [{tags}]" if tags else title,
            "source": str(rel),
        })

    # Build JSON
    data: dict[str, list[dict]] = {}
    for item in imported:
        cat = item["category"]
        data.setdefault(cat, []).append({
            "name": item["name"],
            "version": item["version"],
            "description": item["description"],
            "template": item["template"],
        })

    print(f"\n=== Import Summary ===")
    print(f"  Valid prompts:   {len(imported)}")
    print(f"  Skipped:         {len(skipped)}")
    print(f"  Errors:          {len(errors)}")
    print(f"  Categories:      {list(data.keys())}")

    for item in imported[:5]:
        print(f"  + {item['category']}/{item['name']} - {item['description'][:60]}")

    if dry_run:
        print("\n[Dry run — no file written]")
        if skipped:
            print("\nSkipped:")
            for s in skipped[:10]:
                print(f"  - {s}")
        return

    # Write to data/prompts.json
    output_path = Path(OUTPUT)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nWritten to {output_path}")

    # Load into runtime
    from core.prompt_manager import prompts
    prompts.load_file(str(output_path))
    snap = prompts.snapshot()
    total = sum(len(t) for t in snap.values())
    print(f"Runtime: {total} templates loaded")


if __name__ == "__main__":
    main()
