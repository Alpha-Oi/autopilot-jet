"""Память проекта не врёт о том, что можно проверить: число тестов и пути к файлам.

AGENTS.md и CLAUDE.md читаются каждым следующим прогоном как факты о проекте. Два раза число тестов
в них отставало от кода (оно правилось руками в #27 и #32), и устаревшая память выглядит так же
убедительно, как свежая. Эти проверки ловят расхождение в тот же момент, когда оно возникает, и CI
краснеет, пока память не обновлена (REQ-CORE-19 стандарта DOA: у памяти нет «молчаливого устаревания»).

Проверяется только то, что проверяется машиной: число тестов в строке «Актуально на development» и
существование путей репозитория, названных в обратных кавычках. Остальные утверждения памяти
(сроки, версии окружения, результаты ручных проверок) здесь не проверяются.

Функции проверки проверены на синтетическом тексте: тест, который не умеет краснеть, ничего не доказывает.
"""

import os
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).parents[1]
TESTS = Path(__file__).parent
MEMORY_FILES = ("AGENTS.md", "CLAUDE.md")
CURRENT_LINE = re.compile(r"Актуально на `development`[^\n]*?(\d+) tests?/`OK`")
REPO_PATH = re.compile(r"(?:skills|tools|tests|docs|\.github|assets)/[\w./-]+")


def declared_test_count(text):
    """Число тестов из строки «Актуально на `development` …: N tests/`OK`»; None, если строки нет."""
    match = CURRENT_LINE.search(text)
    return int(match.group(1)) if match else None


def actual_test_count():
    suite = unittest.defaultTestLoader.discover(str(TESTS), top_level_dir=str(TESTS))
    return suite.countTestCases()


def missing_paths(text, root):
    """Пути репозитория из обратных кавычек, которых нет на диске (шаблоны со `*` пропускаются)."""
    missing = []
    for token in sorted(set(re.findall(r"`([^`\n]+)`", text))):
        if REPO_PATH.fullmatch(token) and "*" not in token and not os.path.exists(os.path.join(root, token)):
            missing.append(token)
    return missing


class CheckersCanTurnRed(unittest.TestCase):
    def test_declared_count_is_read_from_the_current_line_only(self):
        text = (
            "- Локальный release gate: 33 tests/`OK` за 9.5s\n"
            "- Актуально на `development` после PR #30 (2026-10-01): 88 tests/`OK` (41 прежний), flake8 `0`\n"
        )
        self.assertEqual(declared_test_count(text), 88)

    def test_missing_current_line_is_reported_as_none(self):
        self.assertIsNone(declared_test_count("- 33 tests/`OK` без пометки актуальности\n"))

    def test_missing_paths_are_found(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "docs").mkdir()
            (Path(tmp) / "docs" / "there.md").write_text("x", encoding="utf-8")
            text = "см. `docs/there.md`, `docs/gone.md`, `skills/*/x.md`, `не/путь`, `.autopilot/state.js`"
            self.assertEqual(missing_paths(text, tmp), ["docs/gone.md"])


class MemoryIsFresh(unittest.TestCase):
    def test_declared_test_count_matches_the_suite(self):
        text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        declared = declared_test_count(text)
        self.assertIsNotNone(declared, "в AGENTS.md нет строки «Актуально на `development` … N tests/`OK`»")
        self.assertEqual(
            declared, actual_test_count(),
            "число тестов в AGENTS.md устарело: обнови строку «Актуально на `development`»")

    def test_paths_named_in_memory_files_exist(self):
        for name in MEMORY_FILES:
            with self.subTest(file=name):
                text = (ROOT / name).read_text(encoding="utf-8")
                self.assertEqual(missing_paths(text, ROOT), [])


if __name__ == "__main__":
    unittest.main()
