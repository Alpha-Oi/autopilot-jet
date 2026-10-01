<!-- autopilot:start -->
# Autopilot JET

Переносимый skill превращает пользовательский бриф в проверенный проект; runtime — Python standard library и dependency-free HTML/JavaScript dashboard.
Активный worktree — ветка `development` (локальная копия автора — отдельный worktree).
Целевой Public repository — `Alpha-Oi/autopilot-jet` (id `1372711955`, default branch `development`, origin `https://github.com/Alpha-Oi/autopilot-jet.git`); локальное имя папки не обязано совпадать с repository name.
Канон project memory — `AGENTS.md`; `CLAUDE.md` — компактное зеркало, не второй журнал прогона.

## Ключевые файлы

- `skills/autopilot-jet/SKILL.md` задаёт режимы, глубину и gates G1–G4; инструкции из `skills/autopilot-jet/phases/` читаются только для текущего этапа.
- `skills/autopilot-jet/prompts/executor.md` и `skills/autopilot-jet/prompts/craft-review.md` — контракты независимых исполнителя и reviewer.
- `skills/autopilot-jet/tools/sync.py` и `skills/autopilot-jet/phases/dashboard-template.html` — канонические helper и dashboard; продуктовые правки делаются здесь, не в runtime copies.
- `skills/autopilot-jet/tools/redact.py` — детерминированный фильтр секретов (формы из `phases/1-manifest.md`): `--check [--write] PATH`, `--stdin`; печатает имена переменных, не значения; покрыт `tests/test_redact.py`.
- `tools/measure-run.py` — CLI анализа Claude Code JSONL: project path → logs directory → выбранная session и subagents → сравнительные token/time metrics.
- `.agents/skills/autopilot-jet` → `skills/autopilot-jet/`; `.claude/skills/autopilot-jet` → `.agents/skills/autopilot-jet`; обе привязки — symlinks.
- `.autopilot/state.js`, `.autopilot/sync.py`, `.autopilot/dashboard.html`, `.autopilot/index.html` — состояние и runtime конкретного прогона, а не канонический исходник skill.
- `.github/workflows/verify.yml` — native Ubuntu/Windows/macOS matrix для push/PR на `main`, `master`, `development`: Python 3.11, Node 20, exact flake8, full unittest и measure check-only.
- `tests/test_measure_run.py`, `tests/test_sync.py`, `tests/test_sync_state.py`, `tests/test_redact.py`, `tests/test_dashboard.py`, `tests/test_native_runtime.py` покрывают path/JSONL/CLI, process ownership/HTTP seams, инварианты жизненного цикла `close_passed()`/`audit()`, фильтр секретов, Node VM render/performance и cold relocated/native subprocess behavior.
- `docs/adr/0006-preserve-server-registry-on-unknown-process-status.md` закрепляет durable decision: неопределённый статус процесса не разрешает потерю server registry или duplicate launch.

## Архитектура и контракты

- Поток dashboard: соседний `.autopilot/state.js` → `read_state()` → state transitions/audit → атомарный embedded snapshot → optional loopback server; browser стартует со snapshot и при доступном sibling state переходит на live polling.
- Helper разрешает файлы относительно собственного `__file__`, не `cwd`: прямой запуск канонического исходника не обновляет существующий dashboard, runtime copy должна лежать рядом с состоянием и страницей.
- `read_state()` принимает JSON или JS assignment; ошибочный JSON останавливает обновление до snapshot и server actions. `write_snapshot(state)` меняет только `/*STATE-BEGIN*/…/*STATE-END*/`, экранирует `</` и публикует через соседний temporary file + `os.replace`.
- `cmdline(pid) -> str` и `iter_processes() -> list[tuple[int, str]]` используют `powershell.exe`/CIM на Windows и `ps` на POSIX без shell; `process_status(pid) -> str` различает `present`, `absent`, `unknown`.
- `serve(state)` переиспользует только записанный owned PID с точным `-m http.server --directory` и отвечающим HTTP; owned PID без HTTP и unknown ownership сохраняются без duplicate launch и переписи registry.
- Чужой или незаписанный server не завершается даже при совпадающем directory; новый server слушает только `127.0.0.1`, Windows launch hidden/detached, POSIX — `start_new_session=True`.
- Stage IDs: `preflight`, `manifest`, `briefing`, `spec`, `plan`, `build`, `review`, `final`; `close_passed(state)` закрывает только прежние active временем следующего этапа, `review` не закрывает `build`, `audit(state)` только сообщает неполные переходы.
- Dashboard использует `stateURL()`, `applyState()`, `pollState()`, `render(lang)`, `tick()`: `data:` остаётся snapshot-only, `file:`/`http:` live-poll каждые 10 секунд; секундный clock работает через DOM cache.
- Render stamp — `updatedAt|finishedAt|tickets.length`: при изменении содержимого состояния двигать `updatedAt`, иначе изменение той же длины не вызывает render.
- Схема результата разделяет `tests={passed,failed}`, `checks.flake8.status`, закрытые `resolved[]={status,finding,evidence}` и активные `concerns`.
- `encode_project_path(path) -> str` кодирует colon/slashes; relative input сначала разрешается относительно native cwd. `logs_dir_for(project_path, root=None)` использует профиль Claude Code независимо от cwd для absolute input; `analyse(path,label)` пропускает повреждённые JSONL строки; `main(argv=None)` поддерживает optional session ID и `--check-only`.

## Соглашения кода и окружение

- Production runtime не требует install/build, package manager, обязательных API keys или third-party Python/npm dependencies; Node нужен для dashboard tests.
- Локальный проверенный toolchain — Python 3.14.3 и Node 25.8.0; CI фиксирует Python 3.11 и Node 20.
- `CI` и `SSH_CONNECTION` запрещают server query/launch; `finishedAt` также запрещает launch; `--no-serve` пропускает server path, но выполняет state transitions, audit и snapshot.
- flake8 7.3.0 живёт в изолированном verification environment вне worktree; production dependencies, lockfiles и global config без отдельного решения не менять.
- `measure-run` понимает layout Claude Code, не логи всех runners; weighted token units — не цены и не доказательство host model/reasoning.

## Тесты и рабочие команды

Все команды запускаются из активного worktree. Переданные результаты ниже уже актуальны; повторный полный прогон для обновления памяти не нужен.

```powershell
python -B -m unittest discover -s tests -v
python -B -m unittest discover -s tests -p test_measure_run.py -v
python -B tools/measure-run.py --check-only
python -m flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
```

Для существующего dashboard обновлять snapshot без вмешательства в lifecycle уже работающего localhost server:

```powershell
python -X utf8 -B .autopilot/sync.py --no-serve
```

## Подводные камни

- `WinError 5` на CIM или multiprocessing Pipe может быть sandbox limitation; пустой query не равен dead PID, lint selection/exclusions не ослаблять.
- Loopback server обслуживает весь runtime directory, включая внутренние артефакты; bind шире `127.0.0.1` запрещён.
- Node VM проверки не заменяют настоящий browser smoke; `file:`/`http:` polling не переносится на `data:` preview. Реальный Edge smoke остаётся отдельным release evidence.
- Прямой запуск `skills/autopilot-jet/tools/sync.py` работает рядом с каноническим source path и не обновляет уже созданный `.autopilot/dashboard.html`; для существующего прогона использовать runtime copy.

## Текущий проверенный срез

- Финальный release payload — `c23de4263454dae03faa5341bceb7d5d24360230` в `development`; PR #1 смержен в `main` merge commit `ca6743bb0b2453c79325fe30f6b9680b911ef4ed`.
- Локальный release gate на момент release payload: 33 tests/`OK` за 9.587s, exact isolated flake8 7.3.0 → `0`, `measure-run --check-only` → `OK`; benchmark `457.34ms < 712.29ms`, queries `0/15000`.
- Актуально на `development` после PR с таблицей классов отказов (2026-10-01): 141 tests/`OK` (41 прежний, включая тест лимитов запросов процессов из #31, + 21 `tests/test_redact.py` + 26 `tests/test_sync_state.py` + 7 `tests/test_dependency_free.py` + 5 `tests/test_memory_freshness.py` + 21 `tests/test_sync_caps.py` + 9 `tests/test_sync_dials.py` + 11 `tests/test_failure_classes.py`), flake8 `0`, `measure-run --check-only` → `OK`; CI подтверждается Actions на соответствующем коммите. Строки про 33 теста выше — исторический release gate, не текущее состояние.
- Реальный Edge smoke предыдущего среза → live state update и controls видимы, exit `0`; benchmark `483.02ms < 666.80ms`, queries `0/15000`. Для текущего 100% checkpoint реальная browser tab отдельно не подтверждена.
- GitHub Actions run `36339995752` для exact development SHA и PR-head run `36340188512` завершились `success` на Windows/Ubuntu/macOS (на момент release payload): 33 tests/`OK`, lint `0`, benchmark pass и measure `OK` на каждом native runner.
- Финальный dashboard: embedded snapshot совпадает с `.autopilot/state.js`, `100%`, `7/7` тасков, run завершён. Реальный Edge smoke относится к предыдущему source-identical срезу; финальный metadata-only snapshot отдельно в живой browser tab не проверялся.
- Frozen governance harness → `45/45`, `dangerousCommandsExecuted=false`.
- Последние host metadata — `gpt-5.6-sol/max`; история неоднородна (`3 medium / 36 max / 36 xhigh`), поэтому утверждение о `max` для всей истории не делается.
- Независимый G4 pre-release gate для этого среза дал `GO`; это подтверждает срез до release boundary, но не завершает внешнюю финализацию.

## Release status

- Пользователь 2026-09-27 явно разрешил exact Public payload и последовательность; она выполнена: lease-защищённый `development`, exact-SHA CI, `main` от upstream base `99c7e736`, PR #1, fresh PR-head CI, merge и post-merge memory/dashboard.
- Public repository остаётся `Alpha-Oi/autopilot-jet`, id `1372711955`, default branch `development`; `main` содержит полный release через merge commit `ca6743b`.
- Финальное evidence (`release-finalization-20260927.json`) хранится локально у автора в `.autopilot/` и в репозиторий не входит. Незавершённых release-обязательств нет.

## Как здесь работает Autopilot

`/autopilot-jet` ведёт бриф через требования, спецификацию, план, разработку, код-ревью и слепую приёмку; требование может снять только пользователь.
«Сборка» — весь прогон, единица работы — «таск»; пользовательские названия этапов берутся из таблицы skill.
`.autopilot/` — требования и история конкретных прогонов, не исходник skill и не замена памяти; прогресс показывает `.autopilot/dashboard.html`.
При продолжении сначала читать эту память, затем `.autopilot/state.js` и только инструкции текущего этапа; глобальная установленная копия skill не обновлялась и может отличаться от checkout.

<!-- autopilot:end -->
