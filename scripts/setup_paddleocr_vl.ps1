<#
Install PaddleOCR-VL in a separate environment.  The existing ppocrlabel
environment is deliberately left unchanged so its current OCR remains usable.
#>
param(
    [string]$Environment = "ppocrlabel-vl-runtime"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$targetPython = "D:\anaconda3\envs\$Environment\python.exe"

if (-not (Test-Path -LiteralPath $targetPython)) {
    Write-Host "Creating isolated $Environment environment..."
    conda create -y -n $Environment python=3.10 pip
}

Write-Host "Installing PaddleOCR-VL dependencies in $Environment..."
conda run -n $Environment python -m pip install --upgrade "paddleocr[doc-parser]==3.7.0"
conda run -n $Environment python -c "from paddleocr import PaddleOCRVL; print('PaddleOCRVL ready:', PaddleOCRVL.__name__)"

Write-Host "PaddleOCR-VL environment ready. Its model files download automatically on first use."
