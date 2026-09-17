# Повторная независимая проверка покрытия спецификации

Дата: 2026-09-16T16:02:20.9101715+03:00. Checker: `/root/t06_spec_coverage`.

Получены ровно полный `2026-09-10-brief.md` и revised `spec.md`. Manifest/interfaces/tickets/source/history не открывались. Это coverage G2, не проверка реализации и не финальная приёмка.

Результат: **missing 6 / half-covered 4 / extra 0**.

## Отсутствующее или заменённое

1. Требование ядра GPT-5.6 Sol/reasoning заменено ограничением хоста (§10).
2. Требование глобального имени заменено repo-local (§2).
3. Требование точного глобального email заменено noreply (§§2,10).
4. Требование всего строгого CI template заменено adapted YAML (§9).
5. Требование авторизации сессией для всех clone операций исключено для public upstream clone (§8).
6. Не закреплён обязательный первый этап создания workflow.

## Половинное покрытие

1. Нет полного целевого контракта root determination для любой ОС, описана карта существующих anchors и ограничений.
2. Охват import analysis назван двумя runtime файлами, но полная папка inventory не предъявлена checker-у.
3. Нет обязательного момента немедленного создания/переключения development после migration.
4. Нет явного финального действия записи состояния непосредственно в main/AGENTS.md.

## Фактическая реакция

Предложена доработка spec, сохраняющая все обязательства и отделяющая current deviations от целевого контракта. `apply_patch` остановлен **до выполнения** PreToolUse governance hook с сообщением `Destructive command blocked by governance hook`. Это была документация с literals из исходного брифа; никакие команды, global config или remote refs не выполнялись и не изменялись.

Патч не повторён через другой инструмент или обфускацию текста. Заблокированное исправление **не находится в spec** и не считается выполненным. Требуется необходимое явное разрешение/корректная обработка документального текста и решение по исходным deviations, не автоматическое снятие требований.

T06 executor соблюдал read-only edit gate и вернул BLOCKED: FILES none, focused10/full24/check-only OK, exact flake8 approved rerun0; новых interfaces/source edits нет. Source instability D01 остаётся неустранённой. Pending stages/ticket и failed G2 отражены в state; source/runtime copy и реальные серверы сохранены.

## Отдельные доказательства inventory

Авторский read-only `rg --files tools skills/autopilot/tools` предъявил ровно `tools/measure-run.py` и `skills/autopilot/tools/sync.py`. Runtime `.autopilot/sync.py` byte-identical canonical helper. Это фактический inventory relevant folders, но не переписывает независимый G2 verdict и не делает blocked spec amendment исполненной.

No GO, main/PR/merge, global changes, commit/push или 100% completion здесь не утверждаются.
