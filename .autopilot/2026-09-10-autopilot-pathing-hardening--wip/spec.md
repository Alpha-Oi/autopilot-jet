# Спецификация: кроссплатформенный Autopilot и быстрый дашборд

## 1. Задача

Владелец `Alpha-Oi` хочет продолжить историю `nick-vels/skills` в публичном `Alpha-Oi/skills`, вести изменения в `development` и получить доказуемо переносимый Autopilot. Сейчас `tools/measure-run.py` неверно кодирует Windows-пути и не имеет `--check-only`; `skills/autopilot/tools/sync.py` падает на Windows при вызове `ps`; дашборд повторяет относительный путь `state.js` и выполняет лишние DOM-сканирования каждую секунду. Предложенный CI-шаблон также ссылается на отсутствующие `package.json` и `инструменты/measure-run.py`.

## 2. Решение и Git-инварианты

- Рабочая история начинается от upstream commit `99c7e73678195cac08080bdd442f0e49a7ccb640` и развивается только в локальной ветке `development`.
- `upstream` остаётся `https://github.com/nick-vels/skills.git`; будущий `origin` — `https://github.com/Alpha-Oi/skills.git`.
- До финальной приёмки `main` не изменяется. После зелёного CI создаётся PR `development -> main`; merge выполняется только по подтверждённому состоянию.
- Для коммитов применяется repo-local identity. Имя — `Alpha-Oi`; email — подтверждённый GitHub noreply, а не ошибочный литерал из брифа. Глобальный config машины не меняется.
- Репозиторий создаётся Public, если API снова подтверждает отсутствие `Alpha-Oi/skills`. Если он возникнет до публикации, обновляется только `development`; `main` не перезаписывается.

## 3. Процесс и доказательства

- Выполняются фазы Autopilot 0–9 с G1–G4; один реализационный таск — один проверенный commit в `development`.
- Фаза спецификации считается явно инициализированной чтением и применением `skills/autopilot/phases/3-spec.md`; её артефакт — этот `spec.md`.
- Переход между фазами разрешён только после 100% выполнения контракта текущей фазы. Непройденный gate возвращает фазу на доработку и не превращается в предупреждение.
- Проектный код изменяют субагенты по таскам; оркестратор ведёт `.autopilot/`, интегрирует результаты и проверяет полный набор.
- Commit допустим после зелёного локального эквивалента CI. Push допустим после повторной проверки diff и отсутствия секретов. 100% на дашборде допустим только после blind acceptance и фактически зелёного GitHub Actions.
- Первая публикация не должна менять `main`; финальный merge — отдельная операция после CI.

## 4. Карта путей и кроссплатформенный контракт

| Объект | Источник истины | Потребители | Контракт |
|---|---|---|---|
| Корень checkout | `git rev-parse --show-toplevel` или явный аргумент CLI | CI, измеритель, Autopilot | абсолютный нормализованный путь, не зависит от cwd |
| Каталог логов Claude | `<home>/.claude/projects/<encoded-project-path>` | `measure-run.py` | Windows `C:\\Users\\X` → `C--Users-X`; POSIX `/Users/x` → `-Users-x`; оба разделителя и `:` кодируются в `-` |
| Измеритель | `<repo>/tools/measure-run.py` | разработчик, CI | запуск из любого cwd с абсолютным/относительным project path; `--check-only` не требует реальных логов |
| Шаблон дашборда | `<repo>/skills/autopilot/phases/dashboard-template.html` | Phase 0 | копируется, а не импортируется в рантайме |
| Живое состояние | `<project>/.autopilot/state.js` | initial script и poller | единый вычисленный URL рядом с текущим dashboard document; query-параметр меняется только для cache busting |
| Снимок состояния | маркеры внутри `.autopilot/dashboard.html` | file/data fallback | атомарно обновляется `sync.py`; относительные ресурсы не обязательны для отображения снимка |
| Сервер дашборда | `.autopilot` на `127.0.0.1` | browser pane | управление процессом работает на Windows, Linux и macOS; чужие процессы не завершаются |
| Состояние прогона | `.autopilot/state.js` | dashboard, resume | все файловые пути строятся через `dir`, не через `slug` |

Анализ импортов охватывает весь текущий Python runtime проекта: единственный скрипт верхнего `tools/` — `tools/measure-run.py`, и единственный runtime helper Autopilot — `skills/autopilot/tools/sync.py`. HTML-анализ охватывает все `src`, runtime URL и snapshot markers в `skills/autopilot/phases/dashboard-template.html`. Каталога `инструменты/` в исходнике нет; его имя из CI-шаблона является ошибочным переводом фактического `tools/`.

### 4.1 Первый запуск, пустые состояния и неверный ввод

- `measure-run.py --check-only` проверяет нормализацию репрезентативных POSIX/Windows путей, синтаксис и доступность внутренних функций, печатает краткий успешный результат и возвращает `0`.
- Без аргумента обычный режим печатает usage и возвращает ненулевой код; отсутствующий каталог логов и пустой каталог дают понятные ошибки без traceback.
- Пустой `state.js`, повреждённый JSON и отсутствующий dashboard не затирают последний корректный снимок.

### 4.2 Сбой, прерывание, рост и границы

- Файлы JSONL читаются с `encoding="utf-8"`; повреждённые строки пропускаются, отсутствующие usage/content не падают.
- Тысячи session/subagent files обрабатываются детерминированно; сортировка и выбор сессии не зависят от cwd.
- PID без подходящей командной строки никогда не считается своим. На Windows команда процесса получается через доступный системный механизм либо проверка PID деградирует безопасно без массового завершения процессов.
- Сервер всегда привязан к `127.0.0.1`; SSH/CI не поднимают его. Повторный запуск переиспользует живой сервер или старый порт, если он свободен.
- Завершение прогона не поднимает сервер заново; ошибка запуска оставляет работоспособный file/snapshot fallback.

## 5. Надёжность Python-автоматизации

### 5.1 `measure-run.py`

- Ввести чистые функции нормализации project path и разрешения logs root; для тестов home/log root передаются явно, а production default берётся из `Path.home()`.
- Использовать `pathlib.Path` для локальных файловых операций, но кодировать исходный абсолютный project path по фактическому правилу Claude: `:` и каждый `/`/`\\` становятся `-`.
- Добавить argparse-совместимый `--check-only`; сохранить существующий positional interface `<project> [session-id]`.
- Деление `read/write` защищено от нуля; timestamps разных timezone не вызывают необработанный `TypeError`; чтение файлов явно UTF-8.
- Проверки покрывают POSIX/Windows encoding, `--check-only`, пустые/битые JSONL, выбор основной сессии и нулевые counters.

### 5.2 `sync.py`

- Изолировать получение command line процесса за переносимым `cmdline(pid)` и перечисление процессов за `iter_processes()`.
- POSIX использует `ps`; Windows использует безопасный системный запрос без shell interpolation. Недоступность механизма возвращает пустой список и не мешает запуску нового локального сервера.
- `subprocess.Popen` применяет платформенные detached flags: `start_new_session=True` на POSIX, скрытое окно и новая process group на Windows.
- Все читаемые/записываемые текстовые файлы имеют `encoding="utf-8"`; log handle закрывается в родителе после запуска.
- Unit tests мокируют процессы/HTTP/порт и доказывают, что чужой сервер не завершается.

## 6. Дашборд и производительность

- Определить один `STATE_URL` из URL исходного `<script data-state-source>`; initial load и poller используют один и тот же относительный ресурс. Для `file:` и `http:` путь должен указывать на соседний `state.js`; для `data:` снимок остаётся единственным источником.
- Cache-busting добавляется через `URL.searchParams`, не строковой конкатенацией, чтобы уже существующие query/hash не ломались.
- `tick()` получает один snapshot `STATE`, один busy-state и кэшированные коллекции live/idle/ago elements. DOM-кэши обновляются только после `render()`.
- Полный `innerHTML` render выполняется только при изменении stamp. Stamp включает `updatedAt`, `finishedAt` и число тасков; контракт `state.js` гарантирует изменение `updatedAt` при любом значимом обновлении.
- Acceptance performance: на репрезентативном состоянии (8 этапов, 100 тасков) 1 000 вызовов `tick()` после render не медленнее baseline и даёт минимум 20% сокращения DOM-query invocations; один неизменившийся poll не вызывает render.
- Доступность, RU/EN, theme, scroll position, offline snapshot, progress math и 100% финальное состояние сохраняются.

## 7. Память проекта

- `AGENTS.md` — каноническое текущее описание проекта между marker-блоками; `CLAUDE.md` содержит `См. @AGENTS.md` и компактное зеркало текущего состояния прогона.
- На каждой итерации/commit безусловно обновляются состояние в `AGENTS.md` и его компактное зеркало в `CLAUDE.md`. Полное описание не дублируется, но branch/stage/run/last-commit физически присутствуют в обоих файлах.
- `.autopilot/` хранит brief, manifest, spec, interfaces, таски, state и dashboard этого прогона.
- После каждого commit безусловно обновляются state/interfaces и оба файла проектной памяти; итоговый `AGENTS.md` описывает реальные команды и ограничения из завершённого кода.

## 8. GitHub-публикация

- Read-only API сначала проверяет login и наличие `Alpha-Oi/skills`.
- Любая внешняя create/push/PR/merge операция выполняется только авторизацией активной GitHub-сессии `Alpha-Oi`. Публичный upstream clone не требует передачи токена; credential value никогда не извлекается и не записывается.
- Если репозиторий отсутствует, создать Public через доступную авторизацию сессии. Текущий GitHub connector подтверждает login, но не предоставляет create-repository; до появления допустимой операции локальная сборка продолжается, публикация остаётся внешним gate.
- После создания добавить `origin`, проверить точный URL и права, затем опубликовать только `development`.
- Если target существует на момент публикации, обязательное принудительное обновление выполняется только для `refs/heads/development` после чтения remote ref, через lease-защищённый force update. `main` до финала не обновлять.
- После зелёного workflow создать PR `development -> main`, дождаться terminal success и выполнить merge. Затем подтвердить remote `main`, Public visibility и содержимое `AGENTS.md`.

## 9. CI/CD и приёмка

`.github/workflows/verify.yml` сохраняет назначение предложенного шаблона, но исправляет два фактически неработоспособных места: npm не запускается без `package.json`, а измеритель находится в `tools/measure-run.py`.

Дословный YAML из брифа не может одновременно выполнить R12/R16/R25: `setup-node` получает не npm lockfile, `npm ci` запускается без `package.json`, а проверка ищет отсутствующий `инструменты/measure-run.py`. Решение `ASSUMPTION`: сохранить имя workflow, triggers, версии Actions, Python/Node версии и flake8-команду; заменить только три доказанно нерабочих repo-specific строки и добавить тесты. Рабочий CI имеет приоритет над дословным, но гарантированно падающим шаблоном; отклонение обязательно перечисляется в итоговом отчёте.

Обязательные шаги:

1. `actions/checkout@v4`.
2. `actions/setup-node@v4`, Node 20, без ложного npm cache для `skills-lock.json`.
3. `actions/setup-python@v5`, Python 3.11.
4. npm install только если существует `package.json`; иначе явное сообщение о dependency-free dashboard.
5. `flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics`.
6. `python -m unittest discover -s tests -v`.
7. `python tools/measure-run.py --check-only`.
8. Статическая проверка dashboard и браузерная smoke/performance-проверка локально.

Локальная приёмка повторяет шаги 5–8. Любой ненулевой код блокирует commit. Внешняя приёмка требует успешного GitHub Actions run на опубликованном `development`.

## 10. Вне рамок и ограничения

| Требование | Почему не сейчас |
|---|---|
| R01 — конкретная модель/уровень reasoning | Выбирается средой Codex, не кодом репозитория; выполнение проверяется по артефактам, не заявлению о модели |
| R03 — глобальный `user.name` | Изменение конфигурации всей машины не требуется; применяется repo-local identity |
| R04 — глобальный ошибочный email | Литерал `Alpha-Oi@://github.com` некорректен; используется GitHub noreply после подтверждения account id/login |

Не добавляются новые production dependencies, bundler, framework, внешний backend, telemetry или публичный hosting дашборда.

Три требования не могут быть выполнены буквально внутри проекта и потому не считаются молча выполненными:

1. R01 — выбор `GPT-5.6 Sol` и уровня reasoning принадлежит хосту; доказательство качества строится на G1–G4 и тестах.
2. R03–R04 — глобальный config затрагивает все репозитории машины, а email из брифа некорректен; repo-local identity обеспечивает нужного автора без побочного эффекта.
3. R14 — дословный workflow гарантированно красный на текущем дереве; применяется минимально исправленный вариант из §9.

## 11. Пользовательские истории и приёмка

| # | Метка | История | Приёмка |
|---|---|---|---|
| 1 | R05–R07, R17, R32i | Как владелец, я продолжаю upstream-историю в `development`, чтобы `main` оставался стабильным | branch от точного upstream commit; `main` неизменён до финала |
| 2 | R10, R12, R18 | Как разработчик Windows/Linux/macOS, я запускаю измеритель из любого cwd | одинаково корректный logs path; тесты трёх платформ |
| 3 | R10.1 | Как CI, я запускаю `--check-only` без пользовательских логов | exit `0`, краткий отчёт |
| 4 | R10.2, R22 | Как разработчик, я вижу контролируемую ошибку для отсутствующих/битых данных | нет traceback, остальные строки анализируются |
| 5 | R11, R12 | Как пользователь, я открываю dashboard по file/http и получаю правильный `state.js` рядом | state подхватывается или используется snapshot fallback |
| 6 | R21 | Как пользователь, я вижу плавно обновляемые часы без лишнего полного render | benchmark и DOM-query budget выполнены |
| 7 | R22 | Как пользователь Windows, я запускаю `sync.py` без Unix `ps` | snapshot и server path завершаются без `WinError 2` |
| 8 | R22.1 | Как владелец машины, я не теряю чужие процессы | тест доказывает узкую проверку ownership |
| 9 | R08–R09, R20, R23 | Как заказчик, я получаю трассируемый агентный прогон | G1–G4, таски, review и отдельные commits |
| 10 | R13, R27 | Как следующая сессия, я читаю одну непротиворечивую память | `AGENTS.md` канон, `CLAUDE.md` pointer |
| 11 | R14–R16 | Как сопровождающий, я получаю работающий CI вместо декларативного шаблона | workflow соответствует реальным путям и локально воспроизводим |
| 12 | R24–R25 | Как заказчик, я вижу 100% только после доказанной готовности | dashboard final state и зелёный Actions run |
| 13 | R02, R26, R28–R31 | Как `Alpha-Oi`, я получаю Public `Alpha-Oi/skills` и PR в `main` | API metadata, remote refs, PR и merge подтверждены |

Для process-only требований измерения First run/Empty/Wrong input/Failure/Interruption/Growth/Boundaries/Aftermath не применимы к отдельному UI; их наблюдаемая приёмка определена Git-инвариантами, CI gate и внешним release gate выше. Для `measure-run.py`, `sync.py` и dashboard все восемь измерений определены в §§4–6.

## 12. Границы и швы

| Модуль | Владеет | Выставляет | Прячет |
|---|---|---|---|
| `tools/measure-run.py` | нормализация project/log paths и анализ JSONL | `encode_project_path(path)`, `logs_dir_for(path, root=None)`, `analyse(path, label)`, CLI `main(argv=None)` | globbing, weights, формат таблицы |
| `skills/autopilot/tools/sync.py` | атомарный snapshot и жизненный цикл локального сервера | `read_state()`, `write_snapshot(state)`, `cmdline(pid)`, `iter_processes()`, `serve(state)`, `main()` | платформенные process queries и detached flags |
| dashboard inline runtime | URL состояния, render и clock updates | `stateURL()`, `applyState()`, `pollState()`, `render(lang)`, `tick()` | DOM caches, presentation HTML, theme/lang storage |
| `.github/workflows/verify.yml` | воспроизводимый quality gate | команды CI §9 | GitHub runner setup |
| Git release boundary | target visibility, refs, PR, merge | GitHub API metadata и remote refs | credential values |

Основные тестовые швы: чистая path normalization для измерителя; замоканные process/HTTP функции для sync; реально загруженная dashboard page для browser smoke/performance. Новые production abstractions не создаются.

### 12.1 Привязка глубокой проработки

| Уточнение | Родитель |
|---|---|
| CLI usage, `--check-only`, malformed JSONL, timestamps, zero counters | R10, R12, R22 |
| Переносимое перечисление процессов, detached flags, PID ownership | R12, R22 |
| `127.0.0.1`, SSH/CI fallback, повторный запуск сервера | R12, R22 |
| Единый state URL, cache busting, offline snapshot | R11, R12 |
| DOM cache, benchmark и отсутствие render без нового stamp | R21 |
| Unit/browser tests и локальный эквивалент workflow | R14–R16, R25 |
| Read-only target check, origin verification, remote refs и Public visibility | R02, R26, R28–R31, R32i |
| Marker-блок, канонический `AGENTS.md` и pointer | R13, R27 |

Это `R##.n`-углубления, а не свободные новые возможности: каждое существует только для проверяемого выполнения указанного родителя.

## 13. Покрытие манифеста

| Требование | Раздел спецификации |
|---|---|
| R01 | §10 |
| R02 | §§2, 8 |
| R03–R04 | §§2, 10 |
| R05–R07 | §§2, 11 |
| R08–R09 | §3 |
| R10 | §§4–5, 11–12 |
| R11 | §§4, 6, 11–12 |
| R12 | §§4–6 |
| R13 | §7 |
| R14–R16 | §§3, 9 |
| R17 | §2 |
| R18–R19 | §4 |
| R20 | §3 |
| R21 | §6 |
| R22 | §§4–5 |
| R23 | §3 |
| R24–R25 | §§3, 9 |
| R26–R31 | §8 |
| R32i | §§2, 8 |
