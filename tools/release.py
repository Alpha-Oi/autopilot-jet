#!/usr/bin/env python3
"""Версия и описание релиза из CHANGELOG.md.

Используется `.github/workflows/release.yml`: после слияния в `main` workflow спрашивает здесь, какая версия
записана в журнале последней, и берёт текст её раздела как описание релиза. Только стандартная библиотека,
ничего не пишет и никуда не ходит.

    python tools/release.py version [CHANGELOG.md]   -> X.Y.Z последнего выпущенного раздела
    python tools/release.py notes   [CHANGELOG.md]   -> текст этого раздела

Раздел `## [Unreleased]` пропускается. Заголовок разбирается строго: `## [X.Y.Z]`, дальше по желанию ` — ГГГГ-ММ-ДД`;
всё остальное (предрелизы, опечатки) не считается версией. Код выхода 0 — готово, 1 — версии или описания нет
(workflow при этом падает, а не выпускает пустое), 2 — ошибка вызова.
"""

import re
import sys
from pathlib import Path

HEADING = re.compile(r"^## \[(\d+\.\d+\.\d+)\](?:\s+—\s+\d{4}-\d{2}-\d{2})?\s*$")
ANY_HEADING = re.compile(r"^## \[")
LIMIT = 120000   # GitHub принимает описание релиза до 125000 знаков


def latest_section(text):
    """(версия, описание) последнего выпущенного раздела или (None, причина)."""
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if HEADING.match(line)), None)
    if start is None:
        return None, "в журнале нет раздела вида «## [X.Y.Z]»"
    end = next((i for i in range(start + 1, len(lines)) if ANY_HEADING.match(lines[i])), len(lines))
    body = "\n".join(lines[start + 1:end]).strip()
    if not body:
        return None, "раздел %s пуст" % HEADING.match(lines[start]).group(1)
    if len(body) > LIMIT:
        return None, "описание раздела %s длиннее %d знаков" % (HEADING.match(lines[start]).group(1), LIMIT)
    return HEADING.match(lines[start]).group(1), body


def main(argv):
    if not argv or argv[0] not in ("version", "notes") or len(argv) > 2:
        print("использование: release.py version|notes [CHANGELOG.md]", file=sys.stderr)
        return 2
    path = Path(argv[1]) if len(argv) == 2 else Path(__file__).resolve().parents[1] / "CHANGELOG.md"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        print("журнал не прочитан: %s" % (e.strerror or "ошибка"), file=sys.stderr)
        return 1
    version, body = latest_section(text)
    if version is None:
        print(body, file=sys.stderr)
        return 1
    print(version if argv[0] == "version" else body)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
