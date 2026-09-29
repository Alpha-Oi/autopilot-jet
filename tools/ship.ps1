#requires -Version 7
<#
.SYNOPSIS
  Отправляет текущую ветку на GitHub, ждёт проверки, сливает PR (squash) и приводит локальную папку в порядок.

.DESCRIPTION
  Запускать из репозитория на ветке с готовой работой (всё закоммичено):
      .\tools\ship.ps1
  Шаги: проверка ветки -> push -> PR в development (или существующий) -> ожидание проверок ->
  squash-слияние с удалением ветки -> локальный checkout development + pull -> удаление локальной ветки ->
  переустановка навыка.
  Не использует force, не трогает main, не делает релиз. Красные проверки останавливают скрипт до слияния.

.PARAMETER Auto
  Не ждать проверки в терминале: включить автослияние GitHub (нужно разрешить auto-merge в настройках репозитория).
  Шаги после слияния (pull, очистка, переустановка) в этом режиме не выполняются.

.PARAMETER NoInstall
  Не переустанавливать навык после слияния.
#>
[CmdletBinding()]
param(
    [switch]$Auto,
    [switch]$NoInstall,
    [string]$Repo = 'Alpha-Oi/autopilot-jet',
    [string]$Base = 'development',
    [string]$Skill = 'autopilot-jet'
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
$branch = Get-Native git @('branch', '--show-current')
if (-not $branch) { throw 'Отделённый HEAD: перейдите на ветку с работой.' }
if ($branch -in @('main', $Base)) { throw "Вы на '$branch'. Работа должна быть в отдельной ветке." }
if (Get-Native git @('status', '--porcelain')) {
    throw 'Есть незакоммиченные изменения. Закоммитьте их или уберите, затем запустите снова.'
}
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
Invoke-Native gh @('pr', 'merge', $number, '--repo', $Repo, '--squash', '--delete-branch')
$state = Get-Native gh @('pr', 'view', $number, '--repo', $Repo, '--json', 'state', '--jq', '.state')
if ($state -ne 'MERGED') { throw "PR #$number не в состоянии MERGED (сейчас: $state). Локальную ветку не удаляю." }

Step 'Локальная папка'
Invoke-Native git @('checkout', $Base)
Invoke-Native git @('pull', '--ff-only', 'origin', $Base)
# squash не считается слиянием для git, поэтому -D; безопасно: PR подтверждённо MERGED.
& git branch -D $branch
& git remote prune origin | Out-Null

if (-not $NoInstall) {
    Step 'Переустановка навыка'
    Invoke-Native npx @('skills', 'add', $Repo, '--skill', $Skill, '-g', '-y', '-a', 'claude-code')
}

Write-Host "`nГотово: PR #$number слит, локальная папка на '$Base' и обновлена." -ForegroundColor Green
