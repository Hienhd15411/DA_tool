#!/usr/bin/env python
"""Parse docs/exercises/*.md, extract exercises, upsert into public.exercise.

Run:
  python import_exercises.py
"""
from __future__ import annotations
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
from generators.utils import get_conn, bulk_insert

DOCS = Path(__file__).parent.parent / "docs" / "exercises"

# Matches:  ## A1 — title   OR   ## A1. title
HEADER = re.compile(r"^##\s+([A-L])(\d+)\s*[—.\-:]?\s*(.+)$", re.MULTILINE)
# Level:    **Level:** L2      or   Level:    L2
LEVEL  = re.compile(r"(?:Level|level)[:\s\*]+L?(\d)", re.IGNORECASE)


def parse_file(path: Path) -> list[tuple]:
    text = path.read_text(encoding="utf-8")
    matches = list(HEADER.finditer(text))
    out: list[tuple] = []
    for i, m in enumerate(matches):
        theme, num, title = m.group(1), m.group(2), m.group(3).strip()
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        level_m = LEVEL.search(body[:500])
        level = int(level_m.group(1)) if level_m else 2
        exercise_id = f"{theme}{num}"
        out.append((exercise_id, theme, title, level, body))
    return out


def main():
    load_dotenv()
    if not os.environ.get("DATABASE_URL"):
        sys.exit("Set DATABASE_URL")

    all_rows: list[tuple] = []
    for p in sorted(DOCS.glob("[A-L]-*.md")):
        items = parse_file(p)
        print(f"  {p.name}: {len(items)} exercises")
        all_rows.extend(items)

    print(f"\nTotal: {len(all_rows)} exercises")

    conn = get_conn()
    with conn.cursor() as cur:
        # UPSERT (không TRUNCATE vì query_log/attempt có FK → cascade sẽ xoá log học viên).
        bulk_insert(
            cur, "public.exercise",
            ["exercise_id","theme","title","level","description_md"],
            all_rows,
            on_conflict=(
                "(exercise_id) DO UPDATE SET "
                "theme=EXCLUDED.theme, "
                "title=EXCLUDED.title, "
                "level=EXCLUDED.level, "
                "description_md=EXCLUDED.description_md"
            ),
            page_size=200,
        )
    conn.commit()
    conn.close()
    print("✅ Imported / updated.")


if __name__ == "__main__":
    main()
