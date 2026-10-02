"""План отката круга доводки (REQ-CORE-10 стандарта DOA: обратимость).

`phases/polish.md`: круг, который сломал сборку, откатывается целиком, а не чинится. Раньше команды отката агент
придумывал сам, и ошибиться было просто: не те коммиты, не тот порядок, `git reset --hard` по пути.
`sync.py --rollback-plan` читает `polish.baseCommit` и коммиты тасков последнего круга, сверяет их с git (только
чтение) и печатает одну команду `git revert --no-edit …` новыми коммитами вперёд. Это приговор и подсказка, а не
запрет: что агент запускает именно её, остаётся инструкцией.

Главный тест здесь — репетиция: напечатанная команда выполняется на настоящем репозитории, и дерево возвращается
к состоянию до круга, не трогая чужие коммиты и не переписывая историю.
"""

import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


SKILL = Path(__file__).parents[1] / "skills" / "autopilot-jet"
SCRIPT = SKILL / "tools" / "sync.py"
SPEC = importlib.util.spec_from_file_location("autopilot_sync_rollback", SCRIPT)
sync = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync)

BASE = "a" * 40
P1, P2, P3 = "1" * 40, "2" * 40, "3" * 40
OTHER = "9" * 40


def git(cwd, *args):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "commit.gpgsign=false",
                           *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8", check=True).stdout.strip()


def history(*rows):
    """Подложная история: (хеш, число родителей), новые первыми."""
    return lambda root, base: (list(rows), None)


def state(rounds, tickets, base=BASE):
    return {"polish": {"baseCommit": base, "rounds": rounds}, "tickets": tickets}


def ticket(name, commit):
    return {"id": name, "status": "done", "commit": commit}


class PlanTests(unittest.TestCase):
    def plan(self, st, rows=((P3, 1), (P2, 1), (P1, 1), (OTHER, 1))):
        return sync.rollback_plan(st, "/nowhere", history_of=history(*rows))

    def test_there_is_nothing_to_roll_back_without_a_polish_round(self):
        for polish in (None, {}, {"rounds": []}, {"rounds": None}, {"rounds": "x"}, {"rounds": [None]}, "x", 5):
            with self.subTest(polish=polish):
                self.assertEqual(sync.rollback_plan({"polish": polish}, "/nowhere")[0], "none")
        self.assertEqual(sync.rollback_plan({}, "/nowhere")[0], "none")

    def test_a_round_without_tickets_has_nothing_to_roll_back(self):
        for names in ([], None, "P1", 7):
            with self.subTest(tickets=names):
                self.assertEqual(self.plan(state([{"n": 1, "tickets": names}], []))[0], "none")

    def test_the_last_round_only_and_newest_commit_first(self):
        st = state([{"n": 1, "tickets": ["P1"]}, {"n": 2, "tickets": ["P2", "P3"]}],
                   [ticket("P1", P1), ticket("P2", P2), ticket("P3", P3)])
        self.assertEqual(self.plan(st), ("plan", (2, [("P3", P3), ("P2", P2)])))

    def test_the_order_follows_the_history_not_the_order_of_the_tickets(self):
        st = state([{"n": 1, "tickets": ["P1", "P2"]}], [ticket("P1", P1), ticket("P2", P2)])
        self.assertEqual(self.plan(st)[1][1], [("P2", P2), ("P1", P1)])
        st["polish"]["rounds"][0]["tickets"] = ["P2", "P1"]
        self.assertEqual(self.plan(st)[1][1], [("P2", P2), ("P1", P1)])

    def test_commits_of_other_tickets_between_the_round_are_left_alone(self):
        st = state([{"n": 1, "tickets": ["P1", "P3"]}], [ticket("P1", P1), ticket("P3", P3)])
        rows = ((P3, 1), (OTHER, 1), (P1, 1))
        self.assertEqual(self.plan(st, rows)[1][1], [("P3", P3), ("P1", P1)])

    def test_a_short_commit_in_the_record_is_matched_to_the_full_hash(self):
        st = state([{"n": 1, "tickets": ["P1"]}], [ticket("P1", P1[:7].upper())])
        self.assertEqual(self.plan(st)[1][1], [("P1", P1)])

    def test_the_case_of_a_hash_in_the_record_does_not_matter(self):
        full = "abcdef" + "0" * 34
        st = state([{"n": 1, "tickets": ["P1"]}], [ticket("P1", "ABCDEF0")])
        self.assertEqual(self.plan(st, rows=((full, 1),))[1][1], [("P1", full)])

    def test_a_numeric_ticket_id_is_matched_as_text(self):
        st = state([{"n": 1, "tickets": [4]}], [ticket(4, P1)])
        self.assertEqual(self.plan(st)[1][1], [("4", P1)])

    def test_without_a_base_commit_nothing_is_planned(self):
        for base in (None, "", 5, "--exec=x", "not hex", "ab"):
            with self.subTest(base=base):
                st = state([{"n": 1, "tickets": ["P1"]}], [ticket("P1", P1)], base=base)
                self.assertEqual(self.plan(st)[0], "unplanned")

    def test_a_ticket_that_is_not_recorded_or_has_no_commit_is_not_planned(self):
        rounds = [{"n": 1, "tickets": ["P1"]}]
        for tickets in ([], [{"id": "P1", "status": "done"}], [ticket("P1", "")], [ticket("P1", "--force")],
                        [ticket("P1", 5)], [None, 5]):
            with self.subTest(tickets=tickets):
                self.assertEqual(self.plan(state(rounds, tickets))[0], "unplanned")

    def test_a_commit_that_is_not_between_the_base_and_head_is_not_planned(self):
        st = state([{"n": 1, "tickets": ["P1"]}], [ticket("P1", P1)])
        status, why = self.plan(st, rows=((P2, 1),))
        self.assertEqual(status, "unplanned")
        self.assertIn("нет между baseCommit и HEAD", why)

    def test_an_ambiguous_short_commit_is_not_planned(self):
        st = state([{"n": 1, "tickets": ["P1"]}], [ticket("P1", "1111")])
        self.assertEqual(self.plan(st, rows=(("1111" + "a" * 36, 1), ("1111" + "b" * 36, 1)))[0], "unplanned")

    def test_a_merge_commit_is_not_planned(self):
        st = state([{"n": 1, "tickets": ["P1"]}], [ticket("P1", P1)])
        status, why = self.plan(st, rows=((P1, 2),))
        self.assertEqual(status, "unplanned")
        self.assertIn("слияние", why)

    def test_git_that_does_not_answer_is_the_reason(self):
        st = state([{"n": 1, "tickets": ["P1"]}], [ticket("P1", P1)])
        self.assertEqual(sync.rollback_plan(st, "/x", history_of=lambda r, b: (None, "git не ответил")),
                         ("unplanned", "git не ответил"))

    def test_the_plan_does_not_change_the_state(self):
        st = state([{"n": 1, "tickets": ["P1"]}], [ticket("P1", P1)])
        before = json.dumps(st, sort_keys=True)
        self.plan(st)
        self.assertEqual(json.dumps(st, sort_keys=True), before)


class Repo(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="rollback plan ")
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

    def write_state(self, st):
        directory = self.root / ".autopilot"
        directory.mkdir(exist_ok=True)
        (directory / "state.js").write_text("window.STATE =\n" + json.dumps(st, indent=2) + "\n", encoding="utf-8")
        return directory

    def cli(self, st):
        result = subprocess.run([sys.executable, "-X", "utf8", "-B", str(SCRIPT), "--rollback-plan",
                                 str(self.write_state(st))], capture_output=True, text=True, encoding="utf-8",
                                timeout=60, check=False)
        return result.returncode, result.stdout


class HistoryTests(Repo):
    def test_commits_come_newest_first_with_their_parent_counts(self):
        base = self.commit({"a.txt": "0"})
        one = self.commit({"b.txt": "1"})
        two = self.commit({"c.txt": "2"})
        self.assertEqual(sync.commits_since(str(self.root), base), ([(two, 1), (one, 1)], None))

    def test_the_base_itself_is_not_part_of_the_range(self):
        base = self.commit({"a.txt": "0"})
        self.assertEqual(sync.commits_since(str(self.root), base), ([], None))

    def test_a_base_that_git_does_not_know_is_a_reason_not_an_empty_list(self):
        self.commit({"a.txt": "0"})
        rows, why = sync.commits_since(str(self.root), "b" * 40)
        self.assertIsNone(rows)
        self.assertIn("нет в git", why)

    def test_a_base_outside_the_history_of_the_branch_is_a_reason(self):
        self.commit({"a.txt": "0"})
        git(self.root, "checkout", "-q", "-b", "other")
        stray = self.commit({"x.txt": "x"})
        git(self.root, "checkout", "-q", "-")
        rows, why = sync.commits_since(str(self.root), stray)
        self.assertIsNone(rows)
        self.assertIn("не лежит в истории", why)

    def test_a_merge_commit_shows_two_parents(self):
        base = self.commit({"a.txt": "0"})
        branch = git(self.root, "rev-parse", "--abbrev-ref", "HEAD")
        git(self.root, "checkout", "-q", "-b", "side")
        self.commit({"s.txt": "s"})
        git(self.root, "checkout", "-q", branch)
        self.commit({"m.txt": "m"})
        git(self.root, "merge", "-q", "--no-ff", "-m", "слияние", "side")
        rows, _ = sync.commits_since(str(self.root), base)
        self.assertEqual(rows[0][1], 2)


class RehearsalTests(Repo):
    """Репетиция отката: напечатанную команду выполняют, и дерево возвращается к состоянию до круга."""

    def project(self):
        base = self.commit({"app/main.py": "v0\n", "README.md": "r\n"}, "основа")
        p1 = self.commit({"app/main.py": "v0\npolish 1\n"}, "доводка P1")
        other = self.commit({"app/other.py": "other\n"}, "таск 07")
        p2 = self.commit({"app/main.py": "v0\npolish 1\npolish 2\n", "app/new.py": "new\n"}, "доводка P2")
        st = {"polish": {"baseCommit": base, "rounds": [{"n": 1, "tickets": ["P1", "P2"]}]},
              "tickets": [ticket("P1", p1), ticket("P2", p2)]}
        return base, p1, other, p2, st

    def printed_command(self, st):
        code, out = self.cli(st)
        self.assertEqual(code, 0, out)
        line = out.splitlines()[0]
        return shlex.split(line.split(" · ", 3)[3])

    def test_the_printed_command_takes_the_round_back_and_leaves_the_rest(self):
        _base, _p1, _other, _p2, st = self.project()
        command = self.printed_command(st)
        self.assertEqual(command[:3], ["git", "revert", "--no-edit"])
        before = git(self.root, "rev-parse", "HEAD")
        git(self.root, *command[1:])
        self.assertEqual((self.root / "app" / "main.py").read_text(encoding="utf-8"), "v0\n")
        self.assertFalse((self.root / "app" / "new.py").exists())
        self.assertEqual((self.root / "app" / "other.py").read_text(encoding="utf-8"), "other\n")
        self.assertEqual((self.root / "README.md").read_text(encoding="utf-8"), "r\n")
        self.assertEqual(git(self.root, "status", "--porcelain", "--untracked-files=no"), "")
        self.assertEqual(git(self.root, "merge-base", before, "HEAD"), before)     # история только выросла
        self.assertNotEqual(git(self.root, "rev-parse", "HEAD"), before)

    def test_the_tree_after_the_rollback_equals_the_tree_without_the_round(self):
        base, _p1, other, _p2, st = self.project()
        git(self.root, *self.printed_command(st)[1:])
        # то же дерево, что и у основы с одним чужим таском поверх
        expected = self.root.parent / (self.root.name + " expected")
        subprocess.run(["git", "clone", "-q", str(self.root), str(expected)], check=True, capture_output=True)
        self.addCleanup(lambda: __import__("shutil").rmtree(expected, ignore_errors=True))
        git(expected, "checkout", "-q", base)
        git(expected, "cherry-pick", other)
        self.assertEqual(git(self.root, "rev-parse", "HEAD^{tree}"), git(expected, "rev-parse", "HEAD^{tree}"))

    def test_a_dirty_tree_stops_the_revert_instead_of_losing_work(self):
        _base, _p1, _other, _p2, st = self.project()
        command = self.printed_command(st)
        (self.root / "app" / "main.py").write_text("мои несохранённые правки\n", encoding="utf-8")
        result = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *command[1:]],
                                cwd=self.root, capture_output=True, text=True, encoding="utf-8")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.root / "app" / "main.py").read_text(encoding="utf-8"), "мои несохранённые правки\n")

    def test_the_command_names_every_commit_of_the_round_and_no_other(self):
        _base, p1, other, p2, st = self.project()
        command = self.printed_command(st)
        self.assertEqual(command[3:], [p2, p1])
        self.assertNotIn(other, command)


class CliTests(Repo):
    def test_the_report_names_the_round_the_command_and_every_ticket(self):
        base = self.commit({"a.txt": "0"})
        p1 = self.commit({"b.txt": "1"})
        code, out = self.cli({"polish": {"baseCommit": base, "rounds": [{"n": 3, "tickets": ["P1"]}]},
                              "tickets": [ticket("P1", p1)]})
        self.assertEqual(code, 0, out)
        lines = out.splitlines()
        self.assertEqual(lines[0], "rollback · круг 3 · коммитов 1 · git revert --no-edit " + p1)
        self.assertEqual(lines[1], "  · таск P1 · " + p1[:12])

    def test_no_polish_exits_one(self):
        self.commit({"a.txt": "0"})
        code, out = self.cli({"tickets": []})
        self.assertEqual(code, 1, out)
        self.assertTrue(out.startswith("none · откатывать нечего"), out)

    def test_a_round_that_cannot_be_planned_exits_three_and_says_why(self):
        base = self.commit({"a.txt": "0"})
        code, out = self.cli({"polish": {"baseCommit": base, "rounds": [{"n": 1, "tickets": ["P1"]}]},
                              "tickets": [{"id": "P1", "status": "done"}]})
        self.assertEqual(code, 3, out)
        self.assertIn("у таска P1 нет commit", out)

    def test_no_state_means_no_run_here(self):
        (self.root / ".autopilot").mkdir()
        result = subprocess.run([sys.executable, "-X", "utf8", "-B", str(SCRIPT), "--rollback-plan",
                                 str(self.root / ".autopilot")], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0)
        self.assertTrue(result.stdout.startswith("none · state.js нет"), result.stdout)

    def test_a_broken_state_is_unknown_not_a_crash(self):
        directory = self.root / ".autopilot"
        directory.mkdir()
        (directory / "state.js").write_text("window.STATE =\n{нет\n", encoding="utf-8")
        result = subprocess.run([sys.executable, "-X", "utf8", "-B", str(SCRIPT), "--rollback-plan", str(directory)],
                                capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 3)
        self.assertTrue(result.stdout.startswith("unknown · "), result.stdout)

    def test_a_second_directory_or_another_flag_is_a_usage_error(self):
        for args in (["a", "b"], ["--wat"]):
            with self.subTest(args=args):
                result = subprocess.run([sys.executable, "-X", "utf8", "-B", str(SCRIPT), "--rollback-plan", *args],
                                        capture_output=True, text=True, encoding="utf-8")
                self.assertEqual(result.returncode, 2)
                self.assertIn("использование", result.stdout)


class DispatchTests(unittest.TestCase):
    def test_the_flag_does_not_fall_through_to_the_ordinary_sync(self):
        with mock.patch.object(sys, "argv", ["sync.py", "--rollback-plan"]), \
                mock.patch.object(sync, "check_rollback_plan", return_value=1) as check, \
                mock.patch.object(sync, "read_state", side_effect=AssertionError("ordinary sync ran")), \
                mock.patch.object(sync, "serve", side_effect=AssertionError("server touched")), \
                contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as raised:
            sync.main()
        self.assertEqual(raised.exception.code, 1)
        check.assert_called_once_with(sync.A)


class TheProcedureIsWritten(unittest.TestCase):
    def text(self):
        return (SKILL / "phases" / "polish.md").read_text(encoding="utf-8")

    def test_the_regression_rule_names_the_plan_command(self):
        self.assertIn("--rollback-plan", self.text())

    def test_the_rollback_runs_the_printed_command_and_nothing_destructive(self):
        text = self.text()
        self.assertIn("git revert --no-edit", text)
        self.assertIn("never `git reset --hard`", text)

    def test_a_plan_that_could_not_be_built_goes_to_the_user(self):
        self.assertIn("unplanned", self.text())


if __name__ == "__main__":
    unittest.main()
