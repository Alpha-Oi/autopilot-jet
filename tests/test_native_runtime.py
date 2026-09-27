"""Cold native checks; fixtures never use real home logs or start a server."""

import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "skills" / "autopilot" / "tools" / "sync.py"
MEASURE = ROOT / "tools" / "measure-run.py"


class ColdRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.fixture = tempfile.TemporaryDirectory(prefix="native roots ")
        self.addCleanup(self.fixture.cleanup)
        self.base = Path(self.fixture.name).resolve() / "проверка Unicode"
        self.base.mkdir()
        self.cwd = self.base / "чужой cwd"
        self.cwd.mkdir()
        self.home = self.base / "isolated home ё"
        self.home.mkdir()
        self.child_env = os.environ.copy()
        self.child_env.update({
            "HOME": str(self.home),
            "USERPROFILE": str(self.home),
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUTF8": "1",
        })

    def run_cli(self, script, *args, cwd=None):
        return subprocess.run(
            [sys.executable, "-B", str(script), *args],
            cwd=cwd or self.cwd,
            env=self.child_env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=20,
            check=False,
        )

    def logs_for(self, project):
        # The expected fixture directory follows the literal Claude encoding
        # contract, not the resolver/encoder under test.
        spelling = str(project)
        encoded = "".join("-" if char in ":/\\" else char for char in spelling)
        return self.home / ".claude" / "projects" / encoded

    def write_usage_log(self, path, output_tokens, input_tokens=1000,
                        cache_write=4000, cache_read=5000):
        row = {
            "timestamp": "2026-01-01T00:00:00Z",
            "message": {
                "role": "assistant",
                "usage": {"input_tokens": input_tokens,
                          "output_tokens": output_tokens,
                          "cache_creation_input_tokens": cache_write,
                          "cache_read_input_tokens": cache_read},
                "content": [{"type": "tool_use", "name": "Write",
                             "input": {"file_path": "tests/test_fixture.py"}},
                            {"type": "tool_use", "name": "Bash",
                             "input": {"command": "python -m unittest"}}],
            },
        }
        later = {"timestamp": "2026-01-01T00:01:00Z",
                 "message": {"role": "assistant", "content": [
                     {"type": "tool_use", "name": "Write",
                      "input": {"file_path": "src/fixture.py"}},
                     {"text": "Unicode ё"}]}}
        path.write_text(json.dumps(row, ensure_ascii=False) + "\n{broken\n[]\n"
                        + json.dumps(later, ensure_ascii=False) + "\n",
                        encoding="utf-8")

    def test_relocated_helper_updates_only_its_adjacent_snapshot(self):
        runtime = self.base / "перенесённый project" / ".autopilot"
        runtime.mkdir(parents=True)
        helper = runtime / "sync.py"
        shutil.copyfile(HELPER, helper)
        state = {"updatedAt": "2026-01-02T03:04:05Z", "note": "ёж </script>",
                 "stages": [], "tickets": []}
        state_path = runtime / "state.js"
        state_path.write_text("window.STATE=" + json.dumps(state, ensure_ascii=False),
                              encoding="utf-8")
        original_state = state_path.read_bytes()
        page = runtime / "dashboard.html"
        page.write_text("prefix /*STATE-BEGIN*/old/*STATE-END*/ suffix",
                        encoding="utf-8")
        decoys = []
        for directory in (self.cwd, self.cwd / ".autopilot"):
            directory.mkdir(exist_ok=True)
            for name in ("state.js", "dashboard.html", "serve.pid", "serve.log"):
                path = directory / name
                path.write_text("foreign " + name + " ё", encoding="utf-8")
                decoys.append((path, path.read_bytes()))

        completed = self.run_cli(helper, "--no-serve")

        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("сервер не проверялся", completed.stdout)
        snapshot = page.read_text(encoding="utf-8")
        self.assertTrue(snapshot.startswith("prefix /*STATE-BEGIN*/window.STATE="))
        self.assertTrue(snapshot.endswith(";/*STATE-END*/ suffix"))
        payload = snapshot.split("/*STATE-BEGIN*/window.STATE=", 1)[1]
        payload = payload.split(";/*STATE-END*/", 1)[0]
        self.assertEqual(json.loads(payload), state)
        self.assertNotIn("</script>", snapshot)
        self.assertEqual(state_path.read_bytes(), original_state)
        self.assertEqual({path.name for path in runtime.iterdir()},
                         {"sync.py", "state.js", "dashboard.html"})
        for path, before in decoys:
            self.assertEqual(path.read_bytes(), before, str(path))

        before = page.read_bytes()
        repeated = self.run_cli(helper, "--no-serve", cwd=self.home)
        self.assertEqual(repeated.returncode, 0, repeated.stdout + repeated.stderr)
        self.assertEqual(page.read_bytes(), before)

    def test_relocated_helper_rejects_corrupt_state_without_writes(self):
        runtime = self.base / "ошибочный project" / ".autopilot"
        runtime.mkdir(parents=True)
        helper = runtime / "sync.py"
        shutil.copyfile(HELPER, helper)
        for name, contents in (("state.js", "window.STATE={broken"),
                               ("dashboard.html", "previous snapshot ё"),
                               ("serve.pid", "fixture pid"),
                               ("serve.log", "fixture log")):
            (runtime / name).write_text(contents, encoding="utf-8")
        before = {path.name: path.read_bytes() for path in runtime.iterdir()}

        completed = self.run_cli(helper, "--no-serve")

        self.assertEqual(completed.returncode, 1, completed.stderr)
        self.assertIn("state.js не разбирается", completed.stdout)
        self.assertNotIn("Traceback", completed.stdout + completed.stderr)
        self.assertEqual({path.name: path.read_bytes() for path in runtime.iterdir()},
                         before)

    def test_cold_measure_cli_uses_isolated_home_and_native_project_paths(self):
        project = self.base / "measure project ё"
        project.mkdir()
        logs = self.logs_for(project)
        logs.mkdir(parents=True)
        main_log = logs / "main0001.jsonl"
        other_log = logs / "other002.jsonl"
        self.write_usage_log(main_log, 100000)
        self.write_usage_log(other_log, 800000)
        with other_log.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"text": "larger unrelated session" * 200}))
        agents = logs / "main0001" / "subagents"
        agents.mkdir(parents=True)
        self.write_usage_log(agents / "agent-one.jsonl", 20000, 5000, 0, 0)
        (agents / "agent-one.meta.json").write_text(
            json.dumps({"description": "fixture агент ё"}, ensure_ascii=False),
            encoding="utf-8")

        for spelling, cwd in ((str(project), self.cwd),
                              (os.path.relpath(project, self.cwd), self.cwd),
                              (str(project), self.home)):
            with self.subTest(project=spelling, cwd=str(cwd)):
                completed = self.run_cli(MEASURE, spelling, cwd=cwd)
                self.assertEqual(completed.returncode, 0, completed.stderr)
                self.assertIn("Взята main0001 (1 субагентов)", completed.stdout)
                self.assertIn("контекстов: 2", completed.stdout)
                self.assertIn("fixture агент ё", completed.stdout)
                self.assertRegex(completed.stdout,
                                 r"Оркестратор\s+1\s+10K\s+10K\s+0\s+0\.51M")
                self.assertRegex(completed.stdout, r"ИТОГО\s+2\s+0\.61M")
                self.assertIn("правки тестов к правкам кода: 2/2", completed.stdout)
                self.assertIn("прогонов тестов: 2", completed.stdout)
                self.assertIn("активно 2 мин", completed.stdout)
                self.assertNotIn("4.01M", completed.stdout)

        selected = self.run_cli(MEASURE, str(project), "other002")
        self.assertEqual(selected.returncode, 0, selected.stderr)
        self.assertIn("Взята other002 (0 субагентов)", selected.stdout)
        self.assertIn("контекстов: 1", selected.stdout)
        self.assertRegex(selected.stdout, r"ИТОГО\s+1\s+4\.01M")
        self.assertNotIn("fixture агент ё", selected.stdout)

    def test_cold_measure_cli_reports_controlled_fixture_errors(self):
        project = self.base / "missing logs project ё"
        project.mkdir()
        logs = self.logs_for(project)

        missing = self.run_cli(MEASURE, str(project))
        self.assertEqual(missing.returncode, 1)
        self.assertIn("нет логов: " + str(logs), missing.stderr)
        self.assertNotIn("Traceback", missing.stdout + missing.stderr)

        logs.mkdir(parents=True)
        empty = self.run_cli(MEASURE, str(project))
        self.assertEqual(empty.returncode, 1)
        self.assertIn("нет .jsonl", empty.stderr)
        self.assertIn(str(logs), empty.stderr)
        self.assertNotIn("Traceback", empty.stdout + empty.stderr)

        self.write_usage_log(logs / "exists01.jsonl", 100000)
        unknown = self.run_cli(MEASURE, str(project), "absent-session")
        self.assertEqual(unknown.returncode, 1)
        self.assertIn("сессия absent-session не найдена", unknown.stderr)
        self.assertIn(str(logs), unknown.stderr)
        self.assertNotIn("Traceback", unknown.stdout + unknown.stderr)

        no_project = self.run_cli(MEASURE)
        self.assertEqual(no_project.returncode, 2)
        self.assertIn("usage:", no_project.stderr)
        self.assertNotIn("Traceback", no_project.stdout + no_project.stderr)


class NativeProcessTests(unittest.TestCase):
    def test_own_pid_has_native_python_command_line(self):
        spec = importlib.util.spec_from_file_location("native_sync", HELPER)
        helper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(helper)

        command = helper.cmdline(os.getpid())

        self.assertTrue(command, "Native own-PID query returned unknown/empty")
        self.assertIn("python", command.casefold())
        self.assertIn("unittest", command.casefold())


if __name__ == "__main__":
    unittest.main()
