"""Check local Markdown links and HTML image sources in project documentation."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
DOCUMENTS = (ROOT / "README.md", ROOT / "AGENTS.md", *(ROOT / "docs").glob("*.md"))
MARKDOWN_LINK = re.compile(r"!?(?:\[[^\]]*\])\(([^)]+)\)")
HTML_IMAGE = re.compile(r'<img\b[^>]*\bsrc="([^"]+)"', re.IGNORECASE)


def main() -> int:
    checked = 0
    broken: list[str] = []
    for document in DOCUMENTS:
        content = document.read_text(encoding="utf-8")
        targets = [*MARKDOWN_LINK.findall(content), *HTML_IMAGE.findall(content)]
        for target in targets:
            parts = urlsplit(target)
            if parts.scheme or target.startswith(("#", "//")):
                continue
            checked += 1
            path = document.parent / unquote(parts.path)
            if not path.is_file():
                broken.append(f"{document.relative_to(ROOT)}: {target}")
    for item in broken:
        print(item)
    print(f"relative_links_checked={checked} broken={len(broken)}")
    return int(bool(broken))


if __name__ == "__main__":
    raise SystemExit(main())
