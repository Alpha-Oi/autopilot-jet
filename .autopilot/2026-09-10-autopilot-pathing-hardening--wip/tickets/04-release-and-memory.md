# 04 — Интеграционная приёмка, память и публикация

**Требования:** R02, R05, R06, R07, R08, R09, R13, R15, R16, R17, R20, R23, R24, R25, R26, R27, R28, R29, R30, R31, R32i
**Blocked by:** 01, 02, 03
**Зона:** `AGENTS.md`, `CLAUDE.md`, `.autopilot/`, GitHub release boundary
**Волна:** 3
**Status:** ready

## Что должно заработать

Полный локальный gate и blind acceptance зелёные; memory files отражают завершённый код; Public `Alpha-Oi/skills` получает `development`, успешный Actions run, PR и merge в `main`. Upstream history и target visibility/refs проверены API.

## Из брифа, дословно

> «Убедиться, что дашборд отображает 100% готовность, а тесты GitHub Actions для ветки `development` успешны.»
> «Создать Pull Request, слить ветку `development` в `main`.»
> «Зафиксировать состояние системы в файле памяти AGENTS.md в ветке `main`.»

## Разделы спецификации

§§2–3, 7–13.

## Критерии приёмки

- [ ] Полный локальный gate и независимый blind acceptance зелёные; dashboard ещё не показывает 100% до их завершения.
- [ ] `AGENTS.md` и compact mirror в `CLAUDE.md` обновлены реальными командами/состоянием.
- [ ] `Alpha-Oi/skills` существует как Public, `origin` точен, `development` опубликован авторизацией сессии `Alpha-Oi`.
- [ ] GitHub Actions на `development` завершён успешно; PR `development -> main` создан и слит.
- [ ] Remote `main`, история upstream, финальный `AGENTS.md` и 100% dashboard подтверждены после merge.
