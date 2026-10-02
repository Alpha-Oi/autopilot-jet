"""Файлы таска против его зоны (REQ-CORE-05 и REQ-CORE-26 стандарта DOA: наименьшие права и разделение мышления и власти).

У каждого таска в `state.js` есть `zone`: пути-префиксы, которыми он владеет, и `commit`: один коммит на таск.
`sync.py --zone-check` берёт файлы коммита из git (только чтение) и называет те, что лежат вне зоны. Допустимы вне
зоны `.autopilot/` и файл памяти проекта. Это приговор, а не запрет: файл уже в коммите, и права исполнителю
выдаёт хост, а не навык. Что агент запускает проверку после коммита и разбирает находку, остаётся инструкцией.

Функции проверены на синтетических записях и на настоящем git во временном репозитории: тест, который не умеет
краснеть, ничего не доказывает.
"""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


SKILL = Path(__file__).parents[1] / "skills" / "autopilot-jet"
SCRIPT = SKILL / "tools" / "sync.py"
SPEC = importlib.util.spec_from_file_location("autopilot_sync_zone", SCRIPT)
sync = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync)

ALLOWED = [".autopilot", "AGENTS.md"]


def git(cwd, *args):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "commit.gpgsign=false",
                           *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8", check=True).stdout.strip()


class Repo(unittest.TestCase):
    """Проект во временном каталоге с настоящим git; `.autopilot/` лежит в его корне."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="zone check ")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(os.path.realpath(self.tmp.name))
        git(self.root, "init", "-q")

    def commit(self, files, message="таск"):
        for name, text in files.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", message)
        return git(self.root, "rev-parse", "HEAD")

    def state(self, *tickets, **extra):
        state = {"dir": "2026-10-02-bot--wip", "memoryFile": "AGENTS.md", "tickets": list(tickets)}
        state.update(extra)
        return state

    @staticmethod
    def ticket(number, zone, commit, status="done"):
        return {"id": number, "status": status, "zone": zone, "commit": commit}


class ZoneMembershipTests(unittest.TestCase):
    def test_a_file_inside_a_directory_zone(self):
        self.assertTrue(sync.in_zone("src/bot/intake.py", ["src/bot/"]))
        self.assertTrue(sync.in_zone("src/bot/deep/er/x.py", ["src/bot"]))

    def test_the_zone_is_matched_by_segments_not_by_characters(self):
        self.assertFalse(sync.in_zone("src/bot2/x.py", ["src/bot"]))
        self.assertFalse(sync.in_zone("src/bottle.py", ["src/bot"]))

    def test_a_file_zone_matches_that_file_only(self):
        self.assertTrue(sync.in_zone("migrations/001.sql", ["migrations/001.sql"]))
        self.assertFalse(sync.in_zone("migrations/002.sql", ["migrations/001.sql"]))

    def test_any_of_several_zones(self):
        self.assertTrue(sync.in_zone("migrations/001.sql", ["src/bot/", "migrations/"]))
        self.assertFalse(sync.in_zone("docs/a.md", ["src/bot/", "migrations/"]))

    def test_windows_separators_are_the_same_path(self):
        self.assertTrue(sync.in_zone("src\\bot\\x.py", ["src/bot/"]))
        self.assertTrue(sync.in_zone("src/bot/x.py", ["src\\bot"]))

    def test_a_dot_zone_is_the_whole_project_and_the_declared_width_is_taken_as_is(self):
        self.assertTrue(sync.in_zone("anything/at/all.py", ["."]))
        self.assertTrue(sync.in_zone("x.py", ["./"]))

    def test_a_path_out_of_the_project_is_never_inside(self):
        self.assertFalse(sync.in_zone("../x.py", ["."]))
        self.assertFalse(sync.in_zone("src/../../x.py", ["src/"]))
        self.assertFalse(sync.in_zone("src/bot/x.py", ["src/../src/bot"]))

    def test_empty_things_match_nothing(self):
        self.assertFalse(sync.in_zone("", ["."]))
        self.assertFalse(sync.in_zone("x.py", []))
        self.assertFalse(sync.in_zone("x.py", ["", "/"]))

    def test_the_zone_of_a_ticket_is_read_strictly(self):
        self.assertEqual(sync.ticket_zone({"zone": ["src/bot/"]}), ["src/bot/"])
        self.assertEqual(sync.ticket_zone({"zone": "src/bot/"}), ["src/bot/"])
        for bad in (None, [], "", ["src", 5], [None], 7, {"a": 1}, ["  "]):
            with self.subTest(zone=bad):
                self.assertIsNone(sync.ticket_zone({"zone": bad}))
        self.assertIsNone(sync.ticket_zone({}))

    def test_files_outside_names_exactly_the_strangers(self):
        files = ["src/bot/a.py", "src/db/schema.sql", ".autopilot/state.js", "AGENTS.md", "README.md"]
        self.assertEqual(sync.files_outside(files, ["src/bot/"], ALLOWED), ["src/db/schema.sql", "README.md"])

    def test_allowed_is_exact_for_the_memory_file(self):
        self.assertEqual(sync.files_outside(["AGENTS.md", "docs/AGENTS.md", "AGENTS.md.bak"], ["src/"], ALLOWED),
                         ["docs/AGENTS.md", "AGENTS.md.bak"])


class ReportTests(Repo):
    def fake(self, mapping):
        def files_of(_root, commit):
            if commit not in mapping:
                return None, "коммита %s нет в git" % commit
            return mapping[commit], None
        return files_of

    def test_a_ticket_inside_its_zone_is_inside(self):
        state = self.state(self.ticket("01", ["src/bot/"], "abcd1234"))
        rows = sync.zone_report(state, str(self.root), self.fake({"abcd1234": ["src/bot/a.py", ".autopilot/state.js"]}))
        self.assertEqual(rows, [("01", "inside", [])])

    def test_a_stranger_makes_it_outside_and_is_named(self):
        state = self.state(self.ticket("02", ["src/bot/"], "abcd1234"))
        rows = sync.zone_report(state, str(self.root), self.fake({"abcd1234": ["src/bot/a.py", "src/db/schema.sql"]}))
        self.assertEqual(rows, [("02", "outside", ["src/db/schema.sql"])])

    def test_only_done_tickets_are_judged(self):
        tickets = [self.ticket("01", ["src/"], "abcd1234", status=status)
                   for status in ("pending", "in-progress", "review", "repair")]
        self.assertEqual(sync.zone_report(self.state(*tickets), str(self.root), self.fake({})), [])

    def test_a_done_ticket_without_a_zone_or_a_commit_is_unchecked_never_healthy(self):
        state = self.state({"id": "01", "status": "done", "commit": "abcd1234"},
                           {"id": "02", "status": "done", "zone": ["src/"]},
                           {"id": "03", "status": "done", "zone": ["src/"], "commit": None})
        rows = sync.zone_report(state, str(self.root), self.fake({}))
        self.assertEqual([(name, status) for name, status, _ in rows],
                         [("01", "unchecked"), ("02", "unchecked"), ("03", "unchecked")])

    def test_a_commit_that_is_not_a_hash_never_reaches_git(self):
        calls = []

        def files_of(root, commit):
            calls.append(commit)
            return [], None

        for bad in ("--output=/tmp/x", "-h", "HEAD~1", "main", "abc", "zz" * 8, "a1b2c3d; rm", ""):
            with self.subTest(commit=bad):
                rows = sync.zone_report(self.state(self.ticket("01", ["src/"], bad)), str(self.root), files_of)
                self.assertEqual(rows[0][:2], ("01", "unchecked"))
        self.assertEqual(calls, [])

    def test_the_memory_file_comes_from_the_state_and_must_be_a_plain_name(self):
        mapping = {"abcd1234": ["NOTES.md", "../outside.md"]}
        state = self.state(self.ticket("01", ["src/"], "abcd1234"), memoryFile="NOTES.md")
        self.assertEqual(sync.zone_report(state, str(self.root), self.fake(mapping))[0][2], ["../outside.md"])
        state = self.state(self.ticket("01", ["src/"], "abcd1234"), memoryFile="../outside.md")
        self.assertEqual(sync.zone_report(state, str(self.root), self.fake(mapping))[0][2], ["NOTES.md", "../outside.md"])
        nested = {"abcd1234": ["docs/NOTES.md"]}
        state = self.state(self.ticket("01", ["src/"], "abcd1234"), memoryFile="docs/NOTES.md")
        self.assertEqual(sync.zone_report(state, str(self.root), self.fake(nested))[0][2], ["docs/NOTES.md"])

    def test_a_record_that_is_not_a_list_of_tickets_is_not_a_crash(self):
        for tickets in (None, "x", 5, {"a": 1}):
            with self.subTest(tickets=tickets):
                self.assertEqual(sync.zone_report({"tickets": tickets}, str(self.root), self.fake({})), [])
        self.assertEqual(sync.zone_report(self.state("x", 5, None), str(self.root), self.fake({})), [])


class UnfinishedTests(unittest.TestCase):
    def test_tickets_not_done_are_named_with_their_status(self):
        state = {"tickets": [{"id": "01", "status": "done"}, {"id": "02", "status": "review"},
                             {"id": "03", "status": "pending"}]}
        self.assertEqual(sync.unfinished_tickets(state), ["02 (review)", "03 (pending)"])

    def test_junk_is_not_a_crash(self):
        for tickets in (None, "x", 5, {"a": 1}, [None, 5, "x"]):
            with self.subTest(tickets=tickets):
                self.assertEqual(sync.unfinished_tickets({"tickets": tickets}), [])
        self.assertEqual(sync.unfinished_tickets({}), [])


class RealGitTests(Repo):
    def test_the_files_of_a_commit_come_from_git(self):
        commit = self.commit({"src/bot/a.py": "1", "src/db/schema.sql": "2", ".autopilot/state.js": "3"})
        files, why = sync.commit_files(str(self.root), commit)
        self.assertIsNone(why)
        self.assertEqual(sorted(files), [".autopilot/state.js", "src/bot/a.py", "src/db/schema.sql"])

    def test_only_that_commit_counts_not_the_ones_before(self):
        self.commit({"src/bot/a.py": "1"})
        second = self.commit({"src/db/schema.sql": "2"})
        self.assertEqual(sync.commit_files(str(self.root), second)[0], ["src/db/schema.sql"])

    def test_spaces_and_non_ascii_names_survive(self):
        commit = self.commit({"src/bot/мой файл.py": "1", "src/bot/with space.py": "2"})
        self.assertEqual(sorted(sync.commit_files(str(self.root), commit)[0]),
                         ["src/bot/with space.py", "src/bot/мой файл.py"])

    def test_the_first_commit_of_a_repository_is_read_too(self):
        commit = self.commit({"a.txt": "1"})
        self.assertEqual(sync.commit_files(str(self.root), commit)[0], ["a.txt"])

    def test_an_unknown_commit_is_a_reason_not_an_empty_list(self):
        self.commit({"a.txt": "1"})
        files, why = sync.commit_files(str(self.root), "deadbeef" * 5)
        self.assertIsNone(files)
        self.assertIn("нет в git", why)

    def test_a_directory_that_is_not_a_repository_is_a_reason(self):
        with tempfile.TemporaryDirectory(prefix="no repo ") as bare:
            standalone = os.path.realpath(bare)
            probe = subprocess.run(["git", "rev-parse", "--show-prefix"], cwd=standalone, capture_output=True)
            if probe.returncode == 0:
                self.skipTest("временный каталог лежит внутри чужого репозитория git")
            files, why = sync.commit_files(standalone, "deadbeef")
            self.assertIsNone(files)
            self.assertIn("не в репозитории", why)

    def test_a_project_below_the_repository_root_is_judged_by_paths_inside_it(self):
        sub = self.root / "app"
        sub.mkdir()
        commit = self.commit({"app/src/bot/a.py": "1", "app/.autopilot/state.js": "2", "other/x.py": "3"})
        files, why = sync.commit_files(str(sub), commit)
        self.assertIsNone(why)
        self.assertEqual(sorted(files), ["../other/x.py", ".autopilot/state.js", "src/bot/a.py"])
        state = self.state(self.ticket("01", ["src/bot/"], commit))
        self.assertEqual(sync.zone_report(state, str(sub))[0], ("01", "outside", ["../other/x.py"]))

    def test_a_real_report_names_the_stranger(self):
        inside = self.commit({"src/bot/a.py": "1", ".autopilot/state.js": "2", "AGENTS.md": "3"})
        wandering = self.commit({"src/bot/b.py": "1", "src/db/schema.sql": "2"})
        state = self.state(self.ticket("01", ["src/bot/"], inside), self.ticket("02", ["src/bot/"], wandering))
        self.assertEqual(sync.zone_report(state, str(self.root)),
                         [("01", "inside", []), ("02", "outside", ["src/db/schema.sql"])])

    def test_a_short_hash_works(self):
        commit = self.commit({"src/bot/a.py": "1"})
        state = self.state(self.ticket("01", ["src/bot/"], commit[:8]))
        self.assertEqual(sync.zone_report(state, str(self.root))[0][1], "inside")


class CliTests(Repo):
    def write_state(self, state):
        directory = self.root / ".autopilot"
        directory.mkdir(exist_ok=True)
        (directory / "state.js").write_text("window.STATE =\n" + json.dumps(state, indent=2) + "\n", encoding="utf-8")
        return directory

    def run_cli(self, *args):
        return subprocess.run([sys.executable, "-X", "utf8", "-B", str(SCRIPT), *args], capture_output=True,
                              text=True, encoding="utf-8", timeout=60, check=False)

    def check(self, state):
        result = self.run_cli("--zone-check", str(self.write_state(state)))
        return result.returncode, result.stdout

    def test_everything_inside_exits_zero(self):
        commit = self.commit({"src/bot/a.py": "1"})
        code, out = self.check(self.state(self.ticket("01", ["src/bot/"], commit)))
        self.assertEqual(code, 0, out)
        self.assertEqual(out.splitlines()[0], "zone · проверено 1 из 1 · вне зоны 0")

    def test_a_stranger_exits_one_and_names_ticket_zone_and_file(self):
        commit = self.commit({"src/bot/a.py": "1", "src/db/schema.sql": "2"})
        code, out = self.check(self.state(self.ticket("03", ["src/bot/"], commit)))
        self.assertEqual(code, 1, out)
        lines = out.splitlines()
        self.assertEqual(lines[0], "zone · проверено 1 из 1 · вне зоны 1")
        self.assertEqual(lines[1], "  ! таск 03 вне зоны src/bot/: src/db/schema.sql")

    def test_an_unreadable_ticket_exits_three_and_is_named(self):
        commit = self.commit({"src/bot/a.py": "1"})
        state = self.state(self.ticket("01", ["src/bot/"], commit), {"id": "02", "status": "done", "commit": commit})
        code, out = self.check(state)
        self.assertEqual(code, 3, out)
        self.assertIn("проверено 1 из 2", out)
        self.assertIn("  · таск 02 не проверен: у таска нет зоны", out)

    def test_a_certain_finding_wins_over_an_unchecked_ticket(self):
        commit = self.commit({"README.md": "1"})
        state = self.state(self.ticket("01", ["src/bot/"], commit), {"id": "02", "status": "done"})
        self.assertEqual(self.check(state)[0], 1)

    def test_an_unknown_commit_exits_three(self):
        self.commit({"a.txt": "1"})
        code, out = self.check(self.state(self.ticket("01", ["src/"], "deadbeef" * 5)))
        self.assertEqual(code, 3, out)
        self.assertIn("нет в git", out)

    def test_no_done_tickets_is_none(self):
        code, out = self.check(self.state(self.ticket("01", ["src/"], "abcd1234", status="in-progress")))
        self.assertEqual((code, out.split(" · ")[0]), (0, "none"))

    def test_a_ticket_still_in_review_makes_none_say_so(self):
        self.commit({"src/bot/a.py": "1"})
        code, out = self.check(self.state({"id": "01", "status": "review", "zone": ["src/bot/"]}))
        self.assertEqual((code, out.strip()), (0, "none · готовых тасков нет · ещё не готовы: 01 (review)"))

    def test_run_before_the_state_is_written_says_none_and_after_it_judges(self):
        # порядок шага 8 фазы 5: коммит → запись `done` и `commit` в state.js → проверка зон
        commit = self.commit({"src/bot/a.py": "1"})
        before = self.check(self.state({"id": "01", "status": "review", "zone": ["src/bot/"]}))
        after = self.check(self.state(self.ticket("01", ["src/bot/"], commit)))
        self.assertTrue(before[1].startswith("none · "), before)
        self.assertIn("ещё не готовы: 01 (review)", before[1])
        self.assertEqual(after[1].splitlines()[0], "zone · проверено 1 из 1 · вне зоны 0")

    def test_waiting_tickets_are_named_beside_a_verdict(self):
        commit = self.commit({"src/bot/a.py": "1"})
        state = self.state(self.ticket("01", ["src/bot/"], commit), {"id": "02", "status": "pending", "zone": ["src/db/"]})
        code, out = self.check(state)
        self.assertEqual(code, 0, out)
        self.assertEqual(out.splitlines()[0], "zone · проверено 1 из 1 · вне зоны 0 · ещё не готовы: 02 (pending)")

    def test_no_state_means_no_run_here(self):
        (self.root / ".autopilot").mkdir()
        result = self.run_cli("--zone-check", str(self.root / ".autopilot"))
        self.assertEqual((result.returncode, result.stdout.split(" · ")[0]), (0, "none"))

    def test_a_broken_state_needs_a_human(self):
        directory = self.root / ".autopilot"
        directory.mkdir()
        (directory / "state.js").write_text("window.STATE =\n{ не json\n", encoding="utf-8")
        result = self.run_cli("--zone-check", str(directory))
        self.assertEqual((result.returncode, result.stdout.split(" · ")[0]), (3, "unknown"))

    def test_the_mode_writes_nothing_and_commits_nothing(self):
        commit = self.commit({"src/bot/a.py": "1", "src/db/schema.sql": "2"})
        directory = self.write_state(self.state(self.ticket("01", ["src/bot/"], commit)))
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "состояние")
        head, status = git(self.root, "rev-parse", "HEAD"), git(self.root, "status", "--porcelain")
        before = {str(p.relative_to(self.root)): p.read_bytes() for p in sorted(self.root.rglob("*"))
                  if p.is_file() and ".git" not in p.relative_to(self.root).parts}
        self.run_cli("--zone-check", str(directory))
        after = {str(p.relative_to(self.root)): p.read_bytes() for p in sorted(self.root.rglob("*"))
                 if p.is_file() and ".git" not in p.relative_to(self.root).parts}
        self.assertEqual(after, before)
        self.assertEqual((git(self.root, "rev-parse", "HEAD"), git(self.root, "status", "--porcelain")), (head, status))

    def test_a_bad_call_exits_two(self):
        for args in (("--zone-check", "a", "b"), ("--zone-check", "--write")):
            with self.subTest(args=args):
                self.assertEqual(self.run_cli(*args).returncode, 2)


class DispatchTests(unittest.TestCase):
    def test_the_flag_does_not_fall_through_to_the_ordinary_sync(self):
        with mock.patch.object(sys, "argv", ["sync.py", "--zone-check"]), \
                mock.patch.object(sync, "check_zone", return_value=1) as check, \
                mock.patch.object(sync, "read_state", side_effect=AssertionError("ordinary sync ran")), \
                mock.patch.object(sync, "serve", side_effect=AssertionError("server touched")), \
                self.assertRaises(SystemExit) as raised:
            sync.main()
        self.assertEqual(raised.exception.code, 1)
        check.assert_called_once_with(sync.A)


class TheProcedureIsWritten(unittest.TestCase):
    def test_phase_five_runs_the_check_after_the_commit(self):
        text = (SKILL / "phases" / "5-subagents.md").read_text(encoding="utf-8")
        self.assertIn("--zone-check", text)

    def test_phase_five_runs_the_check_after_the_ticket_is_written_down_not_before(self):
        text = (SKILL / "phases" / "5-subagents.md").read_text(encoding="utf-8")
        self.assertIn("written down as `done` with its `commit`", text)
        self.assertIn("has nothing to judge", text)
        self.assertIn("from T1 up", text)

    def test_phase_four_puts_the_tests_of_a_ticket_into_its_zone(self):
        text = (SKILL / "phases" / "4-plan.md").read_text(encoding="utf-8")
        self.assertIn("--zone-check", text)
        self.assertIn("where its tests live", text)


if __name__ == "__main__":
    unittest.main()
