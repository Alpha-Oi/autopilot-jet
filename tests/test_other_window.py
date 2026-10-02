"""Определение «прогон идёт в другом окне» (четвёртый случай phases/0-preflight.md) как проверяемый код.

Два окна на одном state.js перезаписывают таски друг друга, а первое, дошедшее до Phase 8, замораживает
дашборд второго. Поэтому вердикт строится строго по двум меткам сразу: `updatedAt` моложе пяти минут и
живой сервер на этом каталоге. Одна метка без другой — обычное прерывание. Неизвестное состояние не
выдаётся ни за «да», ни за «нет».

Режим `--other-window` ничего не пишет: это проверяется сравнением содержимого каталога до и после.
"""

from datetime import datetime, timedelta, timezone
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock
import urllib.request


SCRIPT = Path(__file__).parents[1] / "skills" / "autopilot-jet" / "tools" / "sync.py"
SPEC = importlib.util.spec_from_file_location("autopilot_sync_other_window", SCRIPT)
sync = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync)

NOW = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)


def stamp(seconds_ago, offset_hours=0):
    moment = NOW - timedelta(seconds=seconds_ago)
    return moment.astimezone(timezone(timedelta(hours=offset_hours))).isoformat()


class VerdictTests(unittest.TestCase):
    def verdict(self, updated, serving, **extra):
        state = {"updatedAt": updated, **extra}
        return sync.other_window(state, NOW, serving)[0]

    def test_both_marks_mean_another_window(self):
        self.assertEqual(self.verdict(stamp(10), True), "other-window")

    def test_one_mark_without_the_other_is_an_ordinary_resume(self):
        self.assertEqual(self.verdict(stamp(10), False), "resume")        # свежий, сервера нет
        self.assertEqual(self.verdict(stamp(3600), True), "resume")       # сервер есть, метка старая

    def test_the_boundary_is_under_five_minutes(self):
        self.assertEqual(self.verdict(stamp(299), True), "other-window")
        self.assertEqual(self.verdict(stamp(300), True), "resume")
        self.assertEqual(self.verdict(stamp(301), True), "resume")

    def test_the_offset_is_read_not_ignored(self):
        # одно и то же мгновение в другом поясе: 10 секунд назад, но записано как +03:00
        self.assertEqual(self.verdict(stamp(10, 3), True), "other-window")
        # без учёта пояса это выглядело бы как «три часа назад»
        self.assertEqual(self.verdict(stamp(3600, 3), True), "resume")
        self.assertEqual(self.verdict(stamp(10).replace("+00:00", "Z"), True), "other-window")

    def test_a_clock_set_ahead_is_not_old(self):
        self.assertEqual(self.verdict(stamp(-120), True), "other-window")

    def test_a_missing_or_unreadable_stamp_is_unknown_unless_the_server_is_absent(self):
        for bad in (None, "", "вчера", "2026-10-01T11:59:50", 123):
            with self.subTest(updated=bad):
                self.assertEqual(self.verdict(bad, True), "unknown")
                self.assertEqual(self.verdict(bad, None), "unknown")
                self.assertEqual(self.verdict(bad, False), "resume")

    def test_an_unconfirmed_server_is_unknown_when_the_stamp_is_fresh(self):
        self.assertEqual(self.verdict(stamp(10), None), "unknown")
        self.assertEqual(self.verdict(stamp(3600), None), "resume")

    def test_the_reason_names_what_is_unknown(self):
        why = sync.other_window({"updatedAt": "вчера"}, NOW, None)[1]
        self.assertIn("updatedAt", why)
        self.assertIn("сервер", why)

    def test_finishedAt_does_not_change_the_verdict(self):
        self.assertEqual(self.verdict(stamp(10), True, finishedAt=None), "other-window")
        self.assertEqual(self.verdict(stamp(10), True, finishedAt=stamp(5)), "other-window")

    def test_a_state_without_fields_is_safe(self):
        for state in ({}, None):
            with self.subTest(state=state):
                self.assertEqual(sync.other_window(state, NOW, True)[0], "unknown")


class ServerServingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="other window ")
        self.addCleanup(self.tmp.cleanup)
        self.dir = os.path.realpath(self.tmp.name)

    def record(self, port=8123, pid=4242):
        Path(self.dir, "serve.pid").write_text("%d %d\n" % (port, pid), encoding="utf-8")

    def command(self, directory=None):
        return 'python -m http.server 8123 --bind 127.0.0.1 --directory "%s"' % (directory or self.dir)

    def serving(self, command, responding=True, status="present"):
        with mock.patch.object(sync, "cmdline", return_value=command), \
                mock.patch.object(sync, "http_ok", return_value=responding), \
                mock.patch.object(sync, "process_status", return_value=status):
            return sync.server_serving(self.dir)

    def test_no_record_means_no_server(self):
        self.assertFalse(sync.server_serving(self.dir))

    def test_our_process_that_answers_is_a_live_server(self):
        self.record()
        self.assertIs(self.serving(self.command()), True)

    def test_our_process_that_does_not_answer_is_unknown_not_dead(self):
        self.record()
        self.assertIsNone(self.serving(self.command(), responding=False))

    def test_a_process_of_another_directory_or_another_program_is_not_ours(self):
        self.record()
        self.assertIs(self.serving(self.command(directory=self.dir + "-other")), False)
        self.assertIs(self.serving("python worker.py --directory %s" % self.dir), False)

    def test_an_unreadable_command_line_is_decided_by_a_successful_absence_probe_only(self):
        self.record()
        self.assertIs(self.serving("", status="absent"), False)
        self.assertIsNone(self.serving("", status="present"))
        self.assertIsNone(self.serving("", status="unknown"))

    def test_a_directory_with_a_space_is_recognised_when_ps_drops_the_quotes(self):
        self.record()
        self.assertIn(" ", self.dir)
        unquoted = "python -m http.server 8123 --bind 127.0.0.1 --directory %s" % self.dir
        self.assertFalse(sync.is_ours(unquoted, self.dir))          # прежняя проверка режет по пробелу
        self.assertIs(self.serving(unquoted), True)

    def test_the_end_of_the_line_match_does_not_accept_a_longer_foreign_directory(self):
        launched = sync.launched_for
        self.assertTrue(launched("python -m http.server 1 --directory /x/a b", "/x/a b"))
        self.assertFalse(launched("python -m http.server 1 --directory /x/a b", "/x/a"))
        self.assertFalse(launched("python -m http.server 1 --directory /x/a", "/x/a b"))
        self.assertFalse(launched("python -m http.server 1 --directory /x/a --bind 127.0.0.1", "/x/a"))
        self.assertFalse(launched("python worker.py --directory /x/a", "/x/a"))
        self.assertFalse(launched("python -m http.server 1 --directory /y/x/a", "/x/a"))

    def test_the_run_directory_is_the_one_asked_about_not_the_scripts_own(self):
        self.record()
        self.assertNotEqual(self.dir, sync.A)
        self.assertIs(self.serving(self.command()), True)


class CliCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="other window cli ")
        self.addCleanup(self.tmp.cleanup)
        self.dir = os.path.realpath(self.tmp.name)

    def write_state(self, updated):
        Path(self.dir, "state.js").write_text(
            "window.STATE =\n" + json.dumps({"updatedAt": updated, "finishedAt": None}, indent=2) + "\n",
            encoding="utf-8")
        Path(self.dir, "dashboard.html").write_text("<html>dashboard</html>\n", encoding="utf-8")

    def snapshot(self):
        return {name: (Path(self.dir, name).read_bytes() if Path(self.dir, name).is_file() else None)
                for name in sorted(os.listdir(self.dir))}

    def run_cli(self, *args):
        return subprocess.run([sys.executable, "-X", "utf8", "-B", str(SCRIPT), *args], capture_output=True,
                              text=True, encoding="utf-8", timeout=60, check=False)


class CliWithoutServerTests(CliCase):
    def test_a_fresh_stamp_without_a_server_is_a_resume_and_nothing_is_written(self):
        self.write_state(datetime.now(timezone.utc).isoformat())
        before = self.snapshot()
        result = self.run_cli("--other-window", self.dir)
        self.assertEqual((result.returncode, result.stdout.split(" · ")[0]), (0, "resume"), result.stdout)
        self.assertEqual(self.snapshot(), before)

    def test_no_state_is_not_another_window(self):
        result = self.run_cli("--other-window", self.dir)
        self.assertEqual(result.returncode, 0)
        self.assertIn("state.js нет", result.stdout)
        self.assertEqual(os.listdir(self.dir), [])

    def test_a_broken_state_is_unknown_with_exit_three(self):
        Path(self.dir, "state.js").write_text("window.STATE =\n{ не json\n", encoding="utf-8")
        result = self.run_cli("--other-window", self.dir)
        self.assertEqual(result.returncode, 3)
        self.assertTrue(result.stdout.startswith("unknown"))

    def test_a_bad_call_is_exit_two(self):
        for args in (("--other-window", "a", "b"), ("--other-window", "--write")):
            with self.subTest(args=args):
                self.assertEqual(self.run_cli(*args).returncode, 2)

    def test_the_mode_never_starts_a_server_or_a_pid_file(self):
        self.write_state(datetime.now(timezone.utc).isoformat())
        self.run_cli("--other-window", self.dir)
        self.assertFalse(Path(self.dir, "serve.pid").exists())
        self.assertFalse(Path(self.dir, "serve.log").exists())


# `http.server` при старте зовёт socket.getfqdn(): обратный DNS-запрос. На Linux и Windows он мгновенный, на
# раннере macOS в CI он занимал около 35 секунд на каждый запуск сервера. Подмена лежит в sitecustomize вне
# проверяемого каталога и не меняет ни командную строку процесса, ни сам сервер.
NO_REVERSE_DNS = "import socket\nsocket.getfqdn = lambda name='': name or 'localhost'\n"


class CliWithRealServerTests(CliCase):
    def start_server(self):
        helper = tempfile.TemporaryDirectory(prefix="other window helper ")
        self.addCleanup(helper.cleanup)
        Path(helper.name, "sitecustomize.py").write_text(NO_REVERSE_DNS, encoding="utf-8")
        env = dict(os.environ, PYTHONPATH=os.pathsep.join(filter(None, [helper.name, os.environ.get("PYTHONPATH")])))
        server = subprocess.Popen([sys.executable, "-u", "-m", "http.server", "0", "--bind", "127.0.0.1",
                                   "--directory", self.dir], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                  text=True, env=env)
        self.addCleanup(lambda: (server.terminate(), server.wait(timeout=10), server.stdout.close()))
        line = server.stdout.readline()                       # "Serving HTTP on 127.0.0.1 port N ..."
        port = int(line.split("port")[1].split()[0])
        for _ in range(50):
            try:
                with urllib.request.urlopen("http://127.0.0.1:%d/dashboard.html" % port, timeout=2) as reply:
                    if reply.status == 200:
                        break
            except OSError:
                time.sleep(0.1)
        Path(self.dir, "serve.pid").write_text("%d %d\n" % (port, server.pid), encoding="utf-8")
        return server

    def test_a_fresh_stamp_and_a_live_server_is_another_window(self):
        self.write_state(datetime.now(timezone.utc).isoformat())
        self.start_server()
        before = self.snapshot()
        result = self.run_cli("--other-window", self.dir)
        self.assertEqual((result.returncode, result.stdout.split(" · ")[0]), (1, "other-window"), result.stdout)
        self.assertEqual(self.snapshot(), before)

    def test_an_old_stamp_with_a_live_server_is_a_resume(self):
        self.write_state((datetime.now(timezone.utc) - timedelta(hours=1)).isoformat())
        self.start_server()
        result = self.run_cli("--other-window", self.dir)
        self.assertEqual((result.returncode, result.stdout.split(" · ")[0]), (0, "resume"), result.stdout)


class MainDispatchTests(unittest.TestCase):
    def test_the_flag_does_not_fall_through_to_the_ordinary_sync(self):
        with mock.patch.object(sys, "argv", ["sync.py", "--other-window"]), \
                mock.patch.object(sync, "check_other_window", return_value=1) as check, \
                mock.patch.object(sync, "read_state", side_effect=AssertionError("ordinary sync ran")), \
                mock.patch.object(sync, "serve", side_effect=AssertionError("server touched")), \
                self.assertRaises(SystemExit) as raised:
            sync.main()
        self.assertEqual(raised.exception.code, 1)
        check.assert_called_once_with(sync.A)


if __name__ == "__main__":
    unittest.main()
