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
"""

import json
import os
import re
import socket
import subprocess
import sys
import urllib.error
import urllib.request

A = os.path.dirname(os.path.abspath(__file__))          # .autopilot этого прогона
STATE = os.path.join(A, "state.js")
PAGE = os.path.join(A, "dashboard.html")
PIDF = os.path.join(A, "serve.pid")
LOG = os.path.join(A, "serve.log")
BEGIN, END = "/*STATE-BEGIN*/", "/*STATE-END*/"
PROCESS_DELIMITER = "\x1f"


def fail(msg):
    print(msg)
    sys.exit(1)


def read_state():
    try:
        raw = open(STATE, encoding="utf-8").read()
    except FileNotFoundError:
        fail("state.js ещё нет — снимок не вписан, сервер не тронут")
    body = raw.split("=", 1)[1] if "=" in raw.split("\n", 1)[0] else raw
    try:
        return json.loads(body.strip().rstrip(";"))
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


def cmdline(pid):
    if os.name == "nt":
        command = (
            "(Get-CimInstance -ClassName Win32_Process -Filter "
            "'ProcessId = %d').CommandLine" % int(pid)
        )
        argv = ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command]
    else:
        argv = ["ps", "-p", str(pid), "-o", "command="]
    try:
        return subprocess.run(argv, capture_output=True, text=True,
                              timeout=5, check=False).stdout.strip()
    except (OSError, subprocess.SubprocessError, ValueError, TypeError):
        return ""


def iter_processes():
    """Возвращает пары ``(pid, command line)`` или пустой список при сбое."""
    if os.name == "nt":
        command = (
            "Get-CimInstance -ClassName Win32_Process | ForEach-Object { "
            "'{0}{1}{2}' -f $_.ProcessId, [char]31, $_.CommandLine }"
        )
        argv = ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command]
    else:
        argv = ["ps", "-Ao", "pid=,command="]
    try:
        output = subprocess.run(argv, capture_output=True, text=True, timeout=10,
                                check=False).stdout
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


def is_ours(cmd):
    """Наш ли это процесс. Узкая проверка намеренно: широкая уже убивала чужое."""
    if not re.search(r"(?:^|\s)-m\s+http\.server(?:\s|$)", cmd):
        return False
    match = re.search(
        r"(?:^|\s)--directory(?:=|\s+)(?:\"([^\"]*)\"|'([^']*)'|(\S+))",
        cmd,
    )
    if not match:
        return False
    directory = next(value for value in match.groups() if value is not None)
    return os.path.normcase(os.path.normpath(directory)) == os.path.normcase(os.path.normpath(A))


def recorded():
    try:
        port, pid = open(PIDF, encoding="utf-8").read().split()
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
    if port and pid and http_ok(port) and is_ours(cmdline(pid)):
        return "сервер жив: http://localhost:%d/dashboard.html" % port

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
    return out


def main():
    state = read_state()
    passed = close_passed(state)
    if passed:
        save(state)                    # updatedAt не двигаем: пульс принадлежит агенту
    snap = write_snapshot(state)
    srv = "сервер не проверялся" if "--no-serve" in sys.argv else serve(state)
    print("%s · %s · обновлено %s" % (snap, srv, (state.get("updatedAt") or "?")[11:19]))
    for line in passed:
        print("  · " + line)
    for line in audit(state)[:5]:
        print("  ! " + line)


if __name__ == "__main__":
    main()
