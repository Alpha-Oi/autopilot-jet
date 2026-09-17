# Phase 8 — финальная triage

| Finding | Решение | Основание / результат |
|---|---|---|
| Нерабочие npm/path строки исходного CI | Report / user decision | T01/T05 дают зелёный CI, но это не буквальный шаблон. Blind отмечает частично; R14 возвращён в in-ticket, требование не снято. skills-lock.json существует, но это skills registry, не npm package-lock. |
| Нужны baseline и бюджет dashboard regression | Fix now | T05 измеряет baselineQueries и требует cached tickQueries=0; browser benchmark — отдельный gate. |
| Ошибочный email и global Git config | Report | Используется repo-local Alpha-Oi + подтвержденный noreply; global config не меняется. |
| AGENTS канон / CLAUDE указатель | Fix now | Memory agent записал фактическое состояние физически в оба файла: AGENTS — канон, CLAUDE — compact mirror; стандартные marker-блоки и текст вне них сохранены. |
| 100% до CI/blind acceptance | Report / user decision | Current development CI success, blind NO_GO; реальный UI показывает 79%. 100% не выставляется до фактического завершения. |
| Upstream history / main boundary | Report | main остается на upstream base; первая публикация только development. |
| Mixed malformed JSONL с нулевым oracle | Fix now | T05 сохраняет ненулевые usage/context/time metrics. |
| Произвольный cwd без subprocess-test | Fix now | T05 запускает CLI из системного temp cwd. |
| Session selection test mocks internals | Drop | Тест вызывает public main(argv); filesystem mocks изолируют выбор сессии, observed order invariance доказан. |
| root=None default не закреплен | Fix now | T05 проверяет Path.home root при двух cwd values. |
| Same-directory unrecorded process может быть завершен | Fix now | T05 убирает destructive discovery/kill; exact recorded PID используется только для reuse. |
| Windows case/separator test без adapter | Drop / report limit | Windows gate и Ubuntu CI прошли; POSIX adapter покрыт. Native macOS и буквальная любая ОС остаются непроверенными, R12 in-ticket. |
| Нет exact loopback launch oracle | Fix now | T05 утверждает полный Popen argv с 127.0.0.1 и exact directory. |
| Hardcoded baseline query count | Fix now | T05 измеряет 15000 baseline queries. |
| Порог разрешает queries вместо zero-query contract | Fix now | T05 assert tickQueries==0. |
| Node VM не является real browser trace | Fix now | Root real HTTP DOM harness прошёл: 8 stages / 100 tickets / 94 clocks, 570.7ms <= 741.5ms, queries 0/15000. Blind отдельно подтвердил реальный UI и свежий Node VM benchmark; Ubuntu CI success. Эти разные evidence не подменяют друг друга. |
| T04 local readiness до flake8/CI | Drop | Full repo local flake8 прошёл, но T04 остаётся in-progress до фактического внешнего CI/release gate. |
| ticket03 done-with-concerns / state done | Fix now | Канонический status согласован: done. |
| Local flake8 отсутствует | Fix now | flake8 7.3.0 в изолированном venv; full repo CI args дают exit 0 / 0 violations. Current Ubuntu Actions lint также success. Production/global не менялись. |
| GitHub create/push/Actions/PR/merge pending | Report / user decision | Public target, development6265e03 и Actions35094887597 success подтверждены. Main отсутствует; API create-ref main отклонён до исполнения из-за NO_GO/100% gate. PR/merge не выполняются без решения пользователя. |
| Dashboard undefined test cells | Fix now | T05 formatter поддерживает legacy string и object-format. |
| Object passed/failed HTML injection | Fix now | T05 экранирует обе object-format ветки; malicious regression green. |
| Memory содержит старые test counts | Fix now | Memory checkpoint обновлён до 24/10 перед release. |
| State blind NO-GO не виден в dashboard | Fix now | Завершённый независимый verdict сохранён: 31 строка брифа, 11 реализовано, 16 частично, 4 нет. Renderer-compatible blind fields и открытые расхождения обновлены. |
| Два agent-created temp dirs с sandbox ACL | Report | Точные пустые paths не staged; Remove-Item заблокирован governance hook, обход не выполняется. |
