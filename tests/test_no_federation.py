"""Навык ни с чем не объединяется (REQ-COND-02 стандарта DOA: федерация запрещена, и запрет проверяется).

Федерация — это обмен данными, задачами или идентичностью с другой системой по сети. Проверяется то, что
проверяется машиной. Скрипты навыка открывают соединения только на 127.0.0.1, а сервер дашборда слушает только
127.0.0.1, поэтому снаружи до него не достучаться. Страница дашборда читает один файл рядом с собой и ничего
внешнего не подгружает. Запрет записан в SKILL.md.

Чего здесь нет: сетевые инструменты самого хоста (провайдер модели, git, установщик) лежат вне границы навыка,
а продукт, который исполнитель строит в проекте пользователя, может ходить в сеть по замыслу заказчика.
Что навык не добавляет федерации, остаётся инструкцией для LLM: проверены скрипты и шаблон страницы.

Функции проверки проверены на синтетическом коде: тест, который не умеет краснеть, ничего не доказывает.
"""

import ast
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).parents[1]
TOOL_DIRS = (ROOT / "skills" / "autopilot-jet" / "tools", ROOT / "tools")
TEMPLATE = ROOT / "skills" / "autopilot-jet" / "phases" / "dashboard-template.html"
SKILL = ROOT / "skills" / "autopilot-jet" / "SKILL.md"

LOOPBACK = "127.0.0.1"
LOOPBACK_URL = "http://127.0.0.1:"
NETWORK_MODULES = {"http.client", "ftplib", "smtplib", "poplib", "imaplib", "nntplib", "telnetlib", "xmlrpc",
                   "ssl", "smtpd", "socketserver", "webbrowser"}
ALWAYS_OUTBOUND = {"connect", "connect_ex", "create_connection", "sendto", "gethostbyname", "gethostbyname_ex",
                   "getaddrinfo", "getfqdn"}


def network_imports(source):
    """Импорты сетевых клиентов и серверов, которых навыку не нужно."""
    found = set()
    for node in ast.walk(ast.parse(source)):
        names = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names = [node.module]
        for name in names:
            if any(name == module or name.startswith(module + ".") for module in NETWORK_MODULES):
                found.add(name)
    return sorted(found)


def _is_loopback_url(node):
    """Строка-литерал `http://127.0.0.1:...` или такая же, подставленная через `%`."""
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
        node = node.left
    return isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.startswith(LOOPBACK_URL)


def _call_name(node):
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return None


def non_loopback_connections(source):
    """Обращения к сети, которые не доказаны как обращения к 127.0.0.1."""
    found = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        name = _call_name(node)
        first = node.args[0] if node.args else None
        if name == "urlopen" and not (first is not None and _is_loopback_url(first)):
            found.append("urlopen")
        elif name == "bind":
            ok = (isinstance(first, ast.Tuple) and first.elts and isinstance(first.elts[0], ast.Constant)
                  and first.elts[0].value == LOOPBACK)
            if not ok:
                found.append("bind")
        elif name in ALWAYS_OUTBOUND:
            found.append(name)
    return found


def servers_not_bound_to_loopback(source):
    """Списки аргументов запуска `http.server` без `--bind 127.0.0.1` подряд. Возвращает (всего серверов, плохих)."""
    total = bad = 0
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.List):
            continue
        words = [elt.value if isinstance(elt, ast.Constant) and isinstance(elt.value, str) else None
                 for elt in node.elts]
        if "http.server" not in words:
            continue
        total += 1
        if not any(a == "--bind" and b == LOOPBACK for a, b in zip(words, words[1:])):
            bad += 1
    return total, bad


def external_references(html):
    """Всё, что страница берёт не из себя: адреса, сетевые вызовы."""
    found = []
    if re.search(r"https?://", html):
        found.append("absolute url")
    if re.search(r"(?<![:\w])//[A-Za-z0-9.-]+\.[A-Za-z]{2,}", html):
        found.append("protocol-relative url")
    if re.search(r"\bfetch\s*\(|\bnew\s+XMLHttpRequest\b|\bnew\s+WebSocket\b|\bnew\s+EventSource\b"
                 r"|\bsendBeacon\s*\(|\bimportScripts\s*\(", html):
        found.append("network api")
    return found


def lacks(text, marker):
    return marker not in text


def product_sources():
    for directory in TOOL_DIRS:
        for path in sorted(directory.glob("*.py")):
            yield path, path.read_text(encoding="utf-8")


class CheckersCanTurnRed(unittest.TestCase):
    def test_network_clients_are_found(self):
        source = "import os\nimport smtplib\nfrom http.client import HTTPSConnection\nimport ssl, json\nfrom xmlrpc.client import ServerProxy\n"
        self.assertEqual(network_imports(source), ["http.client", "smtplib", "ssl", "xmlrpc.client"])
        self.assertEqual(network_imports("import os, json, urllib.request, socket\n"), [])

    def test_a_loopback_probe_is_allowed_and_any_other_url_is_not(self):
        ok = ('import urllib.request\nurllib.request.urlopen("http://127.0.0.1:%d%s" % (port, path), timeout=2)\n'
              'urllib.request.urlopen("http://127.0.0.1:8123/x")\n')
        self.assertEqual(non_loopback_connections(ok), [])
        for bad in ('urllib.request.urlopen("http://example.com/")',
                    'urllib.request.urlopen("https://127.0.0.1:1/")',
                    'urllib.request.urlopen(url)',
                    'urllib.request.urlopen("http://localhost:8123/")',
                    'urlopen("http://10.0.0.1:80/")'):
            with self.subTest(call=bad):
                self.assertEqual(non_loopback_connections("import urllib.request\n" + bad + "\n"), ["urlopen"])

    def test_binding_is_allowed_to_loopback_only(self):
        self.assertEqual(non_loopback_connections('s.bind(("127.0.0.1", p))\n'), [])
        for bad in ('s.bind(("0.0.0.0", 80))', 's.bind(("", 80))', 's.bind(addr)', 's.bind((host, 80))'):
            with self.subTest(call=bad):
                self.assertEqual(non_loopback_connections(bad + "\n"), ["bind"])

    def test_outbound_socket_calls_are_found(self):
        source = ('import socket\ns = socket.socket()\ns.connect(("example.com", 80))\n'
                  'socket.create_connection(("a", 1))\nsocket.gethostbyname("a")\ns.sendto(b"x", ("a", 1))\n')
        self.assertEqual(sorted(non_loopback_connections(source)),
                         ["connect", "create_connection", "gethostbyname", "sendto"])

    def test_a_server_must_be_bound_to_loopback(self):
        good = 'subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1", "--directory", A])\n'
        self.assertEqual(servers_not_bound_to_loopback(good), (1, 0))
        for bad in ('x = [sys.executable, "-m", "http.server", "8000"]',
                    'x = [sys.executable, "-m", "http.server", "--bind", "0.0.0.0"]',
                    'x = [sys.executable, "-m", "http.server", "--bind", "::"]',
                    'x = [sys.executable, "-m", "http.server", "--bind=127.0.0.1"]'):
            with self.subTest(args=bad):
                self.assertEqual(servers_not_bound_to_loopback(bad + "\n"), (1, 1))
        self.assertEqual(servers_not_bound_to_loopback('x = ["ps", "-A"]\n'), (0, 0))

    def test_external_references_in_a_page_are_found(self):
        self.assertEqual(external_references('<script src="state.js"></script> const a = "data:image/png;base64,AAA";'), [])
        for bad, kind in (('<script src="https://cdn.example.com/x.js"></script>', "absolute url"),
                          ('<link href="http://fonts.example.com/a.css">', "absolute url"),
                          ('<script src="//cdn.example.com/x.js"></script>', "protocol-relative url"),
                          ("fetch('state.js')", "network api"), ("new XMLHttpRequest()", "network api"),
                          ("new WebSocket(u)", "network api"), ("navigator.sendBeacon(u, d)", "network api")):
            with self.subTest(page=bad):
                self.assertIn(kind, external_references(bad))

    def test_a_comment_that_names_fetch_is_not_a_call(self):
        self.assertEqual(external_references("// ни через fetch, ни через XHR\n"), [])
        self.assertEqual(external_references("// путь вида a//b.c не URL: x // y\n"), [])

    def test_a_missing_declaration_is_found(self):
        self.assertTrue(lacks("# nothing\n", "federation: none"))
        self.assertFalse(lacks("`federation: none`\n", "federation: none"))


class ScriptsOpenOnlyLoopback(unittest.TestCase):
    def test_there_are_scripts_to_check_and_they_are_not_vacuous(self):
        names = [path.name for path, _source in product_sources()]
        self.assertIn("sync.py", names)
        sync = dict((path.name, source) for path, source in product_sources())["sync.py"]
        self.assertIn("urlopen", sync)
        self.assertIn(".bind(", sync)
        self.assertEqual(servers_not_bound_to_loopback(sync)[0], 1)

    def test_no_script_imports_a_network_client(self):
        for path, source in product_sources():
            with self.subTest(tool=path.name):
                self.assertEqual(network_imports(source), [])

    def test_no_script_opens_a_connection_that_is_not_to_loopback(self):
        for path, source in product_sources():
            with self.subTest(tool=path.name):
                self.assertEqual(non_loopback_connections(source), [])

    def test_every_server_a_script_starts_is_bound_to_loopback(self):
        for path, source in product_sources():
            with self.subTest(tool=path.name):
                total, bad = servers_not_bound_to_loopback(source)
                self.assertEqual(bad, 0, "%s: сервер без --bind 127.0.0.1" % path.name)


class DashboardReadsOnlyItself(unittest.TestCase):
    def test_the_template_refers_to_nothing_off_the_page(self):
        self.assertEqual(external_references(TEMPLATE.read_text(encoding="utf-8")), [])

    def test_the_state_file_is_loaded_by_a_relative_path(self):
        html = TEMPLATE.read_text(encoding="utf-8")
        self.assertIn('<script src="state.js" data-state-source></script>', html)


class TheDeclarationIsWritten(unittest.TestCase):
    def test_skill_declares_no_federation(self):
        text = SKILL.read_text(encoding="utf-8")
        self.assertFalse(lacks(text, "## Autopilot federates with nothing"))
        self.assertFalse(lacks(text, "federation: none"))
        self.assertFalse(lacks(text, "tests/test_no_federation.py"))


if __name__ == "__main__":
    unittest.main()
