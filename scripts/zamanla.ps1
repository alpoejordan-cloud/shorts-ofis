# Ofisi Windows Görev Zamanlayıcı'ya ekler:
#  - Her gece 02:30: üretim + yükleme (python -m ofis gunluk)
#  - Her sabah 08:30: telafi (yarım kalan işler)
#  - Her gün 14:00: onaylananları yükleme (gün içinde onayladıkların için)
#  - Her pazartesi 09:00: haftalık rapor
# Çalıştır:  powershell -ExecutionPolicy Bypass -File scripts\zamanla.ps1
$ErrorActionPreference = "Stop"
$kok = Split-Path $PSScriptRoot -Parent
$py = Join-Path $kok ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { throw "Önce scripts\kurulum.ps1 çalıştır." }

function Gorev($ad, $komut, $tetik) {
    $eylem = New-ScheduledTaskAction -Execute $py -Argument "-m ofis $komut" -WorkingDirectory $kok
    $ayar = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopIfGoingOnBatteries -AllowStartIfOnBatteries `
        -ExecutionTimeLimit (New-TimeSpan -Hours 6) -WakeToRun
    Register-ScheduledTask -TaskName $ad -Action $eylem -Trigger $tetik -Settings $ayar -Force | Out-Null
    Write-Host "[eklendi] $ad"
}

Gorev "ShortsOfis - Gunluk uretim" "gunluk" (New-ScheduledTaskTrigger -Daily -At 02:30)
# Gece işi yarım kalırsa (elektrik, Ollama hatası) sabah yeniden dener; hedef dolmuşsa hiçbir şey üretmez
Gorev "ShortsOfis - Sabah telafi" "gunluk" (New-ScheduledTaskTrigger -Daily -At 08:30)
Gorev "ShortsOfis - Ogle yukleme" "yukle" (New-ScheduledTaskTrigger -Daily -At 14:00)
Gorev "ShortsOfis - Haftalik rapor" "rapor" (New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At 09:00)
# Kampanya klipleri yayına girince 30 dk içinde Content Rewards'a gönderilmeli: 5 dakikada bir kontrol + bildirim
Gorev "ShortsOfis - Kampanya hatirlatici" "hatirlat" (New-ScheduledTaskTrigger -Once -At (Get-Date) `
    -RepetitionInterval (New-TimeSpan -Minutes 5))
Write-Host "`nZamanlama tamam. Görevleri 'Görev Zamanlayıcı' uygulamasında görebilirsin." -ForegroundColor Green
