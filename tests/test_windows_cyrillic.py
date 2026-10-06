"""Русская буква в пути на Windows не плодит серверы страницы прогресса (находка третьего пробного прогона, 2026-10-06).

На живом прогоне имя пользователя было `а` (кириллица): `C:\\Users\\а\\pilot3`. Навык спрашивает у PowerShell строку запуска
записанного сервера и сверяет в ней `--directory` с каталогом прогона. PowerShell на русской Windows печатает в кодовой
странице консоли (866), Python читал вывод в локальной (cp1251): `а` превращалась в другой знак, пути не совпадали, сервер
считался чужим, и каждая синхронизация поднимала новый. К концу прогона работало семь серверов на разных портах, а
остановить удалось бы только последний, записанный в `serve.pid`.

Починка: строка запуска едет из PowerShell как base64 от UTF-8 (чистый ASCII), Python раскодирует её сам. Кодовая страница
консоли больше ни при чём. Здесь это проверено на подставных ответах PowerShell: настоящий запрос на Windows гоняет
`tests/test_native_runtime.py` в CI на windows-latest. Что тест не видит: русскую Windows с кодовой страницей 866 у нас
в CI нет, поэтому порчу буквы мы воспроизводим вручную (кодируем в 866, читаем в cp1251), как это делал старый конвейер.

Проверка проверена нарочными поломками: тест, который не умеет краснеть, ничего не доказывает.
"""

import base64
import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest import mock


SCRIPT = Path(__file__).parents[1] / "skills" / "autopilot-jet" / "tools" / "sync.py"
SPEC = importlib.util.spec_from_file_location("autopilot_sync_cyrillic", SCRIPT)
sync = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync)

RUN_DIR = "C:\\Users\\\u0430\\pilot3\\.autopilot"            # \u0430 кириллическая, как в имени пользователя с живого прогона
COMMAND = ("C:\\Users\\\u0430\\AppData\\Local\\Programs\\Python\\Python314\\python.exe "
           "-m http.server 54636 --bind 127.0.0.1 --directory " + RUN_DIR)


def b64(text):
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def through_the_old_pipe(text):
    """Что получал Python раньше: PowerShell печатал в cp866, Python читал как cp1251."""
    return text.encode("cp866").decode("cp1251")


def ps_answer(stdout, code=0):
    return subprocess.CompletedProcess([], code, stdout=stdout, stderr="")


class TheFailureThisFixes(unittest.TestCase):
    def test_the_old_pipe_spoils_the_cyrillic_letter(self):
        self.assertNotEqual(through_the_old_pipe("\u0430"), "\u0430")

    def test_a_spoiled_command_is_not_recognised_as_ours(self):
        spoiled = through_the_old_pipe(COMMAND)
        self.assertFalse(sync.is_ours(spoiled, RUN_DIR))
        self.assertFalse(sync.launched_for(spoiled, RUN_DIR))

    def test_the_intact_command_is_recognised(self):
        self.assertTrue(sync.is_ours(COMMAND, RUN_DIR))
        self.assertTrue(sync.launched_for(COMMAND, RUN_DIR))


class CmdlineOnWindows(unittest.TestCase):
    def ask(self, completed):
        with mock.patch.object(sync.os, "name", "nt"), \
                mock.patch.object(sync.subprocess, "run", return_value=completed) as run:
            return sync.cmdline(7700), run

    def test_the_cyrillic_command_comes_back_intact_and_is_ours(self):
        result, _ = self.ask(ps_answer(b64(COMMAND) + "\r\n"))
        self.assertEqual(result, COMMAND)
        self.assertTrue(sync.is_ours(result, RUN_DIR))

    def test_the_query_sends_base64_of_utf8_not_plain_text(self):
        _, run = self.ask(ps_answer(b64(COMMAND)))
        script = run.call_args.args[0][-1]
        self.assertIn("ToBase64String", script)
        self.assertIn("Text.Encoding]::UTF8", script)
        self.assertIn("ProcessId = 7700", script)

    def test_an_answer_that_is_not_base64_is_an_empty_command_not_a_guess(self):
        for junk in ("C:\\Users\\?\\python.exe -m http.server", "не base64", "ab=cd"):
            with self.subTest(junk=junk):
                result, _ = self.ask(ps_answer(junk))
                self.assertEqual(result, "")

    def test_text_around_the_base64_is_an_empty_command_not_a_half_decoded_one(self):
        for stdout in (b64("abc") + "!!", b64(COMMAND) + "\nWARNING: что-то ещё", "WARNING\n" + b64(COMMAND)):
            with self.subTest(stdout=stdout):
                result, _ = self.ask(ps_answer(stdout))
                self.assertEqual(result, "")

    def test_base64_that_is_not_utf8_is_an_empty_command(self):
        not_utf8 = base64.b64encode(COMMAND.encode("cp1251")).decode("ascii")
        result, _ = self.ask(ps_answer(not_utf8))
        self.assertEqual(result, "")

    def test_a_failed_query_stays_empty_even_with_output(self):
        result, _ = self.ask(ps_answer(b64(COMMAND), code=1))
        self.assertEqual(result, "")

    def test_no_process_gives_an_empty_command(self):
        result, _ = self.ask(ps_answer(""))
        self.assertEqual(result, "")

    def test_posix_keeps_plain_text(self):
        with mock.patch.object(sync.os, "name", "posix"), \
                mock.patch.object(sync.subprocess, "run", return_value=ps_answer("python -m http.server 8000\n")):
            self.assertEqual(sync.cmdline(1), "python -m http.server 8000")


class ProcessListOnWindows(unittest.TestCase):
    def listing(self, *rows):
        delimiter = sync.PROCESS_DELIMITER
        text = "".join("%d%s%s\r\n" % (pid, delimiter, payload) for pid, payload in rows)
        with mock.patch.object(sync.os, "name", "nt"), \
                mock.patch.object(sync.subprocess, "run", return_value=ps_answer(text)) as run:
            return sync.iter_processes(), run

    def test_cyrillic_commands_survive_the_listing(self):
        result, _ = self.listing((7700, b64(COMMAND)), (4, b64("System")))
        self.assertEqual(result, [(7700, COMMAND), (4, "System")])
        self.assertTrue(sync.is_ours(result[0][1], RUN_DIR))

    def test_a_process_without_a_command_line_is_left_out_and_does_not_hide_the_next(self):
        # у системных процессов строки запуска нет: пустая полезная часть, разделитель срезается как пробел, как и раньше
        result, _ = self.listing((0, b64("")), (8, b64("x.exe")))
        self.assertEqual(result, [(8, "x.exe")])

    def test_one_broken_row_does_not_hide_the_others(self):
        result, _ = self.listing((1, "%%%not-base64"), (2, b64("ok.exe")))
        self.assertEqual(result, [(1, ""), (2, "ok.exe")])

    def test_a_row_that_is_not_utf8_does_not_break_the_whole_listing(self):
        not_utf8 = base64.b64encode(COMMAND.encode("cp1251")).decode("ascii")
        result, _ = self.listing((1, not_utf8), (2, b64("ok.exe")))
        self.assertEqual(result, [(1, ""), (2, "ok.exe")])      # битая строка даёт пустую команду, остальные целы

    def test_the_listing_query_also_goes_through_base64(self):
        _, run = self.listing((1, b64("a")))
        script = run.call_args.args[0][-1]
        self.assertIn("ToBase64String", script)
        self.assertIn("[char]31", script)


class ServerIsNotMultiplied(unittest.TestCase):
    """Тот случай с живого прогона: записанный сервер работает, каталог с русской буквой, второй не нужен."""

    def run_serve(self, command):
        with mock.patch.dict(sync.os.environ, {}, clear=True), \
                mock.patch.object(sync, "A", RUN_DIR), \
                mock.patch.object(sync, "recorded", return_value=(54636, 7700)), \
                mock.patch.object(sync, "http_ok", return_value=True), \
                mock.patch.object(sync, "cmdline", return_value=command), \
                mock.patch.object(sync, "free_port", return_value=60000), \
                mock.patch.object(sync.subprocess, "Popen") as popen:
            return sync.serve({}), popen

    def test_a_live_recorded_server_in_a_cyrillic_directory_is_reused(self):
        message, popen = self.run_serve(COMMAND)
        self.assertTrue(message.startswith("сервер жив"), message)
        popen.assert_not_called()


class ThePortalIsClosed(unittest.TestCase):
    def test_the_helper_is_what_the_queries_use(self):
        self.assertEqual(sync._from_base64(b64(COMMAND)), COMMAND)
        self.assertEqual(sync._from_base64("  " + b64(COMMAND) + "\r\n"), COMMAND)
        self.assertEqual(sync._from_base64(""), "")
        self.assertEqual(sync._from_base64("!!!"), "")


if __name__ == "__main__":
    unittest.main()
