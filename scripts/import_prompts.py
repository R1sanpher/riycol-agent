"""Batch import prompt .md files from yao-open-prompts into the template library."""
import re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.prompt_manager import prompts, PromptTemplate

SRC = Path(r"D:\AI Prompt\yao-open-prompts-main\prompts\08-ai-marketing")


def extract_prompt(raw: str) -> str | None:
    """Extract prompt body from Obsidian-style .md file."""
    for pattern in [
        r"##\s*Prompt\s*\n\s*````markdown\s*\n(.*?)````",
        r"##\s*Prompt\s*\n\s*```markdown\s*\n(.*?)```",
        r"##\s*Prompt\s*\n\s*```\s*\n(.*?)```",
    ]:
        m = re.search(pattern, raw, re.DOTALL)
        if m:
            return m.group(1).strip()
    if "## Prompt" in raw:
        return raw.split("## Prompt")[-1].strip().removeprefix("```markdown").removeprefix("```").removesuffix("```").strip()
    return None


def extract_yaml(raw: str) -> dict:
    """Extract YAML frontmatter as dict."""
    fm = {}
    if raw.startswith("---"):
        end = raw.index("---", 4)
        for line in raw[4:end].strip().split("\n"):
            if ":" in line:
                k, v = line.split(":", 1)
                fm[k.strip()] = v.strip().strip('"').strip("'")
    return fm


def main():
    files = sorted([f for f in SRC.glob("*.md") if f.name != "README.md"])
    imported = 0
    skipped = 0

    for fp in files:
        raw = fp.read_text(encoding="utf-8")
        fm = extract_yaml(raw)
        prompt_text = extract_prompt(raw)
        if not prompt_text:
            print(f"  SKIP {fp.name}: no prompt body found")
            skipped += 1
            continue

        name = fp.stem  # e.g. "geo-article-generator"
        # Use name as-is, replacing hyphens with underscores for the template key
        template_name = name.replace("-", "_")
        description = fm.get("title", name.replace("-", " ").title())

        tmpl = PromptTemplate(
            name=template_name,
            version=1,
            description=description,
            template=prompt_text,
        )
        prompts.register("marketing", tmpl)
        imported += 1

    prompts.export_file(str(Path(__file__).parent.parent / "data" / "prompts.json"))
    print(f"\nDone: {imported} imported, {skipped} skipped, {prompts.template_count} total templates")


if __name__ == "__main__":
    main()
