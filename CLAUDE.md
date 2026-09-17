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

- Последний root `python -B -m unittest discover -s tests -v` — 24 tests in 7.422s, `OK`; excerpt/snapshot/parity/HTTP — в `.autopilot/2026-09-10-autopilot-pathing-hardening--wip/premerge-release-verification.json`. Independent check-only — `OK`, premerge-blind-acceptance.md; предыдущие root raw outputs — local-verification-result.json.
- Полный repo `flake8` с `--count --select=E9,F63,F7,F82 --show-source --statistics` — `PASS`, stdout `0`, exit `0`, без `exclude` или ослабления. Проверенная копируемая команда PowerShell и полный путь venv Python находятся в @AGENTS.md.
- flake8 7.3.0 запущен из отдельного venv вне Git worktree на CPython 3.14.3 Windows; `flake8` в обычном `PATH` отсутствует. Sandbox дал `WinError 5` в multiprocessing `Pipe`; точный `require_escalated` rerun прошёл. Основной Python, global config и production dependencies не менялись.
- HTTP-браузер — `PASS`: actual DOM 8 stages / 100 tickets / 94 clocks; медиана 5 × 1000 `tick()` — 570.7 ms ≤ upstream baseline 741.5 ms; selector queries 0 / 15000, console logs `[]`. Это не доказательство Ubuntu CI.

## Релиз

- Состояние — `pre-release`, финальная приёмка — `NO-GO`; `development` code checkpoint `7571f27`, локальный `main` и `upstream/main` — `99c7e73678195cac08080bdd442f0e49a7ccb640`.
- `upstream` — `https://github.com/nick-vels/skills.git`; `my-skills-fork` — `https://github.com/Alpha-Oi/skills-Pill.git`; `origin` — точный `https://github.com/Alpha-Oi/skills.git`.
- Прямой approved-network GET /user подтвердил Alpha-Oi; Public Alpha-Oi/skills создан через API (id 1372711955), development опубликована с lease expected absence; remote head 247535a, main отсутствует, default branch development.
- Ubuntu Actions run 35071567560 для 247535a — success; raw evidence в github-actions-result.json. Более новый live run 35094887597 для 6265e03 также success: 24 tests in 2.607s OK, flake8 0, measure check OK, Node VM queries 0/15000.
- Независимая pre-merge приёмка завершена NO_GO: 31 строка брифа, 11 реализовано / 16 частично / 4 нет; свежий Windows suite 24 tests in 8.416s OK, реальный HTTP UI smoke PASS. Полный отчёт: `.autopilot/2026-09-10-autopilot-pathing-hardening--wip/premerge-blind-acceptance.md`.
- R12/R14 возвращены в in-ticket: native macOS/любая ОС и буквальный CI template не доказаны; global identity/email и host model/reasoning остаются расхождениями. Dashboard79%, main отсутствует, PR/merge/post-merge не выполнены.
- Create-ref main на upstream base отклонён проверкой разрешений до выполнения из-за NO_GO/100% gate. Нужен явный ответ пользователя, обход не выполняется; result/refs в premerge-release-verification.json того же run directory.
- Sandbox-сообщение `gh auth status` о token invalid не доказывает отсутствие сессии: сначала используй прямой API GET с разрешённой сетью, без запроса или извлечения токена.
- `main` до финального acceptance/merge gate не изменён; публикация, PR, merge и release остаются отдельной границей разрешения и live-проверки.

## Checkpoint 2026-09-16 — повторная проверка спецификации

- Ветка development / HEAD `6265e03`; source/tests/workflow и runtime helper не изменены. Root repeat: 24 tests in 7.059s OK, check-only OK, exact full-repo flake8 stdout0/exit0; `t06-intake-checkpoint.json` в текущем run directory.
- Анализ импортов и карта путей дополнены; независимый source-aware recheck COMPLETE для обоих artifacts, `phase3-artifact-recheck.md`. Это не G2/G4/GO.
- Fresh G2 failed6/half4: сохраняются подмены/пропуски обязательств. Contract amendment в spec остановлен governance hook до выполнения; не обходить запрет и не считать этот патч исполненным. `t06-spec-coverage.md` содержит точный checkpoint.
- D01/T06: recorded helper отвечает, command query может быть unavailable; два helper ports отдают один state. Недоступный query не равен dead. Executor завершил только read-only intake, edits не начаты, новый interface не реализован. Не завершать существующие серверы; до исправления snapshot refresh через существующий `--no-serve`.
- Actual logs contract: default home/log root cwd-independent при одном absolute project input; relative input разрешается относительно native cwd, absolute dot-segment normalization пока не реализована. Native macOS/any-OS acceptance остаётся unverified.
- Полный checkpoint/G2/D01/permission/release context — @AGENTS.md; source repair и release не выполнены.

- 2026-09-16T16:10:02.2499333+03:00: persistent goal blocked/incomplete; full scope preserved, ждёт решения пользователя. Dashboard доступен, source/main/PR без изменений.

## Checkpoint 2026-09-17 — причина остановки установлена

- Read-only hook diagnosis: configured HOME macro указывает на проверенный global governance_hook.py; case-insensitive `-b`/`-B` collision и классификация patch data подтверждены статически, без handler replay или исправления.
- Fresh GitHub: Public Alpha-Oi/skills, только development6265e03, Actions35094887597 success, main/open PR отсутствуют. Source/tests/workflow/helper без новых правок, commits/push/release не выполнялись.
- Dashboard session95212 live/state200, не перезапущена; snapshot refresh только `--no-serve` до исправления D01.
- Goal blocked/incomplete после повторившегося approval blocker; полный objective сохранён. Global hook repair и original-contract deviations требуют решения пользователя. Полные факты, hash/anchors и ограничения — @AGENTS.md и `.autopilot/2026-09-10-autopilot-pathing-hardening--wip/governance-hook-diagnostic.json`.
- Fresh verification: 24 tests in 7.253s OK, check-only OK, diff-check0, snapshot/served-state/helper parity и unchanged global-hook hash подтверждены; это не D01 repair или GO.
## Checkpoint 2026-09-17 — согласованный контракт восстановлен

- G01 CI/local identity согласован, G02 hook repair завершён 45/45 safe decision checks; backup/report вне Git, не full live Codex E2E. Brief дополнен реальной цитатой; остальной scope сохранён.
- Goal active / development HEAD6265e03; spec amendment выполнен, R01 не deferred. Independent G2 прошёл missing0/half0/extra0; g2-agreed-contract-coverage.md. Старый blind NO_GO не становится GO.
- T06/T07 parallel disjoint wave5, integration T04 wave6; следующий gate G3. Код/commit/push/main/PR пока не менялись. Connected global skill copy ещё старая, установка не обновлялась.
- Dashboard --no-serve/state+snapshot HTTP equality подтверждены; display queued. Dated unit24/8.293s и check-onlyOK — dashboard-refresh-checkpoint.json, не native CI proof. Полный актуальный контекст — @AGENTS.md.

- Current host metadata: GPT-5.6 Sol / effort max подтверждены latest turn_context; три начальных context были medium, поэтому весь прежний цикл не объявляется max. Sanitized host-model-verification.json в current run хранит источник/агрегат без prompts/credentials. G3 passed32/7, T06/T07 implementation started; snapshot/state HTTP200 equality confirmed, visible render NOT_RUN.

- T06 local acceptance: root full33/OK (T06+4, uncommitted T07+5; beforewave24), exact full-repo flake80 и measureOK; independent Manifest+Spec/Craft clean, baseline regression13 failing subtests/0errors. Recorded unknown PID не инициирует duplicate/rewrite; actual server cleanup не выполнялся. Native Actions и полный release pending; t06-local-verification.json.

- T07 local gate: root full33/OK in10.553s, exactlint0/measureOK; independent native5 Windows PASS и review clean. Workflow native matrix3 готова, но externalCI3.11/20 ещё NOT_RUN. Live repaired sync повторён3 раза: honest unknown-ownership warning, registry hash/PID unchanged, loopback200; это не доказательство ownership/полного process inventory. t07-local-verification.json/server-query-recheck.json.

<!-- autopilot:end -->
