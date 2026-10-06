"""Форма записи, которую страница не может прочесть (находки третьего пробного прогона, 2026-10-06).

Настоящий `state.js` того прогона лежит в `tests/data/pilot3_state.json` (Windows, T0, один заход: проект «Консольные итоги
расходов»). Три расхождения между тем, что записал агент, и тем, что читает страница:
  1. Шесть этапов (briefing … final) закрыты как `done` с `finishedAt`, но без `startedAt`: страница писала «не начат» рядом
     с зелёной точкой и считала «8 из 8 этапов пройдено».
  2. Итог слепой приёмки записан как `{verdict, drift}`, а страница читает `{matched, checked, mismatches}`: вышло
     «/ требований подтверждено» без чисел и «Расхождений нет».
  3. `tests` записан строкой («12 passed»), а плитка читала `tests.passed`: плитка осталась пустой.
Что сделано: `sync.py` (`audit_shapes`) называет первые две формы, форма `blind` записана в `phases/7-instruments.md`, правило про
этапы в `phases/8-final.md`; страница не утверждает того, чего нет в записи (прочерк вместо «не начат» у пройденного этапа,
без чисел нет «N / M», без списка нет «Расхождений нет»), а плитка тестов читает и строку. Строка в `tests` допустима
(старые записи), поэтому audit про неё молчит.

Чего тут нет: что агент в следующем прогоне пишет эти поля верно. Это инструкция для модели; тест видит только то, что
записано, и называет отклонение.

Проверка проверена нарочными поломками: тест, который не умеет краснеть, ничего не доказывает.
"""

import copy
import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).parents[1]
SYNC = ROOT / "skills" / "autopilot-jet" / "tools" / "sync.py"
SKILL = ROOT / "skills" / "autopilot-jet"
SPEC = importlib.util.spec_from_file_location("autopilot_sync_shapes", SYNC)
sync = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync)

PILOT = json.loads((ROOT / "tests" / "data" / "pilot3_state.json").read_text(encoding="utf-8"))


def mine(state):
    return sync.audit_shapes(state)


def fixed_pilot():
    state = copy.deepcopy(PILOT)
    for stage in state["stages"]:
        stage.setdefault("startedAt", "2026-10-06T15:38:00+03:00")
    state["blind"] = {"matched": 5, "checked": 5, "mismatches": []}
    return state


class ThePilotRecord(unittest.TestCase):
    def test_the_fixture_is_the_real_record(self):
        self.assertEqual(PILOT["slug"], "expense-summary-cli")
        self.assertEqual(PILOT["tier"], "T0")
        self.assertEqual(sorted(s["id"] for s in PILOT["stages"] if "startedAt" not in s),
                         ["briefing", "build", "final", "plan", "review", "spec"])
        self.assertEqual(sorted(PILOT["blind"]), ["drift", "verdict"])
        self.assertIsInstance(PILOT["tests"], str)

    def test_audit_names_the_unopened_stages_and_the_blind_without_numbers(self):
        findings = mine(PILOT)
        self.assertEqual(len(findings), 2, findings)
        self.assertIn("briefing, spec, plan, build, review, final", findings[0])
        self.assertIn("без startedAt", findings[0])
        self.assertIn("matched, checked", findings[1])

    def test_ordinary_audit_carries_them_too(self):
        lines = sync.audit(PILOT)
        self.assertTrue(any("без startedAt" in line for line in lines), lines)
        self.assertTrue(any("blind без чисел" in line for line in lines), lines)

    def test_a_string_in_tests_is_not_a_finding(self):
        self.assertFalse(any("tests" in line for line in mine(PILOT)))

    def test_the_corrected_record_is_silent(self):
        self.assertEqual(mine(fixed_pilot()), [])

    def test_the_audit_never_changes_the_record(self):
        before = copy.deepcopy(PILOT)
        sync.audit(PILOT)
        self.assertEqual(PILOT, before)


class StagesOfTheShape(unittest.TestCase):
    def stages(self, *items):
        return {"stages": list(items)}

    def test_done_with_finish_and_no_start_is_named_once_for_all(self):
        state = self.stages({"id": "a", "status": "done", "finishedAt": "t"},
                            {"id": "b", "status": "done", "finishedAt": "t"})
        findings = mine(state)
        self.assertEqual(len(findings), 1)
        self.assertIn("a, b", findings[0])

    def test_other_stages_are_silent(self):
        for item in ({"id": "a", "status": "done", "startedAt": "s", "finishedAt": "f"},
                     {"id": "a", "status": "skipped", "finishedAt": "f"},
                     {"id": "a", "status": "pending"},
                     {"id": "a", "status": "active", "startedAt": "s"},
                     {"id": "a", "status": "done"},          # без finishedAt его называет audit() отдельной строкой
                     {"id": "a", "status": "failed", "finishedAt": "f"}):
            with self.subTest(item=item):
                self.assertEqual(mine(self.stages(item)), [])

    def test_missing_or_broken_stages_are_safe(self):
        for state in ({}, {"stages": None}, {"stages": "x"}, {"stages": [None, "x", 3]}):
            with self.subTest(state=state):
                self.assertEqual(mine(state), [])


class BlindOfTheShape(unittest.TestCase):
    def test_no_blind_yet_is_silent(self):
        self.assertEqual(mine({"blind": None}), [])
        self.assertEqual(mine({}), [])

    def test_the_right_shape_is_silent(self):
        self.assertEqual(mine({"blind": {"matched": 5, "checked": 5, "mismatches": []}}), [])
        self.assertEqual(mine({"blind": {"matched": 4, "checked": 5, "mismatches": ["R03"]}}), [])
        self.assertEqual(mine({"blind": {"matched": 0, "checked": 0, "mismatches": []}}), [])

    def test_not_an_object_is_named(self):
        for value in ("все 5 реализованы", ["R01"], 5, True):
            with self.subTest(value=value):
                findings = mine({"blind": value})
                self.assertEqual(len(findings), 1)
                self.assertIn("не объектом", findings[0])

    def test_missing_or_non_integer_numbers_are_named_with_their_names(self):
        for blind, lacking in (({"mismatches": []}, "matched, checked"),
                               ({"matched": 5, "mismatches": []}, "checked"),
                               ({"checked": 5, "mismatches": []}, "matched"),
                               ({"matched": "5", "checked": 5, "mismatches": []}, "matched"),
                               ({"matched": 5.0, "checked": 5, "mismatches": []}, "matched"),
                               ({"matched": True, "checked": 5, "mismatches": []}, "matched"),
                               ({"matched": None, "checked": None}, "matched, checked")):
            with self.subTest(blind=blind):
                findings = mine({"blind": blind})
                self.assertEqual(len(findings), 1)
                self.assertIn("без чисел " + lacking, findings[0])

    def test_numbers_without_a_list_are_named(self):
        for blind in ({"matched": 5, "checked": 5}, {"matched": 5, "checked": 5, "mismatches": "нет"},
                      {"matched": 5, "checked": 5, "drift": []}):
            with self.subTest(blind=blind):
                findings = mine({"blind": blind})
                self.assertEqual(len(findings), 1)
                self.assertIn("mismatches", findings[0])


class TheInstructionsSayIt(unittest.TestCase):
    def text(self, name):
        return (SKILL / "phases" / name).read_text(encoding="utf-8")

    def test_the_blind_shape_is_written_where_the_state_is_described(self):
        text = self.text("7-instruments.md")
        self.assertIn('`{ "matched": 5, "checked": 5, "mismatches": [] }`', text)
        self.assertIn("`sync.py` names such a `blind`", text)

    def test_a_stage_that_never_ran_is_skipped_not_done(self):
        self.assertIn("a stage that never ran is `skipped` with a note, never `done` without a `startedAt`",
                      self.text("7-instruments.md"))
        landing = self.text("8-final.md")
        self.assertIn("`done` is for a stage that actually ran and carries a `startedAt`", landing)
        self.assertIn("is `skipped` with a one-line note, never `done`", landing)

    def test_t0_opens_the_build_stage_with_its_start(self):
        self.assertIn("Mark the `build` stage `active` (with its `startedAt`) before you start", self.text("5-subagents.md"))


if __name__ == "__main__":
    unittest.main()
