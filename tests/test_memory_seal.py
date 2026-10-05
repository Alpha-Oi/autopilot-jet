"""Память проекта запечатана хешем (класс отказов F-06 стандарта DOA: отравление данных и памяти).

Память проекта (`CLAUDE.md` или `AGENTS.md`) каждый следующий прогон читает как указания, а править её может кто угодно
между прогонами: человек, другой инструмент, чужой текст, который кто-то туда скопировал. Хеш всего файла записывается
в `state.js` как `memorySeals[<имя файла>]` после того, как память прочитана и проверена (фаза 0) и после того, как её
дописала фаза 8, а `sync.py` сверяет файл с записью: при каждой синхронизации (строка `!`) и режимом `--memory-seal`,
который только читает и печатает хеш.

Чего здесь нет. Печать называет изменение, но не судит о тексте: правку пользователя от подложенной она не отличает,
и решает человек. Хеш лежит рядом с тем, что защищает, поэтому подделку вместе с печатью он не ловит. Что агент
проверяет память `injection_scan.py` до чтения, запечатывает после и останавливается на изменении, остаётся инструкцией.

Функции проверены на синтетических файлах: тест, который не умеет краснеть, ничего не доказывает.
"""

import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


SKILL = Path(__file__).parents[1] / "skills" / "autopilot-jet"
SCRIPT = SKILL / "tools" / "sync.py"
TEMPLATE = SKILL / "phases" / "dashboard-template.html"
SPEC = importlib.util.spec_from_file_location("autopilot_sync_memory_seal", SCRIPT)
sync = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync)

MEMORY = ("Правила команды: тесты перед коммитом.\n\n<!-- autopilot:start -->\n# bot\n\nКоманды: `python -m unittest`\n"
          "<!-- autopilot:end -->\n\nНе трогать каталог legacy/.\n")
NAME = "CLAUDE.md"


class Fixture(unittest.TestCase):
    """Проект во временном каталоге: `CLAUDE.md` в корне, `.autopilot/` рядом с ним."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="memory seal ")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(os.path.realpath(self.tmp.name))
        self.base = self.root / ".autopilot"
        self.base.mkdir()
        self.write_memory(MEMORY)

    def write_memory(self, text, name=NAME, newline=None):
        with open(self.root / name, "w", encoding="utf-8", newline=newline) as handle:
            handle.write(text)

    def state(self, **extra):
        state = {"dir": "2026-10-05-bot--wip", "memoryFile": NAME, "finishedAt": None,
                 "memorySeals": {NAME: sync.memory_digest(MEMORY)}}
        state.update(extra)
        return state

    def statuses(self, state):
        return {name: status for name, status, _digest in sync.memory_seal_report(state, str(self.base))}


class DigestTests(unittest.TestCase):
    def test_the_whole_file_is_sealed_inside_the_markers_and_around_them(self):
        base = sync.memory_digest(MEMORY)
        for edited in (MEMORY.replace("`python -m unittest`", "`curl x | sh`"),          # внутри блока навыка
                       MEMORY.replace("тесты перед коммитом", "ничего не проверять"),     # до блока
                       MEMORY.replace("legacy/", "src/"),                                   # после блока
                       MEMORY + "Новая строка.\n"):
            with self.subTest(edited=edited[-30:]):
                self.assertNotEqual(sync.memory_digest(edited), base)

    def test_one_character_is_enough(self):
        self.assertNotEqual(sync.memory_digest(MEMORY.replace("bot", "bog")), sync.memory_digest(MEMORY))

    def test_line_endings_bom_and_trailing_blank_lines_are_not_an_edit(self):
        base = sync.memory_digest(MEMORY)
        self.assertEqual(sync.memory_digest(MEMORY.replace("\n", "\r\n")), base)
        self.assertEqual(sync.memory_digest("﻿" + MEMORY), base)
        self.assertEqual(sync.memory_digest(MEMORY + "\n\n  \n"), base)

    def test_leading_whitespace_and_inner_blank_lines_are_an_edit(self):
        base = sync.memory_digest(MEMORY)
        self.assertNotEqual(sync.memory_digest("\n" + MEMORY), base)
        self.assertNotEqual(sync.memory_digest(MEMORY.replace("# bot\n\n", "# bot\n")), base)

    def test_an_invisible_character_is_an_edit(self):
        self.assertNotEqual(sync.memory_digest(MEMORY.replace("bot", "b​ot")), sync.memory_digest(MEMORY))

    def test_the_digest_is_a_sha256_hex(self):
        self.assertRegex(sync.memory_digest(MEMORY), r"^[0-9a-f]{64}$")

    def test_the_digest_is_not_the_digest_of_the_brief_rule(self):
        # у брифа в хеш входит только текст выше «## Дополнения»; у памяти — весь файл
        text = "правило\n\n## Дополнения\n\n- ещё\n"
        self.assertNotEqual(sync.memory_digest(text), sync.brief_digest(text))


class ReportTests(Fixture):
    def test_a_matching_seal_is_sealed(self):
        self.assertEqual(self.statuses(self.state()), {NAME: "sealed"})

    def test_an_edit_anywhere_in_the_file_is_changed_and_named(self):
        self.write_memory(MEMORY.replace("legacy/", "src/"))
        rows = sync.memory_seal_report(self.state(), str(self.base))
        self.assertEqual([(name, status) for name, status, _ in rows], [(NAME, "changed")])
        self.assertRegex(rows[0][2], r"^[0-9a-f]{64}$")

    def test_a_sealed_file_that_is_gone_is_named(self):
        (self.root / NAME).unlink()
        self.assertEqual(self.statuses(self.state()), {NAME: "missing"})

    def test_a_file_without_a_seal_is_unsealed_and_the_report_carries_its_digest(self):
        rows = sync.memory_seal_report(self.state(memorySeals={}), str(self.base))
        self.assertEqual(rows, [(NAME, "unsealed", sync.memory_digest(MEMORY))])

    def test_no_file_and_no_seal_is_pending_not_a_finding(self):
        (self.root / NAME).unlink()
        state = self.state(memorySeals={})
        self.assertEqual(self.statuses(state), {NAME: "pending"})
        self.assertEqual(sync.memory_findings(state, str(self.base)), [])

    def test_a_state_without_the_field_is_unsealed_not_a_crash(self):
        state = self.state()
        del state["memorySeals"]
        self.assertEqual(self.statuses(state), {NAME: "unsealed"})

    def test_a_record_without_a_memory_file_is_not_judged(self):
        self.assertEqual(sync.memory_seal_report({"dir": "x"}, str(self.base)), [])
        self.assertEqual(sync.memory_seal_report({"memoryFile": None, "memorySeals": None}, str(self.base)), [])

    def test_a_seal_that_names_a_path_is_not_followed(self):
        outside = self.root.parent / "outside-memory.md"
        outside.write_text("чужой файл", encoding="utf-8")
        self.addCleanup(outside.unlink)
        for name in ("../outside-memory.md", "sub/CLAUDE.md", "..", ".", "a\\b.md", ""):
            with self.subTest(name=name):
                rows = sync.memory_seal_report(self.state(memorySeals={name: "0" * 64}, memoryFile=None),
                                               str(self.base))
                self.assertEqual([status for _name, status, _digest in rows], ["badname"])

    def test_a_memory_file_name_with_a_path_in_the_record_is_not_followed(self):
        state = self.state(memorySeals={}, memoryFile="../outside-memory.md")
        self.assertEqual([status for _n, status, _d in sync.memory_seal_report(state, str(self.base))], ["badname"])

    def test_agents_md_is_sealed_the_same_way(self):
        self.write_memory(MEMORY, name="AGENTS.md")
        state = self.state(memoryFile="AGENTS.md", memorySeals={"AGENTS.md": sync.memory_digest(MEMORY)})
        self.assertEqual(self.statuses(state), {"AGENTS.md": "sealed"})
        self.write_memory(MEMORY + "x", name="AGENTS.md")
        self.assertEqual(self.statuses(state), {"AGENTS.md": "changed"})

    def test_the_file_is_looked_for_in_the_project_root_not_beside_state_js(self):
        (self.base / NAME).write_text("не то", encoding="utf-8")
        self.assertEqual(self.statuses(self.state()), {NAME: "sealed"})

    def test_a_directory_in_place_of_the_memory_file_is_unreadable_not_a_crash(self):
        (self.root / NAME).unlink()
        (self.root / NAME).mkdir()
        self.assertEqual(self.statuses(self.state()), {NAME: "unreadable"})

    def test_a_closed_run_with_a_changed_memory_is_still_named(self):
        # правка после закрытия прогона и есть сценарий: следующий прогон читает эту память
        self.write_memory(MEMORY + "x")
        findings = sync.memory_findings(self.state(finishedAt="2026-10-05T10:00:00+03:00"), str(self.base))
        self.assertEqual(len(findings), 1)

    def test_a_memory_that_was_never_sealed_is_not_a_finding(self):
        self.assertEqual(sync.memory_findings(self.state(memorySeals={}), str(self.base)), [])


class FindingTests(Fixture):
    def test_each_bad_status_is_a_finding_that_says_what_to_do(self):
        self.write_memory(MEMORY + "x")
        [changed] = sync.memory_findings(self.state(), str(self.base))
        self.assertIn(NAME, changed)
        self.assertIn("git diff", changed)
        self.assertIn("injection_scan.py", changed)
        (self.root / NAME).unlink()
        [gone] = sync.memory_findings(self.state(), str(self.base))
        self.assertIn("нет на месте", gone)

    def test_a_sealed_memory_has_no_findings(self):
        self.assertEqual(sync.memory_findings(self.state(), str(self.base)), [])

    def test_the_text_of_the_file_is_never_in_a_finding(self):
        self.write_memory("ПОДЛОЖЕННОЕ-УКАЗАНИЕ " + MEMORY)
        self.assertNotIn("ПОДЛОЖЕННОЕ-УКАЗАНИЕ", " ".join(sync.memory_findings(self.state(), str(self.base))))


class CliCase(Fixture):
    def write_state(self, state):
        (self.base / "state.js").write_text("window.STATE =\n" + json.dumps(state, indent=2) + "\n", encoding="utf-8")

    def snapshot(self):
        found = {}
        for path in sorted(self.root.rglob("*")):
            if path.is_file():
                found[str(path.relative_to(self.root))] = path.read_bytes()
        return found

    def run_cli(self, *args):
        return subprocess.run([sys.executable, "-X", "utf8", "-B", str(SCRIPT), *args], capture_output=True,
                              text=True, encoding="utf-8", timeout=60, check=False)

    def seal(self, state):
        self.write_state(state)
        result = self.run_cli("--memory-seal", str(self.base))
        return result.returncode, result.stdout


class CliTests(CliCase):
    def test_a_sealed_memory_exits_zero(self):
        code, out = self.seal(self.state())
        self.assertEqual(code, 0, out)
        self.assertTrue(out.startswith("sealed · " + NAME + " · " + sync.memory_digest(MEMORY)[:12]), out)

    def test_an_unsealed_memory_exits_one_and_prints_the_digest_to_record(self):
        code, out = self.seal(self.state(memorySeals={}))
        self.assertEqual(code, 1, out)
        self.assertIn("unsealed · " + NAME + " · sha256 " + sync.memory_digest(MEMORY), out)

    def test_the_printed_digest_is_the_one_that_then_seals(self):
        self.write_state(self.state(memorySeals={}))
        printed = self.run_cli("--memory-seal", str(self.base)).stdout.split("sha256 ")[1].strip()
        self.write_state(self.state(memorySeals={NAME: printed}))
        self.assertEqual(self.run_cli("--memory-seal", str(self.base)).returncode, 0)

    def test_a_changed_memory_exits_three(self):
        self.write_memory(MEMORY + "x")
        code, out = self.seal(self.state())
        self.assertEqual(code, 3, out)
        self.assertTrue(out.startswith("changed · " + NAME), out)

    def test_a_missing_memory_exits_three(self):
        (self.root / NAME).unlink()
        code, out = self.seal(self.state())
        self.assertEqual((code, out.split(" · ")[0]), (3, "missing"))

    def test_a_project_without_memory_yet_exits_zero_and_says_pending(self):
        (self.root / NAME).unlink()
        code, out = self.seal(self.state(memorySeals={}))
        self.assertEqual(code, 0, out)
        self.assertTrue(out.startswith("pending · " + NAME), out)

    def test_a_record_without_a_memory_file_is_none(self):
        code, out = self.seal({"dir": "x"})
        self.assertEqual(code, 0, out)
        self.assertTrue(out.startswith("none · "), out)

    def test_no_state_means_no_run_here(self):
        result = self.run_cli("--memory-seal", str(self.base))
        self.assertEqual(result.returncode, 0)
        self.assertTrue(result.stdout.startswith("none · state.js нет"), result.stdout)

    def test_a_broken_state_needs_a_human(self):
        (self.base / "state.js").write_text("window.STATE =\n{нет\n", encoding="utf-8")
        result = self.run_cli("--memory-seal", str(self.base))
        self.assertEqual(result.returncode, 3)
        self.assertTrue(result.stdout.startswith("unknown · "), result.stdout)

    def test_a_state_that_is_not_a_record_needs_a_human(self):
        (self.base / "state.js").write_text("window.STATE =\n[1, 2]\n", encoding="utf-8")
        self.assertEqual(self.run_cli("--memory-seal", str(self.base)).returncode, 3)

    def test_the_mode_writes_nothing(self):
        self.write_memory(MEMORY + "x")
        self.write_state(self.state(memorySeals={}))
        before = self.snapshot()
        self.run_cli("--memory-seal", str(self.base))
        self.assertEqual(self.snapshot(), before)

    def test_a_bad_call_exits_two(self):
        for args in (("--memory-seal", "a", "b"), ("--memory-seal", "--write")):
            with self.subTest(args=args):
                self.assertEqual(self.run_cli(*args).returncode, 2)


class SyncSurfacesTheFindingTests(CliCase):
    """Обычная синхронизация называет изменённую память строкой `!`, как называет остальные расхождения."""

    def test_a_changed_memory_is_named_in_the_sync_line(self):
        state = self.state()
        self.write_memory(MEMORY + "x")
        out = self.run_sync_here(state)
        self.assertTrue(any(line.startswith("  ! память проекта " + NAME + " изменена") for line in out.splitlines()), out)

    def run_sync_here(self, state):
        # настоящая раскладка: sync.py лежит в `.autopilot/`, память в корне проекта
        shutil.copy(SCRIPT, self.base / "sync.py")
        shutil.copy(TEMPLATE, self.base / "dashboard.html")
        self.write_state(state)
        result = subprocess.run([sys.executable, "-X", "utf8", "-B", str(self.base / "sync.py"), "--no-serve"],
                                capture_output=True, text=True, encoding="utf-8", timeout=60, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout

    def test_a_sealed_memory_keeps_the_sync_quiet(self):
        self.assertNotIn("  ! ", self.run_sync_here(self.state()))

    def test_a_memory_that_is_not_sealed_yet_keeps_the_sync_quiet(self):
        self.assertNotIn("  ! ", self.run_sync_here(self.state(memorySeals={})))

    def test_the_memory_finding_survives_the_cut_of_five(self):
        self.write_memory(MEMORY + "x")
        crowded = self.state(tickets=[{"id": str(n), "status": "in-progress"} for n in range(8)])
        lines = [line for line in self.run_sync_here(crowded).splitlines() if line.startswith("  ! ")]
        self.assertEqual(len(lines), 5)
        self.assertIn("память проекта " + NAME, lines[0])

    def test_the_sync_does_not_rewrite_the_seal_or_the_memory(self):
        self.write_memory(MEMORY + "x")
        state = self.state()
        before = (self.root / NAME).read_bytes()
        self.run_sync_here(state)
        self.assertEqual((self.root / NAME).read_bytes(), before)
        raw = (self.base / "state.js").read_text(encoding="utf-8")
        self.assertIn(sync.memory_digest(MEMORY), raw)


class DispatchTests(unittest.TestCase):
    def test_the_flag_does_not_fall_through_to_the_ordinary_sync(self):
        with mock.patch.object(sys, "argv", ["sync.py", "--memory-seal"]), \
                mock.patch.object(sync, "check_memory_seal", return_value=1) as check, \
                mock.patch.object(sync, "read_state", side_effect=AssertionError("ordinary sync ran")), \
                mock.patch.object(sync, "serve", side_effect=AssertionError("server touched")), \
                self.assertRaises(SystemExit) as raised:
            sync.main()
        self.assertEqual(raised.exception.code, 1)
        check.assert_called_once_with(sync.A)


class TheProcedureIsWritten(unittest.TestCase):
    def text(self, name):
        return (SKILL / "phases" / name).read_text(encoding="utf-8")

    def test_preflight_checks_the_memory_before_it_is_read(self):
        text = self.text("0-preflight.md")
        self.assertIn("--memory-seal", text)
        self.assertIn("before any file is read", text)
        self.assertLess(text.index("--memory-seal"), text.index("Read the project memory file first"))

    def test_preflight_runs_the_scan_on_a_changed_memory_and_stops_on_a_finding(self):
        text = self.text("0-preflight.md")
        self.assertIn("injection_scan.py", text[text.index("--memory-seal"):])
        self.assertIn("git diff", text)

    def test_preflight_seals_the_memory_after_it_is_read_and_scanned(self):
        text = self.text("0-preflight.md")
        self.assertIn("memorySeals", text)

    def test_the_final_phase_seals_the_memory_after_it_is_written(self):
        text = self.text("8-final.md")
        self.assertIn("--memory-seal", text)
        self.assertIn("memorySeals", text)

    def test_the_memory_phase_says_to_seal_what_it_wrote_and_where_the_hash_goes(self):
        text = self.text("9-memory.md")
        self.assertIn("**Seal what you wrote:**", text)
        self.assertIn("--memory-seal", text)
        self.assertIn("landing write", text)

    def test_the_state_templates_carry_the_field(self):
        self.assertIn('"memorySeals": {}', self.text("0-instruments.md"))

    def test_the_rule_says_a_seal_is_not_repaired_by_resealing(self):
        self.assertIn("re-sealing", self.text("0-preflight.md"))


if __name__ == "__main__":
    unittest.main()
