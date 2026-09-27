# Спецификация: Autopilot JET — кроссплатформенность и быстрый дашборд

## 1. Задача

Владелец `Alpha-Oi` хочет продолжить историю `nick-vels/skills` в публичном `Alpha-Oi/autopilot-jet` (новое имя явно согласовано G03), вести изменения в `development` и получить доказуемо переносимый Autopilot. Исходные дефекты на момент брифа: `tools/measure-run.py` неверно кодирует Windows-пути и не имеет `--check-only`; `skills/autopilot/tools/sync.py` падает на Windows при вызове `ps`; дашборд повторяет относительный путь `state.js` и выполняет лишние DOM-сканирования каждую секунду. Предложенный CI-шаблон также ссылается на отсутствующие `package.json` и `инструменты/measure-run.py`. Нынешнее состояние исправлений отражено в manifest/state; этот перечень не объявляет старые дефекты текущими.

## 2. Решение и Git-инварианты

- Рабочая история начинается от upstream commit `99c7e73678195cac08080bdd442f0e49a7ccb640` и развивается только в локальной ветке `development`.
- На этапе 1 `execution_plan`, сразу после переноса/клонирования исходной истории и до изменений кода, создать и выбрать `development` (`git checkout -b development`). Все дальнейшие улучшения, коммиты и тесты выполняются только в ней; при продолжении уже созданная ветка переиспользуется, а не создаётся заново. Первоначальное время этих действий проверяется по журналу, а не по наличию ветки сегодня.
- `upstream` остаётся `https://github.com/nick-vels/skills.git`; текущий `origin` — `https://github.com/Alpha-Oi/autopilot-jet.git` (G03).
- До финальной приёмки `main` не изменяется. Перед PR нужны слепая независимая приёмка без NO_GO, фактически отображаемые 100% и успешный Actions run именно для опубликованного development head. Только затем создать PR `development -> main` и выполнить merge по подтверждённому состоянию. Если main отсутствует, её подготовка относится только к этому финальному gate; прежний отказ create-ref не обходится.
- До первого коммита применяется repo-local identity: `user.name = Alpha-Oi`, `user.email = 266576325+Alpha-Oi@users.noreply.github.com`. Это G01, согласованное 2026-09-17 дополнение брифа («Продолжай, как предлагаешь» в контексте принятия адаптированного CI и локальной identity), а не принятое за пользователя предположение. Только этим согласованием исходные global команды заменены на local config; остальные требования не отменены. Проверить local config и автора самого первого коммита; global settings не менять.
- Public target уже создан и переименован в `Alpha-Oi/autopilot-jet` с сохранением id `1372711955` (G03). При продолжении проверять этот существующий repository, не создавать заново прежнее имя `Alpha-Oi/skills`. Публикация обновляет только `development` после отдельного разрешения конкретного public payload; `main` не перезаписывается.
- 2026-09-17 пользователь ответил «согласен» на вопрос о публикации именно `1ab3dad097d3653564b8b2bf0e71d40b5baa5a6d` и `7911d30636afbf2987274e7c881b8a9977eebc67` в Public `Alpha-Oi/autopilot-jet`, включая содержащиеся в них отчёты, локальные пути и метаданные запусков. Для этого точного payload отдельное согласие получено и прежняя остановка публикации снята; незакоммиченные изменения исключены. Разрешение применяется только к `refs/heads/development`, с explicit SHA и lease по прочитанному remote ref; materially different public payload, исходные требования приёмки/host model/effort, 100% и gates main/PR/merge/post-merge этим не разрешены и не отменены. Доказательство согласия, фактического push и нового native CI — publication-approval-and-native-ci-20260917.json; прежний отказ сохраняется датированным в publication-hold.json, не как действующий запрет этого уже согласованного payload.

## 3. Процесс и доказательства

- Выполняются фазы из `skills/autopilot/phases/` от `0-preflight` до `9-memory` с G1–G4; один реализационный таск — один проверенный commit в development.
- На этапе 1 execution_plan вместе с окружением и development создать `.github/workflows/verify.yml`, до перехода к этапу 2 / спецификации путей. Адаптация содержимого согласована G01, но не отменяет время создания. Проверять первоначальную хронологию отдельно; нынешний зелёный CI не доказывает, что workflow существовал раньше.
- Ядро полного цикла — `GPT-5.6 Sol` с максимальным аналитическим рассуждением, с сохранением явного параметра заказчика `--reasoning-effort=high`. Выбрать указанную модель/effort на хосте оркестратора и передавать указанную модель исполнителям; подтверждать фактические настройки по достоверным метаданным запуска. Это живое требование, не вне рамок: при недоступном выборе/подтверждении фиксировать blocker и не выдавать качество тестов за доказательство модели. Дополнение G01 это требование не отменяет.
- Фаза спецификации считается явно инициализированной чтением и применением `skills/autopilot/phases/3-spec.md`; её артефакт — этот `spec.md`.
- Переход между фазами разрешён только после 100% выполнения контракта текущей фазы. Непройденный gate возвращает фазу на доработку и не превращается в предупреждение.
- Проектный код изменяют субагенты по таскам; оркестратор ведёт `.autopilot/`, интегрирует результаты и проверяет полный набор.
- Commit допустим после зелёного локального эквивалента CI. Push допустим после повторной проверки diff и отсутствия секретов. 100% на дашборде допустим только после blind acceptance и фактически зелёного GitHub Actions.
- Первая публикация не должна менять `main`; финальный merge — отдельная операция после CI.

## 4. Карта путей и кроссплатформенный контракт

Статическая карта ниже сверена с кодом `6265e03` 2026-09-16; это фактические consumers, не доказательство запуска на любой ОС. Каталога `инструменты/` нет: фактическая папка инструментов — `tools/`, CLI — `tools/measure-run.py`. Замена пути в CI согласована G01; глубокий анализ всех скриптов фактической папки инструментов и путей HTML остаётся обязательным.

| Источник / преобразование | Consumer и доказательство | Граница |
|---|---|---|
| Checkout discovery: `git rev-parse --show-toplevel`, fallback `pwd -P` | `skills/autopilot/phases/0-instruments.md:19` | Это initialization Autopilot, не общий resolver для CLI и CI |
| Установленный skill: поиск пользовательских/project skill и plugin roots с symlink traversal → `skillDir` | `0-instruments.md:20–23` | Repo template — один возможный источник; не единственный абсолютный путь |
| `skillDir/phases/dashboard-template.html` → `.autopilot/dashboard.html` | `0-instruments.md:24` | Template копируется, Python/HTML его не импортируют |
| `.autopilot/index.html` → symlink `dashboard.html` → HTTP `/` | `0-instruments.md:24,34` | Root route зависит от созданной ссылки; прямой `/dashboard.html` не требует её |
| `skillDir/tools/sync.py` → `.autopilot/sync.py` → `dirname(abspath(__file__))` (`A`) | `0-instruments.md:25`; `sync.py:33` | Запускается runtime copy; запуск canonical helper напрямую адресует его собственный tools directory |
| `A` → `state.js`, `dashboard.html`, `serve.pid`, `serve.log` | `sync.py:34–37`; readers `:46,64,146–149`; writers `:75–78,193–206,263–269` | Anchor — файл helper, не текущий cwd, не `STATE.dir` |
| `dashboard.html.tmp` → `os.replace(..., PAGE)`; `state.js.tmp` → `os.replace(..., STATE)` | `sync.py:75–78,263–269` | Temporary files соседние; snapshot меняет только `/*STATE-BEGIN*/…/*STATE-END*/` |
| CLI project argument → `expanduser` → проверка Windows/POSIX absolute → относительный input через `Path(...).resolve()` → `[:/\\]` в `-` | `tools/measure-run.py:38–43` | Absolute input сохраняет lexical spelling; relative input зависит от cwd. Нет общего git-root discovery, нет нормализации `.`/`..` absolute input |
| Явный logs root или `Path.home()/.claude/projects` + encoded project | `measure-run.py:46–48,168–176` | При одном absolute project input default logs root не зависит от cwd; одинаковый relative input из разных cwd может обозначать разные проекты |
| `<logs>/*.jsonl` → selection/weight; `<session-id>/subagents/*.jsonl` → `analyse` | `measure-run.py:173,181,195,204–207` | Sorted enumeration; default main selection учитывает subagent count и filesize |
| `<session-id>/subagents/*.meta.json` → metadata dictionary → labels | `measure-run.py:197–207` | JSONL decoder пропускает повреждённые строки; meta decoder отдельный и не имеет того же гарантированного fallback |
| `state.js` рядом с document → initial `<script data-state-source>` и `stateURL()` → `pollState()` | `dashboard-template.html:258,272–277,544–558` | `file:`/`http:` adjacent state; `data:` только embedded snapshot; poll cache-busting не меняет resource anchor |
| `LOGO_LIGHT` / `LOGO_DARK` → inline `data:image/png;base64` → `<img src>` | `dashboard-template.html:298–299,789–790` | Сетевой static asset и filesystem substitution для логотипов не нужны |
| `STATE.dir || STATE.slug` → видимая подпись `.autopilot/<run>/` | `dashboard-template.html:894` | Это display label с fallback, не файловый resolver. Helper state/snapshot/server paths используют `A` |
| Repository-relative workflow commands → unittest + `tools/measure-run.py --check-only` | `.github/workflows/verify.yml:40–44` | CI runs from checked-out repository; arbitrary cwd для этих relative команд не обещается |
| Test root через `Path(__file__).parents[1]` → dynamic import canonical CLI/helper, canonical HTML → `node` с `cwd=ROOT` | `tests/test_measure_run.py:11–14`; `test_sync.py:9–12`; `test_dashboard.py:8–15,84–88` | Tests адресуют canonical sources; runtime copy parity проверяется отдельно |

### 4.0.1 Анализ импортов и зависимостей

Полная инвентаризация Python-скриптов указанных инструментальных каталогов (повторно проверена 2026-09-17): tools/ содержит ровно measure-run.py, skills/autopilot/tools/ — ровно sync.py. Runtime .autopilot/sync.py — копия второго файла, не третья самостоятельная реализация. Все импорты каждого файла перечислены ниже; файлы/импорты не исключаются только потому, что для исправления нужна одна функция. Tests и CI включены как потребители этих runtime boundaries.

Охват — два runtime Python файла, canonical HTML и цепь его создания/обновления; tests и CI включены как потребители. Это не аудит всех Markdown-инструкций или вспомогательных скриптов остальных skills.

| Файл / импорт | Происхождение | Фактическое назначение и path effect |
|---|---|---|
| `measure-run.py`: `argparse`, `sys` | Python standard library | CLI parsing, exit/output; imports не вычисляют repository root |
| `measure-run.py`: `os`, `ntpath`, `posixpath`, `re`, `pathlib.Path` | standard library | User expansion, cross-platform absolute recognition, relative input resolution, encoding, file operations, home/log anchor |
| `measure-run.py`: `glob` | standard library | Session/subagent/meta layout enumeration, а не import lookup |
| `measure-run.py`: `json`, `datetime.datetime`, `datetime.timezone`, `collections.Counter` | standard library | UTF-8 records, timestamps/UTC, metrics; не меняют `cwd`/`sys.path` |
| `sync.py`: `os`, `sys`, `re` | standard library | `__file__` anchor, joins/replace, exact directory parsing, interpreter choice |
| `sync.py`: `json` | standard library | State decode/encode и embedded snapshot payload |
| `sync.py`: `socket`, `urllib.error`, `urllib.request` | standard library | Loopback port probe и HTTP health; HTTP 200 сам по себе не доказывает владение PID |
| `sync.py`: `subprocess` | standard library; вызывает внешние executable dependencies | Windows `powershell.exe`/`Get-CimInstance` или POSIX `ps` (`:90–119`); server через `sys.executable -m http.server` (`:194–197`) |

Импорты перечислены в `measure-run.py:21–31` и `sync.py:24–31`. Между двумя runtime-файлами нет локального Python import, dynamic import или изменения `sys.path`: имя `measure-run.py` не превращается в импортируемый helper. Python module resolution относится к библиотекам; project/log resolution относится к переданным файловым путям; `sync.py` использует свой `__file__`. Эти три механизма нельзя объединять под обещанием «независимо от cwd». Tests используют `importlib.util.spec_from_file_location` с canonical file paths, а не новый production import layer.

HTML не имеет внешнего bundler/module import: inline JavaScript и CSS, embedded state и два embedded PNG. Единственный обязательный live resource — adjacent `state.js`; при недоступности state embedded snapshot остаётся доступным. Поэтому исправление `src` заключается в едином state URL и корректном fallback по scheme, а не в подстановке путей к внешним изображениям.

Platform evidence: Windows runtime и Ubuntu Actions подтверждены отдельно; POSIX mocks/encoding tests не равны native macOS smoke и не доказывают буквальную «любую ОС». Неизвестный или недоступный process query также не равен отсутствующему PID.

### 4.0.2 Требуемое определение корней на любой ОС

Требование «Проект должен корректно определять корневые директории при запуске на любой ОС» остаётся действующим и не заменяется перечнем уже зелёных платформ. В любой среде, запускающей этот Python/HTML runtime, корни не содержат жёстко заданного Windows/Linux/macOS checkout и не выводятся из произвольного cwd:

1. При инициализации получить Git root текущего целевого проекта через git rev-parse --show-toplevel; вне Git использовать физический абсолютный корень выбранного проекта. Найти установленный skill с разрешением symlink chain; skillDir не является корнем целевого проекта.
2. Копировать helper и HTML в <project-root>/.autopilot/. Helper во всех ОС вычисляет A = dirname(abspath(__file__)); state, snapshot, PID/log и соседние temporary files вычисляются только от A. Canonical helper не запускать как runtime другого проекта.
3. CLI native relative project input сначала преобразовать в физический absolute путь относительно native cwd; home/log root получить из Path.home() либо явного root, затем добавить Claude encoding абсолютного project input. Windows и POSIX absolute spelling распознаются независимо от ОС запуска; relative input из разных cwd не объявляется одним проектом. Отсутствующие logs дают контролируемую ошибку, не ошибочный Git root.
4. HTML file:/http: используют URL исходного adjacent state.js, initial load и poller — один resolver. У data: нет файлового корня: оно snapshot-only. Embedded CSS/PNG не требуют внешнего static resource directory.
5. Process query — платформенная граница, не resolver корня: Windows использует CIM, POSIX — ps. Недоступность внешней команды безопасно деградирует по §14, не меняет A и не разрешает завершение чужого процесса/дублирующий server.

Приёмка проверяет каждый root/consumer, CLI/helper из другого cwd, relocated checkout с пробелами/Unicode, explicit/default home/log root, Windows/POSIX inputs и схемы HTML. Нужны native Windows, Linux и macOS проверки основных ветвей; другие ОС и недоступные механизмы нельзя объявить выполненными по одной Windows-проверке. Фактический непроверенный охват остаётся видимым до независимой итоговой проверки; буквальное требование не снимается этим разделом.

### 4.1 Первый запуск, пустые состояния и неверный ввод

- `measure-run.py --check-only` проверяет два encoding examples для absolute POSIX/Windows inputs и возвращает `0`; это smoke, не отдельный syntax/all-functions gate. Синтаксис проверяет exact flake8, поведение — tests.
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
- POSIX использует `ps`; Windows — безопасный системный запрос без shell interpolation. Недоступный query возвращает безопасный unknown/пустой результат, но сам по себе не разрешает новый Popen для уже recorded server; unknown и dead различаются по §14 (D01/T06).
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
- После каждого commit безусловно обновляются state/interfaces и оба файла проектной памяти; итоговый AGENTS.md описывает реальные команды и ограничения из завершённого кода.
- После подтверждённого PR merge отдельно зафиксировать фактическое состояние системы в AGENTS.md именно в ветке main и обновить compact mirror CLAUDE.md. Проверить remote main, соответствующий memory commit, raw AGENTS.md из main и post-merge проверки. Память в development до merge не заменяет этот шаг.

## 8. GitHub-публикация

- Read-only API сначала проверяет login и наличие `Alpha-Oi/autopilot-jet` с id `1372711955`.
- Все операции создания, клонирования и push выполняются через права текущей активной GitHub-сессии Alpha-Oi, как требует исходный бриф. Это включает clone публичного upstream: session-backed credential helper/API без извлечения или печати токена, а не отмена правила потому, что чтение возможно анонимно. Подтверждать login безопасным GET /user, фиксировать способ выполнения; первоначальную неподтверждённую авторизацию clone не объявлять доказанной.
- Исходное создание Public через API авторизованной сессии выполнено при прежнем имени `Alpha-Oi/skills`; G03 переименовал тот же repository. При неожиданном отсутствии нового target остановить release и проверить id/доступ, не создавать другой repository автоматически. Доступный путь — gh api с session-backed авторизацией без чтения credential value; API-создание Public target подтверждено отдельным артефактом. Недоступность одного connector не отменяет API-требование.
- После создания добавить `origin`, проверить точный URL и права, затем опубликовать только `development`.
- Если target существует на момент публикации, обязательное принудительное обновление выполняется только для `refs/heads/development` после чтения remote ref, через lease-защищённый force update. `main` до финала не обновлять.
- После успешной независимой приёмки, честных отображаемых 100% и зелёного workflow текущего development head создать PR development -> main, дождаться terminal success для PR head и выполнить merge. Подтвердить remote main, Public visibility и отдельно обновить AGENTS.md на main по §7. Непройденный gate/прежний отказ создания main не обходятся другой командой/API.

## 9. CI/CD и приёмка

`.github/workflows/verify.yml` сохраняет назначение предложенного шаблона, но исправляет два фактически неработоспособных места: npm не запускается без `package.json`, а измеритель находится в `tools/measure-run.py`.

Дословный YAML из брифа не работает на фактическом дереве: setup-node получает не npm lockfile, npm запускается без package.json, path gate ищет отсутствующий инструменты/measure-run.py. G01 согласован заказчиком 2026-09-17 словами «Продолжай, как предлагаешь» в ответ на предложение принять адаптированный CI. Сохранить имя Autopilot CI/CD Verification, job validate, triggers main/master/development, версии Actions, Python 3.11/Node 20 и exact flake8-команду; убрать ложный npm cache, npm запускать только при реальном package.json, использовать tools/measure-run.py, добавить meaningful unit tests. Согласованная замена содержимого не отменяет раннее создание workflow и свежий CI для нового head; отклонение остаётся в итоговом отчёте.

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

Использовать фактические логи CI/CD для контроля качества кода (R15), а не только общий зелёный статус run. После разрешённой публикации выбрать Actions run с head_sha, равным опубликованному development head; через права текущей сессии прочитать jobs/steps и их логи. Проверить exact flake8-команду и результат, полный unittest/count, measure-run --check-only и dashboard benchmark/query budget; любые traceback, failed/cancelled/timed-out шаги или неизвестный результат блокируют приёмку и release. При дефекте вернуть соответствующий таск на исправление и повторить проверки для нового head. В локальном артефакте прогона сохранить run URL/id, head SHA, время, job/step conclusions и необходимые строки результата; значения credentials не извлекать, возможные секреты редактировать до записи. Исторические логи другого SHA не доказывают качество нового кода. Публикация самого отчёта/локальных метаданных по-прежнему требует отдельного согласия; чтение логов не разрешает push/main/PR/merge.

## 10. Согласованные изменения и остающиеся ограничения

| Требование | Действующий контракт |
|---|---|
| R01 — конкретная модель/уровень reasoning | Живое требование §3; host selection/достоверное подтверждение обязательны, неподтверждённое не равно выполненному |
| R03/R04 — Git identity | Только согласованная G01 замена global команд на existing repo-local Alpha-Oi/noreply из §2; timing первого коммита проверяется отдельно |
| R14 — CI | Только согласованная G01 адаптация содержимого §9; раннее создание workflow по §3 сохраняется |

Не добавляются новые production dependencies, bundler, framework, внешний backend, telemetry или публичный hosting дашборда.

Другие требования не deferred/dropped только потому, что хост, платформа или исторический момент не подтверждены. Пробелы остаются незавершёнными и сообщаются итоговому checker/заказчику. Ретроспективное добавление текста не доказывает прежнюю последовательность фаз, авторизацию clone, отсутствие pre-commit ошибок или model/effort. G01 не разрешает обход NO_GO/прежнего отказа create-ref main.

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
| 13 | R02, R26, R28–R31; G03 | Как `Alpha-Oi`, я получаю Public `Alpha-Oi/autopilot-jet` и PR в `main` | API metadata, remote refs, PR и merge подтверждены |

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

## 14. D01 — недоступность process query и дублирование серверов

Build evidence 2026-09-16, T06: recorded PID 5716 / port 56521 подтверждён своим через approved read-only CIM; ports 56247 и 56521 одновременно HTTP 200 с точным state.js. В sandbox query command line недоступен. Существующий fallback `cmdline == ""` → new port/Popen не отличает unknown от dead и накопил работающие helper copies.

D01 служит R22/R12 и не отменяет ownership boundary или recovery. Исполнитель сохраняет `cmdline(pid) -> str` и `serve(state) -> str`; если нужен status seam, он минимальный и не вносит production dependency. При responding recorded server и unknown command query snapshot обновляется, процесс/PID record не трогаются, возвращается явное предупреждение без claims «наш/жив/готов». При unknown status и кратком HTTP timeout не делается вывод о смерти процесса; controlled restart допускается после положительно доказанного отсутствия/stale PID. Known foreign и unrecorded processes не завершаются. Не применять Windows `os.kill(pid, 0)`: никакие process probes не должны завершать процессы.

Обычный подтверждённый own reuse, bind `127.0.0.1`, detached hidden launch, finished/SSH/CI guards, failed-start cleanup только собственного Popen сохраняются. Критерии и regression tests — T06. Ни main, ни PR/merge не входят в это исправление.

## 13. Покрытие манифеста

| Требование | Раздел спецификации |
|---|---|
| R01 | §§3,10 |
| R02 | §§2,8 |
| R03 | §§2,10; G01 |
| R04 | §§2,10; G01 |
| R05 | §§2,11 |
| R06 | §§2,11 |
| R07 | §§2,11 |
| R08 | §3 |
| R09 | §3 |
| R10 | §§4–5,11–12 |
| R11 | §§4,6,11–12 |
| R12 | §§4.0.2,4–6 |
| R13 | §7 |
| R14 | §§3,9,10; G01 |
| R15 | §§3,9 |
| R16 | §§3,9 |
| R17 | §2 |
| R18 | §§4,4.0.1 |
| R19 | §§4,4.0.2 |
| R20 | §3 |
| R21 | §6 |
| R22 | §§4–5,14 |
| R23 | §3 |
| R24 | §§2,3,9 |
| R25 | §§3,9 |
| R26 | §§2,8 |
| R27 | §7 |
| R28 | §8 |
| R29 | §§8,16; G03 |
| R30 | §8 |
| R31 | §8 |
| R32i | §§2,8 |

G01 (изменение R03/R04/R14 заказчиком): §§2,9,10; цитата и контекст в дополнениях брифа.

## 15. Разрешённая точечная коррекция governance hook

G02 — дополнение пользователя «Исправляй хук» от 2026-09-17. Сценарий: записывать документацию с цитатами брифа без ложного запрета, сохранив запрет опасных исполняемых команд и записей в защищённые пути. Коррекция ограничена установленным C:/Users/Crown-Aliy/.codex/hooks/governance_hook.py; не отключать hook, не менять hooks/config/global Git settings. Это не разрешение на Git/publication.

До правки сохранить byte-identical backup вне всех репозиториев. Различать shell execution и inert payload apply_patch/Edit/Write; protected-path проверки сохранять для всех инструментов, destructive-command запреты — для shell и неизвестных tool kinds. Флаг создания -b не смешивать с принудительным -B из-за case-insensitive matching. Исправить обнаруженные пропуски forced-clean/drive-format patterns, не расширяя права на опасные операции.

Приёмка коррекции — frozen decision-only unit tests и синтетические Python dispatcher события: без запуска опасных команд проверить allow для документации/безопасных команд, deny для опасных команд/защищённых путей и fail-closed для неизвестных tool kinds. Сохранить before/after результаты и source hashes, подтвердить неизменность конфигурации и прохождение harmless live document patch. Simulations не равны full live Codex E2E или доказательству любого будущего перехвата.

Коррекция выполнена по отдельному разрешению; final source SHA256 A9489426518688F5EC772B1FC193D7290491D6CEF482D4B0E08C71288D30CD63 соответствует 45/45 safe decision tests. Backup, frozen harness, результаты и ограничения — verification-tools/governance-hook-repair-20260917-012107 вне Git worktree. Внешние файлы и защита при продолжении не меняются заново без отдельной необходимости/разрешения.

## 16. Согласованное переименование Autopilot JET

G03 — ответ пользователя «да» 2026-09-17 на вопрос «Переименовать `Alpha-Oi/skills` в `Alpha-Oi/autopilot-jet`?». Сценарий: владелец Alpha-Oi продолжает тот же проект под именем Autopilot JET, без повторного создания repository и переписывания истории. PATCH меняет только name; проверка GET должна сохранить id1372711955/Public/default development/remote refs. Origin D: рабочих копий, текущие ссылки плана и dashboard обновляются; локальные папки остаются прежними.

Согласование заменяет только имя R29. Исходный execution_plan и dated evidence с прежним именем не переписываются; G01/G02, full acceptance, current-head native CI и запрет обхода прежнего public-export/main/PR/merge отказа сохраняются. Проверка имени не равна независимому G2 amended brief/spec или release GO. Подтверждение — repository-rename-verification.json.

Более позднее отдельное согласие на exact two-commit public payload описано в §2: G03 сам по себе не разрешал экспорт, но ответ «согласен» снимает прежнюю остановку только для 1ab3dad/7911d30 в development. Остальные ограничения и предыдущие dated evidence сохраняются; публикация нового отчёта или materially different payload не выводится автоматически из согласия на эти два коммита.

## 17. Разрешённая финальная release-последовательность

G04 — ответ пользователя от 2026-09-27: «Разрешаю описанный в `release-authorization-scope-20260925.md` финальный Public payload и release-последовательность для `Alpha-Oi/autopilot-jet`». Разрешение охватывает exact reviewed Public payload и механические финальные записи в тех же зонах, explicit lease-защищённое обновление только `development`, создание отсутствующей `main` строго от `99c7e73678195cac08080bdd442f0e49a7ccb640`, PR `development -> main`, merge только после fresh PR-head checks, затем отдельную final memory/dashboard запись в `main`, CI и read-only verification.

Порядок обязателен: pre-commit local gate и secret/staged-set review → development push → terminal-success Actions и чтение обязательных logs → dashboard 100% → создание main/PR → terminal-success PR checks → merge → post-merge memory/dashboard, CI и синхронизация default development. Ошибка, cancelled/timed-out/unknown результат или несовпадение SHA останавливают последовательность. Разрешение не распространяется на force update других refs, global Git config, dependency changes, пользовательские удаления или новый непроверенный payload.
