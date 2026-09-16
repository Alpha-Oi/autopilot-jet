См. @AGENTS.md

<!-- autopilot:start -->
# Skills / Autopilot — текущее состояние

Канон памяти — @AGENTS.md; здесь компактное зеркало фактического состояния репозитория на 2026-09-16.

## Код и рабочие границы

- Канонический skill — `skills/autopilot/`; `.agents/skills/autopilot` ссылается на него, `.claude/skills/autopilot` — на `.agents/skills/autopilot`.
- Основные точки правок: `skills/autopilot/tools/sync.py`, `skills/autopilot/phases/dashboard-template.html`, `tools/measure-run.py`; runtime — Python standard library + dependency-free HTML/JavaScript, без `package.json` и build-step.
- `sync.py` атомарно обновляет snapshot через `os.replace`, слушает только `127.0.0.1`, переиспользует только собственный HTTP server; Windows detached process запускается hidden.
- Dashboard читает соседний `state.js` на `file:`/`http:`, `data:` остаётся snapshot-only; неизменившийся stamp не вызывает render, `tick()` использует закэшированные DOM references.
- `.autopilot/state.js` хранит состояние прогона; snapshot обновляется `.autopilot/sync.py`. `state.tests`, `state.checks.flake8.status` и `state.resolved[]` разделяют tests, lint и закрытые findings.

## Проверки

- `python -B -m unittest discover -s tests -v` — 24 tests in 8.650s, `OK`; `python -B tools/measure-run.py --check-only` — `OK`. Последние команды и raw output: `.autopilot/2026-09-10-autopilot-pathing-hardening--wip/local-verification-result.json`.
- Полный repo `flake8` с `--count --select=E9,F63,F7,F82 --show-source --statistics` — `PASS`, stdout `0`, exit `0`, без `exclude` или ослабления. Проверенная копируемая команда PowerShell и полный путь venv Python находятся в @AGENTS.md.
- flake8 7.3.0 запущен из отдельного venv вне Git worktree на CPython 3.14.3 Windows; `flake8` в обычном `PATH` отсутствует. Sandbox дал `WinError 5` в multiprocessing `Pipe`; точный `require_escalated` rerun прошёл. Основной Python, global config и production dependencies не менялись.
- HTTP-браузер — `PASS`: actual DOM 8 stages / 100 tickets / 94 clocks; медиана 5 × 1000 `tick()` — 570.7 ms ≤ upstream baseline 741.5 ms; selector queries 0 / 15000, console logs `[]`. Это не доказательство Ubuntu CI.

## Релиз

- Состояние — `pre-release`, финальная приёмка — `NO-GO`; `development` code checkpoint `7571f27`, локальный `main` и `upstream/main` — `99c7e73678195cac08080bdd442f0e49a7ccb640`.
- `upstream` — `https://github.com/nick-vels/skills.git`; `my-skills-fork` — `https://github.com/Alpha-Oi/skills-Pill.git`; `origin` отсутствует.
- API `Alpha-Oi/skills` — `404`, CLI token invalid, последняя device OAuth попытка — `expired_token` без пользовательской авторизации. Actions, PR, merge и post-merge не выполнены; локальные проверки не подтверждают публикацию.
- `main` до финального acceptance/merge gate не изменён; публикация, PR, merge и release остаются отдельной границей разрешения и live-проверки.
<!-- autopilot:end -->
