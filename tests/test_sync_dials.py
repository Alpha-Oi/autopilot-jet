"""Ручки прогона в audit(): записанные mode, depth, tier и polish — из допустимых значений.

Ручки решаются один раз в начале и пишутся в state.js; по записи восстанавливается политика прогона
(REQ-CORE-04 стандарта DOA). audit() называет значение вне списка и молчит о том, чего нет в записи.
"""

import importlib.util
from pathlib import Path
import unittest


SCRIPT = Path(__file__).parents[1] / "skills" / "autopilot-jet" / "tools" / "sync.py"
SPEC = importlib.util.spec_from_file_location("autopilot_sync_dials", SCRIPT)
sync = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync)


def dials(state):
    return sync.audit_dials(state)


class DialValueTests(unittest.TestCase):
    def test_every_documented_value_is_silent(self):
        for key, values in sync.DIAL_VALUES.items():
            for value in values:
                with self.subTest(key=key, value=value):
                    self.assertEqual(dials({key: value}), [])

    def test_the_documented_values_are_the_ones_the_instructions_name(self):
        self.assertEqual(sync.DIAL_VALUES["mode"], ("full", "semi", "interview", "manual"))
        self.assertEqual(sync.DIAL_VALUES["depth"], ("strict", "normal", "deep"))
        self.assertEqual(sync.DIAL_VALUES["tier"], ("T0", "T1", "T2", "T3"))

    def test_a_value_outside_the_list_is_named_with_the_allowed_ones(self):
        for key, bad in (("mode", "turbo"), ("depth", "extreme"), ("tier", "T9"), ("mode", ""), ("depth", 3),
                         ("mode", ["full"]), ("tier", "t2"), ("mode", "Full")):
            with self.subTest(key=key, value=bad):
                findings = dials({key: bad})
                self.assertEqual(len(findings), 1)
                self.assertTrue(findings[0].startswith(key + " "))
                self.assertIn(sync.DIAL_VALUES[key][0], findings[0])

    def test_missing_or_null_dials_are_silent(self):
        for state in ({}, {"mode": None, "depth": None, "tier": None}, {"tier": None, "polish": None}):
            with self.subTest(state=state):
                self.assertEqual(dials(state), [])

    def test_each_wrong_dial_gets_its_own_line(self):
        findings = dials({"mode": "turbo", "depth": "extreme", "tier": "T9"})
        self.assertEqual([line.split(" ")[0] for line in findings], ["mode", "depth", "tier"])


class PolishTests(unittest.TestCase):
    def test_null_and_an_object_are_fine(self):
        self.assertEqual(dials({"polish": None}), [])
        self.assertEqual(dials({"polish": {"reference": "reference.md", "rounds": []}}), [])

    def test_anything_else_is_named(self):
        for value in ("on", True, 3, ["x"], ""):
            with self.subTest(value=value):
                findings = dials({"polish": value})
                self.assertEqual(len(findings), 1)
                self.assertTrue(findings[0].startswith("polish "))


class AuditIntegrationTests(unittest.TestCase):
    def test_audit_includes_dials_after_the_other_findings_and_never_mutates(self):
        state = {"mode": "turbo", "tickets": [{"id": "01", "status": "done", "repairs": 3,
                                               "startedAt": "x", "finishedAt": "y"}]}
        snapshot = {"mode": "turbo", "tickets": [dict(state["tickets"][0])]}
        findings = sync.audit(state)
        self.assertEqual(state, snapshot)
        self.assertIn("repairs", findings[0])
        self.assertTrue(findings[-1].startswith("mode "))

    def test_a_valid_run_stays_silent_end_to_end(self):
        self.assertEqual(sync.audit({"mode": "semi", "depth": "normal", "tier": "T2", "polish": None}), [])


if __name__ == "__main__":
    unittest.main()
