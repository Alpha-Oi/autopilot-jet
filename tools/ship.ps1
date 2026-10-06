#requires -Version 7
<#
.SYNOPSIS
  Отправляет текущую ветку на GitHub, ждёт проверки, сливает PR (squash) и приводит локальную папку в порядок.

.DESCRIPTION
  Запускать из папки репозитория:
      .\tools\ship.ps1                       # ветка, на которой вы стоите (всё закоммичено)
      .\tools\ship.ps1 -Branch feat/имя      # готовая ветка, на которую переключаться не нужно
  Шаги: проверка ветки -> push -> PR в development (или существующий) -> ожидание проверок ->
  squash-слияние с удалением ветки -> обновление локальной development (в том числе в отдельном рабочем
  дереве) -> удаление локальной ветки -> переустановка навыка.
  Не использует force, не трогает main, не делает релиз. Красные проверки останавливают скрипт до слияния.

.PARAMETER Branch
  Ветка для отправки. По умолчанию — текущая. С -Branch чистота рабочего дерева не проверяется:
  уходят только коммиты этой ветки.

.PARAMETER Auto
  Не ждать проверки в терминале: включить автослияние GitHub (нужно разрешить auto-merge в настройках репозитория).
  Шаги после слияния (pull, очистка, переустановка) в этом режиме не выполняются.

.PARAMETER NoInstall
  Не переустанавливать навык после слияния.
#>
[CmdletBinding()]
param(
    [string]$Branch,
    [switch]$Auto,
    [switch]$NoInstall,
    [string]$Repo = 'Alpha-Oi/autopilot-jet',
    [string]$Base = 'development',
    [string]$Skill = 'autopilot-jet',
    # Версия CLI закреплена: `npx skills` без версии каждый раз тянет последнюю и запускает её с -y на вашей машине.
    [string]$SkillsCli = 'skills@1.7.0'
)

$ErrorActionPreference = 'Stop'

function Step([string]$text) { Write-Host "`n== $text" -ForegroundColor Cyan }

# Запускает внешнюю команду и падает, если код возврата не 0.
function Invoke-Native {
    param([Parameter(Mandatory)][string]$File, [string[]]$Arguments)
    & $File @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Команда завершилась с ошибкой ($LASTEXITCODE): $File $($Arguments -join ' ')"
    }
}

# Запускает внешнюю команду и возвращает её вывод одной строкой (ошибка -> исключение).
function Get-Native {
    param([Parameter(Mandatory)][string]$File, [string[]]$Arguments)
    $out = & $File @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Команда завершилась с ошибкой ($LASTEXITCODE): $File $($Arguments -join ' ')"
    }
    return ($out -join "`n").Trim()
}

Step 'Проверка ветки'
$root = Get-Native git @('rev-parse', '--show-toplevel')
Set-Location $root
$current = Get-Native git @('branch', '--show-current')
if ($Branch) {
    $branch = $Branch
    & git rev-parse --verify --quiet "refs/heads/$branch" | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Локальной ветки '$branch' нет." }
}
else {
    $branch = $current
    if (-not $branch) { throw 'Отделённый HEAD: перейдите на ветку с работой или укажите -Branch.' }
    if (Get-Native git @('status', '--porcelain')) {
        throw 'Есть незакоммиченные изменения. Закоммитьте их или уберите, затем запустите снова.'
    }
}
if ($branch -in @('main', $Base)) { throw "Ветка '$branch' не подходит: работа должна быть в отдельной ветке." }
Invoke-Native gh @('auth', 'status')
Write-Host "Ветка: $branch"

Step 'Отправка на GitHub'
Invoke-Native git @('push', '-u', 'origin', $branch)

Step 'Pull Request'
$number = ''
& gh pr view $branch --repo $Repo --json number --jq '.number' 2>$null | ForEach-Object { $number = "$_".Trim() }
if ($LASTEXITCODE -ne 0) { $number = '' }
if ($number) {
    Write-Host "PR уже существует: #$number"
}
else {
    Invoke-Native gh @('pr', 'create', '--repo', $Repo, '--base', $Base, '--head', $branch, '--fill')
    $number = Get-Native gh @('pr', 'view', $branch, '--repo', $Repo, '--json', 'number', '--jq', '.number')
    Write-Host "Создан PR #$number"
}

if ($Auto) {
    Step 'Автослияние GitHub'
    Invoke-Native gh @('pr', 'merge', $number, '--repo', $Repo, '--squash', '--delete-branch', '--auto')
    Write-Host "Автослияние включено для PR #$number. Когда проверки пройдут, GitHub сольёт PR сам."
    Write-Host 'Потом: git checkout development; git pull; переустановка навыка.'
    return
}

Step 'Проверки'
# Сразу после создания PR проверок может ещё не быть: подождать их появления (до ~60 с).
$registered = $false
for ($i = 0; $i -lt 6 -and -not $registered; $i++) {
    $probe = (& gh pr checks $number --repo $Repo 2>&1) -join "`n"
    if ($probe -match 'no checks reported') { Start-Sleep -Seconds 10 } else { $registered = $true }
}
if (-not $registered) { throw 'Проверки не появились за минуту. Посмотрите PR на GitHub.' }
& gh pr checks $number --repo $Repo --watch
if ($LASTEXITCODE -ne 0) { throw "Проверки PR #$number не прошли. Слияния не будет." }

Step 'Слияние'
# gh при --delete-branch сам пытается переключиться с текущей ветки; уходим с неё заранее, без смены файлов.
if ($current -eq $branch) { Invoke-Native git @('switch', '--detach'); $current = '' }
Invoke-Native gh @('pr', 'merge', $number, '--repo', $Repo, '--squash', '--delete-branch')
$state = Get-Native gh @('pr', 'view', $number, '--repo', $Repo, '--json', 'state', '--jq', '.state')
if ($state -ne 'MERGED') { throw "PR #$number не в состоянии MERGED (сейчас: $state). Локальную ветку не удаляю." }

Step 'Локальная папка'
Invoke-Native git @('fetch', 'origin', '--prune')
# squash не считается слиянием для git, поэтому -D; безопасно: PR подтверждённо MERGED.
& git branch -D $branch
# Обновляем локальную development: там, где она выбрана (своё или отдельное рабочее дерево), либо без checkout.
$wt = $null
$path = $null
foreach ($line in (& git worktree list --porcelain)) {
    if ($line -like 'worktree *') { $path = $line.Substring(9) }
    elseif ($line -eq "branch refs/heads/$Base") { $wt = $path }
}
if ($wt) {
    Write-Host "Обновляю $Base в $wt"
    Invoke-Native git @('-C', $wt, 'pull', '--ff-only', 'origin', $Base)
}
else {
    & git fetch origin "${Base}:${Base}"
    if ($LASTEXITCODE -ne 0) { Write-Warning "Локальную $Base не удалось обновить автоматически." }
}

if (-not $NoInstall) {
    Step 'Переустановка навыка'
    Invoke-Native npx @('--yes', $SkillsCli, 'add', $Repo, '--skill', $Skill, '-g', '-y', '-a', 'claude-code')
}

Write-Host "`nГотово: PR #$number слит, локальная $Base обновлена." -ForegroundColor Green
