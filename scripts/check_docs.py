"""Check the three documentation sets and their relative links."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOP_LEVEL = ("README", "SECURITY", "CONTRIBUTING")
GUIDES = ("deployment", "usage", "api", "limitations", "live-test-2026-11-14")


def documents() -> list[Path]:
    result = [ROOT / f"{name}{suffix}.md" for name in TOP_LEVEL for suffix in ("", ".en", ".kk")]
    result += [ROOT / "docs" / language / f"{name}.md"
               for name in GUIDES for language in ("", "en", "kk")]
    return result


def main() -> None:
    errors = []
    for source in documents():
        if not source.is_file():
            errors.append(f"Missing document: {source.relative_to(ROOT)}")
            continue
        body = source.read_text(encoding="utf-8")
        navigation = "\n".join(body.splitlines()[:5])
        for label in ("Русский", "English", "Қазақша"):
            if label not in navigation:
                errors.append(f"Missing {label} language navigation: {source.relative_to(ROOT)}")
        for link in re.findall(r"\[[^\]]+\]\(([^)]+)\)", body):
            if re.match(r"^[a-z]+://", link) or link.startswith("#"):
                continue
            target = (source.parent / link.split("#", 1)[0]).resolve()
            if not target.is_file():
                errors.append(f"Broken link in {source.relative_to(ROOT)}: {link}")
    if errors:
        raise SystemExit("\n".join(errors))
    print(f"Checked {len(documents())} localized Markdown files and relative links")


if __name__ == "__main__":
    main()
