import importlib.util
import io
from pathlib import Path
import unittest
from unittest import mock


SCRIPT = Path(__file__).parents[1] / "tools" / "measure-run.py"
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

    def test_utf8_malformed_jsonl_mixed_timestamps_and_zero_counters(self):
        payload = (
            '{"timestamp":"2026-01-01T00:00:00Z","message":'
            '{"role":"assistant","usage":{"output_tokens":0}}}\n'
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
        self.assertEqual(result["steps"], 0)
        self.assertEqual(result["norm"], 0)


class CliTests(unittest.TestCase):
    def test_check_only_succeeds_without_logs(self):
        output = io.StringIO()
        with mock.patch("sys.stdout", output):
            code = measure_run.main(["--check-only"])

        self.assertEqual(code, 0)
        self.assertIn("check-only: OK", output.getvalue())

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


if __name__ == "__main__":
    unittest.main()
