<#
.SYNOPSIS
    One-command workstation setup for Windows: uv, Python 3.13, all dependencies in .venv, .env.

.DESCRIPTION
    Safe to re-run. Steps:
      1. install uv (official installer) if it is not on PATH;
      2. `uv sync --locked`: Python from .python-version + dependencies from uv.lock into .venv;
      3. scripts/bootstrap.py: create .env for the participant, git hooks, DB connectivity check.

    This file is ASCII-only on purpose: Windows PowerShell 5.1 reads BOM-less files
    as ANSI, and UTF-8 Cyrillic bytes can turn into quote characters and break parsing.
    Russian messages are printed by bootstrap.py instead.

.PARAMETER Dev
    Participant letter: a (core), b (domain), c (web). Picks the personal database.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\setup.ps1 -Dev b
#>
param(
    [ValidateSet("a", "b", "c")]
    [string]$Dev
)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "==> uv not found, installing from https://astral.sh/uv ..."
    powershell -NoProfile -ExecutionPolicy ByPass -Command "irm https://astral.sh/uv/install.ps1 | iex"
    # The installer updates PATH for new windows only; make uv visible in this one too.
    $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        throw "uv is still not on PATH. Open a new terminal and run this script again."
    }
}

Write-Host "==> uv sync: Python + dependencies into .venv"
uv sync --locked
if ($LASTEXITCODE -ne 0) {
    throw "uv sync failed. If uv.lock is out of date, run 'uv lock' and commit it."
}

$bootstrapArgs = @()
if ($Dev) { $bootstrapArgs += @("--dev", $Dev) }
uv run python scripts/bootstrap.py @bootstrapArgs
exit $LASTEXITCODE
