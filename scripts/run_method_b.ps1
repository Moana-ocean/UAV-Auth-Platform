# Method-B scale + ABBA runner (PowerShell)
# Prerequisite: Docker Desktop running (com.docker.service Started) and Besu up.

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..
$py = ".\.venv\Scripts\python.exe"
$root = "results/method_b_scale_20260903"

Write-Host "== Besu status =="
& $py -m scripts.besu_network status
& $py -m scripts.besu_network up

Write-Host "== Redeploy contract =="
& $py -m app.cli deploy-contract

Write-Host "== Scale-valid matrix (50 cells, fresh identities) =="
New-Item -ItemType Directory -Force -Path "$root\logs" | Out-Null
& $py -m scripts.run_chapter5_matrix `
  --only-phases scale-valid `
  --fresh-identities `
  --output-root $root `
  2>&1 | Tee-Object -FilePath "$root\logs\scale_matrix.log"

Write-Host "== Redeploy for ABBA ascending-n =="
& $py -m app.cli deploy-contract

Write-Host "== ABBA batches =="
& $py -m scripts.run_abba_batches `
  --fresh-identities `
  --output-root $root `
  2>&1 | Tee-Object -FilePath "$root\logs\abba.log"

Write-Host "== Export scale bundle =="
& $py -m scripts.export_chapter5_bundle `
  --runs-root "$root\runs" `
  --export-dir "$root\export"

Write-Host "DONE: $root\export"
