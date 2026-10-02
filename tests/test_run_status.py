"""Закрытый прогон не воскресает из старой записи (REQ-CORE-22 стандарта DOA: воскрешение запрещено).

Единица здесь — прогон: каталог `.autopilot/<дата>-<имя>--wip/` и `state.js`. Закрытие записано дважды: `finishedAt`
в `state.js` и каталог, потерявший `--wip`. Возобновить можно только открытый прогон; закрытый заново открывают
словом пользователя («доделай», `phases/0-preflight.md`), и тогда каталог получает `--wip` обратно. Поэтому
воскрешением без заявления считается расхождение двух записей: закрытый прогон, в котором снова идёт работа, и
открытый, лежащий в каталоге без `--wip`.

`sync.py --run-status` называет состояние до возобновления и ничего не пишет; `audit()` называет то же расхождение
при каждой синхронизации. Что агент соблюдает вердикт, остаётся инструкцией: код выносит приговор, а не исполняет.

Функции проверены на синтетических записях: тест, который не умеет краснеть, ничего не доказывает.
"""

from datetime import datetime, timedelta, timezone
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


SCRIPT = Path(__file__).parents[1] / "skills" / "autopilot-jet" / "tools" / "sync.py"
SPEC = importlib.util.spec_from_file_location("autopilot_sync_run_status", SCRIPT)
sync = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync)

NOW = datetime(2026, 10, 2, 12, 0, 0, tzinfo=timezone.utc)


def stamp(days_ago=0.0, seconds=0):
    return (NOW - timedelta(days=days_ago, seconds=seconds)).isoformat()


def open_run(**extra):
    state = {"dir": "2026-10-01-feature--wip", "finishedAt": None, "updatedAt": stamp(1),
             "stages": [{"id": "build", "status": "active", "startedAt": stamp(1)}],
             "tickets": [{"id": "01", "status": "in-progress", "startedAt": stamp(1)}]}
    state.update(extra)
    return state


def closed_run(**extra):
    state = {"dir": "2026-10-01-feature", "finishedAt": stamp(30), "updatedAt": stamp(30),
             "stages": [{"id": "build", "status": "done", "startedAt": stamp(31), "finishedAt": stamp(30)},
                        {"id": "final", "status": "done", "startedAt": stamp(30), "finishedAt": stamp(30)}],
             "tickets": [{"id": "01", "status": "done", "startedAt": stamp(31), "finishedAt": stamp(30)}]}
    state.update(extra)
    return state


def verdict(state):
    return sync.run_status(state, NOW)[0]


class VerdictTests(unittest.TestCase):
    def test_a_fresh_open_run_may_be_resumed(self):
        self.assertEqual(verdict(open_run()), "open")

    def test_a_closed_run_is_closed_and_may_not_be_resumed(self):
        self.assertEqual(verdict(closed_run()), "closed")

    def test_an_old_closed_run_is_closed_not_stale(self):
        self.assertEqual(verdict(closed_run(finishedAt=stamp(400), updatedAt=stamp(400))), "closed")

    def test_staleness_starts_after_seven_days(self):
        self.assertEqual(sync.RESUME_STALE_DAYS, 7)
        self.assertEqual(verdict(open_run(updatedAt=stamp(7))), "open")
        self.assertEqual(verdict(open_run(updatedAt=stamp(7, seconds=1))), "stale")
        self.assertEqual(verdict(open_run(updatedAt=stamp(40))), "stale")

    def test_the_reason_names_the_age_and_the_threshold(self):
        why = sync.run_status(open_run(updatedAt=stamp(12)), NOW)[1]
        self.assertIn("12", why)
        self.assertIn("7", why)

    def test_an_open_run_with_an_unreadable_stamp_is_unknown(self):
        for bad in (None, "", "вчера", "2026-10-01T10:00:00", 5):
            with self.subTest(updated=bad):
                self.assertEqual(verdict(open_run(updatedAt=bad)), "unknown")

    def test_a_record_that_is_not_a_run_is_unknown(self):
        for state in (None, [], "x", 7):
            with self.subTest(state=state):
                self.assertEqual(verdict(state), "unknown")

    def test_a_closed_run_that_is_written_to_again_is_resurrected(self):
        for change in ({"stages": [{"id": "build", "status": "active"}]},
                       {"tickets": [{"id": "07", "status": "in-progress"}]},
                       {"tickets": [{"id": "07", "status": "review"}]},
                       {"tickets": [{"id": "07", "status": "repair"}]}):
            with self.subTest(change=change):
                self.assertEqual(verdict(closed_run(**change)), "resurrected")

    def test_an_open_run_in_a_directory_without_wip_is_resurrected(self):
        self.assertEqual(verdict(open_run(dir="2026-10-01-feature")), "resurrected")

    def test_the_reopen_that_the_instructions_describe_is_open_again(self):
        # «доделай»: finishedAt снова null, каталог получил --wip обратно
        reopened = closed_run(finishedAt=None, dir="2026-10-01-feature--wip", updatedAt=stamp(0, 60),
                              stages=[{"id": "build", "status": "active"}],
                              tickets=[{"id": "08", "status": "in-progress"}])
        self.assertEqual(verdict(reopened), "open")

    def test_a_landed_run_whose_rename_failed_is_still_closed(self):
        # фаза 8: «если переименование не удалось, прогон не отменяется»
        self.assertEqual(verdict(closed_run(dir="2026-10-01-feature--wip")), "closed")

    def test_a_record_without_a_directory_is_not_judged_by_it(self):
        state = open_run()
        del state["dir"]
        self.assertEqual(verdict(state), "open")

    def test_resurrection_wins_over_closed_and_stale(self):
        stale_and_resurrected = open_run(dir="2026-10-01-feature", updatedAt=stamp(90))
        self.assertEqual(verdict(stale_and_resurrected), "resurrected")

    def test_findings_are_silent_for_consistent_records(self):
        self.assertEqual(sync.closure_findings(open_run()), [])
        self.assertEqual(sync.closure_findings(closed_run()), [])
        self.assertEqual(sync.closure_findings({}), [])


class AuditIntegrationTests(unittest.TestCase):
    def test_audit_names_a_closed_run_that_is_written_to_again(self):
        state = closed_run(stages=[{"id": "build", "status": "active", "startedAt": stamp(0, 5)}])
        self.assertTrue(any("закрыт" in line and "build" in line for line in sync.audit(state)), sync.audit(state))

    def test_audit_names_an_open_run_in_a_closed_directory(self):
        self.assertTrue(any("без --wip" in line for line in sync.audit(open_run(dir="2026-10-01-feature"))))

    def test_audit_stays_silent_for_a_consistent_closed_run_and_never_mutates(self):
        state = closed_run()
        before = copy.deepcopy(state)
        self.assertEqual(sync.audit(state), [])
        self.assertEqual(state, before)

    def test_the_closure_findings_follow_the_older_findings(self):
        state = open_run(dir="2026-10-01-feature")
        state["stages"] = [{"id": "build", "status": "done"}]
        lines = sync.audit(state)
        self.assertEqual(len(lines), 2)
        self.assertIn("закрыт без finishedAt", lines[0])
        self.assertIn("без --wip", lines[1])


class CliCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="run status ")
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(os.path.realpath(self.tmp.name))

    def write_state(self, state):
        (self.dir / "state.js").write_text("window.STATE =\n" + json.dumps(state, indent=2) + "\n", encoding="utf-8")

    def snapshot(self):
        return {path.name: path.read_bytes() for path in sorted(self.dir.iterdir())}

    def run_cli(self, *args):
        return subprocess.run([sys.executable, "-X", "utf8", "-B", str(SCRIPT), *args], capture_output=True,
                              text=True, encoding="utf-8", timeout=60, check=False)

    def status(self, state):
        self.write_state(state)
        result = self.run_cli("--run-status", str(self.dir))
        return result.returncode, result.stdout.split(" · ")[0]


class CliTests(CliCase):
    def now_stamp(self, days_ago=0):
        return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()

    def test_exit_codes_follow_the_verdict(self):
        self.assertEqual(self.status(open_run(updatedAt=self.now_stamp(0))), (0, "open"))
        self.assertEqual(self.status(closed_run()), (1, "closed"))
        self.assertEqual(self.status(open_run(updatedAt=self.now_stamp(30))), (3, "stale"))
        self.assertEqual(self.status(closed_run(stages=[{"id": "build", "status": "active"}])), (3, "resurrected"))
        self.assertEqual(self.status(open_run(dir="2026-10-01-feature", updatedAt=self.now_stamp(0))), (3, "resurrected"))

    def test_no_state_means_no_run_here(self):
        result = self.run_cli("--run-status", str(self.dir))
        self.assertEqual((result.returncode, result.stdout.split(" · ")[0]), (0, "none"))
        self.assertEqual(os.listdir(self.dir), [])

    def test_a_broken_state_needs_a_human(self):
        (self.dir / "state.js").write_text("window.STATE =\n{ не json\n", encoding="utf-8")
        result = self.run_cli("--run-status", str(self.dir))
        self.assertEqual((result.returncode, result.stdout.split(" · ")[0]), (3, "unknown"))

    def test_the_mode_writes_nothing(self):
        self.write_state(closed_run(stages=[{"id": "build", "status": "active"}]))
        before = self.snapshot()
        self.assertEqual(list(before), ["state.js"])
        self.run_cli("--run-status", str(self.dir))
        self.assertEqual(self.snapshot(), before)

    def test_a_bad_call_exits_two(self):
        for args in (("--run-status", "a", "b"), ("--run-status", "--write")):
            with self.subTest(args=args):
                self.assertEqual(self.run_cli(*args).returncode, 2)


class DispatchTests(unittest.TestCase):
    def test_the_flag_does_not_fall_through_to_the_ordinary_sync(self):
        with mock.patch.object(sys, "argv", ["sync.py", "--run-status"]), \
                mock.patch.object(sync, "check_run_status", return_value=1) as check, \
                mock.patch.object(sync, "read_state", side_effect=AssertionError("ordinary sync ran")), \
                mock.patch.object(sync, "serve", side_effect=AssertionError("server touched")), \
                self.assertRaises(SystemExit) as raised:
            sync.main()
        self.assertEqual(raised.exception.code, 1)
        check.assert_called_once_with(sync.A)


if __name__ == "__main__":
    unittest.main()
