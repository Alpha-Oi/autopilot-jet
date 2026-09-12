<!-- autopilot:start -->
# Skills / Autopilot

Набор агентных навыков. Текущий прогон укрепляет переносимость Python-инструментов и runtime HTML-дашборда Autopilot.

## Текущее состояние

- Ветка: `development`
- Прогон: `.autopilot/2026-09-10-autopilot-pathing-hardening--wip/`
- Этап: pre-release; локальная часть таска 04 готова, внешняя публикация ожидает оркестратор
- База upstream: `99c7e73678195cac08080bdd442f0e49a7ccb640`
- История: `development` на 3 commit впереди базы; `main` и `upstream/main` остаются на базе
- Последний commit прогона: `dc70117` — быстрый и переносимый dashboard runtime; локальные изменения таска 04 ещё не закоммичены
- Dashboard: не 100%; `build`/`review` активны, `final` ожидает blind acceptance и внешний release gate

## Реализовано

- `tools/measure-run.py` переносимо нормализует Windows/POSIX paths и поддерживает `--check-only`.
- `skills/autopilot/tools/sync.py` и рабочая `.autopilot/sync.py` используют переносимый process adapter и безопасный lifecycle loopback-сервера.
- `skills/autopilot/phases/dashboard-template.html` и рабочая `.autopilot/dashboard.html` используют единый соседний `state.js`, snapshot fallback и кэшированный `tick()`.

## Проверка текущего checkout

- `python -B -m unittest discover -s tests -v` → 20 passed; dashboard benchmark `537.59ms <= 795.02ms`, DOM queries `0/3000`.
- `python -B tools/measure-run.py --check-only` → `measure-run check-only: OK`.
- `py_compile` для обоих `sync.py` → OK.
- System Chrome headless → `file:` и краткоживущий `http://127.0.0.1` загрузили соседний `state.js`, отрисовали snapshot/state без JS console/runtime/load errors; свой server PID остановлен.
- `flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics` → `NOT_RUN`: модуль `flake8` не установлен, зависимости не добавлялись.

## До релиза

- Оркестратору остаются independent blind acceptance, read-only GitHub checks, Public `Alpha-Oi/skills`, точный `origin`, публикация `development`, зелёный Actions, PR/merge в `main` и post-merge verification.
- Только после этих подтверждений закрываются run directory/status и dashboard получает 100%.

## Как здесь работает Autopilot

Сборка ведётся навыком `/autopilot`. Требования, спецификация, доказательства и таски — в `.autopilot/`.
Прогресс — `.autopilot/dashboard.html`. Требование из `manifest.md` может снять только пользователь.

Если работа продолжается — скажи «продолжи автопилот»: состояние поднимется
из `.autopilot/state.js`, переспрашивать ничего не нужно.
<!-- autopilot:end -->
