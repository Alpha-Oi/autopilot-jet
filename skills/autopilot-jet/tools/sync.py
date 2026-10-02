#!/usr/bin/env python3
"""Зеркалит state.js в саму страницу дашборда и держит сервер живым.

Вызывается после каждой правки .autopilot/state.js — одной строкой, без аргументов:

    python3 .autopilot/sync.py

Делает ровно три вещи, в этом порядке:

  1. Проверяет, что state.js разбирается. Битый файл не идёт дальше: снимок на
     странице остаётся прежним, а не затирается мусором.
  2. Вписывает состояние внутрь dashboard.html между маркерами — атомарно, через
     временный файл рядом. Оборвётся на середине — на месте останется целая
     прежняя страница. Отсюда дашборд показывает данные, даже когда его открыли
     файлом, из панели через data:, с мёртвым сервером или через месяц после
     прогона.
  3. Смотрит, жив ли статический сервер этого прогона, и поднимает на прежнем
     порту, если нет. Прежний порт — чтобы ссылка, которую пользователь уже
     скопировал, продолжала работать.

Ничего не печатает в чат сама по себе: одна строка на stdout, её видит агент.

Отдельный режим, который ничего не пишет и сервер не трогает:

    python3 <каталог навыка>/tools/sync.py --other-window [КАТАЛОГ]

Отвечает на вопрос четвёртого случая из phases/0-preflight.md: идёт ли этот прогон в другом окне.
Коды выхода: 0 — нет (обычное возобновление или нет прогона), 1 — да, 3 — не удалось определить.
Запускать нужно из каталога навыка, а не из .autopilot/sync.py: копия в .autopilot/ может быть старой
и тогда выполнит обычную синхронизацию.

Второй такой же режим, тоже только чтение — возраст копий в прогоне (REQ-CORE-21 стандарта DOA):

    python3 <каталог навыка>/tools/sync.py --aging [КАТАЛОГ]

В .autopilot/ лежат копии двух файлов навыка: sync.py и dashboard.html. Навык обновляют, а копии остаются
старыми. Режим сверяет их с установленным навыком и называет устаревшие. Индекс старения — доля копий,
которые не совпали (0 — все свежие). Коды выхода: 0 — все свежие или прогона нет, 1 — есть устаревшие,
3 — запущено не из каталога навыка.

Третий такой же режим, тоже только чтение — состояние прогона перед возобновлением (REQ-CORE-22 стандарта DOA):

    python3 <каталог навыка>/tools/sync.py --run-status [КАТАЛОГ]

Закрытый прогон (finishedAt стоит) возобновлять нельзя: его закрыли, и записанное в нём состояние уже не про
сегодняшний репозиторий. Режим называет: none (прогона нет), open, closed, stale (открытый, но давно не
писался), resurrected (закрытый прогон снова пишется, или открытый лежит в каталоге без --wip), unknown.
Коды выхода: 0 — none или open, 1 — closed, 3 — нужен человек (stale, resurrected, unknown).

Четвёртый такой же режим, тоже только чтение — печать брифа (REQ-CORE-03 и REQ-CORE-09 стандарта DOA):

    python3 <каталог навыка>/tools/sync.py --brief-seal [КАТАЛОГ]

Бриф — желаемое состояние прогона: слова пользователя, с которыми сверяется готовый результат. Текст выше
«## Дополнения» не редактируется (phases/1-manifest.md §2), поэтому его хеш записывают в state.js как
`briefSeals[<имя файла>]`, а режим сверяет файл с записью. Дополнения ниже заголовка растут и в хеш не входят.
Режим только читает и печатает хеш: записывает его агент. Коды выхода: 0 — все брифы совпали или прогона нет,
1 — есть не запечатанный бриф (хеш напечатан), 3 — бриф изменён, исчез или не прочитан.

Пятый такой же режим, тоже только чтение — файлы таска против его зоны (REQ-CORE-05 и REQ-CORE-26 стандарта DOA):

    python3 <каталог навыка>/tools/sync.py --zone-check [КАТАЛОГ]

У каждого готового таска в state.js есть `zone` (пути-префиксы, которыми он владеет) и `commit` (один коммит на таск).
Режим берёт файлы коммита из git (`git diff-tree`, только чтение) и называет те, что лежат вне зоны. Вне зоны
допустимы только `.autopilot/` и файл памяти проекта (`memoryFile`). Это приговор, а не запрет: файл уже в коммите.
Коды выхода: 0 — все проверенные таски в своих зонах или готовых тасков нет, 1 — есть файлы вне зоны, 3 — таск
проверить нечем (нет zone или commit, коммита нет в git, git не ответил), 2 — ошибка вызова.
"""

import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

A = os.path.dirname(os.path.abspath(__file__))          # .autopilot этого прогона
STATE = os.path.join(A, "state.js")
PAGE = os.path.join(A, "dashboard.html")
PIDF = os.path.join(A, "serve.pid")
LOG = os.path.join(A, "serve.log")
BEGIN, END = "/*STATE-BEGIN*/", "/*STATE-END*/"
PROCESS_DELIMITER = "\x1f"

# Потолки из инструкций (phases/5-repair.md, 4-plan.md, polish.md). Здесь они только названы:
# audit() сверяет с ними state.js, ничего не чинит и не блокирует.
COUNTER_CEILING = 2       # repairs, retries, handoffs на один таск
TICKET_CEILING = 16       # таски плана; P-таски доводки считаются отдельно
POLISH_ROUNDS_CEILING = 3
RESUME_STALE_DAYS = 7           # открытый прогон, не писавшийся дольше, возобновляют только по слову пользователя
LIVE_TICKET_STATUSES = ("in-progress", "review", "repair")
OTHER_WINDOW_SECONDS = 300   # «меньше пяти минут» из четвёртого случая phases/0-preflight.md
COUNTERS = ("repairs", "retries", "handoffs")

# Допустимые значения «ручек» прогона (phases/0-modes.md, 4-plan.md). Ручки решаются один раз
# в начале и записываются в state.js: по записи восстанавливается политика прогона.
DIAL_VALUES = {
    "mode": ("full", "semi", "interview", "manual"),
    "depth": ("strict", "normal", "deep"),
    "tier": ("T0", "T1", "T2", "T3"),
}


def fail(msg):
    print(msg)
    sys.exit(1)


def _state_body(raw):
    """JSON из state.js: после `window.STATE =` в первой строке, без хвостового `;`."""
    body = raw.split("=", 1)[1] if "=" in raw.split("\n", 1)[0] else raw
    return body.strip().rstrip(";")


def read_state():
    try:
        raw = open(STATE, encoding="utf-8").read()
    except FileNotFoundError:
        fail("state.js ещё нет — снимок не вписан, сервер не тронут")
    try:
        return json.loads(_state_body(raw))
    except json.JSONDecodeError as e:
        # Здесь и был режим отказа «файл помялся»: раньше он был виден только по
        # пустой странице, теперь — строкой с номером строки, сразу после записи.
        fail("state.js не разбирается (строка %d: %s) — снимок оставлен прежним" % (e.lineno, e.msg))


def write_snapshot(state):
    """Снимок внутрь страницы. Возвращает текст для отчёта."""
    try:
        page = open(PAGE, encoding="utf-8").read()
    except FileNotFoundError:
        return "страницы нет — перекопируй dashboard.html из навыка"
    i, j = page.find(BEGIN), page.find(END)
    if i < 0 or j < 0:
        return "страница без маркеров снимка — перекопируй dashboard.html из навыка"
    # </ внутри <script> закрыл бы тег и порвал страницу; < безопасен в JSON.
    payload = "window.STATE=" + json.dumps(state, ensure_ascii=False).replace("</", "<\\/") + ";"
    new = page[: i + len(BEGIN)] + payload + page[j:]
    if new == page:
        return "снимок уже совпадал"
    tmp = PAGE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(new)
    os.replace(tmp, PAGE)                                # атомарно: битой страницы не бывает
    return "снимок вписан"


def http_ok(port, path="/dashboard.html"):
    try:
        with urllib.request.urlopen("http://127.0.0.1:%d%s" % (port, path), timeout=2) as r:
            return r.status == 200
    except (urllib.error.URLError, OSError, ValueError):
        return False


def _query_timeout(seconds):
    """Холодный запуск powershell.exe + CIM на Windows занимает секунды: лимит шире, чем у ``ps``."""
    return seconds * 4 if os.name == "nt" else seconds


def cmdline(pid):
    if os.name == "nt":
        command = (
            "(Get-CimInstance -ClassName Win32_Process -Filter "
            "'ProcessId = %d' -ErrorAction Stop).CommandLine" % int(pid)
        )
        argv = ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command]
    else:
        argv = ["ps", "-p", str(pid), "-o", "command="]
    try:
        result = subprocess.run(argv, capture_output=True, text=True,
                                timeout=_query_timeout(5), check=False)
        return result.stdout.strip() if result.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError, ValueError, TypeError):
        return ""


def process_status(pid):
    """Положительное отсутствие отличается от сбоя запроса; PID не сигналим."""
    try:
        pid = int(pid)
        if pid <= 0:
            return "unknown"
        if os.name == "nt":
            command = (
                "$ErrorActionPreference = 'Stop'; "
                "$process = Get-CimInstance -ClassName Win32_Process -Filter "
                "'ProcessId = %d' -ErrorAction Stop; "
                "if ($null -eq $process) { 'absent' } else { 'present' }" % pid
            )
            argv = ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command]
        else:
            argv = ["ps", "-Ao", "pid="]
        result = subprocess.run(argv, capture_output=True, text=True,
                                timeout=_query_timeout(5), check=False)
        if result.returncode != 0 or result.stderr.strip():
            return "unknown"
        output = result.stdout.strip()
        if os.name == "nt":
            return output if output in ("present", "absent") else "unknown"
        pids = output.split()
        if not pids or not all(value.isdigit() and int(value) > 0 for value in pids):
            return "unknown"
        return "present" if str(pid) in pids else "absent"
    except (OSError, subprocess.SubprocessError, ValueError, TypeError):
        return "unknown"


def iter_processes():
    """Возвращает пары ``(pid, command line)`` или пустой список при сбое."""
    if os.name == "nt":
        command = (
            "Get-CimInstance -ClassName Win32_Process -ErrorAction Stop | ForEach-Object { "
            "'{0}{1}{2}' -f $_.ProcessId, [char]31, $_.CommandLine }"
        )
        argv = ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command]
    else:
        argv = ["ps", "-Ao", "pid=,command="]
    try:
        result = subprocess.run(argv, capture_output=True, text=True,
                                timeout=_query_timeout(10), check=False)
        if result.returncode != 0:
            return []
        output = result.stdout
    except (OSError, subprocess.SubprocessError):
        return []
    processes = []
    for line in output.splitlines():
        stripped = line.strip()
        pid_text, separator, command = stripped.partition(PROCESS_DELIMITER)
        if not separator:
            pid_text, separator, command = stripped.partition(" ")
        if separator and pid_text.isdigit():
            processes.append((int(pid_text), command.strip()))
    return processes


def is_ours(cmd, directory=None):
    """Наш ли это процесс. Узкая проверка намеренно: широкая уже убивала чужое.

    ``directory`` — каталог прогона; по умолчанию тот, где лежит этот скрипт."""
    if not re.search(r"(?:^|\s)-m\s+http\.server(?:\s|$)", cmd):
        return False
    match = re.search(
        r"(?:^|\s)--directory(?:=|\s+)(?:\"([^\"]*)\"|'([^']*)'|(\S+))",
        cmd,
    )
    if not match:
        return False
    served = next(value for value in match.groups() if value is not None)
    return os.path.normcase(os.path.normpath(served)) == os.path.normcase(os.path.normpath(directory or A))


def recorded(pidfile=None):
    try:
        with open(pidfile or PIDF, encoding="utf-8") as handle:
            port, pid = handle.read().split()
        return int(port), int(pid)
    except (OSError, ValueError):
        return None, None


def free_port(prefer):
    """Прежний порт, если свободен, иначе любой. Стабильный адрес важнее случайного."""
    for p in ([prefer] if prefer else []) + [0]:
        s = socket.socket()
        try:
            s.bind(("127.0.0.1", p))
            return s.getsockname()[1]
        except OSError:
            continue
        finally:
            s.close()
    return None


def serve(state):
    if state.get("finishedAt"):
        return "прогон закрыт — сервер не поднимаю"     # Phase 8 его уже убила
    if os.environ.get("SSH_CONNECTION") or os.environ.get("CI"):
        return "удалённая сессия — без сервера"

    port, pid = recorded()
    if port and pid:
        responding = http_ok(port)
        command = cmdline(pid)
        if is_ours(command):
            if responding:
                return "сервер жив: http://localhost:%d/dashboard.html" % port
            return ("записанный процесс найден, но HTTP не ответил — "
                    "PID сохранён, новый сервер не запущен; "
                    "дашборд открывается файлом: %s" % PAGE)
        if not command and process_status(pid) != "absent":
            return ("принадлежность записанного процесса не подтверждена — "
                    "PID сохранён, новый сервер не запущен; "
                    "дашборд открывается файлом: %s" % PAGE)

    # Процесс, которого нет в PIDF, не наш: одного совпадения --directory
    # недостаточно для безопасного завершения. Занятый прежний порт пропускаем.
    port = free_port(port)
    if not port:
        return "порт не нашёлся — дашборд открывается файлом: %s" % PAGE
    detached = {"start_new_session": True}
    if os.name == "nt":
        detached = {
            "creationflags": (
                getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
                | getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
            )
        }
    log = None
    try:
        log = open(LOG, "a", encoding="utf-8")
        srv = subprocess.Popen([sys.executable, "-m", "http.server", str(port),
                                "--bind", "127.0.0.1", "--directory", A],
                               stdout=subprocess.DEVNULL, stderr=log,
                               **detached)       # переживает конец сессии агента
    except OSError as e:
        return "сервер не запустился (%s) — дашборд открывается файлом: %s" % (e, PAGE)
    finally:
        if log is not None:
            log.close()
    for _ in range(10):
        if http_ok(port):
            with open(PIDF, "w", encoding="utf-8") as pid_file:
                pid_file.write("%d %d\n" % (port, srv.pid))
            return "сервер поднят: http://localhost:%d/dashboard.html" % port
        try:
            srv.wait(timeout=0.5)
            break
        except subprocess.TimeoutExpired:
            continue
    srv.terminate()
    return "сервер не ответил — дашборд открывается файлом: %s" % PAGE


def parse_time(text):
    """ISO 8601 со смещением или `Z` -> aware datetime; None, если не разбирается или без часового пояса.

    Шаблон state.js всегда пишет смещение. Время без пояса не угадываем: местное оно или UTC,
    неизвестно, а от этого зависит, моложе ли оно пяти минут."""
    if not isinstance(text, str):
        return None
    try:
        moment = datetime.fromisoformat(text.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return moment if moment.tzinfo is not None else None


def launched_for(command, directory):
    """Запущен ли сервер этим скриптом для каталога: `--directory <каталог>` стоит в строке последним.

    `ps` не сохраняет кавычки, поэтому каталог с пробелом is_ours() режет по первому пробелу и
    не узнаёт собственный сервер. Здесь сверка идёт с концом строки: префикс чужого каталога
    (`/x/a b` при искомом `/x/a`) не совпадёт."""
    if not re.search(r"(?:^|\s)-m\s+http\.server(?:\s|$)", command):
        return False
    line = os.path.normcase(command.rstrip())
    tail = os.path.normcase("--directory " + directory)
    return line.endswith(tail) and (len(line) == len(tail) or line[-len(tail) - 1].isspace())


def server_serving(directory):
    """Отвечает ли за этот каталог живой сервер дашборда: True, False или None (не удалось определить).

    Тот же принцип, что в serve(): записанный в serve.pid процесс считается нашим только по
    `--directory`; неизвестное состояние не выдаётся ни за «жив», ни за «нет»."""
    port, pid = recorded(os.path.join(directory, "serve.pid"))
    if not (port and pid):
        return False
    command = cmdline(pid)
    if command:
        if not (is_ours(command, directory) or launched_for(command, directory)):
            return False                     # PID достался другому процессу
        return True if http_ok(port) else None
    return False if process_status(pid) == "absent" else None


def other_window(state, now, serving):
    """Идёт ли прогон в другом окне. Четвёртый случай phases/0-preflight.md.

    Нужны обе метки сразу: `updatedAt` моложе пяти минут и живой сервер на этом каталоге. Одна без
    другой — обычное прерывание, то есть возобновление. ``serving`` — результат server_serving().
    Возвращает (вердикт, пояснение); вердикт: "other-window", "resume" или "unknown".
    `finishedAt` не учитывается: инструкция называет две метки, и он не одна из них.
    """
    moment = parse_time((state or {}).get("updatedAt"))
    recent = None if moment is None else (now - moment).total_seconds() < OTHER_WINDOW_SECONDS
    if recent is False:
        return "resume", "state.js старше пяти минут"
    if serving is False:
        return "resume", "сервера на этом каталоге нет"
    if recent and serving:
        return "other-window", "state.js моложе пяти минут и сервер отвечает"
    unknown = []
    if recent is None:
        unknown.append("не прочитана метка updatedAt")
    if serving is None:
        unknown.append("не подтверждено, жив ли сервер")
    return "unknown", "; ".join(unknown)


AGING_COMPONENTS = ("sync.py", "dashboard.html")


def _normalized(name, data):
    """Содержимое копии для сравнения: без различий в переводах строк и без снимка состояния в странице.

    Снимок в dashboard.html между маркерами у каждого прогона свой и меняется при каждой синхронизации,
    возрастом копии он не считается."""
    data = data.replace(b"\r\n", b"\n")
    if name == "dashboard.html":
        begin, end = BEGIN.encode(), END.encode()
        i, j = data.find(begin), data.find(end)
        if 0 <= i < j:
            data = data[: i + len(begin)] + data[j:]
    return data


def fingerprint(name, path):
    """Отпечаток файла для сравнения или None, если файла нет."""
    try:
        with open(path, "rb") as handle:
            return hashlib.sha256(_normalized(name, handle.read())).hexdigest()
    except OSError:
        return None


def aging_report(run_dir, sources):
    """Возраст копий навыка в прогоне. Возвращает (строки, индекс старения).

    Строка — (имя, состояние, отпечаток копии, отпечаток источника); состояние: "current", "senescent"
    (копия отличается от установленного навыка) или "missing" (копии нет). Индекс — доля копий, которые
    не "current": 0 — все свежие, 1 — все устарели.
    """
    rows = []
    for name in AGING_COMPONENTS:
        want = fingerprint(name, sources[name])
        have = fingerprint(name, os.path.join(run_dir, name))
        state = "missing" if have is None else "current" if have == want else "senescent"
        rows.append((name, state, have, want))
    aged = sum(1 for row in rows if row[1] != "current")
    return rows, aged / len(rows)


def skill_sources():
    """Файлы установленного навыка, с которыми сверяются копии; None, если запущено не из каталога навыка."""
    here = os.path.dirname(os.path.abspath(__file__))
    template = os.path.join(here, "..", "phases", "dashboard-template.html")
    if not os.path.isfile(template):
        return None
    return {"sync.py": os.path.abspath(__file__), "dashboard.html": os.path.normpath(template)}


def check_aging(run_dir):
    """Режим --aging: ничего не пишет. Возвращает код выхода."""
    sources = skill_sources()
    if sources is None:
        print("aging · запущено не из каталога навыка: источника для сверки нет")
        return 3
    if not os.path.isdir(run_dir):
        print("aging · индекс 0.00 · каталога прогона нет")
        return 0
    rows, index = aging_report(run_dir, sources)
    aged = [row for row in rows if row[1] != "current"]
    print("aging · индекс %.2f · устарело %d из %d" % (index, len(aged), len(rows)))
    for name, state, have, want in aged:
        print("  · %s: %s (копия %s, в навыке %s)" % (name, state, (have or "нет")[:8], (want or "нет")[:8]))
    return 1 if aged else 0


def closure_findings(state):
    """Что в записи противоречит тому, закрыт прогон или нет. Пусто — запись согласована сама с собой.

    Закрытый прогон (finishedAt) по фазе 8 тих: ни активного этапа, ни таска в работе. Открытый прогон лежит в
    каталоге с --wip; закрытый его теряет, а «доделай» возвращает при возобновлении. Расхождение значит, что закрытое
    снова пишется без заявленного возобновления: так воскресает то, что закрыли."""
    out = []
    if state.get("finishedAt"):
        live = [str(s.get("id")) for s in (state.get("stages") or []) if s.get("status") == "active"]
        busy = [str(item.get("id")) for item in (state.get("tickets") or []) if item.get("status") in LIVE_TICKET_STATUSES]
        if live:
            out.append("прогон закрыт (finishedAt), а этап %s снова active: закрытый прогон пишется молча" % ", ".join(live))
        if busy:
            out.append("прогон закрыт (finishedAt), а таск %s снова в работе: закрытый прогон пишется молча" % ", ".join(busy))
    else:
        directory = state.get("dir")
        if isinstance(directory, str) and directory and not directory.endswith("--wip"):
            out.append("finishedAt пуст, а каталог %s без --wip: закрытый прогон открыт заново без переименования" % directory)
    return out


def run_status(state, now):
    """Можно ли возобновлять прогон. Возвращает (вердикт, пояснение).

    Вердикт: "closed", "resurrected", "stale", "open" или "unknown". Закрытый не возобновляют; воскрешённому,
    давнему и нечитаемому нужно слово человека."""
    if not isinstance(state, dict):
        return "unknown", "state.js не разобран как запись прогона"
    problems = closure_findings(state)
    if problems:
        return "resurrected", problems[0]
    if state.get("finishedAt"):
        return "closed", "finishedAt стоит: прогон закрыт, возобновлять нельзя"
    moment = parse_time(state.get("updatedAt"))
    if moment is None:
        return "unknown", "не прочитана метка updatedAt"
    days = (now - moment).total_seconds() / 86400
    if days > RESUME_STALE_DAYS:
        return "stale", "последняя запись %d дн. назад (порог %d)" % (int(days), RESUME_STALE_DAYS)
    return "open", "прогон открыт, последняя запись %d дн. назад" % max(int(days), 0)


def check_run_status(directory):
    """Режим --run-status: ничего не пишет. Возвращает код выхода."""
    path = os.path.join(directory, "state.js")
    try:
        with open(path, encoding="utf-8") as handle:
            raw = handle.read()
    except FileNotFoundError:
        print("none · state.js нет: прогона здесь нет")
        return 0
    except OSError as e:
        print("unknown · state.js не прочитан (%s)" % (e.strerror or "ошибка"))
        return 3
    try:
        state = json.loads(_state_body(raw))
    except json.JSONDecodeError:
        print("unknown · state.js не разбирается")
        return 3
    verdict, why = run_status(state, datetime.now(timezone.utc))
    print("%s · %s" % (verdict, why))
    return {"open": 0, "closed": 1}.get(verdict, 3)


def check_other_window(directory):
    """Режим --other-window: ничего не пишет, сервер не трогает. Возвращает код выхода."""
    try:
        raw = open(os.path.join(directory, "state.js"), encoding="utf-8").read()
    except FileNotFoundError:
        print("resume · state.js нет — прогона здесь нет")
        return 0
    except OSError as e:
        print("unknown · state.js не прочитан (%s)" % (e.strerror or "ошибка"))
        return 3
    try:
        state = json.loads(_state_body(raw))
    except json.JSONDecodeError:
        print("unknown · state.js не разбирается")
        return 3
    verdict, why = other_window(state, datetime.now(timezone.utc), server_serving(directory))
    print("%s · %s" % (verdict, why))
    return {"resume": 0, "other-window": 1}.get(verdict, 3)


BRIEF_MARKER = re.compile(r"^## Дополнения[ \t]*$", re.MULTILINE)


def brief_original(text):
    """Текст брифа выше первого заголовка «## Дополнения» — тот, что не редактируется. Без заголовка — весь файл.

    Переводы строк и хвостовые пробелы не считаются изменением: их меняют редакторы и git."""
    text = text.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    found = BRIEF_MARKER.search(text)
    return (text[: found.start()] if found else text).rstrip()


def brief_digest(text):
    return hashlib.sha256(brief_original(text).encode("utf-8")).hexdigest()


def _plain_name(value):
    return isinstance(value, str) and value != "" and value not in (".", "..") and os.path.basename(value) == value \
        and "\\" not in value


def brief_seal_report(state, base):
    """Печати брифов прогона. Возвращает список (файл, статус, хеш файла или None).

    Статусы: "sealed" — хеш совпал; "changed" — текст выше «## Дополнения» не тот, что запечатан; "missing" —
    запечатанного файла нет; "unreadable" — не прочитан; "unsealed" — бриф из `briefFile` есть, печати нет;
    "pending" — `briefFile` назван (его пишет шаблон `state.js` в Phase 0), а файла ещё нет: бриф пишет фаза 1,
    это не находка; "badname" — запись печати указывает не на файл рядом, а на путь. Каталог брифов: `base/<dir>`."""
    seals = state.get("briefSeals")
    seals = seals if isinstance(seals, dict) else {}
    directory = state.get("dir")
    if not _plain_name(directory):
        return []
    names = list(seals)
    brief = state.get("briefFile")
    if isinstance(brief, str) and brief not in seals:
        names.append(brief)
    rows = []
    for name in names:
        if not _plain_name(name):
            rows.append((str(name), "badname", None))
            continue
        path = os.path.join(base, directory, name)
        try:
            with open(path, encoding="utf-8", errors="replace") as handle:
                digest = brief_digest(handle.read())
        except FileNotFoundError:
            rows.append((name, "missing" if name in seals else "pending", None))
            continue
        except OSError:
            rows.append((name, "unreadable", None))
            continue
        if name not in seals:
            rows.append((name, "unsealed", digest))
        else:
            rows.append((name, "sealed" if seals[name] == digest else "changed", digest))
    return rows


def seal_findings(state, base):
    """Что в печатях брифов требует слова человека. Пусто — все запечатанные брифы совпали.

    Не запечатанный бриф у закрытого прогона не находка: печатать там уже нечего."""
    out = []
    closed = bool(state.get("finishedAt"))
    for name, status, _digest in brief_seal_report(state, base):
        if status == "changed":
            out.append("бриф %s изменён выше «## Дополнения»: текст пользователя не редактируется" % name)
        elif status == "missing":
            out.append("запечатанного брифа %s нет на месте" % name)
        elif status == "unreadable":
            out.append("бриф %s не прочитан: сверить с печатью нечем" % name)
        elif status == "badname":
            out.append("печать брифа указывает не на файл рядом: %s" % name)
        elif status == "unsealed" and not closed:
            out.append("бриф %s не запечатан: sync.py --brief-seal печатает хеш для briefSeals" % name)
    return out


def check_brief_seal(directory):
    """Режим --brief-seal: ничего не пишет. Возвращает код выхода."""
    try:
        with open(os.path.join(directory, "state.js"), encoding="utf-8") as handle:
            raw = handle.read()
    except FileNotFoundError:
        print("none · state.js нет: прогона здесь нет")
        return 0
    except OSError as e:
        print("unknown · state.js не прочитан (%s)" % (e.strerror or "ошибка"))
        return 3
    try:
        state = json.loads(_state_body(raw))
    except json.JSONDecodeError:
        print("unknown · state.js не разбирается")
        return 3
    if not isinstance(state, dict):
        print("unknown · state.js не разобран как запись прогона")
        return 3
    rows = brief_seal_report(state, directory)
    if not rows:
        print("none · брифа в записи нет (нет dir или briefFile)")
        return 0
    worst = 0
    for name, status, digest in rows:
        if status == "sealed":
            print("sealed · %s · %s" % (name, digest[:12]))
        elif status == "pending":
            print("pending · %s · файла ещё нет: его запишет фаза 1" % name)
        elif status == "unsealed":
            worst = max(worst, 1)
            print("unsealed · %s · sha256 %s" % (name, digest))
        else:
            worst = 3
            print("%s · %s%s" % (status, name, (" · сейчас %s" % digest[:12]) if digest else ""))
    return worst


ZONE_ALWAYS_ALLOWED = (".autopilot",)
COMMIT_ID = re.compile(r"^[0-9a-fA-F]{4,64}$")


def _path_segments(path):
    return [part for part in str(path).replace("\\", "/").split("/") if part and part != "."]


def in_zone(path, zone):
    """Лежит ли путь внутри одной из зон (по сегментам: `src/bot` не содержит `src/bot2/x`). `.` — весь проект."""
    parts = _path_segments(path)
    if not parts or ".." in parts:
        return False
    for entry in zone:
        if str(entry).strip() in (".", "./"):
            return True
        zone_parts = _path_segments(entry)
        if zone_parts and parts[:len(zone_parts)] == zone_parts:
            return True
    return False


def ticket_zone(ticket):
    """Зона таска как список строк. None — зоны нет или она записана не так, проверять нечем."""
    zone = ticket.get("zone")
    if isinstance(zone, str):
        zone = [zone]
    if isinstance(zone, list) and zone and all(isinstance(entry, str) and entry.strip() for entry in zone):
        return zone
    return None


def files_outside(files, zone, allowed):
    return [name for name in files if not in_zone(name, allowed) and not in_zone(name, zone)]


def commit_files(root, commit):
    """Файлы коммита относительно корня проекта. Возвращает (список, None) или (None, причина). Только чтение."""
    try:
        prefix = subprocess.run(["git", "rev-parse", "--show-prefix"], cwd=root, capture_output=True, timeout=30)
        listing = subprocess.run(["git", "diff-tree", "--no-commit-id", "--name-only", "-r", "-z", "--root", commit],
                                 cwd=root, capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None, "git не ответил"
    if prefix.returncode != 0:
        return None, "каталог не в репозитории git"
    if listing.returncode != 0:
        return None, "коммита %s нет в git" % commit[:12]
    base = prefix.stdout.decode("utf-8", "replace").strip()
    names = [name for name in listing.stdout.decode("utf-8", "replace").split("\0") if name]
    if not base:
        return names, None
    return [name[len(base):] if name.startswith(base) else "../" + name for name in names], None


def zone_report(state, root, files_of=commit_files):
    """Файлы готовых тасков против их зон. Возвращает список (id, статус, подробности).

    Статусы: "inside" — все файлы коммита в зоне или в допустимом; "outside" — есть файлы вне зоны (подробности:
    список); "unchecked" — таск готов, но проверить нечем (подробности: причина). Таски не в `done` не берутся:
    коммит появляется только у готового."""
    allowed = list(ZONE_ALWAYS_ALLOWED)
    memory = state.get("memoryFile")
    if isinstance(memory, str) and memory and os.path.basename(memory) == memory:
        allowed.append(memory)
    rows = []
    tickets = state.get("tickets")
    for ticket in tickets if isinstance(tickets, list) else []:
        if not isinstance(ticket, dict) or ticket.get("status") != "done":
            continue
        name = str(ticket.get("id"))
        zone = ticket_zone(ticket)
        commit = ticket.get("commit")
        if zone is None:
            rows.append((name, "unchecked", "у таска нет зоны"))
        elif not isinstance(commit, str) or not COMMIT_ID.match(commit):
            rows.append((name, "unchecked", "у таска нет commit"))
        else:
            files, why = files_of(root, commit)
            if files is None:
                rows.append((name, "unchecked", why))
            else:
                outside = files_outside(files, zone, allowed)
                rows.append((name, "outside" if outside else "inside", outside))
    return rows


def unfinished_tickets(state):
    """Таски не в `done`, как «id (статус)»: проверка зон их не судит, и об этом надо сказать вслух."""
    tickets = state.get("tickets")
    return ["%s (%s)" % (t.get("id"), t.get("status")) for t in (tickets if isinstance(tickets, list) else [])
            if isinstance(t, dict) and t.get("status") != "done"]


def check_zone(directory):
    """Режим --zone-check: ничего не пишет. Возвращает код выхода."""
    try:
        with open(os.path.join(directory, "state.js"), encoding="utf-8") as handle:
            raw = handle.read()
    except FileNotFoundError:
        print("none · state.js нет: прогона здесь нет")
        return 0
    except OSError as e:
        print("unknown · state.js не прочитан (%s)" % (e.strerror or "ошибка"))
        return 3
    try:
        state = json.loads(_state_body(raw))
    except json.JSONDecodeError:
        print("unknown · state.js не разбирается")
        return 3
    if not isinstance(state, dict):
        print("unknown · state.js не разобран как запись прогона")
        return 3
    rows = zone_report(state, os.path.dirname(os.path.abspath(directory)))
    waiting = unfinished_tickets(state)
    later = ("ещё не готовы: " + ", ".join(waiting)) if waiting else ""
    if not rows:
        print("none · готовых тасков нет" + ((" · " + later) if later else ""))
        return 0
    outside = [row for row in rows if row[1] == "outside"]
    unchecked = [row for row in rows if row[1] == "unchecked"]
    print("zone · проверено %d из %d · вне зоны %d%s" % (len(rows) - len(unchecked), len(rows), len(outside),
                                                          (" · " + later) if later else ""))
    zones = {str(t.get("id")): ticket_zone(t) for t in state.get("tickets") or [] if isinstance(t, dict)}
    for name, _status, files in outside:
        print("  ! таск %s вне зоны %s: %s" % (name, " · ".join(zones.get(name) or []), ", ".join(files)))
    for name, _status, why in unchecked:
        print("  · таск %s не проверен: %s" % (name, why))
    return 1 if outside else (3 if unchecked else 0)


def commits_since(root, base):
    """Коммиты от `base` (не включая) до HEAD, новые первыми: [(полный хеш, число родителей)]. Только чтение.

    Возвращает (список, None) или (None, причина). Не предок HEAD или отсутствующий в git `base` — причина, а не
    пустой список: откат от неизвестной точки назвал бы чужие коммиты кругом."""
    try:
        known = subprocess.run(["git", "rev-parse", "--verify", "--quiet", base + "^{commit}"], cwd=root,
                               capture_output=True, timeout=30)
        if known.returncode != 0:
            return None, "baseCommit %s нет в git" % base[:12]
        stray = subprocess.run(["git", "rev-list", "-n", "1", base, "^HEAD"], cwd=root, capture_output=True,
                               timeout=30)
        walk = subprocess.run(["git", "rev-list", "--topo-order", "--parents", base + "..HEAD"], cwd=root,
                              capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None, "git не ответил"
    if stray.returncode != 0 or walk.returncode != 0:
        return None, "git не ответил"
    if stray.stdout.strip():
        return None, "baseCommit %s не лежит в истории текущей ветки" % base[:12]
    rows = []
    for line in walk.stdout.decode("utf-8", "replace").splitlines():
        names = line.split()
        if names:
            rows.append((names[0], len(names) - 1))
    return rows, None


def rollback_plan(state, root, history_of=commits_since):
    """План отката последнего круга доводки (REQ-CORE-10). Возвращает (статус, подробности).

    "none" — откатывать нечего (подробности: почему); "unplanned" — круг есть, а план по записи не построить
    (подробности: причина); "plan" — подробности: (номер круга, [(таск, полный хеш)] новыми первыми). Ничего не
    пишет: команда отката печатается, а не выполняется."""
    polish = state.get("polish")
    rounds = polish.get("rounds") if isinstance(polish, dict) else None
    if not isinstance(rounds, list) or not rounds or not isinstance(rounds[-1], dict):
        return "none", "кругов доводки нет"
    last = rounds[-1]
    number = last.get("n")
    names = last.get("tickets")
    if not isinstance(names, list) or not names:
        return "none", "в круге %s нет тасков" % number
    base = polish.get("baseCommit")
    if not isinstance(base, str) or not COMMIT_ID.match(base):
        return "unplanned", "у доводки нет baseCommit"
    tickets = {str(t.get("id")): t for t in state.get("tickets") or [] if isinstance(t, dict)}
    wanted = []
    for name in (str(n) for n in names):
        ticket = tickets.get(name)
        commit = ticket.get("commit") if ticket else None
        if ticket is None:
            return "unplanned", "таска %s нет в tickets" % name
        if not isinstance(commit, str) or not COMMIT_ID.match(commit):
            return "unplanned", "у таска %s нет commit" % name
        wanted.append((name, commit.lower()))
    history, why = history_of(root, base)
    if history is None:
        return "unplanned", why
    found = {}
    for name, commit in wanted:
        hits = [(sha, parents) for sha, parents in history if sha.startswith(commit)]
        if len(hits) != 1:
            return "unplanned", "коммита %s (таск %s) нет между baseCommit и HEAD" % (commit[:12], name)
        if hits[0][1] > 1:
            return "unplanned", "коммит %s (таск %s) — слияние: откат слияния не планируется" % (commit[:12], name)
        found[hits[0][0]] = name
    return "plan", (number, [(found[sha], sha) for sha, _parents in history if sha in found])


def check_rollback_plan(directory):
    """Режим --rollback-plan: ничего не пишет. Возвращает код выхода."""
    try:
        with open(os.path.join(directory, "state.js"), encoding="utf-8") as handle:
            raw = handle.read()
    except FileNotFoundError:
        print("none · state.js нет: прогона здесь нет")
        return 0
    except OSError as e:
        print("unknown · state.js не прочитан (%s)" % (e.strerror or "ошибка"))
        return 3
    try:
        state = json.loads(_state_body(raw))
    except json.JSONDecodeError:
        print("unknown · state.js не разбирается")
        return 3
    if not isinstance(state, dict):
        print("unknown · state.js не разобран как запись прогона")
        return 3
    status, detail = rollback_plan(state, os.path.dirname(os.path.abspath(directory)))
    if status == "none":
        print("none · откатывать нечего: %s" % detail)
        return 1
    if status == "unplanned":
        print("unplanned · план отката не построен: %s" % detail)
        return 3
    number, rows = detail
    print("rollback · круг %s · коммитов %d · git revert --no-edit %s" % (number, len(rows),
                                                                          " ".join(sha for _name, sha in rows)))
    for name, sha in rows:
        print("  · таск %s · %s" % (name, sha[:12]))
    return 0


ORDER = ["preflight", "manifest", "briefing", "spec", "plan", "build", "review", "final"]


def close_passed(state):
    """Закрывает этапы, которые прогон уже прошёл. Возвращает список закрытых.

    Инвариант, а не событие: раньше активного этапа не может быть другого
    активного. Поэтому агент только открывает следующий — предыдущий
    закрывается здесь, временем открытия нового, тем самым, что он и получил бы
    вручную. Половина ритуала перестала быть работой агента, а вместе с ней —
    класс ошибок, где переход записан наполовину (2026-08-19: spec простоял
    активным два с половиной часа рядом с готовым планом и идущей сборкой).

    Одно исключение, и оно в самой модели работы: ревью идёт по таскам внутри
    сборки, поэтому review не закрывает build. Всё, что позже review, закрывает
    обоих.

    Не трогает ничего, кроме active: skipped и failed — осознанные состояния,
    и превратить их в done значило бы стереть сказанное о прогоне.
    """
    rank = {v: i for i, v in enumerate(ORDER)}
    stages = state.get("stages") or []
    live = [s for s in stages if s.get("status") == "active" and s.get("id") in rank]
    if len(live) < 2:
        return []
    closed = []
    for s in live:
        # Что идёт следом. Ревью не считается «следующим» для сборки: оно живёт
        # внутри неё, поэтому не закрывает её и не даёт ей времени закрытия.
        later = [o for o in live if rank[o["id"]] > rank[s["id"]]
                 and not (s["id"] == "build" and o["id"] == "review")]
        if not later:
            continue
        # Закрываем моментом, когда прогон ушёл дальше, — открытием ближайшего
        # следующего этапа, а не самого дальнего: иначе спецификация получила бы
        # время начала ревью и час чужой работы в свой счёт.
        marks = sorted(o["startedAt"] for o in later if o.get("startedAt"))
        when = marks[0] if marks else state.get("updatedAt")
        if not when:
            continue
        s["status"] = "done"
        s["finishedAt"] = when
        closed.append("%s закрыт автоматически (%s)" % (s["id"], when[11:19]))
    return closed


def save(state):
    raw = open(STATE, encoding="utf-8").read()
    head = raw.split("=", 1)[0]
    tmp = STATE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(head + "=\n" + json.dumps(state, ensure_ascii=False, indent=2) + "\n")
    os.replace(tmp, STATE)


def audit(state):
    """Молчит, пока состояние сходится само с собой. Не чинит: называет.

    Ловит один класс ошибок — переход, записанный наполовину. Стадию оставили
    active и ушли дальше; таск запустили без startedAt; закрыли без finishedAt.
    Каждая такая живёт до тех пор, пока её не увидит человек: 2026-08-19 spec
    простоял активным два с половиной часа рядом с готовым планом и идущей
    сборкой, и заметил это пользователь, а не прогон.
    """
    out = []
    stages = state.get("stages") or []
    rank = {v: i for i, v in enumerate(ORDER)}
    live = [s["id"] for s in stages if s.get("status") == "active" and s.get("id") in rank]
    # Этап, до которого прогон дошёл, но который так и не отметили ни пройденным,
    # ни пропущенным: close_passed его не трогает — «пропущен» требует причины,
    # а её знает только агент. На экране он иначе читается как «сборка застряла».
    if live:
        edge = max(rank[i] for i in live)
        for s in stages:
            if s.get("status") == "pending" and rank.get(s.get("id"), 99) < edge:
                out.append("этап %s остался pending, а прогон ушёл дальше — пометь skipped с причиной" % s.get("id"))
    for s in stages:
        if s.get("status") == "done" and not s.get("finishedAt"):
            out.append("этап %s закрыт без finishedAt" % s.get("id"))
    for t in state.get("tickets") or []:
        if t.get("status") in ("in-progress", "review", "repair") and not t.get("startedAt"):
            out.append("таск %s в работе без startedAt" % t.get("id"))
        if t.get("status") == "done" and not t.get("finishedAt"):
            out.append("таск %s закрыт без finishedAt" % t.get("id"))
    out.extend(closure_findings(state))
    out.extend(audit_caps(state))
    out.extend(audit_dials(state))
    return out


def _over(value, ceiling):
    """Число выше потолка. Не число (нет поля, null, строка, bool) — не нарушение: audit молчит о том, чего не видит."""
    return isinstance(value, int) and not isinstance(value, bool) and value > ceiling


def _zones_overlap(a, b):
    """Зоны — списки путей-префиксов. Пересекаются, если один путь равен другому или лежит внутри него (по сегментам)."""
    def segs(path):
        return [part for part in str(path).replace("\\", "/").split("/") if part and part != "."]
    for x in a or []:
        for y in b or []:
            sx, sy = segs(x), segs(y)
            if sx and sy and (sx[:len(sy)] == sy or sy[:len(sx)] == sx):
                return True
    return False


def _ancestors(ticket_id, by_id):
    """Все таски, от которых ticket_id зависит прямо или через цепочку blockedBy."""
    seen, stack = set(), list(by_id.get(ticket_id, {}).get("blockedBy") or [])
    while stack:
        current = stack.pop()
        if current not in seen:
            seen.add(current)
            stack.extend(by_id.get(current, {}).get("blockedBy") or [])
    return seen


def audit_caps(state):
    """Потолки и зоны. Не переход, записанный наполовину, а прогон, вышедший за правило.

    Что проверяется и почему только это:
      - repairs / retries / handoffs не выше двух на таск, тасков плана не больше шестнадцати,
        раундов доводки не больше трёх: счётчики только растут, поэтому превышение — не гонка
        записей, а факт;
      - зоны тасков «в работе» не пересекаются, если один не зависит от другого.
    Чего здесь нет: «не больше трёх в полёте». Правило запуска (5-subagents.md) велит сначала
    запустить следующий таск и только потом обработать вернувшийся, так что у верного прогона
    в state.js на миг четыре in-progress; по записи это не отличить от нарушения.
    Что делать с найденным — в phases/5-repair.md: отрез был неверным, это в отчёт, не в новую попытку.
    """
    out = []
    tickets = [t for t in (state.get("tickets") or []) if isinstance(t, dict)]
    for name in COUNTERS:
        names = [str(t.get("id")) for t in tickets if _over(t.get(name), COUNTER_CEILING)]
        if names:
            out.append("таски %s: %s выше потолка %d — отрез был неверным, это в отчёт, а не в ещё одну попытку"
                       % (", ".join(names), name, COUNTER_CEILING))
    plan = [t for t in tickets if not str(t.get("id", "")).startswith("P")]
    if len(plan) > TICKET_CEILING:
        out.append("тасков плана %d, потолок %d — обоснуй строкой в spec.md или раздели работу на два прогона"
                   % (len(plan), TICKET_CEILING))
    polish = state.get("polish")
    rounds = polish.get("rounds") if isinstance(polish, dict) else None
    if isinstance(rounds, list) and len(rounds) > POLISH_ROUNDS_CEILING:
        out.append("раундов доводки %d, потолок %d — потолок не поднимают потому, что последний раунд был удачным"
                   % (len(rounds), POLISH_ROUNDS_CEILING))
    flying = [t for t in tickets if t.get("status") == "in-progress" and t.get("id") is not None]
    by_id = {t["id"]: t for t in tickets if t.get("id") is not None}
    clashes = []
    for i, first in enumerate(flying):
        for second in flying[i + 1:]:
            related = (first["id"] in _ancestors(second["id"], by_id)
                       or second["id"] in _ancestors(first["id"], by_id))
            if not related and _zones_overlap(first.get("zone"), second.get("zone")):
                clashes.append("%s и %s" % (first["id"], second["id"]))
    if clashes:
        out.append("таски в работе с пересекающимися зонами: %s — одни и те же файлы идут по очереди" % ", ".join(clashes))
    return out


def audit_dials(state):
    """Записанные «ручки» прогона — из допустимых значений. Не заданное поле молчит (старый state.js).

    mode и depth решаются один раз в начале (0-modes.md) и пишутся в state.js; tier ставит план;
    polish — null или объект доводки. Значение вне списка значит, что политику прогона по записи
    уже не восстановить. Что именно было задумано, знает только агент: audit называет, не правит.
    """
    out = []
    for key, allowed in DIAL_VALUES.items():
        if key not in state or state.get(key) is None:
            continue
        value = state[key]
        if not isinstance(value, str) or value not in allowed:
            out.append("%s %r не из допустимых (%s) — политику прогона по записи не восстановить"
                       % (key, value, ", ".join(allowed)))
    polish = state.get("polish")
    if polish is not None and not isinstance(polish, dict):
        out.append("polish %r: ожидался null или объект доводки" % (polish,))
    return out


def main():
    if "--zone-check" in sys.argv:
        rest = [a for a in sys.argv[1:] if a != "--zone-check"]
        if len(rest) > 1 or any(a.startswith("--") for a in rest):
            print("использование: sync.py --zone-check [КАТАЛОГ]")
            sys.exit(2)
        sys.exit(check_zone(os.path.abspath(rest[0]) if rest else A))
    if "--rollback-plan" in sys.argv:
        rest = [a for a in sys.argv[1:] if a != "--rollback-plan"]
        if len(rest) > 1 or any(a.startswith("--") for a in rest):
            print("использование: sync.py --rollback-plan [КАТАЛОГ]")
            sys.exit(2)
        sys.exit(check_rollback_plan(os.path.abspath(rest[0]) if rest else A))
    if "--brief-seal" in sys.argv:
        rest = [a for a in sys.argv[1:] if a != "--brief-seal"]
        if len(rest) > 1 or any(a.startswith("--") for a in rest):
            print("использование: sync.py --brief-seal [КАТАЛОГ]")
            sys.exit(2)
        sys.exit(check_brief_seal(os.path.abspath(rest[0]) if rest else A))
    if "--run-status" in sys.argv:
        rest = [a for a in sys.argv[1:] if a != "--run-status"]
        if len(rest) > 1 or any(a.startswith("--") for a in rest):
            print("использование: sync.py --run-status [КАТАЛОГ]")
            sys.exit(2)
        sys.exit(check_run_status(os.path.abspath(rest[0]) if rest else A))
    if "--aging" in sys.argv:
        rest = [a for a in sys.argv[1:] if a != "--aging"]
        if len(rest) > 1 or any(a.startswith("--") for a in rest):
            print("использование: sync.py --aging [КАТАЛОГ]")
            sys.exit(2)
        sys.exit(check_aging(os.path.abspath(rest[0]) if rest else A))
    if "--other-window" in sys.argv:
        rest = [a for a in sys.argv[1:] if a != "--other-window"]
        if len(rest) > 1 or any(a.startswith("--") for a in rest):
            print("использование: sync.py --other-window [КАТАЛОГ]")
            sys.exit(2)
        sys.exit(check_other_window(os.path.abspath(rest[0]) if rest else A))
    state = read_state()
    passed = close_passed(state)
    if passed:
        save(state)                    # updatedAt не двигаем: пульс принадлежит агенту
    snap = write_snapshot(state)
    srv = "сервер не проверялся" if "--no-serve" in sys.argv else serve(state)
    print("%s · %s · обновлено %s" % (snap, srv, (state.get("updatedAt") or "?")[11:19]))
    for line in passed:
        print("  · " + line)
    for line in (seal_findings(state, A) + audit(state))[:5]:
        print("  ! " + line)


if __name__ == "__main__":
    main()
