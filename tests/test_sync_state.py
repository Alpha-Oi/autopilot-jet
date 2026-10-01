"""Инварианты жизненного цикла в sync.py: close_passed() и audit().

Это единственный код, который сам закрывает этапы и называет половинчатые переходы,
поэтому его поведение зафиксировано отдельно от жизненного цикла сервера (test_sync.py).
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
SPEC = importlib.util.spec_from_file_location("autopilot_sync_state", SCRIPT)
sync = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync)


def stage(stage_id, status, started=None, finished=None):
    item = {"id": stage_id, "status": status}
    if started:
        item["startedAt"] = started
    if finished:
        item["finishedAt"] = finished
    return item


def by_id(state):
    return {item["id"]: item for item in state["stages"]}


class ClosePassedTests(unittest.TestCase):
    def test_nothing_to_close_with_fewer_than_two_active_stages(self):
        for stages in ([], [stage("spec", "active", "2026-09-01T10:00:00Z")],
                       [stage("spec", "done", "2026-09-01T10:00:00Z", "2026-09-01T10:30:00Z"),
                        stage("plan", "active", "2026-09-01T10:30:00Z")]):
            with self.subTest(stages=len(stages)):
                state = {"stages": stages}
                before = copy.deepcopy(state)
                self.assertEqual(sync.close_passed(state), [])
                self.assertEqual(state, before)

    def test_missing_or_empty_stages_are_safe(self):
        for state in ({}, {"stages": None}, {"stages": []}):
            with self.subTest(state=state):
                self.assertEqual(sync.close_passed(state), [])

    def test_earlier_active_stage_is_closed_at_the_moment_the_next_one_opened(self):
        state = {"stages": [
            stage("briefing", "active", "2026-09-01T10:00:00Z"),
            stage("spec", "active", "2026-09-01T10:20:30Z"),
        ]}

        closed = sync.close_passed(state)

        self.assertEqual(closed, ["briefing закрыт автоматически (10:20:30)"])
        stages = by_id(state)
        self.assertEqual(stages["briefing"]["status"], "done")
        self.assertEqual(stages["briefing"]["finishedAt"], "2026-09-01T10:20:30Z")
        self.assertEqual(stages["spec"]["status"], "active")
        self.assertNotIn("finishedAt", stages["spec"])

    def test_each_stage_closes_at_the_nearest_next_stage_not_the_furthest(self):
        state = {"stages": [
            stage("spec", "active", "2026-09-01T10:00:00Z"),
            stage("plan", "active", "2026-09-01T11:00:00Z"),
            stage("build", "active", "2026-09-01T12:00:00Z"),
        ]}

        closed = sync.close_passed(state)

        stages = by_id(state)
        self.assertEqual(stages["spec"]["finishedAt"], "2026-09-01T11:00:00Z")
        self.assertEqual(stages["plan"]["finishedAt"], "2026-09-01T12:00:00Z")
        self.assertEqual(stages["build"]["status"], "active")
        self.assertEqual(len(closed), 2)

    def test_order_of_the_list_does_not_matter(self):
        state = {"stages": [
            stage("build", "active", "2026-09-01T12:00:00Z"),
            stage("plan", "active", "2026-09-01T11:00:00Z"),
            stage("spec", "active", "2026-09-01T10:00:00Z"),
        ]}

        sync.close_passed(state)

        stages = by_id(state)
        self.assertEqual(stages["spec"]["finishedAt"], "2026-09-01T11:00:00Z")
        self.assertEqual(stages["plan"]["finishedAt"], "2026-09-01T12:00:00Z")
        self.assertEqual(stages["build"]["status"], "active")

    def test_review_does_not_close_build(self):
        state = {"stages": [
            stage("build", "active", "2026-09-01T10:00:00Z"),
            stage("review", "active", "2026-09-01T10:30:00Z"),
        ]}
        before = copy.deepcopy(state)

        self.assertEqual(sync.close_passed(state), [])
        self.assertEqual(state, before)

    def test_anything_after_review_closes_both_build_and_review(self):
        state = {"stages": [
            stage("build", "active", "2026-09-01T10:00:00Z"),
            stage("review", "active", "2026-09-01T10:30:00Z"),
            stage("final", "active", "2026-09-01T13:00:00Z"),
        ]}

        closed = sync.close_passed(state)

        stages = by_id(state)
        self.assertEqual(stages["build"]["finishedAt"], "2026-09-01T13:00:00Z")
        self.assertEqual(stages["review"]["finishedAt"], "2026-09-01T13:00:00Z")
        self.assertEqual(stages["final"]["status"], "active")
        self.assertEqual(len(closed), 2)

    def test_conscious_states_are_never_turned_into_done(self):
        state = {"stages": [
            stage("preflight", "done", "2026-09-01T09:00:00Z", "2026-09-01T09:05:00Z"),
            stage("manifest", "skipped"),
            stage("briefing", "failed", "2026-09-01T09:10:00Z"),
            stage("spec", "active", "2026-09-01T10:00:00Z"),
            stage("plan", "pending"),
            stage("build", "active", "2026-09-01T11:00:00Z"),
        ]}
        before = {item["id"]: copy.deepcopy(item) for item in state["stages"]}

        sync.close_passed(state)

        stages = by_id(state)
        for untouched in ("preflight", "manifest", "briefing", "plan"):
            self.assertEqual(stages[untouched], before[untouched], untouched)
        self.assertEqual(stages["spec"]["status"], "done")

    def test_unknown_stage_ids_are_ignored(self):
        state = {"stages": [
            stage("custom", "active", "2026-09-01T10:00:00Z"),
            stage("spec", "active", "2026-09-01T10:30:00Z"),
        ]}
        before = copy.deepcopy(state)

        self.assertEqual(sync.close_passed(state), [])
        self.assertEqual(state, before)

    def test_falls_back_to_updated_at_when_the_later_stage_has_no_start(self):
        state = {"updatedAt": "2026-09-01T15:45:10Z", "stages": [
            stage("spec", "active", "2026-09-01T10:00:00Z"),
            stage("plan", "active"),
        ]}

        closed = sync.close_passed(state)

        self.assertEqual(by_id(state)["spec"]["finishedAt"], "2026-09-01T15:45:10Z")
        self.assertEqual(closed, ["spec закрыт автоматически (15:45:10)"])

    def test_without_any_timestamp_nothing_is_invented(self):
        state = {"stages": [stage("spec", "active"), stage("plan", "active")]}
        before = copy.deepcopy(state)

        self.assertEqual(sync.close_passed(state), [])
        self.assertEqual(state, before)

    def test_the_pulse_belongs_to_the_agent_updated_at_is_not_moved(self):
        state = {"updatedAt": "2026-09-01T09:00:00Z", "stages": [
            stage("spec", "active", "2026-09-01T10:00:00Z"),
            stage("plan", "active", "2026-09-01T11:00:00Z"),
        ]}

        sync.close_passed(state)

        self.assertEqual(state["updatedAt"], "2026-09-01T09:00:00Z")


class AuditTests(unittest.TestCase):
    def test_a_consistent_state_is_silent(self):
        state = {
            "stages": [
                stage("preflight", "done", "2026-09-01T09:00:00Z", "2026-09-01T09:05:00Z"),
                stage("manifest", "skipped"),
                stage("briefing", "active", "2026-09-01T09:10:00Z"),
                stage("spec", "pending"),
            ],
            "tickets": [
                {"id": "01", "status": "in-progress", "startedAt": "2026-09-01T09:20:00Z"},
                {"id": "02", "status": "done", "startedAt": "2026-09-01T09:20:00Z",
                 "finishedAt": "2026-09-01T09:40:00Z"},
                {"id": "03", "status": "pending"},
            ],
        }
        self.assertEqual(sync.audit(state), [])

    def test_missing_keys_are_safe(self):
        for state in ({}, {"stages": None, "tickets": None}):
            with self.subTest(state=state):
                self.assertEqual(sync.audit(state), [])

    def test_a_pending_stage_behind_the_active_one_is_named_not_fixed(self):
        state = {"stages": [
            stage("manifest", "pending"),
            stage("briefing", "skipped"),
            stage("spec", "active", "2026-09-01T10:00:00Z"),
            stage("plan", "pending"),
        ]}
        before = copy.deepcopy(state)

        messages = sync.audit(state)

        self.assertEqual(messages, ["этап manifest остался pending, а прогон ушёл дальше — пометь skipped с причиной"])
        self.assertEqual(state, before)

    def test_the_furthest_active_stage_sets_the_edge(self):
        state = {"stages": [
            stage("spec", "active", "2026-09-01T10:00:00Z"),
            stage("plan", "pending"),
            stage("build", "active", "2026-09-01T11:00:00Z"),
        ]}
        self.assertEqual(sync.audit(state),
                         ["этап plan остался pending, а прогон ушёл дальше — пометь skipped с причиной"])

    def test_without_an_active_stage_pending_is_not_a_problem(self):
        state = {"stages": [stage("manifest", "pending"), stage("spec", "pending")]}
        self.assertEqual(sync.audit(state), [])

    def test_unknown_stage_ids_do_not_set_the_edge(self):
        state = {"stages": [stage("manifest", "pending"), stage("custom", "active")]}
        self.assertEqual(sync.audit(state), [])

    def test_done_stage_without_finished_at_is_named(self):
        state = {"stages": [
            stage("preflight", "done", "2026-09-01T09:00:00Z"),
            stage("manifest", "done", "2026-09-01T09:05:00Z", "2026-09-01T09:10:00Z"),
        ]}
        self.assertEqual(sync.audit(state), ["этап preflight закрыт без finishedAt"])

    def test_tickets_in_work_without_started_at_are_named(self):
        state = {"tickets": [
            {"id": "01", "status": "in-progress"},
            {"id": "02", "status": "review"},
            {"id": "03", "status": "repair"},
            {"id": "04", "status": "pending"},
            {"id": "05", "status": "in-progress", "startedAt": "2026-09-01T09:00:00Z"},
        ]}
        self.assertEqual(sync.audit(state), [
            "таск 01 в работе без startedAt",
            "таск 02 в работе без startedAt",
            "таск 03 в работе без startedAt",
        ])

    def test_done_ticket_without_finished_at_is_named(self):
        state = {"tickets": [
            {"id": "01", "status": "done", "startedAt": "2026-09-01T09:00:00Z"},
            {"id": "02", "status": "done", "startedAt": "2026-09-01T09:00:00Z",
             "finishedAt": "2026-09-01T09:30:00Z"},
        ]}
        self.assertEqual(sync.audit(state), ["таск 01 закрыт без finishedAt"])

    def test_audit_never_mutates_the_state(self):
        state = {
            "stages": [stage("manifest", "pending"), stage("spec", "active"),
                       stage("preflight", "done")],
            "tickets": [{"id": "01", "status": "in-progress"}, {"id": "02", "status": "done"}],
        }
        before = copy.deepcopy(state)
        self.assertEqual(len(sync.audit(state)), 4)
        self.assertEqual(state, before)

    def test_close_passed_then_audit_reports_what_only_a_human_can_decide(self):
        state = {"stages": [
            stage("manifest", "pending"),
            stage("spec", "active", "2026-09-01T10:00:00Z"),
            stage("plan", "active", "2026-09-01T11:00:00Z"),
        ]}

        sync.close_passed(state)

        self.assertEqual(sync.audit(state),
                         ["этап manifest остался pending, а прогон ушёл дальше — пометь skipped с причиной"])


class MainIntegrationTests(unittest.TestCase):
    """Тот же код через настоящий запуск: перенесённый helper, соседние state.js и страница."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="sync state проверка ")
        self.addCleanup(self.tmp.cleanup)
        self.runtime = Path(self.tmp.name).resolve() / "project" / ".autopilot"
        self.runtime.mkdir(parents=True)
        self.helper = self.runtime / "sync.py"
        shutil.copyfile(SCRIPT, self.helper)
        self.page = self.runtime / "dashboard.html"
        self.page.write_text("a /*STATE-BEGIN*/old/*STATE-END*/ b", encoding="utf-8")
        self.state_path = self.runtime / "state.js"

    def write_state(self, state):
        self.state_path.write_text("window.STATE=" + json.dumps(state, ensure_ascii=False),
                                   encoding="utf-8")

    def read_state(self):
        body = self.state_path.read_text(encoding="utf-8").split("=", 1)[1]
        return json.loads(body.strip().rstrip(";"))

    def run_helper(self):
        return subprocess.run(
            [sys.executable, "-X", "utf8", "-B", str(self.helper), "--no-serve"],
            capture_output=True, text=True, encoding="utf-8", timeout=30, check=False,
        )

    def test_passed_stage_is_closed_saved_and_reported_without_moving_updated_at(self):
        self.write_state({"updatedAt": "2026-09-01T09:00:00Z", "tickets": [], "stages": [
            stage("briefing", "active", "2026-09-01T10:00:00Z"),
            stage("spec", "active", "2026-09-01T10:20:30Z"),
        ]})

        done = self.run_helper()

        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("  · briefing закрыт автоматически (10:20:30)", done.stdout)
        saved = self.read_state()
        self.assertEqual(saved["updatedAt"], "2026-09-01T09:00:00Z")
        self.assertEqual(by_id(saved)["briefing"]["status"], "done")
        self.assertEqual(by_id(saved)["briefing"]["finishedAt"], "2026-09-01T10:20:30Z")
        snapshot = self.page.read_text(encoding="utf-8")
        self.assertIn('"finishedAt": "2026-09-01T10:20:30Z"', snapshot)

    def test_consistent_state_is_not_rewritten_and_prints_no_findings(self):
        self.write_state({"updatedAt": "2026-09-01T09:00:00Z", "tickets": [], "stages": [
            stage("spec", "active", "2026-09-01T10:00:00Z")]})
        before = self.state_path.read_bytes()

        done = self.run_helper()

        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(self.state_path.read_bytes(), before)
        self.assertNotIn("  · ", done.stdout)
        self.assertNotIn("  ! ", done.stdout)

    def test_audit_findings_are_printed_and_limited_to_five(self):
        tickets = [{"id": "%02d" % number, "status": "in-progress"} for number in range(1, 9)]
        self.write_state({"updatedAt": "2026-09-01T09:00:00Z", "tickets": tickets, "stages": []})

        done = self.run_helper()

        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        findings = [line for line in done.stdout.splitlines() if line.startswith("  ! ")]
        self.assertEqual(len(findings), 5)
        self.assertIn("  ! таск 01 в работе без startedAt", findings)
        self.assertNotIn("таск 06", done.stdout)


if __name__ == "__main__":
    unittest.main()
