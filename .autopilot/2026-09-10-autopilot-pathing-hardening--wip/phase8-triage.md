# Phase 8 — финальная triage

| Finding | Решение | Основание / результат |
|---|---|---|
| Нерабочие npm/path строки исходного CI | Drop | Исправлены T01; точные workflow name/job возвращены T05. |
| Нужны baseline и бюджет dashboard regression | Fix now | T05 измеряет baselineQueries и требует cached tickQueries=0; browser benchmark — отдельный gate. |
| Ошибочный email и global Git config | Report | Используется repo-local Alpha-Oi + подтвержденный noreply; global config не меняется. |
| AGENTS канон / CLAUDE указатель | Fix now | Memory agent записал фактическое состояние физически в оба файла: AGENTS — канон, CLAUDE — compact mirror; стандартные marker-блоки и текст вне них сохранены. |
| 100% до CI/blind acceptance | Report | State остается незавершенным; внешний gate обязателен. |
| Upstream history / main boundary | Report | main остается на upstream base; первая публикация только development. |
| Mixed malformed JSONL с нулевым oracle | Fix now | T05 сохраняет ненулевые usage/context/time metrics. |
| Произвольный cwd без subprocess-test | Fix now | T05 запускает CLI из системного temp cwd. |
| Session selection test mocks internals | Drop | Тест вызывает public main(argv); filesystem mocks изолируют выбор сессии, observed order invariance доказан. |
| root=None default не закреплен | Fix now | T05 проверяет Path.home root при двух cwd values. |
| Same-directory unrecorded process может быть завершен | Fix now | T05 убирает destructive discovery/kill; exact recorded PID используется только для reuse. |
| Windows case/separator test без adapter | Drop | Текущий gate выполняется на Windows с реальным ntpath; POSIX adapter покрыт unit tests и ожидает Ubuntu CI. |
| Нет exact loopback launch oracle | Fix now | T05 утверждает полный Popen argv с 127.0.0.1 и exact directory. |
| Hardcoded baseline query count | Fix now | T05 измеряет 15000 baseline queries. |
| Порог разрешает queries вместо zero-query contract | Fix now | T05 assert tickQueries==0. |
| Node VM не является real browser trace | Fix now | Real HTTP DOM harness прошёл: 8 stages / 100 tickets / 94 clocks; медианы 570.7ms <= 741.5ms, queries 0/15000; raw result сохранён отдельно. Ubuntu CI остаётся pending. |
| T04 local readiness до flake8/CI | Drop | Full repo local flake8 прошёл, но T04 остаётся in-progress до фактического внешнего CI/release gate. |
| ticket03 done-with-concerns / state done | Fix now | Канонический status согласован: done. |
| Local flake8 отсутствует | Fix now | flake8 7.3.0 в изолированном проверочном venv вне worktree; exact full repo CI parameters дают exit 0 / 0 violations. Production/global не менялись; Actions ещё не проверен. |
| GitHub create/push/Actions/PR/merge pending | Report | Требуется действующая API-авторизация Alpha-Oi; target name не подменяется. |
| Dashboard undefined test cells | Fix now | T05 formatter поддерживает legacy string и object-format. |
| Object passed/failed HTML injection | Fix now | T05 экранирует обе object-format ветки; malicious regression green. |
| Memory содержит старые test counts | Fix now | Memory checkpoint обновлён до 24/10 перед release. |
| State blind NO-GO не виден в dashboard | Fix now | checked/matched/mismatches согласованы с renderer; pending финальной повторной приёмки и отсутствующие внешние подтверждения показаны явно. |
| Два agent-created temp dirs с sandbox ACL | Report | Точные пустые paths не staged; Remove-Item заблокирован governance hook, обход не выполняется. |
