# Ofisi Windows Görev Zamanlayıcı'ya ekler (kullanıcı 18:00'e kadar işte: gündüz ağır iş yok):
#  - Her akşam 18:30: üretim + kalite + zamanlanmış yükleme (o gecenin geç slotları: Tech 23:00, GTA 02:00)
#  - Her gece 02:30: üretim + kalite + zamanlanmış yükleme (ertesi akşam slotları: Tech 17:00, GTA 19:00)
#    Her çalışma önce yarım kalan işleri bitirir (telafi) ve hazır videoları yükler.
#  - Pazartesi 18:15: haftalık rapor
#  - 5 dakikada bir: kampanya gönderim hatırlatıcısı (hafif)
# Çalıştır:  powershell -ExecutionPolicy Bypass -File scripts\zamanla.ps1
$ErrorActionPreference = "Stop"
$kok = Split-Path $PSScriptRoot -Parent
$py = Join-Path $kok ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { throw "Önce scripts\kurulum.ps1 çalıştır." }

function Gorev($ad, $komut, $tetik) {
    $eylem = New-ScheduledTaskAction -Execute $py -Argument "-m ofis $komut" -WorkingDirectory $kok
    $ayar = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopIfGoingOnBatteries -AllowStartIfOnBatteries `
        -ExecutionTimeLimit (New-TimeSpan -Hours 6) -WakeToRun -Priority 7  # 7 = normalin altı: bilgisayar yavaşlamasın
    Register-ScheduledTask -TaskName $ad -Action $eylem -Trigger $tetik -Settings $ayar -Force | Out-Null
    Write-Host "[eklendi] $ad"
}

# eski gündüz görevleri kaldırılır
foreach ($eski in "ShortsOfis - Sabah telafi", "ShortsOfis - Ogle yukleme", "ShortsOfis - Ogle uretim") {
    if (Get-ScheduledTask -TaskName $eski -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $eski -Confirm:$false
        Write-Host "[kaldırıldı] $eski"
    }
}
Gorev "ShortsOfis - Aksam uretim" "gunluk" (New-ScheduledTaskTrigger -Daily -At 18:30)
Gorev "ShortsOfis - Gunluk uretim" "gunluk" (New-ScheduledTaskTrigger -Daily -At 02:30)
Gorev "ShortsOfis - Haftalik rapor" "rapor" (New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At 18:15)
# Kampanya klipleri yayına girince 30 dk içinde Content Rewards'a gönderilmeli: 5 dakikada bir kontrol + bildirim
Gorev "ShortsOfis - Kampanya hatirlatici" "hatirlat" (New-ScheduledTaskTrigger -Once -At (Get-Date) `
    -RepetitionInterval (New-TimeSpan -Minutes 5))
Write-Host "`nZamanlama tamam. Görevleri 'Görev Zamanlayıcı' uygulamasında görebilirsin." -ForegroundColor Green
