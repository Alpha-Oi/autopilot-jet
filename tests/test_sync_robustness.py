"""Находки аудита 2026-10-06 в sync.py: каждая закреплена воспроизведением, которое до исправления падало.

Что именно было не так, написано у каждого теста: чистый JSON в state.js портился при записи, битая запись валила
sync.py обычным AttributeError, сервер в каталоге с пробелом запускался вторым, зона-строка давала ложные
пересечения, а маркер снимка внутри данных рвал страницу при следующей записи.
"""

import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


SCRIPT = Path(__file__).parents[1] / "skills" / "autopilot-jet" / "tools" / "sync.py"
SPEC = importlib.util.spec_from_file_location("autopilot_sync_robustness", SCRIPT)
sync = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync)

TWO_ACTIVE = {"stages": [{"id": "spec", "status": "active", "startedAt": "2026-01-01T10:00:00+00:00"},
                         {"id": "plan", "status": "active", "startedAt": "2026-01-01T11:00:00+00:00"}]}


class StateFileFormTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patcher = mock.patch.object(sync, "STATE", os.path.join(self.tmp.name, "state.js"))
        patcher.start()
        self.addCleanup(patcher.stop)

    def write(self, text):
        Path(sync.STATE).write_text(text, encoding="utf-8")

    def test_plain_json_survives_save_and_is_read_back(self):
        # Раньше save() брал всё до первого «=» за голову: у чистого JSON голова — весь файл, и он дописывался к себе.
        self.write(json.dumps(TWO_ACTIVE, indent=2))
        state = sync.read_state()
        self.assertTrue(sync.close_passed(state))
        sync.save(state)
        again = sync.read_state()
        self.assertEqual(again["stages"][0]["status"], "done")

    def test_assignment_head_is_kept_by_save(self):
        self.write("window.STATE =\n" + json.dumps(TWO_ACTIVE))
        sync.save(sync.read_state())
        self.assertTrue(Path(sync.STATE).read_text(encoding="utf-8").startswith("window.STATE =\n"))

    def test_an_equals_sign_inside_json_is_not_an_assignment(self):
        self.write('{"title": "a=b", "stages": []}')
        self.assertEqual(sync.read_state()["title"], "a=b")

    def test_const_assignment_is_read(self):
        self.write('const STATE = {"title": "x"};')
        self.assertEqual(sync.read_state()["title"], "x")

    def test_a_record_that_is_not_an_object_stops_before_the_snapshot(self):
        for body in ("[]", '"text"', "7", "null"):
            with self.subTest(body=body):
                self.write("window.STATE = " + body)
                # stdout в буфер: консоль Windows в CI не UTF-8, а сообщение русское (тесты-подпроцессы идут с -X utf8)
                with contextlib.redirect_stdout(io.StringIO()) as out, self.assertRaises(SystemExit):
                    sync.read_state()
                self.assertIn("не запись прогона", out.getvalue())


class MalformedRecordTests(unittest.TestCase):
    BAD = ({"stages": [1, None, "x"], "tickets": ["x", 3, None]},
           {"stages": "text", "tickets": {"a": 1}},
           {"finishedAt": "2026-01-01T00:00:00Z", "stages": [5], "tickets": [None]},
           {"stages": [{"id": "build", "status": "active"}, 7], "tickets": [{"id": "01", "status": "in-progress"}, 8]})

    def test_close_passed_audit_and_closure_do_not_raise(self):
        for state in self.BAD:
            with self.subTest(state=state):
                sync.close_passed(state)
                sync.audit(state)
                sync.closure_findings(state)

    def test_good_items_next_to_bad_ones_are_still_judged(self):
        state = self.BAD[3]
        self.assertIn("таск 01 в работе без startedAt", sync.audit(state))


class ZoneOverlapTests(unittest.TestCase):
    def test_string_zones_are_one_path_each_not_a_list_of_letters(self):
        # Раньше зона-строка шла по символам: «src/a» и «sandbox/b» совпадали по букве «s».
        self.assertFalse(sync._zones_overlap("src/a", "sandbox/b"))
        self.assertTrue(sync._zones_overlap("src/a", "src/a/deeper"))

    def test_string_zones_do_not_name_a_clash_in_audit(self):
        tickets = [{"id": "01", "status": "in-progress", "startedAt": "t", "zone": "src/a"},
                   {"id": "02", "status": "in-progress", "startedAt": "t", "zone": "sandbox/b"}]
        self.assertEqual(sync.audit_caps({"tickets": tickets}), [])


class SnapshotMarkerTests(unittest.TestCase):
    PAGE = "<script>/*STATE-BEGIN*/window.STATE=null;/*STATE-END*/</script><p>tail</p>"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.page = Path(self.tmp.name) / "dashboard.html"
        patcher = mock.patch.object(sync, "PAGE", str(self.page))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.page.write_text(self.PAGE, encoding="utf-8")

    def test_a_marker_inside_the_data_does_not_corrupt_the_next_write(self):
        sync.write_snapshot({"title": "x /*STATE-END*/ y /*STATE-BEGIN*/ z"})
        sync.write_snapshot({"title": "second"})
        self.assertEqual(self.page.read_text(encoding="utf-8"),
                         "<script>/*STATE-BEGIN*/window.STATE={\"title\": \"second\"};/*STATE-END*/</script><p>tail</p>")

    def test_the_escaped_value_is_the_same_javascript_value(self):
        sync.write_snapshot({"title": "a /*b*/ <!-- c --> </script>"})
        text = self.page.read_text(encoding="utf-8")
        payload = text.split("/*STATE-BEGIN*/window.STATE=", 1)[1].split(";/*STATE-END*/", 1)[0]
        for raw in ("</", "<!--", "/*"):
            self.assertNotIn(raw, payload)
        # \/ \! \* — те же знаки в JS-строке; в JSON-разборщике эти три экранирования запрещены, поэтому сверяем так
        decoded = payload.replace("<\\/", "</").replace("<\\!--", "<!--").replace("/\\*", "/*")
        self.assertEqual(json.loads(decoded), {"title": "a /*b*/ <!-- c --> </script>"})

    def test_end_marker_before_begin_is_a_page_without_markers(self):
        self.page.write_text("/*STATE-END*/ x /*STATE-BEGIN*/", encoding="utf-8")
        self.assertIn("без маркеров", sync.write_snapshot({"a": 1}))
        self.assertEqual(self.page.read_text(encoding="utf-8"), "/*STATE-END*/ x /*STATE-BEGIN*/")


class ServeOwnershipTests(unittest.TestCase):
    def test_own_server_in_a_directory_with_a_space_is_reused_not_duplicated(self):
        # ps не сохраняет кавычки, и is_ours() режет каталог по пробелу: раньше serve() запускал второй сервер
        # на другом порту и затирал serve.pid.
        directory = "/x/my run/.autopilot"
        command = "/usr/bin/python3 -m http.server 8000 --bind 127.0.0.1 --directory " + directory
        env = {key: value for key, value in os.environ.items() if key not in ("CI", "SSH_CONNECTION")}
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(sync, "A", directory), \
                mock.patch.object(sync, "recorded", return_value=(8000, 4242)), \
                mock.patch.object(sync, "http_ok", return_value=True), \
                mock.patch.object(sync, "cmdline", return_value=command), \
                mock.patch.object(sync.subprocess, "Popen", side_effect=AssertionError("second server launched")):
            self.assertIn("сервер жив", sync.serve({}))


class MainArgumentsTests(unittest.TestCase):
    def test_an_unknown_argument_is_a_usage_error_not_a_silent_sync(self):
        with contextlib.redirect_stdout(io.StringIO()), mock.patch.object(sys, "argv", ["sync.py", "--no-serv"]), \
                mock.patch.object(sync, "read_state", side_effect=AssertionError("ordinary sync ran")), \
                mock.patch.object(sync, "serve", side_effect=AssertionError("server touched")), \
                self.assertRaises(SystemExit) as raised:
            sync.main()
        self.assertEqual(raised.exception.code, 2)

    def test_every_mode_in_the_table_names_a_function(self):
        for flag, name in sync.MODES:
            with self.subTest(flag=flag):
                self.assertTrue(callable(getattr(sync, name)))


class ReadModesOnMalformedRecordTests(unittest.TestCase):
    def test_other_window_on_a_list_record_is_unknown_not_a_crash(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "state.js").write_text("window.STATE = [1]", encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(sync.check_other_window(tmp), 3)
            self.assertIn("unknown", out.getvalue())


if __name__ == "__main__":
    unittest.main()
