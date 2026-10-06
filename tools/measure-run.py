#!/usr/bin/env python3
"""Замер прогона Autopilot по логам сессии Claude Code.

Отвечает на три вопроса, ради которых он написан:
  · во что обошёлся прогон и кто именно потратил;
  · насколько выросли контексты — единственная величина, которой можно управлять;
  · соблюдаются ли правила, которые нельзя проверить чтением скилла.

Использование:
    python3 tools/measure-run.py <путь к каталогу проекта>
    python3 tools/measure-run.py ~/Documents/VScode/EDU/share

Каталог логов вычисляется из пути проекта так же, как это делает Claude Code:
слэши заменяются дефисами внутри ~/.claude/projects/.

Нормировка стоимости — относительно входного токена:
    output ×5 · cache_write ×1.25 · cache_read ×0.1
Это пропорции, а не деньги: они нужны, чтобы сравнивать прогоны между собой.
"""

import argparse
import json
import ntpath
import os
import posixpath
import re
import sys
import glob
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter

W_OUT, W_WRITE, W_READ = 5.0, 1.25, 0.1
IDLE_GAP_SEC = 300          # пауза длиннее — это простой, а не работа
CEILING_HINT = 120_000      # потолок из phases/5-subagents.md, для колонки «перебор»


def encode_project_path(path):
    """Encode an absolute project path using Claude's log-directory rule."""
    raw = os.path.expanduser(os.fspath(path))
    if not (ntpath.isabs(raw) or posixpath.isabs(raw)):
        raw = str(Path(raw).resolve())
    return re.sub(r"[:/\\]", "-", raw)


def logs_dir_for(project_path, root=None):
    root = Path(root) if root is not None else Path.home() / ".claude" / "projects"
    return root / encode_project_path(project_path)


def parse_ts(s):
    if not s:
        return None
    try:
        stamp = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        return stamp.astimezone(timezone.utc)
    except ValueError:
        return None


def load(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
                if isinstance(row, dict):
                    rows.append(row)
            except json.JSONDecodeError:
                pass
    return rows


# Виды шагов для разбивки расхода (--steps). Порядок = приоритет, если в одном сообщении несколько действий.
CATS = ("субагент", "правка state.js", "sync.py", "тесты/сборка", "git/gh", "правка кода",
        "правка тестов", "чтение (Read/Grep/Glob)", "другой Bash", "задачи (TaskCreate/Update)",
        "прочий инструмент", "ответ без действий")
TEST_WORDS = ("pytest", "npm test", "npm run test", "go test", "cargo test", "unittest", "vitest", "jest",
              "tsc", "npm run build", "npm run lint", "flake8", "ruff", "eslint", "mypy", "pnpm test", "yarn test")


def is_test_path(fp):
    """Путь к тесту: каталог tests/test, файл test_*.py или *.test.*; разделители Windows и POSIX равны."""
    norm = str(fp).replace("\\", "/")
    base = os.path.basename(norm)
    return "/tests/" in norm or "/test/" in norm or norm.startswith(("tests/", "test/")) \
        or base.startswith("test_") or ".test." in base


def classify(name, inp):
    """Вид одного действия модели. Только по имени инструмента и его входу, без чтения результата."""
    inp = inp or {}
    if name in ("Agent", "Task"):
        return "субагент"
    if name == "Bash":
        cmd = str(inp.get("command", ""))
        if "sync.py" in cmd:
            return "sync.py"
        if "state.js" in cmd:
            return "правка state.js"
        if any(k in cmd for k in TEST_WORDS):
            return "тесты/сборка"
        if cmd.lstrip().startswith(("git ", "gh ")) or " git " in cmd[:20]:
            return "git/gh"
        return "другой Bash"
    if name in ("Edit", "Write", "NotebookEdit"):
        fp = str(inp.get("file_path", ""))
        base = os.path.basename(fp.replace("\\", "/"))
        if base == "state.js":
            return "правка state.js"
        if is_test_path(fp):
            return "правка тестов"
        return "правка кода"
    if name in ("Read", "Grep", "Glob"):
        return "чтение (Read/Grep/Glob)"
    if name in ("TaskCreate", "TaskUpdate", "TaskList", "TaskGet", "TodoWrite"):
        return "задачи (TaskCreate/Update)"
    return "прочий инструмент"


def step_category(blocks):
    """Вид шага по приоритету CATS; шаг без tool_use — «ответ без действий»."""
    found = {classify(b.get("name"), b.get("input")) for b in blocks
             if isinstance(b, dict) and b.get("type") == "tool_use"}
    for cat in CATS:
        if cat in found:
            return cat
    return "ответ без действий"


SAMPLE_CATS = ("другой Bash", "прочий инструмент", "правка кода", "чтение (Read/Grep/Glob)")


def describe(blocks, cat):
    """Короткое описание действия, определившего вид шага: команда Bash, файл или имя инструмента."""
    for b in blocks:
        if not isinstance(b, dict) or b.get("type") != "tool_use":
            continue
        if classify(b.get("name"), b.get("input")) != cat:
            continue
        inp = b.get("input") or {}
        if b.get("name") == "Bash":
            return " ".join(str(inp.get("command", "")).split())[:90]
        target = inp.get("file_path") or inp.get("pattern") or inp.get("path") or ""
        return ("%s %s" % (b.get("name"), os.path.basename(str(target).replace("\\", "/")))).strip()[:90]
    return ""


def analyse(path, label):
    rows = load(path)
    ctx, tools = [], Counter()
    out = win = rin = cold = 0
    test_edits = code_edits = test_runs = 0
    stamps = []
    cats = {c: [0, 0.0] for c in CATS}
    samples = []   # (вид, описание, стоимость) для видов из SAMPLE_CATS

    # Claude Code пишет каждый блок одного ответа модели (размышление, текст, вызов инструмента)
    # отдельной строкой лога с одним и тем же message.id и одним и тем же usage. Считать каждую
    # строку значило бы считать один вызов несколько раз, поэтому строки склеиваются по id.
    # Если id нет, каждая строка — отдельный шаг (как было раньше).
    steps = {}
    for i, r in enumerate(rows):
        m = r.get("message") or {}
        ts = parse_ts(r.get("timestamp"))
        if ts:
            stamps.append(ts)
        if (m.get("role") or r.get("type")) != "assistant":
            continue
        st = steps.setdefault(m.get("id") or ("row", i), {"u": {}, "content": []})
        for k, v in (m.get("usage") or {}).items():
            if isinstance(v, (int, float)):
                st["u"][k] = max(st["u"].get(k, 0), v)
        st["content"].extend(c for c in (m.get("content") or []) if isinstance(c, dict))

    for st in steps.values():
        u = st["u"]
        if u:
            cr = u.get("cache_read_input_tokens", 0) or 0
            cw = u.get("cache_creation_input_tokens", 0) or 0
            ip = u.get("input_tokens", 0) or 0
            out += u.get("output_tokens", 0) or 0
            win += cw
            rin += cr
            if cw > 20_000:
                cold += 1
            if cr + cw + ip:
                ctx.append(cr + cw + ip)
                cat = step_category(st["content"])
                cost = (u.get("output_tokens", 0) or 0) * W_OUT + cw * W_WRITE + cr * W_READ
                cats[cat][0] += 1
                cats[cat][1] += cost
                if cat in SAMPLE_CATS:
                    samples.append((cat, describe(st["content"], cat), cost))
        for c in st["content"]:
            if c.get("type") != "tool_use":
                continue
            name, inp = c.get("name"), c.get("input", {})
            tools[name] += 1
            if name == "Bash":
                cmd = str(inp.get("command", ""))
                if any(k in cmd for k in ("pytest", "npm test", "go test", "cargo test", "unittest")):
                    test_runs += 1
            elif name in ("Edit", "Write", "NotebookEdit"):
                if is_test_path(inp.get("file_path", "")):
                    test_edits += 1
                else:
                    code_edits += 1

    stamps.sort()
    active = idle = 0
    for a, b in zip(stamps, stamps[1:]):
        gap = (b - a).total_seconds()
        if gap <= IDLE_GAP_SEC:
            active += gap
        else:
            idle += gap

    return {
        "label": label, "steps": len(ctx),
        "avg_ctx": sum(ctx) / len(ctx) if ctx else 0,
        "max_ctx": max(ctx) if ctx else 0,
        "over": sum(1 for c in ctx if c > CEILING_HINT),
        "out": out, "write": win, "read": rin, "cold": cold,
        "norm": out * W_OUT + win * W_WRITE + rin * W_READ,
        "active": active, "idle": idle,
        "test_edits": test_edits, "code_edits": code_edits, "test_runs": test_runs,
        "cats": cats, "samples": samples,
    }


def print_steps(results):
    """Куда уходят шаги: оркестратор отдельно, остальные контексты вместе."""
    orch = [r for r in results if r["label"] == "Оркестратор"]
    others = [r for r in results if r["label"] != "Оркестратор"]
    for title, group in (("Оркестратор", orch), ("Остальные контексты вместе", others)):
        agg = {c: [0, 0.0] for c in CATS}
        for r in group:
            for c, (n, cost) in r["cats"].items():
                agg[c][0] += n
                agg[c][1] += cost
        steps = sum(v[0] for v in agg.values())
        cost = sum(v[1] for v in agg.values())
        if not steps:
            continue
        print(f"\n{title}: разбивка шагов по видам (шаг = одно сообщение модели)")
        print(f"{'вид шага':<32}{'шагов':>7}{'доля шагов':>12}{'норм.ед':>10}{'доля':>7}")
        print("-" * 68)
        for c, (n, cst) in sorted(agg.items(), key=lambda kv: -kv[1][1]):
            if n:
                print(f"{c:<32}{n:>7}{n/steps*100:>11.0f}%{cst/1e6:>9.2f}M{cst/cost*100:>6.0f}%")
        print("-" * 68)
        rows = Counter()
        counts = Counter()
        for r in group:
            for cat, desc, cst in r.get("samples", []):
                rows[(cat, desc)] += cst
                counts[(cat, desc)] += 1
        if rows:
            print(f"  самые дорогие действия ({title.lower()}):")
            for (cat, desc), cst in rows.most_common(12):
                print(f"    {cst/1e6:>5.2f}M ×{counts[(cat, desc)]:<3} [{cat}] {desc}")


def _check_only():
    checks = {
        "/Users/alice/project": "-Users-alice-project",
        r"C:\Users\Alice\project": "C--Users-Alice-project",
    }
    if any(encode_project_path(path) != expected
           for path, expected in checks.items()):
        return 1
    print("measure-run check-only: OK")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--steps", action="store_true",
                        help="добавить разбивку шагов по видам действий (state.js, тесты, чтение и т. д.)")
    parser.add_argument("project", nargs="?")
    parser.add_argument("session_id", nargs="?")
    args = parser.parse_args(argv)

    if args.check_only:
        return _check_only()
    if not args.project:
        parser.print_usage(sys.stderr)
        return 2

    d = logs_dir_for(args.project)
    if not os.path.isdir(d):
        print(f"нет логов: {d}", file=sys.stderr)
        return 1

    sessions = sorted(glob.glob(os.path.join(d, "*.jsonl")))
    if not sessions:
        print(f"в {d} нет .jsonl", file=sys.stderr)
        return 1

    def weight(p):
        """Прогон Autopilot узнаётся по субагентам, а не по свежести:
        последняя по времени сессия — обычно та, в которой смотрят результат."""
        n = len(glob.glob(os.path.join(p[:-6], "subagents", "*.jsonl")))
        return (n, os.path.getsize(p))

    if args.session_id:                         # явный выбор: id сессии
        picked = ([p for p in sessions if os.path.basename(p)[:-6] == args.session_id]
                  or [p for p in sessions if args.session_id in os.path.basename(p)])
        if not picked:
            print(f"сессия {args.session_id} не найдена в {d}", file=sys.stderr)
            return 1
        if len(picked) > 1:
            print(f"id {args.session_id} подходит к {len(picked)} сессиям, уточни: "
                  + ", ".join(os.path.basename(p)[:-6] for p in picked[:5]), file=sys.stderr)
            return 1
        main_log = picked[0]
    else:
        main_log = max(sessions, key=weight)

    if len(sessions) > 1:
        print(f"\nСессий в каталоге: {len(sessions)}. Взята {os.path.basename(main_log)[:8]}"
              f" ({len(glob.glob(os.path.join(main_log[:-6], 'subagents', '*.jsonl')))} субагентов)."
              f"\nДругую — вторым аргументом: measure-run.py <проект> <id сессии>")
    sub_dir = main_log[:-6]

    metas = {}
    for mf in glob.glob(os.path.join(sub_dir, "subagents", "*.meta.json")):
        try:
            with open(mf, encoding="utf-8") as f:
                meta = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue                                 # описание субагента — подпись, без неё считаем по имени файла
        if isinstance(meta, dict):
            metas[os.path.basename(mf)[:-10]] = meta

    results = [analyse(main_log, "Оркестратор")]
    for jf in sorted(glob.glob(os.path.join(sub_dir, "subagents", "*.jsonl"))):
        key = os.path.basename(jf)[:-6]
        results.append(analyse(jf, metas.get(key, {}).get("description", key)))
    results.sort(key=lambda r: -r["norm"])

    total = sum(r["norm"] for r in results) or 1
    print(f"\nПрогон: {args.project}   контекстов: {len(results)}\n")
    print(f"{'контекст':<38}{'шагов':>7}{'ср.ctx':>9}{'макс':>9}{'>120K':>7}{'норм.ед':>11}{'доля':>7}")
    print("-" * 88)
    for r in results:
        print(f"{r['label'][:37]:<38}{r['steps']:>7}{r['avg_ctx']/1000:>8.0f}K"
              f"{r['max_ctx']/1000:>8.0f}K{r['over']:>7}{r['norm']/1e6:>10.2f}M"
              f"{r['norm']/total*100:>6.1f}%")
    print("-" * 88)

    o = sum(r["out"] for r in results)
    w = sum(r["write"] for r in results)
    rd = sum(r["read"] for r in results)
    steps = sum(r["steps"] for r in results)
    print(f"{'ИТОГО':<38}{steps:>7}{'':>9}{'':>9}{'':>7}{total/1e6:>10.2f}M\n")

    print("Структура расхода")
    for name, val in (("чтение кэша", rd * W_READ), ("запись кэша", w * W_WRITE), ("генерация", o * W_OUT)):
        bar = "█" * round(val / total * 46)
        print(f"  {name:<14}{val/total*100:>5.1f}%  {bar}")
    print(f"\n  прочитано на каждый написанный токен: {(rd + w) / o:.0f}:1" if o else "")

    print("\nСоблюдение правил")
    hot = [r for r in results if r["avg_ctx"] > CEILING_HINT * 1.5]
    print(f"  контекстов выше полуторного потолка: {len(hot)}"
          + (f" — {', '.join(r['label'][:24] for r in hot[:4])}" if hot else " — нет"))
    te = sum(r["test_edits"] for r in results)
    ce = sum(r["code_edits"] for r in results)
    print(f"  правки тестов к правкам кода: {te}/{ce}"
          + (f" ({te/(te+ce)*100:.0f}%)" if te + ce else ""))
    print(f"  прогонов тестов: {sum(r['test_runs'] for r in results)}")
    cold_agents = [r for r in results if r["read"] and r["write"] / r["read"] > 0.10]
    print(f"  контекстов с протухшим кэшем (запись/чтение > 10%): {len(cold_agents)}"
          + (f" — {', '.join(r['label'][:24] for r in cold_agents[:4])}" if cold_agents else " — нет"))

    act = sum(r["active"] for r in results)
    idl = sum(r["idle"] for r in results)
    print(f"\nВремя по всем контекстам: активно {act/60:.0f} мин · простой {idl/60:.0f} мин"
          f" ({act/(act+idl)*100:.0f}% активного)" if act + idl else "")
    if args.steps:
        print_steps(results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
