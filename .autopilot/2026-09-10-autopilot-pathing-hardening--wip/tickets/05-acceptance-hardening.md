# 05 — Усиление доказательств финальной приемки

**Requirements:** R10, R12, R15, R16, R19, R21, R22, R23, R24
**Blocked by:** 01, 02, 03
**Зона:** `tools/measure-run.py`, `skills/autopilot/tools/sync.py`, `skills/autopilot/phases/dashboard-template.html`, соответствующие tests и runtime copies
**Волна:** 4
**Status:** done

## Что должно заработать

Финальная приемка должна опираться на ненулевые JSONL-oracles, реальный subprocess из произвольного `cwd`, измеренный baseline query count и строгий zero-query fast path. Dashboard обязан корректно показывать как структурированный, так и исторический строковый результат тестов. `sync.py` не должен завершать неучтенный `http.server` только по совпадению каталога.

## Критерии приемки

- [x] Mixed malformed JSONL сохраняет ненулевые метрики валидной строки.
- [x] `--check-only` проходит из произвольного `cwd`, а default logs root не зависит от него.
- [x] Cached dashboard tick делает ровно `0` selector queries; baseline queries измеряются.
- [x] Ticket tests не показывают `undefined` для legacy string и сохраняют object-format; все строковые поля экранируются.
- [x] Неучтенный same-directory server никогда не завершается; launch привязан к `127.0.0.1` и точному run directory.
- [x] Workflow возвращает заданные `name`/job и сохраняет только доказанные repo-aware отклонения.
- [x] Полный локальный gate зеленый; отдельный commit готовится оркестратором в `development`.

## Источник

Phase 8 craft triage и наблюдаемое отображение актуального dashboard.

## Доказательства

- Full suite: `24 tests`, `OK`; focused dashboard: `5 tests`, `OK`.
- Root independent gate: benchmark `532.45ms <= 766.90ms`, DOM queries `0/15000`; measure check и compileall — exit `0`.
- Craft review: `PASS`, BLOCKER/MAJOR нет; оба MINOR закрыты formatter escaping и финальным обновлением памяти.
- Source/runtime parity для dashboard и sync — `True`.
- Live loopback HTTP dashboard: соседний `state.js`, `undefinedTests=false`, console errors/warnings `[]`.
- `flake8` остается `NOT_RUN` локально до GitHub Actions; реальные POSIX/browser release gates не подменяются unit tests.
