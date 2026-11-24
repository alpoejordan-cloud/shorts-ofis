# Shorts Ofis kurulumu (Windows). PowerShell'de proje klasöründeyken çalıştır:
#   powershell -ExecutionPolicy Bypass -File scripts\kurulum.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

function Kur($id, $komut) {
    if (Get-Command $komut -ErrorAction SilentlyContinue) { Write-Host "[tamam] $komut zaten kurulu" }
    else {
        Write-Host "[kuruluyor] $id"
        winget install --id $id -e --accept-package-agreements --accept-source-agreements
    }
}

Kur "Python.Python.3.12" "python"
Kur "Gyan.FFmpeg" "ffmpeg"
Kur "Ollama.Ollama" "ollama"
Kur "Git.Git" "git"

# Yeni kurulan programların PATH'e girmesi için
$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")

if (-not (Test-Path ".venv")) { python -m venv .venv }
$py = ".\.venv\Scripts\python.exe"
& $py -m pip install --upgrade pip
& $py -m pip install -r requirements.txt

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "`n.env dosyası oluşturuldu. İçine PEXELS_API_ANAHTARI ve YOUTUBE_API_ANAHTARI yaz." -ForegroundColor Yellow
}

$model = (Select-String -Path ".env" -Pattern "^OLLAMA_MODEL=(.+)$").Matches.Groups[1].Value
if (-not $model) { $model = "qwen2.5:7b" }
Write-Host "Yapay zeka modeli indiriliyor: $model (birkaç GB, biraz sürebilir)"
ollama pull $model

& $py -m ofis sesleri-indir
& $py -m ofis doktor

Write-Host "`nKurulum bitti. Sıradaki adımlar docs\KURULUM.md dosyasında." -ForegroundColor Green
