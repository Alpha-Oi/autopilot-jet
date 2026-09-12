import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest import mock


SCRIPT = Path(__file__).parents[1] / "skills" / "autopilot" / "tools" / "sync.py"
SPEC = importlib.util.spec_from_file_location("autopilot_sync", SCRIPT)
sync = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync)


class ProcessQueryTests(unittest.TestCase):
    def test_cmdline_windows_uses_non_shell_system_query(self):
        completed = subprocess.CompletedProcess([], 0, stdout="python -m http.server", stderr="")

        with mock.patch.object(sync.os, "name", "nt"), \
                mock.patch.object(sync.subprocess, "run", return_value=completed) as run:
            result = sync.cmdline(42)

        self.assertEqual(result, "python -m http.server")
        args, kwargs = run.call_args
        self.assertNotEqual(args[0][0], "ps")
        self.assertIs(kwargs.get("shell", False), False)

    def test_iter_processes_windows_parses_safe_query(self):
        delimiter = sync.PROCESS_DELIMITER
        completed = subprocess.CompletedProcess(
            [], 0,
            stdout=("42%s python -m http.server\n77%sother.exe\n"
                    % (delimiter, delimiter)),
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
    def test_foreign_process_is_never_terminated(self):
        foreign = (77, "python -m http.server 8123 --directory /somewhere/else")
        completed = subprocess.CompletedProcess([], 0, stdout="", stderr="")

        with mock.patch.dict(sync.os.environ, {}, clear=True), \
                mock.patch.object(sync, "recorded", return_value=(8123, 77)), \
                mock.patch.object(sync, "http_ok", return_value=True), \
                mock.patch.object(sync, "cmdline", return_value=foreign[1]), \
                mock.patch.object(sync, "iter_processes", return_value=[foreign]) as processes, \
                mock.patch.object(sync, "free_port", return_value=None), \
                mock.patch.object(sync.subprocess, "run", return_value=completed), \
                mock.patch.object(sync.os, "kill") as kill:
            result = sync.serve({})

        processes.assert_called_once_with()
        kill.assert_not_called()
        self.assertIn("порт не нашёлся", result)

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
