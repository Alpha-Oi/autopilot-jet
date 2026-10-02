"""Возраст копий навыка в прогоне (REQ-CORE-21 стандарта DOA: индекс старения, устаревшее состояние, замена).

В .autopilot/ лежат копии двух файлов навыка, sync.py и dashboard.html. Навык обновляют, копии остаются старыми:
проект, сохранивший старый dashboard.html, целый прогон показывал прежний логотип (замечено глазами 2026-09-29).
`sync.py --aging` сверяет копии с установленным навыком и называет устаревшие, индекс старения — доля копий, которые
не совпали. Режим только читает: это проверяется сравнением каталога до и после.

Замена устаревшей копии остаётся инструкцией (`phases/0-instruments.md`: копирование при каждом прогоне); код её
не выполняет, а проверяет результат: после копирования индекс должен быть нулевым.

Функции проверены на синтетических файлах: тест, который не умеет краснеть, ничего не доказывает.
"""

import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


TOOLS = Path(__file__).parents[1] / "skills" / "autopilot-jet" / "tools"
SCRIPT = TOOLS / "sync.py"
TEMPLATE = TOOLS.parent / "phases" / "dashboard-template.html"
SPEC = importlib.util.spec_from_file_location("autopilot_sync_aging", SCRIPT)
sync = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync)

PAGE = "<html><script>/*STATE-BEGIN*/window.STATE=%s;/*STATE-END*/</script><body>%s</body></html>\n"


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="aging ")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(os.path.realpath(self.tmp.name))
        self.skill = self.root / "skill"
        self.run_dir = self.root / "run"
        self.skill.mkdir()
        self.run_dir.mkdir()
        self.write(self.skill / "sync.py", "print('v2')\n")
        self.write(self.skill / "dashboard.html", PAGE % ("null", "logo v2"))
        self.sources = {"sync.py": str(self.skill / "sync.py"), "dashboard.html": str(self.skill / "dashboard.html")}

    @staticmethod
    def write(path, text, newline=None):
        with open(path, "w", encoding="utf-8", newline=newline) as handle:
            handle.write(text)

    def install_current(self):
        self.write(self.run_dir / "sync.py", "print('v2')\n")
        self.write(self.run_dir / "dashboard.html", PAGE % ("null", "logo v2"))

    def states(self):
        rows, index = sync.aging_report(str(self.run_dir), self.sources)
        return {name: state for name, state, _have, _want in rows}, index


class AgingIndexTests(Fixture):
    def test_current_copies_give_index_zero(self):
        self.install_current()
        self.assertEqual(self.states(), ({"sync.py": "current", "dashboard.html": "current"}, 0.0))

    def test_one_stale_copy_gives_half_and_names_the_copy(self):
        self.install_current()
        self.write(self.run_dir / "sync.py", "print('v1')\n")
        self.assertEqual(self.states(), ({"sync.py": "senescent", "dashboard.html": "current"}, 0.5))

    def test_both_stale_gives_one(self):
        self.write(self.run_dir / "sync.py", "print('v1')\n")
        self.write(self.run_dir / "dashboard.html", PAGE % ("null", "logo v1"))
        self.assertEqual(self.states()[1], 1.0)

    def test_a_missing_copy_counts_as_aged(self):
        self.install_current()
        (self.run_dir / "dashboard.html").unlink()
        self.assertEqual(self.states(), ({"sync.py": "current", "dashboard.html": "missing"}, 0.5))

    def test_the_state_snapshot_in_the_page_is_not_age(self):
        self.install_current()
        self.write(self.run_dir / "dashboard.html", PAGE % ('{"slug":"x","tickets":[1,2,3]}', "logo v2"))
        self.assertEqual(self.states()[1], 0.0)

    def test_a_change_outside_the_snapshot_is_age(self):
        self.install_current()
        self.write(self.run_dir / "dashboard.html", PAGE % ("null", "logo v1"))
        self.assertEqual(self.states(), ({"sync.py": "current", "dashboard.html": "senescent"}, 0.5))

    def test_line_endings_are_not_age(self):
        self.write(self.run_dir / "sync.py", "print('v2')\r\n", newline="")
        self.write(self.run_dir / "dashboard.html", (PAGE % ("null", "logo v2")).replace("\n", "\r\n"), newline="")
        self.assertEqual(self.states()[1], 0.0)

    def test_a_snapshot_without_markers_is_compared_whole(self):
        self.install_current()
        self.write(self.run_dir / "dashboard.html", "<html>logo v2</html>\n")
        self.assertEqual(self.states()[0]["dashboard.html"], "senescent")

    def test_the_report_carries_both_fingerprints(self):
        self.install_current()
        self.write(self.run_dir / "sync.py", "print('v1')\n")
        rows, _index = sync.aging_report(str(self.run_dir), self.sources)
        name, state, have, want = rows[0]
        self.assertEqual((name, state), ("sync.py", "senescent"))
        self.assertEqual(len(have), 64)
        self.assertNotEqual(have, want)


class CliCase(Fixture):
    """Настоящий sync.py навыка и настоящий шаблон страницы: источником служит сам установленный навык."""

    def install_real(self):
        self.write(self.run_dir / "sync.py", SCRIPT.read_text(encoding="utf-8"), newline="")
        self.write(self.run_dir / "dashboard.html", TEMPLATE.read_text(encoding="utf-8"), newline="")

    def run_cli(self, *args, script=SCRIPT):
        return subprocess.run([sys.executable, "-X", "utf8", "-B", str(script), *args], capture_output=True,
                              text=True, encoding="utf-8", timeout=60, check=False)

    def snapshot(self):
        return {path.name: path.read_bytes() for path in sorted(self.run_dir.iterdir())}


class AgingCliTests(CliCase):
    def test_fresh_copies_exit_zero(self):
        self.install_real()
        result = self.run_cli("--aging", str(self.run_dir))
        self.assertEqual((result.returncode, result.stdout.splitlines()[0]),
                         (0, "aging · индекс 0.00 · устарело 0 из 2"), result.stdout)

    def test_a_stale_copy_exits_one_and_is_named_with_short_fingerprints(self):
        self.install_real()
        with open(self.run_dir / "sync.py", "a", encoding="utf-8") as handle:
            handle.write("# старая копия\n")
        result = self.run_cli("--aging", str(self.run_dir))
        lines = result.stdout.splitlines()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(lines[0], "aging · индекс 0.50 · устарело 1 из 2")
        self.assertTrue(lines[1].startswith("  · sync.py: senescent (копия "), lines[1])
        self.assertEqual(len(lines), 2)

    def test_the_mode_writes_nothing(self):
        self.install_real()
        with open(self.run_dir / "sync.py", "a", encoding="utf-8") as handle:
            handle.write("# старая копия\n")
        (self.run_dir / "state.js").write_text("window.STATE =\n{}\n", encoding="utf-8")
        before = self.snapshot()
        self.run_cli("--aging", str(self.run_dir))
        self.assertEqual(self.snapshot(), before)

    def test_no_run_directory_is_not_old_age(self):
        result = self.run_cli("--aging", str(self.root / "no-such-run"))
        self.assertEqual((result.returncode, result.stdout.strip()), (0, "aging · индекс 0.00 · каталога прогона нет"))

    def test_a_bad_call_exits_two(self):
        for args in (("--aging", "a", "b"), ("--aging", "--write")):
            with self.subTest(args=args):
                self.assertEqual(self.run_cli(*args).returncode, 2)

    def test_running_the_copy_instead_of_the_skill_exits_three_and_does_not_sync(self):
        self.install_real()
        result = self.run_cli("--aging", str(self.run_dir), script=self.run_dir / "sync.py")
        self.assertEqual(result.returncode, 3)
        self.assertIn("не из каталога навыка", result.stdout)
        self.assertFalse((self.run_dir / "serve.pid").exists())

    def test_the_skills_own_copy_and_template_agree_with_themselves(self):
        sources = sync.skill_sources()
        self.assertIsNotNone(sources)
        self.assertEqual(sources["sync.py"], str(SCRIPT))
        self.assertTrue(Path(sources["dashboard.html"]).samefile(TEMPLATE))


class DispatchTests(unittest.TestCase):
    def test_the_flag_does_not_fall_through_to_the_ordinary_sync(self):
        with mock.patch.object(sys, "argv", ["sync.py", "--aging"]), \
                mock.patch.object(sync, "check_aging", return_value=1) as check, \
                mock.patch.object(sync, "read_state", side_effect=AssertionError("ordinary sync ran")), \
                mock.patch.object(sync, "serve", side_effect=AssertionError("server touched")), \
                self.assertRaises(SystemExit) as raised:
            sync.main()
        self.assertEqual(raised.exception.code, 1)
        check.assert_called_once_with(sync.A)


class ReplacementIsVerifiedTests(CliCase):
    """После копирования (инструкция phases/0-instruments.md) индекс должен стать нулевым: так видно тихий сбой cp."""

    def test_copying_the_skill_files_brings_the_index_to_zero(self):
        self.write(self.run_dir / "sync.py", "# старая копия\n")
        self.write(self.run_dir / "dashboard.html", PAGE % ('{"slug":"keep"}', "logo v1"))
        self.assertEqual(self.run_cli("--aging", str(self.run_dir)).returncode, 1)
        self.write(self.run_dir / "sync.py", SCRIPT.read_text(encoding="utf-8"), newline="")
        self.write(self.run_dir / "dashboard.html", TEMPLATE.read_text(encoding="utf-8"), newline="")
        self.assertEqual(self.run_cli("--aging", str(self.run_dir)).returncode, 0)

    def test_a_copy_that_silently_failed_is_still_named(self):
        self.install_real()
        self.write(self.run_dir / "sync.py", "# cp не отработал, лежит прежняя копия\n")
        result = self.run_cli("--aging", str(self.run_dir))
        self.assertEqual(result.returncode, 1)
        self.assertIn("sync.py: senescent", result.stdout)


if __name__ == "__main__":
    unittest.main()
