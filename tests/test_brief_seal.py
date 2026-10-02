"""Бриф запечатан хешем (REQ-CORE-03 и REQ-CORE-09 стандарта DOA: желаемое состояние под защитой целостности).

Бриф — желаемое состояние прогона: слова пользователя, с которыми сверяется готовый результат. Текст выше
«## Дополнения» не редактируется (`phases/1-manifest.md` §2), а ниже заголовка файл растёт. Поэтому в `state.js`
записывается хеш верхней части, `briefSeals[<имя файла>]`, и `sync.py` сверяет файл с записью: при каждой
синхронизации (строка `!`) и режимом `--brief-seal`, который только читает и печатает хеш.

Чего здесь нет. Агент, который перепишет и бриф, и печать, подменит бриф незаметно: хеш лежит рядом с тем, что
защищает, и ловит случайную правку и правку чужим контекстом, а не подделку. Дополнения ниже заголовка и
манифест хешем не закрыты: статусы строк манифеста меняются законно. Что агент запечатывает бриф и перезаписывает
печать только после слова пользователя, остаётся инструкцией.

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
SPEC = importlib.util.spec_from_file_location("autopilot_sync_brief_seal", SCRIPT)
sync = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync)

BRIEF = ("# Изначальная задача\n\n> Записано 2026-10-02.\n\nтелеграм-бот для заявок на ремонт\n"
         "и складывать их в таблицу\n\n## Дополнения\n\n- 2026-10-02 — «SMS не надо»\n")
NAME = "2026-10-02-brief.md"


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="brief seal ")
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(os.path.realpath(self.tmp.name))
        self.run_dir = self.base / "2026-10-02-bot--wip"
        self.run_dir.mkdir()
        self.write_brief(BRIEF)

    def write_brief(self, text, name=NAME, newline=None):
        with open(self.run_dir / name, "w", encoding="utf-8", newline=newline) as handle:
            handle.write(text)

    def state(self, **extra):
        state = {"dir": self.run_dir.name, "briefFile": NAME, "finishedAt": None,
                 "briefSeals": {NAME: sync.brief_digest(BRIEF)}}
        state.update(extra)
        return state

    def statuses(self, state):
        return {name: status for name, status, _digest in sync.brief_seal_report(state, str(self.base))}


class DigestTests(unittest.TestCase):
    def test_additions_below_the_heading_are_not_part_of_the_seal(self):
        grown = BRIEF + "- 2026-10-03 — «и чтобы заявку можно было отменить»\n"
        self.assertEqual(sync.brief_digest(grown), sync.brief_digest(BRIEF))

    def test_an_edit_of_the_original_text_changes_the_digest(self):
        self.assertNotEqual(sync.brief_digest(BRIEF.replace("ремонт", "ремонта")), sync.brief_digest(BRIEF))
        self.assertNotEqual(sync.brief_digest(BRIEF.replace("и складывать", "складывать")), sync.brief_digest(BRIEF))

    def test_one_character_is_enough(self):
        self.assertNotEqual(sync.brief_digest(BRIEF + ""), sync.brief_digest(BRIEF.replace("бот", "бог")))

    def test_line_endings_bom_and_trailing_blank_lines_are_not_an_edit(self):
        self.assertEqual(sync.brief_digest(BRIEF.replace("\n", "\r\n")), sync.brief_digest(BRIEF))
        self.assertEqual(sync.brief_digest("﻿" + BRIEF), sync.brief_digest(BRIEF))
        self.assertEqual(sync.brief_digest(BRIEF.replace("\n\n## Дополнения", "\n\n\n\n## Дополнения")),
                         sync.brief_digest(BRIEF))

    def test_a_merged_addition_is_an_edit(self):
        # «Дополнение» дописали в текст выше заголовка, а не под ним: правило «не вливать в текст выше» нарушено
        merged = BRIEF.replace("\n\n## Дополнения", "\nи SMS убрать\n\n## Дополнения")
        self.assertNotEqual(sync.brief_digest(merged), sync.brief_digest(BRIEF))

    def test_moving_the_heading_is_an_edit(self):
        up = BRIEF.replace("и складывать их в таблицу\n", "").replace("\n## Дополнения", "\n## Дополнения\nи складывать")
        down = BRIEF.replace("## Дополнения\n", "").rstrip() + "\n\n## Дополнения\n"
        self.assertNotEqual(sync.brief_digest(up), sync.brief_digest(BRIEF))
        self.assertNotEqual(sync.brief_digest(down), sync.brief_digest(BRIEF))

    def test_a_brief_without_the_heading_is_sealed_whole(self):
        plain = "сделай бота\n"
        self.assertEqual(sync.brief_original(plain), "сделай бота")
        self.assertNotEqual(sync.brief_digest(plain + "и ещё\n"), sync.brief_digest(plain))

    def test_only_the_heading_alone_on_its_line_splits(self):
        text = "задача про ## Дополнения в тексте\n\n## Дополнения ниже\n\nхвост\n"
        self.assertEqual(sync.brief_original(text), text.rstrip())

    def test_the_digest_is_a_sha256_hex(self):
        self.assertEqual(len(sync.brief_digest(BRIEF)), 64)
        self.assertTrue(all(c in "0123456789abcdef" for c in sync.brief_digest(BRIEF)))


class ReportTests(Fixture):
    def test_a_matching_seal_is_sealed(self):
        self.assertEqual(self.statuses(self.state()), {NAME: "sealed"})
        self.assertEqual(sync.seal_findings(self.state(), str(self.base)), [])

    def test_appending_an_addition_keeps_the_seal(self):
        self.write_brief(BRIEF + "- 2026-10-03 — «отмена в течение часа»\n")
        self.assertEqual(self.statuses(self.state()), {NAME: "sealed"})

    def test_an_edited_original_is_changed_and_named(self):
        self.write_brief(BRIEF.replace("ремонт", "ремонта"))
        self.assertEqual(self.statuses(self.state()), {NAME: "changed"})
        findings = sync.seal_findings(self.state(), str(self.base))
        self.assertEqual(len(findings), 1)
        self.assertIn(NAME, findings[0])
        self.assertIn("изменён", findings[0])

    def test_a_missing_sealed_brief_is_named(self):
        (self.run_dir / NAME).unlink()
        self.assertEqual(self.statuses(self.state()), {NAME: "missing"})
        self.assertIn("нет на месте", sync.seal_findings(self.state(), str(self.base))[0])

    def test_a_brief_without_a_seal_is_unsealed_and_the_report_carries_its_digest(self):
        state = self.state(briefSeals={})
        report = sync.brief_seal_report(state, str(self.base))
        self.assertEqual([(name, status) for name, status, _ in report], [(NAME, "unsealed")])
        self.assertEqual(report[0][2], sync.brief_digest(BRIEF))
        self.assertIn("не запечатан", sync.seal_findings(state, str(self.base))[0])

    def test_a_state_without_the_field_is_unsealed_not_a_crash(self):
        state = self.state()
        del state["briefSeals"]
        self.assertEqual(self.statuses(state), {NAME: "unsealed"})
        state["briefSeals"] = "x"
        self.assertEqual(self.statuses(state), {NAME: "unsealed"})

    def test_a_closed_run_is_not_nagged_to_seal(self):
        state = self.state(briefSeals={}, finishedAt="2026-10-02T12:00:00+00:00")
        self.assertEqual(sync.seal_findings(state, str(self.base)), [])

    def test_a_closed_run_with_a_changed_brief_is_still_named(self):
        self.write_brief(BRIEF.replace("ремонт", "ремонта"))
        state = self.state(finishedAt="2026-10-02T12:00:00+00:00")
        self.assertEqual(len(sync.seal_findings(state, str(self.base))), 1)

    def test_every_brief_of_a_run_is_checked(self):
        second = "2026-11-01-brief.md"
        self.write_brief("# Изначальная задача\n\nещё одно\n\n## Дополнения\n", name=second)
        seals = {NAME: sync.brief_digest(BRIEF), second: sync.brief_digest("# Изначальная задача\n\nещё одно\n")}
        self.assertEqual(self.statuses(self.state(briefSeals=seals)), {NAME: "sealed", second: "sealed"})
        self.write_brief("# Изначальная задача\n\nдругое\n\n## Дополнения\n", name=second)
        self.assertEqual(self.statuses(self.state(briefSeals=seals)), {NAME: "sealed", second: "changed"})

    def test_a_seal_that_names_a_path_is_not_followed(self):
        outside = self.base / "outside.md"
        outside.write_text("секрет\n", encoding="utf-8")
        for name in ("../outside.md", "sub/x.md", "..", "a\\b.md", ""):
            with self.subTest(name=name):
                self.assertEqual(self.statuses(self.state(briefFile=None, briefSeals={name: "0" * 64})), {name: "badname"})
        self.assertEqual(self.statuses(self.state(briefFile="../outside.md", briefSeals={})), {"../outside.md": "badname"})

    def test_a_record_without_a_directory_is_not_judged(self):
        self.assertEqual(sync.brief_seal_report({"briefFile": NAME}, str(self.base)), [])
        self.assertEqual(sync.brief_seal_report({"dir": "../x", "briefFile": NAME}, str(self.base)), [])

    def test_a_directory_in_place_of_the_brief_is_unreadable_not_a_crash(self):
        (self.run_dir / NAME).unlink()
        (self.run_dir / NAME).mkdir()
        self.assertEqual(self.statuses(self.state()), {NAME: "unreadable"})


class CliCase(Fixture):
    def write_state(self, state):
        (self.base / "state.js").write_text("window.STATE =\n" + json.dumps(state, indent=2) + "\n", encoding="utf-8")

    def snapshot(self):
        found = {}
        for path in sorted(self.base.rglob("*")):
            if path.is_file():
                found[str(path.relative_to(self.base))] = path.read_bytes()
        return found

    def run_cli(self, *args):
        return subprocess.run([sys.executable, "-X", "utf8", "-B", str(SCRIPT), *args], capture_output=True,
                              text=True, encoding="utf-8", timeout=60, check=False)

    def seal(self, state):
        self.write_state(state)
        result = self.run_cli("--brief-seal", str(self.base))
        return result.returncode, result.stdout


class CliTests(CliCase):
    def test_a_sealed_brief_exits_zero(self):
        code, out = self.seal(self.state())
        self.assertEqual(code, 0, out)
        self.assertTrue(out.startswith("sealed · " + NAME), out)

    def test_an_unsealed_brief_exits_one_and_prints_the_digest_to_record(self):
        code, out = self.seal(self.state(briefSeals={}))
        self.assertEqual(code, 1, out)
        self.assertIn(sync.brief_digest(BRIEF), out)
        self.assertTrue(out.startswith("unsealed · " + NAME), out)

    def test_a_changed_brief_exits_three(self):
        self.write_brief(BRIEF.replace("ремонт", "ремонта"))
        code, out = self.seal(self.state())
        self.assertEqual(code, 3, out)
        self.assertTrue(out.startswith("changed · " + NAME), out)

    def test_a_missing_brief_exits_three(self):
        (self.run_dir / NAME).unlink()
        self.assertEqual(self.seal(self.state())[0], 3)

    def test_the_worse_verdict_wins_over_the_better(self):
        second = "2026-11-01-brief.md"
        self.write_brief("# Изначальная задача\n\nещё\n", name=second)
        self.write_brief(BRIEF.replace("ремонт", "ремонта"))
        code, out = self.seal(self.state(briefFile=second))
        self.assertEqual(code, 3, out)
        self.assertIn("unsealed · " + second, out)

    def test_no_state_means_no_run_here(self):
        result = self.run_cli("--brief-seal", str(self.base))
        self.assertEqual((result.returncode, result.stdout.split(" · ")[0]), (0, "none"))

    def test_a_record_without_a_brief_is_none(self):
        self.write_state({"slug": "x"})
        result = self.run_cli("--brief-seal", str(self.base))
        self.assertEqual((result.returncode, result.stdout.split(" · ")[0]), (0, "none"))

    def test_a_broken_state_needs_a_human(self):
        (self.base / "state.js").write_text("window.STATE =\n{ не json\n", encoding="utf-8")
        result = self.run_cli("--brief-seal", str(self.base))
        self.assertEqual((result.returncode, result.stdout.split(" · ")[0]), (3, "unknown"))

    def test_a_state_that_is_not_a_record_needs_a_human(self):
        (self.base / "state.js").write_text("window.STATE =\n[1, 2]\n", encoding="utf-8")
        self.assertEqual(self.run_cli("--brief-seal", str(self.base)).returncode, 3)

    def test_the_mode_writes_nothing(self):
        self.write_brief(BRIEF.replace("ремонт", "ремонта"))
        self.write_state(self.state(briefSeals={}))
        before = self.snapshot()
        self.run_cli("--brief-seal", str(self.base))
        self.assertEqual(self.snapshot(), before)

    def test_a_bad_call_exits_two(self):
        for args in (("--brief-seal", "a", "b"), ("--brief-seal", "--write")):
            with self.subTest(args=args):
                self.assertEqual(self.run_cli(*args).returncode, 2)


class SyncSurfacesTheFindingTests(CliCase):
    """Обычная синхронизация называет изменённый бриф строкой `!`, как называет остальные расхождения."""

    def sync_output(self, state):
        runtime = self.base / "runtime"
        runtime.mkdir()
        shutil.copy(SCRIPT, runtime / "sync.py")
        shutil.copy(TEMPLATE, runtime / "dashboard.html")
        (runtime / "state.js").write_text("window.STATE =\n" + json.dumps(state, indent=2) + "\n", encoding="utf-8")
        shutil.copytree(self.run_dir, runtime / self.run_dir.name)
        result = subprocess.run([sys.executable, "-X", "utf8", "-B", str(runtime / "sync.py"), "--no-serve"],
                                capture_output=True, text=True, encoding="utf-8", timeout=60, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout

    def test_a_changed_brief_is_named_in_the_sync_line(self):
        self.write_brief(BRIEF.replace("ремонт", "ремонта"))
        out = self.sync_output(self.state())
        self.assertTrue(any(line.startswith("  ! бриф " + NAME + " изменён") for line in out.splitlines()), out)

    def test_a_sealed_brief_keeps_the_sync_quiet(self):
        out = self.sync_output(self.state())
        self.assertNotIn("  ! ", out)

    def test_the_seal_comes_before_the_older_findings_and_survives_the_cut_of_five(self):
        self.write_brief(BRIEF.replace("ремонт", "ремонта"))
        crowded = self.state(tickets=[{"id": str(n), "status": "in-progress"} for n in range(8)])
        lines = [line for line in self.sync_output(crowded).splitlines() if line.startswith("  ! ")]
        self.assertEqual(len(lines), 5)
        self.assertIn("бриф " + NAME, lines[0])


class DispatchTests(unittest.TestCase):
    def test_the_flag_does_not_fall_through_to_the_ordinary_sync(self):
        with mock.patch.object(sys, "argv", ["sync.py", "--brief-seal"]), \
                mock.patch.object(sync, "check_brief_seal", return_value=1) as check, \
                mock.patch.object(sync, "read_state", side_effect=AssertionError("ordinary sync ran")), \
                mock.patch.object(sync, "serve", side_effect=AssertionError("server touched")), \
                self.assertRaises(SystemExit) as raised:
            sync.main()
        self.assertEqual(raised.exception.code, 1)
        check.assert_called_once_with(sync.A)


class TheProcedureIsWritten(unittest.TestCase):
    def test_phase_one_tells_the_orchestrator_to_seal_after_the_redaction_check(self):
        text = (SKILL / "phases" / "1-manifest.md").read_text(encoding="utf-8")
        self.assertIn("--brief-seal", text)
        self.assertIn("briefSeals", text)

    def test_the_state_template_carries_the_field(self):
        text = (SKILL / "phases" / "0-instruments.md").read_text(encoding="utf-8")
        self.assertIn('"briefSeals": {}', text)

    def test_preflight_runs_the_check_before_resuming(self):
        self.assertIn("--brief-seal", (SKILL / "phases" / "0-preflight.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
