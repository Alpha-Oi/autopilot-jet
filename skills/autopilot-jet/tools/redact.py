#!/usr/bin/env python3
"""Детерминированный фильтр секретов: таблица форм из phases/1-manifest.md.

Заменяет значение на ``[REDACTED:<VAR_NAME>]``; имя переменной остаётся, значение —
нет. Само значение не печатается нигде: ни в stdout, ни в stderr, ни в сообщениях
об ошибках.

Режимы:

    python3 redact.py --stdin                  текст со stdin -> очищенный текст в stdout
    python3 redact.py --check PATH [PATH ...]  найти секреты в файлах и папках
    python3 redact.py --check --write PATH ... то же и переписать найденное на месте

Коды выхода: 0 — чисто (для ``--stdin`` всегда 0), 1 — секреты найдены, 2 — ошибка
вызова. Только стандартная библиотека; файлы читаются и пишутся как UTF-8 байты, так
что переводы строк не меняются.
"""

import os
import re
import shutil
import sys
import tempfile
from collections import Counter, namedtuple

Finding = namedtuple("Finding", "kind name start end")
Result = namedtuple("Result", "text findings")

MAX_FILE_BYTES = 5 * 1024 * 1024
SKIP_DIRS = {".git", "node_modules", "__pycache__"}

_STRIPE_NAMES = {
    "sk": "STRIPE_SECRET_KEY",
    "rk": "STRIPE_RESTRICTED_KEY",
    "pk": "STRIPE_PUBLISHABLE_KEY",
}
_SLACK_NAMES = {"b": "SLACK_BOT_TOKEN", "p": "SLACK_USER_TOKEN", "a": "SLACK_TOKEN"}
_SCHEME_NAMES = {
    "postgres": "DATABASE_URL", "postgresql": "DATABASE_URL",
    "mysql": "DATABASE_URL", "mariadb": "DATABASE_URL",
    "mongodb": "MONGODB_URI", "mongodb+srv": "MONGODB_URI",
    "redis": "REDIS_URL", "rediss": "REDIS_URL",
    "amqp": "AMQP_URL", "amqps": "AMQP_URL",
    "http": "BASIC_AUTH_URL", "https": "BASIC_AUTH_URL",
}
_KEYWORD_NAMES = {
    "key": "API_KEY", "ключ": "API_KEY",
    "token": "ACCESS_TOKEN", "токен": "ACCESS_TOKEN", "доступ": "ACCESS_TOKEN",
    "secret": "SECRET",
    "password": "PASSWORD", "пароль": "PASSWORD",
}

_SEP = r"[\s:=—–\"'«»(),-]{1,8}"
_KEYWORDS = "key|token|secret|password|passwd|pwd|ключ|токен|пароль|доступ"
# Значение, оборванное знаком вне набора hex/base64 (`abc…!tail`), редактируется целиком: хвост до пробела, кавычки или
# скобки тоже часть секрета. Знаки конца фразы (`. , : ; ?`) в хвост не входят, иначе съелась бы пунктуация вокруг.
_TAIL = r"(?:[^\s\"'`,;<>)\]}]*[^\s\"'`,;<>)\]}.:?])?"


def _env_name(identifier):
    """Имя переменной из идентификатора; для не-ASCII (``токен``, ``ключ``) — по ключевому слову."""
    if not identifier.isascii():
        word = re.search(_KEYWORDS, identifier, re.IGNORECASE)
        return _keyword_name(word.group(0)) if word else "SECRET"
    name = re.sub(r"[^A-Za-z0-9_]", "_", identifier).upper()
    return name if re.match(r"[A-Z_]", name) else "_" + name


def _has_digit(value):
    return any(ch.isdigit() for ch in value)


def _looks_like_words(value):
    """Дефисные/подчёркнутые слова и пути не похожи на hex/base64: два и более «слова»."""
    parts = re.split(r"[-_/]", value)
    return sum(1 for part in parts if len(part) >= 4 and part.isalpha()) >= 2


def _secret_like(value):
    return _has_digit(value) and not _looks_like_words(value)


def _keyword_name(word):
    word = word.lower()
    if word in ("passwd", "pwd"):
        word = "password"
    return _KEYWORD_NAMES.get(word, "SECRET")


# (kind, compiled regex, group that holds the value (0 = whole match), name(match), priority)
# Меньший priority побеждает при пересечении; общие формы идут последними.
def _build_rules():
    rules = []

    def add(kind, pattern, name, group=0, priority=1, flags=0, accept=None):
        rules.append((kind, re.compile(pattern, flags), group, name, priority, accept))

    add("private-key",
        r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----[\s\S]*?(?:-----END [A-Z0-9 ]*PRIVATE KEY-----|\Z)",
        lambda m: "PRIVATE_KEY", priority=0)
    add("connection-string",
        r"\b([a-zA-Z][a-zA-Z0-9+.-]{1,30})://[^\s:/@'\"`<>]+:[^\s@/'\"`<>]+@[^\s/'\"`<>)]+(?:/[^\s'\"`<>)]*)?",
        lambda m: _SCHEME_NAMES.get(m.group(1).lower(), "CONNECTION_STRING"), priority=1)
    add("jwt", r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}(?:\.[A-Za-z0-9_-]+)?",
        lambda m: "JWT_TOKEN")
    add("stripe", r"\b(sk|rk|pk)_(?:live|test)_[A-Za-z0-9]{10,}",
        lambda m: _STRIPE_NAMES[m.group(1)])
    add("openai-style", r"(?<![A-Za-z0-9_])sk-(ant-|proj-)?[A-Za-z0-9_-]{20,}",
        lambda m: "ANTHROPIC_API_KEY" if m.group(1) == "ant-" else "OPENAI_API_KEY")
    add("github", r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{20,})",
        lambda m: "GITHUB_TOKEN")
    add("aws", r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b", lambda m: "AWS_ACCESS_KEY_ID")
    add("google-api", r"\bAIza[0-9A-Za-z_-]{35}(?![0-9A-Za-z_-])", lambda m: "GOOGLE_API_KEY")
    add("google-oauth", r"\bya29\.[0-9A-Za-z_-]{20,}", lambda m: "GOOGLE_OAUTH_TOKEN")
    add("slack", r"\bxox([bpa])-[A-Za-z0-9-]{10,}", lambda m: _SLACK_NAMES[m.group(1)])
    add("telegram", r"(?<![\w:])\d{8,10}:[A-Za-z0-9_-]{35}(?![\w-])",
        lambda m: "TELEGRAM_BOT_TOKEN")
    # Общая форма 1: NAME=value / NAME: "value" — имя берётся из самой строки.
    add("generic-assignment",
        r"(?i)(?<![A-Za-z0-9_])((?:[A-Za-z_][A-Za-z0-9_.-]*?)?(?:" + _KEYWORDS +
        r")[A-Za-z0-9_.-]*)[\"']?\s*[:=]\s*[\"']?([A-Za-z0-9][A-Za-z0-9+/_=-]{31,}" + _TAIL + ")",
        lambda m: _env_name(m.group(1)), group=2, priority=5,
        accept=lambda m: _secret_like(m.group(2)))
    # Общая форма 2: «токен: <значение>», «password is <значение>».
    add("generic-near-keyword",
        r"(?i)(?<![A-Za-z0-9_])(" + _KEYWORDS + r")[^\W\d_]*(?:\s+[^\W\d_]{1,12}){0,3}" + _SEP +
        r"([A-Za-z0-9][A-Za-z0-9+/_=-]{31,}" + _TAIL + ")",
        lambda m: _keyword_name(m.group(1)), group=2, priority=6,
        accept=lambda m: _secret_like(m.group(2)))
    return rules


_RULES = _build_rules()


def find(text):
    """Находит секреты. Возвращает неперекрывающиеся Finding по позициям в ``text``."""
    candidates = []
    for kind, pattern, group, name, priority, accept in _RULES:
        for match in pattern.finditer(text):
            if accept is not None and not accept(match):
                continue
            start, end = match.span(group)
            if start == end:
                continue
            candidates.append((start, priority, -(end - start), Finding(kind, name(match), start, end)))
    candidates.sort(key=lambda item: item[:3])
    chosen, last_end = [], 0
    for start, _priority, _length, finding in candidates:
        if start >= last_end:
            chosen.append(finding)
            last_end = finding.end
    return chosen


def redact(text):
    """Возвращает ``Result(text, findings)``; значение секрета в результат не попадает."""
    findings = find(text)
    out, cursor = [], 0
    for item in findings:
        out.append(text[cursor:item.start])
        out.append("[REDACTED:%s]" % item.name)
        cursor = item.end
    out.append(text[cursor:])
    return Result("".join(out), findings)


def _line_of(text, offset):
    return text.count("\n", 0, offset) + 1


def _iter_files(paths):
    for path in paths:
        if os.path.isdir(path):
            for root, dirs, files in os.walk(path):
                dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
                for name in sorted(files):
                    yield os.path.join(root, name)
        else:
            yield path


def _atomic_write(path, data):
    directory = os.path.dirname(os.path.abspath(path))
    handle, tmp = tempfile.mkstemp(prefix=".redact-", dir=directory)
    try:
        with os.fdopen(handle, "wb") as out:
            out.write(data)
        shutil.copymode(path, tmp)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def check_paths(paths, write=False, out=None):
    """Сканирует пути. Печатает ``path:line: NAME`` и итог. Возвращает код выхода."""
    out = out or sys.stdout
    hits = skipped = scanned = 0
    for path in _iter_files(paths):
        try:
            if os.path.getsize(path) > MAX_FILE_BYTES:
                print("%s: пропущен (больше %d МБ)" % (path, MAX_FILE_BYTES // (1024 * 1024)), file=out)
                skipped += 1
                continue
            with open(path, "rb") as handle:
                data = handle.read()
        except OSError as error:
            print("%s: не прочитан (%s)" % (path, error.strerror or "ошибка"), file=out)
            skipped += 1
            continue
        if b"\x00" in data[:8192]:
            skipped += 1
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            print("%s: пропущен (не UTF-8)" % path, file=out)
            skipped += 1
            continue
        scanned += 1
        result = redact(text)
        for item in result.findings:
            hits += 1
            print("%s:%d: %s%s" % (path, _line_of(text, item.start), item.name,
                                   " (переписан)" if write else ""), file=out)
        if write and result.findings:
            _atomic_write(path, result.text.encode("utf-8"))
    print("redact: файлов %d, пропущено %d, секретов %d" % (scanned, skipped, hits), file=out)
    return 1 if hits else 0


def _stdin_mode():
    raw = sys.stdin.buffer.read().decode("utf-8", errors="replace")
    result = redact(raw)
    sys.stdout.buffer.write(result.text.encode("utf-8"))
    sys.stdout.buffer.flush()
    for name, count in Counter(item.name for item in result.findings).items():
        print("redacted: %s x%d" % (name, count), file=sys.stderr)
    return 0


def _safe_streams():
    """Консоль Windows может быть не UTF-8: нечитаемый символ в пути не должен ронять отчёт."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="backslashreplace")
        except (AttributeError, ValueError):
            pass


def main(argv=None):
    _safe_streams()
    args = list(sys.argv[1:] if argv is None else argv)
    if args == ["--stdin"]:
        return _stdin_mode()
    if args and args[0] == "--check":
        rest = args[1:]
        write = "--write" in rest
        paths = [item for item in rest if item != "--write"]
        if not paths or any(item.startswith("--") for item in paths):
            print("использование: redact.py --check [--write] PATH [PATH ...]", file=sys.stderr)
            return 2
        return check_paths(paths, write=write)
    print(__doc__.strip().splitlines()[0], file=sys.stderr)
    print("использование: redact.py --stdin | --check [--write] PATH [PATH ...]", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
