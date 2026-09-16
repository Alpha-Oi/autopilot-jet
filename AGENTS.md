<!-- autopilot:start -->
# Skills / Autopilot

Репозиторий исходников Autopilot: агентный skill проводит пользовательский бриф через требования, спецификацию, разработку, ревью и слепую приёмку, сохраняя трассировку и наблюдаемое состояние прогона.

## Назначение и устройство

- Канонический пакет находится в `skills/autopilot/`; `.agents/skills/autopilot` ссылается на него, а `.claude/skills/autopilot` — на `.agents/skills/autopilot`.
- `skills/autopilot/SKILL.md` — оркестратор режимов, глубины, фаз и gates G1–G4; файлы из `skills/autopilot/phases/` читаются целиком только в момент соответствующей фазы.
- Поток прогона: brief → numbered manifest → briefing → spec → plan/tickets → subagents → per-ticket review → blind acceptance; требование может снять только пользователь.
- `skills/autopilot/prompts/` содержит контракты исполнителя и craft-reviewer, передаваемые субагентам как пути, а не загружаемые оркестратором заранее.
- `.autopilot/` хранит историю и runtime конкретного прогона; это не канонический источник skill-кода и не заменяет текущую память проекта.
- Runtime не имеет production npm dependencies: dashboard — один dependency-free HTML/JavaScript-файл, вспомогательные инструменты написаны на Python standard library.

## Команды локальной проверки

| Команда | Что проверяет |
|---|---|
| `python -B -m unittest discover -s tests -v` | Все unit/runtime tests; `test_dashboard.py` дополнительно вызывает `node` |
| `python -B -m unittest discover -s tests -p 'test_sync.py' -v` | Один test-файл через устойчивый для Windows/POSIX discovery pattern |
| `python -B tools/measure-run.py --check-only` | Встроенный smoke для Windows/POSIX path encoding |
| `& 'C:\Users\Crown-Aliy\Documents\Codex\2026-09-10\engineering-advanced-skills-plugin-engineering-advanced\verification-tools\flake8-7.3.0\Scripts\python.exe' -m flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics` | Проверенный локальный syntax/error lint всего репозитория; запускать в PowerShell из корня worktree |

- Подтверждено 2026-09-16: полный suite — 24 tests in 8.650s, `OK`; `test_sync.py` — 10 tests `OK`; `measure-run check-only: OK`. Последние команды и raw output сохранены в `.autopilot/2026-09-10-autopilot-pathing-hardening--wip/local-verification-result.json`.
- Локальный `flake8` всего репозитория — `PASS`: stdout `0`, exit `0`, точные CI args без `exclude` и ослабления selection. Изолированный venv вне Git worktree: flake8 7.3.0, mccabe 0.7.0, pycodestyle 2.14.0, pyflakes 3.4.0; CPython 3.14.3 Windows.
- В sandbox этот же `flake8` получил `WinError 5` в multiprocessing `Pipe`; точный rerun через `require_escalated` прошёл. Обычный `flake8` в `PATH` не установлен; основной Python, global config и production dependencies не менялись. `.github/workflows/verify.yml` самостоятельно устанавливает `flake8` в CI.
- В репозитории нет `package.json` и build-step; не добавляй фиктивные `npm install`/`npm run build` команды.

## Структура и ключевые entry points

```text
skills/autopilot/SKILL.md                       orchestrator и публичная точка входа skill
skills/autopilot/phases/                        пофазные правила и dashboard template
skills/autopilot/prompts/                       executor/reviewer prompt contracts
skills/autopilot/tools/sync.py                  snapshot, state audit и loopback server lifecycle
tools/measure-run.py                            CLI анализа Claude Code JSONL-прогонов
tests/test_{measure_run,sync,dashboard}.py       portable unit/runtime seams
.github/workflows/verify.yml                    Linux CI gate для push/PR
.agents/skills/autopilot                        symlink на канонический пакет
.claude/skills/autopilot                        symlink-chain для Claude Code
.autopilot/<run>/                               неизменяемая после завершения история прогона
```

## Архитектура и interface contracts

- `tools/measure-run.py`: `encode_project_path(path) -> str` одинаково кодирует абсолютные Windows/POSIX paths; `logs_dir_for(path, root=None) -> Path` находит Claude logs независимо от `cwd`.
- `analyse(path, label) -> dict` читает UTF-8 JSONL, пропускает повреждённые строки и агрегирует context, token, tool, test-edit и active/idle metrics; `main(argv=None) -> int` поддерживает `<project> [session-id]` и `--check-only`.
- `skills/autopilot/tools/sync.py`: `read_state()` разбирает `state.js`; при ошибке JSON прежний snapshot и server остаются нетронутыми.
- `write_snapshot(state)` заменяет только `/*STATE-BEGIN*/…/*STATE-END*/`, экранирует `</` внутри script и публикует страницу атомарно через соседний temporary file + `os.replace`.
- `cmdline(pid)` и `iter_processes()` используют `Get-CimInstance` на Windows и `ps` на POSIX, не запускают shell и возвращают безопасный пустой результат при недоступном process query.
- `serve(state)` слушает только `127.0.0.1`, не стартует для `finishedAt`, `SSH_CONNECTION` или `CI`, переиспользует лишь живой PID с точным `-m http.server --directory <run-dir>` и никогда не завершает чужой server.
- Windows server запускается detached и hidden через `CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW`; POSIX использует `start_new_session=True`.
- `close_passed(state)` закрывает ранее active stages временем старта ближайшего следующего; `review` не закрывает `build`, а `audit(state)` только сообщает неполные переходы и не угадывает исправления.
- Dashboard `stateURL() -> URL|null`: `file:` и `http:` читают соседний `state.js`, `data:` намеренно остаётся snapshot-only; poll добавляет cache-buster каждые 10 секунд.
- `applyState()` не вызывает `render()` при неизменившемся stamp; `tick()` обновляет clocks через закэшированные DOM references без повторных selector queries.
- Durable state seams: `state.tests = {passed, failed}`, `state.checks.flake8.status`, `state.resolved[] = {status, finding, evidence}`; закрытые findings не возвращаются в активные `concerns`.
- `.github/workflows/verify.yml` запускается на push/PR для `main`, `master`, `development`: Ubuntu, Python 3.11, Node 20, flake8, full unittest и `measure-run --check-only`; npm устанавливается только если появится `package.json`.

## Инварианты и соглашения

- Канонические правки dashboard/sync делай в `skills/autopilot/phases/dashboard-template.html` и `skills/autopilot/tools/sync.py`; копии внутри `.autopilot/` принадлежат конкретному прогону.
- `.autopilot/state.js` — machine-readable truth прогона; после его изменения запускается `.autopilot/sync.py`, а `.autopilot/dashboard.html` вручную не редактируется.
- Snapshot может быть равен `state.js` или старше него, но не является более новым источником; при доступном `state.js` dashboard предпочитает его.
- Stage IDs и порядок фиксированы: `preflight`, `manifest`, `briefing`, `spec`, `plan`, `build`, `review`, `final`; `skipped` и `failed` не превращаются автоматически в `done`.
- Один пользовательский прогон называется «сборка», единица работы — «таск», а пользовательские названия стадий должны совпадать с таблицей в `SKILL.md`.
- Секреты не запрашиваются, не печатаются и не записываются; `.env`/`.env.*` игнорируются, разрешён только шаблон `.env.example` без значений.
- Новые production dependencies и lockfile changes требуют отдельного решения; текущий runtime остаётся Python standard library + vanilla HTML/JavaScript.

## Ограничения и границы проверки

- Node VM tests доказывают URL/state/runtime contracts и отсутствие лишних DOM queries, но не заменяют smoke в реальном браузере.
- Подтверждено 2026-09-16 в HTTP-браузере: actual DOM 8 stages / 100 tickets / 94 live clocks, медиана 5 × 1000 `tick()` — 570.7 ms против upstream baseline 741.5 ms, selector queries 0 / 15000, console logs пусты. Harness `browser-benchmark.html` и raw result `browser-benchmark-result.json` находятся в `.autopilot/2026-09-10-autopilot-pathing-hardening--wip/`; это не подтверждение Ubuntu CI.
- `data:`-страница не может live-poll по дизайну и показывает только встроенный snapshot; `file:`/`http:` live behavior требует доступного соседнего `state.js`.
- Локальный `http.server` обслуживает весь run directory, включая внутренние артефакты, поэтому bind шире `127.0.0.1` запрещён.
- Зелёные local tests не доказывают GitHub Actions, remote refs, публикацию, PR/merge или post-merge behavior; каждое внешнее утверждение требует свежей live-проверки.
- `tools/measure-run.py` анализирует Claude Code layout `~/.claude/projects/`; это не универсальный reader логов других агентов.

## Git и release discipline

- Интеграционная ветка — `development`; кодовый checkpoint перед публикацией: `7571f27` (5 implementation/runtime commits поверх `upstream/main`); последующие локальные commits сохраняют память и доказательства приёмки. Текущий HEAD сверяй через Git; `upstream/main` и локальный `main` — `99c7e73678195cac08080bdd442f0e49a7ccb640`.
- `upstream` настроен на `https://github.com/nick-vels/skills.git`, `my-skills-fork` — на `https://github.com/Alpha-Oi/skills-Pill.git`; `origin` — точный `https://github.com/Alpha-Oi/skills.git`, другие remotes сохранены.
- Проверено 2026-09-16: прямой `gh api --method GET user --jq .login` с разрешённой сетью подтвердил `Alpha-Oi`; после прямого API 404 через `POST /user/repos` создан Public `Alpha-Oi/skills`, id `1372711955`, GET подтвердил admin/push true. Перед первой публикацией удалённые `development` и `main` отсутствуют. Actions, PR, merge и post-merge ещё не выполнены; финальная приёмка — `NO-GO`, состояние `pre-release`.
- Sandbox `gh auth status` сообщал token invalid, но это не было доказательством отсутствия действительной сессии: прямой approved-network API request работает. Не запускай OAuth повторно только по этому сообщению; сначала проверь GET /user. Credential helper задаётся через одноразовые git `-c`, без global config или извлечения токена.
- Локальная конфигурация remote или remote-tracking ref не является доказательством текущей публикации; перед fetch/push/PR сверяй live refs, авторизацию и точный target.
- Не изменяй и не переписывай `main` до финального acceptance/merge gate; commit, push, PR, merge и release выполняются только по явному разрешению и с отдельной проверкой Actions/post-merge.
- Перед любым release action заново проверь `git status --short --branch`, active branch, `git diff`, divergence от `upstream/main` и отсутствие secrets/generated artifacts.

## Как здесь работает Autopilot

Сборка ведётся навыком `/autopilot`. Требования, спецификация, доказательства и таски находятся в `.autopilot/`; прогресс показывает `.autopilot/dashboard.html`.

При продолжении сначала прочитай этот файл, затем `.autopilot/state.js`, `manifest.md`, `interfaces.md` и только файл текущей фазы; не перечитывай все phase-файлы заранее.
<!-- autopilot:end -->
