# Compile the in-repo thesis chapters (requires MiKTeX or TeX Live).
# Validation without TeX: .\.venv\Scripts\python.exe -m scripts.validate_thesis_tex

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot/..

$pdflatex = Get-Command pdflatex -ErrorAction SilentlyContinue
if (-not $pdflatex) {
    $candidate = "$env:LOCALAPPDATA\Programs\MiKTeX\miktex\bin\x64\pdflatex.exe"
    if (Test-Path $candidate) { $pdflatex = $candidate } else { throw "pdflatex not found; install MiKTeX or TeX Live" }
} else {
    $pdflatex = $pdflatex.Source
}

& $pdflatex -interaction=nonstopmode main.tex
& bibtex main
& $pdflatex -interaction=nonstopmode main.tex
& $pdflatex -interaction=nonstopmode main.tex
Write-Host "Built main.pdf"
