"""Потолки и зоны в audit(): повторы, число тасков, раунды доводки, пересечение зон.

audit() не чинит и не блокирует: он называет. Здесь зафиксировано, что именно он называет и,
не менее важно, о чём молчит: «не больше трёх в полёте» из state.js проверить нельзя без ложных
срабатываний (правило запуска велит сначала запустить следующий таск, потом обработать вернувшийся),
поэтому на четырёх in-progress верный прогон остаётся тихим.
"""

import copy
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).parents[1] / "skills" / "autopilot-jet" / "tools" / "sync.py"
SPEC = importlib.util.spec_from_file_location("autopilot_sync_caps", SCRIPT)
sync = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync)


def ticket(ticket_id, status="done", zone=None, blocked_by=None, **counters):
    item = {"id": ticket_id, "status": status, "startedAt": "2026-09-01T10:00:00Z",
            "finishedAt": "2026-09-01T10:30:00Z", "zone": zone or ["src/%s/" % ticket_id],
            "blockedBy": blocked_by or [], "retries": 0, "repairs": 0, "handoffs": 0}
    item.update(counters)
    return item


def caps(state):
    return sync.audit_caps(state)


class CounterCeilingTests(unittest.TestCase):
    def test_at_the_ceiling_is_silent_above_it_is_named(self):
        for name in ("repairs", "retries", "handoffs"):
            with self.subTest(counter=name):
                self.assertEqual(caps({"tickets": [ticket("01", **{name: 2})]}), [])
                findings = caps({"tickets": [ticket("01", **{name: 3}), ticket("02")]})
                self.assertEqual(len(findings), 1)
                self.assertIn("01", findings[0])
                self.assertIn(name, findings[0])
                self.assertNotIn("02", findings[0])

    def test_one_line_per_counter_lists_every_ticket(self):
        state = {"tickets": [ticket("01", repairs=3), ticket("02", repairs=5), ticket("03", retries=4)]}
        findings = caps(state)
        self.assertEqual(len(findings), 2)
        self.assertIn("01, 02", [line for line in findings if "repairs" in line][0])
        self.assertIn("03", [line for line in findings if "retries" in line][0])

    def test_values_that_are_not_numbers_are_not_violations(self):
        for value in (None, "5", True, 2.5, [], {}):
            with self.subTest(value=value):
                self.assertEqual(caps({"tickets": [ticket("01", repairs=value)]}), [])

    def test_missing_counters_and_malformed_tickets_are_safe(self):
        state = {"tickets": [{"id": "01"}, None, "text", {"status": "done"}]}
        self.assertEqual(caps(state), [])


class TicketAndPolishCeilingTests(unittest.TestCase):
    def tickets(self, count, prefix=""):
        return [ticket("%s%02d" % (prefix, number)) for number in range(1, count + 1)]

    def test_sixteen_plan_tickets_are_allowed_seventeen_are_named(self):
        self.assertEqual(caps({"tickets": self.tickets(16)}), [])
        findings = caps({"tickets": self.tickets(17)})
        self.assertEqual(len(findings), 1)
        self.assertIn("17", findings[0])
        self.assertIn("16", findings[0])

    def test_polish_tickets_are_not_counted_against_the_plan(self):
        state = {"tickets": self.tickets(16) + self.tickets(4, prefix="P")}
        self.assertEqual(caps(state), [])

    def test_three_polish_rounds_are_allowed_four_are_named(self):
        rounds = lambda count: {"polish": {"rounds": [{"n": n} for n in range(1, count + 1)]}}
        self.assertEqual(caps(rounds(3)), [])
        findings = caps(rounds(4))
        self.assertEqual(len(findings), 1)
        self.assertIn("доводки", findings[0])

    def test_missing_or_malformed_polish_is_safe(self):
        for polish in (None, {}, {"rounds": None}, {"rounds": "many"}, "x"):
            with self.subTest(polish=polish):
                self.assertEqual(caps({"polish": polish}), [])


class ZoneTests(unittest.TestCase):
    def flying(self, first_zone, second_zone, **second):
        return {"tickets": [ticket("01", "in-progress", zone=first_zone),
                            ticket("02", "in-progress", zone=second_zone, **second)]}

    def test_overlapping_zones_of_unrelated_flying_tickets_are_named(self):
        for first, second in ((["src/bot/"], ["src/bot/"]), (["src/"], ["src/bot/"]),
                              (["src/bot/intake.ts"], ["src/bot"]), (["a/", "b/"], ["c/", "b/x/"])):
            with self.subTest(first=first, second=second):
                findings = caps(self.flying(first, second))
                self.assertEqual(len(findings), 1)
                self.assertIn("01 и 02", findings[0])

    def test_windows_separators_are_treated_like_slashes(self):
        self.assertEqual(len(caps(self.flying(["src\\bot\\"], ["src/bot/intake.ts"]))), 1)
        self.assertEqual(caps(self.flying(["src\\bot"], ["src\\bot2"])), [])

    def test_disjoint_zones_are_silent_including_a_shared_name_prefix(self):
        for first, second in ((["src/bot/"], ["src/admin/"]), (["src/bot/"], ["src/bot2/"]), (["src/bot"], ["src/bot2"]),
                              (["lib/a.py"], ["lib/a.pyc"]), (["a/"], ["b/"])):
            with self.subTest(first=first, second=second):
                self.assertEqual(caps(self.flying(first, second)), [])

    def test_a_ticket_and_its_dependent_may_share_a_zone(self):
        # Правило запуска: следующий таск летит, пока вернувшийся ещё записан как in-progress.
        self.assertEqual(caps(self.flying(["src/bot/"], ["src/bot/"], blocked_by=["01"])), [])

    def test_dependency_through_a_chain_counts(self):
        state = {"tickets": [ticket("01", "in-progress", zone=["src/"]),
                             ticket("02", "done", zone=["lib/"], blocked_by=["01"]),
                             ticket("03", "in-progress", zone=["src/"], blocked_by=["02"])]}
        self.assertEqual(caps(state), [])

    def test_only_tickets_in_progress_are_compared(self):
        for status in ("pending", "review", "repair", "done", "failed"):
            with self.subTest(status=status):
                state = {"tickets": [ticket("01", "in-progress", zone=["src/"]),
                                     ticket("02", status, zone=["src/"])]}
                self.assertEqual(caps(state), [])

    def test_missing_zone_or_ids_are_safe(self):
        state = {"tickets": [{"status": "in-progress"}, {"id": "02", "status": "in-progress"},
                             {"id": "03", "status": "in-progress", "zone": None},
                             {"id": "04", "status": "in-progress", "zone": ["", "."]}]}
        self.assertEqual(caps(state), [])


class WhatAuditCapsDoesNotSayTests(unittest.TestCase):
    def test_four_in_progress_with_disjoint_zones_is_a_correct_run_not_a_violation(self):
        state = {"tickets": [ticket(str(n), "in-progress") for n in range(1, 5)]}
        self.assertEqual(caps(state), [])

    def test_a_clean_state_is_silent_end_to_end(self):
        state = {"tickets": [ticket("01"), ticket("02", "in-progress")], "polish": {"rounds": [{"n": 1}]}}
        self.assertEqual(sync.audit(state), [])


class AuditIntegrationTests(unittest.TestCase):
    def test_audit_includes_caps_and_never_mutates_the_state(self):
        state = {"tickets": [ticket("01", repairs=3)], "polish": {"rounds": [{}] * 4}}
        before = copy.deepcopy(state)
        findings = sync.audit(state)
        self.assertEqual(state, before)
        self.assertTrue(any("repairs" in line for line in findings))
        self.assertTrue(any("доводки" in line for line in findings))

    def test_cap_findings_follow_the_transition_findings(self):
        state = {"stages": [{"id": "spec", "status": "done"}],
                 "tickets": [ticket("01", repairs=3)]}
        findings = sync.audit(state)
        self.assertIn("spec", findings[0])
        self.assertIn("repairs", findings[-1])


class MainIntegrationTests(unittest.TestCase):
    """Через настоящий запуск: перенесённый helper видит потолки и печатает их, ничего не меняя в state.js."""

    def run_with(self, state):
        with tempfile.TemporaryDirectory(prefix="sync caps проверка ") as tmp:
            runtime = Path(tmp).resolve() / "project" / ".autopilot"
            runtime.mkdir(parents=True)
            helper = runtime / "sync.py"
            shutil.copyfile(SCRIPT, helper)
            (runtime / "dashboard.html").write_text("a /*STATE-BEGIN*/old/*STATE-END*/ b", encoding="utf-8")
            state_path = runtime / "state.js"
            state_path.write_text("window.STATE=" + json.dumps(state, ensure_ascii=False), encoding="utf-8")
            before = state_path.read_bytes()
            result = subprocess.run([sys.executable, "-X", "utf8", "-B", str(helper), "--no-serve"],
                                    capture_output=True, text=True, encoding="utf-8", timeout=30, check=False)
            return result, state_path.read_bytes() == before

    def test_a_ticket_over_the_ceiling_is_printed_and_the_state_is_untouched(self):
        result, unchanged = self.run_with({"updatedAt": "2026-09-01T10:00:00Z", "tickets": [ticket("03", repairs=3)]})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("  ! таски 03: repairs выше потолка 2", result.stdout)
        self.assertTrue(unchanged)

    def test_a_correct_run_prints_nothing_after_the_summary_line(self):
        result, unchanged = self.run_with({"updatedAt": "2026-09-01T10:00:00Z",
                                           "tickets": [ticket(str(n), "in-progress") for n in range(1, 5)]})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("!", result.stdout)
        self.assertTrue(unchanged)


if __name__ == "__main__":
    unittest.main()
