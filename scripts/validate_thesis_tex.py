"""Lightweight LaTeX sanity checks when no local TeX engine is installed."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEX_FILES = [
    ROOT / "main.tex",
    ROOT / "abstract.tex",
    ROOT / "chapter3.tex",
    ROOT / "chapter4_proposed_authentication_scheme.tex",
    ROOT / "chapter5_evaluation.tex",
    ROOT / "chapter6_discussion.tex",
    ROOT / "chapter7_conclusion.tex",
    ROOT / "appendices.tex",
    *sorted((ROOT / "docs/chapter5_drafts").glob("*.tex")),
    *sorted((ROOT / "docs/appendices").glob("*.tex")),
]

STALE_PATTERNS = [
    (r"(?<![\d/])0/750", "stale zero-acceptance count"),
    (r"0\\% \(0/750\)", "stale blockchain acceptance"),
    (r"0x25629De856e42E1D2d52C8916622938C20A37Cc8", "old contract address"),
    (r"1\\,298\\,376", "old deployment gas"),
    (r"fece3e0d05ec63f0f71a2f2a1944f0efb0993b35a66b4de550a1aaeb30d8eec3", "old bytecode hash"),
    (r"% TODO: Add measured", "unresolved Chapter 5 TODO"),
]

REF_RE = re.compile(r"\\ref\{([^}]+)\}")
LABEL_RE = re.compile(r"\\label\{([^}]+)\}|label=(lst:[^,\]]+)")


def main() -> int:
    errors: list[str] = []
    labels: set[str] = set()
    refs: list[tuple[str, str]] = []

    for path in TEX_FILES:
        if not path.exists():
            errors.append(f"missing file: {path.relative_to(ROOT)}")
            continue
        text = path.read_text(encoding="utf-8")
        rel = str(path.relative_to(ROOT))
        for pattern, msg in STALE_PATTERNS:
            if re.search(pattern, text):
                errors.append(f"{rel}: {msg}")
        for m in LABEL_RE.finditer(text):
            labels.add(m.group(1) or m.group(2))
        for ref in REF_RE.findall(text):
            refs.append((rel, ref))
        if "??" in text:
            errors.append(f"{rel}: contains literal ??")

    missing = sorted({ref for _, ref in refs if ref not in labels})
    if missing:
        for ref in missing:
            users = [f for f, r in refs if r == ref]
            errors.append(f"undefined ref '{ref}' used in {users[0]}")

    if errors:
        print("VALIDATION FAILED")
        for e in errors:
            print(f"  - {e}")
        return 1

    print(f"OK: {len(TEX_FILES)} tex files, {len(labels)} labels, {len(refs)} refs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
