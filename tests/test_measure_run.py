import importlib.util
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


SCRIPT = (Path(__file__).parents[1] / "tools" / "measure-run.py").resolve()
SPEC = importlib.util.spec_from_file_location("measure_run", SCRIPT)
measure_run = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(measure_run)


class PathTests(unittest.TestCase):
    def test_encode_project_path_posix(self):
        self.assertEqual(measure_run.encode_project_path("/Users/alice/project"),
                         "-Users-alice-project")

    def test_encode_project_path_windows(self):
        self.assertEqual(measure_run.encode_project_path(r"C:\Users\Alice\project"),
                         "C--Users-Alice-project")

    def test_logs_dir_for_uses_explicit_root(self):
        root = Path("C:/claude-logs")
        self.assertEqual(measure_run.logs_dir_for("/srv/app", root),
                         root / "-srv-app")

    def test_logs_dir_for_default_root_uses_home_independently_of_cwd(self):
        home = Path("/home/tester")
        project = "/srv/project"
        with mock.patch.object(measure_run.Path, "home", return_value=home), \
                mock.patch.object(measure_run.os, "getcwd", return_value="/first"):
            first = measure_run.logs_dir_for(project)
        with mock.patch.object(measure_run.Path, "home", return_value=home), \
                mock.patch.object(measure_run.os, "getcwd", return_value="/second"):
            second = measure_run.logs_dir_for(project)

        expected = home / ".claude" / "projects" / measure_run.encode_project_path(project)
        self.assertEqual(first, expected)
        self.assertEqual(second, expected)


class AnalyseTests(unittest.TestCase):
    def test_empty_jsonl_returns_zeroed_result(self):
        opened = mock.mock_open(read_data="")
        with mock.patch("builtins.open", opened):
            result = measure_run.analyse("empty.jsonl", "пусто")

        opened.assert_called_once_with("empty.jsonl", encoding="utf-8")
        self.assertEqual(result["label"], "пусто")
        self.assertEqual(result["steps"], 0)
        self.assertEqual(result["avg_ctx"], 0)
        self.assertEqual(result["max_ctx"], 0)
        self.assertEqual(result["norm"], 0)
        self.assertEqual(result["active"], 0)
        self.assertEqual(result["idle"], 0)

    def test_utf8_malformed_jsonl_keeps_valid_nonzero_usage_metrics(self):
        payload = (
            '{"timestamp":"2026-01-01T00:00:00Z","message":'
            '{"role":"assistant","usage":{"input_tokens":11,"output_tokens":7,'
            '"cache_creation_input_tokens":13,"cache_read_input_tokens":17}}}\n'
            '{bad json\n'
            '[]\n'
            '{"timestamp":"2026-01-01T00:00:01","message":'
            '{"role":"assistant","content":[{"text":"ёж"}]}}\n'
        )
        opened = mock.mock_open(read_data=payload)
        with mock.patch("builtins.open", opened):
            result = measure_run.analyse("session.jsonl", "тест")

        opened.assert_called_once_with("session.jsonl", encoding="utf-8")
        self.assertEqual(result["label"], "тест")
        self.assertGreater(result["steps"], 0)
        self.assertGreater(result["avg_ctx"], 0)
        self.assertGreater(result["max_ctx"], 0)
        self.assertGreater(result["out"], 0)
        self.assertGreater(result["write"], 0)
        self.assertGreater(result["read"], 0)
        self.assertGreater(result["norm"], 0)
        self.assertGreater(result["active"], 0)


class StepBreakdownTests(unittest.TestCase):
    def test_classify_kinds(self):
        c = measure_run.classify
        self.assertEqual(c("Agent", {}), "субагент")
        self.assertEqual(c("Bash", {"command": "python3 .autopilot/sync.py"}), "sync.py")
        self.assertEqual(c("Bash", {"command": "sed -i s/a/b/ .autopilot/state.js"}), "правка state.js")
        self.assertEqual(c("Edit", {"file_path": "D:\\p\\.autopilot\\state.js"}), "правка state.js")
        self.assertEqual(c("Bash", {"command": "python -m pytest -q"}), "тесты/сборка")
        self.assertEqual(c("Bash", {"command": "git status --short"}), "git/gh")
        self.assertEqual(c("Bash", {"command": "ls -la"}), "другой Bash")
        self.assertEqual(c("Edit", {"file_path": "/p/tests/test_a.py"}), "правка тестов")
        self.assertEqual(c("Write", {"file_path": "/p/src/a.py"}), "правка кода")
        self.assertEqual(c("Read", {"file_path": "/p/a"}), "чтение (Read/Grep/Glob)")
        self.assertEqual(c("TaskUpdate", {}), "задачи (TaskCreate/Update)")
        self.assertEqual(c("WebSearch", {}), "прочий инструмент")

    def test_step_category_priority_and_text_only(self):
        blocks = [{"type": "tool_use", "name": "Read", "input": {}},
                  {"type": "tool_use", "name": "Bash", "input": {"command": "pytest"}}]
        self.assertEqual(measure_run.step_category(blocks), "тесты/сборка")
        self.assertEqual(measure_run.step_category([{"type": "text", "text": "ok"}]),
                         "ответ без действий")

    def test_analyse_accumulates_cost_per_category(self):
        def row(content, cw=100, cr=1000, out=10):
            return ('{"timestamp":"2026-01-01T00:00:00Z","message":{"role":"assistant",'
                    '"content":%s,"usage":{"input_tokens":1,"output_tokens":%d,'
                    '"cache_creation_input_tokens":%d,"cache_read_input_tokens":%d}}}\n'
                    % (content, out, cw, cr))
        payload = (
            row('[{"type":"tool_use","name":"Bash","input":{"command":"python3 .autopilot/sync.py"}}]')
            + row('[{"type":"tool_use","name":"Read","input":{}}]')
            + row('[{"type":"text","text":"готово"}]')
        )
        with mock.patch("builtins.open", mock.mock_open(read_data=payload)):
            result = measure_run.analyse("s.jsonl", "тест")
        self.assertEqual(result["cats"]["sync.py"][0], 1)
        self.assertEqual(result["cats"]["чтение (Read/Grep/Glob)"][0], 1)
        self.assertEqual(result["cats"]["ответ без действий"][0], 1)
        total = sum(v[1] for v in result["cats"].values())
        self.assertAlmostEqual(total, result["norm"])

    def test_rows_of_one_message_are_counted_once(self):
        def row(mid, content, out):
            return ('{"timestamp":"2026-01-01T00:00:00Z","message":{"id":"%s","role":"assistant",'
                    '"content":%s,"usage":{"input_tokens":1,"output_tokens":%d,'
                    '"cache_creation_input_tokens":100,"cache_read_input_tokens":1000}}}\n'
                    % (mid, content, out))
        payload = (
            row("m1", '[{"type":"thinking","thinking":"..."}]', 3)
            + row("m1", '[{"type":"text","text":"иду читать"}]', 5)
            + row("m1", '[{"type":"tool_use","name":"Read","input":{}}]', 9)
            + row("m2", '[{"type":"text","text":"готово"}]', 4)
        )
        with mock.patch("builtins.open", mock.mock_open(read_data=payload)):
            result = measure_run.analyse("s.jsonl", "тест")
        self.assertEqual(result["steps"], 2)
        self.assertEqual(result["out"], 9 + 4)
        self.assertEqual(result["write"], 200)
        self.assertEqual(result["cats"]["чтение (Read/Grep/Glob)"][0], 1)
        self.assertEqual(result["cats"]["ответ без действий"][0], 1)

    def test_samples_describe_expensive_actions(self):
        payload = (
            '{"timestamp":"2026-01-01T00:00:00Z","message":{"id":"a","role":"assistant","content":'
            '[{"type":"tool_use","name":"Bash","input":{"command":"ls   -la  /tmp"}}],'
            '"usage":{"input_tokens":1,"output_tokens":2,"cache_creation_input_tokens":10,'
            '"cache_read_input_tokens":100}}}\n'
        )
        with mock.patch("builtins.open", mock.mock_open(read_data=payload)):
            result = measure_run.analyse("s.jsonl", "тест")
        self.assertEqual(len(result["samples"]), 1)
        cat, desc, cost = result["samples"][0]
        self.assertEqual((cat, desc), ("другой Bash", "ls -la /tmp"))
        self.assertGreater(cost, 0)
        output = io.StringIO()
        with mock.patch("sys.stdout", output):
            measure_run.print_steps([dict(result, label="Оркестратор")])
        self.assertIn("ls -la /tmp", output.getvalue())

    def test_print_steps_outputs_table(self):
        cats = {c: [0, 0.0] for c in measure_run.CATS}
        cats["sync.py"] = [2, 500000.0]
        result = {"label": "Оркестратор", "cats": cats}
        output = io.StringIO()
        with mock.patch("sys.stdout", output):
            measure_run.print_steps([result])
        text = output.getvalue()
        self.assertIn("Оркестратор", text)
        self.assertIn("sync.py", text)


class CliTests(unittest.TestCase):
    def test_check_only_succeeds_without_logs(self):
        output = io.StringIO()
        with mock.patch("sys.stdout", output):
            code = measure_run.main(["--check-only"])

        self.assertEqual(code, 0)
        self.assertIn("check-only: OK", output.getvalue())

    def test_check_only_subprocess_is_independent_of_cwd(self):
        completed = subprocess.run(
            [sys.executable, "-B", str(SCRIPT), "--check-only"],
            cwd=tempfile.gettempdir(),
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("measure-run check-only: OK", completed.stdout)

    def test_main_session_selection_is_independent_of_glob_order(self):
        result = {
            "label": "Оркестратор", "steps": 0, "avg_ctx": 0, "max_ctx": 0,
            "over": 0, "out": 0, "write": 0, "read": 0, "cold": 0,
            "norm": 0, "active": 0, "idle": 0, "test_edits": 0,
            "code_edits": 0, "test_runs": 0,
        }

        def selected(order):
            def fake_glob(pattern):
                return order if "subagents" not in pattern and pattern.endswith("*.jsonl") else []

            with mock.patch.object(measure_run, "logs_dir_for", return_value=Path("logs")), \
                    mock.patch.object(measure_run.os.path, "isdir", return_value=True), \
                    mock.patch.object(measure_run.os.path, "getsize", return_value=1), \
                    mock.patch.object(measure_run.glob, "glob", side_effect=fake_glob), \
                    mock.patch.object(measure_run, "analyse", return_value=result) as analyse, \
                    mock.patch("sys.stdout", io.StringIO()):
                self.assertEqual(measure_run.main(["project"]), 0)
            return analyse.call_args_list[0].args[0]

        first = selected(["logs/bbbbbbbb.jsonl", "logs/aaaaaaaa.jsonl"])
        second = selected(["logs/aaaaaaaa.jsonl", "logs/bbbbbbbb.jsonl"])
        self.assertEqual(first, second)


class AuditFixesTests(unittest.TestCase):
    def test_test_paths_are_recognised_with_both_separators(self):
        for path in (r"C:\proj\tests\helpers.py", "/p/tests/helpers.py", "tests/helpers.py", "/p/test_x.py", "a.test.js"):
            with self.subTest(path=path):
                self.assertTrue(measure_run.is_test_path(path))
        for path in (r"C:\proj\src\app.py", "/p/src/contest.py", ""):
            with self.subTest(path=path):
                self.assertFalse(measure_run.is_test_path(path))

    def test_analyse_counts_windows_test_edits_as_test_edits(self):
        row = ('{"timestamp":"2026-01-01T00:00:00Z","message":{"role":"assistant","content":'
               '[{"type":"tool_use","name":"Edit","input":{"file_path":"C:\\\\p\\\\tests\\\\helpers.py"}}],'
               '"usage":{"input_tokens":1,"output_tokens":1}}}\n')
        with mock.patch("builtins.open", mock.mock_open(read_data=row)):
            result = measure_run.analyse("s.jsonl", "тест")
        self.assertEqual((result["test_edits"], result["code_edits"]), (1, 0))

    def _run_main(self, files, argv):
        with tempfile.TemporaryDirectory() as tmp:
            logs = Path(tmp)
            for name, text in files.items():
                target = logs / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(text, encoding="utf-8")
            stderr = io.StringIO()
            with mock.patch.object(measure_run, "logs_dir_for", return_value=logs), \
                    mock.patch.object(sys, "stderr", stderr), mock.patch.object(sys, "stdout", io.StringIO()):
                code = measure_run.main(argv)
            return code, stderr.getvalue()

    def test_a_broken_subagent_meta_does_not_stop_the_report(self):
        code, _err = self._run_main({"abc.jsonl": "{}\n", "abc/subagents/x.jsonl": "{}\n",
                                     "abc/subagents/x.meta.json": "{oops"}, ["/p"])
        self.assertEqual(code, 0)

    def test_an_ambiguous_session_id_is_named_not_guessed(self):
        code, err = self._run_main({"abc111.jsonl": "{}\n", "abc222.jsonl": "{}\n"}, ["/p", "abc"])
        self.assertEqual(code, 1)
        self.assertIn("abc111", err)
        self.assertIn("abc222", err)

    def test_an_exact_session_id_wins_over_longer_names(self):
        code, _err = self._run_main({"abc.jsonl": "{}\n", "abc2.jsonl": "{}\n"}, ["/p", "abc"])
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
