# UAV auth evaluation helpers for Windows PowerShell
# Usage: .\scripts\uav.ps1 setup
param(
    [Parameter(Position = 0, Mandatory = $true)]
    [ValidateSet(
        "setup", "besu-up", "besu-status", "deploy-contract", "init-identities",
        "ui", "smoke-test", "test", "lint", "besu-down", "reset-local", "run-chapter5"
    )]
    [string]$Command
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$VenvPy = Join-Path $Root ".venv\Scripts\python.exe"
$Py = if (Test-Path $VenvPy) { $VenvPy } else { "python" }
Write-Host "Using Python: $Py"

switch ($Command) {
    "setup" {
        & $Py -m pip install -r requirements.txt
        & $Py -m app.cli setup
    }
    "besu-up" { & $Py -m scripts.besu_network up }
    "besu-status" { & $Py -m scripts.besu_network status }
    "deploy-contract" { & $Py -m app.cli deploy-contract }
    "init-identities" { & $Py -m app.cli init-identities --count 10 }
    "ui" { & $Py -m streamlit run streamlit_app.py }
    "smoke-test" { & $Py -m app.cli smoke-test }
    "test" {
        & $Py -m pytest tests -q --ignore=tests/test_blockchain_integration.py
        & $Py -m pytest tests/test_blockchain_integration.py -q --tb=short
    }
    "lint" {
        & $Py -m ruff check app tests scripts
        & $Py -m black --check app tests scripts streamlit_app.py
    }
    "besu-down" { & $Py -m scripts.besu_network down }
    "reset-local" { & $Py -m app.cli reset-local --confirm }
    "run-chapter5" { & $Py -m scripts.run_chapter5_matrix }
}
