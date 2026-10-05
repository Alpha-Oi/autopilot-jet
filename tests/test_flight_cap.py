"""Потолок полёта: не больше трёх тасков в работе (F-14 каскадный отказ, класс отказов стандарта DOA).

Правило записано в `phases/5-subagents.md`: тройка в полёте, следующий таск запускают, пока вернувшийся ещё не
обработан. Поэтому у верного прогона в `state.js` на миг четыре `in-progress`, и по записи это не отличить от
нарушения. Код называет то, что нарушением является при любой очерёдности записей: пять и больше.

Что остаётся инструкцией: ровно четыре молчат, а сам параллелизм агентов хоста лежит вне репозитория и по записи
не виден. Тесты проверяют запись, а не то, сколько субагентов летело на самом деле.

Проверка проверена нарочными поломками: тест, который не умеет краснеть, ничего не доказывает.
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


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "skills" / "autopilot-jet" / "tools" / "sync.py"
TEMPLATE = ROOT / "skills" / "autopilot-jet" / "phases" / "dashboard-template.html"
PHASE = ROOT / "skills" / "autopilot-jet" / "phases" / "5-subagents.md"
SPEC = importlib.util.spec_from_file_location("autopilot_sync_flight", SCRIPT)
sync = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync)


def ticket(ticket_id, status="in-progress", **extra):
    item = {"id": ticket_id, "status": status, "startedAt": "2026-10-05T10:00:00Z", "zone": ["src/%s/" % ticket_id],
            "blockedBy": [], "retries": 0, "repairs": 0, "handoffs": 0}
    if status == "done":
        item["finishedAt"] = "2026-10-05T10:30:00Z"
    item.update(extra)
    return item


def flight(count, **extra):
    return {"tickets": [ticket("%02d" % number, **extra) for number in range(1, count + 1)]}


def named(state):
    return [line for line in sync.audit_caps(state) if "потолок полёта" in line]


class ThresholdTests(unittest.TestCase):
    def test_the_ceiling_constants_say_three_and_the_correct_transient_four(self):
        self.assertEqual((sync.FLIGHT_CAP, sync.FLIGHT_SEEN_MAX), (3, 4))

    def test_up_to_four_in_progress_is_silent(self):
        for count in range(0, 5):
            with self.subTest(count=count):
                self.assertEqual(named(flight(count)), [])

    def test_five_and_more_are_named_once(self):
        for count in (5, 6, 9):
            with self.subTest(count=count):
                findings = named(flight(count))
                self.assertEqual(len(findings), 1)
                self.assertIn("в работе %d тасков" % count, findings[0])

    def test_the_line_names_every_flying_ticket_and_the_cap(self):
        line = named(flight(5))[0]
        for number in range(1, 6):
            self.assertIn("%02d" % number, line)
        self.assertIn("потолок полёта 3", line)

    def test_only_in_progress_counts_review_repair_done_and_pending_do_not(self):
        quiet = ("review", "repair", "done", "pending")
        for status in quiet:
            with self.subTest(status=status):
                self.assertEqual(named(flight(8, status=status)), [])
        mixed = {"tickets": [ticket("%02d" % n, status=quiet[n % 4]) for n in range(1, 9)] + [ticket("A"), ticket("B")]}
        self.assertEqual(named(mixed), [])

    def test_a_returned_ticket_that_is_written_to_review_brings_the_count_back_under(self):
        state = flight(5)
        self.assertEqual(len(named(state)), 1)
        state["tickets"][0]["status"] = "review"
        self.assertEqual(named(state), [])

    def test_malformed_tickets_are_not_counted_and_do_not_crash(self):
        state = {"tickets": [None, "text", {"status": "in-progress"}, {"id": None, "status": "in-progress"}]
                 + [ticket("%02d" % n) for n in range(1, 5)]}
        self.assertEqual(named(state), [])
        self.assertEqual(named({}), [])
        self.assertEqual(named({"tickets": None}), [])


class WhereTheFindingShowsUpTests(unittest.TestCase):
    def test_audit_carries_it_into_the_ordinary_sync_output(self):
        self.assertTrue(any("потолок полёта" in line for line in sync.audit(flight(5))))
        self.assertFalse(any("потолок полёта" in line for line in sync.audit(flight(4))))

    def test_audit_never_mutates_the_state(self):
        state = flight(6)
        before = json.dumps(state, sort_keys=True)
        sync.audit(state)
        self.assertEqual(json.dumps(state, sort_keys=True), before)

    def run_sync_here(self, state):
        # настоящая раскладка: sync.py лежит рядом с state.js в `.autopilot/`
        with tempfile.TemporaryDirectory(prefix="flight cap ") as tmp:
            base = Path(os.path.realpath(tmp))
            shutil.copy(SCRIPT, base / "sync.py")
            shutil.copy(TEMPLATE, base / "dashboard.html")
            (base / "state.js").write_text("window.STATE =\n" + json.dumps(state, indent=2) + "\n", encoding="utf-8")
            result = subprocess.run([sys.executable, "-X", "utf8", "-B", str(base / "sync.py"), "--no-serve"],
                                    capture_output=True, text=True, encoding="utf-8", timeout=60, check=False)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            return result.stdout

    def run_state(self, count):
        state = flight(count)
        state.update({"dir": "2026-10-05-feature--wip", "finishedAt": None, "updatedAt": "2026-10-05T10:00:00Z",
                      "stages": [{"id": "build", "status": "active", "startedAt": "2026-10-05T10:00:00Z"}]})
        return state

    def test_the_ordinary_sync_prints_it_end_to_end(self):
        out = self.run_sync_here(self.run_state(5))
        self.assertTrue(any(line.startswith("  ! ") and "потолок полёта" in line for line in out.splitlines()), out)

    def test_the_ordinary_sync_stays_quiet_on_four(self):
        self.assertNotIn("потолок полёта", self.run_sync_here(self.run_state(4)))


class InstructionTests(unittest.TestCase):
    def setUp(self):
        self.text = PHASE.read_text(encoding="utf-8")

    def test_the_phase_keeps_the_cap_of_three(self):
        self.assertIn("Cap at three in flight", self.text)

    def test_the_phase_says_that_five_is_a_finding_and_four_is_not(self):
        self.assertIn("**five or more** tickets `in-progress`", self.text)
        self.assertIn("four is not a finding", self.text)


if __name__ == "__main__":
    unittest.main()
