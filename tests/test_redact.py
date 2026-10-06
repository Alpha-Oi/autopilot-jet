"""Фильтр секретов: все формы из phases/1-manifest.md, ложные срабатывания, CLI.

Секреты в фикстурах собираются во время выполнения из кусков: так в исходниках нет
подряд идущих значений, похожих на настоящие ключи, и push protection не срабатывает.
"""

import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).parents[1] / "skills" / "autopilot-jet" / "tools" / "redact.py"
SPEC = importlib.util.spec_from_file_location("autopilot_redact", SCRIPT)
redact_mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(redact_mod)


def fake(prefix, length, seed="aB3dE5fG7h"):
    """prefix + детерминированные символы с цифрами; значение заведомо ненастоящее."""
    return prefix + (seed * length)[:length]


STRIPE_LIVE = fake("sk_" "live_", 24)
STRIPE_RESTRICTED = fake("rk_" "live_", 24)
STRIPE_PUBLISHABLE = fake("pk_" "test_", 24)
OPENAI = fake("sk" "-", 48)
ANTHROPIC = fake("sk" "-" "ant-", 40)
GITHUB = fake("gh" "p_", 36)
GITHUB_PAT = fake("github" "_pat_", 40)
AWS = "AK" "IA" + "ABCD1234EFGH5678"
GOOGLE_KEY = fake("AI" "za", 35)
GOOGLE_OAUTH = fake("ya" "29.", 40)
SLACK = "xox" "b-" + "1234567890-abcdefghij"
TELEGRAM = "123456789" + ":" + fake("", 35)
JWT = "ey" "J" + "hbGciOiJIUzI1NiJ9" + "." + "eyJzdWIiOiIxMjM0NTY3ODkwIn0" + "." + "dBjftJeZ4CVPmB92K27uhbUJU1p1r"
PG_URL = "postgres://app_user:" + fake("", 12) + "@db.example.com:5432/app"
KEY_BEGIN = "-----BEGIN RSA " + "PRIVATE KEY-----"
KEY_END = "-----END RSA " + "PRIVATE KEY-----"
PRIVATE_KEY = KEY_BEGIN + "\nMIIEowIBAAKCAQEA1234567890abcdef\nZZZZ1234567890abcdef\n" + KEY_END

KINDS = [
    ("stripe secret", STRIPE_LIVE, "STRIPE_SECRET_KEY"),
    ("stripe restricted", STRIPE_RESTRICTED, "STRIPE_RESTRICTED_KEY"),
    ("stripe publishable", STRIPE_PUBLISHABLE, "STRIPE_PUBLISHABLE_KEY"),
    ("openai", OPENAI, "OPENAI_API_KEY"),
    ("anthropic", ANTHROPIC, "ANTHROPIC_API_KEY"),
    ("github", GITHUB, "GITHUB_TOKEN"),
    ("github pat", GITHUB_PAT, "GITHUB_TOKEN"),
    ("aws", AWS, "AWS_ACCESS_KEY_ID"),
    ("google api", GOOGLE_KEY, "GOOGLE_API_KEY"),
    ("google oauth", GOOGLE_OAUTH, "GOOGLE_OAUTH_TOKEN"),
    ("slack", SLACK, "SLACK_BOT_TOKEN"),
    ("telegram", TELEGRAM, "TELEGRAM_BOT_TOKEN"),
    ("jwt", JWT, "JWT_TOKEN"),
    ("connection string", PG_URL, "DATABASE_URL"),
]


def run_cli(*args, stdin=None, cwd=None):
    return subprocess.run(
        [sys.executable, "-X", "utf8", "-B", str(SCRIPT), *args],
        input=stdin, capture_output=True, text=True, encoding="utf-8", cwd=cwd, timeout=30,
    )


class DetectionTests(unittest.TestCase):
    def test_every_provider_shape_is_replaced_with_its_variable_name(self):
        for label, secret, name in KINDS:
            with self.subTest(label):
                result = redact_mod.redact("перед %s после" % secret)
                self.assertEqual(result.text, "перед [REDACTED:%s] после" % name)
                self.assertEqual([item.name for item in result.findings], [name])
                self.assertNotIn(secret, result.text)

    def test_private_key_block_is_replaced_whole(self):
        result = redact_mod.redact("до\n%s\nпосле" % PRIVATE_KEY)
        self.assertEqual(result.text, "до\n[REDACTED:PRIVATE_KEY]\nпосле")

    def test_unterminated_private_key_fails_closed(self):
        result = redact_mod.redact("до\n%s\nMIIEowIBAAKCAQEA1234567890abcdef" % KEY_BEGIN)
        self.assertEqual(result.text, "до\n[REDACTED:PRIVATE_KEY]")

    def test_connection_string_schemes_pick_conventional_names(self):
        cases = {
            "mongodb+srv": "MONGODB_URI",
            "redis": "REDIS_URL",
            "mysql": "DATABASE_URL",
            "amqps": "AMQP_URL",
            "ftp": "CONNECTION_STRING",
        }
        for scheme, name in cases.items():
            with self.subTest(scheme):
                text = "%s://user:%s@host.example.com/x" % (scheme, fake("", 10))
                self.assertEqual(redact_mod.redact(text).text, "[REDACTED:%s]" % name)

    def test_generic_assignment_keeps_the_identifier_as_name(self):
        value = fake("", 40)
        for line, name in (
            ("MY_SERVICE_TOKEN=%s" % value, "MY_SERVICE_TOKEN"),
            ('db.password: "%s"' % value, "DB_PASSWORD"),
            ("api-key = '%s'" % value, "API_KEY"),
            ('{"api_key": "%s"}' % value, "API_KEY"),
            ('{"clientSecret":"%s","x":1}' % value, "CLIENTSECRET"),
        ):
            with self.subTest(line):
                result = redact_mod.redact(line)
                self.assertIn("[REDACTED:%s]" % name, result.text)
                self.assertNotIn(value, result.text)

    def test_generic_value_next_to_a_keyword_in_prose(self):
        value = fake("", 40)
        for text, name in (
            ("мой токен: %s" % value, "ACCESS_TOKEN"),
            ("пароль от базы — %s, спасибо" % value, "PASSWORD"),
            ("the password is %s." % value, "PASSWORD"),
            ("secret %s" % value, "SECRET"),
            ("ключ (%s)" % value, "API_KEY"),
        ):
            with self.subTest(text):
                result = redact_mod.redact(text)
                self.assertIn("[REDACTED:%s]" % name, result.text)
                self.assertNotIn(value, result.text)

    def test_specific_provider_wins_over_the_generic_keyword_rule(self):
        result = redact_mod.redact("токен бота: %s" % TELEGRAM)
        self.assertEqual([item.name for item in result.findings], ["TELEGRAM_BOT_TOKEN"])

    def test_several_secrets_in_one_text(self):
        text = "a %s b %s c %s" % (STRIPE_LIVE, GITHUB, AWS)
        result = redact_mod.redact(text)
        self.assertEqual(result.text, "a [REDACTED:STRIPE_SECRET_KEY] b [REDACTED:GITHUB_TOKEN] c [REDACTED:AWS_ACCESS_KEY_ID]")

    def test_redaction_is_idempotent(self):
        text = "x %s y %s z\n%s\nTOKEN=%s" % (STRIPE_LIVE, PG_URL, PRIVATE_KEY, fake("", 40))
        once = redact_mod.redact(text).text
        twice = redact_mod.redact(once)
        self.assertEqual(twice.text, once)
        self.assertEqual(twice.findings, [])

    def test_findings_never_carry_the_value(self):
        result = redact_mod.redact("k %s" % STRIPE_LIVE)
        for item in result.findings:
            self.assertNotIn(STRIPE_LIVE, repr(item))


class FalsePositiveTests(unittest.TestCase):
    def test_ordinary_text_is_untouched(self):
        samples = [
            "Хочу телеграм-бота, который принимает заявки и складывает их в таблицу",
            "commit 8c8cb33353df35c2831d977ad5d81922191738d9 прошёл CI",
            "id 123e4567-e89b-12d3-a456-426614174000",
            "см. https://example.com/docs/api-keys/page без логина",
            "the task-force-assessment-framework-document-2026 is a word, not a key",
            "key: short1",
            "token = abc",
            "ключ SomeVeryLongCamelCaseIdentifierNameThatHasNoDigitsAtAll",
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 (sha256 пустого файла)",
            "STRIPE_SECRET_KEY=",
            "STRIPE_SECRET_KEY=[REDACTED:STRIPE_SECRET_KEY]",
            "/etc/ssl/private/server-key-2024-01-01-extra-long-path-name/file",
        ]
        for text in samples:
            with self.subTest(text):
                self.assertEqual(redact_mod.redact(text).text, text)

    def test_empty_and_unicode_text(self):
        self.assertEqual(redact_mod.redact("").text, "")
        self.assertEqual(redact_mod.redact("Привет, мир — ёжик").text, "Привет, мир — ёжик")


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="redact проверка ")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_stdin_mode_filters_and_never_echoes_the_value(self):
        text = "Привет\nключ Stripe: %s\nконец\n" % STRIPE_LIVE
        done = run_cli("--stdin", stdin=text)
        self.assertEqual(done.returncode, 0)
        self.assertEqual(done.stdout, "Привет\nключ Stripe: [REDACTED:STRIPE_SECRET_KEY]\nконец\n")
        self.assertIn("STRIPE_SECRET_KEY", done.stderr)
        self.assertNotIn(STRIPE_LIVE, done.stdout + done.stderr)

    def test_stdin_mode_passes_clean_text_through(self):
        done = run_cli("--stdin", stdin="просто текст\n")
        self.assertEqual((done.returncode, done.stdout, done.stderr), (0, "просто текст\n", ""))

    def test_check_reports_path_line_and_name_but_not_the_value(self):
        (self.root / "clean.md").write_text("ничего такого\n", encoding="utf-8")
        (self.root / "dirty.md").write_text("строка 1\nTOKEN: %s\n" % fake("", 40), encoding="utf-8")
        done = run_cli("--check", str(self.root))
        self.assertEqual(done.returncode, 1)
        self.assertIn("dirty.md:2: TOKEN", done.stdout)
        self.assertNotIn("clean.md:", done.stdout)
        self.assertNotIn(fake("", 40), done.stdout + done.stderr)

    def test_check_exits_zero_on_a_clean_tree(self):
        (self.root / "a.md").write_text("чисто\n", encoding="utf-8")
        done = run_cli("--check", str(self.root))
        self.assertEqual(done.returncode, 0)
        self.assertIn("секретов 0", done.stdout)

    def test_check_skips_git_dir_binary_and_non_utf8_files(self):
        (self.root / ".git").mkdir()
        (self.root / ".git" / "config").write_text("TOKEN=%s\n" % fake("", 40), encoding="utf-8")
        (self.root / "image.bin").write_bytes(b"\x00\x01" + fake("", 40).encode("ascii"))
        (self.root / "latin.txt").write_bytes("TOKEN=".encode("ascii") + b"\xff\xfe")
        done = run_cli("--check", str(self.root))
        self.assertEqual(done.returncode, 0)
        self.assertIn("не UTF-8", done.stdout)

    def test_write_rewrites_in_place_and_keeps_crlf(self):
        target = self.root / "brief.md"
        target.write_bytes(("первая\r\nключ: %s\r\nтретья\r\n" % fake("", 40)).encode("utf-8"))
        first = run_cli("--check", "--write", str(target))
        self.assertEqual(first.returncode, 1)
        self.assertIn("переписан", first.stdout)
        self.assertEqual(target.read_bytes(),
                         "первая\r\nключ: [REDACTED:API_KEY]\r\nтретья\r\n".encode("utf-8"))
        second = run_cli("--check", str(self.root))
        self.assertEqual(second.returncode, 0)
        leftovers = [p.name for p in self.root.iterdir() if p.name.startswith(".redact-")]
        self.assertEqual(leftovers, [])

    @unittest.skipIf(os.name == "nt", "POSIX file modes")
    def test_write_preserves_file_mode(self):
        target = self.root / "run.sh"
        target.write_text("TOKEN=%s\n" % fake("", 40), encoding="utf-8")
        target.chmod(0o750)
        run_cli("--check", "--write", str(target))
        self.assertEqual(target.stat().st_mode & 0o777, 0o750)

    def test_usage_errors_exit_two(self):
        for args in ([], ["--check"], ["--check", "--bogus"], ["--stdin", "extra"], ["--nope"]):
            with self.subTest(args=args):
                self.assertEqual(run_cli(*args).returncode, 2)

    def test_missing_path_is_reported_without_a_traceback(self):
        done = run_cli("--check", str(self.root / "нет-такого-файла"))
        self.assertEqual(done.returncode, 0)
        self.assertIn("не прочитан", done.stdout)
        self.assertNotIn("Traceback", done.stderr)


class ValueTailTests(unittest.TestCase):
    """Значение, оборванное знаком вне hex/base64, редактировалось не целиком: хвост оставался в тексте."""

    VALUE = fake("", 36)

    def test_the_tail_after_a_symbol_is_part_of_the_secret(self):
        for text in ('API_KEY="%s!tailtail"' % self.VALUE, "token: %s#rest9" % self.VALUE):
            with self.subTest(text=text):
                result = redact_mod.redact(text).text
                self.assertNotIn("tail", result)
                self.assertNotIn("rest9", result)
                self.assertIn("[REDACTED:", result)

    def test_punctuation_around_the_value_is_kept(self):
        self.assertEqual(redact_mod.redact("token: %s." % self.VALUE).text, "token: [REDACTED:TOKEN].")
        self.assertEqual(redact_mod.redact("(secret=%s), next" % self.VALUE).text, "(secret=[REDACTED:SECRET]), next")
        self.assertEqual(redact_mod.redact('"API_KEY": "%s", "x": 1' % self.VALUE).text,
                         '"API_KEY": "[REDACTED:API_KEY]", "x": 1')


if __name__ == "__main__":
    unittest.main()
