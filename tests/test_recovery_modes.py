"""Пути восстановления названы, различаются и проверяются (REQ-CORE-20 стандарта DOA: таксономия восстановления).

`phases/5-repair.md` (раздел «Recovery modes») держит таблицу из пяти путей: возобновление из файлов, правка в том
же контексте, пересборка в свежем контексте, откат всего раунда, пересоздание дашборда из шаблона. Для каждого в
строке записано, когда он применим, что ему нельзя и чем он проверяется. Здесь проверяется то, что проверяется
машиной:
  - таблица цела: пять строк, имена разные, ни одной пустой ячейки;
  - всё, на что строки ссылаются, существует: файлы фаз, режимы `sync.py` (они подключены в `main`) и потолки счётчиков;
  - режимы `sync.py` из таблицы действительно только читают: запуск на пустом каталоге ничего в нём не создаёт и
    не заканчивается ошибкой вызова;
  - правило «испорченное состояние не клонируют» записано.

Чего здесь нет: что агент выбирает путь по строке таблицы, а не по привычке, остаётся инструкцией. Таблица не
проверяет, что восстановление удалось, и не заменяет репетиции откатов (`tests/test_rollback_plan.py`,
`tests/test_resume_rehearsal.py`). Откат отдельного таска и `ship.ps1` не покрыты.

Проверка проверена нарочными поломками: тест, который не умеет краснеть, ничего не доказывает.
"""

import importlib.util
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).parents[1]
SKILL = ROOT / "skills" / "autopilot-jet"
REPAIR = SKILL / "phases" / "5-repair.md"
SYNC = SKILL / "tools" / "sync.py"
SPEC = importlib.util.spec_from_file_location("sync_for_recovery", SYNC)
sync = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync)

MODES = ["Resume from files", "Repair in the same context", "Rebuild in a fresh context", "Whole-round rollback",
         "Dashboard regenerated from the template"]


def table():
    """Строки таблицы `Recovery modes` как списки ячеек (без заголовка и разделителя)."""
    text = REPAIR.read_text(encoding="utf-8")
    section = text[text.index("## Recovery modes"):]
    rows = [line for line in section.splitlines() if line.startswith("|")]
    cells = [[cell.strip() for cell in row.strip().strip("|").split("|")] for row in rows]
    return cells[0], cells[2:]


class TableShapeTests(unittest.TestCase):
    def setUp(self):
        self.header, self.rows = table()

    def test_the_columns_are_mode_when_may_not_checked_by(self):
        self.assertEqual(self.header, ["Mode", "When", "May not", "Checked by"])

    def test_five_rows_with_the_five_named_modes_in_order(self):
        self.assertEqual([row[0] for row in self.rows], MODES)

    def test_no_empty_cell_and_no_two_rows_alike(self):
        for row in self.rows:
            with self.subTest(row=row[0]):
                self.assertEqual(len(row), 4)
                self.assertTrue(all(len(cell) > 8 for cell in row), row)
        for column in range(4):
            cells = [row[column] for row in self.rows]
            self.assertEqual(len(set(cells)), len(cells), "column %d repeats" % column)

    def test_the_rule_against_cloning_a_corrupted_state_is_written(self):
        text = REPAIR.read_text(encoding="utf-8")
        self.assertIn("Corrupted state is never cloned forward", text)

    def test_a_fresh_context_gets_files_not_the_transcript(self):
        row = [row for row in self.rows if row[0] == "Rebuild in a fresh context"][0]
        self.assertIn("the files on disk and the handoff, not the transcript", row[2])

    def test_a_rollback_is_never_a_hard_reset(self):
        row = [row for row in self.rows if row[0] == "Whole-round rollback"][0]
        self.assertIn("`git reset --hard`", row[2])


class ReferencesExistTests(unittest.TestCase):
    def setUp(self):
        _, self.rows = table()
        self.text = "\n".join(" ".join(row) for row in self.rows)

    def test_every_phase_file_it_names_exists(self):
        paths = re.findall(r"`(phases/[\w\-.]+\.md)`", self.text)
        self.assertGreaterEqual(len(paths), 4)
        for path in paths:
            with self.subTest(path=path):
                self.assertTrue((SKILL / path).is_file())

    def test_every_sync_flag_it_names_is_wired_in_main(self):
        flags = re.findall(r"`sync\.py (--[\w\-]+)`", self.text)
        self.assertEqual(sorted(set(flags)), ["--aging", "--other-window", "--rollback-plan", "--run-status"])
        for flag in flags:
            with self.subTest(flag=flag):
                self.assertIn(flag, [name for name, _mode in sync.MODES])

    def test_the_audit_ceilings_it_names_are_real(self):
        for counter in ("repairs", "retries", "handoffs"):
            with self.subTest(counter=counter):
                self.assertIn(counter, self.text)
                self.assertIn(counter, sync.COUNTERS)
        self.assertEqual(sync.COUNTER_CEILING, 2)
        self.assertIn("two `repairs`", self.text)


class ModesOnlyReadTests(unittest.TestCase):
    def run_mode(self, flag):
        with tempfile.TemporaryDirectory(prefix="recovery ") as tmp:
            directory = Path(os.path.realpath(tmp))
            result = subprocess.run([sys.executable, "-X", "utf8", "-B", str(SYNC), flag, str(directory)],
                                    capture_output=True, text=True, encoding="utf-8", timeout=60, check=False)
            return result.returncode, sorted(os.listdir(directory))

    def test_each_mode_creates_nothing_and_is_not_a_call_error(self):
        for flag in ("--run-status", "--other-window", "--rollback-plan", "--aging"):
            with self.subTest(flag=flag):
                code, left = self.run_mode(flag)
                self.assertNotEqual(code, 2)
                self.assertEqual(left, [])


if __name__ == "__main__":
    unittest.main()
