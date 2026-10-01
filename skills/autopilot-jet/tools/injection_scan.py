#!/usr/bin/env python3
"""Детектор очевидных приёмов prompt injection в файлах и тексте, которые читает навык.

Навык действует по тексту из репозитория, брифа и файла памяти пользователя. Этот текст — данные,
а не команды. Инструмент ищет в нём приёмы, которым в данных делать нечего, и называет место.
Он НЕ защищает целиком: это поиск по шаблонам, обойти его легко (перефразировать, разбить буквы,
перевести на другой язык). Он ловит нетонкие и автоматические попытки и скрытые символы, и даёт
человеку повод посмотреть. Решение — за человеком.

Правило, из-за которого инструмент устроен именно так: **найденный текст не печатается нигде.**
Вывод инструмента попадает в контекст агента; процитировать в нём враждебную фразу значило бы
доставить её по другому адресу. Печатается только ``путь:строка: вид`` (для скрытых символов —
ещё кодовые точки). Открыть файл и прочитать место — дело человека.

Режимы:

    python3 injection_scan.py --check PATH [PATH ...]   файлы и папки
    python3 injection_scan.py --stdin                   текст со stdin (например, бриф)

Коды выхода: 0 — ничего не найдено, 1 — найдено, 2 — ошибка вызова. Только стандартная библиотека.
"""

import os
import re
import sys
import unicodedata
from collections import Counter, namedtuple

Finding = namedtuple("Finding", "kind line detail")

MAX_FILE_BYTES = 5 * 1024 * 1024
SKIP_DIRS = {".git", "node_modules", "__pycache__"}

# Невидимые символы: у них в тексте для людей нет законной работы, а для модели они читаются.
# U+200C и U+200D (ZWNJ, ZWJ) не трогаем: они нужны эмодзи и персидскому письму.
_TAG = range(0xE0000, 0xE0080)             # «тег-символы»: ASCII, невидимый для глаза
_VARIATION_SUPPLEMENT = range(0xE0100, 0xE01F0)
_BIDI = set(range(0x202A, 0x202F)) | set(range(0x2066, 0x206A))
_ZERO_WIDTH = {0x200B, 0x2060, 0x180E}


def _hidden_chars(text):
    """Находки по невидимым символам. detail — кодовые точки, не текст."""
    found = []
    line = 1
    for index, char in enumerate(text):
        code = ord(char)
        if char == "\n":
            line += 1
            continue
        if code in _TAG:
            found.append(Finding("hidden-tag-chars", line, "U+%04X" % code))
        elif code in _VARIATION_SUPPLEMENT:
            found.append(Finding("hidden-variation-selector", line, "U+%04X" % code))
        elif code in _BIDI:
            found.append(Finding("bidi-control", line, "U+%04X" % code))
        elif code in _ZERO_WIDTH or (code == 0xFEFF and index > 0):
            found.append(Finding("zero-width", line, "U+%04X" % code))
    return found


_FLAGS = re.IGNORECASE | re.UNICODE
_VERB = r"(?:ignore|disregard|forget|override|bypass|overrule)"
_NOUN = r"(?:instructions?|prompts?|rules|guidelines|directions|constraints|safeguards|guardrails)"
_QUALIFIER = r"(?:previous|prior|above|earlier|preceding|system|your|original)"
_RU_VERB = r"(?:игнорируй(?:те)?|забудь(?:те)?|не\s+учитывай(?:те)?|отмени(?:те)?|обойди(?:те)?)"
_RU_NOUN = r"(?:инструкци\w*|правил\w*|указани\w*|промпт\w*|ограничени\w*)"
_RU_QUALIFIER = r"(?:предыдущ\w*|прежн\w*|выше|системн\w*|свои|все|любые|эти)"

# (kind, pattern). Порядок значения не имеет; кортеж собирается один раз.
_PATTERNS = [
    ("override-phrase", re.compile(
        r"\b%s(?:\s+\w+){0,2}\s+%s(?:\s+\w+){0,2}\s+%s\b" % (_VERB, _QUALIFIER, _NOUN), _FLAGS)),
    ("override-phrase", re.compile(
        r"\b%s(?:\s+\w+){0,2}\s+(?:all|any|the|these|those)(?:\s+\w+){0,2}\s+(?:instructions?|prompts?)\b" % _VERB,
        _FLAGS)),
    ("override-phrase", re.compile(
        r"\bforget\s+(?:everything|all)\s+(?:you|that|above|before|i|we)\b", _FLAGS)),
    ("override-phrase", re.compile(
        r"(?<!\w)%s(?:\s+\w+){0,2}\s+%s(?:\s+\w+){0,2}\s+%s(?!\w)" % (_RU_VERB, _RU_QUALIFIER, _RU_NOUN), _FLAGS)),
    ("conceal-from-user", re.compile(
        r"\b(?:do\s+not|don'?t|never|without)\b(?:\s+\w+){0,3}?\s+"
        r"(?:tell|telling|inform|informing|notify|notifying|alert|alerting)\s+(?:the\s+)?(?:user|human|operator)\b",
        _FLAGS)),
    ("conceal-from-user", re.compile(
        r"(?<!\w)не\s+(?:говори|сообщай|рассказывай|показывай)(?:те)?\s+(?:об\s+этом\s+)?пользователю", _FLAGS)),
    ("reveal-prompt", re.compile(
        r"\b(?:reveal|print|output|show|repeat|leak)\b(?:\s+\w+){0,3}?\s+(?:your|the)\s+"
        r"(?:system\s+prompt|hidden\s+(?:prompt|instructions)|initial\s+instructions)", _FLAGS)),
    ("reveal-prompt", re.compile(
        r"(?<!\w)(?:раскрой|покажи|выведи|повтори)(?:те)?\s+(?:свой\s+|твой\s+)?системн\w*\s+(?:промпт|инструкци\w*)",
        _FLAGS)),
    ("exfiltration-request", re.compile(
        r"\b(?:send|post|upload|exfiltrate|forward|email)\b[^.\n]{0,60}"
        r"(?:\b(?:secrets?|credentials?|tokens?|api[ _-]?keys?|passwords?|ssh[ _-]?keys?)\b|(?<!\w)\.env\b)[^.\n]{0,60}"
        r"(?:https?://|\bto\s+\S+@\S+)", _FLAGS)),
    ("role-spoof", re.compile(
        r"<\|(?:im_start|im_end|system|user|assistant|endoftext)\|>|\[/?INST\]|<<\s*/?SYS\s*>>|</?system>",
        _FLAGS)),
    ("pipe-to-shell", re.compile(
        r"\b(?:curl|wget)\b[^\n|;]*\|\s*(?:sudo\s+)?(?:ba|z|da|k)?sh\b", _FLAGS)),
    ("pipe-to-shell", re.compile(
        r"\b(?:iwr|irm|invoke-webrequest|invoke-restmethod)\b[^\n]*\|\s*iex\b", _FLAGS)),
]
# Виды, которые в HTML-комментарии выдают спрятанное обращение к модели. pipe-to-shell и role-spoof
# в комментариях встречаются в обычной документации, поэтому сюда не входят.
_COMMENT_KINDS = {"override-phrase", "conceal-from-user", "reveal-prompt", "exfiltration-request"}
_COMMENT = re.compile(r"<!--(.*?)-->", re.DOTALL)
_ADDRESSED_TO_AI = re.compile(
    r"\b(?:ai|assistant|agent|llm|claude|chatgpt|copilot|cursor|gpt)\b[^\n]{0,40}"
    r"\b(?:must|should|always|never|do\s+not|don'?t|run|execute|ignore|instead)\b", _FLAGS)


def _line_of(text, offset):
    return text.count("\n", 0, offset) + 1


def _phrase_findings(text):
    found = []
    for kind, pattern in _PATTERNS:
        for match in pattern.finditer(text):
            found.append(Finding(kind, _line_of(text, match.start()), ""))
    for comment in _COMMENT.finditer(text):
        body = comment.group(1)
        if _ADDRESSED_TO_AI.search(body) or any(p.search(body) for k, p in _PATTERNS if k in _COMMENT_KINDS):
            found.append(Finding("hidden-comment", _line_of(text, comment.start()), ""))
    return found


def find(text):
    """Находки в тексте без самого текста. Возвращает список Finding без повторов (вид, строка)."""
    found = _hidden_chars(text)
    found += _phrase_findings(text)
    # Полноширинные и подобные буквы: если NFKC не меняет длину, сопоставление позиций сохраняется.
    folded = unicodedata.normalize("NFKC", text)
    if folded != text and len(folded) == len(text):
        found += _phrase_findings(folded)
    seen, unique = set(), []
    for item in sorted(found, key=lambda f: (f.line, f.kind, f.detail)):
        key = (item.kind, item.line, item.detail)
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def _format(item):
    return "%s%s" % (item.kind, (" " + item.detail) if item.detail else "")


def _iter_files(paths):
    for path in paths:
        if os.path.isdir(path):
            for root, dirs, files in os.walk(path):
                dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
                for name in sorted(files):
                    yield os.path.join(root, name)
        else:
            yield path


def check_paths(paths, out=None):
    """Сканирует пути. Печатает ``путь:строка: вид`` и итог. Возвращает код выхода."""
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
        for item in find(text):
            hits += 1
            print("%s:%d: %s" % (path, item.line, _format(item)), file=out)
    print("injection-scan: файлов %d, пропущено %d, находок %d" % (scanned, skipped, hits), file=out)
    return 1 if hits else 0


def _stdin_mode():
    text = sys.stdin.buffer.read().decode("utf-8", errors="replace")
    findings = find(text)
    for item in findings:
        print("stdin:%d: %s" % (item.line, _format(item)))
    counts = Counter(item.kind for item in findings)
    print("injection-scan: находок %d%s" % (len(findings), "".join(" · %s x%d" % kv for kv in sorted(counts.items()))))
    return 1 if findings else 0


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
        paths = args[1:]
        if not paths or any(item.startswith("--") for item in paths):
            print("использование: injection_scan.py --check PATH [PATH ...]", file=sys.stderr)
            return 2
        return check_paths(paths)
    print(__doc__.strip().splitlines()[0], file=sys.stderr)
    print("использование: injection_scan.py --stdin | --check PATH [PATH ...]", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
