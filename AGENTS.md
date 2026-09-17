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

- Подтверждено 2026-09-16: последний root suite — 24 tests in 7.422s, `OK`; excerpt и проверки snapshot/parity/HTTP сохранены в `.autopilot/2026-09-10-autopilot-pathing-hardening--wip/premerge-release-verification.json`. Предыдущие root raw outputs — в local-verification-result.json; independent suite/check-only — в premerge-blind-acceptance.md; `test_sync.py` — 10 tests `OK`.
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
- Проверено 2026-09-16: прямой approved-network GET /user подтвердил Alpha-Oi; Public `Alpha-Oi/skills` создан через API (id `1372711955`, admin/push true). Первая публикация отправила только development с explicit lease, требующим отсутствия ref; remote development `247535a`, main отсутствует, GitHub автоматически выбрал default branch development.
- Ubuntu Actions run `35071567560` для development `247535a` завершён success; raw jobs/quality logs сохранены в `.autopilot/2026-09-10-autopilot-pathing-hardening--wip/github-actions-result.json`. Более новый live run `35094887597` для `6265e03` также success: flake8 0, 24 tests in 2.607s OK, measure check OK, Node VM 210.33ms ≤ 231.46ms, queries 0/15000.
- Независимая pre-merge приёмка завершена `NO_GO`: 31 выделенная строка брифа, 11 реализовано, 16 частично, 4 нет. Свежий Windows suite — 24 tests in 8.416s OK; HTTP UI, theme/lang/poll smoke PASS. Полный отчёт: `.autopilot/2026-09-10-autopilot-pathing-hardening--wip/premerge-blind-acceptance.md`.
- Буквальные Git identity/CI-template требования не выполнены, host model/reasoning и ряд исторических требований не доказаны; native macOS не проверен. R12/R14 возвращены из done в in-ticket. Реальный dashboard остаётся 79%, PR/merge и post-merge не выполнены.
- Удалённая main отсутствует. Create-ref main на source base отклонён проверкой разрешений до выполнения из-за `NO_GO`/100% gate; повторять через другой инструмент нельзя без явного решения пользователя. Текущие refs и отказ записаны в `premerge-release-verification.json` того же run directory. Полная цель остаётся незавершённой.
- Sandbox `gh auth status` сообщал token invalid, но это не было доказательством отсутствия действительной сессии: прямой approved-network API request работает. Не запускай OAuth повторно только по этому сообщению; сначала проверь GET /user. Credential helper задаётся через одноразовые git `-c`, без global config или извлечения токена.
- Локальная конфигурация remote или remote-tracking ref не является доказательством текущей публикации; перед fetch/push/PR сверяй live refs, авторизацию и точный target.
- Не изменяй и не переписывай `main` до финального acceptance/merge gate; commit, push, PR, merge и release выполняются только по явному разрешению и с отдельной проверкой Actions/post-merge.
- Перед любым release action заново проверь `git status --short --branch`, active branch, `git diff`, divergence от `upstream/main` и отсутствие secrets/generated artifacts.

## Как здесь работает Autopilot

Сборка ведётся навыком `/autopilot`. Требования, спецификация, доказательства и таски находятся в `.autopilot/`; прогресс показывает `.autopilot/dashboard.html`.

При продолжении сначала прочитай этот файл, затем `.autopilot/state.js`, `manifest.md`, `interfaces.md` и только файл текущей фазы; не перечитывай все phase-файлы заранее.

## Checkpoint 2026-09-16 — повторная проверка спецификации

- Ветка development / HEAD `6265e03`; source/tests/workflow и runtime helper не изменены. Root repeat: 24 tests in 7.059s OK, check-only OK, exact full-repo flake8 stdout0/exit0; `t06-intake-checkpoint.json` в текущем run directory.
- Анализ импортов и карта путей дополнены; независимый source-aware recheck COMPLETE для обоих artifacts, `phase3-artifact-recheck.md`. Это не G2/G4/GO.
- Fresh G2 failed6/half4: сохраняются подмены/пропуски обязательств. Contract amendment в spec остановлен governance hook до выполнения; не обходить запрет и не считать этот патч исполненным. `t06-spec-coverage.md` содержит точный checkpoint.
- D01/T06: recorded helper отвечает, command query может быть unavailable; два helper ports отдают один state. Недоступный query не равен dead. Executor завершил только read-only intake, edits не начаты, новый interface не реализован. Не завершать существующие серверы; до исправления snapshot refresh через существующий `--no-serve`.
- Actual logs contract: default home/log root cwd-independent при одном absolute project input; relative input разрешается относительно native cwd, absolute dot-segment normalization пока не реализована. Native macOS/any-OS acceptance остаётся unverified.
- Remote refs read-only: только development `6265e03`, main отсутствует, PR list пуст. Actions35094887597 completed/success; full goal и release не завершены. Project memory за пределами markers сохранена.

- 2026-09-16T16:10:02.2499333+03:00: persistent goal marked blocked, not complete. Полный objective сохранён; дальнейшее продолжение требует решения пользователя по original-contract deviations и разрешённой доработке spec. Owned dashboard session95212 остаётся live; не перезапущена/не завершена.

## Checkpoint 2026-09-17 — причина остановки установлена

- Read-only diagnosis: PreToolUse использует `$HOME/.codex/hooks/governance_hook.py`; после подстановки текущего profile это проверенный глобальный файл. SHA256 и source anchors записаны в `.autopilot/2026-09-10-autopilot-pathing-hardening--wip/governance-hook-diagnostic.json`.
- Статическое сопоставление существующей цитаты брифа подтвердило collision `-b`/`-B` в case-insensitive rule; handler проверяет patch data до различения tool kind. Это объяснение прежнего отказа, не live replay и не исправление. Hook/config вне workspace не изменялись, заблокированный spec patch не повторялся.
- Fresh GitHub GET: Public `Alpha-Oi/skills`, только development `6265e03`, Actions35094887597 completed/success, main отсутствует, open PR list пуст. Source/tests/workflow/helper diff от HEAD пуст; commit/push/release не выполнялись.
- Dashboard session95212 подтверждена live, state GET200; сервер не перезапущен. Snapshot refresh только `--no-serve` до устранения D01.
- Persistent goal снова blocked, не complete: прежний approval blocker повторяется после resume; полный objective сохранён. Нужны решение по CI/identity/остальным обязательствам и явное разрешение точечной коррекции глобального хука либо одобренного документального amendment. G2/D01/NO_GO не закрыты.
- Fresh verification: 24 tests in 7.253s OK, measure check-only OK, diff-check0; state/snapshot/served-state совпали, helper parity и неизменный hash global hook подтверждены. Это не устранение D01 и не G2/GO; результаты в governance-hook-diagnostic.json.
## Checkpoint 2026-09-17 — согласованный контракт восстановлен

- Пользователь отдельно разрешил точечный ремонт governance hook: 45/45 frozen safe decision tests и Python dispatcher simulations, без опасного исполнения. Backup/harness/report вне Git в verification-tools/governance-hook-repair-20260917-012107; это не full live Codex E2E. Global Git и hook configuration при ремонте не менялись.
- G01: «Продолжай, как предлагаешь» согласовало адаптированный CI и existing repo-local Alpha-Oi/noreply. Цитата и контекст добавлены в brief; остальные требования сохранены, R01 возвращён из неподтверждённого deferred в in-ticket. G02 — отдельно разрешённый ремонт хука.
- Goal active; development HEAD6265e03 сохранён. Contract amendment действительно применён: все roots/import inventory, session-backed clone, ранний CI/development timing, host model/effort и отдельный post-merge AGENTS.md на main. Independent revised G2 после исправления одного hook-contract missing прошёл missing0/half0/extra0; g2-agreed-contract-coverage.md. Это не execution/release GO.
- T06 и новый T07 native verification имеют disjoint edit zones в волне5. T04 теперь после обоих в волне6; прежний ID и история сохранены. Нужен G3 recheck до code dispatch, потом independent review/зелёный local gate/отдельный commit каждого шага и свежие native Actions.
- Dashboard обновлён только штатным --no-serve без restart/Popen. HTTP200/state+snapshot equality подтверждены; Codex display queued, visible render этого обновления не проверен. Последний suite 24 tests in8.293s OK, Node VM592.47ms ≤ baseline861.94ms, queries0/15000; check-onlyOK/diff-check0. dashboard-refresh-checkpoint.json — dated pre-replan result, не current native CI proof.
- Connected global skill copy не равна development и содержит старые unconditional ps/server cleanup; установка не обновлялась. Старый blind NO_GO, main/PR/merge/post-merge и непроверенные model/history/platform требования не закрыты.

- Current host metadata: GPT-5.6 Sol / effort max подтверждены latest turn_context; три начальных context были medium, поэтому весь прежний цикл не объявляется max. Sanitized host-model-verification.json в current run хранит источник/агрегат без prompts/credentials. G3 passed32/7, T06/T07 implementation started; snapshot/state HTTP200 equality confirmed, visible render NOT_RUN.

- T06 local acceptance: root full33/OK (T06+4, uncommitted T07+5; beforewave24), exact full-repo flake80 и measureOK; independent Manifest+Spec/Craft clean, baseline regression13 failing subtests/0errors. Recorded unknown PID не инициирует duplicate/rewrite; actual server cleanup не выполнялся. Native Actions и полный release pending; t06-local-verification.json.

- T07 local gate: root full33/OK in10.553s, exactlint0/measureOK; independent native5 Windows PASS и review clean. Workflow native matrix3 готова, но externalCI3.11/20 ещё NOT_RUN. Live repaired sync повторён3 раза: honest unknown-ownership warning, registry hash/PID unchanged, loopback200; это не доказательство ownership/полного process inventory. t07-local-verification.json/server-query-recheck.json.

<!-- autopilot:end -->
