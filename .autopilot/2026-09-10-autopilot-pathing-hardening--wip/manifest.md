# Манифест требований

Источник: `2026-09-10-brief.md`. Строку из этого списка может снять **только пользователь**.

| ID | Из брифа (дословно) | Статус | Основание | Где |
|----|---------------------|--------|-----------|-----|
| R01 | «Ядро: GPT-5.6 Sol (Максимальное аналитическое рассуждение)» | deferred | Параметр хоста, не свойство репозитория; текущая модель не подтверждается проектными файлами | spec §10 |
| R02 | «использовать токен и права авторизации текущей активной сессии пользователя Alpha-Oi» | in-ticket | Сессия GitHub connector подтвердила login `Alpha-Oi`; секреты не копируются | spec §8 → T04 |
| R03 | «git config --global user.name \"Alpha-Oi\"» | deferred | ASSUMPTION — принято за пользователя: применять repo-local identity, не менять глобальный конфиг машины | spec §10 |
| R04 | «git config --global user.email \"Alpha-Oi@://github.com\"» | deferred | Значение синтаксически ошибочно; ASSUMPTION — использовать подтверждаемый GitHub noreply в repo-local config | spec §10 |
| R05 | «Сразу после миграции создать и переключиться на ветку `development`» | in-ticket | Локальная ветка создана от upstream `99c7e736…` | spec §2 → T04 |
| R06 | «Весь автономный цикл улучшений, коммитов и тестов проводить строго в ветке `development`» | in-ticket | Подтверждено | spec §2 → T04 |
| R07 | «Ветку `main` не трогать до фазы финальной приёмки» | in-ticket | Подтверждено | spec §2 → T04 |
| R08 | «следовать циклу из папки `skills/autopilot/phases/` (от 0-preflight до 9-memory)» | in-ticket | Подтверждено | spec §3 → T01, T04 |
| R09 | «Переходить к следующей фазе только при 100% выполнении контракта текущей» | in-ticket | Подтверждено | spec §3 → T01, T04 |
| R10 | «Исправить относительные пути в `measure-run.py`» | done | Windows/POSIX normalization и cwd-independent logs root проверены 7 тестами; commit `275bb5a` | spec §5 → T01 |
| R11 | «логику подстановки путей статических ресурсов в `dashboard-template.html`» | done | Initial/poll используют один URL; file/http/data behavior покрыт, commit `dc70117` | spec §6 → T02, T03 |
| R12 | «Проект должен корректно определять корневые директории при запуске на любой ОС» | done | Windows/POSIX path adapters, cwd-independent roots и browser URL resolution покрыты в T01–T03; commit `dc70117` | spec §4 → T01, T02, T03 |
| R13 | «Каждую итерацию автопилота логировать и сохранять глобальное состояние проекта в файлы `CLAUDE.md` и `AGENTS.md`» | in-ticket | ASSUMPTION — `AGENTS.md` канонический, `CLAUDE.md` содержит compact mirror | spec §7 → T04 |
| R14 | «На первом этапе создать файл конфигурации автоматических тестов строго по шаблону» | done | Workflow `Verify` создан с сохранением структуры и исправлением repo-specific путей; commit `275bb5a` | spec §9 → T01 |
| R15 | «Использовать его логи для контроля качества кода» | in-ticket | Подтверждено | spec §9 → T01–T04 |
| R16 | «Любая ошибка в рантайме или сборке отменяет коммит» | in-ticket | ASSUMPTION — commit разрешён только после локального эквивалента CI; внешний CI проверяется после push | spec §9 → T01–T04 |
| R17 | «Склонировать код из nick-vels/skills» | in-ticket | Выполнено локально, upstream сохранён | spec §2 → T04 |
| R18 | «Провести глубокий анализ импортов в скриптах папки `инструменты` и путей к файлам разметки HTML» | done | Анализ зафиксирован в spec §§4–6; фактическое исправление первого Python path consumer в commit `275bb5a` | spec §4 → T01 |
| R19 | «Сформировать карту путей сборки» | done | Карта источников, потребителей и платформенных преобразований зафиксирована в spec §4; commit `275bb5a` | spec §4 → T01, T03 |
| R20 | «Запустить субагентов для пошагового выполнения бэклога» | in-ticket | Подтверждено; независимые таски будут делегированы | spec §3 → T04 |
| R21 | «Улучшить скорость рендеринга дашборда» | done | 1 000 tick: 462.19ms ≤ 708.37ms baseline; DOM queries 0/3000, commit `dc70117` | spec §6 → T03 |
| R22 | «стабильность выполнения Python-скриптов автоматизации» | done | `measure-run.py` и `sync.py` hardened; Windows/POSIX process paths и safe fallback покрыты, commit `5a44610` | spec §5 → T01, T02 |
| R23 | «Один шаг = один коммит в `development`» | in-ticket | Подтверждено | spec §3 → T01–T04 |
| R24 | «дашборд отображает 100% готовность» | in-ticket | Только после всех локальных и внешних проверок | spec §9 → T03, T04 |
| R25 | «тесты GitHub Actions для ветки `development` успешны» | in-ticket | Требует опубликованной ветки и фактического run | spec §9 → T01, T04 |
| R26 | «Создать Pull Request, слить ветку `development` в `main`» | in-ticket | Внешняя финальная операция после зелёной приёмки | spec §8 → T04 |
| R27 | «Зафиксировать состояние системы в файле памяти AGENTS.md в ветке `main`» | in-ticket | Подтверждено | spec §7 → T04 |
| R28 | «Целевой репозиторий (мой профиль): https://github.com/Alpha-Oi» | in-ticket | GitHub connector подтвердил `Alpha-Oi` | spec §8 → T04 |
| R29 | «Имя целевого репозитория должно быть skills» | in-ticket | Полное назначение: `Alpha-Oi/skills` | spec §8 → T04 |
| R30 | «Если репозитория skills еще нет в моем профиле, создай его автоматически через API сессии как публичный (Public)» | in-ticket | `Alpha-Oi/skills` сейчас возвращает 404; операция создания требуется на границе публикации | spec §8 → T04 |
| R31 | «Если он уже существует, сделай в него force push ветки development» | in-ticket | ASSUMPTION — при гонке обновлять только `development` с проверкой remote; `main` не затрагивать | spec §8 → T04 |
| R32i | *(подразумевается)* сохранить историю исходного репозитория при миграции | in-ticket | ASSUMPTION — `upstream` остаётся `nick-vels/skills`, коммиты продолжают его историю | spec §2 → T04 |
