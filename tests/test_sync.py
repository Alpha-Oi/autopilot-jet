import base64
import importlib.util
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock


SCRIPT = Path(__file__).parents[1] / "skills" / "autopilot-jet" / "tools" / "sync.py"
SPEC = importlib.util.spec_from_file_location("autopilot_sync", SCRIPT)
sync = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync)


def b64(text):
    """Так строку запуска процесса отдаёт PowerShell на Windows: base64 от UTF-8 (см. POWERSHELL_BASE64 в sync.py)."""
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


class ProcessQueryTests(unittest.TestCase):
    def test_failed_queries_do_not_confirm_partial_stdout(self):
        for platform in ("nt", "posix"):
            with self.subTest(platform=platform), \
                    mock.patch.object(sync.os, "name", platform), \
                    mock.patch.object(sync.subprocess, "run", return_value=
                                      subprocess.CompletedProcess(
                                          [], 1, stdout="42 python -m http.server", stderr="denied")):
                self.assertEqual(sync.cmdline(42), "")
                self.assertEqual(sync.iter_processes(), [])

    def test_cmdline_windows_uses_non_shell_system_query(self):
        completed = subprocess.CompletedProcess([], 0, stdout=b64("python -m http.server"), stderr="")

        with mock.patch.object(sync.os, "name", "nt"), \
                mock.patch.object(sync.subprocess, "run", return_value=completed) as run:
            result = sync.cmdline(42)

        self.assertEqual(result, "python -m http.server")
        args, kwargs = run.call_args
        self.assertNotEqual(args[0][0], "ps")
        self.assertIs(kwargs.get("shell", False), False)

    def test_windows_queries_get_a_wider_timeout_than_ps(self):
        completed = subprocess.CompletedProcess([], 0, stdout="present", stderr="")
        queries = (lambda: sync.cmdline(42), lambda: sync.process_status(42), sync.iter_processes)
        timeouts = {}
        for platform in ("nt", "posix"):
            seen = []
            for query in queries:
                with mock.patch.object(sync.os, "name", platform), \
                        mock.patch.object(sync.subprocess, "run", return_value=completed) as run:
                    query()
                seen.append(run.call_args.kwargs["timeout"])
            timeouts[platform] = seen
        self.assertEqual(timeouts["posix"], [5, 5, 10])
        for windows, posix in zip(timeouts["nt"], timeouts["posix"]):
            self.assertGreater(windows, posix)

    def test_iter_processes_windows_parses_safe_query(self):
        delimiter = sync.PROCESS_DELIMITER
        completed = subprocess.CompletedProcess(
            [], 0,
            stdout=("42%s%s\n77%s%s\n"
                    % (delimiter, b64("python -m http.server"), delimiter, b64("other.exe"))),
            stderr="")

        with mock.patch.object(sync.os, "name", "nt"), \
                mock.patch.object(sync.subprocess, "run", return_value=completed) as run:
            result = sync.iter_processes()

        self.assertEqual(result, [(42, "python -m http.server"), (77, "other.exe")])
        self.assertNotEqual(run.call_args.args[0][0], "ps")
        self.assertIs(run.call_args.kwargs.get("shell", False), False)
        self.assertIn("[char]31", run.call_args.args[0][-1])

    def test_is_ours_requires_exact_directory_argument(self):
        with mock.patch.object(sync, "A", r"C:\runs\active"):
            self.assertTrue(sync.is_ours(
                r'python -m http.server 8000 --directory "C:\runs\active"'))
            self.assertFalse(sync.is_ours(
                r'python -m http.server 8000 --directory "C:\runs\active-old"'))

    def test_posix_queries_and_unavailable_enumeration(self):
        completed = subprocess.CompletedProcess(
            [], 0, stdout="  42 python -m http.server\n  77 other\n", stderr="")
        with mock.patch.object(sync.os, "name", "posix"), \
                mock.patch.object(sync.subprocess, "run", return_value=completed) as run:
            self.assertEqual(sync.cmdline(42),
                             "42 python -m http.server\n  77 other")
            self.assertEqual(sync.iter_processes(),
                             [(42, "python -m http.server"), (77, "other")])
        self.assertEqual(run.call_args_list[0].args[0][:2], ["ps", "-p"])
        self.assertEqual(run.call_args_list[1].args[0], ["ps", "-Ao", "pid=,command="])

        with mock.patch.object(sync.subprocess, "run", side_effect=FileNotFoundError):
            self.assertEqual(sync.cmdline(42), "")
            self.assertEqual(sync.iter_processes(), [])


class ServeTests(unittest.TestCase):
    def test_owned_pid_with_http_timeout_is_not_blindly_restarted(self):
        command = 'python -m http.server 8123 --directory "%s"' % sync.A
        with mock.patch.dict(sync.os.environ, {}, clear=True), \
                mock.patch.object(sync, "recorded", return_value=(8123, 91)), \
                mock.patch.object(sync, "http_ok", return_value=False), \
                mock.patch.object(sync, "cmdline", return_value=command), \
                mock.patch.object(sync, "free_port", return_value=8124) as free_port, \
                mock.patch("builtins.open", mock.mock_open()) as opened, \
                mock.patch.object(sync.subprocess, "Popen") as popen, \
                mock.patch.object(sync.os, "kill") as kill:
            result = sync.serve({})
        popen.assert_not_called()
        free_port.assert_not_called()
        opened.assert_not_called()
        kill.assert_not_called()
        self.assertIn("HTTP не ответил", result)
        self.assertNotIn("сервер жив", result)

    def test_recorded_pid_recovery_requires_successful_absence_probe(self):
        cases = [("nt", "absent", 0, "", True),
                 ("nt", "present", 0, "", False),
                 ("nt", "absent", 1, "denied", False),
                 ("nt", "garbage", 0, "", False),
                 ("posix", "42\n77\n", 0, "", True),
                 ("posix", "42\n91\n", 0, "", False),
                 ("posix", "42\n77\n", 1, "denied", False),
                 ("posix", "not a PID", 0, "", False),
                 ("posix", "", 0, "", False)]
        for platform, output, code, error, absent in cases:
            server = mock.Mock(pid=92)
            with self.subTest(platform=platform, output=output, code=code), \
                    mock.patch.dict(sync.os.environ, {}, clear=True), \
                    mock.patch.object(sync.os, "name", platform), \
                    mock.patch.object(sync, "recorded", return_value=(8123, 91)), \
                    mock.patch.object(sync, "http_ok", return_value=True), \
                    mock.patch.object(sync.subprocess, "run", side_effect=[
                        subprocess.CompletedProcess([], 0, stdout="", stderr=""),
                        subprocess.CompletedProcess([], code, stdout=output, stderr=error)]) as run, \
                    mock.patch.object(sync, "free_port", return_value=8124) as free_port, \
                    mock.patch("builtins.open", mock.mock_open()) as opened, \
                    mock.patch.object(sync.subprocess, "Popen", return_value=server) as popen, \
                    mock.patch.object(sync.os, "kill") as kill:
                result = sync.serve({})
                if absent:
                    popen.assert_called_once()
                    free_port.assert_called_once_with(8123)
                    opened.return_value.write.assert_called_once_with("8124 92\n")
                    self.assertIn("сервер поднят", result)
                else:
                    popen.assert_not_called()
                    free_port.assert_not_called()
                    opened.assert_not_called()
                    self.assertIn("не подтверждена", result)
                kill.assert_not_called()
                server.terminate.assert_not_called()
                self.assertEqual(run.call_count, 2)
                query = run.call_args.args[0]
                self.assertFalse(run.call_args.kwargs.get("shell", False))
                if platform == "nt":
                    self.assertIn("Get-CimInstance", query[-1])
                    self.assertIn("-ErrorAction Stop", query[-1])
                else:
                    self.assertEqual(query, ["ps", "-Ao", "pid="])

    def test_unknown_recorded_process_never_duplicates_or_rewrites_pid(self):
        outcomes = [FileNotFoundError(), subprocess.TimeoutExpired("query", 5),
                    subprocess.CompletedProcess([], 0, stdout="", stderr=""),
                    subprocess.CompletedProcess([], 1, stdout="partial", stderr="denied")]
        for platform in ("nt", "posix"):
            for responding in (True, False):
                for outcome in outcomes:
                    with self.subTest(platform=platform, responding=responding, outcome=outcome), \
                            mock.patch.dict(sync.os.environ, {}, clear=True), \
                            mock.patch.object(sync.os, "name", platform), \
                            mock.patch.object(sync, "http_ok", return_value=responding), \
                            mock.patch.object(sync.subprocess, "run", side_effect=
                                              outcome if isinstance(outcome, Exception) else None,
                                              return_value=outcome), \
                            mock.patch.object(sync, "free_port", return_value=8124) as free_port, \
                            mock.patch.object(sync, "iter_processes") as processes, \
                            mock.patch("builtins.open", mock.mock_open(read_data="8123 91\n")) as opened, \
                            mock.patch.object(sync.subprocess, "Popen") as popen, \
                            mock.patch.object(sync.os, "kill") as kill:
                        results = [sync.serve({}) for _ in range(3)]
                    popen.assert_not_called()
                    free_port.assert_not_called()
                    processes.assert_not_called()
                    kill.assert_not_called()
                    opened.return_value.write.assert_not_called()
                    self.assertEqual(opened.call_args_list,
                                     [mock.call(sync.PIDF, encoding="utf-8")] * 3)
                    for result in results:
                        self.assertIn("не подтверждена", result)
                        self.assertNotIn("сервер жив", result)
                        self.assertNotIn("сервер поднят", result)

    def test_foreign_process_is_never_terminated(self):
        foreign = (77, "python -m http.server 8123 --directory /somewhere/else")

        with mock.patch.dict(sync.os.environ, {}, clear=True), \
                mock.patch.object(sync, "recorded", return_value=(8123, 77)), \
                mock.patch.object(sync, "http_ok", return_value=True), \
                mock.patch.object(sync, "cmdline", return_value=foreign[1]), \
                mock.patch.object(sync, "iter_processes", return_value=[foreign]) as processes, \
                mock.patch.object(sync, "free_port", return_value=None), \
                mock.patch.object(sync.os, "kill") as kill:
            result = sync.serve({})

        processes.assert_not_called()
        kill.assert_not_called()
        self.assertIn("порт не нашёлся", result)

    def test_unrecorded_same_directory_server_is_left_running(self):
        orphan = (
            77,
            'python -m http.server 8123 --directory "%s"' % sync.A,
        )
        server = mock.Mock(pid=91)
        log_handle = mock.MagicMock()
        pid_handle = mock.MagicMock()

        with mock.patch.dict(sync.os.environ, {}, clear=True), \
                mock.patch.object(sync, "recorded", return_value=(None, None)), \
                mock.patch.object(sync, "iter_processes", return_value=[orphan]) as processes, \
                mock.patch.object(sync, "free_port", return_value=8124) as free_port, \
                mock.patch.object(sync, "http_ok", return_value=True), \
                mock.patch("builtins.open", side_effect=[log_handle, pid_handle]), \
                mock.patch.object(sync.subprocess, "Popen", return_value=server) as popen, \
                mock.patch.object(sync.os, "kill") as kill:
            result = sync.serve({})

        processes.assert_not_called()
        kill.assert_not_called()
        free_port.assert_called_once_with(None)
        self.assertEqual(
            popen.call_args.args[0],
            [
                sys.executable,
                "-m",
                "http.server",
                "8124",
                "--bind",
                "127.0.0.1",
                "--directory",
                sync.A,
            ],
        )
        self.assertIn("сервер поднят", result)

    def test_windows_launch_is_detached_hidden_and_closes_parent_log(self):
        server = mock.Mock(pid=91)
        log_handle = mock.MagicMock()
        pid_handle = mock.MagicMock()

        with mock.patch.dict(sync.os.environ, {}, clear=True), \
                mock.patch.object(sync.os, "name", "nt"), \
                mock.patch.object(sync, "recorded", return_value=(None, None)), \
                mock.patch.object(sync, "iter_processes", return_value=[]), \
                mock.patch.object(sync, "free_port", return_value=8123), \
                mock.patch.object(sync, "http_ok", return_value=True), \
                mock.patch("builtins.open", side_effect=[log_handle, pid_handle]), \
                mock.patch.object(sync.subprocess, "Popen", return_value=server) as popen:
            result = sync.serve({})

        kwargs = popen.call_args.kwargs
        self.assertNotIn("start_new_session", kwargs)
        self.assertTrue(kwargs["creationflags"] & 0x00000200)
        self.assertTrue(kwargs["creationflags"] & 0x08000000)
        log_handle.close.assert_called_once_with()
        self.assertIn("сервер поднят", result)

    def test_posix_launch_uses_new_session(self):
        server = mock.Mock(pid=91)
        log_handle = mock.MagicMock()
        pid_handle = mock.MagicMock()

        with mock.patch.dict(sync.os.environ, {}, clear=True), \
                mock.patch.object(sync.os, "name", "posix"), \
                mock.patch.object(sync, "recorded", return_value=(None, None)), \
                mock.patch.object(sync, "iter_processes", return_value=[]), \
                mock.patch.object(sync, "free_port", return_value=8123), \
                mock.patch.object(sync, "http_ok", return_value=True), \
                mock.patch("builtins.open", side_effect=[log_handle, pid_handle]), \
                mock.patch.object(sync.subprocess, "Popen", return_value=server) as popen:
            sync.serve({})

        self.assertIs(popen.call_args.kwargs["start_new_session"], True)
        self.assertNotIn("creationflags", popen.call_args.kwargs)

    def test_finished_ssh_and_ci_never_query_or_launch_processes(self):
        cases = [
            ({"finishedAt": "2026-09-11T00:00:00Z"}, {}),
            ({}, {"SSH_CONNECTION": "client server"}),
            ({}, {"CI": "true"}),
        ]
        for state, environment in cases:
            with self.subTest(state=state, environment=environment), \
                    mock.patch.dict(sync.os.environ, environment, clear=True), \
                    mock.patch.object(sync, "iter_processes") as processes, \
                    mock.patch.object(sync.subprocess, "Popen") as popen:
                sync.serve(state)
            processes.assert_not_called()
            popen.assert_not_called()

    def test_live_owned_server_is_reused(self):
        command = 'python -m http.server 8123 --directory "%s"' % sync.A
        with mock.patch.dict(sync.os.environ, {}, clear=True), \
                mock.patch.object(sync, "recorded", return_value=(8123, 91)), \
                mock.patch.object(sync, "http_ok", return_value=True), \
                mock.patch.object(sync, "cmdline", return_value=command), \
                mock.patch.object(sync, "iter_processes") as processes, \
                mock.patch.object(sync.subprocess, "Popen") as popen:
            result = sync.serve({})

        processes.assert_not_called()
        popen.assert_not_called()
        self.assertEqual(result, "сервер жив: http://localhost:8123/dashboard.html")


if __name__ == "__main__":
    unittest.main()
